"""Where a long video is cut into shorts, and what the app tells the user.

The cut points come from the pauses in the speech and the changes of scene:
a short that ends in the middle of a sentence is worse than one a few
seconds off its length.
"""

from __future__ import annotations

import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

logger = logging.getLogger(__name__)

#: YouTube Shorts stops at three minutes.
SHORTS_LIMIT = 180.0

#: A pause in the speech, in dB below the loudest part of the track.
SILENCE_THRESHOLD = -30

#: A pause shorter than this is a gap between words, not a pause to cut at.
SILENCE_MIN = 0.4

#: How far from the target a pause may sit and still be used.
CUT_WINDOW = 15.0

#: The scene score above which a frame counts as a change of scene.
SCENE_THRESHOLD = 0.4

#: The lengths the dropdown offers.
TARGETS = {"30 s": 30.0, "45 s": 45.0, "60 s": 60.0, "90 s": 90.0}

_SILENCE = re.compile(r"silence_(start|end):\s*(-?[\d.]+)")
_SCENE_TIME = re.compile(r"pts_time:\s*([\d.]+)")
_SCENE_SCORE = re.compile(r"lavfi\.scene_score=([\d.]+)")

Runner = Callable[[list[str]], str]


@dataclass(frozen=True)
class Segment:
    """One short: where it starts and where it ends."""

    index: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class CutPlan:
    """The split of a video, and the line the app shows about it."""

    segments: list[Segment] = field(default_factory=list)
    clip_duration: float = 0.0
    clips: int = 0
    note: str = ""


@dataclass(frozen=True)
class SplitResult:
    outputs: list[str] = field(default_factory=list)
    note: str = ""


def format_duration(seconds: float) -> str:
    """A length as short text: 330 -> ``5 min 30 s``."""
    total = round(seconds)
    minutes, rest = divmod(total, 60)
    if minutes and rest:
        return f"{minutes} min {rest} s"
    if minutes:
        return f"{minutes} min"
    return f"{rest} s"


def clips_that_fit(duration: float) -> int:
    """How many Shorts-length clips the video could be cut into."""
    return max(1, math.ceil(duration / SHORTS_LIMIT))


def clip_note(segments: Sequence[Segment], duration: float) -> str:
    count = len(segments)
    shortest = min(segment.duration for segment in segments)
    longest = max(segment.duration for segment in segments)
    text = f"{count} clips → about {format_duration(duration / count)} each on average."
    if not math.isclose(shortest, longest):
        text += f" Planned lengths: {format_duration(shortest)} to {format_duration(longest)}."
    if longest > SHORTS_LIMIT:
        text += " At least one clip is over YouTube Shorts' 3-minute limit."
        text += f" At equal lengths, {clips_that_fit(duration)} clips would fit; pauses may vary."
    return text


def parse_silences(text: str) -> list[float]:
    """The middle of every pause ffmpeg's silencedetect found."""
    points: list[float] = []
    start: float | None = None
    for match in _SILENCE.finditer(text):
        kind, value = match.group(1), float(match.group(2))
        if kind == "start":
            start = value
        elif start is not None:
            if value - start >= SILENCE_MIN:
                points.append((start + value) / 2)
            start = None
    return points


def parse_scene_changes(text: str, threshold: float = SCENE_THRESHOLD) -> list[float]:
    """The times ffmpeg scored as a change of scene."""
    points: list[float] = []
    moment: float | None = None
    for line in text.splitlines():
        time_match = _SCENE_TIME.search(line)
        if time_match:
            moment = float(time_match.group(1))
            continue
        score_match = _SCENE_SCORE.search(line)
        if score_match and moment is not None:
            if float(score_match.group(1)) >= threshold:
                points.append(moment)
            moment = None
    return points


def nearest_point(target: float, points: Sequence[float], window: float) -> float | None:
    """The point closest to the target, if one is close enough."""
    best: float | None = None
    for point in points:
        if abs(point - target) > window:
            continue
        if best is None or abs(point - target) < abs(best - target):
            best = point
    return best


def plan_cuts(
    duration: float,
    target: float | None = None,
    silences: Sequence[float] = (),
    scenes: Sequence[float] = (),
    clips: int | None = None,
) -> CutPlan:
    """The split of a video into shorts.

    ``target`` is the length of each short; ``clips`` asks for a number of
    shorts instead, and the length each one gets is the duration divided by
    that number. Without either, the cut points are the scene changes.
    """
    if not math.isfinite(duration) or duration < 0:
        raise ValueError("The video duration must be finite and nonnegative.")
    if target is not None and (not math.isfinite(target) or target <= 0):
        raise ValueError("The target duration must be finite and positive.")
    if clips is not None and (type(clips) is not int or clips < 1):
        raise ValueError("The clip count must be a positive integer.")
    if target is not None and clips is not None:
        raise ValueError("Choose a target duration or a clip count, not both.")
    if duration == 0:
        return CutPlan(note="No video duration; not split.")
    if clips == 1 or (target is not None and duration <= target):
        return CutPlan(note="One clip covers the video; not split.")

    silences = sorted({p for p in silences if math.isfinite(p) and 0 < p < duration})
    scenes = sorted({p for p in scenes if math.isfinite(p) and 0 < p < duration})
    clip_duration = duration / clips if clips is not None else (target or 0.0)
    if clip_duration:
        count = clips if clips is not None else math.ceil(duration / clip_duration)
        targets = [index * clip_duration for index in range(1, count)]
        boundaries = _target_boundaries(duration, targets, silences, scenes)
    else:
        boundaries = scenes

    if not boundaries:
        return CutPlan(note="No scene changes found; not split.")
    segments = _segments(boundaries, duration)
    note = clip_note(segments, duration)
    if not clip_duration:
        note += " Cut at scene changes."
    return CutPlan(segments, clip_duration, len(segments), note)


