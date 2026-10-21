"""Export helpers for the Niche Research pages.

Three formats, one entry point:

* **CSV** — a flat table for spreadsheets (UTF-8 with BOM so Excel opens it).
* **JSON** — full fidelity, nested structures kept as they are.
* **Markdown** — a human-readable report (a title, a generated-at line and
  tables), used for the AI analysis pages.

Every format can carry the extra *sections* of a page (the Competitors page
has three groups, the analysis modal has ideas/scripts/blueprint), so no group
is silently dropped:

* CSV — one table with a leading ``section`` column; the main rows come first
  and every section follows, each row labelled with its group.
* JSON — ``{"rows": [...], "sections": {...}}`` when sections exist; a payload
  without sections stays a plain list so the single-group pages keep their
  old shape.
* Markdown — one titled table per section (unchanged).

The serialisers are pure functions so they can be tested without Qt.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import Any

# A cell starting with one of these is evaluated as a formula by Excel,
# LibreOffice and Google Sheets (CWE-1236 / CSV injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@")
# Characters that let a cell break out of a Markdown table cell and inject
# HTML or a link into the generated report.
_MD_ESCAPES = ("<", ">", "`", "[", "]")


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


def _csv_cell(value: Any) -> str:
    """Render one cell value as text, neutralising spreadsheet formulas.

    CSV quoting does not stop a spreadsheet from evaluating a cell that starts
    with ``=``/``+``/``-``/``@`` (or a tab/CR/LF), and the values come from
    attacker-controlled data (channel titles, video titles, autocomplete
    terms).  A leading single quote makes the spreadsheet treat the cell as
    text — the standard CSV-injection defence.
    """
    text = _flatten(value)
    if text.startswith(("\t", "\r", "\n")) or text[:1] in _FORMULA_PREFIXES:
        return "'" + text
    return text


def _column_order(rows: Iterable[dict[str, Any]]) -> list[str]:
    """The union of the row keys, in first-seen order."""
    seen: list[str] = []
    for row in rows:
        for key in row:
            if key not in seen:
                seen.append(key)
    return seen


def _split_sections(
    rows: Sequence[dict[str, Any]],
    sections: Sequence[tuple[str, Sequence[dict[str, Any]]]],
) -> tuple[str, list[dict[str, Any]], list[tuple[str, list[dict[str, Any]]]]]:
    """Split the main rows from the named sections.

    Some pages (the Competitors page) hand the *same* list to the exporter
    twice: once as the main rows and once as the first named section.  The
    main group is therefore matched against the sections by content: the
    matching section supplies the label and is not written a second time.
    """
    main_rows = list(rows)
    remaining = [(name, list(section_rows)) for name, section_rows in sections]
    for index, (name, section_rows) in enumerate(remaining):
        if section_rows == main_rows:
            return name, main_rows, remaining[:index] + remaining[index + 1 :]
    return "Main", main_rows, remaining


def to_csv(
    rows: Sequence[dict[str, Any]],
    columns: Sequence[str] | None = None,
    *,
    sections: Sequence[tuple[str, Sequence[dict[str, Any]]]] = (),
) -> str:
    """Serialise rows (and optional extra sections) to CSV text.

    ``columns`` fixes the column order; without it the union of the row keys
    is used (first-seen order).  With ``sections`` the table grows a leading
    ``section`` column: the main rows come first, then the rows of every
    section, each row labelled with the group it belongs to.  A main group
    that is also passed as a section is labelled with that section's name and
    written only once.
    """
    if not sections:
        if not rows:
            return ""
        cols = list(columns) if columns is not None else _column_order(rows)
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(cols)
        for row in rows:
            writer.writerow([_csv_cell(row.get(col)) for col in cols])
        return buffer.getvalue()

    label, main_rows, extra = _split_sections(rows, sections)
    groups: list[tuple[str, list[dict[str, Any]]]] = [(label, main_rows)]
    groups.extend((name, section_rows) for name, section_rows in extra if section_rows)
    all_rows = [row for _name, group_rows in groups for row in group_rows]
    if not all_rows:
        return ""
    if columns is None:
        cols = _column_order(all_rows)
    else:
        cols = list(columns)
        for key in _column_order(all_rows):
            if key not in cols:
                cols.append(key)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["section", *cols])
    for group_label, group_rows in groups:
        for row in group_rows:
            writer.writerow(
                [_csv_cell(group_label), *(_csv_cell(row.get(col)) for col in cols)]
            )
    return buffer.getvalue()


def to_json(
    rows: Any,
    *,
    sections: Sequence[tuple[str, Sequence[dict[str, Any]]]] = (),
) -> str:
    """Serialise rows (or any JSON-able payload) to pretty JSON text.

    With ``sections`` the payload becomes ``{"rows": [...], "sections": {...}}``
    so every group survives the export; without them the payload stays a
    plain list, as the single-group pages expect.

    The sections keep their names even when a page hands the same group as the
    main rows (the Competitors page does): the JSON is keyed, so the extra
    copy is unambiguous and nothing is lost.
    """
    if not sections:
        return json.dumps(rows, ensure_ascii=False, indent=2, default=str)
    main = list(rows) if isinstance(rows, (list, tuple)) else rows
    payload = {
        "rows": main,
        "sections": {name: list(section_rows) for name, section_rows in sections},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _md_cell(value: Any) -> str:
    """Render one cell value as text, safe to drop into a Markdown table.

    Pipes and newlines break the table; ``<``, ``>``, a backtick and the
    square brackets let a title inject HTML or a ``](javascript:…)`` link into
    the report.
    """
    text = _flatten(value).replace("|", "\\|").replace("\n", " ")
    for char in _MD_ESCAPES:
        text = text.replace(char, "\\" + char)
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
    """Serialise rows in the requested format.

    ``sections`` are the extra groups of a page; every format keeps them.
    """
    fmt = (fmt or "").lower()
    if fmt == "csv":
        return to_csv(rows, columns, sections=sections)
    if fmt == "json":
        return to_json(rows, sections=sections)
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
