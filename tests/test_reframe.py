"""Tests for the 9:16 reframe maths - the crop window and the path it takes.

The detector tests use a public-domain portrait; see
``tests/fixtures/PORTRAIT.txt`` for where it came from. The video tests use a
clip built by ffmpeg; see ``tests/fixtures/TRACKER_CLIP.txt`` for why it is a
committed file instead of one the test writes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from s_q_ali_media_downloader.core import reframe

FIXTURES = Path(__file__).parent / "fixtures"
TRACKER_CLIP = FIXTURES / "tracker-clip.mp4"


def test_the_crop_window_is_exactly_nine_by_sixteen():
    """The window has to be 9:16 to the pixel, or the scale to 1080x1920
    stretches the picture by a fraction of a percent."""
    width, height = reframe.crop_window(1920, 1080)

    assert (width, height) == (594, 1056)
    assert width * 16 == height * 9


def test_a_720p_source_gets_a_720_crop():
    assert reframe.crop_window(1280, 720) == (396, 704)


def test_a_source_too_small_to_crop_vertically_is_refused():
    with pytest.raises(ValueError):
        reframe.crop_window(100, 20)


# --------------------------------------------------------------------------- #
# The letterbox: the window is cut from the picture, not the container
# --------------------------------------------------------------------------- #
def test_the_picture_is_read_out_of_what_cropdetect_reports():
    """ffmpeg says the same box for every frame of a letterboxed film; the
    answer is that box, in the pixels of the file it read."""
    report = (
        "[cropdetect_0 @ 0x1] x1:0 x2:3839 y1:256 y2:1901 w:3840 h:1646 x:0 y:256 "
        "pts:1 t:0.0 crop=3840:1646:0:256\n"
        "[cropdetect_0 @ 0x1] x1:2 x2:3836 y1:256 y2:1901 w:3834 h:1646 x:2 y:256 "
        "pts:2 t:0.2 crop=3834:1646:2:256\n"
        "[cropdetect_0 @ 0x1] x1:0 x2:3839 y1:256 y2:1901 w:3840 h:1646 x:0 y:256 "
        "pts:3 t:0.4 crop=3840:1646:0:256\n"
    )

    assert reframe.detect_picture_text(report) == (256, 1901)


def test_a_frame_that_is_all_picture_reports_the_whole_frame():
    assert reframe.detect_picture_text("crop=1920:1080:0:0\n") == (0, 1079)


def test_no_cropdetect_report_is_no_picture():
    assert reframe.detect_picture_text("ffmpeg said nothing useful") is None


def test_the_window_is_cut_from_the_picture_and_sits_inside_it():
    """A 3840x2160 container holding a 3840x1646 picture: the 9:16 window
    comes out of the 1646 rows, and starts where the picture starts."""
    chain = reframe.filter_chain("crop.cmd", 3840, 2160, box=(256, 1901))

    assert "crop@c=w=918:h=1632" in chain
    assert "scale=1080:1920" in chain
    # 256 + (1646 - 1632) // 2 = 263, and an odd offset shifts the chroma.
    assert "x=1460:y=262" in chain


def test_a_box_that_is_the_whole_frame_is_the_old_centred_crop():
    assert reframe.filter_chain("c.cmd", 1920, 1080) == reframe.filter_chain(
        "c.cmd", 1920, 1080, box=(0, 1079)
    )


def test_a_box_that_is_not_a_picture_keeps_the_whole_frame():
    """A strip of the frame is not a letterbox: a subtitle bar, or a decode
    that reported one dark row, would cut the picture to nothing."""
    assert reframe.filter_chain("c.cmd", 3840, 2160, box=(1000, 1039)) == reframe.filter_chain(
        "c.cmd", 3840, 2160
    )


def test_the_crop_x_is_clamped_inside_the_frame():
    assert reframe.clamp_x(-40, 1920, 594) == 0
    assert reframe.clamp_x(4000, 1920, 594) == 1920 - 594
    assert reframe.clamp_x(600, 1920, 594) == 600


def test_a_jump_in_the_detection_does_not_snap_the_camera():
    """A detector that moves the subject across the frame in one sample must
    not move the window with it in one step."""
    path = reframe.crop_path([100, 1000], 1920, 594, max_step=100)

    assert path == [100, 200]


def test_a_sample_without_a_detection_keeps_the_previous_position():
    path = reframe.crop_path([100, None, 300], 1920, 594, max_step=1000)

    assert path == [100, 100, 300]


def test_the_path_stays_inside_the_frame():
    path = reframe.crop_path([-40, 4000], 1920, 594, max_step=10_000)

    assert path == [0, 1920 - 594]
    assert all(0 <= x <= 1920 - 594 for x in path)


def test_the_crop_x_is_always_even():
    """An odd offset shifts the chroma by half a pixel."""
    path = reframe.crop_path([101, 202], 1920, 594)

    assert path == [100, 202]


def test_the_window_travels_at_most_a_quarter_of_its_width_per_sample():
    assert reframe.max_step_for(594) == 148


def test_the_command_file_holds_one_line_per_sample_in_time_order(tmp_path):
    command_file = tmp_path / "crop.cmd"

    reframe.write_command_file(
        command_file,
        [reframe.Sample(0.0, 100), reframe.Sample(1.5, 400)],
    )

    assert command_file.read_text(encoding="utf-8").splitlines() == [
        "0.000 crop@c x 100;",
        "1.500 crop@c x 400;",
    ]


def test_the_vertical_file_sits_next_to_the_original():
    assert (
        reframe.vertical_output_path("How to cook.mp4") == "How to cook_9x16.mp4"
    )


def test_the_filter_names_the_command_file_the_window_and_the_output_size():
    chain = reframe.filter_chain("crop.cmd", 1920, 1080)

    assert chain == (
        "sendcmd=f=crop.cmd,"
        # 662, not 663: the window sits here until the first command arrives,
        # and an odd offset shifts the chroma by half a pixel.
        "crop@c=w=594:h=1056:x=662:y=12,"
        "scale=1080:1920,setsar=1"
    )


def test_the_audio_is_copied_and_the_video_is_re_encoded():
    command = reframe.build_command(
        "ffmpeg", "in.mp4", "out.mp4", "sendcmd=f=crop.cmd"
    )

    assert command[command.index("-c:a") + 1] == "copy"
    assert command[command.index("-c:v") + 1] == "libx264"


def test_a_vertical_source_is_left_alone():
    result = reframe.render_vertical(
        source="in.mp4",
        output="in_9x16.mp4",
        source_width=1080,
        source_height=1920,
        samples=[reframe.Sample(0.0, 0)],
        ffmpeg="there-is-no-ffmpeg-here",
    )

    assert result.output is None
    assert "vertical" in result.note.lower()


def test_an_audio_only_download_is_left_alone():
    result = reframe.render_vertical(
        source="in.mp3",
        output="in_9x16.mp4",
        source_width=0,
        source_height=0,
        samples=[],
        ffmpeg="there-is-no-ffmpeg-here",
    )

    assert result.output is None
    assert "audio" in result.note.lower()


def test_a_landscape_source_is_rendered(tmp_path):
    source = tmp_path / "in.mp4"
    source.write_bytes(b"not really a video")
    output = tmp_path / "in_9x16.mp4"

    ran = {}

    def fake_run(command, cwd):
        ran["command"] = command
        ran["cwd"] = cwd
        ran["commands"] = Path(cwd, "crop.cmd").read_text(encoding="utf-8")
        Path(output).write_bytes(b"made")
        return 0

    result = reframe.render_vertical(
        source=str(source),
        output=str(output),
        source_width=1920,
        source_height=1080,
        samples=[reframe.Sample(0.0, 100)],
        ffmpeg="ffmpeg",
        runner=fake_run,
    )

    assert result.output == str(output)
    assert any("sendcmd=f=crop.cmd" in part for part in ran["command"])
    assert ran["commands"].splitlines() == ["0.000 crop@c x 100;"]


def test_the_render_resolves_the_paths_before_it_moves_to_its_own_folder(
    tmp_path, monkeypatch
):
    """ffmpeg runs in the folder that holds the command file, so a relative
    path would be looked up in the wrong place."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "in.mp4").write_bytes(b"x")
    seen = {}

    def fake_run(command, cwd):
        seen["input"] = command[command.index("-i") + 1]
        return 1

    reframe.render_vertical(
        source="in.mp4",
        output="out.mp4",
        source_width=1920,
        source_height=1080,
        samples=[reframe.Sample(0.0, 0)],
        runner=fake_run,
    )

    assert os.path.isabs(seen["input"])



