"""AnalysisModal — AI channel strategy, ideas, scripts, blueprint + thumbnail.

Ported from the companion research web tool's AnalysisModal.tsx. Rendered as a QDialog with a
tabbed body. All network/analysis work runs on QThread workers.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.niche_research.research import ai_analysis_engine as ai
from s_q_ali_media_downloader.niche_research.ui import widgets as w
from s_q_ali_media_downloader.niche_research.ui.theme import research_style

logger = logging.getLogger(__name__)

TABS = ("strategy", "ideas", "scripts", "blueprint", "thumbnail")


class ChannelDataWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, channel_id: str, *, parent: QWidget | None = None):
        super().__init__(parent)
        self.channel_id = channel_id

    def run(self) -> None:
        try:
            self.done.emit(ai.load_channel_analysis_data(self.channel_id))
        except Exception as exc:
            logger.warning("Channel data load failed", exc_info=True)
            self.failed.emit(str(exc))


class AnalyzeWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, channel_id: str, *, parent: QWidget | None = None):
        super().__init__(parent)
        self.channel_id = channel_id

    def run(self) -> None:
        try:
            analysis = ai.analyze_channel(self.channel_id)
            self.done.emit(analysis)
        except Exception as exc:
            logger.warning("AI analysis failed", exc_info=True)
            self.failed.emit(str(exc))


class ThumbnailWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, title: str, style: str, niche: str | None, *, parent=None):
        super().__init__(parent)
        self.title = title
        self.style = style
        self.niche = niche

    def run(self) -> None:
        try:
            self.done.emit(ai.generate_thumbnail(self.title, style=self.style, niche=self.niche))
        except Exception as exc:
            logger.warning("Thumbnail generation failed", exc_info=True)
            self.failed.emit(str(exc))


def _fmt(n: float | None) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))


def _selectable(label: QLabel) -> QLabel:
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class AnalysisModal(QDialog):
    def __init__(self, channel_id: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("analysisModal")
        self.setWindowTitle("Channel Analysis")
        self.resize(880, 660)
        self.setMinimumSize(700, 520)
        self.setStyleSheet(research_style())
        self.channel_id = channel_id

        self._workers: list[QThread] = []
        self._active_tab = "strategy"
        self._thumb_image: str | None = None
        self._thumb_style = "bold"
        self._build()
        self._load()

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("modalPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(12)

        header = QHBoxLayout()
        self._modal_title = _selectable(QLabel("Loading…"))
        self._modal_title.setObjectName("modalHeader")
        header.addWidget(self._modal_title, 1)
        close_x = QPushButton("✕")
        close_x.setProperty("variant", "ghost")
        close_x.setFixedWidth(34)
        close_x.clicked.connect(self.reject)
        header.addWidget(close_x)
        panel_layout.addLayout(header)

        self._stack = QStackedWidget()
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        outer.setFrameShape(QFrame.Shape.NoFrame)
        outer.setWidget(self._stack)
        panel_layout.addWidget(outer, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setProperty("variant", "outline")
        close_btn.clicked.connect(self.reject)
        footer.addWidget(close_btn)
        panel_layout.addLayout(footer)

        root.addWidget(panel)

        self._stack.addWidget(self._build_loading())
        self._stack.addWidget(self._build_error())
        self._stack.addWidget(self._build_content())

    def _build_loading(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addStretch(1)
        icon = QLabel("⚙️")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(icon)
        text = QLabel("Loading channel…")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setObjectName("smallLabel")
        box.addWidget(text)
        box.addStretch(1)
        return page

    def _build_error(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addStretch(1)
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setObjectName("statusError")
        self._error_label.setWordWrap(True)
        box.addWidget(self._error_label)
        retry = QPushButton("Retry")
        retry.setFixedWidth(140)
        retry.clicked.connect(self._load)
        box.addWidget(retry, 0, Qt.AlignmentFlag.AlignCenter)
        box.addStretch(1)
        return page

    def _build_content(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(12)

        self._channel_row = QWidget()
        box.addWidget(self._channel_row)

        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(8)
        stats_wrap = QWidget()
        stats_wrap.setLayout(self._stats_row)
        box.addWidget(stats_wrap)

        self._trending_row = QHBoxLayout()
        self._trending_row.setSpacing(14)
        trending_wrap = QWidget()
        trending_wrap.setLayout(self._trending_row)
        box.addWidget(trending_wrap)

        self._recent_cap = QLabel("")
        self._recent_cap.setObjectName("sectionLabel")
        box.addWidget(self._recent_cap, 0, Qt.AlignmentFlag.AlignLeft)

        self._recent_grid = w.FlowLayout(margin=0, spacing=10)
        recent_wrap = QWidget()
        recent_wrap.setLayout(self._recent_grid)
        box.addWidget(recent_wrap)

        self._analysis_stack = QStackedWidget()
        box.addWidget(self._analysis_stack, 1)
        self._analysis_stack.addWidget(self._build_not_analyzed())
        self._analysis_stack.addWidget(self._build_analyzed_tabs())
        return page

    def _build_not_analyzed(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addStretch(1)
        card = QFrame()
        card.setObjectName("emptyState")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 32, 40, 32)
        card_layout.setSpacing(8)
        icon = QLabel("💡")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon)
        title = QLabel("Ready to Analyze")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("sectionLabel")
        card_layout.addWidget(title)
        sub = QLabel(
            "Generate AI-powered strategy, content ideas, scripts, and a growth blueprint "
            "for this channel."
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setObjectName("smallLabel")
        sub.setWordWrap(True)
        card_layout.addWidget(sub)
        self._analyze_btn = QPushButton("Create Similar Channel")
        self._analyze_btn.setFixedWidth(220)
        self._analyze_btn.clicked.connect(self._start_analyze)
        card_layout.addWidget(self._analyze_btn, 0, Qt.AlignmentFlag.AlignCenter)
        box.addWidget(card)
        box.addStretch(1)
        return page

    def _build_analyzed_tabs(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)

        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        self._tab_buttons: dict[str, QPushButton] = {}
        for tab, label in (
            ("strategy", "Strategy"),
            ("ideas", "Content Ideas"),
            ("scripts", "Scripts"),
            ("blueprint", "Growth Blueprint"),
            ("thumbnail", "Thumbnail"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("tabBtn")
            btn.setProperty("active", tab == "strategy")
            btn.clicked.connect(lambda _=False, t=tab: self._set_tab(t))
            tab_row.addWidget(btn)
            self._tab_buttons[tab] = btn
        tab_row.addStretch(1)
        box.addLayout(tab_row)

        self._tab_stack = QStackedWidget()
        self._strategy_page = QWidget()
        self._strategy_layout = QVBoxLayout(self._strategy_page)
        self._ideas_page = QWidget()
        self._ideas_layout = QVBoxLayout(self._ideas_page)
        self._scripts_page = QWidget()
        self._scripts_layout = QVBoxLayout(self._scripts_page)
        self._blueprint_page = QWidget()
        self._blueprint_layout = QHBoxLayout(self._blueprint_page)
        self._blueprint_layout.setSpacing(10)
        self._thumbnail_page = self._build_thumbnail_tab()
        for pg in (
            self._strategy_page,
            self._ideas_page,
            self._scripts_page,
            self._blueprint_page,
            self._thumbnail_page,
        ):
            self._tab_stack.addWidget(pg)
        box.addWidget(self._tab_stack, 1)
        return page

    def _build_thumbnail_tab(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)

        card = QFrame()
        card.setObjectName("svgCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)

        cap = QLabel("Thumbnail Generator")
        cap.setObjectName("sectionLabel")
        card_layout.addWidget(cap)
        hint = QLabel(
            "Generate AI-powered thumbnails for your videos. Requires the aiHubMix API key "
            "in Settings."
        )
        hint.setObjectName("smallLabel")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)

        self._thumb_title = QLineEdit()
        self._thumb_title.setPlaceholderText("Enter your video title...")
        card_layout.addWidget(self._thumb_title)

        style_row = QHBoxLayout()
        style_row.setSpacing(6)
        self._style_buttons: dict[str, QPushButton] = {}
        for style in ("bold", "modern", "minimal", "cinematic", "vibrant"):
            btn = QPushButton(style.capitalize())
            btn.setObjectName("tabBtn")
            btn.setProperty("active", style == "bold")
            btn.clicked.connect(lambda _=False, s=style: self._set_style(s))
            style_row.addWidget(btn)
            self._style_buttons[style] = btn
        style_row.addStretch(1)
        card_layout.addLayout(style_row)

        self._gen_btn = QPushButton("Generate Thumbnail")
        self._gen_btn.clicked.connect(self._start_thumbnail)
        card_layout.addWidget(self._gen_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self._thumb_error = QLabel("")
        self._thumb_error.setObjectName("statusError")
        self._thumb_error.setWordWrap(True)
        card_layout.addWidget(self._thumb_error)

        box.addWidget(card)

        self._preview_wrap = QWidget()
        preview_layout = QVBoxLayout(self._preview_wrap)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)
        self._preview = QLabel("No thumbnail yet")
        self._preview.setObjectName("smallLabel")
        self._preview.setFixedHeight(260)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setFrameShape(QFrame.Shape.StyledPanel)
        preview_layout.addWidget(self._preview)
        self._download_btn = QPushButton("Save thumbnail…")
        self._download_btn.hide()
        self._download_btn.clicked.connect(self._download_thumbnail)
        preview_layout.addWidget(self._download_btn, 0, Qt.AlignmentFlag.AlignLeft)
        box.addWidget(self._preview_wrap, 1)
        return page

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        self._stack.setCurrentIndex(0)
        worker = ChannelDataWorker(self.channel_id, parent=self)
        self._track_worker(worker)
        worker.done.connect(self._on_channel_data)
        worker.failed.connect(self._on_channel_error)
        worker.start()

    def _track_worker(self, worker: QThread) -> None:
        worker.finished.connect(
            lambda w=worker: self._workers.remove(w) if w in self._workers else None
        )
        self._workers.append(worker)

    def _on_channel_error(self, error: str) -> None:
        self._error_label.setText(f"Failed to load channel: {error}")
        self._stack.setCurrentIndex(1)

    def _on_channel_data(self, data: dict) -> None:
        self._data = data
        self._modal_title.setText(data["channel"].get("title") or "Channel Analysis")
        self._render_channel(data)
        self._stack.setCurrentIndex(2)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def _render_channel(self, data: dict) -> None:
        channel = data["channel"]
        trending = data.get("trending")

        # Channel row
        channel_box = QVBoxLayout(self._channel_row)
        channel_box.setContentsMargins(0, 0, 0, 0)
        channel_box.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(12)
        avatar = w.AvatarThumbnail(
            channel.get("thumbnailUrl", ""), channel.get("title", ""), size=64
        )
        row.addWidget(avatar)
        info = QVBoxLayout()
        info.setSpacing(2)
        name = _selectable(QLabel(channel.get("title", "")))
        name.setObjectName("headerTitle")
        info.addWidget(name)
        meta = _selectable(
            QLabel(
                f"{channel.get('country') or 'Unknown'} • "
                f"{(trending or {}).get('categoryName') or 'Unknown Category'}"
            )
        )
        meta.setObjectName("urlMeta")
        info.addWidget(meta)
        desc = _selectable(QLabel(channel.get("description", "") or "No description"))
        desc.setObjectName("smallLabel")
        desc.setWordWrap(True)
        info.addWidget(desc)
        row.addLayout(info, 1)
        channel_box.addLayout(row)

        # Stats
        self._clear_layout(self._stats_row)
        for label, value in (
            ("Subscribers", _fmt(channel.get("subscriberCount"))),
            ("Total Views", _fmt(channel.get("viewCount"))),
            ("Videos", _fmt(channel.get("videoCount"))),
            ("Viral Score", _fmt((trending or {}).get("viralScore"))),
        ):
            self._stats_row.addWidget(self._stat_tile(value, label))

        # Trending row
        self._clear_layout(self._trending_row)
        if trending:
            growth = trending.get("growthRate")
            growth_text = f"+{growth:.1f}% growth (30d)" if growth is not None else "— growth (30d)"
            growth = QLabel(growth_text)
            growth.setObjectName("growthPositive")
            self._trending_row.addWidget(growth)
            ratio = trending.get("viewSubRatio")
            ratio_text = f"{ratio:.1f}x View/Sub Ratio" if ratio is not None else "— View/Sub Ratio"
            ratio = QLabel(ratio_text)
            ratio.setObjectName("smallLabel")
            self._trending_row.addWidget(ratio)
            if trending.get("isNewlyCreated"):
                badge = QLabel("Newly Created")
                badge.setObjectName("badgeNew")
                self._trending_row.addWidget(badge)
        self._trending_row.addStretch(1)

        # Recent videos
        self._clear_layout(self._recent_grid)
        recent = data.get("recentVideos") or []
        self._recent_cap.setText(f"Recent Videos ({len(recent)})")
        self._recent_cap.setVisible(bool(recent))
        for video in recent[:8]:
            tile = QFrame()
            tile.setObjectName("panel")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(6, 6, 6, 6)
            tile_layout.setSpacing(4)
            thumb = w.VideoThumb(
                video.get("thumbnailUrl") or "", video.get("title") or video.get("videoId", "")
            )
            tile_layout.addWidget(thumb, 0, Qt.AlignmentFlag.AlignHCenter)
            title = _selectable(QLabel(video.get("title", "") or video.get("videoId", "")))
            title.setObjectName("smallLabel")
            title.setWordWrap(True)
            title.setFixedWidth(128)
            tile_layout.addWidget(title)
            meta = _selectable(
                QLabel(
                    f"{_fmt(video.get('viewCount'))} views"
                    + (f" · {video['publishedAt']}" if video.get("publishedAt") else "")
                )
            )
            meta.setObjectName("urlMeta")
            tile_layout.addWidget(meta)
            self._recent_grid.addWidget(tile)

        # Analysis section
        if data.get("analyzed"):
            self._render_analysis(data.get("analysis") or {})
            self._analysis_stack.setCurrentIndex(1)
        else:
            self._analyze_btn.setEnabled(True)
            self._analyze_btn.setText("Create Similar Channel")
            self._analysis_stack.setCurrentIndex(0)

    def _render_analysis(self, analysis: dict) -> None:
        self._render_strategy(analysis.get("strategy") or {})
        self._render_ideas(analysis.get("contentIdeas") or [])
        self._render_scripts(analysis.get("scripts") or [])
        self._render_blueprint(analysis.get("growthBlueprint") or {})
        if self._tab_buttons.get("ideas"):
            self._tab_buttons["ideas"].setText(
                f"Content Ideas ({len(analysis.get('contentIdeas') or [])})"
            )
            self._tab_buttons["scripts"].setText(f"Scripts ({len(analysis.get('scripts') or [])})")

    def _render_strategy(self, strategy: dict) -> None:
        self._clear_layout(self._strategy_layout)
        card = QFrame()
        card.setObjectName("svgCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        cap = QLabel("Content Strategy")
        cap.setObjectName("sectionLabel")
        layout.addWidget(cap)

        def row(label: str, value_widget: QWidget) -> None:
            box = QVBoxLayout()
            box.setSpacing(4)
            lab = QLabel(label)
            lab.setObjectName("svgMeta")
            box.addWidget(lab)
            box.addWidget(value_widget)
            layout.addLayout(box)

        def chips(values: list[str]) -> QWidget:
            wrap = QWidget()
            row_l = QHBoxLayout(wrap)
            row_l.setSpacing(6)
            for value in values:
                chip = QLabel(value)
                chip.setObjectName("chip")
                row_l.addWidget(chip)
            row_l.addStretch(1)
            return wrap

        row("Content Types", chips(strategy.get("contentType") or []))
        row("Posting Schedule", _selectable(QLabel(strategy.get("postingSchedule") or "")))
        row("Thumbnail Style", _selectable(QLabel(strategy.get("thumbnailStyle") or "")))
        row("Title Formula", _selectable(QLabel(strategy.get("titleFormula") or "")))
        row("Tag Strategy", chips(strategy.get("tagStrategy") or []))
        usps = strategy.get("uniqueSellingPoints") or []
        if usps:
            row("Unique Selling Points", _selectable(QLabel(" • ".join(usps))))
        layout.addStretch(1)
        self._strategy_layout.addWidget(card)

    def _render_ideas(self, ideas: list) -> None:
        self._clear_layout(self._ideas_layout)
        for idea in ideas:
            card = QFrame()
            card.setObjectName("svgCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(6)
            title = _selectable(QLabel(idea.get("title", "")))
            title.setObjectName("urlTitle")
            title.setWordWrap(True)
            layout.addWidget(title)
            desc = _selectable(QLabel(idea.get("description", "")))
            desc.setObjectName("smallLabel")
            desc.setWordWrap(True)
            layout.addWidget(desc)
            pills = QHBoxLayout()
            pills.setSpacing(6)
            for value, obj in (
                (idea.get("difficulty", "medium"), "chip"),
                (f"{idea.get('estimatedViews', 'medium')} views", "chip"),
                (idea.get("contentType", "video"), "chip"),
            ):
                pill = QLabel(str(value))
                pill.setObjectName(obj)
                pills.addWidget(pill)
            pills.addStretch(1)
            layout.addLayout(pills)
            self._ideas_layout.addWidget(card)
        self._ideas_layout.addStretch(1)

    def _render_scripts(self, scripts: list) -> None:
        self._clear_layout(self._scripts_layout)
        for script in scripts:
            card = QFrame()
            card.setObjectName("svgCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(8)
            head = QHBoxLayout()
            title = _selectable(QLabel(script.get("title", "")))
            title.setObjectName("urlTitle")
            head.addWidget(title, 1)
            dur = QLabel(self._fmt_duration(script.get("estimatedDuration", 600)))
            dur.setObjectName("chip")
            head.addWidget(dur)
            layout.addLayout(head)
            for section in ("hook", "intro", "outro"):
                layout.addLayout(
                    self._script_block(section.capitalize(), script.get(section, ""))
                )
            body = script.get("bodySections") or []
            if body:
                wrap = QWidget()
                body_box = QVBoxLayout(wrap)
                body_box.setContentsMargins(0, 0, 0, 0)
                body_box.setSpacing(4)
                cap = QLabel("Body")
                cap.setObjectName("svgMeta")
                body_box.addWidget(cap)
                for section in body:
                    paragraph = QLabel(str(section))
                    paragraph.setObjectName("svgBody")
                    paragraph.setWordWrap(True)
                    body_box.addWidget(paragraph)
                layout.addWidget(wrap)
            self._scripts_layout.addWidget(card)
        self._scripts_layout.addStretch(1)

    def _script_block(self, label: str, body: str) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        cap = QLabel(label)
        cap.setObjectName("svgMeta")
        box.addWidget(cap)
        text = _selectable(QLabel(body))
        text.setObjectName("svgBody")
        text.setWordWrap(True)
        box.addWidget(text)
        return box

    def _render_blueprint(self, blueprint: dict) -> None:
        self._clear_layout(self._blueprint_layout)
        for phase, label in (("30day", "30-Day"), ("60day", "60-Day"), ("90day", "90-Day")):
            plan = blueprint.get(phase) or {"goals": [], "actions": [], "metrics": []}
            card = QFrame()
            card.setObjectName("svgCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(6)
            cap = QLabel(label)
            cap.setObjectName("sectionLabel")
            layout.addWidget(cap)
            layout.addLayout(self._bullet_block("Goals", plan.get("goals") or []))
            layout.addLayout(self._bullet_block("Actions", plan.get("actions") or []))
            layout.addLayout(self._bullet_block("Metrics", plan.get("metrics") or []))
            layout.addStretch(1)
            self._blueprint_layout.addWidget(card, 1)

    def _bullet_block(self, label: str, items: list) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        cap = QLabel(label)
        cap.setObjectName("svgMeta")
        box.addWidget(cap)
        for item in items:
            text = _selectable(QLabel(f"•  {item}"))
            text.setObjectName("svgBody")
            text.setWordWrap(True)
            box.addWidget(text)
        return box

    def _stat_tile(self, value: str, label: str) -> QWidget:
        tile = QFrame()
        tile.setObjectName("svgCard")
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)
        val = QLabel(value)
        val.setObjectName("statTileValue")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(val)
        cap = QLabel(label)
        cap.setObjectName("statTileLabel")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(cap)
        return tile

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is None:
                # Spacers and other non-widget items are freed by takeAt.
                continue
            widget.setParent(None)
            widget.deleteLater()

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def _start_analyze(self) -> None:
        self._analyze_btn.setText("Analyzing...")
        self._analyze_btn.setEnabled(False)
        worker = AnalyzeWorker(self.channel_id, parent=self)
        self._track_worker(worker)
        worker.done.connect(self._on_analyze_done)
        worker.failed.connect(self._on_analyze_failed)
        worker.start()

    def _on_analyze_done(self, _analysis) -> None:
        self._analyze_btn.setEnabled(True)
        self._analyze_btn.setText("Create Similar Channel")
        self._load()

    def _on_analyze_failed(self, error: str) -> None:
        self._analyze_btn.setEnabled(True)
        self._analyze_btn.setText("Create Similar Channel")
        self._analysis_stack.setCurrentIndex(0)
        self._error_label.setText(f"Analysis failed: {error}")
        self._stack.setCurrentIndex(1)

    def _set_tab(self, tab: str) -> None:
        self._active_tab = tab
        for name, btn in self._tab_buttons.items():
            btn.setProperty("active", name == tab)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._tab_stack.setCurrentIndex(list(TABS).index(tab))

    def _set_style(self, style: str) -> None:
        self._thumb_style = style
        for name, btn in self._style_buttons.items():
            active = name == style
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _start_thumbnail(self) -> None:
        title = self._thumb_title.text().strip()
        if not title:
            return
        self._thumb_error.setText("")
        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("Generating...")
        niche = (
            (self._data.get("trending") or {}).get("categoryName")
            if hasattr(self, "_data")
            else None
        )
        worker = ThumbnailWorker(title, self._thumb_style, niche, parent=self)
        self._track_worker(worker)
        worker.done.connect(self._on_thumbnail_done)
        worker.failed.connect(self._on_thumbnail_failed)
        worker.start()

    def _on_thumbnail_done(self, result: dict) -> None:
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("Generate Thumbnail")
        if not result.get("success"):
            self._thumb_error.setText(str(result.get("error", "Failed to generate thumbnail")))
            return
        self._thumb_image = result["imageData"]
        self._show_preview(self._thumb_image)

    def _on_thumbnail_failed(self, error: str) -> None:
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("Generate Thumbnail")
        self._thumb_error.setText(error)

    def _show_preview(self, data_uri: str) -> None:
        import base64

        _, _, b64 = data_uri.partition(",")
        pixmap = QPixmap()
        pixmap.loadFromData(bytearray(base64.b64decode(b64)))
        self._preview.setPixmap(
            pixmap.scaled(
                400,
                260,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._download_btn.show()

    def _download_thumbnail(self) -> None:
        if not self._thumb_image:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save thumbnail", "thumbnail.png", "PNG Image (*.png)"
        )
        if not path:
            return
        import base64

        _, _, b64 = self._thumb_image.partition(",")
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(b64))

    @staticmethod
    def _fmt_duration(seconds: int) -> str:
        seconds = int(seconds or 0)
        minutes = seconds // 60
        return f"{minutes}:{seconds % 60:02d}"

    def closeEvent(self, event) -> None:
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(3000)
        super().closeEvent(event)
