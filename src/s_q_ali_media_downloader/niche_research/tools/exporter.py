"""Export helpers for the Niche Research pages.

Three formats, one entry point:

* **CSV** — a flat table for spreadsheets (UTF-8 with BOM so Excel opens it).
* **JSON** — full fidelity, nested structures kept as they are.
* **Markdown** — a human-readable report (a title, a generated-at line and
  tables), used for the AI analysis pages.

The serialisers are pure functions so they can be tested without Qt.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import Any

FORMATS = ("csv", "json", "markdown")


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _flatten(value: Any) -> str:
    """Render one cell value as text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return ", ".join(_flatten(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def to_csv(rows: Sequence[dict[str, Any]], columns: Sequence[str] | None = None) -> str:
    """Serialise rows to CSV text.

    ``columns`` fixes the column order; without it the union of the row keys
    is used (first-seen order).
    """
    if not rows:
        return ""
    if columns is None:
        seen: list[str] = []
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.append(key)
        columns = seen
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(columns))
    for row in rows:
        writer.writerow([_flatten(row.get(col)) for col in columns])
    return buffer.getvalue()


def to_json(rows: Any) -> str:
    """Serialise rows (or any JSON-able payload) to pretty JSON text."""
    return json.dumps(rows, ensure_ascii=False, indent=2, default=str)


def _md_cell(value: Any) -> str:
    text = _flatten(value).replace("|", "\\|").replace("\n", " ")
    return text


def to_markdown(
    title: str,
    rows: Sequence[dict[str, Any]],
    columns: Sequence[str] | None = None,
    *,
    sections: Sequence[tuple[str, Sequence[dict[str, Any]]]] = (),
) -> str:
    """Build a Markdown report.

    ``rows`` is the main table; ``sections`` adds extra titled tables (the AI
    analysis uses it for ideas, scripts and the growth blueprint).
    """
    lines: list[str] = [f"# {title}", "", f"Generated {_now_label()}", ""]

    def add_table(table_rows: Sequence[dict[str, Any]], cols: Sequence[str] | None) -> None:
        if not table_rows:
            lines.append("_No data._")
            lines.append("")
            return
        if cols is None:
            seen: list[str] = []
            for row in table_rows:
                for key in row:
                    if key not in seen:
                        seen.append(key)
            cols = seen
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join("---" for _ in cols) + " |")
        for row in table_rows:
            lines.append("| " + " | ".join(_md_cell(row.get(col)) for col in cols) + " |")
        lines.append("")

    add_table(rows, columns)
    for name, section_rows in sections:
        lines.append(f"## {name}")
        lines.append("")
        add_table(section_rows, None)
    return "\n".join(lines).rstrip() + "\n"


def serialise(
    fmt: str,
    rows: Sequence[dict[str, Any]],
    *,
    title: str = "Niche Research export",
    columns: Sequence[str] | None = None,
    sections: Sequence[tuple[str, Sequence[dict[str, Any]]]] = (),
) -> str:
    """Serialise rows in the requested format."""
    fmt = (fmt or "").lower()
    if fmt == "csv":
        return to_csv(rows, columns)
    if fmt == "json":
        return to_json(rows)
    if fmt in ("markdown", "md"):
        return to_markdown(title, rows, columns, sections=sections)
    raise ValueError(f"Unknown export format: {fmt}")


def suggested_filename(base: str, fmt: str, *, today: str | None = None) -> str:
    """A dated default file name, e.g. ``niche-discovery-2026-10-20.csv``."""
    stamp = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    extension = {"markdown": "md", "md": "md"}.get(fmt, fmt)
    return f"{base}-{stamp}.{extension}"


def write_export(path: str, text: str) -> None:
    """Write the serialised text to disk (UTF-8, BOM for CSV)."""
    if path.lower().endswith(".csv"):
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(text)
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def rows_from(items: Iterable[Any]) -> list[dict[str, Any]]:
    """Normalise an iterable of dataclasses/dicts into plain dicts."""
    from dataclasses import asdict, is_dataclass

    out: list[dict[str, Any]] = []
    for item in items:
        if is_dataclass(item) and not isinstance(item, type):
            out.append(asdict(item))
        elif isinstance(item, dict):
            out.append(dict(item))
    return out
