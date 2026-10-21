"""Main window for S-Q Creator Studio."""

import json
import os
import sys

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFontMetrics
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader import __version__
from s_q_ali_media_downloader.engine import (
    ACCOUNT_LIMITS,
    APP_NAME,
    APP_TITLE,
    INLINE_RETRIES,
    MAX_ACCOUNT_VIDEOS,
    PARALLEL_OPTIONS,
    RETRY_PASSES,
    AccountFetchThread,
    DownloadThread,
    YouTubeFetchThread,
    default_output_dir,
    impersonation_summary,
    is_profile_url,
    is_tiktok_url,
    is_youtube_channel_url,
    is_youtube_playlist_url,
    is_youtube_url,
    normalize_youtube_channel_url,
    platform_of,
)
from s_q_ali_media_downloader.theme import STATUS_COLORS, C
from s_q_ali_media_downloader.ui.agent_tab import AgentTabWidget
from s_q_ali_media_downloader.ui.settings_page import SettingsPage
from s_q_ali_media_downloader.ui.widgets import Chip, Job, JobCard, shield_pixmap

ORG = "S-Q-Ali"
VERSION = __version__

NOTICE = "Use only for content you own or have permission to download."
INLINE_RETRY_WAIT_TEXT = "2-5s"
MAX_SAVED_QUEUE = 500

SOCIALS = [
    ("GitHub", "GH", "#24292F", "https://github.com/S-Q-Ali"),
    ("LinkedIn", "in", "#0A66C2", "https://linkedin.com/in/s-qasim-ali"),
]


def resource(name):
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for root in (here, os.path.join(here, "resources")):
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate):
                return candidate
        base = here
    return os.path.join(base, name)


def storage_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME, "storage")


