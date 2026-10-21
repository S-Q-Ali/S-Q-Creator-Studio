"""Reusable app-style widgets: flow layout, badges, stats, avatar, helpers."""

from __future__ import annotations

import hashlib
import logging
import os
import queue
import threading

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QLabel, QLayout, QSizePolicy, QWidget

from s_q_ali_media_downloader.niche_research.ui.theme import (
    ACCENT,
    ACCENT_TEXT,
    CARD,
    DANGER,
    PANEL,
    TEAL,
    TEXT,
)

logger = logging.getLogger(__name__)


HARD_STOP_TIMEOUT_MS = 35_000


def stop_worker(worker: QThread | None, timeout_ms: int = 3000) -> None:
    """Stop and join a worker thread.

    The worker is asked to stop and then gets time to finish the item it is
    on. A QThread that is destroyed while it is still running aborts the
    whole process, and ``terminate()`` is a last resort: on Windows it kills
    the thread at an arbitrary instruction, which can corrupt the
    interpreter. Workers poll ``isInterruptionRequested()``, so the grace
    period is normally enough.
    """
    if worker is None:
        return
    if not worker.isRunning():
        return
    worker.requestInterruption()
    if worker.wait(timeout_ms):
        return
    logger.warning("Worker still running after %dms — waiting for it to finish", timeout_ms)
    if worker.wait(HARD_STOP_TIMEOUT_MS):
        return
    logger.error("Worker did not stop — terminating it")
    worker.terminate()
    worker.wait(1000)


# --------------------------------------------------------------------------- #
# Async thumbnail loading (never block the GUI thread)
# --------------------------------------------------------------------------- #
def _url_candidates(url: str) -> list[str]:
    """Progressively lower-quality variants for a video URL."""
    candidates = [url]
    if "maxresdefault" in url:
        candidates.append(url.replace("maxresdefault", "hqdefault"))
        candidates.append(url.replace("maxresdefault", "mqdefault"))
    return candidates


def _fetch_image_bytes(url: str, timeout: float = 8.0) -> bytes | None:
    """Background download with cheap fallback chain. Returns raw bytes or None."""
    import httpx

    for candidate in _url_candidates(url):
        try:
            resp = httpx.get(
                candidate,
                headers={"accept": "image/*"},
                timeout=timeout,
                follow_redirects=True,
            )
        except Exception:
            logger.debug("thumbnail fetch failed for %s", candidate, exc_info=True)
            continue
        if resp.status_code == 200 and resp.content:
            return resp.content
    return None


def _cache_dir() -> str:
    override = os.environ.get("NICHE_DB_PATH")
    if override:
        base = os.path.dirname(os.path.abspath(override))
    else:
        base = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
            "S-Q-Ali Media Downloader",
            "storage",
        )
    directory = os.path.join(base, "thumb_cache")
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        pass
    return directory


def _cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _read_cached_image(url: str) -> bytes | None:
    try:
        with open(os.path.join(_cache_dir(), _cache_key(url) + ".img"), "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _write_cached_image(url: str, data: bytes) -> None:
    try:
        with open(os.path.join(_cache_dir(), _cache_key(url) + ".img"), "wb") as fh:
            fh.write(data)
    except OSError:
        pass


class ThumbLoader(QObject):
    """Fetches thumbnail bytes off the GUI thread and delivers them on it.

    A single daemon thread consumes a small request queue and drops results into
    a results queue; a QTimer on the GUI thread drains that queue and emits
    ``finished`` — every Qt object is only ever touched on the GUI thread, so the
    loader is safe to abandon at interpreter shutdown (no cross-thread signals,
    no owned QThreads).
    """

    finished = Signal(str, object)  # url -> bytes | None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._requests: queue.Queue = queue.Queue()
        self._results: queue.Queue = queue.Queue()
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._drain)
        self._timer.start()
        worker = threading.Thread(target=self._run, daemon=True)
        worker.start()

    def start(self, url: str) -> None:
        if url:
            self._requests.put(url)

    def _run(self) -> None:
        while True:
            url = self._requests.get()
            data = _fetch_image_bytes(url)
            self._results.put((url, data))

    def _drain(self) -> None:
        while not self._results.empty():
            url, data = self._results.get_nowait()
            self.finished.emit(url, data)


_loader_singleton: ThumbLoader | None = None


def thumb_loader() -> ThumbLoader:
    global _loader_singleton
    if _loader_singleton is None:
        _loader_singleton = ThumbLoader()
    return _loader_singleton


# --------------------------------------------------------------------------- #
# Number / tier formatting helpers (ported from TrendingChannelCard.tsx)
# --------------------------------------------------------------------------- #
def format_number(num: float) -> str:
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(int(num))


def format_earnings(rpm: dict, views: float) -> str:
    per1k = views / 1000
    min_earn = round(per1k * rpm["min"])
    max_earn = round(per1k * rpm["max"])
    fmt = lambda n: f"${n / 1000:.1f}K" if n >= 1000 else f"${n}"
    return f"{fmt(min_earn)}-{fmt(max_earn)}"


