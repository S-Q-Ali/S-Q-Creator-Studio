"""Reusable widgets: queue cards, chips and small drawing helpers."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
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
from s_q_ali_media_downloader.theme import STATUS_COLORS, C


def shorten(text, limit=95):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def shield_pixmap(size=15, colour="#FFB020"):
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
        self.status.setStyleSheet(f"color: {colour};")

        self.title.setText(shorten(j.title) if j.title else "Waiting for details")
        self.title.setStyleSheet("" if j.title else f"color: {C['faint']}; font-weight: 500;")

        self.url.setText(shorten(j.url, 110))

        self.bar.setValue(int(j.percent))

        bits = [f"{int(j.percent)}%", j.size]
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
