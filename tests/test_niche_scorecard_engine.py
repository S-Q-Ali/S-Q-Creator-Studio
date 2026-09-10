"""Tests for the scorecard + VPH engine (ported from scorecard.ts / vphEngine.ts)."""

from datetime import datetime, timedelta, timezone

import pytest

from s_q_ali_media_downloader.niche_research.research import scorecard_engine as se
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.youtube_client import ChannelInfo, VideoInfo


# --------------------------------------------------------------------------- #
# Pure scorers
# --------------------------------------------------------------------------- #
def test_score_char_ramp():
    assert se.score_char(40, 20, 40) == 100
    assert se.score_char(4, 20, 40) == 0  # good/5 = 4
    assert se.score_char(20, 20, 40) == 50
    assert se.score_char(200, 20, 40) == 100


def test_contains_keyword():
    assert se.contains_keyword("10 AI Tools That Work", "ai tools") is True
    assert se.contains_keyword("10 AI Tools That Work", "gadgets") is False
    assert se.contains_keyword("Cooking Basics", "cooking for beginners") is True  # word match
    assert se.contains_keyword("", "") is False


def test_score_label_letters():
    assert se.score_label(95) == "A"
    assert se.score_label(85) == "B"
    assert se.score_label(75) == "C"
    assert se.score_label(60) == "D"
    assert se.score_label(45) == "E"
    assert se.score_label(20) == "F"


def test_save_channel_snapshot_keeps_unknown_counts_null():
    db.configure(None)
    channel = ChannelInfo(channel_id="UCxyz", video_count=0, view_count=0, subscriber_count=1000)
    se.save_channel_snapshot(channel)
    row = db.get(
        "SELECT subscriber_count, video_count, view_count FROM channels WHERE channel_id = ?",
        ("UCxyz",),
    )
    assert row is not None
    assert row["subscriber_count"] == 1000
    assert row["video_count"] is None  # unknown, not a fabricated 0
    assert row["view_count"] is None  # unknown, not a fabricated 0
    db.close_db()


def test_save_channel_snapshot_keeps_real_counts():
    db.configure(None)
    channel = ChannelInfo(
        channel_id="UCxyz2", subscriber_count=1000, video_count=42, view_count=7_000_000
    )
    se.save_channel_snapshot(channel)
    row = db.get(
        "SELECT subscriber_count, video_count, view_count FROM channels WHERE channel_id = ?",
        ("UCxyz2",),
    )
    assert row == {"subscriber_count": 1000, "video_count": 42, "view_count": 7_000_000}
    db.close_db()


def test_seo_full_video():
    result = se.compute_seo_score(
        {
            "title": "10 Best AI Tools You Need in 2026",
            "description": "AI Tools " + "x" * 300,
            "tags": ["ai tools", "ai", "tools", "tech", "learning"],
            "view_count": 100_000,
            "like_count": 6_000,
            "comment_count": 2_000,
            "published_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "focus_keyword": "ai tools",
        }
    )
    ids = [c.id for c in result.checks]
    assert "keywordTitle" in ids and "tripleKeyword" in ids
    title_c = next(c for c in result.checks if c.id == "titleLength")
    assert title_c.passed is True
    desc_c = next(c for c in result.checks if c.id == "descriptionLength")
    assert desc_c.passed is True
    tags_c = next(c for c in result.checks if c.id == "tagCount")
    assert tags_c.passed is True
    assert 0 <= result.total <= 100
    actionable = next(c for c in result.checks if c.id == "titleLength")
    assert actionable.score == 100
    assert result.actionable_pct == 100  # all on-page checks perfect
    assert result.performance_pct >= 50  # strong engagement + velocity


def test_seo_without_keyword_no_keyword_checks():
    result = se.compute_seo_score(
        {
            "title": "Short",
            "description": "",
            "tags": [],
            "view_count": 10,
            "like_count": 0,
            "comment_count": 0,
            "published_at": "",
        }
    )
    ids = [c.id for c in result.checks]
    assert "keywordTitle" not in ids
    assert result.total < 10  # nearly nothing scored
    titles = next(c for c in result.checks if c.id == "titleLength")
    assert titles.passed is False


