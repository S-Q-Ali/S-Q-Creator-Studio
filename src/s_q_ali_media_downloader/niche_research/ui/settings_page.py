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
            "Optional API keys. AI analysis prefers aiHubMix, then Groq, OpenRouter, Google."
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

        self._keys: dict[str, QLineEdit] = {}
        for key, label, hint in (
            (
                "aihubmix_api_key",
                "aiHubMix API key",
                "Used for chat analysis and the Thumbnail generator (gpt-image-2-free).",
            ),
            ("groq_api_key", "Groq API key", ""),
            ("openrouter_api_key", "OpenRouter API key", ""),
            ("google_ai_api_key", "Google AI (Gemini) API key", ""),
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