def _target_boundaries(
    duration: float,
    targets: Sequence[float],
    silences: Sequence[float],
    scenes: Sequence[float],
) -> list[float]:
    boundaries: list[float] = []
    edges = [0.0, *targets, duration]
    for index, wanted in enumerate(targets, start=1):
        # Disjoint windows stop adjacent cuts reusing the same pause.
        low = (edges[index - 1] + wanted) / 2
        high = (wanted + edges[index + 1]) / 2
        chosen = nearest_point(wanted, [p for p in silences if low < p < high], CUT_WINDOW)
        if chosen is None:
            chosen = nearest_point(wanted, [p for p in scenes if low < p < high], CUT_WINDOW)
        boundaries.append(wanted if chosen is None else chosen)
    return boundaries


def _segments(boundaries: Sequence[float], duration: float) -> list[Segment]:
    """The clips between the cut points, covering the whole video."""
    edges = [0.0, *boundaries, duration]
    return [
        Segment(index, start, end)
        for index, (start, end) in enumerate(pairwise(edges))
    ]


def detect_silences(
    video: str, ffmpeg: str = "ffmpeg", runner: Runner | None = None
) -> list[float]:
    """The pauses in the speech of a video."""
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-i",
        os.path.abspath(video),
        "-map",
        "0:a:0?",
        "-vn",
        "-sn",
        "-dn",
        "-af",
        f"silencedetect=n={SILENCE_THRESHOLD}dB:d={SILENCE_MIN}",
        "-f",
        "null",
        "-",
    ]
    run = runner or _run_ffmpeg
    return parse_silences(run(command))


def detect_scene_changes(
    video: str, ffmpeg: str = "ffmpeg", runner: Runner | None = None
) -> list[float]:
    """The changes of scene in a video."""
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-i",
        os.path.abspath(video),
        "-map",
        "0:v:0",
        "-vf",
        f"select='gt(scene,{SCENE_THRESHOLD})',metadata=print",
        "-an",
        "-f",
        "null",
        "-",
    ]
    run = runner or _run_ffmpeg
    return parse_scene_changes(run(command))


def build_split_command(
    ffmpeg: str, source: str, output: str, segment: Segment,
) -> list[str]:
    # A 1/fps encoder time base can drop a frame at fractional cut boundaries.
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-i", os.path.abspath(source),
        "-ss", f"{segment.start:.9f}", "-t", f"{segment.duration:.9f}",
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-fps_mode:v", "passthrough",
        "-enc_time_base:v", "demux", "-c:a", "copy",
        "-movflags", "+faststart", os.path.abspath(output),
    ]


def split_video(
    source: str,
    plan: CutPlan,
    ffmpeg: str = "ffmpeg",
    runner: Callable[[list[str]], int] | None = None,
) -> SplitResult:
    if not plan.segments:
        return SplitResult(note=plan.note)
    original = Path(source).resolve()
    destinations = [
        original.with_name(f"{original.stem}_short{segment.index + 1:02d}.mp4")
        for segment in plan.segments
    ]
    if any(os.path.lexists(path) for path in destinations):
        return SplitResult(note="A short output already exists; nothing was overwritten.")
    outputs: list[str] = []
    run = runner or _run_split
    try:
        if not original.is_file():
            return SplitResult(note="The source could not be opened; no shorts made.")
        with tempfile.TemporaryDirectory(prefix=".shorts-", dir=original.parent) as work:
            for segment, destination in zip(plan.segments, destinations):
                staged = Path(work) / destination.name
                command = build_split_command(ffmpeg, str(original), str(staged), segment)
                code = run(command)
                if code != 0 or not staged.is_file() or staged.stat().st_size == 0:
                    return SplitResult(outputs, "The split could not finish; original kept.")
                _publish_clip(staged, destination)
                outputs.append(str(destination))
    except OSError:
        logger.warning("Could not finish writing shorts; original kept.")
        return SplitResult(outputs, "The split could not finish; original kept.")
    return SplitResult(outputs, f"{len(outputs)} shorts saved beside the original.")


def _publish_clip(staged: Path, destination: Path) -> None:
    created = False
    try:
        # Exclusive creation also protects against another writer during the render.
        with destination.open("xb") as output:
            created = True
            with staged.open("rb") as source:
                shutil.copyfileobj(source, output)
    except OSError:
        if created:
            destination.unlink(missing_ok=True)
        raise


def _run_split(command: list[str]) -> int:
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode:
        logger.warning("ffmpeg short render failed (exit %s).", result.returncode)
    return result.returncode


def _run_ffmpeg(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError:
        logger.warning("Could not start ffmpeg cut-point detection.")
        return ""
    if result.returncode != 0:
        logger.warning("ffmpeg cut-point detection failed (exit %s).", result.returncode)
        return ""
    return f"{result.stdout}\n{result.stderr}"