def test_engagement_scoring():
    result = se.compute_seo_score(
        {
            "title": "x" * 30,
            "description": "y" * 300,
            "tags": ["a", "b", "c", "d", "e"],
            "view_count": 100,
            "like_count": 5,  # 5% likes target
            "comment_count": 1,  # 1% comments target
            "published_at": "2026-09-01T00:00:00Z",
        }
    )
    eng = next(c for c in result.checks if c.id == "engagement")
    assert eng.score == 100


def test_velocity_views_per_day():
    # 100k views / 100 days = 1000/day -> velocity = 20
    result = se.compute_seo_score(
        {
            "title": "z" * 30,
            "description": "z",
            "tags": [],
            "view_count": 100_000,
            "like_count": 0,
            "comment_count": 0,
            "published_at": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(),
        }
    )
    vel = next(c for c in result.checks if c.id == "velocity")
    assert 15 <= vel.score <= 25


def test_channel_seo_score():
    channel = ChannelInfo(
        channel_id="UCc",
        title="My Tech Channel",
        description="Long description about technology.",
        channel_tags=["tech", "ai", "gadgets"],
        subscriber_count=50_000,
    )
    result = se.compute_channel_seo_score(channel)
    assert 0 <= result.total <= 100
    ids = [c.id for c in result.checks]
    # channel has no keyword, but velocity is fed by the subscriber count
    assert "velocity" in ids


# --------------------------------------------------------------------------- #
# VPH
# --------------------------------------------------------------------------- #
def test_vph_requires_two_snapshots(isolated_appdata):
    db.configure(None)
    v = se.compute_vph("video-1")
    assert v.vph is None
    assert v.error
    assert v.points == []
    db.close_db()


def test_vph_computes_delta(isolated_appdata):
    db.configure(None)
    now_ms = 1_750_000_000_000
    db.run(
        """
        INSERT INTO video_snapshots (video_id, ts, view_count, like_count, comment_count)
        VALUES ('v1', ?, 1000, 10, 1), ('v1', ?, 2000, 20, 2)
        """,
        (now_ms - 7_200_000, now_ms),
    )
    v = se.compute_vph("v1")
    assert v.vph is not None
    assert v.window_hours == 2.0
    assert v.vph == 500.0  # (2000-1000) / 2h
    assert len(v.points) == 2
    db.close_db()


def test_vph_too_short_window(isolated_appdata):
    db.configure(None)
    now_ms = 1_750_000_000_000
    db.run(
        """
        INSERT INTO video_snapshots (video_id, ts, view_count, like_count, comment_count)
        VALUES ('v2', ?, 1000, 0, 0), ('v2', ?, 1100, 0, 0)
        """,
        (now_ms - 600_000, now_ms),
    )
    v = se.compute_vph("v2")
    assert v.vph is None
    assert "1 hour" in v.error
    db.close_db()


