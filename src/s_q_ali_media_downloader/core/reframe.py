"""The maths of the 9:16 reframe - where the crop window sits over time.

The window is cut, the path is smoothed, and the path is written out as the
command file that ffmpeg's ``sendcmd`` reads. ``analyse`` finds the picture
and the path in a real file; ``render_vertical`` writes the vertical version.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

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

#: The window is cut in whole 16-row bands, so the 9:16 comes out exact and
#: the scale to the output size does not stretch the picture.
CROP_HEIGHT_STEP = 32

#: The window may travel at most this much of its own width between two
#: samples, so a detection that jumps does not snap the camera.
MAX_STEP_RATIO = 0.25

#: The detectors do not need the file at its own size. This is the copy they
#: read, and it cannot be much smaller: at 1280 the subject of a 4K film is a
#: few pixels and the path misses the one read at full size by over half a
#: window on 49 samples in 100; at 1920 it misses on 9, for a fifth of the
#: work.
PROXY_WIDTH = 1920
PROXY_FPS = 5.0


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
    start: int = 0,
) -> list[int]:
    """The legal path of the crop window.

    The wanted positions are clamped into the frame and then moved towards at
    most ``max_step`` per sample. A sample with no detection keeps the
    position it had; ``start`` is where the window sits until the first
    detection.
    """
    step = max_step_for(crop_width) if max_step is None else max_step
    path: list[int] = []
    current: int | None = None

    for wanted in positions:
        if wanted is None:
            path.append(current if current is not None else start)
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
    """The vertical size: as near the source height as a 9:16 frame can be.

    The size is cut from the same 18x32 grid as the crop window, so the
    scale from the window to the output is the same in both directions and
    the picture is not stretched.
    """
    units = max(1, round(source_height / 18))
    return 18 * units, 32 * units


def vertical_output_path(source: str) -> str:
    """Where the vertical version of a download goes."""
    return f"{os.path.splitext(source)[0]}_9x16.mp4"


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


def detect_picture(video: str, ffmpeg: str = "ffmpeg") -> tuple[int, int] | None:
    """Where the picture is inside the frame, as ffmpeg's cropdetect sees it."""
    result = subprocess.run(
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
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    return detect_picture_text(result.stderr or "")


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
) -> RenderResult:
    """Render the vertical version of a download beside it.

    A download that is already vertical, or that has no video at all, is left
    alone and says why.
    """
    if not source_width or not source_height:
        return RenderResult(None, "The download has no video, only audio.")
    if not is_landscape(source_width, source_height):
        return RenderResult(None, "The download is already vertical.")

    try:
        chain = filter_chain("crop.cmd", source_width, source_height, box)
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


def path_from_centres(
    centres: Sequence[tuple[float, int | None]],
    source_width: int,
    crop_width: int,
) -> list[Sample]:
    """The crop path from the sampled subject centres.

    A centre of None means nothing was found in that frame; the window keeps
    the position it had. With no detection at all the window stays centred.
    """
    times = [time for time, _ in centres]
    wanted = [
        None if centre is None else centre - crop_width // 2
        for _, centre in centres
    ]
    start = _even((source_width - crop_width) // 2)
    path = crop_path(wanted, source_width, crop_width, start=start)
    return [Sample(time, x) for time, x in zip(times, path)]


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
) -> list[tuple[float, int | None]]:
    """When the subject is in a video and where, as that video is measured."""
    import cv2

    capture = cv2.VideoCapture(video)
    if not capture.isOpened():
        return []
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, round(fps / sample_fps))

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
            index += 1
    finally:
        capture.release()

    return centres


def analyse(
    video: str,
    ffmpeg: str = "ffmpeg",
    sample_fps: float = PROXY_FPS,
    runner: Callable[[list[str], str], int] | None = None,
    detector: SubjectDetector | None = None,
) -> tuple[tuple[int, int] | None, list[Sample]]:
    """The picture inside the frame, and the crop path for the window.

    Detection is the expensive half of a reframe: on a 4K download it costs
    twelve seconds of work for every second of film. A copy at PROXY_WIDTH
    and five frames a second costs a fifth of that, which is why the centres
    are read there and scaled back - and why that width is not free to shrink.
    """
    width, height, _fps = frame_size(video)
    box = detect_picture(video, ffmpeg=ffmpeg)
    _top, picture_height = _picture_rows(width, height, box)
    crop_width, _height = crop_window(width, picture_height)

    run = runner or _run_ffmpeg
    proxy_width = 0
    with tempfile.TemporaryDirectory() as work:
        proxy = os.path.join(work, "proxy.mp4")
        if run(proxy_command(ffmpeg, os.path.abspath(video), proxy), work) == 0:
            proxy_width = frame_size(proxy)[0]
        if proxy_width:
            ratio = width / proxy_width
            centres = [
                (time, None if x is None else round(x * ratio))
                for time, x in track_centres(
                    proxy, sample_fps=sample_fps, detector=detector
                )
            ]
        else:
            # shortcut: a file that gives no proxy is tracked at its own size,
            # which is slow but correct.
            centres = track_centres(video, sample_fps=sample_fps, detector=detector)

    return box, path_from_centres(centres, width, crop_width)


def model_path(name: str) -> Path:
    """Where a model file lives - in the frozen bundle or beside this module."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "models" / name
        if bundled.is_file():
            return bundled
    return Path(__file__).resolve().parents[1] / "models" / name


class SubjectDetector:
    """Finds the subject in a frame: a face if there is one, a body if not.

    The models are loaded once and kept - loading them per frame would cost
    more than the detection itself.
    """

    def __init__(self) -> None:
        import cv2

        self._cv2 = cv2
        self._face = cv2.FaceDetectorYN.create(
            str(model_path(FACE_MODEL)), "", (320, 320), 0.6, 0.3, 5000
        )
        self._body = cv2.dnn.readNet(str(model_path(BODY_MODEL)))

    def detect(self, frame) -> tuple[int, int] | None:
        """The centre of the subject in the frame, or None if there is none."""
        centre = self.face_centre(frame)
        if centre is not None:
            return centre
        return self.body_centre(frame)

    def face_centre(self, frame) -> tuple[int, int] | None:
        height, width = frame.shape[:2]
        self._face.setInputSize((width, height))
        _, faces = self._face.detect(frame)
        if faces is None or len(faces) == 0:
            return None
        biggest = max(faces, key=lambda face: float(face[2]) * float(face[3]))
        x, y, box_width, box_height = (float(value) for value in biggest[:4])
        return int(x + box_width / 2), int(y + box_height / 2)

    def body_centre(self, frame) -> tuple[int, int] | None:
        height, width = frame.shape[:2]
        resized = self._cv2.resize(frame, (BODY_SIZE, BODY_SIZE))
        self._body.setInput(self._cv2.dnn.blobFromImage(self._prepare(resized)))
        outputs = self._body.forward(self._body.getUnconnectedOutLayersNames())

        boxes = self._person_boxes(outputs)
        if not boxes:
            return None
        x, y, box_width, box_height = max(
            boxes, key=lambda box: box[2] * box[3]
        )
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


def _towards(current: int, target: int, step: int) -> int:
    if abs(target - current) <= step:
        return target
    return _even(current + step if target > current else current - step)