def test_both_models_are_in_the_package():
    assert reframe.model_path(reframe.FACE_MODEL).is_file()
    assert reframe.model_path(reframe.BODY_MODEL).is_file()


def test_a_frozen_app_reads_the_models_from_its_own_bundle(tmp_path, monkeypatch):
    """PyInstaller stages the data files under ``sys._MEIPASS``, and the module
    itself lives inside the archive - so the bundle is the only place a frozen
    app can find them."""
    models = tmp_path / "models"
    models.mkdir()
    for name in (reframe.FACE_MODEL, reframe.BODY_MODEL):
        (models / name).write_text("model")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert reframe.model_path(reframe.FACE_MODEL) == models / reframe.FACE_MODEL


def test_a_bundle_without_the_model_falls_back_to_the_source_folder(tmp_path, monkeypatch):
    """Running from the source tree is the other half: a bundle that carries
    nothing beside this module is not where the models are."""
    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert reframe.model_path(reframe.FACE_MODEL) != models / reframe.FACE_MODEL
    assert reframe.model_path(reframe.FACE_MODEL).is_file()


def test_a_frame_with_a_person_gives_the_subject():
    cv2 = pytest.importorskip("cv2")
    frame = cv2.imread(str(FIXTURES / "portrait.jpg"))

    centre = reframe.SubjectDetector().detect(frame)

    assert centre is not None
    x, y = centre
    assert 0 < x < frame.shape[1]
    assert 0 < y < frame.shape[0]


