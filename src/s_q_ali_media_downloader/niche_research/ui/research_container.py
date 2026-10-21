"""ResearchContainer — sidebar + stacked research pages for the main nav.

Ported from the companion research web tool's DashboardShell: internal sidebar (Dashboard /
Niche Discovery / Keyword Research / Scorecard / Competitors / Settings)
over a QStackedWidget of the research pages. Also owns the NichePoller that
fires hourly snapshot refreshes on the Competitors page.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.niche_research.research import competitor_engine, dashboard_engine
from s_q_ali_media_downloader.niche_research.ui import widgets as w
from s_q_ali_media_downloader.niche_research.ui.analysis_modal import AnalysisModal
from s_q_ali_media_downloader.niche_research.ui.competitors_page import CompetitorsPage, NichePoller
from s_q_ali_media_downloader.niche_research.ui.keyword_page import KeywordResearchPage
from s_q_ali_media_downloader.niche_research.ui.scorecard_page import ScorecardPage
from s_q_ali_media_downloader.niche_research.ui.settings_page import SettingsPage
from s_q_ali_media_downloader.niche_research.ui.theme import research_style
from s_q_ali_media_downloader.niche_research.ui.trending_page import TrendingChannelsPage

logger = logging.getLogger(__name__)

SIDEBAR = (
    ("dashboard", "📊  Dashboard"),
    ("trending", "🔥  Niche Discovery"),
    ("keywords", "🔍  Keyword Research"),
    ("scorecard", "🏆  Scorecard"),
    ("competitors", "👥  Competitors"),
    ("settings", "⚙️  Settings"),
)


class ResearchContainer(QWidget):
    """Sidebar + stacked research pages.

    ``send_to_queue_requested`` is the single bridge from the research tab
    to the app's download queue; the Agent tab uses the same bridge.
    """

    send_to_queue_requested = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("researchContainer")
        self.setStyleSheet(research_style())
        self._analysis_modal = None
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.dashboard_page = self._build_dashboard()
        self.trending_page = TrendingChannelsPage()
        self.keyword_page = KeywordResearchPage()
        self.scorecard_page = ScorecardPage()
        self.competitors_page = CompetitorsPage()
        self.settings_page = SettingsPage()
        for page in (
            self.dashboard_page,
            self.trending_page,
            self.keyword_page,
            self.scorecard_page,
            self.competitors_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

        # Poller: hourly snapshot refresh — runs app-wide, not only while the
        # Competitors page is open, so VPH and growth actually accumulate.
        self._poller = NichePoller(
            self, interval_ms=competitor_engine.snapshot_interval_minutes() * 60 * 1000
        )
        self._poller.snapshot_requested.connect(self._on_poll_tick)

        self.trending_page.analyze_requested.connect(self._open_analysis)
        self.trending_page.queue_urls_requested.connect(self.send_to_queue_requested)
        self.trending_page.scorecard_requested.connect(
            lambda cid: self._open_scorecard(f"https://www.youtube.com/channel/{cid}", "channel")
        )
        self.trending_page.tracked.connect(self._on_channel_tracked)
        self.scorecard_page.analyze_requested.connect(self._open_analysis)
        self.scorecard_page.queue_urls_requested.connect(self.send_to_queue_requested)
        self.scorecard_page.open_browser_requested.connect(self._open_in_browser)
        self.competitors_page.scorecard_requested.connect(self._open_scorecard)
        self.competitors_page.analyze_requested.connect(self._open_analysis)
        self.competitors_page.keyword_requested.connect(self._open_keyword)
        self.competitors_page.queue_urls_requested.connect(self.send_to_queue_requested)
        self.keyword_page.scorecard_requested.connect(self._open_keyword_scorecard)
        self.settings_page.snapshot_interval_saved.connect(self._on_snapshot_interval_saved)
        self._sync_update_btn()
        self.refresh_dashboard()

    def _build_sidebar(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("researchSidebar")
        rail.setFixedWidth(220)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(12, 18, 12, 12)
        lay.setSpacing(6)

        brand = QLabel("S-Q CREATOR STUDIO")
        brand.setObjectName("researchBrand")
        lay.addWidget(brand)
        sub = QLabel("Content discovery toolkit")
        sub.setObjectName("researchSub")
        lay.addWidget(sub)
        lay.addSpacing(10)

        self._sidebar_group = QButtonGroup(self)
        self._sidebar_group.setExclusive(True)
        self._sidebar_buttons: dict[str, QPushButton] = {}
        for key, label in SIDEBAR:
            btn = QPushButton(label)
            btn.setProperty("sidebar", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(38)
            self._sidebar_group.addButton(btn)
            self._sidebar_buttons[key] = btn
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            lay.addWidget(btn)

        self._sidebar_buttons["dashboard"].setChecked(True)
        lay.addStretch(1)

        self.btn_update = QPushButton("🔄  Update")
        self.btn_update.setProperty("sidebar", True)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setMinimumHeight(38)
        self.btn_update.setToolTip(
            "Update refreshes this page: Niche Discovery re-scans YouTube · "
            "Keyword Research re-runs the last search · Competitors takes a fresh snapshot"
        )
        self.btn_update.clicked.connect(self.update_now)
        lay.addWidget(self.btn_update)
        return rail

    def _build_dashboard(self) -> QWidget:
        page = QWidget()
        page.setObjectName("researchPage")
        box = QVBoxLayout(page)
        box.setContentsMargins(24, 20, 24, 20)
        box.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Research Dashboard")
        title.setObjectName("headerTitle")
        self._dash_subtitle = QLabel("Live view of your research")
        self._dash_subtitle.setObjectName("headerSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(self._dash_subtitle)
        header.addLayout(title_box, 1)
        self._dash_refresh = QPushButton("🔄  Refresh")
        self._dash_refresh.setProperty("variant", "outline")
        self._dash_refresh.clicked.connect(self.refresh_dashboard)
        header.addWidget(self._dash_refresh)
        box.addLayout(header)

        # Metric tiles
        self._dash_metrics: dict[str, QLabel] = {}
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        for key, label in (
            ("channelsDiscovered", "Channels discovered"),
            ("trackedChannels", "Channels tracked"),
            ("trackedVideos", "Videos tracked"),
            ("trackedKeywords", "Keywords tracked"),
            ("keywordsResearched", "Keywords researched"),
            ("videosScored", "Videos scored"),
        ):
            tile = QFrame()
            tile.setObjectName("card")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(14, 10, 14, 10)
            tile_layout.setSpacing(2)
            value = QLabel("0")
            value.setObjectName("statTileValue")
            cap = QLabel(label)
            cap.setObjectName("statTileLabel")
            tile_layout.addWidget(value)
            tile_layout.addWidget(cap)
            tiles.addWidget(tile, 1)
            self._dash_metrics[key] = value
        box.addLayout(tiles)

        # Top channels + top keywords
        columns = QHBoxLayout()
        columns.setSpacing(12)
        self._dash_top_channels = self._dash_list("Top channels")
        self._dash_top_keywords = self._dash_list("Top keywords")
        columns.addWidget(self._dash_top_channels, 1)
        columns.addWidget(self._dash_top_keywords, 1)
        box.addLayout(columns)

        # Recent activity
        activity = QFrame()
        activity.setObjectName("card")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(14, 12, 14, 12)
        activity_layout.setSpacing(6)
        cap = QLabel("Recent activity")
        cap.setObjectName("sectionLabel")
        activity_layout.addWidget(cap)
        self._dash_activity = QVBoxLayout()
        self._dash_activity.setSpacing(4)
        activity_layout.addLayout(self._dash_activity)
        box.addWidget(activity)

        # Quick actions (the guide cards are buttons now, not static labels)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for label, key in (
            ("🔥  Niche Discovery", "trending"),
            ("🔍  Keyword Research", "keywords"),
            ("🏆  Scorecard", "scorecard"),
            ("👥  Competitors", "competitors"),
            ("⚙️  Settings", "settings"),
        ):
            btn = QPushButton(label)
            btn.setProperty("variant", "outline")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            actions.addWidget(btn)
        box.addLayout(actions)
        box.addStretch(1)
        return page

    def _dash_list(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        cap = QLabel(title)
        cap.setObjectName("sectionLabel")
        layout.addWidget(cap)
        body = QVBoxLayout()
        body.setSpacing(4)
        layout.addLayout(body)
        frame.setProperty("bodyLayout", body)
        return frame

    def refresh_dashboard(self) -> None:
        """Reload the dashboard from the database."""
        data = dashboard_engine.get_dashboard_data()
        metrics = data["metrics"]
        for key, label in self._dash_metrics.items():
            label.setText(str(metrics.get(key, 0)))

        self._fill_dash_list(
            self._dash_top_channels,
            [
                f"{row['title'] or row['channel_id']} — {int(row['viral_score'] or 0)} viral"
                for row in data["topChannels"]
            ],
            empty="No channels discovered yet — run Niche Discovery.",
        )
        self._fill_dash_list(
            self._dash_top_keywords,
            [
                f"{row['display_term'] or row['term']} — {int(row['score'] or 0)} overall"
                for row in data["topKeywords"]
            ],
            empty="No keywords researched yet.",
        )

        while self._dash_activity.count():
            item = self._dash_activity.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        activity = data["activity"]
        if not activity:
            note = QLabel("Nothing has happened yet — start with Niche Discovery.")
            note.setObjectName("smallLabel")
            self._dash_activity.addWidget(note)
        for entry in activity:
            row = QLabel(f"{entry['label']}  ·  {w.time_ago(entry['ts'])}")
            row.setObjectName("smallLabel")
            self._dash_activity.addWidget(row)

    def _fill_dash_list(self, frame: QFrame, items: list[str], empty: str) -> None:
        body = frame.property("bodyLayout")
        if body is None:
            return
        while body.count():
            item = body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not items:
            note = QLabel(empty)
            note.setObjectName("smallLabel")
            note.setWordWrap(True)
            body.addWidget(note)
            return
        for text in items:
            label = QLabel(text)
            label.setObjectName("smallLabel")
            body.addWidget(label)

    def show_page(self, key: str) -> None:
        order = {k: i for i, (k, _) in enumerate(SIDEBAR)}
        index = order.get(key, 0)
        self.stack.setCurrentIndex(index)
        btn = self._sidebar_buttons.get(key)
        if btn is not None:
            btn.setChecked(True)
        if key == "competitors":
            self.competitors_page.refresh_dashboard()
        elif key == "trending":
            self.trending_page.reload(keep_page=True)
        elif key == "dashboard":
            self.refresh_dashboard()
        self._sync_update_btn()

    def _sync_update_btn(self) -> None:
        self.btn_update.setEnabled(self.current_page() in ("trending", "keywords", "competitors"))

    def current_page(self) -> str:
        index = self.stack.currentIndex()
        return SIDEBAR[index][0] if index < len(SIDEBAR) else "dashboard"

    def update_now(self) -> None:
        """Refresh the visible page's data (live scan / re-research / snapshots)."""
        page = self.current_page()
        if page == "trending":
            self.trending_page.start_discovery()
        elif page == "keywords":
            self.keyword_page.re_run()
        elif page == "competitors":
            self.competitors_page.refresh_now()

    def _on_poll_tick(self) -> None:
        """The hourly snapshot refresh — app-wide, not page-dependent."""
        self.competitors_page.refresh_now()

    def _open_analysis(self, channel_id: str) -> None:
        if not channel_id or self._analysis_modal is not None:
            return
        modal = AnalysisModal(channel_id, parent=self)
        self._analysis_modal = modal
        modal.open_scorecard_requested.connect(
            lambda cid: self._open_scorecard(
                f"https://www.youtube.com/channel/{cid}", "channel"
            )
        )
        modal.queue_urls_requested.connect(self.send_to_queue_requested)
        modal.track_channel_requested.connect(self._track_channel)
        modal.finished.connect(lambda *args: setattr(self, "_analysis_modal", None))
        modal.exec()

    def _track_channel(self, channel_id: str) -> None:
        """Track a channel from the analysis modal (AI Analysis -> Competitors)."""
        if not channel_id:
            return
        competitor_engine.track_item("channel", channel_id, channel_id)
        self.competitors_page.refresh_dashboard()

    def _open_scorecard(self, url: str, mode: str = "video", focus_keyword: str = "") -> None:
        """Open the Scorecard on a URL, with the input prefilled."""
        if not url:
            return
        page = self.scorecard_page
        page.set_mode(mode)
        page.prefill(url, focus_keyword)
        self.show_page("scorecard")

    def _open_keyword_scorecard(self, url: str, focus_keyword: str) -> None:
        """Keyword Research -> Scorecard: score a ranked video for a keyword."""
        self._open_scorecard(url, "video", focus_keyword)

    def _open_in_browser(self, url: str) -> None:
        """Open an https URL in the default browser — nothing else."""
        if not url or not url.lower().startswith("https://"):
            logger.warning("Refusing to open a non-https URL: %r", url)
            return
        QDesktopServices.openUrl(QUrl(url))

    def _on_snapshot_interval_saved(self, minutes: int) -> None:
        """A new snapshot interval must reach the running poller."""
        self._poller.set_interval_minutes(minutes)

    def _open_keyword(self, term: str) -> None:
        """Open a tracked keyword's detail view."""
        if not term:
            return
        self.keyword_page.show_detail(term)
        self.show_page("keywords")

    def _on_channel_tracked(self, channel_id: str) -> None:
        """A channel tracked from Discovery shows up on Competitors."""
        self.competitors_page.refresh_dashboard()

    def stop_poller(self) -> None:
        self._poller.stop()

    def shutdown(self) -> None:
        """Stop the poller and every page worker.

        Called when the app closes: a QThread that is destroyed while it is
        still running aborts the whole process, and so does the thumbnail
        loader's fetch thread if it is still inside a request.
        """
        self.stop_poller()
        for page in (
            self.trending_page,
            self.keyword_page,
            self.scorecard_page,
            self.competitors_page,
        ):
            stop = getattr(page, "stop_workers", None)
            if callable(stop):
                stop()
        if self._analysis_modal is not None:
            self._analysis_modal.reject()
        w.shutdown_thumb_loader()
