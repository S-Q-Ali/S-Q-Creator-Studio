"""What the worker does after a download lands: the shorts and the vertical.

Both are opt-in, both run in the worker thread, and neither may fail a
download that already succeeded.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import types
from itertools import pairwise

import pytest

from s_q_ali_media_downloader import engine
from s_q_ali_media_downloader.core import reframe, shorts
from s_q_ali_media_downloader.engine import DownloadThread

SOURCE = "out/How to cook.mp4"


def _thread(monkeypatch, **options):
    monkeypatch.setattr(engine, "find_ffmpeg", lambda: None)
    return DownloadThread(jobs=[], output_dir="out", quality="Best up to 4K", **options)


def _install(monkeypatch, seen, *, plan=None, pieces=None):
    """Replace the ffmpeg and OpenCV legs with ones that only remember calls."""
    if plan is None:
        plan = shorts.CutPlan(
            segments=[
                shorts.Segment(index=0, start=0.0, end=60.0),
                shorts.Segment(index=1, start=60.0, end=120.0),
            ],
            clip_duration=60.0,
            clips=2,
            note="2 clips → about 1 min each on average.",
        )
    if pieces is None:
        pieces = ["out/How to cook_short01.mp4", "out/How to cook_short02.mp4"]

    def detect_silences(video, **kwargs):
        seen.append(("silences", video))
        return [40.0, 80.0]

    def detect_scene_changes(video, **kwargs):
        seen.append(("scenes", video))
        return [40.0]

    def plan_cuts(duration, **kwargs):
        seen.append(("plan", duration, kwargs))
        return plan

    def split_video(source, cut_plan, **kwargs):
        seen.append(("split", source))
        return shorts.SplitResult(
            outputs=list(pieces), note="2 shorts saved beside the original."
        )

    def frame_size(video):
        seen.append(("size", video))
        return 1920, 1080, 30.0

    def analyse(video, **kwargs):
        seen.append(("analyse", video))
        return None, []

    def render_vertical(source, output, width, height, samples, **kwargs):
        seen.append(("render", source, output))
        return reframe.RenderResult(output=output, note="The vertical version is beside it.")

    for name, fake in (
        ("detect_silences", detect_silences),
        ("detect_scene_changes", detect_scene_changes),
        ("plan_cuts", plan_cuts),
        ("split_video", split_video),
    ):
        monkeypatch.setattr(engine.shorts, name, fake)
    options = {
        "frame_size": frame_size,
        "analyse": analyse,
        "render_vertical": render_vertical,
    }
    for name, fake in options.items():
        monkeypatch.setattr(engine.reframe, name, fake)
    return pieces


def _plan_options(seen):
    """What the engine handed to the cut-point planner."""
    return next(entry for entry in seen if entry[0] == "plan")[2]


def _leg(lines=None, stages=None, ticks=None, **options):
    """Call the legs over one file that is already on disk, no download thread."""
    args = {
        "vertical": True,
        "split": engine.DEFAULT_SPLIT,
        "clips": 0,
        "ffmpeg": "ffmpeg",
        "duration": 120.0,
    }
    args.update(options)
    engine.run_post_leg(
        SOURCE,
        report=(lines if lines is not None else []).append,
        stage=(stages if stages is not None else []).append,
        progress=(ticks if ticks is not None else []).append,
        **args,
    )
    return lines, stages


def test_the_legs_run_on_a_file_that_was_never_downloaded(monkeypatch):
    """The Vertical Studio drops a local file in and asks for the same two
    passes the download flow runs - so they live in one place."""
    seen = []
    pieces = _install(monkeypatch, seen)
    lines = []

    _leg(lines, split="60 s")

    assert ("split", SOURCE) in seen
    assert [entry[1] for entry in seen if entry[0] == "render"] == pieces
    assert "2 clips → about 1 min each on average." in lines


def test_the_legs_do_nothing_when_both_options_are_off(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    lines = []

    _leg(lines, vertical=False)

    assert seen == []
    assert lines == []


def test_the_stage_names_the_pass_the_file_is_in(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    stages = []

    _leg(stages=stages, split="60 s")

    assert stages == [
        "finding the pauses",
        "finding the scenes",
        "splitting",
        "finding the subject",
        "writing the vertical",
        "finding the subject",
        "writing the vertical",
    ]


def test_the_bar_counts_the_reads_of_the_film(monkeypatch):
    """The passes are priced before any of them runs - three reads of the
    whole file, then four reads of each of the two clips it became - so a
    five-minute film spends the same shape of bar on it as a one-minute one,
    and the number is never a step count dressed up as a percent."""
    _install(monkeypatch, [])

    def scan(video, **kwargs):
        kwargs["progress"](1.0)
        return [40.0]

    def analyse(video, **kwargs):
        kwargs["progress"](1.0)
        return None, []

    def render(source, output, width, height, samples, **kwargs):
        kwargs["progress"](1.0)
        return reframe.RenderResult(output=output, note="The vertical version is beside it.")

    def split(source, cut_plan, **kwargs):
        kwargs["progress"](1.0)
        return shorts.SplitResult(
            outputs=["out/How to cook_short01.mp4", "out/How to cook_short02.mp4"],
            note="2 shorts saved beside the original.",
        )

    monkeypatch.setattr(engine.shorts, "detect_silences", scan)
    monkeypatch.setattr(engine.shorts, "detect_scene_changes", scan)
    monkeypatch.setattr(engine.shorts, "split_video", split)
    monkeypatch.setattr(engine.reframe, "analyse", analyse)
    monkeypatch.setattr(engine.reframe, "render_vertical", render)
    ticks = []

    _leg(ticks=ticks, split="60 s")

    # Three reads of the whole 120 s file, then four reads of each of the two
    # 60 s clips it became: 840 priced seconds, so the first read of the file
    # is worth a seventh of the bar and one read of a clip a fourteenth.
    assert ticks == [14.3, 28.6, 42.9, 64.3, 71.4, 92.9, 100.0]


def test_work_found_late_fills_the_bar_instead_of_pushing_it_back(monkeypatch):
    """The clips are only counted once the split has run, but the whole of
    the file's work was priced before it started - so the bar that had shown
    a half is not asked to show a fifth by a pass nobody had named."""
    ticks = []
    meter = engine._Meter(ticks.append, 120.0)

    first = meter.price(60.0)
    first(1.0)
    later = meter.price(60.0)
    later(0.0)
    first(0.5)

    assert ticks == [50.0]
    later(1.0)
    assert ticks == [50.0, 100.0]
    meter.finish()


def test_a_run_nobody_is_watching_priced_nothing():
    """The download worker asks for no bar over the legs, and the passes it
    hands to ffmpeg stay exactly as they were: no listener, no callback, and
    the file is worked on as it always was."""
    meter = engine._Meter()

    assert meter.price(60.0) is None
    meter.finish()


def test_a_step_that_blows_up_is_reported_and_never_raises(monkeypatch):
    seen = []
    _install(monkeypatch, seen)

    def explode(video):
        raise RuntimeError("no opencv here")

    monkeypatch.setattr(engine.reframe, "frame_size", explode)
    lines = []

    _leg(lines)

    assert any("vertical" in line.lower() for line in lines)


def test_a_file_that_reports_no_length_is_not_cut(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    lines = []

    _leg(lines, vertical=False, split="60 s", duration=0.0)

    assert "split" not in [entry[0] for entry in seen]
    assert any("length" in line.lower() for line in lines)


def test_both_options_are_off_by_default(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    thread = _thread(monkeypatch)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert seen == []


def test_the_vertical_box_makes_the_vertical_file_beside_the_download(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    thread = _thread(monkeypatch, vertical=True)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert ("analyse", SOURCE) in seen
    assert ("render", SOURCE, "out/How to cook_9x16.mp4") in seen


def test_the_picture_and_the_path_from_the_analysis_reach_the_render(monkeypatch):
    """A film in a 16:9 container carries black bars and the tracker reads a
    small copy of it; the render has to be told both."""
    seen = []
    _install(monkeypatch, seen)
    handed = {}

    def analyse(video, **kwargs):
        return (256, 1901), [reframe.Sample(0.0, 1460)]

    def render_vertical(source, output, width, height, samples, **kwargs):
        handed["box"] = kwargs.get("box")
        handed["samples"] = samples
        return reframe.RenderResult(output=output, note="done")

    monkeypatch.setattr(engine.reframe, "analyse", analyse)
    monkeypatch.setattr(engine.reframe, "render_vertical", render_vertical)
    thread = _thread(monkeypatch, vertical=True)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert handed == {"box": (256, 1901), "samples": [reframe.Sample(0.0, 1460)]}


def test_the_split_runs_before_the_reframe(monkeypatch):
    seen = []
    pieces = _install(monkeypatch, seen)
    thread = _thread(monkeypatch, vertical=True, split="60 s")

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    names = [entry[0] for entry in seen]
    assert names.index("split") < names.index("render")
    assert names.count("render") == len(pieces)
    assert ("render", pieces[0], "out/How to cook_short01_9x16.mp4") in seen


def test_each_short_gets_its_own_vertical_version(monkeypatch):
    seen = []
    pieces = _install(monkeypatch, seen)
    thread = _thread(monkeypatch, vertical=True, split="N clips", clips=2)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert [entry[1] for entry in seen if entry[0] == "render"] == pieces


def test_the_shorts_stay_landscape_when_the_vertical_box_is_unticked(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    thread = _thread(monkeypatch, split="Auto")

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert "split" in [entry[0] for entry in seen]
    assert "render" not in [entry[0] for entry in seen]


def test_the_clip_count_only_matters_in_the_n_clips_mode(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    thread = _thread(monkeypatch, split="60 s", clips=6)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert seen[0] == ("silences", SOURCE)
    assert _plan_options(seen)["target"] == 60.0
    assert _plan_options(seen)["clips"] is None


def test_the_n_clips_mode_hands_the_clip_count_to_the_plan(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    thread = _thread(monkeypatch, split="N clips", clips=6)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert _plan_options(seen)["clips"] == 6
    assert _plan_options(seen)["target"] is None


def test_the_auto_mode_asks_for_no_target_length(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    thread = _thread(monkeypatch, split="Auto")

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert _plan_options(seen)["target"] is None
    assert _plan_options(seen)["clips"] is None


def test_the_plan_is_read_out_before_anything_is_cut(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    lines = []
    thread = _thread(monkeypatch, split="60 s")
    thread.log.connect(lines.append)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert "2 clips → about 1 min each on average." in lines
    assert lines.index("2 clips → about 1 min each on average.") < lines.index(
        "2 shorts saved beside the original."
    )


def test_a_download_that_reports_no_length_is_not_cut(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    lines = []
    thread = _thread(monkeypatch, split="60 s")
    thread.log.connect(lines.append)

    thread._post_leg(1, SOURCE, {})

    assert "split" not in [entry[0] for entry in seen]
    assert any("length" in line.lower() for line in lines)


def test_a_plan_that_cuts_nothing_leaves_the_video_whole(monkeypatch):
    seen = []
    _install(
        monkeypatch,
        seen,
        plan=shorts.CutPlan(note="One clip covers the video; not split."),
    )
    lines = []
    thread = _thread(monkeypatch, vertical=True, split="90 s")
    thread.log.connect(lines.append)

    thread._post_leg(1, SOURCE, {"duration": 60.0})

    assert "split" not in [entry[0] for entry in seen]
    assert ("render", SOURCE, "out/How to cook_9x16.mp4") in seen
    assert "One clip covers the video; not split." in lines


def test_an_audio_only_download_gets_no_vertical_version(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    thread = _thread(monkeypatch, vertical=True, split="60 s")
    thread.quality = "Audio only"

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert seen == []


def test_a_broken_vertical_render_is_reported_and_the_download_stands(monkeypatch):
    seen = []
    _install(monkeypatch, seen)

    def explode(video):
        raise RuntimeError("no opencv here")

    monkeypatch.setattr(engine.reframe, "frame_size", explode)
    lines = []
    thread = _thread(monkeypatch, vertical=True)
    thread.log.connect(lines.append)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert any("vertical" in line.lower() for line in lines)


def test_a_broken_split_still_gets_a_vertical_version_of_the_whole_video(monkeypatch):
    seen = []
    _install(monkeypatch, seen)

    def explode(source, cut_plan, **kwargs):
        raise OSError("ffmpeg is missing")

    monkeypatch.setattr(engine.shorts, "split_video", explode)
    lines = []
    thread = _thread(monkeypatch, vertical=True, split="60 s")
    thread.log.connect(lines.append)

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert ("render", SOURCE, "out/How to cook_9x16.mp4") in seen
    assert any("ffmpeg is missing" in line for line in lines)


def test_the_leg_is_quiet_when_the_run_was_stopped(monkeypatch):
    seen = []
    _install(monkeypatch, seen)
    thread = _thread(monkeypatch, vertical=True)
    thread.stop()

    thread._post_leg(1, SOURCE, {"duration": 120.0})

    assert seen == []


def test_the_download_still_reports_its_size_when_the_leg_blows_up(monkeypatch, tmp_path):
    """The leg runs after the file landed: nothing it does may fail the job."""
    downloaded = tmp_path / "video.mp4"
    downloaded.write_bytes(b"x" * 32)
    monkeypatch.setattr(engine, "find_ffmpeg", lambda: None)

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=True):
            return {
                "id": "abc",
                "title": "How to cook",
                "duration": 120.0,
                "requested_downloads": [{"filepath": str(downloaded)}],
            }

        def prepare_filename(self, info):
            return str(downloaded)

    monkeypatch.setattr(engine, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYDL))
    thread = DownloadThread(
        jobs=[], output_dir=str(tmp_path), quality="Best up to 4K", vertical=True
    )

    def explode(video):
        raise RuntimeError("no opencv here")

    monkeypatch.setattr(engine.reframe, "frame_size", explode)

    size = thread._download_one(3, "https://example.com/v")

    assert size != "—"
    assert os.path.isfile(tmp_path / "How to cook.mp4")
    assert not os.path.isfile(tmp_path / "How to cook_9x16.mp4")


@pytest.fixture(scope="module")
def landscape_video(tmp_path_factory):
    """A real two-minute landscape file: scene changes and pauses at 40 s and 80 s.

    The picture is solid colour, so no subject is ever found and the window
    stays centred; this proves the whole leg runs on real media, not that the
    tracker follows a face.
    """
    directory = engine.find_ffmpeg()
    assert directory, "The real media tests need ffmpeg."
    folder = tmp_path_factory.mktemp("post-leg-media")
    source = folder / "How to cook.mp4"
    subprocess.run(
        [
            engine.ffmpeg_binary(),
            "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
            "-f", "lavfi", "-i", "color=black:s=320x180:r=10:d=40",
            "-f", "lavfi", "-i", "color=white:s=320x180:r=10:d=40",
            "-f", "lavfi", "-i", "color=black:s=320x180:r=10:d=40",
            "-f", "lavfi", "-i",
            ("sine=frequency=440:sample_rate=48000:duration=120,"
             "volume=0:enable='between(t,38,42)+between(t,78,82)'"),
            "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
            "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-preset", "ultrafast",
            "-g", "100", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
        ],
        capture_output=True,
        check=True,
        timeout=180,
    )
    return directory, source


@pytest.mark.live
def test_a_real_download_is_cut_into_shorts_and_each_one_turns_vertical(
    tmp_path, monkeypatch, landscape_video
):
    directory, source = landscape_video
    monkeypatch.setattr(engine, "find_ffmpeg", lambda: directory)
    downloaded = tmp_path / "How to cook.mp4"
    shutil.copyfile(source, downloaded)
    original_bytes = downloaded.read_bytes()
    thread = DownloadThread(
        jobs=[],
        output_dir=str(tmp_path),
        quality="Best up to 4K",
        vertical=True,
        split="N clips",
        clips=3,
    )
    lines = []
    thread.log.connect(lines.append)

    thread._post_leg(1, str(downloaded), {"duration": 120.0})

    pieces = sorted(
        path.name
        for path in tmp_path.glob("*_short*.mp4")
        if not path.name.endswith("_9x16.mp4")
    )
    assert pieces == [
        "How to cook_short01.mp4",
        "How to cook_short02.mp4",
        "How to cook_short03.mp4",
    ]
    # The download itself is never touched, and with the split on the vertical
    # versions are made from the shorts, not from the long file.
    assert downloaded.read_bytes() == original_bytes
    assert not (tmp_path / "How to cook_9x16.mp4").exists()
    assert any("3 clips" in line for line in lines)

    for name in pieces:
        short = tmp_path / name
        width, height, _fps = reframe.frame_size(str(short))
        assert reframe.is_landscape(width, height)

        vertical = tmp_path / f"{short.stem}_9x16.mp4"
        assert vertical.is_file()
        out_width, out_height, _ = reframe.frame_size(str(vertical))
        assert out_width * 16 == out_height * 9  # fills the frame: no bars
        assert vertical.stat().st_size > 0


@pytest.mark.live
def test_a_real_reframe_reports_the_film_as_it_is_written(
    tmp_path, monkeypatch, landscape_video
):
    """The offline gate proves where `-progress pipe:1` goes in the command;
    only real ffmpeg says whether it answers. A bar that sits at zero for the
    whole file is the bug the owner saw on the packaged build."""
    directory, source = landscape_video
    monkeypatch.setattr(engine, "find_ffmpeg", lambda: directory)
    film = tmp_path / "How to cook.mp4"
    shutil.copyfile(source, film)
    told = []

    engine.run_post_leg(
        str(film),
        vertical=True,
        split=engine.DEFAULT_SPLIT,
        clips=3,
        ffmpeg=engine.ffmpeg_binary(),
        duration=120.0,
        report=lambda line: None,
        progress=told.append,
    )

    assert (tmp_path / "How to cook_9x16.mp4").is_file()
    assert len(told) > 2, told
    assert all(0.0 <= percent <= 100.0 for percent in told)
    assert all(after >= before for before, after in pairwise(told))
    assert told[-1] == 100.0


@pytest.fixture(scope="module")
def letterboxed_video(tmp_path_factory):
    """A film in a 16:9 container: a 320x120 picture with 30 rows of black
    above and below, the shape a downloaded movie actually arrives in."""
    directory = engine.find_ffmpeg()
    assert directory, "The real media tests need ffmpeg."
    folder = tmp_path_factory.mktemp("letterbox-media")
    source = folder / "Film.mp4"
    subprocess.run(
        [
            engine.ffmpeg_binary(),
            "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
            "-f", "lavfi", "-i", "color=white:s=320x120:r=10:d=20",
            "-vf", "pad=320:180:0:30:color=black",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(source),
        ],
        capture_output=True,
        check=True,
        timeout=180,
    )
    return directory, source


@pytest.mark.live
def test_the_black_bands_of_a_film_do_not_travel_into_the_vertical_file(
    tmp_path, monkeypatch, letterboxed_video
):
    directory, source = letterboxed_video
    monkeypatch.setattr(engine, "find_ffmpeg", lambda: directory)
    downloaded = tmp_path / "Film.mp4"
    shutil.copyfile(source, downloaded)
    assert reframe.detect_picture(str(downloaded), engine.ffmpeg_binary()) == (30, 149)
    thread = DownloadThread(
        jobs=[], output_dir=str(tmp_path), quality="Best up to 4K", vertical=True
    )

    thread._post_leg(1, str(downloaded), {"duration": 20.0})

    vertical = tmp_path / "Film_9x16.mp4"
    assert vertical.is_file()
    _width, height, _fps = reframe.frame_size(str(vertical))
    box = reframe.detect_picture(str(vertical), engine.ffmpeg_binary())
    # Untouched bands are a third of this file. Nine tenths is the room left for
    # a decode that reads the edges of a picture as slightly dark.
    assert box is not None
    assert (box[1] - box[0] + 1) * 10 >= height * 9
