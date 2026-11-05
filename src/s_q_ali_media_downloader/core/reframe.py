"""The maths of the 9:16 reframe - where the crop window sits over time.

Nothing here touches a video. The window is cut, the path is smoothed, and
the path is written out as the command file that ffmpeg's ``sendcmd`` reads.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

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


def _even(value: int) -> int:
    """Round down to the nearest even number - an odd offset shifts the
    chroma by half a pixel."""
    return value - value % 2


def _towards(current: int, target: int, step: int) -> int:
    if abs(target - current) <= step:
        return target
    return _even(current + step if target > current else current - step)
