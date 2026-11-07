"""The maths of the 9:16 reframe - where the crop window sits over time.

The window is cut, the path is smoothed, and the path is written out as the
command file that ffmpeg's ``sendcmd`` reads. ``analyse`` finds the picture
and the path in a real file; ``render_vertical`` writes the vertical version.
"""

from __future__ import annotations

import logging
import math
import os
import re
import statistics
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg_process, output_names

logger = logging.getLogger(__name__)

#: YuNet finds a face. It is small and it is fast.
FACE_MODEL = "face_detection_yunet_2023mar.onnx"

#: NanoDet finds a person. It is the fallback for a shot with no face in it.
BODY_MODEL = "object_detection_nanodet_2022nov_int8.onnx"

#: The size NanoDet was exported at.
BODY_SIZE = 416

#: COCO class 0 is the person.
PERSON_CLASS = 0

#: How sure a detection has to be before it counts.
BODY_SCORE = 0.35
BODY_NMS = 0.6

#: The window is cut in whole 32-row bands, so the 9:16 comes out exact and
#: the scale to the output size does not stretch the picture.
CROP_HEIGHT_STEP = 32

#: The vertical file stops at full HD - 60 of those bands, 1080x1920. The
#: window cut from a 4K film is about a thousand pixels wide, so a taller
#: output is the same picture in more bytes and more encode time than a
#: phone ever shows.
MAX_OUTPUT_UNITS = 60

#: The detectors do not need the file at its own size. This is the copy they
#: read, and it cannot be much smaller: at 1280 the subject of a 4K film is a
#: few pixels and the path misses the one read at full size by over half a
#: window on 49 samples in 100; at 1920 it misses on 9, for a fifth of the
#: work.
PROXY_WIDTH = 1920
PROXY_FPS = 5.0

#: The reads of the film an analysis makes: the picture, the copy it detects
#: on, and the subject.
ANALYSIS_PASSES = 3

#: One bad detection is one read in ``MEDIAN_WINDOW``, so the position the
#: window is asked for is the median of the last reads it believed in.
MEDIAN_WINDOW = 5

#: Of the distance the median leaves, the window is asked for this much per
#: sample. Chasing every sample exactly is what made the camera crawl.
SMOOTH_ALPHA = 0.35

#: A position this close to where the window already sits is not chased at
#: all, so a subject that only wanders leaves the camera still. On a 4K probe
#: this tenth of the window was the point past which chasing more bought a
#: camera that never settled and no framing worth having: the measured lag
#: from the subject went from 115 to 117 pixels and the still frames from 72
#: to 82 per cent.
DEADBAND_RATIO = 0.10

#: The window never travels more than half its own width in a second, and no
#: pan is over in less than half a second. A cut is not a pan and obeys
#: neither: see ``CUT_RATIO``.
MAX_SPEED_RATIO = 0.5
MIN_GLIDE_SECONDS = 0.5

#: Two reads this far apart across the picture are a different shot, not a
#: move within this one. Measured on a 4K film: the subject moves 17 pixels
#: between two samples inside a shot and a thousand at a cut. A pan across a
#: cut is the unsteady camera; a new framing the moment the picture changes
#: is not.
CUT_RATIO = 0.15

#: A box this far across the picture from where the subject last was is a
#: different subject: a cut to another shot, or someone bigger walking in.
STICKY_RATIO = 0.2


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


