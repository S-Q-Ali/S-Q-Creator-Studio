"""Running ffmpeg, and hearing how far it has got.

The portable build is `--windowed`: it has no console of its own, so Windows
hands every ffmpeg child one. A job that shells out four times a minute fills
the desktop with blank terminal windows. One place spawns ffmpeg, so one
place hides the window — and the same place reads ffmpeg's own progress
report, which is the only honest way to fill a bar while it runs.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable

_PROGRESS_TIME = re.compile(r"out_time_(?:us|ms)=(\d+)")
_CLOCK_TIME = re.compile(r"out_time=(\d+):(\d+):([\d.]+)")


def child_kwargs() -> dict:
    """The kwargs that keep a Windows child process off the screen."""
    if sys.platform != "win32":
        return {}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": info, "creationflags": subprocess.CREATE_NO_WINDOW}


def run(command: list[str], *, cwd: str | None = None) -> subprocess.CompletedProcess:
    """ffmpeg to completion, with its two output streams kept apart."""
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        **child_kwargs(),
    )


def stream(command: list[str], *, cwd: str | None = None, on_line=None) -> subprocess.CompletedProcess:
    """ffmpeg to completion, handing every output line to ``on_line`` as it lands.

    The lines of both streams arrive together in ``stdout``, which is what a
    caller reading a progress report wants; a caller that needs the two apart
    wants :func:`run`.
    """
    with subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        **child_kwargs(),
    ) as process:
        lines = []
        for line in process.stdout:
            lines.append(line)
            if on_line is not None:
                on_line(line)
        returncode = process.wait()
    return subprocess.CompletedProcess(command, returncode, "".join(lines), "")


def out_time_seconds(line: str) -> float | None:
    """The seconds of film ffmpeg says it has processed, from one progress line."""
    stamp = _PROGRESS_TIME.search(line)
    if stamp:
        return int(stamp.group(1)) / 1_000_000
    clock = _CLOCK_TIME.search(line)
    if clock:
        hours, minutes, rest = clock.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(rest)
    return None


def progress_hook(
    seconds: float, on_progress: Callable[[float], None] | None
) -> Callable[[str], None] | None:
    """The line hook that reads ffmpeg's own report as a fraction of a pass.

    With no length to divide by, or nobody listening, there is no hook and the
    job runs exactly as it did: ``-progress pipe:1`` costs nothing either way.
    """
    if on_progress is None or not seconds:
        return None

    def report(line: str) -> None:
        done = out_time_seconds(line)
        if done is not None:
            on_progress(min(done / seconds, 1.0))

    return report


def watch(
    command: list[str],
    *,
    duration: float = 0.0,
    on_progress: Callable[[float], None] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """A pass over a film, with how far it has got read out as it runs.

    ``-progress pipe:1`` makes ffmpeg write its counters to stdout instead of
    hiding them in a stats line, and the output file is always the last
    argument, so the option goes before it. With nothing to read - no length,
    or nobody listening - the command runs as :func:`run` has always run it.
    """
    hook = progress_hook(duration, on_progress)
    if hook is None:
        return run(command, cwd=cwd)
    return stream(
        [*command[:-1], "-progress", "pipe:1", command[-1]], cwd=cwd, on_line=hook
    )