# --------------------------------------------------------------------------- #
# Lookups (no network — fakes)
# --------------------------------------------------------------------------- #
def test_lookup_video_flow(isolated_appdata, monkeypatch):
    db.configure(None)

    def fake_parse_video_id(url):
        return "vid123" if "watch" in url else None

    def fake_fetch_video(video_id, cookiefile=None):
        assert video_id == "vid123"
        return VideoInfo(
            video_id="vid123",
            channel_id="UCchan",
            channel_title="Chan",
            title="Great Video About Ai Tools",
            description="An awesome description " * 10,
            published_at="2026-08-20T10:00:00Z",
            duration_seconds=612,
            thumbnail_url="https://img/t.jpg",
            view_count=50_000,
            like_count=3_000,
            comment_count=900,
            tags=["ai", "tools", "great", "five"],
        )

    def fake_fetch_channel(channel_id, cookiefile=None):
        return ChannelInfo(channel_id=channel_id, title="Chan", thumbnail_url="https://img/c.jpg")

    monkeypatch.setattr(se, "parse_video_id", fake_parse_video_id)
    monkeypatch.setattr(se, "fetch_video", fake_fetch_video)
    monkeypatch.setattr(se, "fetch_channel", fake_fetch_channel)

    result = se.lookup_video("https://youtube.com/watch?v=vid123")
    assert result.kind == "video"
    assert result.video["video_id"] == "vid123"
    assert result.video["view_count"] == 50_000
    assert result.channel["channel_id"] == "UCchan"
    assert result.seo.total > 0
    assert result.vph.vph is None  # only one snapshot so far
    assert result.tracked is False

    # snapshot recorded
    snaps = se.get_video_snapshots("vid123")
    assert len(snaps) == 1
    assert snaps[0]["viewCount"] == 50_000
    db.close_db()


def test_lookup_video_raises_on_bad_url(isolated_appdata, monkeypatch):
    db.configure(None)

    def fake_parse_video_id(url):
        return None

    monkeypatch.setattr(se, "parse_video_id", fake_parse_video_id)
    with pytest.raises(ValueError):
        se.lookup_video("not a url")
    db.close_db()


def test_lookup_channel_flow(isolated_appdata, monkeypatch):
    db.configure(None)

    def fake_parse_channel_id(url):
        return "UCchan" if "channel" in url else None

    def fake_fetch_channel(channel_id, cookiefile=None):
        return ChannelInfo(
            channel_id=channel_id,
            title="My Channel",
            description="desc",
            thumbnail_url="https://img/c.jpg",
            subscriber_count=123_456,
            video_count=200,
            view_count=50_000_000,
            channel_tags=["tech"],
            uploads=[
                {"video_id": "u1", "title": "First", "upload_date": "20260901", "view_count": 500},
                {"video_id": "u2", "title": "Second", "upload_date": "20260825", "view_count": 300},
            ],
        )

    monkeypatch.setattr(se, "parse_channel_id", fake_parse_channel_id)
    monkeypatch.setattr(se, "fetch_channel", fake_fetch_channel)

    result = se.lookup_channel("https://youtube.com/channel/UCchan")
    assert result.kind == "channel"
    assert result.channel["subscriber_count"] == 123_456
    assert result.seo.total > 0
    assert len(result.recent_videos) == 2
    assert result.recent_videos[0]["published_at"].startswith("2026-09-01")
    # channel snapshot recorded
    rows = db.all("SELECT * FROM channel_snapshots WHERE channel_id=?", ("UCchan",))
    assert len(rows) == 1
    db.close_db()


def test_lookup_channel_handle_url_passthrough(isolated_appdata, monkeypatch):
    db.configure(None)

    def fake_parse_channel_id(url):
        return None

    def fake_fetch_channel(channel_id, cookiefile=None):
        assert channel_id == "https://www.youtube.com/@MrBeast"
        return ChannelInfo(channel_id="UCmrbeast", title="MrBeast", subscriber_count=1)

    monkeypatch.setattr(se, "parse_channel_id", fake_parse_channel_id)
    monkeypatch.setattr(se, "fetch_channel", fake_fetch_channel)

    result = se.lookup_channel("https://www.youtube.com/@MrBeast")
    assert result.channel["title"] == "MrBeast"
    rows = db.all("SELECT * FROM channels WHERE channel_id=?", ("UCmrbeast",))
    assert len(rows) == 1
    db.close_db()


def test_save_video_snapshot_idempotent(isolated_appdata):
    db.configure(None)
    video = VideoInfo(video_id="vidX", title="T", view_count=10, like_count=1, comment_count=0)
    se.save_video_snapshot(video)
    se.save_video_snapshot(video)
    rows = db.all("SELECT * FROM video_snapshots WHERE video_id='vidX'")
    assert len(rows) == 2  # one snapshot per call, timestamp differs
    db.close_db()