def smooth_positions(
    positions: Sequence[int | None], source_width: int
) -> list[int | None]:
    """The positions the window is asked for, with the spikes taken out.

    The median is over the last few reads this shot is still believed to be
    in, so the first detection is the position it reads and nothing arrives
    before it happens. A position of None is a frame with nothing in it: it is
    passed through, and the window keeps the position it had.

    A read further across the picture than the cut measured on a real film is
    either the shot changing or one detection pointing elsewhere, and the
    sample after it tells them apart. A cut the next read agrees with is the
    new position at once and starts the median again, because a median taken
    across a cut frames a picture that is in neither shot; a far read nobody
    agrees with is not a position at all, and moves nothing.
    """
    out: list[int | None] = []
    smoothed: int | None = None
    previous: int | None = None
    seen: list[int] = []
    cut = CUT_RATIO * source_width

    for index, wanted in enumerate(positions):
        if wanted is None:
            out.append(None)
            continue
        if previous is not None and abs(wanted - previous) > cut:
            if _next_sample_agrees(positions, index, wanted, previous):
                smoothed = wanted
                seen = [wanted]
                previous = wanted
            out.append(smoothed)
            continue
        seen.append(wanted)
        middle = round(statistics.median_low(seen[-MEDIAN_WINDOW:]))
        smoothed = (
            middle
            if smoothed is None
            else round(smoothed + SMOOTH_ALPHA * (middle - smoothed))
        )
        out.append(smoothed)
        previous = wanted

    return out


def _next_sample_agrees(
    positions: Sequence[int | None],
    index: int,
    wanted: int,
    previous: int,
) -> bool:
    """Whether the sample after this one is nearer the new position than the
    old: the picture changed, rather than one detection pointing elsewhere."""
    for value in positions[index + 1 : index + MEDIAN_WINDOW + 1]:
        if value is not None:
            return abs(value - wanted) <= abs(value - previous)
    return False


def glide_seconds(distance: int, crop_width: int) -> float:
    """How long the window takes to travel ``distance`` pixels."""
    return max(MIN_GLIDE_SECONDS, distance / (MAX_SPEED_RATIO * crop_width))


def write_command_file(path: Path | str, samples: Iterable[Sample]) -> None:
    """Write the path out in the format ffmpeg's ``sendcmd`` reads.

    ``sendcmd`` holds the value until the next command, so a frame that keeps
    the position needs no line: a film that pans ten times is ten lines, not
    one a frame.
    """
    lines: list[str] = []
    last: int | None = None
    for sample in samples:
        if sample.x != last:
            lines.append(f"{sample.time:.3f} crop@c x {sample.x};")
            last = sample.x

    Path(path).write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def output_size(source_height: int) -> tuple[int, int]:
    """The vertical size: the source height, never more than full HD.

    The size is cut from the same 18x32 grid as the crop window, so the
    scale from the window to the output is the same in both directions and
    the picture is not stretched.
    """
    units = max(1, min(MAX_OUTPUT_UNITS, round(source_height / 18)))
    return 18 * units, 32 * units


def vertical_output_path(source: str) -> str:
    """Where the vertical version of a download goes.

    A name the folder already holds - from an earlier run or a file the user
    put there - is not asked for twice; the next part of it is.
    """
    folder, name = os.path.split(source)
    return output_names.next_part_path(folder, os.path.splitext(name)[0] + "_9x16")


