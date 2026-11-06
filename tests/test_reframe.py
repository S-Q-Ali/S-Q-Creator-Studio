"""Tests for the 9:16 reframe maths - the crop window and the path it takes.

The detector tests use a public-domain portrait; see
``tests/fixtures/PORTRAIT.txt`` for where it came from. The video tests use a
clip built by ffmpeg; see ``tests/fixtures/TRACKER_CLIP.txt`` for why it is a
committed file instead of one the test writes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

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


def test_the_picture_scan_says_how_far_over_the_film_it_has_read(monkeypatch):
    """cropdetect is the first read of the file and the first minutes of a
    long job; with a bar to fill it is watched, and its report is read from
    whichever stream ffmpeg left it in."""
    asked = {}

    def watch(command, *, duration=0.0, on_progress=None, cwd=None):
        asked.update(duration=duration, command=command)
        on_progress(0.25)
        return subprocess.CompletedProcess(
            command, 0, "[cropdetect_0 @ 0x1] crop=3840:1646:0:256\n", ""
        )

    monkeypatch.setattr(reframe.ffmpeg_process, "watch", watch)
    told = []

    box = reframe.detect_picture("Film.mp4", duration=60.0, progress=told.append)

    assert box == (256, 1901)
    assert told == [0.25]
    assert asked["duration"] == 60.0


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


def test_a_single_bad_detection_does_not_move_the_window():
    """One sample that points at something else is the median of the five
    around it, and the next sample disagrees with it, so it never becomes
    the position the window is asked for."""
    positions = reframe.smooth_positions([662, 662, 1300, 662, 662, 662], 1920)

    assert positions == [662] * 6


def test_a_cut_gives_the_filter_a_new_position_at_once():
    """A sample the next one agrees with, far across the picture from where
    the camera points, is the shot changing. Half-way across a cut is a
    framing that shows neither shot, so the filter goes to it in one read."""
    positions = reframe.smooth_positions([662] * 4 + [1300] * 4, 1920)

    assert positions[:4] == [662] * 4
    assert positions[4:] == [1300] * 4


def test_a_far_detection_the_next_one_contradicts_does_not_move_at_all():
    """After the detectors lose the subject the median window can hold two
    reads and pick the wrong one; a read the next one contradicts is one
    detection pointing elsewhere, so the camera keeps the framing it had."""
    positions = reframe.smooth_positions(
        [2065, None, None, None, 227, 2065, 2065], 3840
    )

    assert positions == [2065, None, None, None, 2065, 2065, 2065]


def test_a_walk_within_a_shot_still_survives_the_filter():
    """Steps smaller than a cut are a subject that really moved, and the
    filter has to follow them or the camera stops tracking."""
    positions = reframe.smooth_positions([662, 700, 760, 840, 920, 1000], 1920)

    assert all(after >= before for before, after in pairwise(positions))
    assert positions[-1] > 700


def test_a_frame_with_no_detection_is_not_a_position():
    assert reframe.smooth_positions([662, None, 662, 662], 1920) == [662, None, 662, 662]


def test_a_move_never_finishes_in_less_than_half_a_second():
    assert reframe.glide_seconds(20, 594) == reframe.MIN_GLIDE_SECONDS
    assert reframe.glide_seconds(594, 594) == 2.0


def test_the_path_has_a_keyframe_for_every_frame_of_the_video():
    """``sendcmd`` holds a value until the next command and does not
    interpolate, so a path written at the five-frames-a-second rate the
    centres were read at is a staircase of teleports."""
    path = reframe.path_from_centres(
        [(0.0, 960), (1.0, 960)], 1920, 594, fps=25.0
    )

    assert len(path) == 26
    assert path[0].time == 0.0
    assert path[-1].time == pytest.approx(1.0)


def test_a_walk_across_the_picture_moves_the_window_a_few_pixels_a_frame():
    """Inside one shot the way from one framing to the next is every position
    in between: no frame of a pan is more than a tenth of the window."""
    path = reframe.path_from_centres(
        [(0.0, 300), (0.2, 500), (0.4, 700), (2.0, 900)], 1920, 594, fps=30.0
    )
    steps = [after.x - before.x for before, after in pairwise(path)]

    assert all(abs(step) <= 594 // 10 for step in steps)
    assert all(0 <= sample.x <= 1920 - 594 for sample in path)


def test_a_cut_sets_the_new_framing_the_frame_it_is_read():
    """Measured on a 4K film, the subject moves 17 pixels between two samples
    inside a shot and a thousand at a cut. Panning across a cut is the camera
    that never settles; the new framing the moment the picture changes is the
    one the shot was composed for."""
    path = reframe.path_from_centres(
        [(0.0, 300), (0.2, 300), (0.4, 1700), (0.6, 1700), (0.8, 1700)],
        1920,
        594,
        fps=25.0,
    )

    assert {sample.x for sample in path if sample.time < 0.4} == {2}
    assert {sample.x for sample in path if sample.time >= 0.4} == {1326}
    assert {sample.x for sample in path} == {2, 1326}


def test_a_cut_near_the_edge_of_the_picture_still_sets_at_once():
    """The cut is read from where the subject is, not from how far the window
    is allowed to go: pinned against the edge, a cut looks like a short
    move, and a pan that short is the camera drifting off the new shot."""
    path = reframe.path_from_centres(
        [(0.0, 1397), (0.2, 1397), (0.4, 1747), (0.6, 1747)], 1920, 594, fps=25.0
    )

    assert {sample.x for sample in path if sample.time < 0.4} == {1100}
    assert {sample.x for sample in path if sample.time >= 0.4} == {1326}


def test_a_subject_that_wanders_leaves_the_camera_still():
    """Inside the deadband the position is frozen and the same value is
    written again: a static shot is the same crop from frame to frame."""
    centres = [(index * 0.2, 960 + (index % 2) * 20) for index in range(10)]
    path = reframe.path_from_centres(centres, 1920, 594, fps=25.0)

    assert {sample.x for sample in path} == {662}


def test_a_walk_within_a_shot_pans_and_does_not_take_the_shortcut():
    """A subject that walks is followed by a glide that runs for its own time,
    so the way there is every position in between, not one jump."""
    path = reframe.path_from_centres(
        [(0.0, 960), (0.5, 1060), (1.0, 1160), (1.5, 1260), (2.0, 1360)],
        1920,
        594,
        fps=25.0,
    )
    steps = [after.x - before.x for before, after in pairwise(path)]
    between = {sample.x for sample in path if 662 < sample.x < path[-1].x}

    assert max(abs(step) for step in steps) <= 594 // 10
    assert len(between) > 4
    assert path[-1].x == 770


def test_a_glide_still_running_after_the_last_detection_is_finished():
    """The detectors stop with the last sampled frame; the camera does not
    freeze half-way to where it was going."""
    centres = [(index * 0.2, 960 + 80 * index) for index in range(6)]
    path = reframe.path_from_centres(centres, 1920, 594, fps=25.0)
    last_centre = [sample for sample in path if sample.time <= 1.0][-1]

    assert path[-1].time > last_centre.time
    assert path[-1].x == max(sample.x for sample in path) > last_centre.x


def test_the_command_file_writes_a_line_only_when_the_window_moves(tmp_path):
    command_file = tmp_path / "crop.cmd"

    reframe.write_command_file(
        command_file,
        [
            reframe.Sample(0.0, 100),
            reframe.Sample(0.04, 100),
            reframe.Sample(0.08, 400),
            reframe.Sample(0.12, 400),
        ],
    )

    assert command_file.read_text(encoding="utf-8").splitlines() == [
        "0.000 crop@c x 100;",
        "0.080 crop@c x 400;",
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


def two_faces():
    """The faces a stubbed YuNet hands back, one list per frame."""
    small = [800.0, 500.0, 80.0, 80.0] + [0.0] * 11
    big = [200.0, 500.0, 300.0, 300.0] + [0.0] * 11
    return small, big


def stub_faces(detector, frames):
    """Give the detector faces to find, one set per call, and no model."""
    np = pytest.importorskip("numpy")
    queue = list(frames)

    def detect(_frame):
        return 0, np.array(queue.pop(0), dtype=np.float32)

    detector._face = SimpleNamespace(setInputSize=lambda size: None, detect=detect)


def test_the_camera_keeps_the_person_it_was_showing():
    """Two people in the frame and the other one is bigger: the window stays
    on the face it had, because that is the one that was there last frame."""
    np = pytest.importorskip("numpy")
    detector = reframe.SubjectDetector()
    small, big = two_faces()
    frame = np.zeros((1080, 1920, 3), dtype="uint8")
    stub_faces(detector, [[small], [small, big]])

    assert detector.detect(frame) == (840, 540)
    assert detector.detect(frame) == (840, 540)


def test_the_first_face_the_camera_sees_is_the_biggest_one():
    np = pytest.importorskip("numpy")
    detector = reframe.SubjectDetector()
    small, big = two_faces()
    frame = np.zeros((1080, 1920, 3), dtype="uint8")
    stub_faces(detector, [[small, big]])

    assert detector.detect(frame) == (350, 650)


def test_a_cut_to_a_different_person_is_followed():
    """Nothing is near the last centre after a cut, so the biggest box in the
    new shot is the subject and the camera pans to it."""
    np = pytest.importorskip("numpy")
    detector = reframe.SubjectDetector()
    frame = np.zeros((1080, 1920, 3), dtype="uint8")
    new = [1200.0, 400.0, 300.0, 300.0] + [0.0] * 11
    near_but_not = [660.0, 500.0, 80.0, 80.0] + [0.0] * 11
    stub_faces(detector, [[[200.0, 500.0, 80.0, 80.0] + [0.0] * 11], [new, near_but_not]])

    assert detector.detect(frame) == (240, 540)
    assert detector.detect(frame) == (1350, 550)


def test_a_frame_with_no_detection_keeps_the_previous_position():
    path = reframe.path_from_centres(
        [(0.0, 960), (0.8, None), (1.6, 960)], 1920, 594, fps=25.0
    )

    assert {sample.x for sample in path} == {662}


def test_a_video_with_no_detection_falls_back_to_the_centred_crop():
    path = reframe.path_from_centres(
        [(0.0, None), (1.0, None)], 1920, 594, fps=25.0
    )

    assert {sample.x for sample in path} == {662}


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
        lambda video, **kwargs: [
            (0.0, 663),
            (0.2, 723),
            (0.4, 783),
            (0.6, 843),
            (0.8, 903),
        ],
    )
    read = []

    def fake_runner(command, cwd):
        read.append(command[-1])
        return 0

    box, samples = reframe.analyse(str(tmp_path / "Film.mp4"), runner=fake_runner)

    assert box == (256, 1901)
    # 663 in the copy is 1326 in the file, and the 918-wide window is placed
    # with its middle under it: 866, made even. The camera is set to that
    # framing on the first frame - the middle of the film is not a shot it was
    # ever in - and then holds until the subject has moved enough to be worth
    # a pan, and pans it: a keyframe for every one of the file's sixty frames
    # a second.
    assert samples[0].x == 866
    assert samples[-1].x == 996
    assert len(samples) > 6
    assert all(
        abs(after.x - before.x) <= 918 // 10
        for before, after in pairwise(samples)
    )
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


def test_the_three_reads_of_an_analysis_share_the_bar_it_is_given(
    tmp_path, monkeypatch
):
    """The picture, the copy it is detected on, and the subject are three
    reads of the film, and the bar handed to an analysis is split between
    them - so half way through the tracking is a sixth of the file's work
    left, not half of one step."""
    monkeypatch.setattr(reframe, "frame_size", lambda video: (1920, 1080, 30.0))
    told = []

    def picture(video, ffmpeg="ffmpeg", duration=0.0, progress=None):
        progress(1.0)
        return (0, 1079)

    def encode(duration, progress):
        def run(command, cwd):
            assert command[-1].endswith("proxy.mp4")
            progress(1.0)
            return 0

        return run

    def centres(video, sample_fps=5.0, detector=None, progress=None):
        progress(0.5)
        return [(0.0, 500)]

    monkeypatch.setattr(reframe, "detect_picture", picture)
    monkeypatch.setattr(reframe, "track_centres", centres)
    monkeypatch.setattr(reframe, "_ffmpeg_runner", encode)

    reframe.analyse(str(tmp_path / "Film.mp4"), duration=60.0, progress=told.append)

    assert [round(value, 3) for value in told] == [0.333, 0.667, 0.833]


def test_the_write_of_the_vertical_reports_the_film_it_has_written(
    tmp_path, monkeypatch
):
    """The last pass is an encode, and ffmpeg counts the seconds it has
    written: with a length to divide by, that is the bar."""
    (tmp_path / "in.mp4").write_bytes(b"x")
    asked = {}

    def watch(command, *, duration=0.0, on_progress=None, cwd=None):
        asked.update(duration=duration)
        on_progress(0.5)
        Path(command[-1]).write_bytes(b"made")
        return subprocess.CompletedProcess(command, 0, "out_time_ms=1000000\n", "")

    monkeypatch.setattr(reframe.ffmpeg_process, "watch", watch)
    told = []

    result = reframe.render_vertical(
        source=str(tmp_path / "in.mp4"),
        output=str(tmp_path / "in_9x16.mp4"),
        source_width=1920,
        source_height=1080,
        samples=[reframe.Sample(0.0, 100)],
        duration=20.0,
        progress=told.append,
    )

    assert result.output == str(tmp_path / "in_9x16.mp4")
    assert asked["duration"] == 20.0
    assert told == [0.5]


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


def test_the_length_of_a_local_file_comes_from_the_file():
    """The split plans its cuts from a duration. A download got that from the
    site's metadata; a file nobody downloaded only has what the container
    says, and the decoder that reads the picture can read the count too."""
    pytest.importorskip("cv2")

    assert reframe.duration_seconds(str(TRACKER_CLIP)) == pytest.approx(2.0, abs=0.2)


def test_a_file_that_holds_no_video_has_no_length(tmp_path):
    pytest.importorskip("cv2")
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")

    assert reframe.duration_seconds(str(broken)) == 0.0


def test_a_frame_wider_than_nine_by_sixteen_is_the_one_worth_reframing():
    """The bar is the shape of the output, not whether the source is wide."""
    assert reframe.is_landscape(1920, 1080)
    assert reframe.is_landscape(1000, 1000)
    assert not reframe.is_landscape(1080, 1920)
    assert not reframe.is_landscape(562, 1000)
