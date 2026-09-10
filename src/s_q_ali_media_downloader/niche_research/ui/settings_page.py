"""Settings page — API keys for the AI analysis / thumbnail providers."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
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

    def _save(self) -> None:
        for key, edit in self._keys.items():
            db.set_setting(key, edit.text().strip())
        db.set_setting("ai_primary_provider", self._default_provider.currentData() or "aihubmix")
        self._status.setText("Settings saved.")
        self.reload()

    def reload(self) -> None:
        self._status.clear()
