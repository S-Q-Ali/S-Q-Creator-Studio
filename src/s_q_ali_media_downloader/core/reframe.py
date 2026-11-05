"""The maths of the 9:16 reframe - where the crop window sits over time.

Nothing here touches a video. The window is cut, the path is smoothed, and
the path is written out as the command file that ffmpeg's ``sendcmd`` reads.
"""

from __future__ import annotations

import logging
import os
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
