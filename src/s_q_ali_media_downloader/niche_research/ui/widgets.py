"""Reusable Niche-Scope style widgets: flow layout, badges, stats, avatar, helpers."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QLabel, QLayout, QSizePolicy, QWidget


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
        stroke: str = "#dc2626",
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
        for i, value in enumerate(points):
            x = i * (width - 4) / (len(points) - 1) + 2
            norm = max(0.0, min(1.0, value / 100.0))
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
        dot_color = QColor("#22c55e")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(QPointF(last_x, last_y), 2.5, 2.5)


class AvatarInitials(QWidget):
    """Round gradient avatar with channel initials (red→rose gradient like Niche-Scope)."""

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
        grad.setColorAt(0, QColor("#ef4444"))
        grad.setColorAt(1, QColor("#be123c"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(0, 0, self._size, self._size)
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(int(self._size * 0.34))
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self._size, self._size), Qt.AlignmentFlag.AlignCenter, self._text
        )


class AvatarThumbnail(QWidget):
    """Round channel avatar with a fetched image, falling back to initials."""

    def __init__(self, url: str, text: str, size: int = 48, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._initials = get_initials(text)
        self._size = size
        self.setFixedSize(size, size)
        self._load(url)

    def _load(self, url: str) -> None:
        if not url:
            return
        try:
            import httpx

            resp = httpx.get(url, timeout=8, follow_redirects=True)
            if resp.status_code == 200 and resp.content:
                pixmap = QPixmap()
                if pixmap.loadFromData(resp.content):
                    self._pixmap = pixmap.scaled(
                        self._size,
                        self._size,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
        except Exception:
            self._pixmap = None
        self.update()

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
        grad.setColorAt(0, QColor("#ef4444"))
        grad.setColorAt(1, QColor("#be123c"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self._size, self._size)
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(int(self._size * 0.34))
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self._size, self._size), Qt.AlignmentFlag.AlignCenter, self._initials
        )


class VideoThumb(QWidget):
    """Rounded 16:9 video thumbnail with a fallback play glyph."""

    def __init__(self, url: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._url = url
        self._text = text
        self._pixmap: QPixmap | None = None
        self.setFixedSize(120, 68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if url:
            self._load()

    def _load(self) -> None:
        try:
            import httpx

            headers = {"accept": "image/*"}
            resp = httpx.get(self._url, headers=headers, timeout=8)
            self._pixmap = QPixmap()
            self._pixmap.loadFromData(resp.content)
        except Exception:
            self._pixmap = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#27272a"))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 6, 6)
        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(self.rect(), self._pixmap)
        painter.setBrush(QColor(0, 0, 0, 110))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 6, 6)
        color = QColor("#ffffff")
        painter.setBrush(color)
        painter.drawEllipse(self.width() - 22, int((self.height() - 16) / 2) + 8, 16, 16)
        painter.setPen(QColor("#18181b"))
        painter.drawPolygon(
            [
                QPoint(self.width() - 18, int((self.height() - 10) / 2) + 4),
                QPoint(self.width() - 18, int((self.height() - 10) / 2) + 14),
                QPoint(self.width() - 10, int((self.height() - 10) / 2) + 9),
            ]
        )
