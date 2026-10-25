"""The app's settings page: one place for every setting.

The page used to be split across the app. The download preferences sat in
the left rail, where they took a quarter of the width on a small screen and
buried the thing the user actually came to do - paste a link. The API keys
sat in the research module's own settings page, which left the desktop app
with no place to enter the Groq key at all.

Now the keys, the download preferences and the layout preference live in one
column of cards, in the app's own design language.
"""

from __future__ import annotations

import os
import os.path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.core import settings_store
from s_q_ali_media_downloader.engine import (
    APP_NAME,
    DEFAULT_DELAY,
    DEFAULT_PARALLEL,
    DEFAULT_PASSES,
    DELAY_PRESETS,
    PARALLEL_OPTIONS,
    QUALITY_OPTIONS,
    RETRY_PASSES,
    default_output_dir,
    impersonation_summary,
)

ORG = "S-Q-Ali"

# The version of the stored preferences. It is bumped only when the meaning
# of a stored value changes - the settings moved to this page, but the keys
# and the values did not, so an existing user's choices are still there.
SETTINGS_VERSION = "2.1"

# The keys the app keeps in the sealed store rather than in QSettings.
GROQ_KEY = "groq_api_key"
YOUTUBE_KEY = "youtube_api_key"
COOKIES_FILE_KEY = "youtube_cookies_file"


def make_settings() -> QSettings:
    """The app's preferences.

    On Windows these live in the registry. ``SQ_SETTINGS_FILE`` points them
    at an ini file instead, which is how the tests keep out of the user's
    own preferences without changing the format for the whole process.
    """
    override = os.environ.get("SQ_SETTINGS_FILE")
    if override:
        return QSettings(override, QSettings.Format.IniFormat)
    return QSettings(ORG, APP_NAME)