def filter_chain(
    command_file: str,
    source_width: int,
    source_height: int,
    box: tuple[int, int] | None = None,
) -> str:
    """The filter chain: read the path, cut the window out, make it vertical.

    ``box`` is where the picture sits inside the frame. A film with black
    bands above and below has to be cut from the picture, or the bands travel
    into the vertical file and the frame is not filled.
    """
    top, height = _picture_rows(source_width, source_height, box)
    crop_width, crop_height = crop_window(source_width, height)
    out_width, out_height = output_size(height)
    x = _even((source_width - crop_width) // 2)
    y = _even(top + (height - crop_height) // 2)
    return (
        f"sendcmd=f={command_file},"
        f"crop@c=w={crop_width}:h={crop_height}:x={x}:y={y},"
        f"scale={out_width}:{out_height},setsar=1"
    )


def _picture_rows(
    source_width: int, source_height: int, box: tuple[int, int] | None
) -> tuple[int, int]:
    """The rows the window is cut from, and where they start.

    A box under half the frame is not a letterbox - a subtitle bar, or a
    decode that reported nothing - and the whole frame is cut instead. The
    widest film in release is 2.76:1, which is still 58 percent of 16:9.
    """
    if box:
        top, bottom = box
        height = bottom - top + 1
        if height * 2 >= source_height:
            try:
                crop_window(source_width, height)
            except ValueError:
                pass
            else:
                return top, height
    return 0, source_height


def detect_picture(
    video: str,
    ffmpeg: str = "ffmpeg",
    duration: float = 0.0,
    progress: Callable[[float], None] | None = None,
) -> tuple[int, int] | None:
    """Where the picture is inside the frame, as ffmpeg's cropdetect sees it."""
    result = ffmpeg_process.watch(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-nostdin",
            "-i",
            video,
            "-vf",
            "cropdetect=24:2:0",
            "-an",
            "-f",
            "null",
            "-",
        ],
        duration=duration,
        on_progress=progress,
    )
    # Running the scan with a listener merges its two streams into stdout, so
    # the report is read from whichever of them is holding it.
    return detect_picture_text(result.stderr or result.stdout or "")


def detect_picture_text(report: str) -> tuple[int, int] | None:
    """The picture box out of ffmpeg's cropdetect output: first row, last row.

    The box the report gives most often is the one to cut to. A film keeps
    its bands from end to end, so they are the rule and a full-frame shot is
    the exception; a tie goes to the bigger box, which cuts less.
    """
    boxes = [
        (int(top), int(top) + int(height) - 1)
        for _width, height, _left, top in re.findall(
            r"crop=(\d+):(\d+):(\d+):(\d+)", report
        )
    ]
    if not boxes:
        return None
    return max(set(boxes), key=lambda box: (boxes.count(box), box[1] - box[0]))


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
    box: tuple[int, int] | None = None,
    duration: float = 0.0,
    progress: Callable[[float], None] | None = None,
) -> RenderResult:
    """Render the vertical version of a video beside it.

    A file that is already vertical, or that has no video at all, is left
    alone and says why. So is ``output`` if something is standing at it: this
    writes a new file or nothing.
    """
    if not source_width or not source_height:
        return RenderResult(None, "The video has no picture, only audio.")
    if not is_landscape(source_width, source_height):
        return RenderResult(None, "The video is already vertical.")

    try:
        chain = filter_chain("crop.cmd", source_width, source_height, box)
    except ValueError as exc:
        return RenderResult(None, str(exc))

    output = os.path.abspath(output)
    try:
        # Holding the name by writing it is what makes the -y below safe: the
        # file ffmpeg replaces is this placeholder, never one that was there.
        with open(output, "xb"):
            pass
    except OSError:
        return RenderResult(
            None,
            f"{os.path.basename(output)} is already there; nothing was overwritten.",
        )

    command = build_command(ffmpeg, os.path.abspath(source), output, chain)
    length = duration or (duration_seconds(source) if progress else 0.0)
    run = runner or _ffmpeg_runner(length, progress)
    with tempfile.TemporaryDirectory() as work:
        write_command_file(os.path.join(work, "crop.cmd"), samples)
        code = run(command, work)

    if code != 0 or not os.path.isfile(output) or os.path.getsize(output) == 0:
        # A half-written mp4 is not a result, and the next run would count it as
        # one and step aside for it, so the file this render made is taken back.
        try:
            os.remove(output)
        except OSError:
            pass
        return RenderResult(None, "The vertical version could not be made.")
    return RenderResult(output, f"Made {os.path.basename(output)}.")


def _ffmpeg_runner(duration: float, progress: Callable[[float], None] | None):
    """An ffmpeg call that says how far over the film it has got, if asked."""

    def run(command: list[str], cwd: str) -> int:
        result = ffmpeg_process.watch(
            command, duration=duration, on_progress=progress, cwd=cwd
        )
        if result.returncode != 0:
            logger.error(
                "ffmpeg failed: %s", (result.stderr or result.stdout or "").strip()[-800:]
            )
        return result.returncode

    return run