def test_an_empty_frame_gives_no_subject():
    cv2 = pytest.importorskip("cv2")
    frame = cv2.imread(str(FIXTURES / "portrait.jpg")) * 0

    assert reframe.SubjectDetector().detect(frame) is None


def test_a_face_is_preferred_over_the_body():
    cv2 = pytest.importorskip("cv2")
    frame = cv2.imread(str(FIXTURES / "portrait.jpg"))
    detector = reframe.SubjectDetector()

    assert detector.detect(frame) == detector.face_centre(frame)


def test_a_jump_in_the_subject_does_not_snap_the_camera():
    path = reframe.path_from_centres([(0.0, 960), (0.5, 1600)], 1920, 594)

    assert path[0].x == 662
    assert path[1].x - path[0].x == reframe.max_step_for(594)


def test_a_frame_with_no_detection_keeps_the_previous_position():
    path = reframe.path_from_centres(
        [(0.0, 960), (0.5, None), (1.0, 960)], 1920, 594
    )

    assert [sample.x for sample in path] == [662, 662, 662]


def test_a_video_with_no_detection_falls_back_to_the_centred_crop():
    path = reframe.path_from_centres([(0.0, None), (0.5, None)], 1920, 594)

    assert [sample.x for sample in path] == [662, 662]


def test_the_tracker_reads_the_frames_of_a_video():
    """The tracker samples at 5 fps from a 2-second 10 fps clip: ten frames,
    every other one of the twenty."""
    pytest.importorskip("cv2")

    class Stub:
        def __init__(self):
            self.seen = 0

        def detect(self, frame):
            self.seen += 1
            return (160, 120)

    stub = Stub()
    centres = reframe.track_centres(str(TRACKER_CLIP), sample_fps=5.0, detector=stub)

    assert stub.seen == 10
    assert [time for time, _x in centres] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8]
    assert [x for _time, x in centres] == [160] * 10


def test_the_copy_the_detectors_read_is_smaller_and_slower():
    """Detection on the file as it landed costs twelve seconds per second of
    film; the subject is no harder to see at 1920 across and five frames a
    second, and that width is what keeps the two paths in agreement."""
    command = reframe.proxy_command("ffmpeg", "in.mp4", "out.mp4")

    assert "fps=5.0,scale=w='min(1920,iw)':h=-2" in command
    assert "-an" in command
    assert "-preset" in command
    assert command[-1] == "out.mp4"


