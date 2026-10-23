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


def _csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


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


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
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

