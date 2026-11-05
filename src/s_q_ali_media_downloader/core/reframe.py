"""The maths of the 9:16 reframe - where the crop window sits over time.

Nothing here touches a video. The window is cut, the path is smoothed, and
the path is written out as the command file that ffmpeg's ``sendcmd`` reads.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: The window is cut in whole 16-row bands, so the 9:16 comes out exact and
#: the scale to the output size does not stretch the picture.
CROP_HEIGHT_STEP = 32

#: The window may travel at most this much of its own width between two
#: samples, so a detection that jumps does not snap the camera.
MAX_STEP_RATIO = 0.25


@dataclass(frozen=True)
class Sample:
    time: float
    x: int


@dataclass(frozen=True)
class RenderResult:
    output: str | None = None
    note: str = ""


def crop_window(source_width: int, source_height: int) -> tuple[int, int]:
    """The largest exact 9:16 window that fits in the frame."""
    height = (source_height // CROP_HEIGHT_STEP) * CROP_HEIGHT_STEP
    width = height * 9 // 16
    if height < CROP_HEIGHT_STEP or width > source_width:
        raise ValueError(
            f"a {source_width}x{source_height} frame has no 9:16 window in it"
        )
    return width, height


def clamp_x(x: int, source_width: int, crop_width: int) -> int:
    """The window may not leave the frame."""
    return max(0, min(x, source_width - crop_width))


def max_step_for(crop_width: int) -> int:
    """How far the window may travel between two samples."""
    return _even(int(crop_width * MAX_STEP_RATIO))


def crop_path(
    positions: Sequence[int | None],
    source_width: int,
    crop_width: int,
    max_step: int | None = None,
) -> list[int]:
    """The legal path of the crop window.

    The wanted positions are clamped into the frame and then moved towards at
    most ``max_step`` per sample. A sample with no detection keeps the
    position it had.
    """
    step = max_step_for(crop_width) if max_step is None else max_step
    path: list[int] = []
    current: int | None = None

    for wanted in positions:
        if wanted is None:
            path.append(current if current is not None else 0)
            continue
        target = _even(clamp_x(wanted, source_width, crop_width))
        if current is None:
            current = target
        else:
            current = _towards(current, target, step)
        path.append(current)

    return path


def write_command_file(path: Path | str, samples: Iterable[Sample]) -> None:
    """Write the path out in the format ffmpeg's ``sendcmd`` reads."""
    lines = [f"{sample.time:.3f} crop@c x {sample.x};" for sample in samples]
    Path(path).write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def output_size(source_height: int) -> tuple[int, int]:
    """The vertical size: the source height across, 16:9 taller."""
    return source_height, source_height * 16 // 9


def vertical_output_path(source: str) -> str:
    """Where the vertical version of a download goes."""
    return f"{os.path.splitext(source)[0]}_9x16.mp4"


def filter_chain(command_file: str, source_width: int, source_height: int) -> str:
    """The filter chain: read the path, cut the window out, make it vertical."""
    crop_width, crop_height = crop_window(source_width, source_height)
    out_width, out_height = output_size(source_height)
    x = (source_width - crop_width) // 2
    y = (source_height - crop_height) // 2
    return (
        f"sendcmd=f={command_file},"
        f"crop@c=w={crop_width}:h={crop_height}:x={x}:y={y},"
        f"scale={out_width}:{out_height},setsar=1"
    )


def build_command(
    ffmpeg: str, source: str, output: str, chain: str
) -> list[str]:
    """The ffmpeg call. The audio is copied, never re-encoded."""
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        source,
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        chain,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        output,
    ]


def render_vertical(
    source: str,
    output: str,
    source_width: int,
    source_height: int,
    samples: Sequence[Sample],
    ffmpeg: str = "ffmpeg",
    runner: Callable[[list[str], str], int] | None = None,
) -> RenderResult:
    """Render the vertical version of a download beside it.

    A download that is already vertical, or that has no video at all, is left
    alone and says why.
    """
    if not source_width or not source_height:
        return RenderResult(None, "The download has no video, only audio.")
    if source_width * 16 <= source_height * 9:
        return RenderResult(None, "The download is already vertical.")

    try:
        chain = filter_chain("crop.cmd", source_width, source_height)
    except ValueError as exc:
        return RenderResult(None, str(exc))

    command = build_command(ffmpeg, os.path.abspath(source), os.path.abspath(output), chain)
    run = runner or _run_ffmpeg
    with tempfile.TemporaryDirectory() as work:
        write_command_file(os.path.join(work, "crop.cmd"), samples)
        code = run(command, work)

    if code != 0 or not os.path.isfile(output):
        return RenderResult(None, "The vertical version could not be made.")
    return RenderResult(output, "The vertical version is beside the original.")


def _run_ffmpeg(command: list[str], cwd: str) -> int:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        logger.error("ffmpeg failed: %s", (result.stderr or "").strip()[-800:])
    return result.returncode


def _even(value: int) -> int:
    """Round down to the nearest even number - an odd offset shifts the
    chroma by half a pixel."""
    return value - value % 2


def _towards(current: int, target: int, step: int) -> int:
    if abs(target - current) <= step:
        return target
    return _even(current + step if target > current else current - step)
