"""Settings page — API keys for the AI analysis / thumbnail providers."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.niche_research.research import competitor_engine as ce
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui.theme import research_style


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("researchPage")
        self.setStyleSheet(research_style())
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Research Settings")
        title.setObjectName("headerTitle")
        subtitle = QLabel(
            "Optional API keys. A YouTube Data API key unlocks exact channel stats; "
            "AI analysis prefers aiHubMix, then Groq, OpenRouter, Google."
        )
        subtitle.setObjectName("headerSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        root.addLayout(title_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(12)

        self._default_provider = QComboBox()
        for name, label in (
            ("aihubmix", "aiHubMix (chat + thumbnails)"),
            ("groq", "Groq"),
            ("openrouter", "OpenRouter"),
            ("google", "Google AI"),
        ):
            self._default_provider.addItem(label, name)
        current = db.get_setting("ai_primary_provider") or "aihubmix"
        idx = self._default_provider.findData(current)
        self._default_provider.setCurrentIndex(max(idx, 0))

        provider_card = QFrame()
        provider_card.setObjectName("panel")
        provider_layout = QFormLayout(provider_card)
        provider_layout.setContentsMargins(14, 12, 14, 12)
        provider_layout.setSpacing(6)
        provider_layout.addRow("Default AI provider", self._default_provider)
        provider_hint = QLabel("Used by the AI channel analysis when several keys are set.")
        provider_hint.setObjectName("formHint")
        provider_layout.addRow("", provider_hint)
        body_layout.addWidget(provider_card)

        self._keys: dict[str, QLineEdit] = {}
        for key, label, hint in (
            (
                "youtube_api_key",
                "YouTube Data API key",
                (
                    "Optional. Unlocks exact channel stats — total uploads, total views, join date — "
                    "matching the web tool. Channel search & discovery always stay keyless (yt-dlp)."
                ),
            ),
            (
                "aihubmix_api_key",
                "aiHubMix API key",
                "Used for chat analysis and as the first choice for the Thumbnail generator.",
            ),
            ("groq_api_key", "Groq API key", "Chat analysis only."),
            ("openrouter_api_key", "OpenRouter API key", "Chat analysis and Thumbnail fallback."),
            (
                "google_ai_api_key",
                "Google AI (Gemini) API key",
                "Chat analysis and Thumbnail generation fallback.",
            ),
        ):
            edit = QLineEdit()
            edit.setPlaceholderText("sk-...")
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setText(db.get_setting(key) or "")
            card = QFrame()
            card.setObjectName("panel")
            card_layout = QFormLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(6)
            card_layout.addRow(label, edit)
            if hint:
                hint_label = QLabel(hint)
                hint_label.setObjectName("formHint")
                card_layout.addRow("", hint_label)
            body_layout.addWidget(card)
            self._keys[key] = edit

        body_layout.addWidget(self._build_cookies_card())

        interval_card = QFrame()
        interval_card.setObjectName("panel")
        interval_layout = QFormLayout(interval_card)
        interval_layout.setContentsMargins(14, 12, 14, 12)
        interval_layout.setSpacing(6)
        self._interval_combo = QComboBox()
        for minutes in (30, 60, 180):
            label = "Every 30 minutes" if minutes == 30 else (
                "Every hour" if minutes == 60 else "Every 3 hours"
            )
            self._interval_combo.addItem(label, minutes)
        current_minutes = ce.snapshot_interval_minutes()
        idx = self._interval_combo.findData(current_minutes)
        self._interval_combo.setCurrentIndex(max(idx, 0))
        interval_layout.addRow("Snapshot interval", self._interval_combo)
        interval_hint = QLabel(
            "How often the background poller records a snapshot of your tracked items. "
            "VPH and 7-day growth need at least two snapshots."
        )
        interval_hint.setObjectName("formHint")
        interval_hint.setWordWrap(True)
        interval_layout.addRow("", interval_hint)
        body_layout.addWidget(interval_card)

        save_row = QHBoxLayout()
        self._status = QLabel("")
        self._status.setObjectName("statusOk")
        save_row.addWidget(self._status, 1)
        save_btn = QPushButton("Save settings")
        save_btn.clicked.connect(self._save)
        save_row.addWidget(save_btn)
        body_layout.addLayout(save_row)
        body_layout.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    # ------------------------------------------------------------------ #
    # Cookies file
    # ------------------------------------------------------------------ #
    def _build_cookies_card(self) -> QFrame:
        """Cookie file picker — the escape hatch for YouTube bot-checks."""
        card = QFrame()
        card.setObjectName("panel")
        layout = QFormLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self._cookies_edit = QLineEdit()
        self._cookies_edit.setReadOnly(True)
        self._cookies_edit.setPlaceholderText("No cookies.txt selected")
        self._cookies_edit.setText(db.get_setting("youtube_cookies_file") or "")

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self._cookies_edit, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_cookies)
        row.addWidget(browse)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear_cookies)
        row.addWidget(clear)
        holder = QWidget()
        holder.setLayout(row)

        layout.addRow("YouTube cookies.txt", holder)
        hint = QLabel(
            "Optional. Exports from a logged-in browser in Netscape format. "
            "Used for every research request — it is the way around YouTube's "
            "'Sign in to confirm you're not a bot' check."
        )
        hint.setObjectName("formHint")
        hint.setWordWrap(True)
        layout.addRow("", hint)
        return card

    def _browse_cookies(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select cookies.txt",
            "",
            "Cookie files (*.txt);;All files (*)",
        )
        if not path:
            return
        self._cookies_edit.setText(path)
        self._save()

    def _clear_cookies(self) -> None:
        self._cookies_edit.clear()
        db.set_setting("youtube_cookies_file", "")
        self._status.setText("Cookie file cleared.")

    def _save(self) -> None:
        try:
            for key, edit in self._keys.items():
                db.set_setting(key, edit.text().strip())
            db.set_setting("ai_primary_provider", self._default_provider.currentData() or "aihubmix")
            db.set_setting("youtube_cookies_file", self._cookies_edit.text().strip())
            db.set_setting(
                "snapshot_interval_minutes",
                str(self._interval_combo.currentData() or 60),
            )
        except OSError as exc:
            # Windows refused to encrypt the key: nothing was stored, and the
            # user has to know why their key did not stick.
            self._set_status(
                f"Could not protect the API key on this machine: {exc}", error=True
            )
            return
        self.reload()
        self._set_status("Settings saved.")

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self._status.setText(text)
        self._status.setObjectName("statusError" if error else "statusOk")
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)

    def reload(self) -> None:
        self._status.clear()
        if any(db.secret_is_unreadable(key) for key in self._keys):
            self._set_status(
                "Stored API keys cannot be decrypted on this account — please re-enter them.",
                error=True,
            )
