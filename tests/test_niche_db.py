"""Tests for the Niche Research SQLite persistence layer."""

import pytest

from s_q_ali_media_downloader.niche_research.storage import db


@pytest.fixture(autouse=True)
def _isolated_db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


def test_schema_creates_all_tables():
    conn = db._connect()
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    expected = {
        "settings",
        "keywords",
        "keyword_snapshots",
        "channels",
        "channel_snapshots",
        "videos",
        "video_snapshots",
        "tracked_items",
        "rankings",
        "trending_channels",
        "discovery_log",
        "similar_channel_analysis",
        "channel_content_ideas",
        "channel_scripts",
        "channel_growth_blueprints",
    }
    assert expected <= tables
    conn.close()


def test_settings_roundtrip():
    db.set_setting("youtube_api_key", "AIzaSyABC")
    assert db.get_setting("youtube_api_key") == "AIzaSyABC"


def test_settings_upsert():
    db.set_setting("theme", "dark")
    db.set_setting("theme", "light")
    rows = db.all("SELECT value FROM settings WHERE key = ?", ("theme",))
    assert len(rows) == 1
    assert rows[0]["value"] == "light"


def test_run_all_get():
    db.run(
        "INSERT INTO keywords (term, display_term, first_seen, last_checked) VALUES (?, ?, ?, ?)",
        ("skin care", "skin care", 1, 2),
    )
    row = db.get("SELECT * FROM keywords WHERE term = ?", ("skin care",))
    assert row is not None
    assert row["display_term"] == "skin care"
    assert db.get("SELECT * FROM keywords WHERE term = ?", ("missing",)) is None


def test_exec_many():
    db.exec_many(
        "INSERT INTO keyword_snapshots (term, ts, score) VALUES (?, ?, ?)",
        [("skin care", 1, 50), ("skin care", 2, 60)],
    )
    rows = db.all("SELECT term, ts, score FROM keyword_snapshots ORDER BY ts")
    assert len(rows) == 2
    assert rows[1]["score"] == 60


def test_trending_channels_insert():
    db.run(
        "INSERT INTO trending_channels (channel_id, title, category_name, discovered_at) "
        "VALUES (?, ?, ?, ?)",
        ("UCabc", "Channel", "tech", 42),
    )
    row = db.get("SELECT title FROM trending_channels WHERE channel_id = ?", ("UCabc",))
    assert row["title"] == "Channel"


def test_now_is_epoch_millis():
    value = db.now()
    assert isinstance(value, int)
    assert value > 1_600_000_000_000
