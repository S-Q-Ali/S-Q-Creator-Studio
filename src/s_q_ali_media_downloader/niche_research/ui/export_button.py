"""The shared export button (CSV / JSON / Markdown) for the research pages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QMenu, QPushButton, QWidget

from s_q_ali_media_downloader.niche_research.tools import exporter

FORMAT_LABELS = (
    ("csv", "CSV — spreadsheet"),
    ("json", "JSON — full data"),
    ("markdown", "Markdown — report"),
)

_FILTERS = {
    "csv": "CSV (*.csv)",
    "json": "JSON (*.json)",
    "markdown": "Markdown (*.md)",
}


class ExportButton(QPushButton):
    """Exports whatever payload the page sets, in three formats."""

    exported = Signal(str)
    failed = Signal(str)

    def __init__(self, base_name: str, title: str, parent: QWidget | None = None):
        super().__init__("Export", parent)
        self.setProperty("variant", "outline")
        self.setToolTip("Export this page's data")
        self._base_name = base_name
        self._title = title
        self._rows: list[dict[str, Any]] = []
        self._sections: list[tuple[str, Sequence[dict[str, Any]]]] = []
        self._columns: Sequence[str] | None = None

        menu = QMenu(self)
        for fmt, label in FORMAT_LABELS:
            action = menu.addAction(label)
            action.triggered.connect(lambda _=False, f=fmt: self.export(f))
        self.setMenu(menu)
        self.setEnabled(False)

    # ------------------------------------------------------------------ #
    # Payload
    # ------------------------------------------------------------------ #
    def set_payload(
        self,
        rows: Sequence[dict[str, Any]],
        *,
        sections: Sequence[tuple[str, Sequence[dict[str, Any]]]] = (),
        columns: Sequence[str] | None = None,
    ) -> None:
        """Set the data this button exports."""
        self._rows = [dict(r) for r in rows or []]
        self._sections = [(name, list(items)) for name, items in sections or []]
        self._columns = columns
        has_data = bool(self._rows) or any(items for _name, items in self._sections)
        self.setEnabled(has_data)
        self.setToolTip(
            "Export this page's data" if has_data else "Nothing to export yet"
        )

    def has_data(self) -> bool:
        return bool(self._rows) or any(items for _name, items in self._sections)

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def export(self, fmt: str) -> str | None:
        """Write the payload to a file chosen by the user."""
        if not self.has_data():
            return None
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export",
            exporter.suggested_filename(self._base_name, fmt),
            _FILTERS.get(fmt, "All files (*)"),
        )
        if not path:
            return None
        try:
            text = exporter.serialise(
                fmt,
                self._rows,
                title=self._title,
                columns=self._columns,
                sections=self._sections,
            )
            exporter.write_export(path, text)
        except OSError as exc:
            self.failed.emit(f"Export failed: {exc}")
            return None
        self.exported.emit(path)
        return path
