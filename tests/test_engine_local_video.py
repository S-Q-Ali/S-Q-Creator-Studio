"""The Vertical Studio's worker: the two legs over files the user points at.

Nothing is downloaded here, so a dropped file is the whole input. It is read,
worked on, and left exactly as it was, and one bad file never stops the rest
of the list.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from s_q_ali_media_downloader import engine
from s_q_ali_media_downloader.core import reframe, shorts
from s_q_ali_media_downloader.engine import LocalVideoThread

ONE = "out/one.mp4"
TWO = "out/two.mp4"
THREE = "out/three.mp4"

TWO_SHORTS = ["out/one Part 1.mp4", "out/one Part 2.mp4"]


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
    thread.ticks = []
    thread.lines = []
    thread.file_started.connect(lambda index, path: thread.started.append((index, path)))
    thread.progress.connect(lambda percent, stage: thread.ticks.append((percent, stage)))
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

    assert seen["render"] == [(ONE, os.path.join("out", "one_9x16.mp4"))]


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
    assert thread.ticks == [
        (0.0, "finding the pauses"),
        (0.0, "finding the scenes"),
        (0.0, "splitting"),
        (0.0, "finding the subject"),
        (0.0, "writing the vertical"),
        (0.0, "finding the subject"),
        (0.0, "writing the vertical"),
        (100.0, "writing the vertical"),
    ]


def test_the_percent_travels_with_the_pass_it_belongs_to(qapp, monkeypatch):
    """One file, four reads of it: the bar is the share of the priced reads
    reported done, and the name handed with a number is the pass that number
    came out of - the page never has to guess which is which."""
    _fake_legs(monkeypatch)

    def analyse(video, **kwargs):
        kwargs["progress"](0.5)
        return None, []

    monkeypatch.setattr(engine.reframe, "analyse", analyse)
    thread = _thread([ONE])

    thread.run()

    # Three reads of the file for the subject, one for the write: half the
    # subject is 180 of 480 priced seconds.
    assert thread.ticks == [
        (0.0, "finding the subject"),
        (37.5, "finding the subject"),
        (37.5, "writing the vertical"),
        (100.0, "writing the vertical"),
    ]


def test_both_options_off_leaves_the_files_alone(qapp, monkeypatch):
    seen = _fake_legs(monkeypatch)
    thread = _thread([ONE], vertical=False, split=engine.DEFAULT_SPLIT)

    thread.run()

    assert seen == {"render": [], "split": []}
    assert thread.lines == ["__done__"]


# ------------------------------------------------------------- results folder


def _film(tmp_path, where, name="one.mp4", text="the whole film"):
    """A real file, so a copy of it has something to copy."""
    directory = tmp_path / where
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text)
    return str(path)


def _vertical_of(path):
    """The name the legs give the vertical version of a file: beside it."""
    return os.path.splitext(path)[0] + "_9x16.mp4"


def _text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def test_the_results_folder_holds_the_file_it_worked_on_and_its_vertical(
    qapp, monkeypatch, tmp_path
):
    """With a results folder, everything the run makes is in it: the copy of
    the film and, beside that copy, its vertical. The source is read and
    left exactly where the user dropped it."""
    seen = _fake_legs(monkeypatch)
    where = str(tmp_path / "results")
    desktop = _film(tmp_path, "desktop")
    phone = _film(tmp_path, "phone", "two.mp4")

    _thread([desktop, phone], out_dir=where).run()

    copies = [os.path.join(where, "one.mp4"), os.path.join(where, "two.mp4")]
    assert sorted(seen["render"]) == sorted(
        (copy, _vertical_of(copy)) for copy in copies
    )
    assert os.path.join(where, "one.mp4") not in (desktop, phone)
    assert _text(os.path.join(where, "one.mp4")) == "the whole film"
    for source in (desktop, phone):
        assert os.path.isfile(source)


def test_a_file_already_in_the_results_folder_is_not_copied_again(
    qapp, monkeypatch, tmp_path
):
    seen = _fake_legs(monkeypatch)
    where = tmp_path / "results"
    source = _film(tmp_path, "results")

    _thread([source], out_dir=str(where)).run()

    assert seen["render"] == [(source, _vertical_of(source))]
    assert os.listdir(where) == ["one.mp4"]


def test_two_files_of_the_same_name_both_keep_their_results(
    qapp, monkeypatch, tmp_path
):
    """The folder is one flat place, so a name already taken gets the next
    one: nothing the user already had is written over."""
    seen = _fake_legs(monkeypatch)
    where = str(tmp_path / "results")
    first = _film(tmp_path, "desktop", "clip.mp4")
    second = _film(tmp_path, "phone", "clip.mp4", text="a different film")

    _thread([first, second], out_dir=where).run()

    assert [entry[0] for entry in seen["render"]] == [
        os.path.join(where, "clip.mp4"),
        os.path.join(where, "clip (2).mp4"),
    ]
    assert _text(os.path.join(where, "clip (2).mp4")) == "a different film"


def test_the_folder_ends_up_holding_the_film_its_parts_and_their_verticals(
    qapp, monkeypatch, tmp_path
):
    """The worker's promise about a results folder is about files, so it is
    proved with files: the copy, the parts cut from it and a vertical of
    every part, all standing in the folder, and the dropped source left with
    its own bytes."""
    _fake_legs(monkeypatch)

    def write_parts(source, plan, **kwargs):
        original = Path(source)
        outputs = [
            original.with_name(f"{original.stem} Part {segment.index + 1}.mp4")
            for segment in plan.segments
        ]
        for output in outputs:
            output.write_bytes(b"a part")
        return shorts.SplitResult(
            outputs=[str(output) for output in outputs], note="2 shorts made."
        )

    def write_vertical(source, output, width, height, samples, **kwargs):
        Path(output).write_bytes(b"9 by 16")
        return reframe.RenderResult(
            output=output, note=f"Made {os.path.basename(output)}."
        )

    monkeypatch.setattr(engine.shorts, "split_video", write_parts)
    monkeypatch.setattr(engine.reframe, "render_vertical", write_vertical)
    where = tmp_path / "results"
    desktop = _film(tmp_path, "desktop")

    _thread([desktop], out_dir=str(where), split="60 s").run()

    assert set(os.listdir(where)) == {
        "one.mp4",
        "one Part 1.mp4",
        "one Part 1_9x16.mp4",
        "one Part 2.mp4",
        "one Part 2_9x16.mp4",
    }
    assert (where / "one Part 1_9x16.mp4").read_bytes() == b"9 by 16"
    assert _text(desktop) == "the whole film"


def test_the_work_is_named_by_the_copy_in_the_folder(qapp, monkeypatch, tmp_path):
    """The writes of a folder run land in the staged copy, not in the file the
    user dropped, so by the time the legs start the worker names the copy: a
    status line about the dropped file would describe writes that never touch
    it."""
    seen = _fake_legs(monkeypatch)
    where = str(tmp_path / "results")
    dropped = _film(tmp_path, "desktop")

    thread = _thread([dropped], out_dir=where)
    thread.run()

    staged = os.path.join(where, "one.mp4")
    assert thread.started == [(0, dropped), (0, staged)]
    assert seen["render"] == [(staged, os.path.join(where, "one_9x16.mp4"))]


def test_the_copy_says_so_before_the_work_starts(qapp, monkeypatch, tmp_path):
    """A big film takes minutes to copy and the bar is priced in ffmpeg
    seconds, so it sits at zero through it. The pass name is what tells the
    user the app is working, not stuck."""
    _fake_legs(monkeypatch)
    thread = _thread([_film(tmp_path, "desktop")], out_dir=str(tmp_path / "results"))

    thread.run()

    assert thread.ticks[0] == (0.0, "copying to the folder")


def test_a_folder_that_cannot_hold_the_copy_names_every_file_and_finishes(
    qapp, monkeypatch, tmp_path
):
    """A path that is a file, not a folder: the run says which files it could
    not stage and moves to the next instead of dying on the first."""
    seen = _fake_legs(monkeypatch)
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the folder should be")

    thread = _thread(
        [_film(tmp_path, "desktop"), _film(tmp_path, "phone", "two.mp4")],
        out_dir=str(blocker),
    )

    thread.run()

    assert seen == {"render": [], "split": []}
    assert any("one.mp4" in line for line in thread.lines)
    assert any("two.mp4" in line for line in thread.lines)
    assert thread.lines[-1] == "__done__"


def test_a_copy_that_dies_halfway_leaves_nothing_behind(
    qapp, monkeypatch, tmp_path
):
    """A full disk stops the copy with a part of the film on disk. That part
    is not a result: it is taken back out, and the next file still gets its
    turn at the folder."""
    _fake_legs(monkeypatch)
    where = tmp_path / "results"

    def half_copy(source, target, stopped):
        (where / os.path.basename(target)).write_bytes(b"hal")
        raise OSError("the disk filled up")

    monkeypatch.setattr(engine, "_copy_file", half_copy)
    thread = _thread([_film(tmp_path, "desktop")], out_dir=str(where))

    thread.run()

    assert not (where / "one.mp4").exists()
    assert any("the disk filled up" in line for line in thread.lines)


def test_a_surprise_from_the_copy_ends_the_file_not_the_run(
    qapp, monkeypatch, tmp_path
):
    """The copy says it raises OSError, and the leg around it catches that.
    Anything else it did not expect - a name the filesystem refuses, a
    library that throws what it was not asked to - is still one file's
    sentence, not the end of the list."""
    _fake_legs(monkeypatch)

    def no_name(folder, base):
        raise RuntimeError("the folder had a name nobody expected")

    monkeypatch.setattr(engine, "unique_basename", no_name)
    thread = _thread(
        [_film(tmp_path, "desktop"), _film(tmp_path, "phone", "two.mp4")],
        out_dir=str(tmp_path / "results"),
    )

    thread.run()

    assert any("one.mp4" in line for line in thread.lines)
    assert any("two.mp4" in line for line in thread.lines)
    assert thread.lines[-1] == "__done__"


def test_stop_ends_a_copy_under_way(monkeypatch, tmp_path):
    """Stop says "Stopping after the file in hand", and a write started is a
    write finished - except a copy, which the user can be waiting minutes on.
    The chunks check the flag, so what Stop leaves behind is nothing."""
    monkeypatch.setattr(engine, "COPY_CHUNK", 4)
    folder = tmp_path / "results"
    film = tmp_path / "one.mp4"
    film.write_bytes(b"x" * 40)
    lines = []
    chunks = []

    def stop_after_the_first_chunk():
        chunks.append(1)
        return len(chunks) > 1

    staged = engine.stage_for_folder(
        str(film), str(folder), lines.append, stopped=stop_after_the_first_chunk
    )

    assert staged is None
    assert not (folder / "one.mp4").exists()
    assert any("stopped" in line for line in lines)


def test_stop_pressed_during_the_copy_leaves_the_file_unworked(qapp, monkeypatch, tmp_path):
    """The page's Stop reaches the copy the worker is inside, so no leg runs
    over a file that never finished coming over."""
    seen = _fake_legs(monkeypatch)
    where = tmp_path / "results"
    thread = _thread([_film(tmp_path, "desktop")], out_dir=str(where))
    thread.progress.connect(
        lambda percent, stage: thread.stop() if stage == "copying to the folder" else None
    )

    thread.run()

    assert seen == {"render": [], "split": []}
    assert not (where / "one.mp4").exists()
    assert thread.lines[-1] == "__done__"


def test_two_runs_of_the_same_name_do_not_share_a_copy(tmp_path, monkeypatch):
    """The folder is one flat place and two files can be named the same:
    the name and its copy are reserved in one lock, so a second worker is
    told the next name rather than writing over the film already there."""
    sources = []
    for name, text in (("desktop", b"from the desktop"), ("phone", b"from the phone")):
        directory = tmp_path / name
        directory.mkdir()
        path = directory / "clip.mp4"
        path.write_bytes(text)
        sources.append((str(path), text))

    def slow_copy(source, target, stopped):
        time.sleep(0.02)
        with open(source, "rb") as src, open(target, "wb") as dst:
            dst.write(src.read())
        return True

    monkeypatch.setattr(engine, "_copy_file", slow_copy)
    folder = str(tmp_path / "results")
    ready = threading.Barrier(2)
    staged = {}

    def stage(key):
        ready.wait()
        staged[key] = engine.stage_for_folder(
            sources[key][0], folder, lambda line: None
        )

    workers = [threading.Thread(target=stage, args=(key,)) for key in (0, 1)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)

    assert {os.path.basename(staged[0]), os.path.basename(staged[1])} == {
        "clip.mp4",
        "clip (2).mp4",
    }
    for key, (_path, text) in enumerate(sources):
        with open(staged[key], "rb") as handle:
            assert handle.read() == text


# --------------------------------------------------------- what the options allow


def test_the_worker_keeps_only_the_options_it_can_act_on(qapp):
    """The page's widgets cannot hand over a nonsense option, but the worker
    is built from the code as easily as from the page: a folder of spaces is
    no folder, a length that is not one of the app's is Off, and a count
    under one is one."""
    thread = LocalVideoThread(
        [ONE], vertical=True, split="30 seconds", clips=0, out_dir="   "
    )

    assert thread.split == engine.DEFAULT_SPLIT
    assert thread.clips == 1
    assert thread.out_dir is None


def test_the_options_the_worker_can_act_on_survive_the_trip(qapp, tmp_path):
    thread = LocalVideoThread(
        [ONE], vertical=True, split="30 s", clips=4, out_dir=f"  {tmp_path}  "
    )

    assert thread.split == "30 s"
    assert thread.clips == 4
    assert thread.out_dir == str(tmp_path)

