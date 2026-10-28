"""A small, capped, read-only log the user can watch while discovery runs.

The status line says what is happening *now*; it cannot say what already
happened. When a run stalls or the AI step is skipped, the reason is in the
lines above. The panel keeps a bounded number of lines so a long batch cannot
grow the window's memory without limit.
"""

from __future__ import annotations

import time

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

#: Enough to follow a 100-channel batch without holding everything forever.
MAX_LINES = 500


class ActivityLog(QWidget):
    """A timestamped, read-only log with a Clear button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("Activity log")
        title.setProperty("role", "hint")
        title.setStyleSheet("font-weight: bold;")
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setProperty("kind", "ghost")
        self.btn_clear.setToolTip("Clear the activity log.")
        self.btn_clear.clicked.connect(self.clear_log)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.btn_clear)
        layout.addLayout(header)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(MAX_LINES)
        self.view.setPlaceholderText("Discovery steps appear here ...")
        self.view.setMinimumHeight(90)
        self.view.setMaximumHeight(160)
        layout.addWidget(self.view)

    def append_line(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        stamp = time.strftime("%H:%M:%S")
        self.view.appendPlainText(f"[{stamp}] {text}")

    def clear_log(self) -> None:
        self.view.clear()

    def text(self) -> str:
        return self.view.toPlainText()
