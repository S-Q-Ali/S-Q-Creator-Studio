"""The Social Discovery page: a channel in, the creator's accounts out.

The page lives in the AI Finder tab as its own mode. Everything happens
in the page — no dialogs, no modal results — and the table grows a row per
channel as the run goes on.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from s_q_ali_media_downloader.agent.social_discovery import (
    PLATFORMS,
    DiscoveryResult,
    discover,
)
from s_q_ali_media_downloader.agent.tools.browser import BrowserSession
from s_q_ali_media_downloader.core import exporter

logger = logging.getLogger(__name__)

VERDICT_TEXT = {
    "found": "✓ Found",
    "not_found": "✗ Not found",
    "no_match": "✗ Not this creator",
    "unknown": "? Unknown",
}


class SocialDiscoveryWorker(QThread):
    """Runs the discovery for a list of channels, one after the other."""

    progress = Signal(str)
    finished_one = Signal(object)
    failed = Signal(str)

    def __init__(self, queries: list[str], parent=None):
        super().__init__(parent)
        self.queries = queries
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:  # pragma: no cover - exercised through the page
        try:
            with BrowserSession() as session:
                for index, query in enumerate(self.queries, start=1):
                    if self._cancelled:
                        self.progress.emit("Cancelled.")
                        return
                    total = len(self.queries)
                    self.progress.emit(f"[{index}/{total}] {query} ...")
                    result = discover(
                        session,
                        query,
                        progress=lambda message, q=query, i=index, n=total: self.progress.emit(
                            f"[{i}/{n}] {q}: {message}"
                        ),
                    )
                    if self._cancelled:
                        return
                    self.finished_one.emit(result)
        except Exception as exc:
            logger.warning("Social discovery failed", exc_info=True)
            self.failed.emit(str(exc))


class SocialDiscoveryPage(QWidget):
    """Paste a channel, get the creator's other accounts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: SocialDiscoveryWorker | None = None
        self._results: list[DiscoveryResult] = []
        self._last_clicked: tuple[int, int] | None = None
        self._build()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        title = QLabel("🔎 SOCIAL DISCOVERY")
        title.setProperty("role", "pageTitle")
        layout.addWidget(title)

        hint = QLabel(
            "Paste a YouTube channel URL, an @handle, or a channel name — one per line "
            "for a batch. The channel's own links are checked first; the AI agent proposes "
            "the rest and every account is confirmed in a real browser."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText(
            "https://www.youtube.com/@mkbhd\n@MrBeast\nMarques Brownlee"
        )
        self.input_edit.setMinimumHeight(96)
        self.input_edit.setMaximumHeight(140)
        layout.addWidget(self.input_edit)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.btn_find = QPushButton("🔎 Find social accounts")
        self.btn_find.setProperty("kind", "primary")
        self.btn_find.setMinimumHeight(40)
        self.btn_find.clicked.connect(self._start)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(lambda: self._export("csv"))
        self.btn_json = QPushButton("Export JSON")
        self.btn_json.setMinimumHeight(40)
        self.btn_json.setEnabled(False)
        self.btn_json.clicked.connect(lambda: self._export("json"))
        buttons.addWidget(self.btn_find, 0)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_export)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_json)
        layout.addLayout(buttons)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "hint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 1 + len(PLATFORMS))
        self.table.setHorizontalHeaderLabels(
            ["Channel", "Facebook", "Instagram", "TikTok"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in range(1, 1 + len(PLATFORMS)):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.Stretch
            )
        self.table.cellClicked.connect(self._on_cell_clicked)

        # The table and the empty state share one slot. A table with no rows
        # is a screen of nothing; the empty state says what to do instead.
        self.table_stack = QStackedWidget()
        self.table_stack.addWidget(self.table)
        self.empty_state = QLabel(
            "No accounts checked yet.\n\n"
            "Paste a YouTube channel URL, an @handle or a channel name above, "
            "then press Find social accounts."
        )
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setWordWrap(True)
        self.table_stack.addWidget(self.empty_state)
        self.table_stack.setCurrentWidget(self.empty_state)
        layout.addWidget(self.table_stack, 1)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setProperty("role", "hint")
        self.detail_label.setMinimumHeight(48)
        layout.addWidget(self.detail_label)

    # ------------------------------------------------------------------ #
    # Running
    # ------------------------------------------------------------------ #
    def _queries(self) -> list[str]:
        return [line.strip() for line in self.input_edit.toPlainText().splitlines() if line.strip()]

    def _start(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        queries = self._queries()
        if not queries:
            self.status_label.setText("Paste a channel URL, an @handle or a channel name first.")
            return
        self._results = []
        self.table.setRowCount(0)
        self.btn_find.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_export.setEnabled(False)
        self.btn_json.setEnabled(False)
        self.status_label.setText(f"Working on {len(queries)} channel(s) ...")

        self.worker = SocialDiscoveryWorker(queries, parent=self)
        self.worker.progress.connect(self.status_label.setText)
        self.worker.finished_one.connect(self._on_result)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def cancel(self) -> None:
        """Ask the worker to stop without waiting for it."""
        if self.worker is not None:
            self.worker.cancel()

    def _cancel(self) -> None:
        self.cancel()
        self.status_label.setText("Cancelling ...")

    def shutdown(self) -> bool:
        """Stop the discovery worker and wait for it. True when it is gone."""
        worker = self.worker
        if worker is None or not worker.isRunning():
            return True
        self.cancel()
        return worker.wait(4000)

    def _on_result(self, result: DiscoveryResult) -> None:
        self._results.append(result)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table_stack.setCurrentWidget(self.table)

        channel = QTableWidgetItem(
            f"{result.title}  (@{result.handle})\n{result.subscribers:,} subscribers"
        )
        tip = result.url
        if result.reason:
            tip += f"\n{result.reason}"
        if result.warning:
            tip += f"\n{result.warning}"
        channel.setToolTip(tip)
        self.table.setItem(row, 0, channel)

        for index, platform in enumerate(PLATFORMS, start=1):
            outcome = result.outcome(platform)
            if outcome is None:
                item = QTableWidgetItem("—")
                item.setForeground(Qt.GlobalColor.gray)
            else:
                item = QTableWidgetItem(VERDICT_TEXT.get(outcome.verdict, outcome.verdict))
                item.setForeground(Qt.GlobalColor.green if outcome.is_found else Qt.GlobalColor.gray)
                tip = outcome.url or outcome.detail
                if outcome.evidence:
                    tip += "\n\n" + ", ".join(outcome.evidence)
                item.setToolTip(tip)
                if outcome.url:
                    item.setData(Qt.ItemDataRole.UserRole, outcome.url)
            self.table.setItem(row, index, item)

        self.table.resizeRowsToContents()
        status = f"{result.title}: {result.found_count} of {len(PLATFORMS)} confirmed."
        if result.warning:
            status += f"  ·  {result.warning}"
        self.status_label.setText(status)

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"Failed: {message}")

    def _on_finished(self) -> None:
        self.btn_find.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_export.setEnabled(bool(self._results))
        self.btn_json.setEnabled(bool(self._results))
        if self._results:
            total = sum(r.found_count for r in self._results)
            self.status_label.setText(
                f"Done — {total} confirmed account(s) across {len(self._results)} channel(s)."
            )

    # ------------------------------------------------------------------ #
    # The detail line
    # ------------------------------------------------------------------ #
    def _on_cell_clicked(self, row: int, column: int) -> None:
        if column == 0:
            return
        result = self._results[row] if row < len(self._results) else None
        if result is None:
            return
        outcome = result.outcome(PLATFORMS[column - 1])
        if outcome is None:
            self.detail_label.setText("")
            return
        parts = [f"{outcome.platform}: {VERDICT_TEXT.get(outcome.verdict, outcome.verdict)}"]
        if outcome.display_name:
            parts.append(f"account name: {outcome.display_name}")
        if outcome.url:
            parts.append(outcome.url)
        if outcome.evidence:
            parts.append("evidence: " + ", ".join(outcome.evidence))
        if outcome.detail:
            parts.append(outcome.detail)
        if outcome.url:
            parts.append("click the cell again to open the account")
        self.detail_label.setText("  ·  ".join(parts))

        # The first click shows the account; a second click on the same cell
        # opens it. The hint says so, and it is what a link is expected to
        # do.
        cell = (row, column)
        if outcome.url and self._last_clicked == cell:
            QDesktopServices.openUrl(QUrl(outcome.url))
            self._last_clicked = None
        else:
            self._last_clicked = cell

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def _rows(self) -> list[dict[str, str]]:
        rows = []
        for result in self._results:
            row = {
                "channel": result.title,
                "handle": result.handle,
                "url": result.url,
                "subscribers": str(result.subscribers),
            }
            for platform in PLATFORMS:
                outcome = result.outcome(platform)
                row[platform] = outcome.url if outcome and outcome.url else ""
                row[f"{platform}_status"] = outcome.verdict if outcome else ""
            rows.append(row)
        return rows

    def _export(self, fmt: str) -> None:
        if not self._results:
            return
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export social discovery",
            exporter.suggested_filename("social-discovery", fmt),
            f"Text documents (*.{fmt})",
        )
        if not path:
            return
        try:
            text = exporter.serialise(fmt, self._rows())
            exporter.write_export(path, text)
        except OSError as exc:
            self.status_label.setText(f"Could not write the export: {exc}")
            return
        self.status_label.setText(f"Saved {len(self._results)} rows to {path}")
