"""Niche Discovery page — trending channel card grid (app look)."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.niche_research.data.niches import format_name, get_niche, get_niches
from s_q_ali_media_downloader.niche_research.research import trending_engine as te
from s_q_ali_media_downloader.niche_research.research.competitor_engine import track_item
from s_q_ali_media_downloader.niche_research.tools import exporter
from s_q_ali_media_downloader.niche_research.tools import youtube_client as yc
from s_q_ali_media_downloader.niche_research.ui import widgets as w
from s_q_ali_media_downloader.niche_research.ui.export_button import ExportButton
from s_q_ali_media_downloader.niche_research.ui.theme import research_style
from s_q_ali_media_downloader.niche_research.ui.trending_card import (
    TrendingCardData,
    TrendingChannelCard,
)

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


class TrendingDiscoveryWorker(QThread):
    progress = Signal(str)
    done = Signal(int, int)  # discovered, searches_used
    failed = Signal(str)

    def __init__(
        self,
        video_format: str,
        niche: str,
        *,
        cookiefile: str | None = None,
        force: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.video_format = video_format
        self.niche = niche
        self.cookiefile = cookiefile
        self.force = force

    def run(self) -> None:
        try:
            result = te.refresh_all_trending(
                self.video_format,
                self.niche,
                cookiefile=self.cookiefile,
                progress=lambda msg: self.progress.emit(msg),
                force=self.force,
                cancel=self.isInterruptionRequested,
            )
            self.done.emit(result["discovered"], result["searches_used"])
        except Exception as exc:
            self.failed.emit(str(exc))


class ChannelUploadsWorker(QThread):
    """Fetches a channel's recent uploads so they can be queued for download."""

    done = Signal(list)
    failed = Signal(str)

    def __init__(self, channel_id: str, *, parent: QWidget | None = None):
        super().__init__(parent)
        self.channel_id = channel_id

    def run(self) -> None:
        try:
            info = yc.fetch_channel(self.channel_id, uploads_limit=10)
            urls = [
                f"https://www.youtube.com/watch?v={u.get('video_id')}"
                for u in info.uploads
                if u.get("video_id")
            ]
            self.done.emit(urls)
        except Exception as exc:
            logger.warning("Upload fetch failed for %s", self.channel_id, exc_info=True)
            self.failed.emit(str(exc))