def path_from_centres(
    centres: Sequence[tuple[float, int | None]],
    source_width: int,
    crop_width: int,
    fps: float,
) -> list[Sample]:
    """The crop path as ffmpeg should read it: a keyframe for every frame.

    The centres were read five times a second and ``sendcmd`` holds a value
    until the next command, so a path written at that rate is a staircase of
    teleports. Here the window holds still inside the deadband and pans
    between the positions it is asked for, except across a cut: there it is
    set to the new framing on the frame that read it, because a pan across a
    cut is the camera that never settles. A pan still running when the last
    centre was read runs on to its end.
    """
    if not centres:
        return []
    times = [time for time, _ in centres]
    wanted = [
        None if centre is None else centre - crop_width // 2
        for _time, centre in centres
    ]
    targets = smooth_positions(wanted, source_width)
    last_frame = round(times[-1] * fps)
    deadband = DEADBAND_RATIO * crop_width
    cut = CUT_RATIO * source_width

    current = _even((source_width - crop_width) // 2)
    glide_from = glide_to = current
    glide_left = glide_total = 0.0
    index = 0
    path: list[Sample] = []
    frame = -1

    while frame < last_frame or glide_left > 0:
        frame += 1
        time = frame / fps
        while index + 1 < len(times) and times[index + 1] <= time:
            index += 1
        if targets[index] is not None:
            target = _even(clamp_x(targets[index], source_width, crop_width))
            where = glide_to if glide_left > 0 else current
            if abs(target - where) > deadband:
                # the cut is read from where the subject is, not from how far
                # the window is allowed to go: near an edge a cut is a shorter
                # move than it looks.
                if abs(_even(targets[index]) - current) > cut:
                    glide_left = 0.0
                    current = target
                else:
                    glide_from = current
                    glide_to = target
                    glide_total = glide_seconds(abs(target - current), crop_width)
                    glide_left = glide_total
        if glide_left > 0:
            glide_left = max(0.0, glide_left - 1.0 / fps)
            done = 1.0 if glide_left == 0.0 else 1.0 - glide_left / glide_total
            current = _even(round(glide_from + done * (glide_to - glide_from)))
        path.append(Sample(time, current))

    return path


def frame_size(video: str) -> tuple[int, int, float]:
    """The width, the height and the frame rate of a video file.

    The file is the truth: what a site said a download would be is not
    always what landed, and the crop window has to fit the file.
    """
    import cv2

    capture = cv2.VideoCapture(video)
    try:
        if not capture.isOpened():
            return 0, 0, 0.0
        return (
            int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            capture.get(cv2.CAP_PROP_FPS) or 0.0,
        )
    finally:
        capture.release()


def duration_seconds(video: str) -> float:
    """How long a file runs, in seconds.

    A download gets its length from the site; a file nobody downloaded only
    has the container. The decoder the tracker already opens can say it.
    """
    import cv2

    capture = cv2.VideoCapture(video)
    try:
        if not capture.isOpened():
            return 0.0
        fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        count = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    finally:
        capture.release()
    return count / fps if fps else 0.0


def is_landscape(source_width: int, source_height: int) -> bool:
    """Whether the frame is wide enough that a 9:16 crop adds something."""
    return source_width * 16 > source_height * 9


def proxy_command(
    ffmpeg: str,
    source: str,
    output: str,
    fps: float = PROXY_FPS,
    width: int = PROXY_WIDTH,
) -> list[str]:
    """The copy the detectors read: the same film, small and slow.

    Nothing listens to it, so the audio is dropped. The scale expression keeps
    a file that is already smaller than the proxy the size it is.
    """
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        source,
        "-vf",
        f"fps={fps},scale=w='min({width},iw)':h=-2",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "30",
        "-pix_fmt",
        "yuv420p",
        output,
    ]


def track_centres(
    video: str,
    sample_fps: float = PROXY_FPS,
    detector: SubjectDetector | None = None,
    progress: Callable[[float], None] | None = None,
) -> list[tuple[float, int | None]]:
    """When the subject is in a video and where, as that video is measured."""
    import cv2

    capture = cv2.VideoCapture(video)
    if not capture.isOpened():
        return []
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, round(fps / sample_fps))
        #: The frames still to come, as the file gives them - and nothing when
        #: it will not say, which leaves the bar where it is instead of lying.
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        finder = detector or SubjectDetector()
        centres: list[tuple[float, int | None]] = []
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                found = finder.detect(frame)
                centres.append((index / fps, None if found is None else found[0]))
                if progress is not None and frames:
                    progress(index / frames)
            index += 1
    finally:
        capture.release()

    return centres


