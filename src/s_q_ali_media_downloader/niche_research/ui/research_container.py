"""ResearchContainer — sidebar + stacked research pages for the main nav.

Ported from the companion research web tool's DashboardShell: internal sidebar (Dashboard /
Niche Discovery / Keyword Research / Scorecard / Competitors / Settings)
over a QStackedWidget of the research pages. Also owns the NichePoller that
fires hourly snapshot refreshes on the Competitors page.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
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

from s_q_ali_media_downloader.niche_research.ui.analysis_modal import AnalysisModal
from s_q_ali_media_downloader.niche_research.ui.competitors_page import CompetitorsPage, NichePoller
from s_q_ali_media_downloader.niche_research.ui.keyword_page import KeywordResearchPage
from s_q_ali_media_downloader.niche_research.ui.scorecard_page import ScorecardPage
from s_q_ali_media_downloader.niche_research.ui.settings_page import SettingsPage
from s_q_ali_media_downloader.niche_research.ui.theme import research_style
from s_q_ali_media_downloader.niche_research.ui.trending_page import TrendingChannelsPage

SIDEBAR = (
    ("dashboard", "📊  Dashboard"),
    ("trending", "🔥  Niche Discovery"),
    ("keywords", "🔍  Keyword Research"),
    ("scorecard", "🏆  Scorecard"),
    ("competitors", "👥  Competitors"),
    ("settings", "⚙️  Settings"),
)


class ResearchContainer(QWidget):
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

        # Poller: hourly snapshot refresh on the Competitors page.
        self._poller = NichePoller(self)
        self._poller.snapshot_requested.connect(self._on_poll_tick)

        self.trending_page.analyze_requested.connect(self._open_analysis)
        self._sync_update_btn()

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
        box = QVBoxLayout(page)
        box.setContentsMargins(24, 20, 24, 20)
        box.setSpacing(10)

        title = QLabel("Research Dashboard")
        title.setObjectName("headerTitle")
        box.addWidget(title)

        card = QFrame()
        card.setObjectName("emptyState")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(8)
        icon = QLabel("🚀")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon)
        cap = QLabel("Everything you need to find your next viral channel")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setObjectName("sectionLabel")
        card_layout.addWidget(cap)

        intro = QLabel(
            "Niche Discovery finds channels trending in any niche • Keyword Research "
            "scores SEO terms • Scorecard audits any channel or video • Competitors tracks "
            "the rivals you care about • AI Analysis builds strategies and scripts, and "
            "generates thumbnails."
        )
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.setObjectName("smallLabel")
        intro.setWordWrap(True)
        card_layout.addWidget(intro)
        box.addWidget(card)

        for index, key in enumerate(("discovery", "keywords", "scorecard")):
            hint = QFrame()
            hint.setObjectName("svgCard")
            hint_layout = QHBoxLayout(hint)
            hint_layout.setContentsMargins(12, 12, 12, 12)
            guide = QLabel(
                [
                    "🔥  Start here — run Niche Discovery to surface channels.",
                    "🔍  Score keywords before you plan content around them.",
                    "🏆  Audit a channel or video with the SEO Scorecard.",
                ][index]
            )
            guide.setObjectName("svgMeta")
            hint_layout.addWidget(guide)
            box.addWidget(hint)

        quick = QPushButton("Open Niche Discovery")
        quick.setFixedWidth(180)
        quick.clicked.connect(lambda: self.show_page("trending"))
        box.addWidget(quick, 0, Qt.AlignmentFlag.AlignCenter)
        box.addStretch(1)
        return page

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
        if self.current_page() == "competitors":
            self.competitors_page.refresh_now()

    def _open_analysis(self, channel_id: str) -> None:
        if not channel_id or self._analysis_modal is not None:
            return
        modal = AnalysisModal(channel_id, parent=self)
        self._analysis_modal = modal
        modal.finished.connect(lambda *args: setattr(self, "_analysis_modal", None))
        modal.exec()

    def stop_poller(self) -> None:
        self._poller.stop()
