"""PySide6 Desktop User Interface Tab for YouTube Discovery & Social Inspection Agent."""


from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.agent.orchestrator import AgentOrchestrator
from s_q_ali_media_downloader.agent.schema import (
    AgentSearchResult,
    ChannelMetadata,
    SocialStatus,
    TikTokSearchResult,
)
from s_q_ali_media_downloader.core.exporter import to_csv, write_export
from s_q_ali_media_downloader.theme import C
from s_q_ali_media_downloader.ui.activity_log import ActivityLog
from s_q_ali_media_downloader.ui.settings_page import discovery_browser_is_visible
from s_q_ali_media_downloader.ui.social_discovery_page import SocialDiscoveryPage

MODE_YOUTUBE = "YouTube → Socials (FB/IG/TikTok)"
MODE_TIKTOK = "TikTok → YouTube (Creators Without YT)"
MODE_SOCIAL = "🔎 Social Discovery (URL / @handle / name)"


class AgentWorkerThread(QThread):
    """Background worker thread for running AgentOrchestrator without blocking Qt main loop."""

    progress_updated = Signal(int, str)
    log = Signal(str)
    search_finished = Signal(object)
    search_failed = Signal(str)

    def __init__(
        self,
        query: str,
        max_channels: int,
        min_subs: int,
        check_fb: bool,
        check_ig: bool,
        check_tiktok: bool,
        only_no_socials: bool,
        only_no_youtube: bool,
        api_key: str,
        mode: str = MODE_YOUTUBE,
        cookiefile: str | None = None,
        show_browser: bool = True,
    ):
        super().__init__()
        self.query = query
        self.max_channels = max_channels
        self.min_subs = min_subs
        self.check_fb = check_fb
        self.check_ig = check_ig
        self.check_tiktok = check_tiktok
        self.only_no_socials = only_no_socials
        self.only_no_youtube = only_no_youtube
        self.api_key = api_key
        self.mode = mode
        self.cookiefile = cookiefile
        self.show_browser = show_browser

    def run(self):
        try:
            orchestrator = AgentOrchestrator(
                api_key=self.api_key,
                progress_callback=lambda pct, msg: self.progress_updated.emit(pct, msg),
                log_callback=self.log.emit,
                show_browser=self.show_browser,
            )
            if self.mode == MODE_TIKTOK:
                result = orchestrator.run_tiktok_discovery(
                    query=self.query,
                    max_profiles=self.max_channels,
                    only_no_youtube=self.only_no_youtube,
                    cookiefile=self.cookiefile,
                )
            else:
                result = orchestrator.run_discovery(
                    query=self.query,
                    max_channels=self.max_channels,
                    min_subscribers=self.min_subs,
                    check_facebook=self.check_fb,
                    check_instagram=self.check_ig,
                    check_tiktok=self.check_tiktok,
                    only_no_socials=self.only_no_socials,
                )
            self.search_finished.emit(result)
        except Exception as e:
            self.log.emit(f"Error: {e}")
            self.search_failed.emit(str(e))