class TrendingChannelsPage(QWidget):
    analyze_requested = Signal(str)
    queue_urls_requested = Signal(list)
    scorecard_requested = Signal(str)
    tracked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("researchPage")
        self.setStyleSheet(research_style())

        self._worker: TrendingDiscoveryWorker | None = None
        self._uploads_worker: ChannelUploadsWorker | None = None
        self._selected_format = "all"
        self._selected_niche = "all"
        self._ai_only = False
        self._page = 1
        self._load_count = 0

        self._build()

    # ------------------------------------------------------------------ #
    # UI build
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Header + toolbar
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self._title = QLabel("Trending Channels")
        self._title.setObjectName("headerTitle")
        self._subtitle = QLabel("No channels discovered yet")
        self._subtitle.setObjectName("headerSubtitle")
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self._format_combo = QComboBox()
        self._format_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._niche_combo = QComboBox()
        self._niche_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._niche_combo.setMinimumWidth(190)
        self._discover_btn = QPushButton("Discover")
        self._discover_btn.clicked.connect(self.start_discovery)
        self._ai_only_check = QCheckBox("AI only")
        self._ai_only_check.setToolTip(
            "Only show channels that look AI-generated (score 70+)"
        )
        self._ai_only_check.toggled.connect(self._on_ai_only_changed)
        self._export_btn = ExportButton("niche-discovery", "Niche Discovery")
        self._export_btn.exported.connect(self._on_exported)
        controls.addWidget(self._format_combo)
        controls.addWidget(self._niche_combo)
        controls.addWidget(self._ai_only_check)
        controls.addWidget(self._discover_btn)
        controls.addWidget(self._export_btn)
        header.addLayout(controls)
        root.addLayout(header)

        # Status bar
        status = QFrame()
        status.setObjectName("statusBar")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(16)
        self._budget_icon = QLabel("")
        self._last_discovered = QLabel("")
        self._last_discovered.setObjectName("statusText")
        self._message = QLabel("")
        self._message.setObjectName("statusText")
        status_layout.addWidget(self._budget_icon)
        status_layout.addWidget(self._last_discovered)
        status_layout.addStretch(1)
        status_layout.addWidget(self._message)
        root.addWidget(status)

        # Card grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_widget = QWidget()
        self._grid = w.FlowLayout(self._grid_widget, margin=4, spacing=14)
        self._grid_widget.setLayout(self._grid)
        self._scroll.setWidget(self._grid_widget)
        self._empty_state: QWidget | None = None
        root.addWidget(self._scroll, 1)

        # Pagination
        pager = QHBoxLayout()
        pager.setContentsMargins(0, 0, 0, 0)
        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setProperty("variant", "outline")
        self._next_btn = QPushButton("Next")
        self._next_btn.setProperty("variant", "outline")
        self._page_label = QLabel("")
        self._page_label.setObjectName("statusText")
        pager.addStretch(1)
        pager.addWidget(self._prev_btn)
        pager.addWidget(self._page_label)
        pager.addWidget(self._next_btn)
        pager.addStretch(1)
        root.addLayout(pager)

        self._prev_btn.clicked.connect(lambda: self.show_page(self._page - 1))
        self._next_btn.clicked.connect(lambda: self.show_page(self._page + 1))

        self._populate_format_combo()
        self._populate_niche_combo()
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        self._niche_combo.currentIndexChanged.connect(self._on_niche_changed)
        self.reload(keep_page=True)

    # ------------------------------------------------------------------ #
    # Plumbing
    # ------------------------------------------------------------------ #
    def _populate_format_combo(self) -> None:
        self._format_combo.blockSignals(True)
        self._format_combo.clear()
        self._format_combo.addItem("All Formats", "all")
        self._format_combo.addItem("Longform", "longform")
        self._format_combo.addItem("Shortform", "shortform")
        self._format_combo.blockSignals(False)

    def _populate_niche_combo(self) -> None:
        """Fill the niche filter.

        With a format selected only that format's niches are offered; with
        "All Formats" the union of every format's niches is offered, so the
        filter is usable without touching the format combo first.
        """
        self._niche_combo.blockSignals(True)
        self._niche_combo.clear()
        self._niche_combo.addItem("All Niches", "all")
        fmt = self._selected_format if self._selected_format != "all" else None
        for niche in get_niches(fmt).values():
            self._niche_combo.addItem(niche.name, niche.id)
        self._niche_combo.blockSignals(False)
        self._fit_niche_combo()

    def _fit_niche_combo(self) -> None:
        fm = self._niche_combo.fontMetrics()
        widest = 0
        for i in range(self._niche_combo.count()):
            widest = max(widest, fm.horizontalAdvance(self._niche_combo.itemText(i)))
        width = max(190, min(340, widest + 48))
        self._niche_combo.setMinimumWidth(width)
        view = self._niche_combo.view()
        if view is not None:
            view.setMinimumWidth(width)

    def _on_format_changed(self, index: int) -> None:
        self._selected_format = self._format_combo.itemData(index)
        self._selected_niche = "all"
        self._page = 1
        self._populate_niche_combo()
        self.reload(keep_page=True)

    def _on_niche_changed(self, index: int) -> None:
        self._selected_niche = self._niche_combo.itemData(index)
        self._page = 1
        self.reload(keep_page=True)

    def _on_ai_only_changed(self, checked: bool) -> None:
        self._ai_only = bool(checked)
        self._page = 1
        self.reload(keep_page=True)

    def reload(self, keep_page: bool = False) -> None:
        if not keep_page:
            self._page = 1
        self._refresh_grid()
        self._refresh_status_bar()

    def selected_format(self) -> str:
        return self._selected_format

    def selected_niche(self) -> str:
        return self._selected_niche

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    def start_discovery(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        fmt = self.selected_format()
        niche = self.selected_niche()
        if fmt == "all" and niche == "all":
            answer = QMessageBox.question(
                self,
                "Full discovery",
                "This will re-scan ALL niches across BOTH formats "
                "(50+ niches, several yt-dlp searches each).\n\n"
                "It can take a long time. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        nfmt = "All formats" if fmt == "all" else format_name(fmt)
        nname = "all niches" if niche == "all" else self._niche_combo.currentText()
        self._set_message(f"Discovering {nfmt} / {nname} ... (force refresh, may take a minute)")
        self._discover_btn.setEnabled(False)
        self._discover_btn.setText("Discovering...")
        self._worker = TrendingDiscoveryWorker(fmt, niche, parent=self, force=True)
        self._worker.progress.connect(self._on_discovery_progress)
        self._worker.done.connect(self._on_discovery_done)
        self._worker.failed.connect(self._on_discovery_failed)
        self._worker.start()

    def _on_discovery_progress(self, message: str) -> None:
        self._set_message(message)

    def _on_discovery_done(self, discovered: int, searches_used: int) -> None:
        self._discover_btn.setEnabled(True)
        self._discover_btn.setText("Discover")
        self._set_message(
            f"Discovered {discovered} new channels ({searches_used} searches)", ok=True
        )
        self.reload(keep_page=True)

    def _on_discovery_failed(self, error: str) -> None:
        self._discover_btn.setEnabled(True)
        self._discover_btn.setText("Discover")
        self._set_message(f"Discovery failed: {error}", error=True)

    def _set_message(self, text: str, ok: bool = False, error: bool = False) -> None:
        self._message.setText(text)
        if error:
            self._message.setObjectName("statusError")
        elif ok:
            self._message.setObjectName("statusOk")
        else:
            self._message.setObjectName("statusText")
        self._message.style().unpolish(self._message)
        self._message.style().polish(self._message)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def _refresh_grid(self) -> None:
        self._clear_grid()
        fmt = self.selected_format()
        niche = self.selected_niche()
        offset = (self._page - 1) * PAGE_SIZE

        channels = te.get_trending_channels(
            fmt, niche, limit=PAGE_SIZE, offset=offset, ai_only=self._ai_only
        )
        # The count must use the same filters, or the header lies and "Next"
        # leads to an empty page.
        total = te.get_trending_channel_count(fmt, niche, ai_only=self._ai_only)
        total_pages = max(1, -(-total // PAGE_SIZE)) if total else 1

        self._load_count = total
        self._subtitle.setText(
            f"{total} channels discovered  \u2022  newly created + rapidly growing rank first in every niche"
        )

        for ch in channels:
            rpm = None
            niche_data = get_niche(ch.video_format, ch.niche)
            if niche_data is not None:
                rpm = {
                    "min": niche_data.rpm.min,
                    "max": niche_data.rpm.max,
                    "avg": niche_data.rpm.avg,
                }
            card = TrendingChannelCard(
                TrendingCardData(
                    channel_id=ch.channel_id,
                    title=ch.title,
                    thumbnail_url=ch.thumbnail_url,
                    subscriber_count=ch.subscriber_count,
                    view_count=ch.view_count,
                    video_count=ch.video_count,
                    viral_score=ch.viral_score,
                    growth_rate=ch.growth_rate,
                    is_newly_created=ch.is_newly_created,
                    is_rapidly_growing=ch.is_rapidly_growing,
                    ai_score=ch.ai_score,
                    category_name=ch.category_name,
                    view_sub_ratio=ch.view_sub_ratio,
                    video_format=ch.video_format,
                    niche=ch.niche,
                    rpm=rpm,
                    niche_competition=(niche_data.competition if niche_data else ""),
                    niche_difficulty=(niche_data.difficulty if niche_data else ""),
                )
            )
            card.analyze_requested.connect(self.analyze_requested)
            card.queue_requested.connect(self._queue_channel_videos)
            card.scorecard_requested.connect(self.scorecard_requested)
            card.track_requested.connect(self._track_channel)
            card.open_requested.connect(self._open_channel)
            self._grid.addWidget(card)

        self._export_btn.set_payload(exporter.rows_from(channels))

        if not channels:
            self._show_empty_state()

        self._prev_btn.setEnabled(self._page > 1)
        self._next_btn.setEnabled(self._page < total_pages)
        self._page_label.setText(f"Page {self._page} of {total_pages}")

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if self._empty_state is not None:
            self._empty_state.deleteLater()
            self._empty_state = None

    def _show_empty_state(self) -> None:
        state = QFrame()
        state.setObjectName("emptyState")
        layout = QVBoxLayout(state)
        layout.setContentsMargins(24, 48, 24, 48)
        layout.setSpacing(8)
        icon = QLabel("\U0001f4e6")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 40px; background: transparent; border: none;")
        text = QLabel("No trending channels found")
        text.setObjectName("headerSubtitle")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn = QPushButton("Discover Channels")
        btn.clicked.connect(self.start_discovery)
        btn.setFixedWidth(180)
        layout.addWidget(icon)
        layout.addWidget(text)
        layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self._empty_state = state
        self._grid.addWidget(state)

    def _refresh_status_bar(self) -> None:
        discovery = te.get_discovery_status()
        if discovery:
            latest = discovery[0]
            self._last_discovered.setText(
                f"Last discovered: {w.time_ago(latest['discovered_at'])} "
                f"({latest['channels_found']} channels)"
            )
        else:
            self._last_discovered.setText("Not discovered yet")
        self._budget_icon.setText("Search: yt-dlp, no quota")

    def show_page(self, page: int) -> None:
        self._page = max(1, page)
        self.reload(keep_page=True)

    # ------------------------------------------------------------------ #
    # Card actions
    # ------------------------------------------------------------------ #
    def _track_channel(self, channel_id: str, title: str = "") -> None:
        """Track the channel so the Competitors page can follow it."""
        if not title:
            row = te.get_trending_channel_by_id(channel_id)
            title = (row.title if row is not None else "") or channel_id
        track_item("channel", channel_id, title)
        self.tracked.emit(channel_id)
        self._set_message(f"Tracking {title}.", ok=True)

    def _open_channel(self, channel_id: str) -> None:
        """Open the channel on YouTube in the default browser."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        url = f"https://www.youtube.com/channel/{channel_id}"
        QDesktopServices.openUrl(QUrl(url))

    def _queue_channel_videos(self, channel_id: str) -> None:
        """Fetch the channel's recent uploads and hand them to the queue."""
        if self._uploads_worker is not None and self._uploads_worker.isRunning():
            self._set_message("Already fetching uploads…")
            return
        self._set_message("Fetching this channel's recent videos…")
        self._uploads_worker = ChannelUploadsWorker(channel_id, parent=self)
        self._uploads_worker.done.connect(self._on_uploads_ready)
        self._uploads_worker.failed.connect(self._on_uploads_failed)
        self._uploads_worker.start()

    def _on_uploads_ready(self, urls: list) -> None:
        if not urls:
            self._set_message("No videos found for that channel.", error=True)
            return
        self._set_message(f"Queueing {len(urls)} videos…", ok=True)
        self.queue_urls_requested.emit(urls)

    def _on_uploads_failed(self, error: str) -> None:
        self._set_message(f"Could not fetch videos: {error}", error=True)

    def _on_exported(self, path: str) -> None:
        self._set_message(f"Exported to {path}", ok=True)

    def stop_workers(self) -> None:
        """Stop and join the discovery worker (called when the app closes)."""
        w.stop_worker(self._worker)
        self._worker = None
        w.stop_worker(self._uploads_worker)
        self._uploads_worker = None
