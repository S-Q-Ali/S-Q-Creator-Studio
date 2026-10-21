"""Tests for the research exporter (CSV / JSON / Markdown)."""

from __future__ import annotations

import json

from s_q_ali_media_downloader.niche_research.tools import exporter

ROWS = [
    {"title": "First video", "views": 1200, "channel": "Chan A"},
    {"title": "Second, video", "views": 34, "channel": "Chan B"},
]


def test_to_csv_has_a_header_and_one_row_per_item():
    text = exporter.to_csv(ROWS)
    lines = text.strip().splitlines()
    assert lines[0] == "title,views,channel"
    assert len(lines) == 3
    assert lines[1] == "First video,1200,Chan A"


def test_to_csv_quotes_commas_and_keeps_the_column_order():
    text = exporter.to_csv(ROWS, columns=["channel", "title"])
    lines = text.strip().splitlines()
    assert lines[0] == "channel,title"
    assert lines[2] == 'Chan B,"Second, video"'


def test_to_csv_of_nothing_is_empty():
    assert exporter.to_csv([]) == ""


def test_to_json_keeps_the_structure():
    text = exporter.to_json(ROWS)
    parsed = json.loads(text)
    assert parsed[0]["views"] == 1200
    assert parsed[1]["channel"] == "Chan B"


def test_to_markdown_writes_a_table():
    text = exporter.to_markdown("Discovery", ROWS)
    assert text.startswith("# Discovery")
    assert "| title | views | channel |" in text
    assert "First video" in text


def test_to_markdown_escapes_pipes():
    rows = [{"title": "a | b", "views": 1}]
    text = exporter.to_markdown("T", rows)
    assert "a \\| b" in text


def test_to_markdown_includes_extra_sections():
    text = exporter.to_markdown(
        "Analysis",
        ROWS,
        sections=[("Content ideas", [{"title": "Idea one"}])],
    )
    assert "## Content ideas" in text
    assert "Idea one" in text


def test_serialise_rejects_an_unknown_format():
    try:
        exporter.serialise("pdf", ROWS)
    except ValueError as exc:
        assert "pdf" in str(exc)
    else:  # pragma: no cover - the call must raise
        raise AssertionError("unknown format must raise")


def test_suggested_filename_is_dated():
    name = exporter.suggested_filename("niche-discovery", "csv", today="2026-10-20")
    assert name == "niche-discovery-2026-10-20.csv"
    md = exporter.suggested_filename("analysis", "markdown", today="2026-10-20")
    assert md == "analysis-2026-10-20.md"


def test_write_export_adds_a_bom_for_csv(tmp_path):
    path = tmp_path / "out.csv"
    exporter.write_export(str(path), exporter.to_csv(ROWS))
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "First video" in raw.decode("utf-8-sig")


def test_write_export_for_json(tmp_path):
    path = tmp_path / "out.json"
    exporter.write_export(str(path), exporter.to_json(ROWS))
    assert json.loads(path.read_text(encoding="utf-8"))[0]["title"] == "First video"


def test_rows_from_handles_dicts_and_dataclasses():
    from dataclasses import dataclass

    @dataclass
    class Row:
        a: int
        b: str

    rows = exporter.rows_from([Row(1, "x"), {"a": 2, "b": "y"}])
    assert rows == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
