"""The Vertical Studio's worker: the two legs over files the user points at.

Nothing is downloaded here, so a dropped file is the whole input. It is read,
worked on, and left exactly as it was, and one bad file never stops the rest
of the list.
"""

from __future__ import annotations

from s_q_ali_media_downloader import engine
from s_q_ali_media_downloader.core import reframe, shorts
from s_q_ali_media_downloader.engine import LocalVideoThread

ONE = "out/one.mp4"
TWO = "out/two.mp4"
THREE = "out/three.mp4"

TWO_SHORTS = ["out/one_short01.mp4", "out/one_short02.mp4"]


def _plan():
    return shorts.CutPlan(
        segments=[
            shorts.Segment(index=0, start=0.0, end=60.0),
            shorts.Segment(index=1, start=60.0, end=120.0),
        ],
        clip_duration=60.0,
        clips=2,
        note="2 clips → about 1 min each on average.",
    )


def _fake_legs(monkeypatch, *, sizes=None):
    """Replace the ffmpeg and OpenCV passes with recorders."""
    seen = {"render": [], "split": []}
    sizes = sizes or {}

    def frame_size(video):
        return sizes.get(video, (1920, 1080, 30.0))

    def render_vertical(source, output, width, height, samples, **kwargs):
        seen["render"].append((source, output))
        return reframe.RenderResult(output=output, note="The vertical version is beside it.")

    def split_video(source, plan, **kwargs):
        seen["split"].append(source)
        return shorts.SplitResult(outputs=list(TWO_SHORTS), note="2 shorts saved.")

    monkeypatch.setattr(engine, "find_ffmpeg", lambda: None)
    monkeypatch.setattr(engine.reframe, "duration_seconds", lambda video: 120.0)
    monkeypatch.setattr(engine.reframe, "frame_size", frame_size)
    monkeypatch.setattr(engine.reframe, "analyse", lambda video, **kwargs: (None, []))
    monkeypatch.setattr(engine.reframe, "render_vertical", render_vertical)
    monkeypatch.setattr(engine.shorts, "detect_silences", lambda video, **kwargs: [40.0])
    monkeypatch.setattr(engine.shorts, "detect_scene_changes", lambda video, **kwargs: [40.0])
    monkeypatch.setattr(engine.shorts, "plan_cuts", lambda duration, **kwargs: _plan())
    monkeypatch.setattr(engine.shorts, "split_video", split_video)
    return seen


def _thread(files, **options):
    """The worker plus what the page would draw: the file in hand, the pass
    underway, the log."""
    args = {"vertical": True}
    args.update(options)
    thread = LocalVideoThread(files, **args)
    thread.started = []
    thread.stages = []
    thread.lines = []
    thread.file_started.connect(lambda index, path: thread.started.append((index, path)))
    thread.progress.connect(lambda percent, stage: thread.stages.append(stage))
    thread.log.connect(thread.lines.append)
    thread.finished_all.connect(lambda: thread.lines.append("__done__"))
    return thread


def test_the_files_are_worked_on_one_after_another(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch)
    thread = _thread([ONE, TWO, THREE])

    thread.run()

    assert [path for _index, path in thread.started] == [ONE, TWO, THREE]
    assert [entry[0] for entry in seen["render"]] == [ONE, TWO, THREE]
    assert thread.lines[-1] == "__done__"


def test_the_vertical_file_lands_beside_the_one_the_user_dropped(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch)
    _thread([ONE]).run()

    assert seen["render"] == [(ONE, "out/one_9x16.mp4")]


def test_a_file_that_cannot_be_read_does_not_stop_the_list(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch)

    def unreadable(video):
        if video == TWO:
            raise OSError("the container is a lie")
        return 120.0

    monkeypatch.setattr(engine.reframe, "duration_seconds", unreadable)
    thread = _thread([ONE, TWO, THREE])

    thread.run()

    assert [entry[0] for entry in seen["render"]] == [ONE, THREE]
    assert any("the container is a lie" in line for line in thread.lines)


def test_an_already_vertical_video_gets_one_sentence_and_moves_on(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch, sizes={TWO: (1080, 1920, 30.0)})
    thread = _thread([ONE, TWO])

    thread.run()

    assert [entry[0] for entry in seen["render"]] == [ONE]
    assert any("already vertical" in line for line in thread.lines)


def test_a_file_with_no_picture_gets_one_sentence_and_moves_on(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch, sizes={TWO: (0, 0, 0.0)})
    thread = _thread([ONE, TWO])

    thread.run()

    assert [entry[0] for entry in seen["render"]] == [ONE]
    assert any("no picture" in line for line in thread.lines)


def test_stop_leaves_the_rest_of_the_list_alone(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch)
    thread = _thread([ONE, TWO, THREE])
    thread.file_started.connect(lambda index, path: thread.stop() if index == 0 else None)

    thread.run()

    assert [entry[0] for entry in seen["render"]] == [ONE]


def test_the_shorts_are_cut_first_and_each_one_turns_vertical(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch)
    thread = _thread([ONE], split="60 s")

    thread.run()

    assert seen["split"] == [ONE]
    assert [entry[0] for entry in seen["render"]] == TWO_SHORTS
    assert thread.stages == ["splitting", "vertical 9:16", "vertical 9:16"]


def test_both_options_off_leaves_the_files_alone(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch)
    thread = _thread([ONE], vertical=False, split=engine.DEFAULT_SPLIT)

    thread.run()

    assert seen == {"render": [], "split": []}
    assert thread.lines == ["__done__"]
