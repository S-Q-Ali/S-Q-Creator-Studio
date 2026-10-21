"""Tests for the competitor dashboard + snapshot refresh engine."""

from __future__ import annotations

import time

import pytest

from s_q_ali_media_downloader.niche_research.research import competitor_engine as ce
from s_q_ali_media_downloader.niche_research.storage import db


def _track(kind: str, ref_id: str, label: str | None = None) -> None:
    db.run(
        "INSERT OR IGNORE INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        (kind, ref_id, label or ref_id, db.now()),
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


@pytest.fixture(autouse=True)
def _configure_db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


# --------------------------------------------------------------------------- #
# Regression (2026-10): tracked items must show a real channel title
# --------------------------------------------------------------------------- #
def test_tracked_video_shows_the_channel_title(isolated_appdata):
    _track("video", "vid123", "My Vlog")
    db.run(
        """
        INSERT INTO videos (
            video_id, title, thumbnail_url, channel_id, channel_title,
            published_at, view_count, like_count, comment_count, last_fetched
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "vid123",
            "My Vlog",
            "http://x/thumb.jpg",
            "chan1",
            "Chan One",
            "2026-01-01",
            1_000,
            10,
            1,
            db.now(),
        ),
    )

    videos = ce.get_tracked_videos()

    assert videos[0]["channelTitle"] == "Chan One"


def test_tracked_keyword_ranked_videos_show_the_channel_title(isolated_appdata):
    _track("keyword", "ai tools", "AI Tools")
    db.run(
        """
        INSERT INTO keywords (
            term, display_term, score, demand_score, competition_score,
            competition_label, source, first_seen, last_checked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("ai tools", "AI Tools", 82, 90, 25, "Low", "search", db.now(), db.now()),
    )
    db.run(
        "INSERT INTO rankings (term, video_id, position, ts) VALUES (?, ?, ?, ?)",
        ("ai tools", "vidA", 1, _now_ms()),
    )
    db.run(
        """
        INSERT INTO videos (video_id, title, channel_id, channel_title, view_count, last_fetched)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("vidA", "Some Video", "chanX", "Chan X", 500, db.now()),
    )

    keywords = ce.get_tracked_keywords()

    ranked = keywords[0]["rankedVideos"]
    assert ranked[0]["channelTitle"] == "Chan X"



def test_get_tracked_videos_includes_vph_series(isolated_appdata):
    _track("video", "vid123", "My Vlog")
    db.run(
        """
        INSERT INTO videos (
            video_id, title, thumbnail_url, channel_id, published_at,
            view_count, like_count, comment_count, last_fetched
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "vid123",
            "My Vlog",
            "http://x/thumb.jpg",
            "chan1",
            "2026-01-01",
            1_000_000,
            10_000,
            1_000,
            db.now(),
        ),
    )
    # One timestamp for both snapshots: two separate _now_ms() calls land a
    # millisecond apart on a slow machine, and the window is then 2h + 1ms
    # instead of exactly 2h — which made this test fail on CI.
    t_now = _now_ms()
    t_old = t_now - 2 * 3600 * 1000
    db.run(
        "INSERT INTO video_snapshots (video_id, ts, view_count, like_count, comment_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("vid123", t_old, 900_000, 9_000, 900),
    )
    db.run(
        "INSERT INTO video_snapshots (video_id, ts, view_count, like_count, comment_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("vid123", t_now, 1_000_000, 10_000, 1_000),
    )

    videos = ce.get_tracked_videos()
    assert len(videos) == 1
    v = videos[0]
    assert v["videoId"] == "vid123"
    assert v["title"] == "My Vlog"
    assert v["viewCount"] == 1_000_000
    assert v["vph"] == 50000.0  # 100k views / 2 hours
    assert len(v["series"]) == 2
    assert v["series"][0]["ts"] == t_old


def test_get_tracked_videos_empty(isolated_appdata):
    assert ce.get_tracked_videos() == []


def test_get_tracked_videos_single_snapshot_has_error(isolated_appdata):
    _track("video", "vid456")
    db.run(
        "INSERT INTO videos (video_id, title, view_count, last_fetched) VALUES (?, ?, ?, ?)",
        ("vid456", "Lonely", 500, db.now()),
    )
    db.run(
        "INSERT INTO video_snapshots (video_id, ts, view_count, like_count, comment_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("vid456", _now_ms(), 500, 0, 0),
    )
    v = ce.get_tracked_videos()[0]
    assert v["vph"] is None
    assert "two snapshots" in v["vphError"]


def test_get_tracked_channels_growth7d(isolated_appdata):
    _track("channel", "chan123", "Tech Channel")
    db.run(
        """
        INSERT INTO channels (
            channel_id, title, thumbnail_url, subscriber_count,
            video_count, view_count, last_fetched
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("chan123", "Tech Channel", "http://x/av.jpg", 120_000, 300, 40_000_000, db.now()),
    )
    # 7 days ago and yesterday (matches the .capitalize .32 growth)
    db.run(
        "INSERT INTO channel_snapshots (channel_id, ts, subscriber_count, video_count, view_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("chan123", _now_ms() - 6 * 24 * 3600 * 1000, 100_000, 290, 38_000_000),
    )
    db.run(
        "INSERT INTO channel_snapshots (channel_id, ts, subscriber_count, video_count, view_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("chan123", _now_ms() - 24 * 3600 * 1000, 120_000, 300, 40_000_000),
    )
    # Old snapshot outside the 7-day window must not be used as the base
    db.run(
        "INSERT INTO channel_snapshots (channel_id, ts, subscriber_count, video_count, view_count) "
        "VALUES (?, ?, ?, ?, ?)",
        ("chan123", _now_ms() - 30 * 24 * 3600 * 1000, 50_000, 200, 10_000_000),
    )

    channels = ce.get_tracked_channels()
    assert len(channels) == 1
    c = channels[0]
    assert c["subscriberCount"] == 120_000
    assert c["growth7d"] == 20_000  # latest 120k - oldest in window 100k
    assert c["series"][-1]["value"] == 120_000


def test_get_tracked_channels_no_growth(isolated_appdata):
    _track("channel", "chan999")
    db.run(
        "INSERT INTO channels (channel_id, title, subscriber_count, last_fetched) "
        "VALUES (?, ?, ?, ?)",
        ("chan999", "Empty", 10, db.now()),
    )
    c = ce.get_tracked_channels()[0]
    assert c["growth7d"] is None


def test_get_tracked_keywords_series_and_rankings(isolated_appdata):
    _track("keyword", "ai tools", "AI Tools")
    db.run(
        """
        INSERT INTO keywords (
            term, display_term, score, demand_score, competition_score,
            competition_label, source, first_seen, last_checked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("ai tools", "AI Tools", 82, 90, 25, "Low", "search", db.now(), db.now()),
    )
    db.run(
        "INSERT INTO keyword_snapshots (term, ts, demand_score, competition_score, score) "
        "VALUES (?, ?, ?, ?, ?)",
        ("ai tools", _now_ms() - 3600 * 1000, 90, 25, 82),
    )
    db.run(
        "INSERT INTO keyword_snapshots (term, ts, demand_score, competition_score, score) "
        "VALUES (?, ?, ?, ?, ?)",
        ("ai tools", _now_ms(), 90, 25, 84),
    )
    db.run(
        "INSERT INTO rankings (term, video_id, position, ts) VALUES (?, ?, ?, ?)",
        ("ai tools", "vidA", 1, _now_ms()),
    )
    db.run(
        "INSERT INTO rankings (term, video_id, position, ts) VALUES (?, ?, ?, ?)",
        ("ai tools", "vidB", 2, _now_ms() - 3600 * 1000),
    )
    db.run(
        "INSERT INTO videos (video_id, title, view_count, last_fetched) VALUES (?, ?, ?, ?)",
        ("vidA", "Best AI tools 2026", 5000, db.now()),
    )
    db.run(
        "INSERT INTO videos (video_id, title, view_count, last_fetched) VALUES (?, ?, ?, ?)",
        ("vidB", "Old ranking video", 5000, db.now()),
    )

    keywords = ce.get_tracked_keywords()
    assert len(keywords) == 1
    k = keywords[0]
    assert k["displayTerm"] == "AI Tools"
    assert k["score"] == 82
    assert len(k["series"]) == 2
    assert k["series"][-1]["value"] == 84
    # Only the latest-rank batch (ts = MAX) appears
    assert len(k["rankedVideos"]) == 1
    assert k["rankedVideos"][0]["videoId"] == "vidA"
    assert k["rankedVideos"][0]["title"] == "Best AI tools 2026"
    assert k["rankedVideos"][0]["position"] == 1


def test_get_competitor_dashboard_aggregates(isolated_appdata):
    _track("video", "vidA")
    _track("channel", "chanA")
    _track("keyword", "termA")
    db.run(
        "INSERT INTO videos (video_id, title, view_count, last_fetched) VALUES (?, ?, ?, ?)",
        ("vidA", "V", 10, db.now()),
    )
    db.run(
        "INSERT INTO channels (channel_id, title, subscriber_count, last_fetched) VALUES (?, ?, ?, ?)",
        ("chanA", "C", 5, db.now()),
    )
    db.run(
        "INSERT INTO keywords (term, display_term, score, demand_score, competition_score, competition_label, source, first_seen, last_checked) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("termA", "Term A", 70, 80, 30, "Medium", "search", db.now(), db.now()),
    )
    dash = ce.get_competitor_dashboard()
    assert len(dash["videos"]) == 1
    assert len(dash["channels"]) == 1
    assert len(dash["keywords"]) == 1


def test_refresh_snapshots_snapshots_all_kinds(isolated_appdata, monkeypatch):
    _track("video", "vidA", "Video A")
    _track("channel", "chanB", "Channel B")
    _track("keyword", "termC", "Term C")

    called_videos: list[str] = []
    called_channels: list[str] = []

    def fake_fetch_video(video_id, cookiefile=None):
        called_videos.append(video_id)
        return _video(video_id)

    def fake_fetch_channel(channel_id, cookiefile=None, **kwargs):
        called_channels.append(channel_id)
        return _channel(channel_id)

    def fake_rank_keyword(term, opts=None):
        assert opts is not None and opts.force_refresh

    monkeypatch.setattr(ce, "fetch_video", fake_fetch_video)
    monkeypatch.setattr(ce, "fetch_channel", fake_fetch_channel)
    monkeypatch.setattr(ce, "rank_keyword", fake_rank_keyword)
    monkeypatch.setattr(
        ce.se,
        "save_video_snapshot",
        lambda video: db.run(
            "INSERT OR IGNORE INTO video_snapshots "
            "(video_id, ts, view_count, like_count, comment_count) VALUES (?, ?, ?, ?, ?)",
            (video.video_id, db.now(), video.view_count, video.like_count, video.comment_count),
        ),
    )
    monkeypatch.setattr(
        ce.se,
        "save_channel_snapshot",
        lambda channel: db.run(
            "INSERT OR IGNORE INTO channel_snapshots "
            "(channel_id, ts, subscriber_count, video_count, view_count) VALUES (?, ?, ?, ?, ?)",
            (
                channel.channel_id,
                db.now(),
                channel.subscriber_count,
                channel.video_count,
                channel.view_count,
            ),
        ),
    )

    progress: list[str] = []
    counts = ce.refresh_snapshots(progress=progress.append)

    assert counts["videos"] == 1
    assert counts["channels"] == 1
    assert counts["keywords"] == 1
    assert counts["failed"] == 0
    assert called_videos == ["vidA"]
    assert called_channels == ["chanB"]
    assert progress  # progress fired at least once


def test_refresh_snapshots_counts_failures(isolated_appdata, monkeypatch):
    """A tracked item that cannot be fetched must be reported, not silently
    skipped."""
    _track("video", "vidA", "Video A")
    _track("video", "vidB", "Video B")

    def boom(video_id, cookiefile=None):
        if video_id == "vidB":
            raise RuntimeError("gone")
        return _video(video_id)

    monkeypatch.setattr(ce, "fetch_video", boom)

    counts = ce.refresh_snapshots()

    assert counts["videos"] == 1
    assert counts["failed"] == 1
    assert counts["failures"]["videos"] == 1


def test_snapshot_interval_setting(isolated_appdata):
    db.set_setting("snapshot_interval_minutes", "30")
    assert ce.snapshot_interval_minutes() == 30
    db.set_setting("snapshot_interval_minutes", "nonsense")
    assert ce.snapshot_interval_minutes() == 60
    db.set_setting("snapshot_interval_minutes", "180")
    assert ce.snapshot_interval_minutes() == 180


# --------------------------------------------------------------------------- #
# The canonical tracked-items helpers
# --------------------------------------------------------------------------- #
def test_track_item_reports_whether_it_was_new(isolated_appdata):
    assert ce.track_item("video", "vid1", "A Video") is True
    assert ce.is_tracked("video", "vid1") is True
    # Tracking it again is a no-op, but the helper says so.
    assert ce.track_item("video", "vid1", "A Video") is False


def test_untrack_item_removes_the_item(isolated_appdata):
    ce.track_item("channel", "chan1", "A Channel")
    ce.untrack_item("channel", "chan1")
    assert ce.is_tracked("channel", "chan1") is False


def test_track_item_ignores_an_empty_ref_id(isolated_appdata):
    assert ce.track_item("video", "", "Nothing") is False
    assert ce.is_tracked("video", "") is False


def _video(video_id: str):
    from s_q_ali_media_downloader.niche_research.tools.youtube_client import VideoInfo

    return VideoInfo(
        video_id=video_id,
        title="T",
        channel_id="ch",
        description="",
        published_at="2026-01-01T00:00:00Z",
        duration_seconds=60,
        thumbnail_url="",
        language=None,
        view_count=100,
        like_count=10,
        comment_count=1,
        tags=None,
        category_id=None,
    )


def _channel(channel_id: str):
    from s_q_ali_media_downloader.niche_research.tools.youtube_client import ChannelInfo

    return ChannelInfo(
        channel_id=channel_id,
        title="C",
        description="",
        thumbnail_url="",
        custom_url="",
        country="",
        publish_date="",
        subscriber_count=1_000,
        video_count=10,
        view_count=50_000,
        channel_tags=None,
        topic_categories=None,
        uploads=[],
    )


# --------------------------------------------------------------------------- #
# Regression (2026-10): a snapshot refresh must be stoppable
# --------------------------------------------------------------------------- #
def test_refresh_snapshots_stops_when_cancelled(monkeypatch):
    """The refresh runs one network request per tracked item; cancelling
    between items keeps the worker responsive."""
    from s_q_ali_media_downloader.niche_research.tools.youtube_client import VideoInfo

    _track("video", "vidA")
    _track("video", "vidB")
    fetched: list[str] = []

    def fake_fetch(video_id, cookiefile=None, api_key=None):
        fetched.append(video_id)
        return VideoInfo(
            video_id=video_id, title="T", view_count=1, like_count=0, comment_count=0
        )

    monkeypatch.setattr(ce, "fetch_video", fake_fetch)

    ce.refresh_snapshots(cancel=lambda: len(fetched) >= 1)

    assert fetched == ["vidA"]
