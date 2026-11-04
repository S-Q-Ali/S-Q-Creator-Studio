"""Reusable widgets: the painted backdrop, queue cards, chips and helpers."""

from math import ceil

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.engine import is_youtube_url
from s_q_ali_media_downloader.theme import (
    BACKDROP,
    STATUS_COLORS,
    STATUS_WEIGHTS,
    UI_FAMILIES,
    C,
)


def shorten(text, limit=95):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def shield_pixmap(size=15, colour=C["amber"]):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(colour))
    path = QPainterPath()
    path.moveTo(size * 0.5, size * 0.06)
    path.lineTo(size * 0.9, size * 0.22)
    path.lineTo(size * 0.9, size * 0.52)
    path.lineTo(size * 0.5, size * 0.94)
    path.lineTo(size * 0.1, size * 0.52)
    path.lineTo(size * 0.1, size * 0.22)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return pm


WORDMARK_TEXT = "S-Q-Ali"
_wordmarks: dict[tuple[int, str, float], QPixmap] = {}


def wordmark_pixmap(height: int, colour: str = C["text"]) -> QPixmap:
    """The rail's logotype, painted once at ``height`` and reused.

    A QLabel typesets the name in whatever font the machine has and clips it
    to whatever the layout hands over. Drawing it measures the name first,
    and buys the letter-spacing QSS has no property for. Cached by size, so a
    resize or a density change never repaints it per frame.
    """
    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if app is not None else 1.0
    key = (height, colour, ratio)
    if key not in _wordmarks:
        _wordmarks[key] = _paint_wordmark(height, colour, ratio)
    return _wordmarks[key]


def _paint_wordmark(height: int, colour: str, ratio: float) -> QPixmap:
    font = QFont()
    font.setFamilies(list(UI_FAMILIES))
    font.setPixelSize(height)
    font.setWeight(QFont.Weight.Bold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(0.5, height * 0.05))
    metrics = QFontMetrics(font)
    box = metrics.boundingRect(WORDMARK_TEXT)
    pm = QPixmap(
        max(1, ceil((box.width() + 2) * ratio)),
        max(1, ceil((box.height() + 2) * ratio)),
    )
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    painter.setFont(font)
    painter.setPen(QColor(colour))
    painter.drawText(1, 1 + metrics.ascent(), WORDMARK_TEXT)
    painter.end()
    return pm


class Backdrop(QWidget):
    """The app's one paintEvent: the depth every panel sits on.

    Qt has no blur-behind, so the glass is composited against a backdrop the
    app owns - void at the top, graphite at the bottom, and two pools where
    that range reaches its ceiling early. Panels are opaque, so this shows
    through only where a container is transparent, and the ceiling is the
    panel token, so no text is ever read against a surface the sheet has not
    measured. One gradient per paint, no timer, no effect on a container.
    """

    def paintEvent(self, event):
        rect = self.rect()
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)

        base = QLinearGradient(0, rect.top(), 0, rect.bottom())
        base.setColorAt(0.0, QColor(BACKDROP["top"]))
        base.setColorAt(1.0, QColor(BACKDROP["bottom"]))
        painter.fillRect(rect, base)

        height = max(rect.height(), 1)
        for spec in BACKDROP["pools"].values():
            centre = QPointF(
                rect.left() + spec["at"][0] * rect.width(),
                rect.top() + spec["at"][1] * height,
            )
            radius = spec["radius"] * height
            peak = QColor(BACKDROP[spec["colour"]])
            fade = QColor(peak)
            fade.setAlpha(0)
            pool = QRadialGradient(centre, radius)
            pool.setColorAt(0.0, peak)
            pool.setColorAt(1.0, fade)
            painter.setBrush(pool)
            painter.drawEllipse(centre, radius, radius)
        painter.end()


class Job:
    _next_uid = 1

    def __init__(self, url):
        self.uid = Job._next_uid
        Job._next_uid += 1
        self.url = url
        self.title = ""
        self.status = "Queued"
        self.percent = 0.0
        self.size = "—"
        self.speed = ""
        self.quality = ""
        self.error = ""
        self.note = ""


