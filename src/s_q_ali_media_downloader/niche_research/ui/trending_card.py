"""Trending channel card in the app's visual style (ported from TrendingChannelCard.tsx)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.niche_research.ui import widgets as w


@dataclass
class TrendingCardData:
    channel_id: str = ""
    title: str = ""
    thumbnail_url: str = ""
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0
    viral_score: float = 0
    growth_rate: float = 0
    is_newly_created: bool = False
    is_rapidly_growing: bool = False
    ai_score: int | None = None
    category_name: str = ""
    view_sub_ratio: float = 0
    video_format: str = "longform"
    niche: str = ""
    rpm: dict | None = None  # {"min":..,"max":..,"avg":..}


def _stat_block(value_text: str, key_text: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    value = QLabel(value_text)
    value.setObjectName("statValue")
    value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    key = QLabel(key_text)
    key.setObjectName("statKey")
    key.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(value)
    layout.addWidget(key)
    return widget


class TrendingChannelCard(QFrame):
    analyze_requested = Signal(str)

    def __init__(self, data: TrendingCardData, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setProperty("hoverable", True)
        self._data = data

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        # Avatar + title row
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(
            w.AvatarThumbnail(data.thumbnail_url, data.title, size=48)
            if data.thumbnail_url
            else w.AvatarInitials(data.title, size=48)
        )
        title_box = QVBoxLayout()
        title = QLabel(data.title or "Untitled Channel")
        title.setWordWrap(False)
        title.setToolTip(data.title)
        title.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: palette(text); "
            "background: transparent; border: none;"
        )
        category = QLabel(data.category_name or "")
        category.setStyleSheet(
            "font-size: 12px; color: palette(mid); background: transparent; border: none;"
        )
        title_box.addWidget(title)
        title_box.addWidget(category)
        title_box.addStretch(1)
        header.addLayout(title_box, 1)
        outer.addLayout(header)

        # Stats row: Subs / Views / Videos
        stats = QHBoxLayout()
        stats.setSpacing(8)
        stats.addWidget(_stat_block(w.format_number(data.subscriber_count), "Subs"), 1)
        stats.addWidget(_stat_block(w.format_number(data.view_count), "Views"), 1)
        stats.addWidget(_stat_block(str(data.video_count), "Videos"), 1)
        outer.addLayout(stats)

        # Badges row
        badges = QHBoxLayout()
        badges.setSpacing(6)
        score_color = w.get_viral_score_color(data.viral_score)
        score_badge = w.make_badge(
            f"{w.get_viral_score_label(data.viral_score)} {int(data.viral_score)}",
            f"badgeScore{score_color}",
        )
        badges.addWidget(score_badge)
        if data.is_newly_created:
            badges.addWidget(w.make_badge("New", "badgeNew"))
        if data.is_rapidly_growing:
            badges.addWidget(w.make_badge("Rapid", "badgeRapid"))
        if data.ai_score is not None and data.ai_score >= 70:
            badges.addWidget(w.make_badge("AI", "badgeAi"))
        badges.addStretch(1)
        outer.addLayout(badges)

        # Growth + V/S row
        meta = QHBoxLayout()
        positive = data.growth_rate >= 0
        growth = QLabel(f"{'+' if positive else ''}{data.growth_rate:.1f}% growth")
        growth.setObjectName("growthPositive" if positive else "growthNegative")
        vs = QLabel(f"{data.view_sub_ratio:.1f}x V/S")
        vs.setStyleSheet("font-size: 12px; color: palette(mid);")
        meta.addWidget(growth)
        meta.addStretch(1)
        meta.addWidget(vs)
        outer.addLayout(meta)

        # RPM earnings bar
        if data.rpm:
            rpm_bar = QFrame()
            rpm_bar.setObjectName("rpmBar")
            rpm_layout = QHBoxLayout(rpm_bar)
            rpm_layout.setContentsMargins(10, 6, 10, 6)
            rpm_layout.setSpacing(4)
            earn = QLabel(f"Est. {w.format_earnings(data.rpm, data.view_count)}/total")
            earn.setObjectName("rpmLabel")
            rpm_avg = QLabel(f"(RPM ${data.rpm['avg']})")
            rpm_avg.setObjectName("rpmSubLabel")
            rpm_layout.addWidget(QLabel("\U0001f4b0"))
            rpm_layout.addWidget(earn)
            rpm_layout.addWidget(rpm_avg)
            rpm_layout.addStretch(1)
            outer.addWidget(rpm_bar)

        # Analyze button
        analyze_btn = QPushButton("Create Similar Channel")
        analyze_btn.clicked.connect(lambda: self.analyze_requested.emit(data.channel_id))
        outer.addWidget(analyze_btn)

    def data(self) -> TrendingCardData:
        return self._data