class SettingsPage(QWidget):
    """Every setting of the app, in three cards."""

    density_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self.settings = make_settings()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        host = QWidget()
        host.setObjectName("SettingsHost")
        page = QVBoxLayout(host)
        page.setContentsMargins(24, 20, 24, 24)
        page.setSpacing(16)

        page.addWidget(self._card("AI KEYS", self._build_keys()))
        page.addWidget(self._card("DOWNLOADS", self._build_downloads()))
        page.addWidget(self._card("LAYOUT", self._build_layout()))
        page.addStretch(1)

        scroll.setWidget(host)

        self.status = QLabel("")
        self.status.setProperty("role", "hint")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

    # ------------------------------------------------------------------ #
    # The cards
    # ------------------------------------------------------------------ #
    def _card(self, title: str, rows: list[tuple]) -> QFrame:
        """A titled card. The rows share one grid, so every label lines up."""
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 18)
        lay.setSpacing(12)
        heading = QLabel(title)
        heading.setProperty("role", "section")
        lay.addWidget(heading)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        grid.setColumnMinimumWidth(0, 150)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)

        row_index = 0
        for label, control, hint in rows:
            text = QLabel(label)
            text.setStyleSheet("color: #9C93AE;")
            text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(text, row_index, 0)
            grid.addWidget(control, row_index, 1)
            if hint:
                note = QLabel(hint)
                note.setProperty("role", "hint")
                note.setWordWrap(True)
                grid.addWidget(note, row_index + 1, 1)
                row_index += 1
            row_index += 1

        lay.addLayout(grid)
        return card

    def _build_keys(self) -> list[tuple]:
        self.groq_edit = QLineEdit()
        self.groq_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.groq_edit.setPlaceholderText("gsk_...")
        self.groq_edit.setMaximumWidth(460)
        self.groq_edit.textChanged.connect(self._save_keys)

        self.youtube_key_edit = QLineEdit()
        self.youtube_key_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.youtube_key_edit.setPlaceholderText("AIza... (optional)")
        self.youtube_key_edit.setMaximumWidth(460)
        self.youtube_key_edit.textChanged.connect(self._save_keys)

        cookies_row = QWidget()
        cookies_lay = QHBoxLayout(cookies_row)
        cookies_lay.setContentsMargins(0, 0, 0, 0)
        cookies_lay.setSpacing(8)
        self.cookies_file_edit = QLineEdit()
        self.cookies_file_edit.setPlaceholderText("No cookies file selected")
        self.cookies_file_edit.textChanged.connect(self._save_keys)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self.choose_cookies)
        clear = QPushButton("Clear")
        clear.setProperty("kind", "ghost")
        clear.clicked.connect(self.clear_cookies)
        cookies_lay.addWidget(self.cookies_file_edit, 1)
        cookies_lay.addWidget(browse)
        cookies_lay.addWidget(clear)

        self.key_warning = QLabel("")
        self.key_warning.setProperty("role", "hint")
        self.key_warning.setWordWrap(True)
        self.key_warning.setStyleSheet("color: #FFB020;")
        self.key_warning.setVisible(False)

        return [
            (
                "Groq API key",
                self.groq_edit,
                (
                    "Used by Social Discovery: the agent proposes the accounts, a "
                    "real browser confirms them. Leave it empty to search by name only."
                ),
            ),
            (
                "YouTube API key",
                self.youtube_key_edit,
                (
                    "Optional. Without it the search runs keyless through yt-dlp; "
                    "with it the results carry the exact view and subscriber counts."
                ),
            ),
            (
                "Cookies file",
                cookies_row,
                (
                    "Optional. A Netscape cookies.txt exported from a signed-in "
                    "browser - the way around YouTube's 'confirm you are not a bot'."
                ),
            ),
            ("", self.key_warning, ""),
        ]

    def _build_downloads(self) -> list[tuple]:
        folder_row = QWidget()
        folder_lay = QHBoxLayout(folder_row)
        folder_lay.setContentsMargins(0, 0, 0, 0)
        folder_lay.setSpacing(8)
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Choose a folder")
        browse = QPushButton("Browse")
        browse.clicked.connect(self.choose_folder)
        open_btn = QPushButton("Open folder")
        open_btn.clicked.connect(self.open_folder)
        folder_lay.addWidget(self.folder_edit, 1)
        folder_lay.addWidget(browse)
        folder_lay.addWidget(open_btn)

        self.quality = QComboBox()
        self.quality.addItems(QUALITY_OPTIONS.keys())
        self.quality.setMaximumWidth(220)

        self.pace = QComboBox()
        self.pace.addItems(DELAY_PRESETS.keys())
        self.pace.setMaximumWidth(220)
        self.pace.setToolTip(
            "How long each worker waits between its own videos.\n"
            "With 2 workers running, the effective rate is double this."
        )

        self.parallel = QComboBox()
        self.parallel.addItems(PARALLEL_OPTIONS.keys())
        self.parallel.setMaximumWidth(220)
        self.parallel.setToolTip(
            "How many videos download at once. A single link always runs on its own."
        )

        self.passes = QComboBox()
        self.passes.addItems(RETRY_PASSES.keys())
        self.passes.setMaximumWidth(220)
        self.passes.setToolTip(
            "How many extra sweeps run over the Waiting list at the end."
        )

        self.cookies = QCheckBox("Sign in with Chrome cookies")
        self.cookies.setToolTip(
            "Use your Chrome session for private or age-gated videos. "
            "Close Chrome before you start a run."
        )

        self.identity = QLabel("")
        self.identity.setProperty("role", "hint")
        self.identity.setWordWrap(True)
        self.identity.setMaximumWidth(460)

        rows = [
            ("Save to", folder_row, ""),
            ("Quality", self.quality, ""),
            ("Pace", self.pace, ""),
            ("Workers", self.parallel, ""),
            ("End passes", self.passes, ""),
            ("", self.cookies, ""),
            ("", self.identity, ""),
        ]
        return rows

    def _build_layout(self) -> list[tuple]:
        self.compact_check = QCheckBox("Compact layout")
        self.compact_check.toggled.connect(self._on_compact_toggled)

        self.density_note = QLabel("")
        self.density_note.setProperty("role", "hint")
        self.density_note.setWordWrap(True)
        self.density_note.setMaximumWidth(460)

        return [
            ("", self.compact_check, ""),
            ("", self.density_note, ""),
        ]

    # ------------------------------------------------------------------ #
    # Loading and saving
    # ------------------------------------------------------------------ #
    def load(self) -> None:
        """Read every setting into the page."""
        self.settings_page_loaded = False

        if self.settings.value("settings_version") != SETTINGS_VERSION:
            self.settings.setValue("quality", "1080p")
            self.settings.setValue("pace", DEFAULT_DELAY)
            self.settings.setValue("passes", DEFAULT_PASSES)
            self.settings.setValue("parallel", DEFAULT_PARALLEL)
            self.settings.setValue("settings_version", SETTINGS_VERSION)

        self.folder_edit.setText(self.settings.value("output_dir") or default_output_dir())

        quality = self.settings.value("quality")
        self.quality.setCurrentText(quality if quality in QUALITY_OPTIONS else "1080p")

        pace = self.settings.value("pace")
        self.pace.setCurrentText(pace if pace in DELAY_PRESETS else DEFAULT_DELAY)

        passes = self.settings.value("passes")
        self.passes.setCurrentText(passes if passes in RETRY_PASSES else DEFAULT_PASSES)

        parallel = self.settings.value("parallel")
        self.parallel.setCurrentText(
            parallel if parallel in PARALLEL_OPTIONS else DEFAULT_PARALLEL
        )

        self.cookies.setChecked(self.settings.value("cookies") == "true")

        self.groq_edit.setText(settings_store.get_setting(GROQ_KEY) or "")
        self.youtube_key_edit.setText(settings_store.get_setting(YOUTUBE_KEY) or "")
        cookies_path = settings_store.get_setting(COOKIES_FILE_KEY) or ""
        self.cookies_file_edit.setText(cookies_path)

        unreadable = [
            name
            for key, name in ((GROQ_KEY, "Groq API key"), (YOUTUBE_KEY, "YouTube API key"))
            if settings_store.secret_is_unreadable(key)
        ]
        if unreadable:
            self.key_warning.setText(
                "The stored "
                + " and ".join(unreadable)
                + " cannot be decrypted on this Windows account. Enter them again."
            )
            self.key_warning.setVisible(True)
        elif cookies_path and not os.path.isfile(cookies_path):
            # Cookies file is configured but doesn't exist — show a warning.
            self.key_warning.setText(
                f"Configured cookies file not found: {cookies_path}\n"
                "YouTube bot checks will block downloads until you configure a valid file."
            )
            self.key_warning.setStyleSheet("color: #FFB020;")
            self.key_warning.setVisible(True)
        else:
            self.key_warning.setVisible(False)

        self._refresh_identity()
        self._refresh_density_note()

        self.settings_page_loaded = True

    def save(self) -> None:
        """Write the download preferences back."""
        self.settings.setValue("output_dir", self.folder_edit.text().strip())
        self.settings.setValue("quality", self.quality.currentText())
        self.settings.setValue("pace", self.pace.currentText())
        self.settings.setValue("passes", self.passes.currentText())
        self.settings.setValue("parallel", self.parallel.currentText())
        self.settings.setValue("cookies", "true" if self.cookies.isChecked() else "false")
        self.settings.sync()

    def _save_keys(self) -> None:
        """Write the secrets back as the user types."""
        if not getattr(self, "settings_page_loaded", False):
            return
        for key, edit in (
            (GROQ_KEY, self.groq_edit),
            (YOUTUBE_KEY, self.youtube_key_edit),
            (COOKIES_FILE_KEY, self.cookies_file_edit),
        ):
            text = edit.text().strip()
            if text:
                settings_store.set_setting(key, text)
            else:
                settings_store.set_setting(key, "")
        self.set_status("Saved.")

    def _refresh_identity(self) -> None:
        ok, label = impersonation_summary()
        self.identity.setText(
            ("Browser identity · " if ok else "No browser identity · ") + label
        )
        self.identity.setStyleSheet(
            f"color: {'#2DD4BF' if ok else '#F2547D'}; font-size: 10px;"
        )
        self.identity.setToolTip(
            "TikTok blocks requests that don't look like a real browser.\n"
            "This is the signature yt-dlp is sending on your behalf."
        )

    def _refresh_density_note(self) -> None:
        choice = self.settings.value("density") or "auto"
        if choice == "auto":
            self.compact_check.setChecked(self._window_is_small())
            self.compact_check.setEnabled(True)
            self.density_note.setText(
                "Follows the window: a small screen gets the compact layout. "
                "Tick the box to choose it yourself."
            )
        else:
            self.compact_check.setChecked(choice == "compact")
            self.compact_check.setEnabled(True)
            self.density_note.setText("You chose this. Unticking it follows the window again.")

    def _window_is_small(self) -> bool:
        window = self.window()
        if window is None:
            return False
        return window.width() < 1500 or window.height() < 850

    def _on_compact_toggled(self, checked: bool) -> None:
        if not getattr(self, "settings_page_loaded", False):
            return
        if checked == self._window_is_small() and (
            self.settings.value("density") or "auto"
        ) == "auto":
            return
        self.settings.setValue("density", "compact" if checked else "comfortable")
        self.settings.sync()
        self._refresh_density_note()
        self.density_changed.emit()

    # ------------------------------------------------------------------ #
    # The small actions
    # ------------------------------------------------------------------ #
    def set_status(self, text: str) -> None:
        self.status.setText(text)

    def choose_cookies(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a cookies.txt", "", "Text files (*.txt);;All files (*)"
        )
        if path:
            self.cookies_file_edit.setText(path)

    def clear_cookies(self) -> None:
        self.cookies_file_edit.clear()
        self.set_status("Cookies file cleared.")

    def choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose a folder")
        if path:
            # Validate the folder is writable before accepting.
            try:
                os.makedirs(path, exist_ok=True)
                test_file = os.path.join(path, ".write_test")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                self.folder_edit.setText(path)
                self.set_status(f"Folder validated: {path}")
            except OSError as exc:
                QMessageBox.warning(
                    self,
                    "Invalid Folder",
                    f"Cannot write to this folder:\n{path}\n\n{exc}",
                )
                self.set_status("Folder not writable — please choose another.")

    def open_folder(self) -> None:
        path = self.folder_edit.text().strip()
        if not path:
            return
        os.makedirs(path, exist_ok=True)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