def queue_file():
    return os.path.join(storage_dir(), "queue.json")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE}  ·  {VERSION}")
        self.resize(1240, 840)
        self.setMinimumSize(1060, 720)

        self.settings = QSettings(ORG, APP_NAME)
        self.jobs = []
        self.cards = {}
        self.thread = None
        self.fetcher = None
        self.expander = None
        self._expand_queue = []
        self.active_uids = set()
        self.autoscroll = True

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # The settings page owns every setting of the app. It is built first
        # because the rail shows where the downloads land, and that is one
        # of the settings.
        self.settings_page = SettingsPage()
        self.settings_page.density_changed.connect(self._apply_density)
        self.settings_page.folder_edit.textChanged.connect(self._update_folder_label)

        # The window keeps the old attribute names for the download
        # preferences, so the rest of the code does not have to know where
        # they live.
        self.folder_edit = self.settings_page.folder_edit
        self.quality = self.settings_page.quality
        self.pace = self.settings_page.pace
        self.parallel = self.settings_page.parallel
        self.passes = self.settings_page.passes
        self.cookies = self.settings_page.cookies

        self.rail = self._build_rail()
        layout.addWidget(self.rail)
        layout.addWidget(self._build_workspace(), 1)

        self._restore_settings()
        self._update_folder_label()
        restored = self._load_queue()
        self._sync_buttons()
        self._update_stats()

        ok, label = impersonation_summary()
        if not ok:
            self.set_status(
                f"Warning · browser impersonation {label}. Expect heavy failures until curl_cffi is installed."
            )
            return

        if restored:
            self.set_status(
                f"Restored {restored} item"
                + ("s" if restored != 1 else "")
                + f" from your last session · impersonating {label}."
            )
            return

        self.set_status(f"Ready · impersonating {label}.")

    def _build_rail(self):
        rail = QFrame()
        rail.setObjectName("Rail")
        rail.setFixedWidth(344)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setSpacing(12)
        stripe = QFrame()
        stripe.setObjectName("RailStripe")
        stripe.setFixedSize(4, 40)
        head.addWidget(stripe)
        names = QVBoxLayout()
        names.setSpacing(2)
        mark = QLabel("S-Q-Ali")
        mark.setObjectName("Wordmark")
        sub = QLabel("CREATOR STUDIO")
        sub.setObjectName("WordmarkSub")
        names.addWidget(mark)
        names.addWidget(sub)
        head.addLayout(names)
        head.addStretch(1)
        lay.addLayout(head)
        lay.addSpacing(20)

        lay.addSpacing(14)

        lay.addLayout(self._build_source_tabs())
        lay.addSpacing(8)
        lay.addWidget(self._build_source_stack(), 1)
        lay.addSpacing(10)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        add = QPushButton("Add to queue")
        add.setProperty("kind", "primary")
        add.clicked.connect(self.add_links)
        clear_box = QPushButton("Clear box")
        clear_box.clicked.connect(self.links.clear)
        row2.addWidget(add, 1)
        row2.addWidget(clear_box)
        lay.addLayout(row2)
        lay.addSpacing(8)

        # Where the downloads land. One line, and it opens the folder - the
        # rest of the download settings live in the Settings page, where
        # there is room to edit them. A long path is shortened to fit
        # rather than cut off: the whole path stays in the tooltip.
        self.folder_label = QLabel("")
        self.folder_label.setProperty("role", "hint")
        self.folder_label.setToolTip("Click to open the download folder")
        self.folder_label.setCursor(Qt.PointingHandCursor)
        self.folder_label.mousePressEvent = lambda _event: self.open_folder()
        lay.addWidget(self.folder_label)
        lay.addSpacing(8)

        hint = QLabel(
            f"{1 + INLINE_RETRIES} tries per video, {INLINE_RETRY_WAIT_TEXT} apart, "
            "then it moves on as Waiting."
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addSpacing(10)

        lay.addLayout(self._build_social_buttons())

        return rail

    def _build_source_tabs(self):
        row = QHBoxLayout()
        row.setSpacing(6)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)

        self.tab_links = QPushButton("Paste links")
        self.tab_account = QPushButton("Account based")

        for index, button in enumerate((self.tab_links, self.tab_account)):
            button.setCheckable(True)
            button.setProperty("kind", "tab")
            button.setCursor(Qt.PointingHandCursor)
            self.tab_group.addButton(button, index)
            row.addWidget(button, 1)

        self.tab_links.setChecked(True)
        self.tab_group.idClicked.connect(self._switch_source)
        return row

    def _build_source_stack(self):
        self.source_stack = QStackedWidget()

        page_links = QWidget()
        pl = QVBoxLayout(page_links)
        pl.setContentsMargins(0, 0, 0, 0)
        self.links = QPlainTextEdit()
        self.links.setMinimumHeight(120)
        self.links.setPlaceholderText(
            "One TikTok or YouTube link per line.\n\n"
            "Playlists, channels and TikTok profiles expand into videos automatically."
        )
        pl.addWidget(self.links)
        self.chk_shorts = QCheckBox("Also fetch Shorts")
        self.chk_shorts.setChecked(True)
        self.chk_shorts.setToolTip(
            "A YouTube channel's Shorts live in their own tab. Turn this off to "
            "fetch only the long videos."
        )
        pl.addWidget(self.chk_shorts)
        self.source_stack.addWidget(page_links)

        page_account = QWidget()
        pa = QVBoxLayout(page_account)
        pa.setContentsMargins(0, 0, 0, 0)
        pa.setSpacing(6)

        pa.addWidget(self._section("ACCOUNT"))
        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText("@username  or  profile link")
        self.account_edit.returnPressed.connect(self.fetch_account)
        pa.addWidget(self.account_edit)
        pa.addSpacing(8)

        pair = QHBoxLayout()
        pair.setSpacing(10)

        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(self._section("MAX VIDEOS"))
        self.account_limit = QComboBox()
        self.account_limit.addItems(str(n) for n in ACCOUNT_LIMITS)
        self.account_limit.setCurrentText(str(MAX_ACCOUNT_VIDEOS))
        col.addWidget(self.account_limit)
        pair.addLayout(col, 1)

        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(QLabel(" "))
        self.btn_fetch = QPushButton("Get URLs")
        self.btn_fetch.setProperty("kind", "primary")
        self.btn_fetch.clicked.connect(self.fetch_account)
        col.addWidget(self.btn_fetch)
        pair.addLayout(col, 1)

        pa.addLayout(pair)
        pa.addSpacing(10)

        note = QLabel(
            "Fetches the newest videos from a public account and drops them into Paste links, "
            "where you can check them before adding to the queue."
        )
        note.setProperty("role", "hint")
        note.setWordWrap(True)
        pa.addWidget(note)
        pa.addStretch(1)

        self.source_stack.addWidget(page_account)
        return self.source_stack

    def _handle_agent_urls(self, urls: list):
        if not urls:
            return
        lines = "\n".join(urls)
        current = self.links.toPlainText().strip()
        if current:
            self.links.setPlainText(current + "\n" + lines)
        else:
            self.links.setPlainText(lines)
        self.tab_links.setChecked(True)
        self.source_stack.setCurrentIndex(0)
        self.add_links()
        if hasattr(self, "btn_nav_queue"):
            self.btn_nav_queue.setChecked(True)
        if hasattr(self, "workspace_stack"):
            self.workspace_stack.setCurrentIndex(0)

    def _switch_source(self, index):
        self.source_stack.setCurrentIndex(index)

    def _section(self, text):
        label = QLabel(text)
        label.setProperty("role", "section")
        return label

    def _build_workspace(self):
        work = QWidget()
        lay = QVBoxLayout(work)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Workspace Navigation Header
        nav_bar_frame = QFrame()
        # The frame is styled through the app stylesheet by its object name.
        # A stylesheet set on the frame itself would cascade to the buttons
        # and override their checked state - which is how the active tab
        # ended up with dark text on a dark background.
        nav_bar_frame.setObjectName("NavBar")
        nav_lay = QHBoxLayout(nav_bar_frame)
        nav_lay.setContentsMargins(24, 8, 24, 8)
        nav_lay.setSpacing(12)

        self.work_tab_group = QButtonGroup(self)
        self.work_tab_group.setExclusive(True)

        self.btn_toggle_rail = QPushButton("☰")
        self.btn_toggle_rail.setProperty("kind", "tab")
        self.btn_toggle_rail.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_rail.setMinimumHeight(34)
        self.btn_toggle_rail.setToolTip("Collapse / expand the left panel")
        self.btn_toggle_rail.clicked.connect(self.toggle_rail)
        nav_lay.addWidget(self.btn_toggle_rail)

        self.btn_nav_queue = QPushButton("📥 Download Queue")
        self.btn_nav_agent = QPushButton("🤖 AI Channel Finder & Social Inspector")
        self.btn_nav_settings = QPushButton("⚙️ Settings")

        for idx, btn in enumerate(
            (self.btn_nav_queue, self.btn_nav_agent, self.btn_nav_settings)
        ):
            btn.setCheckable(True)
            btn.setProperty("kind", "tab")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(34)
            self.work_tab_group.addButton(btn, idx)
            nav_lay.addWidget(btn)

        self.btn_nav_queue.setChecked(True)
        nav_lay.addStretch(1)
        lay.addWidget(nav_bar_frame)

        # Workspace Stack
        self.workspace_stack = QStackedWidget()
        self.work_tab_group.idClicked.connect(self.workspace_stack.setCurrentIndex)

        # Page 0: Queue Workspace Page
        page_queue = QWidget()
        pql = QVBoxLayout(page_queue)
        pql.setContentsMargins(0, 0, 0, 0)
        pql.setSpacing(0)

        header = QFrame()
        header.setObjectName("WorkHeader")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(24, 14, 24, 14)
        hl.setSpacing(14)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        self.chip_total = Chip("in queue", C["text"])
        self.chip_done = Chip("completed", C["done"])
        self.chip_wait = Chip("waiting", C["waiting"])
        self.chip_failed = Chip("failed", C["failed"])
        self.chip_left = Chip("remaining", C["amber"])
        for chip in (
            self.chip_total,
            self.chip_done,
            self.chip_wait,
            self.chip_failed,
            self.chip_left,
        ):
            chips.addWidget(chip)
        chips.addStretch(1)

        self.select_all = QCheckBox("Select all")
        self.select_all.stateChanged.connect(self.toggle_select_all)
        chips.addWidget(self.select_all, 0, Qt.AlignVCenter)
        hl.addLayout(chips)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_start = QPushButton("Start")
        self.btn_start.setProperty("kind", "primary")
        self.btn_start.clicked.connect(self.start_run)
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.clicked.connect(self.pause_run)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self.stop_run)
        self.btn_retry = QPushButton("Retry failed")
        self.btn_retry.clicked.connect(self.retry_failed)
        for b in (self.btn_start, self.btn_pause, self.btn_stop, self.btn_retry):
            bar.addWidget(b)

        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background: {C['border']};")
        bar.addSpacing(6)
        bar.addWidget(divider)
        bar.addSpacing(6)

        # The four "remove" actions used to sit between the run controls
        # and the empty-queue button. They are shorter now, so the header
        # is one row of controls and not a wall.
        for text, handler in (
            ("Selected", self.clear_selected),
            ("Done", self.clear_completed),
            ("Failed", self.clear_failed),
            ("Waiting", self.clear_remaining),
        ):
            btn = QPushButton(text)
            btn.setProperty("kind", "ghost")
            btn.setToolTip(f"Remove {text.lower()} from the queue")
            btn.clicked.connect(handler)
            bar.addWidget(btn)

        bar.addStretch(1)
        clear_all = QPushButton("Empty queue")
        clear_all.setProperty("kind", "danger")
        clear_all.clicked.connect(self.clear_all)
        bar.addWidget(clear_all)
        hl.addLayout(bar)

        pql.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        host = QWidget()
        host.setObjectName("QueueHost")
        self.queue_layout = QVBoxLayout(host)
        self.queue_layout.setContentsMargins(24, 18, 24, 24)
        self.queue_layout.setSpacing(9)

        self.empty = QLabel(
            "Nothing queued yet. Paste TikTok links on the left, or fetch them from an account."
        )
        self.empty.setObjectName("EmptyState")
        self.empty.setAlignment(Qt.AlignCenter)
        self.queue_layout.addWidget(self.empty)
        self.queue_layout.addStretch(1)

        self.scroll.setWidget(host)
        pql.addWidget(self.scroll, 1)

        self.workspace_stack.addWidget(page_queue)

        # Page 1: AI Agent Container Workspace Page
        self.agent_tab = AgentTabWidget()
        self.agent_tab.send_to_queue_requested.connect(self._handle_agent_urls)
        self.workspace_stack.addWidget(self.agent_tab)

        # Page 2: Settings
        self.workspace_stack.addWidget(self.settings_page)

        lay.addWidget(self.workspace_stack, 1)

        lay.addWidget(self._build_bottom_bar())

        return work

    def toggle_rail(self):
        self.rail.setVisible(not self.rail.isVisible())

    def _build_bottom_bar(self):
        """One bar for the status, the notice and the social buttons.

        They used to be three separate rows: the notice, the status line and
        the footer. On a 720px screen those three rows ate a tenth of the
        height for no reason, so they share one row now.
        """
        frame = QFrame()
        frame.setObjectName("StatusBar")
        fl = QHBoxLayout(frame)
        fl.setContentsMargins(24, 5, 24, 5)
        fl.setSpacing(9)

        self.status_bar = QLabel("Ready.")
        self.status_bar.setProperty("role", "statusText")
        fl.addWidget(self.status_bar, 1)

        badge = QLabel()
        badge.setPixmap(shield_pixmap())
        badge.setStyleSheet("background: transparent;")
        fl.addWidget(badge, 0, Qt.AlignVCenter)
        text = QLabel(NOTICE)
        text.setProperty("role", "notice")
        fl.addWidget(text, 0, Qt.AlignVCenter)

        return frame

    def _build_social_buttons(self):
        """The GitHub and LinkedIn buttons, small, in the rail's footer."""
        row = QHBoxLayout()
        row.setSpacing(6)
        for label, glyph, colour, url in SOCIALS:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(url)
            btn.setMinimumHeight(28)
            hover = QColor(colour).lighter(118).name()
            pressed = QColor(colour).darker(112).name()
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {colour};
                    border: none;
                    border-radius: 14px;
                    padding: 4px 12px;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background: {hover}; }}
                QPushButton:pressed {{ background: {pressed}; }}
            """)
            btn.clicked.connect(lambda checked=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            row.addWidget(btn)
        row.addStretch(1)
        return row

    def _restore_settings(self):
        """Read every setting into the Settings page."""
        self.settings_page.load()
        self._apply_density()

    def _save_settings(self):
        """Write the download preferences back."""
        self.settings_page.save()

    def _update_folder_label(self):
        """Show where the downloads land, and keep it in step with the setting.

        The path is shortened to what the rail has room for. A plain label
        would cut it in the middle of a word, and a long path used to spill
        past the rail.
        """
        folder = self.output_dir()
        text = f"Saving to {folder}" if folder else "No folder chosen"
        self.folder_label.setToolTip(text)
        metrics = QFontMetrics(self.folder_label.font())
        room = max(60, self.rail.width() - 44)
        self.folder_label.setText(metrics.elidedText(text, Qt.ElideMiddle, room))

    def _apply_density(self):
        """Pick the layout density and tell the widgets about it."""
        from s_q_ali_media_downloader.theme import apply_density

        apply_density(self, self.settings_page.compact_check.isChecked())
        self._update_folder_label()

    def _save_queue(self):
        try:
            os.makedirs(storage_dir(), exist_ok=True)
            items = []
            for job in self.jobs[:MAX_SAVED_QUEUE]:
                status = job.status
                if status in ("Downloading", "Retrying", "Paused"):
                    status = "Queued"
                items.append(
                    {
                        "url": job.url,
                        "title": job.title,
                        "status": status,
                        "size": job.size,
                        "error": job.error,
                    }
                )
            with open(queue_file(), "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "items": items}, handle)
        except (OSError, TypeError, ValueError):
            pass

    def _load_queue(self):
        try:
            with open(queue_file(), "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return 0

        restored = 0
        seen = set()
        for entry in (data.get("items") or [])[:MAX_SAVED_QUEUE]:
            url = (entry or {}).get("url", "")
            if not (platform_of(url) and url not in seen):
                continue
            seen.add(url)
            job = Job(url)
            job.title = (entry or {}).get("title", "") or ""
            status = (entry or {}).get("status", "Queued")
            job.status = status if status in STATUS_COLORS else "Queued"
            job.size = (entry or {}).get("size", "—") or "—"
            job.error = (entry or {}).get("error", "") or ""
            job.percent = 100.0 if job.status == "Completed" else 0.0
            self._add_job(job)
            restored += 1
        return restored

    def set_status(self, text):
        self.status_bar.setText(text)

    def output_dir(self):
        return self.folder_edit.text().strip() or default_output_dir()

    def running(self):
        return self.thread is not None and self.thread.isRunning()

    def fetching(self):
        return self.fetcher is not None and self.fetcher.isRunning()

    def _sync_buttons(self):
        running = self.running()
        paused = running and self.thread.is_paused()

        self.btn_start.setEnabled(not running or paused)
        self.btn_start.setText("Resume" if paused else "Start")

        self.btn_pause.setEnabled(running and not paused)
        self.btn_stop.setEnabled(running)
        self.btn_retry.setEnabled(
            not running and any(j.status in ("Failed", "Waiting") for j in self.jobs)
        )

        self.btn_fetch.setEnabled(not self.fetching())

        for widget in (
            self.quality,
            self.pace,
            self.passes,
            self.parallel,
            self.folder_edit,
            self.cookies,
        ):
            widget.setEnabled(not running)

    def _update_stats(self):
        done = sum(1 for j in self.jobs if j.status == "Completed")
        failed = sum(1 for j in self.jobs if j.status == "Failed")
        waiting = sum(1 for j in self.jobs if j.status == "Waiting")
        left = sum(
            1 for j in self.jobs if j.status in ("Queued", "Downloading", "Retrying", "Paused")
        )

        self.chip_total.set(len(self.jobs))
        self.chip_done.set(done)
        self.chip_wait.set(waiting)
        self.chip_failed.set(failed)
        self.chip_left.set(left)

        self.empty.setVisible(not self.jobs)

    def choose_folder(self):
        """Ask for a download folder. The Settings page owns the widgets."""
        self.settings_page.choose_folder()
        self._save_settings()
        self._update_folder_label()

    def open_folder(self):
        """Open the download folder."""
        self.settings_page.open_folder()

    def fetch_account(self):
        if self.fetching():
            return
        text = self.account_edit.text().strip()
        if not text:
            self.set_status("Type a username or paste a profile link first.")
            return
        limit = int(self.account_limit.currentText())
        # YouTube channel / playlist URL — expand into individual video URLs
        if is_youtube_channel_url(text) or is_youtube_playlist_url(text):
            normalized = normalize_youtube_channel_url(text)
            self.fetcher = YouTubeFetchThread(
                normalized, limit, self, include_shorts=self.chk_shorts.isChecked()
            )
            self.fetcher.note.connect(self.set_status)
            self.fetcher.found.connect(self.on_youtube_channel_fetched)
            self.fetcher.failed.connect(self.on_account_failed)
            self.fetcher.finished.connect(self._sync_buttons)
            self.fetcher.start()
            self.btn_fetch.setEnabled(False)
            self.set_status(f"Fetching up to {limit} video URLs from YouTube channel…")
            return
        # TikTok / other profile-based account
        self.fetcher = AccountFetchThread(text, limit, self.cookies.isChecked(), self)
        self.fetcher.note.connect(self.set_status)
        self.fetcher.found.connect(self.on_account_found)
        self.fetcher.failed.connect(self.on_account_failed)
        self.fetcher.finished.connect(self._sync_buttons)
        self.fetcher.start()
        self.btn_fetch.setEnabled(False)
        self.set_status("Fetching video list…")

    def on_account_found(self, urls, username):
        existing = self.links.toPlainText().strip()
        block = "\n".join(urls)
        self.links.setPlainText(f"{existing}\n{block}" if existing else block)
        self.tab_links.setChecked(True)
        self.source_stack.setCurrentIndex(0)
        n = len(urls)
        self.set_status(
            f"Found {n} video{'s' if n != 1 else ''} from @{username}. "
            "Check the list, then Add to queue."
        )

    def on_youtube_channel_fetched(self, urls, label):
        """Receives individual video URLs from a YouTube channel/playlist fetch and shows them in Paste Links."""
        existing = self.links.toPlainText().strip()
        block = "\n".join(urls)
        self.links.setPlainText(f"{existing}\n{block}" if existing else block)
        self.tab_links.setChecked(True)
        self.source_stack.setCurrentIndex(0)
        n = len(urls)
        self.set_status(
            f"Found {n} video{'s' if n != 1 else ''} from {label}. "
            "Check the list, then Add to queue."
        )

    def on_account_failed(self, message):
        self.set_status(f"Couldn't fetch that account — {message}")

    def add_links(self):
        existing = {j.url for j in self.jobs}
        added = skipped = duplicates = 0
        expand_links = []
        for line in self.links.toPlainText().splitlines():
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            if is_youtube_playlist_url(url) or is_youtube_channel_url(url):
                url = normalize_youtube_channel_url(url)
                if url in existing:
                    duplicates += 1
                    continue
                existing.add(url)
                expand_links.append(url)
                continue
            if is_profile_url(url):
                if url in existing:
                    duplicates += 1
                    continue
                existing.add(url)
                expand_links.append(url)
                continue
            if is_tiktok_url(url) or is_youtube_url(url):
                if url in existing:
                    duplicates += 1
                    continue
                existing.add(url)
                self._add_job(Job(url))
                added += 1
            else:
                skipped += 1

        self.links.clear()

        parts = [f"Added {added} link{'s' if added != 1 else ''}."]
        if expand_links:
            parts.append(
                f"Expanding {len(expand_links)} playlist, channel or TikTok "
                f"profile link{'s' if len(expand_links) != 1 else ''}…"
            )
        if duplicates:
            parts.append(f"{duplicates} already queued.")
        if skipped:
            parts.append(f"{skipped} skipped — TikTok or YouTube links only.")

        self.set_status(" ".join(parts))
        self._update_stats()
        self._sync_buttons()
        self._save_queue()

        if expand_links:
            self._enqueue_expand(expand_links)

    def _enqueue_expand(self, links):
        self._expand_queue.extend(links)
        self._start_next_expand()

    def _start_next_expand(self):
        if self.expander is not None and self.expander.isRunning():
            return
        if not self._expand_queue:
            return
        url = self._expand_queue.pop(0)
        self.expander = self._expand_thread_for(url)
        self.expander.note.connect(self.set_status)
        self.expander.found.connect(self.on_youtube_found)
        self.expander.failed.connect(self.on_youtube_failed)
        self.expander.finished.connect(self._on_expand_finished)
        self.expander.start()

    def _expand_thread_for(self, url):
        limit = MAX_ACCOUNT_VIDEOS
        if is_profile_url(url):
            return AccountFetchThread(url, limit, False, self)
        return YouTubeFetchThread(
            url, limit, self, include_shorts=self.chk_shorts.isChecked()
        )

    def on_youtube_found(self, urls, label):
        existing = {j.url for j in self.jobs}
        added = 0
        for url in urls:
            if url in existing:
                continue
            existing.add(url)
            self._add_job(Job(url))
            added += 1
        self.set_status(f"Added {added} video{'s' if added != 1 else ''} from {label}.")
        self._update_stats()
        self._sync_buttons()
        self._save_queue()

    def on_youtube_failed(self, message):
        self.set_status(f"Could not expand that link — {message}")

    def _on_expand_finished(self):
        self._start_next_expand()

    def _add_job(self, job):
        card = JobCard(job)
        self.jobs.append(job)
        self.cards[job.uid] = card
        self.queue_layout.insertWidget(self.queue_layout.count() - 1, card)

    def _remove_jobs(self, predicate):
        if self.running():
            self.set_status("Pause or stop the run before removing items.")
            return

        removed = 0
        keep = []
        for job in self.jobs:
            if predicate(job):
                card = self.cards.pop(job.uid, None)
                if card:
                    self.queue_layout.removeWidget(card)
                    card.deleteLater()
                removed += 1
            else:
                keep.append(job)

        self.jobs = keep
        self.select_all.setChecked(False)
        self.set_status(f"Removed {removed} item{'s' if removed != 1 else ''}.")
        self._update_stats()
        self._sync_buttons()
        self._save_queue()

    def clear_selected(self):
        chosen = {uid for uid, card in self.cards.items() if card.check.isChecked()}
        if not chosen:
            self.set_status("Tick the items you want to remove first.")
            return
        self._remove_jobs(lambda j: j.uid in chosen)

    def clear_completed(self):
        self._remove_jobs(lambda j: j.status == "Completed")

    def clear_failed(self):
        self._remove_jobs(lambda j: j.status == "Failed")

    def clear_remaining(self):
        self._remove_jobs(lambda j: j.status in ("Queued", "Paused", "Waiting"))

    def clear_all(self):
        self._remove_jobs(lambda j: True)

    def toggle_select_all(self, state):
        checked = int(state) == 2
        for card in self.cards.values():
            card.check.setChecked(checked)

    def start_run(self):
        if self.running():
            self.thread.resume()
            self.set_status("Resumed.")
            self._sync_buttons()
            return

        pending = [(j.uid, j.url) for j in self.jobs if j.status in ("Queued", "Paused")]
        if not pending:
            self.set_status("Nothing waiting. Add links, or use Retry failed.")
            return

        folder = self.output_dir()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, APP_TITLE, f"That folder can't be used.\n{exc}")
            return

        self._save_settings()

        for job in self.jobs:
            if job.status in ("Queued", "Paused"):
                job.status = "Queued"
                job.error = ""
                job.note = ""
                self.cards[job.uid].refresh()

        passes = RETRY_PASSES.get(self.passes.currentText(), 1)
        workers = PARALLEL_OPTIONS.get(self.parallel.currentText(), 2)

        self.active_uids = set()
        self.autoscroll = (workers == 1) or (len(pending) <= 1)

        self.thread = DownloadThread(
            pending,
            folder,
            self.quality.currentText(),
            self.cookies.isChecked(),
            self.pace.currentText(),
            passes,
            workers,
        )
        self.thread.job_started.connect(self.on_started)
        self.thread.job_meta.connect(self.on_meta)
        self.thread.job_progress.connect(self.on_progress)
        self.thread.job_retrying.connect(self.on_retrying)
        self.thread.job_result.connect(self.on_result)
        self.thread.log.connect(self.set_status)
        self.thread.countdown.connect(
            lambda s: self.set_status(f"Waiting {s:.1f}s before the next link…")
        )
        self.thread.finished_all.connect(self.on_run_finished)
        self.thread.start()

        effective = 1 if len(pending) <= 1 else workers
        note = (
            f"Started · {len(pending)} link{'s' if len(pending) != 1 else ''} · "
            f"{effective} worker{'s' if effective != 1 else ''} · "
            f"{1 + INLINE_RETRIES} tries each"
        )
        if passes:
            note += f", then {passes} end pass{'es' if passes != 1 else ''}"
        self.set_status(note + ".")
        self._sync_buttons()

    def pause_run(self):
        if self.running():
            self.thread.pause()
            self.set_status("Paused. The current file resumes where it stopped.")
            self._sync_buttons()

    def stop_run(self):
        if self.running():
            self.thread.stop()
            self.set_status("Stopping after the current step…")
            self._sync_buttons()

    def retry_failed(self):
        stuck = [j for j in self.jobs if j.status in ("Failed", "Waiting")]
        if not stuck:
            self.set_status("Nothing to retry.")
            return
        for job in stuck:
            job.status = "Queued"
            job.percent = 0.0
            job.speed = ""
            job.error = ""
            job.note = ""
            self.cards[job.uid].refresh()
        self._update_stats()
        self.start_run()

    def _job(self, uid):
        for job in self.jobs:
            if job.uid == uid:
                return job
        return None

    def on_started(self, uid, _):
        job = self._job(uid)
        if not job:
            return
        self.active_uids.add(uid)
        job.status = "Downloading"
        job.percent = 0.0
        job.error = ""
        job.note = ""
        card = self.cards.get(uid)
        if card:
            card.refresh()
            if self.autoscroll:
                self.scroll.ensureWidgetVisible(card, 0, 60)
        self._update_stats()

    def on_meta(self, uid, title, _):
        job = self._job(uid)
        if not job:
            return
        job.title = title
        self.cards[uid].refresh()

    def on_progress(self, uid, percent, size, speed):
        job = self._job(uid)
        if not job:
            return
        job.percent = percent
        if size and size != "—":
            job.size = size
        job.speed = speed
        self.cards[uid].refresh()

    def on_retrying(self, uid, attempt, total):
        job = self._job(uid)
        if not job:
            return
        job.status = "Retrying"
        job.percent = 0.0
        job.speed = ""
        job.note = f"retry {attempt} of {total}"
        self.cards[uid].refresh()
        self._update_stats()

    def on_result(self, uid, status, error, size):
        job = self._job(uid)
        if not job:
            return
        self.active_uids.discard(uid)
        job.status = status
        job.speed = ""
        job.note = "queued for an end pass" if status == "Waiting" else ""
        job.error = "" if status == "Completed" else error
        job.percent = 100.0 if status == "Completed" else 0.0
        if size and size != "—":
            job.size = size
        self.cards[uid].refresh()
        self._update_stats()
        self._save_queue()

    def on_run_finished(self):
        for uid in list(self.active_uids):
            job = self._job(uid)
            if not job:
                continue
            if job.status in ("Downloading", "Retrying"):
                job.status = "Queued"
                job.percent = 0.0
                job.speed = ""
                job.note = ""
                self.cards[job.uid].refresh()
        self.active_uids.clear()

        done = sum(1 for j in self.jobs if j.status == "Completed")
        failed = sum(1 for j in self.jobs if j.status in ("Failed", "Waiting"))

        self.thread = None
        self._update_stats()
        self._sync_buttons()
        self._save_queue()

        note = f"Run finished · {done} saved, {failed} failed."
        if failed:
            note += " Try Retry failed, or switch the pace to Safe."
        self.set_status(note)

    def closeEvent(self, event):
        if self.running():
            answer = QMessageBox.question(
                self,
                APP_TITLE,
                "A download is still running. Close anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.thread.stop()
            self.thread.wait(4000)
        if self.fetching():
            self.fetcher.wait(2000)
        if self.expander is not None and self.expander.isRunning():
            self.expander.wait(2000)
        self._save_settings()
        self._save_queue()
        event.accept()
