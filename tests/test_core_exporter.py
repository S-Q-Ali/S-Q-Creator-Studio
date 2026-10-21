"""Tests for the research exporter (CSV / JSON / Markdown)."""

from __future__ import annotations

import csv
import io
import json

import pytest

from s_q_ali_media_downloader.core import exporter

ROWS = [
    {"title": "First video", "views": 1200, "channel": "Chan A"},
    {"title": "Second, video", "views": 34, "channel": "Chan B"},
]

# The Competitors page hands the first group to the exporter twice: once as the
# main rows and once as the first named section.
COMPETITOR_VIDEOS = [{"title": "Video one", "views": 10, "thumbnailUrl": "t1"}]
COMPETITOR_CHANNELS = [{"title": "Channel one", "subscribers": 500}]
COMPETITOR_KEYWORDS = [{"keyword": "ai tools", "score": 42}]
COMPETITOR_SECTIONS = [
    ("Tracked videos", COMPETITOR_VIDEOS),
    ("Tracked channels", COMPETITOR_CHANNELS),
    ("Tracked keywords", COMPETITOR_KEYWORDS),
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


# --------------------------------------------------------------------------- #
# Regression (2026-10): CSV / JSON dropped every section but the first
# --------------------------------------------------------------------------- #
def _csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def test_to_csv_keeps_every_section():
    """The Competitors export used to keep 1 of 3 groups in CSV."""
    text = exporter.to_csv(COMPETITOR_VIDEOS, sections=COMPETITOR_SECTIONS)
    table = _csv_rows(text)

    assert table[0][0] == "section"
    body = table[1:]
    # every group is in the file, labelled
    labels = [row[0] for row in body]
    assert "Tracked videos" in labels
    assert "Tracked channels" in labels
    assert "Tracked keywords" in labels
    # the data of every group is in the file
    flat = "\n".join(",".join(row) for row in body)
    assert "Video one" in flat
    assert "Channel one" in flat
    assert "ai tools" in flat


def test_to_csv_does_not_duplicate_the_main_group():
    """The main rows are the first group; they must not be written twice."""
    text = exporter.to_csv(COMPETITOR_VIDEOS, sections=COMPETITOR_SECTIONS)
    body = _csv_rows(text)[1:]

    video_rows = [row for row in body if row[1] == "Video one"]
    assert len(video_rows) == 1
    assert video_rows[0][0] == "Tracked videos"


def test_to_csv_without_sections_keeps_its_old_shape():
    text = exporter.to_csv(ROWS)
    lines = text.strip().splitlines()
    assert lines[0] == "title,views,channel"
    assert len(lines) == 3


def test_to_json_keeps_every_section():
    text = exporter.to_json(COMPETITOR_VIDEOS, sections=COMPETITOR_SECTIONS)
    parsed = json.loads(text)

    assert parsed["rows"][0]["title"] == "Video one"
    assert set(parsed["sections"]) == {
        "Tracked videos",
        "Tracked channels",
        "Tracked keywords",
    }
    assert parsed["sections"]["Tracked channels"][0]["title"] == "Channel one"
    assert parsed["sections"]["Tracked keywords"][0]["keyword"] == "ai tools"


def test_to_json_without_sections_stays_a_plain_list():
    """The other four pages export a single group; their shape must not change."""
    parsed = json.loads(exporter.to_json(ROWS))
    assert isinstance(parsed, list)
    assert parsed[0]["title"] == "First video"
    assert parsed[1]["channel"] == "Chan B"


def test_serialise_forwards_the_sections_to_csv_and_json():
    csv_text = exporter.serialise("csv", COMPETITOR_VIDEOS, sections=COMPETITOR_SECTIONS)
    assert "Channel one" in csv_text
    assert "ai tools" in csv_text

    json_text = exporter.serialise("json", COMPETITOR_VIDEOS, sections=COMPETITOR_SECTIONS)
    parsed = json.loads(json_text)
    assert parsed["sections"]["Tracked keywords"][0]["keyword"] == "ai tools"


# --------------------------------------------------------------------------- #
# Regression (2026-10): CSV formula injection (CWE-1236)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "prefix",
    ["=", "+", "-", "@", "\t", "\r", "\n"],
)
def test_to_csv_neutralises_formula_prefixes(prefix):
    """A channel title must never become a spreadsheet formula."""
    rows = [{"title": prefix + "HYPERLINK(\"http://evil.tld\",\"Click\")"}]
    text = exporter.to_csv(rows)

    value = _csv_rows(text)[1][0]
    assert value.startswith("'"), value
    assert value[1:] == prefix + "HYPERLINK(\"http://evil.tld\",\"Click\")"


def test_to_csv_leaves_harmless_values_alone():
    text = exporter.to_csv([{"title": "Finance", "views": 1200}])
    table = _csv_rows(text)
    assert table[1][0] == "Finance"
    assert table[1][1] == "1200"


def test_to_json_does_not_touch_formula_text():
    """json.dumps escapes properly; the JSON output must stay untouched."""
    parsed = json.loads(exporter.to_json([{"title": "=1+1"}]))
    assert parsed[0]["title"] == "=1+1"


def test_to_markdown_escapes_html_and_link_injection():
    title = "<script>alert(1)</script> `code` [click](javascript:alert(1))"
    text = exporter.to_markdown("T", [{"title": title}])

    assert "<script>" not in text
    for char in "<>`[]":
        assert text.count(char) == text.count("\\" + char), char