class AgentTabWidget(QWidget):
    """Main UI view for AI Channel & Social Presence Discovery Agent."""

    send_to_queue_requested = Signal(list)
    _URL_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_result: AgentSearchResult = None
        self.worker: AgentWorkerThread = None
        self._init_ui()
        self.social_page.log.connect(self.activity.append_line)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 1. Top Controls Header Panel
        controls_frame = QFrame()
        controls_frame.setObjectName("AgentHeader")
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setSpacing(12)

        # Header Title
        lbl_title = QLabel("🤖 AI CHANNEL FINDER & SOCIAL PRESENCE INSPECTOR")
        lbl_title.setProperty("role", "pageTitle")
        controls_layout.addWidget(lbl_title)

        # Row 0: Discovery Mode
        row0 = QHBoxLayout()
        row0.setSpacing(10)
        lbl_mode = QLabel("Discovery Mode:")
        lbl_mode.setProperty("role", "hint")
        lbl_mode.setStyleSheet("font-weight: bold;")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([MODE_YOUTUBE, MODE_TIKTOK, MODE_SOCIAL])
        self.mode_combo.setMinimumHeight(34)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        row0.addWidget(lbl_mode)
        row0.addWidget(self.mode_combo, 1)
        controls_layout.addLayout(row0)

        # The search controls live in their own panel: the Social Discovery
        # mode has its own input, and the mode combo has to stay visible so
        # the user can switch back.
        self.search_panel = QWidget()
        search_layout = QVBoxLayout(self.search_panel)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(12)
        controls_layout.addWidget(self.search_panel)

        # Row 1: Query Input + Search Button
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(
            "Enter prompt (e.g. 'IShowSpeed content edits'), tag (#techreviews), or creator handle..."
        )
        self.query_edit.setMinimumHeight(40)
        self.query_edit.returnPressed.connect(self._start_agent)

        self.btn_search = QPushButton("🤖 Find && Verify Channels")
        self.btn_search.setProperty("kind", "primary")
        self.btn_search.setMinimumHeight(40)
        self.btn_search.setMinimumWidth(180)
        self.btn_search.clicked.connect(self._start_agent)

        row1.addWidget(self.query_edit, 4)
        row1.addWidget(self.btn_search, 1)
        search_layout.addLayout(row1)

        # The filters, the API key and the cookies file live behind a
        # disclosure. Seven controls in one row gave the panel a 1197px
        # minimum width - wider than a small laptop - so the whole window
        # could not be made smaller than that and everything else was
        # squeezed and clipped. Each group now has its own row, and the
        # whole thing starts closed.
        self.btn_options = QPushButton("⚙ Options")
        self.btn_options.setProperty("kind", "ghost")
        self.btn_options.setCheckable(True)
        self.btn_options.setToolTip(
            "Depth, the platform filters, the YouTube API key and the cookies file"
        )
        self.btn_options.toggled.connect(self._on_options_toggled)
        search_layout.addWidget(self.btn_options, 0, Qt.AlignLeft)

        self.options_panel = QWidget()
        options_layout = QVBoxLayout(self.options_panel)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(10)

        # Row 2a: how deep, and how big
        row2a = QHBoxLayout()
        row2a.setSpacing(16)

        # Depth
        lbl_depth = QLabel("Depth:")
        lbl_depth.setProperty("role", "hint")
        lbl_depth.setStyleSheet("font-weight: bold;")
        self.depth_combo = QComboBox()
        self.depth_combo.addItems(["20 channels", "50 channels", "100 channels"])
        self.depth_combo.setCurrentIndex(1)

        row2a.addWidget(lbl_depth)
        row2a.addWidget(self.depth_combo)

        # Min Subs
        self.lbl_subs = QLabel("Min Subs:")
        self.lbl_subs.setProperty("role", "hint")
        self.lbl_subs.setStyleSheet("font-weight: bold;")
        self.subs_combo = QComboBox()
        self.subs_combo.addItems(["Any", "5K+", "10K+", "50K+", "100K+"])
        self.subs_combo.setCurrentIndex(0)

        row2a.addWidget(self.lbl_subs)
        row2a.addWidget(self.subs_combo)
        row2a.addStretch()
        options_layout.addLayout(row2a)

        # Row 2b: the platforms to look for
        row2b = QHBoxLayout()
        row2b.setSpacing(16)

        # Checkboxes
        self.chk_fb = QCheckBox("Facebook Pages")
        self.chk_fb.setChecked(True)
        self.chk_ig = QCheckBox("Instagram Profiles")
        self.chk_ig.setChecked(True)
        self.chk_tiktok = QCheckBox("TikTok Profiles")
        self.chk_tiktok.setChecked(True)

        row2b.addWidget(self.chk_fb)
        row2b.addWidget(self.chk_ig)
        row2b.addWidget(self.chk_tiktok)
        row2b.addStretch()
        options_layout.addLayout(row2b)

        # Row 2c: who to look for
        row2c = QHBoxLayout()
        row2c.setSpacing(16)
        self.chk_no_socials = QCheckBox("Only Missing Social Pages (Targets)")
        self.chk_no_socials.setChecked(False)
        self.chk_no_youtube = QCheckBox("Only Creators WITHOUT YouTube (Targets)")
        self.chk_no_youtube.setChecked(True)

        row2c.addWidget(self.chk_no_socials)
        row2c.addWidget(self.chk_no_youtube)
        row2c.addStretch()
        options_layout.addLayout(row2c)

        # Row 3: Optional YouTube API Key
        row3 = QHBoxLayout()
        lbl_key = QLabel("YouTube API Key (Optional):")
        lbl_key.setProperty("role", "hint")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText(
            "Leave blank for 100% free zero-key scraper mode (yt-dlp)"
        )
        self.api_key_edit.setEchoMode(QLineEdit.PasswordEchoOnEdit)

        row3.addWidget(lbl_key)
        row3.addWidget(self.api_key_edit)
        options_layout.addLayout(row3)

        # Row 4: TikTok cookies file (optional, TikTok mode only)
        row4 = QHBoxLayout()
        lbl_cookies = QLabel("TikTok cookies.txt (Optional):")
        lbl_cookies.setProperty("role", "hint")
        self.cookies_edit = QLineEdit()
        self.cookies_edit.setPlaceholderText(
            "Paste @handles or profile URLs above, or load a cookies.txt to unlock #tag search"
        )
        self.btn_browse_cookies = QPushButton("Browse...")
        self.btn_browse_cookies.clicked.connect(self._browse_cookies)
        row4.addWidget(lbl_cookies)
        row4.addWidget(self.cookies_edit, 1)
        row4.addWidget(self.btn_browse_cookies)
        # YouTube mode is the default — cookies row only shows in TikTok mode.
        self.cookies_edit.setVisible(False)
        self.btn_browse_cookies.setVisible(False)
        options_layout.addLayout(row4)

        search_layout.addWidget(self.options_panel)
        # The options start closed: the default view is the mode, the query
        # and the results.
        self.options_panel.setVisible(False)

        main_layout.addWidget(controls_frame)

        # 2. Progress Banner & Status Label
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        self.lbl_status = QLabel("Ready to search channels and verify social presences.")
        self.lbl_status.setProperty("role", "hint")
        self.lbl_status.setStyleSheet("font-weight: 600;")

        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.lbl_status)

        # 2b. The activity log stays visible in every mode, so the steps of a
        # run that ends with no rows are not lost.
        self.activity = ActivityLog()
        main_layout.addWidget(self.activity)

        # 3. Results Table (QTableWidget) — columns adapt to the discovery mode
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self._setup_table_columns(MODE_YOUTUBE)
        self.table.cellClicked.connect(self._open_cell_url)
        self.table.cellDoubleClicked.connect(self._open_cell_url)

        # The table and the empty state share one slot: a table with no rows
        # is seven hundred pixels of nothing, which reads as a broken screen
        # rather than as "you have not searched yet".
        self.table_stack = QStackedWidget()
        self.table_stack.addWidget(self.table)
        self.empty_state = QLabel(
            "Nothing here yet.\n\n"
            "Type a prompt, a tag or a creator handle above and press "
            "Find & Verify Channels."
        )
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setWordWrap(True)
        self.table_stack.addWidget(self.empty_state)
        self.table_stack.setCurrentWidget(self.empty_state)

        main_layout.addWidget(self.table_stack, 1)

        # 3b. The Social Discovery page — its own mode, its own controls.
        self.social_page = SocialDiscoveryPage()
        self.social_page.setVisible(False)
        main_layout.addWidget(self.social_page, 1)

        # 4. Footer Actions Bar
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        self.btn_copy_fb = QPushButton("Copy FB Links")
        self.btn_copy_fb.clicked.connect(self._copy_fb_links)
        self.btn_copy_ig = QPushButton("Copy IG Links")
        self.btn_copy_ig.clicked.connect(self._copy_ig_links)
        self.btn_copy_tiktok = QPushButton("Copy TikTok Links")
        self.btn_copy_tiktok.clicked.connect(self._copy_tiktok_links)

        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_export_json = QPushButton("Export JSON")
        self.btn_export_json.clicked.connect(self._export_json)

        self.btn_send_queue = QPushButton("➔ Send Selected Videos to Queue")
        self.btn_send_queue.setProperty("kind", "primary")
        self.btn_send_queue.clicked.connect(self._send_selected_to_queue)

        footer_layout.addWidget(self.btn_copy_fb)
        footer_layout.addWidget(self.btn_copy_ig)
        footer_layout.addWidget(self.btn_copy_tiktok)
        footer_layout.addWidget(self.btn_export_csv)
        footer_layout.addWidget(self.btn_export_json)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_send_queue)

        main_layout.addLayout(footer_layout)

        # The footer's buttons are put away in the Social Discovery mode.
        self._footer_buttons = [
            self.btn_copy_fb,
            self.btn_copy_ig,
            self.btn_copy_tiktok,
            self.btn_export_csv,
            self.btn_export_json,
            self.btn_send_queue,
        ]

    def _on_options_toggled(self, open: bool):
        """Show or hide the advanced options."""
        self.options_panel.setVisible(open)
        self.btn_options.setText("▾ Options" if open else "⚙ Options")

    def _on_mode_changed(self, mode: str):
        if mode == MODE_SOCIAL:
            # Social Discovery has its own input, its own table and its own
            # export. Everything the other two modes use is put away.
            self.search_panel.setVisible(False)
            self.table_stack.setVisible(False)
            self.progress_bar.setVisible(False)
            self.lbl_status.setVisible(False)
            for button in self._footer_buttons:
                button.setVisible(False)
            self.social_page.setVisible(True)
            return

        self.social_page.setVisible(False)
        self.search_panel.setVisible(True)
        self.table_stack.setVisible(True)
        self.lbl_status.setVisible(True)
        for button in self._footer_buttons:
            button.setVisible(True)

        self._setup_table_columns(mode)
        is_tiktok_mode = mode == MODE_TIKTOK
        self.chk_no_socials.setVisible(not is_tiktok_mode)
        self.chk_no_youtube.setVisible(is_tiktok_mode)
        self.chk_fb.setVisible(not is_tiktok_mode)
        self.chk_ig.setVisible(not is_tiktok_mode)
        self.chk_tiktok.setVisible(not is_tiktok_mode)
        self.subs_combo.setVisible(not is_tiktok_mode)
        self.lbl_subs.setVisible(not is_tiktok_mode)
        self.cookies_edit.setVisible(is_tiktok_mode)
        self.btn_browse_cookies.setVisible(is_tiktok_mode)
        self.btn_copy_fb.setVisible(not is_tiktok_mode)
        self.btn_copy_ig.setVisible(not is_tiktok_mode)
        self.btn_copy_tiktok.setVisible(True)
        self.btn_send_queue.setText(
            "➔ Send Selected Profiles to Queue"
            if is_tiktok_mode
            else "➔ Send Selected Videos to Queue"
        )

    def _browse_cookies(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select TikTok cookies.txt", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.cookies_edit.setText(path)

    def _setup_table_columns(self, mode: str):
        if mode == MODE_TIKTOK:
            headers = [
                "Select",
                "Nickname",
                "Handle",
                "Followers",
                "YouTube Status",
                "YouTube Channel",
                "Flag",
                "Action",
            ]
            stretch_cols = [1, 4, 5]
        else:
            headers = [
                "Select",
                "Channel Name",
                "Handle",
                "Subscribers",
                "Facebook Page",
                "Instagram Profile",
                "TikTok Profile",
                "Flag",
                "Action",
            ]
            stretch_cols = [1, 4, 5, 6]

        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setDefaultSectionSize(34)
        for col, _ in enumerate(headers):
            self.table.horizontalHeader().setSectionResizeMode(
                col,
                QHeaderView.Stretch if col in stretch_cols else QHeaderView.ResizeToContents,
            )

    def _start_agent(self):
        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "Input Required", "Please enter a search prompt or tag!")
            return

        depth_map = {0: 20, 1: 50, 2: 100}
        subs_map = {0: 0, 1: 5000, 2: 10000, 3: 50000, 4: 100000}

        max_channels = depth_map.get(self.depth_combo.currentIndex(), 50)
        min_subs = subs_map.get(self.subs_combo.currentIndex(), 0)
        mode = self.mode_combo.currentText()

        self.btn_search.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Starting Agent...")

        self.worker = AgentWorkerThread(
            query=query,
            max_channels=max_channels,
            min_subs=min_subs,
            check_fb=self.chk_fb.isChecked(),
            check_ig=self.chk_ig.isChecked(),
            check_tiktok=self.chk_tiktok.isChecked(),
            only_no_socials=self.chk_no_socials.isChecked(),
            only_no_youtube=self.chk_no_youtube.isChecked(),
            api_key=self.api_key_edit.text().strip(),
            mode=mode,
            cookiefile=self.cookies_edit.text().strip() or None,
            show_browser=discovery_browser_is_visible(),
        )

        self.worker.progress_updated.connect(self._on_progress)
        self.worker.log.connect(self.activity.append_line)
        self.worker.search_finished.connect(self._on_finished)
        self.worker.search_failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(message)

    def _on_finished(self, result):
        self.search_result = result
        self.btn_search.setEnabled(True)
        self.progress_bar.setVisible(False)
        mode = self.mode_combo.currentText()
        self._setup_table_columns(mode)
        if isinstance(result, TikTokSearchResult):
            self._populate_tiktok_table(result.profiles)
        else:
            self._populate_table(result.channels)

    def _on_failed(self, error_msg: str):
        self.btn_search.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText(f"Error: {error_msg}")
        QMessageBox.critical(self, "Agent Error", f"Agent failed with error:\n{error_msg}")

    @staticmethod
    def _as_link_item(item, url, tooltip):
        if not url:
            return item
        item.setData(AgentTabWidget._URL_ROLE, url)
        item.setForeground(QColor(C["accent"]))
        font = item.font()
        font.setUnderline(True)
        item.setFont(font)
        item.setToolTip(tooltip)
        return item

    def _open_cell_url(self, row, col):
        item = self.table.item(row, col)
        if item is None:
            return
        url = item.data(self._URL_ROLE)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    @staticmethod
    def _status_item(status: SocialStatus, ok_label: str, unknown_label: str = "? Unconfirmed"):
        item = QTableWidgetItem()
        if status == SocialStatus.VERIFIED:
            item.setText(f"✓ {ok_label}")
            item.setForeground(QColor(C["done"]))
        elif status == SocialStatus.NOT_FOUND:
            item.setText("✗ Not Found")
            item.setForeground(QColor(C["failed"]))
        elif status == SocialStatus.INCONCLUSIVE:
            item.setText(unknown_label)
            item.setForeground(QColor(C["amber"]))
        else:  # UNVERIFIED_HANDLE
            item.setText("~ Unverified")
            item.setForeground(QColor(C["muted"]))
        return item

    def _populate_table(self, channels: list[ChannelMetadata]):
        self.table.setRowCount(0)
        for row_idx, ch in enumerate(channels):
            self.table.insertRow(row_idx)

            # Col 0: Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            self.table.setCellWidget(row_idx, 0, chk)

            # Col 1: Title
            title_item = QTableWidgetItem(ch.title)
            title_item.setData(Qt.UserRole, ch)
            self.table.setItem(row_idx, 1, title_item)
            self._as_link_item(title_item, ch.youtube_url, "Click to open the YouTube channel")

            # Col 2: Handle
            self.table.setItem(row_idx, 2, QTableWidgetItem(ch.handle or "N/A"))

            # Col 3: Subs
            self.table.setItem(row_idx, 3, QTableWidgetItem(ch.subscribers_formatted))

            # Col 4: Facebook Status Badge
            fb_item = self._status_item(ch.facebook.status, "Verified Page")
            fb_url = (
                ch.facebook.verified_url
                if ch.facebook.status == SocialStatus.VERIFIED
                else None
            )
            self.table.setItem(
                row_idx, 4, self._as_link_item(fb_item, fb_url, "Click to open the Facebook page")
            )

            # Col 5: Instagram Status Badge
            ig_item = self._status_item(ch.instagram.status, "Verified Profile")
            ig_url = (
                ch.instagram.verified_url
                if ch.instagram.status == SocialStatus.VERIFIED
                else None
            )
            self.table.setItem(
                row_idx,
                5,
                self._as_link_item(ig_item, ig_url, "Click to open the Instagram profile"),
            )

            # Col 6: TikTok Status Badge
            tt_item = self._status_item(ch.tiktok.status, "Verified Profile")
            tt_url = (
                ch.tiktok.verified_url if ch.tiktok.status == SocialStatus.VERIFIED else None
            )
            self.table.setItem(
                row_idx, 6, self._as_link_item(tt_item, tt_url, "Click to open the TikTok profile")
            )

            # Col 7: Opportunity flag
            flag_item = QTableWidgetItem(ch.opportunity_flag)
            if ch.opportunity_flag == "TARGET_NO_SOCIALS":
                flag_item.setForeground(QColor(C["failed"]))
            elif ch.opportunity_flag == "PARTIAL_SOCIALS":
                flag_item.setForeground(QColor(C["amber"]))
            else:
                flag_item.setForeground(QColor(C["done"]))
            self.table.setItem(row_idx, 7, flag_item)

            # Col 8: Action Button
            btn_queue = QPushButton("➔ Queue")
            btn_queue.clicked.connect(lambda _, c=ch: self._send_single_channel_to_queue(c))
            self.table.setCellWidget(row_idx, 8, btn_queue)

        self.table_stack.setCurrentWidget(self.table if channels else self.empty_state)

    def _populate_tiktok_table(self, profiles):
        self.table.setRowCount(0)
        for row_idx, profile in enumerate(profiles):
            self.table.insertRow(row_idx)

            # Col 0: Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            self.table.setCellWidget(row_idx, 0, chk)

            # Col 1: Nickname
            title_item = QTableWidgetItem(profile.nickname)
            title_item.setData(Qt.UserRole, profile)
            self.table.setItem(row_idx, 1, title_item)
            self._as_link_item(title_item, profile.profile_url, "Click to open the TikTok profile")

            # Col 2: Handle
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"@{profile.handle}"))

            # Col 3: Followers
            self.table.setItem(row_idx, 3, QTableWidgetItem(profile.followers_formatted))

            # Col 4: YouTube status badge
            yt_item = self._status_item(profile.youtube.status, "Has Channel")
            yt_url = (
                profile.youtube.verified_url
                if profile.youtube.status == SocialStatus.VERIFIED
                else None
            )
            self.table.setItem(
                row_idx,
                4,
                self._as_link_item(yt_item, yt_url, "Click to open the YouTube channel"),
            )

            # Col 5: YouTube channel URL (if any)
            yt_link = QTableWidgetItem(profile.youtube.verified_url or "—")
            self.table.setItem(row_idx, 5, yt_link)
            self._as_link_item(
                yt_link, profile.youtube.verified_url, "Click to open the YouTube channel"
            )

            # Col 6: Flag
            flag_item = QTableWidgetItem(profile.opportunity_flag)
            if profile.opportunity_flag == "TARGET_NO_YOUTUBE":
                flag_item.setForeground(QColor(C["failed"]))
            elif profile.opportunity_flag == "NEEDS_REVIEW":
                flag_item.setForeground(QColor(C["amber"]))
            else:
                flag_item.setForeground(QColor(C["done"]))
            self.table.setItem(row_idx, 6, flag_item)

            # Col 7: Action Button — queue the TikTok profile itself
            btn_queue = QPushButton("➔ Queue")
            btn_queue.clicked.connect(lambda _, p=profile: self._send_single_profile_to_queue(p))
            self.table.setCellWidget(row_idx, 7, btn_queue)

    def _send_single_channel_to_queue(self, ch: ChannelMetadata):
        target_url = ch.latest_video_url or ch.youtube_url
        self.send_to_queue_requested.emit([target_url])

    def _send_single_profile_to_queue(self, profile):
        self.send_to_queue_requested.emit([profile.profile_url])

    def _send_selected_to_queue(self):
        selected_urls = []
        is_tiktok_mode = self.mode_combo.currentText() == MODE_TIKTOK
        for row in range(self.table.rowCount()):
            chk = self.table.cellWidget(row, 0)
            if chk and chk.isChecked():
                title_item = self.table.item(row, 1)
                obj = title_item.data(Qt.UserRole)
                if is_tiktok_mode:
                    selected_urls.append(obj.profile_url)
                else:
                    selected_urls.append(obj.latest_video_url or obj.youtube_url)

        if selected_urls:
            self.send_to_queue_requested.emit(selected_urls)
            self.lbl_status.setText(f"Sent {len(selected_urls)} URLs to the download queue.")
        else:
            QMessageBox.warning(self, "No Selection", "Please select at least one entry!")

    def _copy_fb_links(self):
        links = []
        if self.search_result:
            for ch in self.search_result.channels:
                if ch.facebook.status == SocialStatus.VERIFIED and ch.facebook.verified_url:
                    links.append(ch.facebook.verified_url)
        if links:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText("\n".join(links))
            self.lbl_status.setText(f"Copied {len(links)} Facebook page link{'s' if len(links) != 1 else ''}.")
        else:
            self.lbl_status.setText("No verified Facebook page links to copy.")

    def _copy_ig_links(self):
        links = []
        if self.search_result:
            for ch in self.search_result.channels:
                if ch.instagram.status == SocialStatus.VERIFIED and ch.instagram.verified_url:
                    links.append(ch.instagram.verified_url)
        if links:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText("\n".join(links))
            self.lbl_status.setText(
                f"Copied {len(links)} Instagram profile link{'s' if len(links) != 1 else ''}."
            )
        else:
            self.lbl_status.setText("No verified Instagram profile links to copy.")

    def _copy_tiktok_links(self):
        links = []
        if isinstance(self.search_result, TikTokSearchResult):
            for profile in self.search_result.profiles:
                links.append(profile.profile_url)
        elif self.search_result:
            for ch in self.search_result.channels:
                if ch.tiktok.status == SocialStatus.VERIFIED and ch.tiktok.verified_url:
                    links.append(ch.tiktok.verified_url)
        if links:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText("\n".join(links))
            self.lbl_status.setText(
                f"Copied {len(links)} TikTok profile link{'s' if len(links) != 1 else ''}."
            )
        else:
            self.lbl_status.setText("No TikTok profile links to copy.")

    def _export_csv(self):
        if not self.search_result:
            return
        is_tiktok_mode = isinstance(self.search_result, TikTokSearchResult)
        if is_tiktok_mode and not self.search_result.profiles:
            return
        if not is_tiktok_mode and not self.search_result.channels:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Agent Results CSV", "channels_social_export.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        # The exporter is the one that writes CSV: it neutralises a cell
        # that starts with a formula, and the channel titles come from
        # YouTube. A spreadsheet would otherwise run them.
        if is_tiktok_mode:
            columns = [
                "Nickname",
                "Handle",
                "Followers",
                "TikTok URL",
                "YouTube Status",
                "YouTube URL",
                "Flag",
            ]
            rows = [
                {
                    "Nickname": profile.nickname,
                    "Handle": f"@{profile.handle}",
                    "Followers": profile.followers_formatted,
                    "TikTok URL": profile.profile_url,
                    "YouTube Status": profile.youtube.status.value,
                    "YouTube URL": profile.youtube.verified_url or "",
                    "Flag": profile.opportunity_flag,
                }
                for profile in self.search_result.profiles
            ]
        else:
            columns = [
                "Channel Title",
                "Handle",
                "Subscribers",
                "YouTube URL",
                "Facebook Status",
                "Facebook URL",
                "Instagram Status",
                "Instagram URL",
                "TikTok Status",
                "TikTok URL",
                "Has No Social Pages",
                "Flag",
            ]
            rows = [
                {
                    "Channel Title": ch.title,
                    "Handle": ch.handle,
                    "Subscribers": ch.subscribers_formatted,
                    "YouTube URL": ch.youtube_url,
                    "Facebook Status": ch.facebook.status.value,
                    "Facebook URL": ch.facebook.verified_url or "",
                    "Instagram Status": ch.instagram.status.value,
                    "Instagram URL": ch.instagram.verified_url or "",
                    "TikTok Status": ch.tiktok.status.value,
                    "TikTok URL": ch.tiktok.verified_url or "",
                    "Has No Social Pages": "YES" if ch.has_no_socials else "NO",
                    "Flag": ch.opportunity_flag,
                }
                for ch in self.search_result.channels
            ]
        write_export(path, to_csv(rows, columns))
        self.lbl_status.setText(f"Saved {len(rows)} rows to {path}")

    def _export_json(self):
        if not self.search_result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Agent Results JSON", "channels_social_export.json", "JSON Files (*.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.search_result.model_dump_json(indent=2))
            self.lbl_status.setText(f"Saved JSON results to {path}")
