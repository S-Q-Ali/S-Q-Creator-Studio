"""Tests for the research dashboard data."""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.niche_research.research import dashboard_engine as de
from s_q_ali_media_downloader.niche_research.storage import db


@pytest.fixture(autouse=True)
def _db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


def _seed() -> None:
    db.run(
        "INSERT INTO trending_channels (channel_id, title, category_name, discovered_at, "
        "viral_score, subscriber_count, niche, video_format) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("UCa", "Alpha", "Tech", 1, 90, 1000, "tech_ai", "longform"),
    )
    db.run(
        "INSERT INTO trending_channels (channel_id, title, category_name, discovered_at, "
        "viral_score, subscriber_count, niche, video_format) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("UCb", "Beta", "Tech", 1, 40, 500, "tech_ai", "longform"),
    )
    db.run(
        "INSERT INTO keywords (term, display_term, score, demand_score, competition_score, "
        "competition_label, source, first_seen, last_checked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ai tools", "AI Tools", 82, 90, 25, "Low", "search", db.now(), db.now()),
    )
    db.run(
        "INSERT INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        ("video", "v1", "V", db.now()),
    )
    db.run(
        "INSERT INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        ("keyword", "ai tools", "AI Tools", db.now()),
    )
    db.run(
        "INSERT INTO discovery_log (video_format, niche, channels_found, searches_used, "
        "discovered_at) VALUES (?, ?, ?, ?, ?)",
        ("longform", "tech_ai", 12, 3, 500),
    )
    db.run(
        "INSERT INTO keyword_snapshots (term, ts, demand_score, competition_score, score) "
        "VALUES (?, ?, ?, ?, ?)",
        ("ai tools", 700, 90, 25, 82),
    )


def test_metrics_count_everything():
    _seed()
    metrics = de.get_metrics()
    assert metrics["channelsDiscovered"] == 2
    assert metrics["keywordsResearched"] == 1
    assert metrics["trackedVideos"] == 1
    assert metrics["trackedKeywords"] == 1
    assert metrics["trackedChannels"] == 0
    assert metrics["bestViralScore"] == 90
    assert metrics["bestViralChannel"] == "Alpha"
    assert metrics["lastDiscoveryAt"] == 500


def test_metrics_of_an_empty_database():
    metrics = de.get_metrics()
    assert metrics["channelsDiscovered"] == 0
    assert metrics["bestViralScore"] == 0
    assert metrics["bestViralChannel"] == ""


def test_top_channels_are_ranked():
    _seed()
    top = de.get_top_channels()
    assert top[0]["title"] == "Alpha"
    assert top[0]["viral_score"] == 90


def test_top_keywords_are_ranked():
    _seed()
    top = de.get_top_keywords()
    assert top[0]["display_term"] == "AI Tools"


def test_activity_is_newest_first():
    _seed()
    activity = de.get_activity()
    assert activity
    assert activity[0]["ts"] >= activity[-1]["ts"]
    kinds = {e["kind"] for e in activity}
    assert "discovery" in kinds
    assert "keyword" in kinds


def test_dashboard_data_has_every_section():
    _seed()
    data = de.get_dashboard_data()
    assert set(data) == {"metrics", "topChannels", "topKeywords", "activity"}
