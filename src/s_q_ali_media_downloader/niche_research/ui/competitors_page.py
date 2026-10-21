"""Competitors page — dashboard of tracked videos / channels / keywords.

Ported from the companion research web tool's CompetitorsView.tsx. Shows VPH live chips, subscriber
growth, and score sparklines, plus a "Refresh now" button (and a 1h poller) that
records fresh snapshots via competitor_engine.refresh_snapshots.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.niche_research.research import competitor_engine as ce
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui import widgets as w
from s_q_ali_media_downloader.niche_research.ui.export_button import ExportButton
from s_q_ali_media_downloader.niche_research.ui.theme import research_style

_VideoThumb = w.VideoThumb

logger = logging.getLogger(__name__)


def _fmt(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        k = n / 1_000
        return f"{int(k)}K" if k == int(k) else f"{k:.1f}K"
    return str(int(n))


class RefreshWorker(QThread):
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, *, parent: QWidget | None = None):
        super().__init__(parent)

    def run(self) -> None:
        try:
            counts = ce.refresh_snapshots(
                progress=self.progress.emit, cancel=self.isInterruptionRequested
            )
            self.done.emit(counts)
        except Exception as exc:
            logger.warning("Competitor refresh failed", exc_info=True)
            self.failed.emit(str(exc))


class NichePoller(QObject):
    """Hourly background snapshot poller (VPH + growth history)."""

    snapshot_requested = Signal()

    def __init__(self, parent: QObject | None = None, interval_ms: int = 3_600_000):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.snapshot_requested)
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()


def _section_heading(title: str, hint: str) -> QWidget:
    box = QVBoxLayout()
    box.setSpacing(2)
    cap = QLabel(title)
    cap.setObjectName("sectionLabel")
    box.addWidget(cap)
    sub = QLabel(hint)
    sub.setObjectName("smallLabel")
    box.addWidget(sub)
    widget = QWidget()
    widget.setLayout(box)
    return widget


class CompetitorsPage(QWidget):
    scorecard_requested = Signal(str)
    analyze_requested = Signal(str)
    keyword_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("researchPage")
        self.setStyleSheet(research_style())
        self._worker: RefreshWorker | None = None
        self._build()
        self.refresh_dashboard()

    # ------------------------------------------------------------------ #
    # UI build
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Competitors")
        title.setObjectName("headerTitle")
        subtitle = QLabel("Track your rivals' videos, channels and keywords over time")
        subtitle.setObjectName("headerSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        root.addLayout(header)

        info_row = QHBoxLayout()
        note = QLabel(
            "A snapshot is recorded in the background every hour (and on every refresh "
            "you trigger). VPH and growth need at least two snapshots ~1h apart."
        )
        note.setObjectName("smallLabel")
        note.setWordWrap(True)
        info_row.addWidget(note, 1)
        self._refresh_btn = QPushButton("Refresh now")
        self._refresh_btn.clicked.connect(self.refresh_now)
        info_row.addWidget(self._refresh_btn)
        self._export_btn = ExportButton("competitors", "Competitors dashboard")
        self._export_btn.exported.connect(
            lambda path: self._summary.setText(f"Exported to {path}")
        )
        self._export_btn.failed.connect(lambda message: self._summary.setText(message))
        info_row.addWidget(self._export_btn)
        root.addLayout(info_row)

        self._summary = QLabel("")
        self._summary.setObjectName("growthPositive")
        root.addWidget(self._summary)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_widget = QWidget()
        self._content_layout = QVBoxLayout(scroll_widget)
        self._content_layout.setContentsMargins(0, 0, 8, 0)
        self._content_layout.setSpacing(28)
        self._scroll.setWidget(scroll_widget)
        root.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------ #
    # Dashboard rendering
    # ------------------------------------------------------------------ #
    def refresh_dashboard(self) -> None:
        dash = ce.get_competitor_dashboard()
        self._render(dash)

    def _render(self, dash: dict) -> None:
        # Wipe everything below the summary line (skip deleted widgets so stale
        # labels don't linger for findChildren / screen readers)
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)
                widget.deleteLater()

        self._content_layout.addWidget(
            _section_heading(
                "Tracked videos",
                "VPH = views per hour from your local snapshot history (24h window).",
            )
        )
        videos = dash["videos"]
        if not videos:
            self._content_layout.addWidget(
                self._empty_note(
                    "Nothing tracked yet. Paste a video into the Scorecard and hit “Track video”."
                )
            )
        else:
            self._content_layout.addWidget(self._grid_widget(videos, self._make_video_card))

        self._content_layout.addWidget(
            _section_heading(
                "Tracked channels",
                "Subscriber growth over the last 7 days from snapshot history.",
            )
        )
        channels = dash["channels"]
        if not channels:
            self._content_layout.addWidget(
                self._empty_note(
                    "Nothing tracked yet. Paste a channel into the Scorecard (Channel tab) and hit "
                    "“Track channel”."
                )
            )
        else:
            self._content_layout.addWidget(self._grid_widget(channels, self._make_channel_card))

        self._content_layout.addWidget(
            _section_heading(
                "Tracked keywords",
                "Overall score trend; current ranking positions from the latest search.",
            )
        )
        keywords = dash["keywords"]
        if not keywords:
            self._content_layout.addWidget(
                self._empty_note(
                    "Nothing tracked yet. Research a keyword and hit “Track this keyword” on its "
                    "detail page."
                )
            )
        else:
            self._content_layout.addWidget(self._grid_widget(keywords, self._make_keyword_card))

        self._content_layout.addStretch(1)

        sections = [
            ("Tracked videos", videos),
            ("Tracked channels", channels),
            ("Tracked keywords", keywords),
        ]
        self._export_btn.set_payload(
            videos or channels or keywords,
            sections=sections,
        )

    def _empty_note(self, text: str) -> QLabel:
        note = QLabel(text)
        note.setObjectName("statusText")
        note.setWordWrap(True)
        return note

    def _grid_widget(self, items: list[dict], factory: Any) -> QWidget:
        wrap = QWidget()
        grid = w.FlowLayout(wrap, margin=0, spacing=12)
        grid.setSpacing(12)
        for item in items:
            grid.addWidget(factory(item))
        return wrap

    # ------------------------------------------------------------------ #
    # Cards
    # ------------------------------------------------------------------ #
    def _make_video_card(self, v: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(_VideoThumb(v.get("thumbnailUrl", ""), v.get("title", "")))

        info = QVBoxLayout()
        info.setSpacing(4)
        title = QLabel(v.get("title") or v["videoId"])
        title.setObjectName("urlTitle")
        title.setToolTip(v.get("title") or v["videoId"])
        info.addWidget(title)

        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(8)
        views = QLabel(f"{_fmt(v.get('viewCount', 0))} views")
        views.setObjectName("smallLabel")
        meta.addWidget(views)
        if v.get("vph") is not None:
            chip = QLabel(f"{v['vph']:g}/hr")
            chip.setObjectName("chip")
            meta.addWidget(chip)
        meta.addStretch(1)
        scorecard = QPushButton("Scorecard")
        scorecard.setProperty("variant", "ghost")
        scorecard.setToolTip("Score this video on the Scorecard page")
        scorecard.clicked.connect(
            lambda _=False, vid=v["videoId"]: self.scorecard_requested.emit(
                f"https://www.youtube.com/watch?v={vid}"
            )
        )
        meta.addWidget(scorecard)
        untrack = QPushButton("Untrack")
        untrack.setProperty("variant", "ghost")
        untrack.setToolTip("Remove from tracking")
        untrack.clicked.connect(lambda _=False, k="video", rid=v["videoId"]: self._untrack(k, rid))
        meta.addWidget(untrack)
        info.addLayout(meta)

        if v.get("vphError"):
            err = QLabel(v["vphError"])
            err.setObjectName("smallLabel")
            err.setWordWrap(True)
            info.addWidget(err)

        spark = w.Sparkline([p["value"] for p in v.get("series", [])], width=220, height=32)
        info.addWidget(spark)
        info.addStretch(1)
        layout.addLayout(info, 1)
        return card

    def _make_channel_card(self, c: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(
            w.AvatarThumbnail(c.get("thumbnailUrl", ""), c.get("title", ""), size=48)
            if c.get("thumbnailUrl")
            else w.AvatarInitials(c.get("title") or c["channelId"], size=48)
        )

        info = QVBoxLayout()
        info.setSpacing(4)
        title = QLabel(c.get("title") or c["channelId"])
        title.setObjectName("urlTitle")
        title.setToolTip(c.get("title") or c["channelId"])
        info.addWidget(title)

        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(8)
        subs = QLabel(f"{_fmt(c.get('subscriberCount', 0))} subs")
        subs.setObjectName("smallLabel")
        meta.addWidget(subs)
        growth = c.get("growth7d")
        if growth is not None:
            grow = QLabel(f"{'+' if growth >= 0 else ''}{_fmt(growth)} / 7d")
            grow.setObjectName("growthPositive" if growth >= 0 else "growthNegative")
            grow.setToolTip("Subscriber change over the last 7 days")
            meta.addWidget(grow)
        meta.addStretch(1)
        scorecard = QPushButton("Scorecard")
        scorecard.setProperty("variant", "ghost")
        scorecard.setToolTip("Score this channel on the Scorecard page")
        scorecard.clicked.connect(
            lambda _=False, cid=c["channelId"]: self.scorecard_requested.emit(
                f"https://www.youtube.com/channel/{cid}"
            )
        )
        meta.addWidget(scorecard)
        analyze = QPushButton("Analyze")
        analyze.setProperty("variant", "ghost")
        analyze.setToolTip("Run the AI channel analysis for this channel")
        analyze.clicked.connect(
            lambda _=False, cid=c["channelId"]: self.analyze_requested.emit(cid)
        )
        meta.addWidget(analyze)
        untrack = QPushButton("Untrack")
        untrack.setProperty("variant", "ghost")
        untrack.setToolTip("Remove from tracking")
        untrack.clicked.connect(
            lambda _=False, k="channel", rid=c["channelId"]: self._untrack(k, rid)
        )
        meta.addWidget(untrack)
        info.addLayout(meta)

        spark = w.Sparkline(
            [p["value"] for p in c.get("series", [])], width=220, height=32, stroke="#16a34a"
        )
        info.addWidget(spark)
        info.addStretch(1)
        layout.addLayout(info, 1)
        return card

    def _make_keyword_card(self, k: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        name = QLabel(k["displayTerm"])
        name.setObjectName("urlTitle")
        name.setToolTip(k["term"])
        top.addWidget(name, 1)
        top.addWidget(w.ScoreBadge(k.get("score", 0), size="sm"))
        top.addWidget(w.CompetitionBadge(k.get("competitionLabel", "Low")))
        details = QPushButton("Details")
        details.setProperty("variant", "ghost")
        details.setToolTip("Open this keyword's detail view")
        details.clicked.connect(
            lambda _=False, term=k["term"]: self.keyword_requested.emit(term)
        )
        top.addWidget(details)
        untrack = QPushButton("✕")
        untrack.setProperty("variant", "ghost")
        untrack.setFixedWidth(28)
        untrack.setToolTip("Remove from tracking")
        untrack.clicked.connect(lambda _=False, rid=k["term"]: self._untrack("keyword", rid))
        top.addWidget(untrack)
        layout.addLayout(top)

        series = [p["value"] for p in k.get("series", [])]
        if series:
            layout.addWidget(w.Sparkline(series, width=280, height=32))

        ranked = k.get("rankedVideos", [])
        if ranked:
            ranked_box = QVBoxLayout()
            ranked_box.setContentsMargins(0, 2, 0, 0)
            ranked_box.setSpacing(2)
            for r in ranked[:5]:
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(6)
                pos = QLabel(str(r["position"]))
                pos.setObjectName("statKey")
                pos.setFixedWidth(20)
                pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row.addWidget(pos)
                title = QLabel(r["title"])
                title.setObjectName("smallLabel")
                title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                row.addWidget(title, 1)
                row_box = QWidget()
                row_box.setLayout(row)
                ranked_box.addWidget(row_box)
            ranked_wrap = QWidget()
            ranked_wrap.setLayout(ranked_box)
            layout.addWidget(ranked_wrap)
        return card

    # ------------------------------------------------------------------ #
    # Untrack
    # ------------------------------------------------------------------ #
    def _untrack(self, kind: str, ref_id: str) -> None:
        db.run("DELETE FROM tracked_items WHERE kind = ? AND ref_id = ?", (kind, ref_id))
        self.refresh_dashboard()

    # ------------------------------------------------------------------ #
    # Refresh
    # ------------------------------------------------------------------ #
    def refresh_now(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._summary.setText("A refresh is already running.")
            return
        if not ce.get_competitor_dashboard()["videos"] and not ce.get_competitor_dashboard()[
            "channels"
        ] and not ce.get_competitor_dashboard()["keywords"]:
            self._summary.setText("Nothing tracked yet — no snapshot to record.")
            return
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Refreshing...")
        self._summary.setText("")
        self._worker = RefreshWorker(parent=self)
        self._worker.progress.connect(self._on_refresh_progress)
        self._worker.done.connect(self._on_refresh_done)
        self._worker.failed.connect(self._on_refresh_failed)
        self._worker.start()

    def _on_refresh_progress(self, message: str) -> None:
        self._summary.setText(message)

    def _on_refresh_done(self, counts: dict) -> None:
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("Refresh now")
        failed = int(counts.get("failed") or 0)
        summary = (
            f"Snapshotted {counts.get('videos', 0)} videos, "
            f"{counts.get('channels', 0)} channels, {counts.get('keywords', 0)} keywords."
        )
        if failed:
            summary += f" {failed} failed."
        self._summary.setText(summary)
        self.refresh_dashboard()

    def _on_refresh_failed(self, error: str) -> None:
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("Refresh now")
        self._summary.setText(f"Refresh failed: {error}")

    def stop_workers(self) -> None:
        """Stop and join the refresh worker (called when the app closes)."""
        w.stop_worker(self._worker)
        self._worker = None