def get_viral_score_color(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Mid"
    return "Low"


def get_viral_score_label(score: float) -> str:
    if score >= 70:
        return "S-Tier"
    if score >= 50:
        return "A-Tier"
    if score >= 30:
        return "B-Tier"
    return "C-Tier"


def get_initials(name: str) -> str:
    return "".join(word[0] for word in name.split()[:2]).upper() if name else "?"


def time_ago(timestamp: float) -> str:
    diff_ms = timestamp * 1000 if timestamp < 10_000_000_000 else timestamp
    try:
        from time import time

        diff = time() * 1000 - diff_ms
    except (TypeError, ValueError):
        return "recently"
    hours = int(diff / 3_600_000)
    if hours < 1:
        return "just now"
    if hours == 1:
        return "1 hour ago"
    if hours < 24:
        return f"{hours} hours ago"
    days = hours // 24
    return f"{days} day ago" if days == 1 else f"{days} days ago"


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #
class FlowLayout(QLayout):
    """Left-aligned grid that wraps (used for the trending card grid)."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 12):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: list[tuple[QLayout, QRect]] = []

    def addItem(self, item) -> None:
        self._items.append((item, QRect()))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index][0] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            item = self._items.pop(index)[0]
            return item
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item, _rect in self._items:
            size = size.expandedTo(item.minimumSize())
        size += QSize(self.contentsMargins().left() * 2, self.contentsMargins().top() * 2)
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        margins = self.contentsMargins()
        available = rect.width() - margins.left() - margins.right()
        for item, stored in self._items:
            widget = item.widget()
            space_x = self.spacing()
            space_y = self.spacing()
            item_size = item.sizeHint() if widget is None else widget.sizeHint()
            if x + item_size.width() > rect.x() + available and line_height > 0:
                x = rect.x()
                y += line_height + space_y
                line_height = 0
            item.setGeometry(QRect(QPoint(x, y), item_size))
            x += item_size.width() + space_x
            line_height = max(line_height, item_size.height())
        return y + line_height - rect.y()


def make_badge(text: str, object_name: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(object_name)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def score_color(score: float) -> str:
    if score >= 80:
        return "green"
    if score >= 60:
        return "lime"
    if score >= 40:
        return "yellow"
    if score >= 20:
        return "orange"
    return "red"


def score_label(score: float) -> str:
    if score >= 80:
        return "Very High"
    if score >= 60:
        return "High"
    if score >= 40:
        return "Medium"
    if score >= 20:
        return "Low"
    return "Very Low"


def competition_color(label: str) -> str:
    if label == "High":
        return "#dc2626"
    if label == "Medium":
        return "#eab308"
    return "#16a34a"


class ScoreBadge(QLabel):
    """Colored score pill with a leading dot (ported from ScoreBadge.tsx)."""

    def __init__(self, score: float, size: str = "md", parent: QWidget | None = None):
        super().__init__(parent)
        self._score = score
        self._size = size
        self.setToolTip(score_label(score))
        self._refresh()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_score(self, score: float) -> None:
        self._score = score
        self.setToolTip(score_label(score))
        self._refresh()

    def _refresh(self) -> None:
        color = score_color(self._score)
        self.setText(f"● {int(self._score)}")
        if self._size == "sm":
            self.setObjectName(f"scoreBadgeSm{color.capitalize()}")
        elif self._size == "lg":
            self.setObjectName(f"scoreBadgeLg{color.capitalize()}")
        else:
            self.setObjectName(f"scoreBadge{color.capitalize()}")
        if self.style():
            self.style().unpolish(self)
            self.style().polish(self)


class CompetitionBadge(QLabel):
    """Solid competition label pill (ported from ScoreBadge.tsx)."""

    def __init__(self, label: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.set_label(label)

    def set_label(self, label: str) -> None:
        self.setText(label)
        self.setObjectName("competitionBadge" + competition_color(label).lstrip("#").capitalize())
        if self.style():
            self.style().unpolish(self)
            self.style().polish(self)


class Sparkline(QWidget):
    """Small line chart for demand/competition history (ported from Sparkline.tsx).

    The trailing (last) point is emphasised and colored by its value.
    """

    def __init__(
        self,
        points: list[float],
        *,
        width: int = 140,
        height: int = 36,
        stroke: str = DANGER,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._points = points
        self._stroke = QColor(stroke)
        self._w = width
        self._h = height
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(self._w, self._h)

    def set_points(self, points: list[float]) -> None:
        self._points = points
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.PenStyle.NoPen)

        width = self.width()
        height = self.height()
        points = [p for p in self._points if p is not None]
        if len(points) < 2:
            return

        pts = []
        # 0-100 series keep the fixed scale; bigger series (view counts,
        # subscriber counts) are scaled to their own maximum, otherwise every
        # point would clamp to the top and the chart would be a flat line.
        top = max(float(p) for p in points)
        scale = max(100.0, top)
        for i, value in enumerate(points):
            x = i * (width - 4) / (len(points) - 1) + 2
            norm = max(0.0, min(1.0, float(value) / scale))
            y = height - 4 - norm * (height - 10)
            pts.append((x, y))

        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)

        # subtle area fill under the line
        from PySide6.QtGui import QLinearGradient

        grad = QLinearGradient(0, 0, 0, height)
        fill = QColor(self._stroke)
        fill.setAlpha(28)
        grad.setColorAt(0, fill)
        base = QColor(self._stroke)
        base.setAlpha(0)
        grad.setColorAt(1, base)
        area = QPainterPath(path)
        area.lineTo(pts[-1][0], height - 4)
        area.lineTo(pts[0][0], height - 4)
        area.closeSubpath()
        painter.setBrush(grad)
        painter.drawPath(area)

        pen = painter.pen()
        pen.setColor(self._stroke)
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.drawPath(path)

        last_x, last_y = pts[-1]
        dot_color = QColor(TEAL)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(QPointF(last_x, last_y), 2.5, 2.5)


class AvatarInitials(QWidget):
    """Round gradient avatar with channel initials (cyan→teal gradient)."""

    def __init__(self, text: str, size: int = 48, parent: QWidget | None = None):
        super().__init__(parent)
        self._text = get_initials(text)
        self._size = size
        self.setFixedSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QBrush, QLinearGradient

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, self._size, self._size)
        grad.setColorAt(0, QColor(ACCENT))
        grad.setColorAt(1, QColor(TEAL))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self._size, self._size)
        painter.setPen(QColor(ACCENT_TEXT))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(int(self._size * 0.34))
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self._size, self._size), Qt.AlignmentFlag.AlignCenter, self._text
        )


class AvatarThumbnail(QWidget):
    """Round channel avatar with a fetched image, falling back to initials.

    The image loads asynchronously off the GUI thread; on failure (or an
    empty/blocked DP url) the initials avatar renders instead.
    """

    def __init__(self, url: str, text: str, size: int = 48, parent: QWidget | None = None):
        super().__init__(parent)
        self._url = url
        self._pixmap: QPixmap | None = None
        self._initials = get_initials(text)
        self._size = size
        self.setFixedSize(size, size)
        thumb_loader().finished.connect(self._on_image)
        if url:
            self._start(url)

    def _start(self, url: str) -> None:
        cached = _read_cached_image(url)
        if cached is not None:
            self._apply_bytes(cached)
            return
        thumb_loader().start(url)

    def _apply_bytes(self, data: bytes) -> None:
        pixmap = QPixmap()
        if data and pixmap.loadFromData(data):
            self._pixmap = pixmap.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.update()

    def _on_image(self, url: str, data: object) -> None:
        if data and url == self._url:
            _write_cached_image(url, data)
            self._apply_bytes(data)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._pixmap:
            from PySide6.QtGui import QBrush

            brush = QBrush(self._pixmap)
            painter.setBrush(brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, self._size, self._size)
            return

        from PySide6.QtGui import QBrush, QLinearGradient

        grad = QLinearGradient(0, 0, self._size, self._size)
        grad.setColorAt(0, QColor(ACCENT))
        grad.setColorAt(1, QColor(TEAL))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self._size, self._size)
        painter.setPen(QColor(ACCENT_TEXT))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(int(self._size * 0.34))
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self._size, self._size), Qt.AlignmentFlag.AlignCenter, self._initials
        )


class VideoThumb(QWidget):
    """Rounded 16:9 video thumbnail with a fallback play glyph.

    Loads asynchronously with a maxres→hq→mq fallback chain and a disk cache.
    """

    def __init__(self, url: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._url = url
        self._text = text
        self._pixmap: QPixmap | None = None
        self.setFixedSize(120, 68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        thumb_loader().finished.connect(self._on_image)
        if url:
            cached = _read_cached_image(url)
            if cached is not None:
                self._apply_bytes(cached)
            else:
                thumb_loader().start(url)

    def _apply_bytes(self, data: bytes) -> None:
        pixmap = QPixmap()
        if data and pixmap.loadFromData(data):
            self._pixmap = pixmap
        self.update()

    def _on_image(self, url: str, data: object) -> None:
        if data and url == self._url:
            _write_cached_image(url, data)
            self._apply_bytes(data)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(CARD))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 6, 6)
        if self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.width(),
                self.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(
                self.rect(), scaled, QRect(x, y, self.width(), self.height())
            )
        painter.setBrush(QColor(0, 0, 0, 110))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 6, 6)
        color = QColor(TEXT)
        painter.setBrush(color)
        painter.drawEllipse(self.width() - 22, int((self.height() - 16) / 2) + 8, 16, 16)
        painter.setPen(QColor(PANEL))
        painter.drawPolygon(
            [
                QPoint(self.width() - 18, int((self.height() - 10) / 2) + 4),
                QPoint(self.width() - 18, int((self.height() - 10) / 2) + 14),
                QPoint(self.width() - 10, int((self.height() - 10) / 2) + 9),
            ]
        )
