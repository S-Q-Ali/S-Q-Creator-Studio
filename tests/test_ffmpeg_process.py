"""Every ffmpeg child of a windowed app must stay off the screen.

The portable build is `--windowed`: it has no console, so Windows gives each
ffmpeg child one of its own. A long job then filled the desktop with blank
terminal windows, which is what the owner saw.
"""

import subprocess

import pytest

from s_q_ali_media_downloader.core import ffmpeg_process


@pytest.fixture
def fake_run(monkeypatch):
    """Capture what would have been handed to subprocess.run."""

    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "stdout text", "stderr text")

    monkeypatch.setattr(ffmpeg_process.subprocess, "run", run)
    return calls


def _force_platform(monkeypatch, name):
    monkeypatch.setattr(ffmpeg_process.sys, "platform", name)


class _FakeStartupInfo:
    """The Windows STARTUPINFO shape, for a machine that has no such class."""

    def __init__(self):
        self.dwFlags = 0
        self.wShowWindow = None


def _win_names(monkeypatch):
    """Put the Windows-only `subprocess` names in place before faking win32.

    `sys.platform` can be forced on any OS; `subprocess.STARTUPINFO` cannot.
    A Linux or macOS CI cell has no such attribute, so the Windows branch died
    with an AttributeError before it could be tested. These are the documented
    Win32 values, so on Windows the stand-in is the same number as the real
    constant and the assertions below keep their meaning on every platform.
    """
    module = ffmpeg_process.subprocess
    monkeypatch.setattr(module, "STARTUPINFO", _FakeStartupInfo, raising=False)
    monkeypatch.setattr(module, "STARTF_USESHOWWINDOW", 0x1, raising=False)
    monkeypatch.setattr(module, "SW_HIDE", 0, raising=False)
    monkeypatch.setattr(module, "CREATE_NO_WINDOW", 0x08000000, raising=False)


class _FakeProcess:
    """An ffmpeg child whose output is a list of lines, drained on close."""

    def __init__(self, lines):
        self._lines = iter(lines)
        self.stdout = self
        self.returncode = None

    def __iter__(self):
        return self._lines

    def __next__(self):
        return next(self._lines)

    def wait(self):
        return 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_windows_gets_a_child_with_no_console(monkeypatch):
    _force_platform(monkeypatch, "win32")
    _win_names(monkeypatch)

    kwargs = ffmpeg_process.child_kwargs()

    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE


@pytest.mark.parametrize("name", ["linux", "darwin"])
def test_other_platforms_need_no_kwargs(monkeypatch, name):
    _force_platform(monkeypatch, name)

    assert ffmpeg_process.child_kwargs() == {}


def test_run_hides_the_window_and_keeps_the_pipes_apart(monkeypatch, fake_run):
    _force_platform(monkeypatch, "win32")
    _win_names(monkeypatch)

    result = ffmpeg_process.run(["ffmpeg", "-version"], cwd="work")

    command, kwargs = fake_run[0]
    assert command == ["ffmpeg", "-version"]
    assert kwargs["cwd"] == "work"
    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    assert result.stderr == "stderr text"


def test_a_missing_ffmpeg_reaches_the_caller_as_it_was(monkeypatch):
    def exploding(command, **kwargs):
        raise FileNotFoundError("no ffmpeg here")

    monkeypatch.setattr(ffmpeg_process.subprocess, "run", exploding)

    with pytest.raises(FileNotFoundError):
        ffmpeg_process.run(["ffmpeg", "-version"])


def test_stream_reports_each_line_as_it_lands(monkeypatch):
    _force_platform(monkeypatch, "win32")
    _win_names(monkeypatch)
    lines = ["frame=1 out_time_ms=1000000\n", "out_time_ms=2000000\n", "progress=end\n"]

    class FakeProcess:
        def __init__(self):
            self.stdout = iter(lines)
            self.returncode = None

        def wait(self):
            return 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    spawned = {}

    def popen(command, **kwargs):
        spawned.update(command=command, kwargs=kwargs)
        return FakeProcess()

    monkeypatch.setattr(ffmpeg_process.subprocess, "Popen", popen)
    seen = []

    result = ffmpeg_process.stream(["ffmpeg", "-i", "a.mp4"], on_line=seen.append)

    assert seen == lines
    assert spawned["kwargs"]["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert spawned["kwargs"]["stderr"] is subprocess.STDOUT
    assert result.returncode == 0
    assert result.stdout == "".join(lines)


@pytest.mark.parametrize(
    "line, seconds",
    [
        ("out_time_ms=1250000\n", 1.25),
        ("out_time_us=4500000\n", 4.5),
        ("out_time=00:00:02.500000\n", 2.5),
        ("frame=12 fps=30.0 out_time_ms=3000000", 3.0),
        ("progress=continue\n", None),
        ("size=1024KiB time=00:00:01.00", None),
        ("out_time=N/A\n", None),
        ("", None),
    ],
)
def test_the_progress_line_gives_seconds_of_film(line, seconds):
    assert ffmpeg_process.out_time_seconds(line) == seconds


def test_the_hook_divides_the_film_read_by_the_film_there_is():
    """ffmpeg counts in seconds of film, the bar counts in shares of a pass,
    and the length is what turns one into the other."""
    told = []

    hook = ffmpeg_process.progress_hook(10.0, told.append)
    hook("out_time_ms=2500000\n")
    hook("out_time_ms=45000000\n")

    assert told == [0.25, 1.0]


@pytest.mark.parametrize("seconds, listener", [(0.0, None), (0.0, print), (10.0, None)])
def test_a_pass_with_nothing_to_read_reports_no_hook(seconds, listener):
    assert ffmpeg_process.progress_hook(seconds, listener) is None


def test_watching_asks_ffmpeg_for_its_counters_before_the_output(monkeypatch, fake_run):
    """``-progress pipe:1`` is an output option, and the output file is always
    the last argument, so the pair goes in front of it - after the filters and
    before the file ffmpeg is writing."""

    watched = []

    def popen(command, **kwargs):
        watched.append(command)
        return _FakeProcess(["out_time_ms=5000000\n"])

    monkeypatch.setattr(ffmpeg_process.subprocess, "Popen", popen)
    told = []

    result = ffmpeg_process.watch(
        ["ffmpeg", "-i", "a.mp4", "-vf", "crop=1", "-y", "b.mp4"],
        duration=10.0,
        on_progress=told.append,
    )

    assert watched[0] == [
        "ffmpeg",
        "-i",
        "a.mp4",
        "-vf",
        "crop=1",
        "-y",
        "-progress",
        "pipe:1",
        "b.mp4",
    ]
    assert told == [0.5]
    assert result.returncode == 0


def test_a_pass_nobody_watches_runs_exactly_as_before(monkeypatch, fake_run):
    result = ffmpeg_process.watch(["ffmpeg", "-i", "a.mp4", "-y", "b.mp4"], duration=10.0)

    command, kwargs = fake_run[0]
    assert command == ["ffmpeg", "-i", "a.mp4", "-y", "b.mp4"]
    assert "-progress" not in command
    assert kwargs["capture_output"] is True
    assert result.returncode == 0