def _share(
    progress: Callable[[float], None] | None, index: int, total: int
) -> Callable[[float], None] | None:
    """One of a pass's equal shares of the progress it was told to report."""
    if progress is None:
        return None
    return lambda fraction: progress(min((index + fraction) / total, 1.0))


def analyse(
    video: str,
    ffmpeg: str = "ffmpeg",
    sample_fps: float = PROXY_FPS,
    runner: Callable[[list[str], str], int] | None = None,
    detector: SubjectDetector | None = None,
    duration: float = 0.0,
    progress: Callable[[float], None] | None = None,
) -> tuple[tuple[int, int] | None, list[Sample]]:
    """The picture inside the frame, and the crop path for the window.

    Detection is the expensive half of a reframe: on a 4K download it costs
    twelve seconds of work for every second of film. A copy at PROXY_WIDTH
    and five frames a second costs a fifth of that, which is why the centres
    are read there and scaled back - and why that width is not free to shrink.

    ``progress`` is told the share of this reading that is done: three passes
    over the film - the picture, the copy, the subject - and each one gets a
    third of the bar it is given.
    """
    width, height, fps = frame_size(video)
    length = duration or (duration_seconds(video) if progress else 0.0)
    box = detect_picture(
        video,
        ffmpeg=ffmpeg,
        duration=length,
        progress=_share(progress, 0, ANALYSIS_PASSES),
    )
    _top, picture_height = _picture_rows(width, height, box)
    crop_width, _height = crop_window(width, picture_height)

    run = runner or _ffmpeg_runner(length, _share(progress, 1, ANALYSIS_PASSES))
    proxy_width = 0
    with tempfile.TemporaryDirectory() as work:
        proxy = os.path.join(work, "proxy.mp4")
        if run(proxy_command(ffmpeg, os.path.abspath(video), proxy), work) == 0:
            proxy_width = frame_size(proxy)[0]
        track = _share(progress, 2, ANALYSIS_PASSES)
        if proxy_width:
            ratio = width / proxy_width
            centres = [
                (time, None if x is None else round(x * ratio))
                for time, x in track_centres(
                    proxy, sample_fps=sample_fps, detector=detector, progress=track
                )
            ]
        else:
            # shortcut: a file that gives no proxy is tracked at its own size,
            # which is slow but correct.
            centres = track_centres(
                video, sample_fps=sample_fps, detector=detector, progress=track
            )

    return box, path_from_centres(centres, width, crop_width, fps or 30.0)