class JobCard(QFrame):
    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.setObjectName("Card")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 14, 0)
        outer.setSpacing(0)

        self.spine = QFrame()
        self.spine.setObjectName("Spine")
        self.spine.setFixedWidth(3)
        self.spine.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        outer.addWidget(self.spine)

        pick = QWidget()
        pick_lay = QHBoxLayout(pick)
        pick_lay.setContentsMargins(12, 0, 6, 0)
        self.check = QCheckBox()
        pick_lay.addWidget(self.check, 0, Qt.AlignVCenter)
        outer.addWidget(pick)

        body = QVBoxLayout()
        body.setContentsMargins(0, 11, 0, 11)
        body.setSpacing(6)
        outer.addLayout(body, 1)

        top = QHBoxLayout()
        top.setSpacing(9)

        self.badge = QLabel("YOUTUBE" if is_youtube_url(job.url) else "TIKTOK")
        self.badge.setProperty("role", "badge")
        top.addWidget(self.badge, 0, Qt.AlignVCenter)

        self.title = QLabel()
        self.title.setProperty("role", "cardTitle")
        top.addWidget(self.title, 1)

        self.status = QLabel()
        self.status.setProperty("role", "status")
        top.addWidget(self.status, 0, Qt.AlignVCenter)
        body.addLayout(top)

        self.url = QLabel()
        self.url.setProperty("role", "cardUrl")
        body.addWidget(self.url)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        bottom.addWidget(self.bar, 1)

        self.meta = QLabel()
        self.meta.setProperty("role", "meta")
        self.meta.setMinimumWidth(190)
        self.meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom.addWidget(self.meta, 0)
        body.addLayout(bottom)

        self.error = QLabel()
        self.error.setProperty("role", "error")
        self.error.setWordWrap(True)
        self.error.hide()
        body.addWidget(self.error)

        self.refresh()

    def refresh(self):
        j = self.job
        colour = STATUS_COLORS.get(j.status, C["queued"])

        self.spine.setStyleSheet(f"#Spine {{ background: {colour}; }}")

        self.status.setText(j.status.upper())
        weight = STATUS_WEIGHTS.get(j.status, 600)
        if j.status == "Failed":
            # The one inverted chip: with no red left in the palette, a failure
            # has to be the brightest thing in the list rather than the warmest.
            self.status.setStyleSheet(
                f"color: {C['bg']}; background: {colour}; font-weight: {weight};"
                " padding: 1px 6px; border-radius: 4px;"
            )
        else:
            self.status.setStyleSheet(f"color: {colour}; font-weight: {weight};")

        self.title.setText(shorten(j.title) if j.title else "Waiting for details")
        self.title.setStyleSheet("" if j.title else f"color: {C['faint']}; font-weight: 500;")

        self.url.setText(shorten(j.url, 110))

        self.bar.setValue(int(j.percent))
        # Blue means moving, chalk means finished, and the bar is the widest
        # thing in the row - a full blue one under COMPLETED read as a
        # download still running.
        self.bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: {C['done']}; }}"
            if j.status == "Completed"
            else ""
        )

        bits = [f"{int(j.percent)}%", j.quality, j.size]
        if j.speed:
            bits.append(j.speed)
        self.meta.setText("   ".join(b for b in bits if b))

        message = " · ".join(p for p in (j.error, j.note) if p)
        if message:
            self.error.setText(message)
            self.error.setStyleSheet(
                f"color: {C['waiting'] if j.status in ('Waiting', 'Retrying') else C['failed']};"
            )
            self.error.show()
        else:
            self.error.hide()


class Chip(QFrame):
    def __init__(self, label, colour, parent=None):
        super().__init__(parent)
        self.setObjectName("Chip")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(1)

        self.value = QLabel("0")
        self.value.setProperty("role", "chipValue")
        self.value.setStyleSheet(f"color: {colour};")
        self.caption = QLabel(label.upper())
        self.caption.setProperty("role", "chipLabel")
        lay.addWidget(self.value)
        lay.addWidget(self.caption)

    def set(self, n):
        self.value.setText(str(n))