def test_the_analysis_reads_the_copy_and_hands_back_a_path_for_the_file(tmp_path, monkeypatch):
    """The detectors see a 1920-wide copy; the crop filter works in the file,
    so every centre is scaled back before the window is placed."""
    monkeypatch.setattr(
        reframe,
        "frame_size",
        lambda video: (3840, 2160, 60.0) if video.endswith("Film.mp4") else (1920, 1080, 5.0),
    )
    monkeypatch.setattr(reframe, "detect_picture", lambda video, **kwargs: (256, 1901))
    monkeypatch.setattr(
        reframe,
        "track_centres",
        lambda video, **kwargs: [(0.0, 663), (0.2, 1200)],
    )
    read = []

    def fake_runner(command, cwd):
        read.append(command[-1])
        return 0

    box, samples = reframe.analyse(str(tmp_path / "Film.mp4"), runner=fake_runner)

    assert box == (256, 1901)
    # 663 in the copy is 1326 in the file, and the 918-wide window is placed
    # with its middle under it. The next centre is far off to the right, so the
    # window travels the most it is allowed between two samples - a quarter of
    # its own width - and lands on 866 + 229, made even.
    assert [sample.x for sample in samples] == [866, 1094]
    assert read and read[0].endswith("proxy.mp4")


def test_a_file_that_refuses_to_give_up_a_proxy_is_still_tracked(tmp_path, monkeypatch):
    """The copy is the cheap way to find the subject, not the only way."""
    monkeypatch.setattr(reframe, "frame_size", lambda video: (3840, 2160, 60.0))
    monkeypatch.setattr(reframe, "detect_picture", lambda video, **kwargs: None)
    read = []

    def spy(video, **kwargs):
        read.append(video)
        return []

    monkeypatch.setattr(reframe, "track_centres", spy)
    monkeypatch.setattr(reframe, "path_from_centres", lambda *args: [])

    reframe.analyse(str(tmp_path / "Film.mp4"), runner=lambda command, cwd: 1)

    assert read == [str(tmp_path / "Film.mp4")]


def test_the_vertical_size_is_nine_by_sixteen_and_even():
    """An odd size is refused by the encoder, and a size that is not 9:16
    would stretch the picture."""
    for height in (1080, 720, 624, 361):
        width, out_height = reframe.output_size(height)
        assert width % 2 == 0 and out_height % 2 == 0
        assert width * 16 == out_height * 9


def test_a_bigger_source_does_not_mean_a_bigger_vertical_file():
    """A 4K film arrives as a 3840x2160 container holding a 2.33:1 picture,
    so the window cut out of it is a thousand pixels wide. Scaling that to
    2912 rows is the same picture in four times the bytes, in four times the
    encode time, on a phone that shows 1080 of them."""
    assert reframe.output_size(2160) == (1080, 1920)
    assert reframe.output_size(1080) == (1080, 1920)
    assert reframe.output_size(720) == (720, 1280)
    assert reframe.output_size(624) == (630, 1120)


def test_the_frame_size_is_what_the_decoder_sees():
    """The site's metadata says what it meant to serve; the file says what
    landed, and the crop window has to fit the file."""
    pytest.importorskip("cv2")

    width, height, fps = reframe.frame_size(str(TRACKER_CLIP))

    assert (width, height) == (320, 240)
    assert fps == pytest.approx(10.0)


def test_a_file_that_holds_no_video_has_no_size(tmp_path):
    pytest.importorskip("cv2")
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")

    assert reframe.frame_size(str(broken)) == (0, 0, 0.0)


def test_a_frame_wider_than_nine_by_sixteen_is_the_one_worth_reframing():
    """The bar is the shape of the output, not whether the source is wide."""
    assert reframe.is_landscape(1920, 1080)
    assert reframe.is_landscape(1000, 1000)
    assert not reframe.is_landscape(1080, 1920)
    assert not reframe.is_landscape(562, 1000)