def model_path(name: str) -> Path:
    """Where a model file lives - in the frozen bundle or beside this module."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "models" / name
        if bundled.is_file():
            return bundled
    return Path(__file__).resolve().parents[1] / "models" / name


def pick_subject(
    boxes: Sequence[Sequence[float]],
    last: tuple[float, float] | None,
    frame_width: int,
) -> Sequence[float]:
    """The box the camera is shown: the one nearest where the subject was.

    The biggest box in every frame is a different person whenever somebody
    closer to the camera walks in, and the window jumps with it. A box
    nothing like the last subject - after a cut - is the new subject, so the
    biggest box wins there.
    """
    biggest = max(boxes, key=lambda box: box[2] * box[3])
    if last is None:
        return biggest
    limit = STICKY_RATIO * frame_width
    near = [box for box in boxes if math.dist(_centre(box), last) <= limit]
    if not near:
        return biggest
    return min(near, key=lambda box: math.dist(_centre(box), last))


def _centre(box: Sequence[float]) -> tuple[float, float]:
    return float(box[0]) + float(box[2]) / 2, float(box[1]) + float(box[3]) / 2


class SubjectDetector:
    """Finds the subject in a frame: a face if there is one, a body if not.

    The models are loaded once and kept - loading them per frame would cost
    more than the detection itself. ``last`` is where the subject was in the
    frame before, which is how the same person is followed from frame to
    frame instead of the biggest box in each one.
    """

    def __init__(self) -> None:
        import cv2

        self._cv2 = cv2
        self._face = cv2.FaceDetectorYN.create(
            str(model_path(FACE_MODEL)), "", (320, 320), 0.6, 0.3, 5000
        )
        self._body = cv2.dnn.readNet(str(model_path(BODY_MODEL)))
        self.last: tuple[int, int] | None = None

    def detect(self, frame) -> tuple[int, int] | None:
        """The centre of the subject in the frame, or None if there is none."""
        centre = self.face_centre(frame)
        if centre is None:
            centre = self.body_centre(frame)
        if centre is not None:
            self.last = centre
        return centre

    def face_centre(self, frame) -> tuple[int, int] | None:
        height, width = frame.shape[:2]
        self._face.setInputSize((width, height))
        _, faces = self._face.detect(frame)
        if faces is None or len(faces) == 0:
            return None
        x, y, box_width, box_height = (
            float(value) for value in pick_subject(faces, self.last, width)[:4]
        )
        return int(x + box_width / 2), int(y + box_height / 2)

    def body_centre(self, frame) -> tuple[int, int] | None:
        height, width = frame.shape[:2]
        resized = self._cv2.resize(frame, (BODY_SIZE, BODY_SIZE))
        self._body.setInput(self._cv2.dnn.blobFromImage(self._prepare(resized)))
        outputs = self._body.forward(self._body.getUnconnectedOutLayersNames())

        boxes = self._person_boxes(outputs)
        if not boxes:
            return None
        last = (
            None
            if self.last is None
            else (self.last[0] * BODY_SIZE / width, self.last[1] * BODY_SIZE / height)
        )
        x, y, box_width, box_height = pick_subject(boxes, last, BODY_SIZE)
        return (
            int((x + box_width / 2) * width / BODY_SIZE),
            int((y + box_height / 2) * height / BODY_SIZE),
        )

    def _prepare(self, image):
        """The model was trained on RGB with this mean and spread."""
        import numpy as np

        mean = np.array([103.53, 116.28, 123.675], dtype=np.float32)
        spread = np.array([57.375, 57.12, 58.395], dtype=np.float32)
        rgb = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2RGB)
        return (rgb.astype(np.float32) - mean) / spread

    def _person_boxes(self, outputs) -> list[list[float]]:
        """Decode NanoDet's output into the boxes of the people in the frame."""
        import numpy as np

        boxes: list[list[float]] = []
        scores: list[float] = []
        for stride, cls_score, bbox_pred in zip(
            (8, 16, 32), outputs[::2], outputs[1::2]
        ):
            distances = np.exp(bbox_pred[0].reshape(-1, 8))
            distances = distances / distances.sum(axis=1, keepdims=True)
            distances = (distances @ np.arange(8)).reshape(-1, 4) * stride

            grid = BODY_SIZE // stride
            shift_x = np.arange(grid) * stride
            shift_y = np.arange(grid) * stride
            xv, yv = np.meshgrid(shift_x, shift_y)
            anchors = np.column_stack(
                (
                    xv.flatten() + 0.5 * (stride - 1),
                    yv.flatten() + 0.5 * (stride - 1),
                )
            )

            left = anchors[:, 0] - distances[:, 0]
            top = anchors[:, 1] - distances[:, 1]
            right = anchors[:, 0] + distances[:, 2]
            bottom = anchors[:, 1] + distances[:, 3]

            confidence = cls_score[0][:, PERSON_CLASS]
            for index in np.nonzero(confidence >= BODY_SCORE)[0]:
                boxes.append(
                    [
                        float(left[index]),
                        float(top[index]),
                        float(right[index] - left[index]),
                        float(bottom[index] - top[index]),
                    ]
                )
                scores.append(float(confidence[index]))

        if not boxes:
            return []
        kept = self._cv2.dnn.NMSBoxes(boxes, scores, BODY_SCORE, BODY_NMS)
        return [boxes[int(index)] for index in np.array(kept).flatten()]


def _even(value: int) -> int:
    """Round down to the nearest even number - an odd offset shifts the
    chroma by half a pixel."""
    return value - value % 2
