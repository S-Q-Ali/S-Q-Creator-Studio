"""Tests for the trending channel engine (ported from the companion research web tool trendingEngine.ts)."""

from datetime import datetime, timedelta, timezone

import pytest

from s_q_ali_media_downloader.niche_research.research import trending_engine as te
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.youtube_client import ChannelInfo, VideoInfo

now = datetime.now(timezone.utc)


def _video(video_id, views, likes=1, comments=1, hours_ago=1, days_ago=None, duration=600):
    if days_ago is not None:
        published = (now - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        published = (now - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return VideoInfo(
        video_id=video_id,
        channel_id="UCtest",
        title="Title",
        description="desc",
        published_at=published,
        duration_seconds=duration,
        view_count=views,
        like_count=likes,
        comment_count=comments,
        tags=[],
    )


def _channel(subscribers=100_000, views=1_000_000, videos=100, published=None):
    return ChannelInfo(
        channel_id="UCtest",
        title="Test Channel",
        description="A channel",
        subscriber_count=subscribers,
        view_count=views,
        video_count=videos,
        publish_date=published,
    )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def test_growth_rate_splits_recent_vs_older():
    videos = [
        _video("a", 100, days_ago=10),
        _video("b", 100, days_ago=9),
        _video("c", 100, days_ago=8),
        _video("d", 300, days_ago=2),
        _video("e", 300, days_ago=1),
        _video("f", 300, days_ago=0),
    ]
    assert te.calculate_growth_rate(videos) == 200  # (300-100)/100


def test_growth_rate_zero_when_older_empty_base():
    videos = [_video("a", 0, days_ago=0)]
    assert te.calculate_growth_rate(videos) == 0.0


def test_rapid_growth_threshold():
    assert te.is_rapidly_growing(50) is True
    assert te.is_rapidly_growing(49.9) is False


def test_detect_ai_generated_contributions():
    channel = ChannelInfo(channel_id="x", description="No ai")
    videos = [_video("a", 1, days_ago=0)]
    assert te.detect_ai_generated(channel, videos) == 0

    channel_ai = ChannelInfo(
        channel_id="x", description="This channel uses ai narration and chatgpt"
    )
    assert te.detect_ai_generated(channel_ai, videos) == 50

    video_ai = [_video("a", 1, days_ago=0)]
    video_ai[0].tags = ["faceless", "sora", "elevenlabs"]
    assert te.detect_ai_generated(channel, video_ai) == 50

    assert te.detect_ai_generated(channel_ai, video_ai) == 70  # capped via 4 hits * 25


def test_detect_ai_faceless_bonus():
    channel = ChannelInfo(channel_id="x", description="nothing here")
    videos = [_video("a", 1, days_ago=0)]
    assert te.detect_ai_generated(channel, videos, is_faceless=True) == 30
    assert te.detect_ai_generated(channel, videos, is_faceless=False) == 0


def test_viral_score_components():
    # High subs, high views, fresh channel, strongly engaged videos.
    videos = [_video("a", 500_000, likes=25_000, comments=500, days_ago=1) for _ in range(5)]
    channel = _channel(
        subscribers=10_000,
        views=2_000_000,
        videos=20,
        published=(now - timedelta(days=30)).isoformat(),
    )
    score = te.calculate_viral_score(channel, videos, growth_rate=80, newly_created=True)
    assert 60 <= score <= 100


def test_viral_score_new_channel_bonus():
    videos = [_video("a", 100, days_ago=1)]
    channel = _channel(
        subscribers=10_000, views=5_000, videos=1, published=(now - timedelta(days=60)).isoformat()
    )
    with_bonus = te.calculate_viral_score(channel, videos, growth_rate=0, newly_created=True)
    without = te.calculate_viral_score(channel, videos, growth_rate=0, newly_created=False)
    assert with_bonus == without + 5


def test_viral_score_old_channel_freshness_falls():
    videos = [_video("a", 100, days_ago=5)]
    old = _channel(
        subscribers=10_000, views=5000, videos=1, published=(now - timedelta(days=3650)).isoformat()
    )
    new = _channel(
        subscribers=10_000, views=5000, videos=1, published=(now - timedelta(days=30)).isoformat()
    )
    assert te.calculate_viral_score(old, videos) < te.calculate_viral_score(new, videos)


# --------------------------------------------------------------------------- #
# Discovery flow (no network — fakes)
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolated_db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


def _make_raw_video(video_id, channel_id, views, likes, comments, days_ago, duration):
    published = (now - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return VideoInfo(
        video_id=video_id,
        channel_id=channel_id,
        title="Vid",
        published_at=published,
        duration_seconds=duration,
        view_count=views,
        like_count=likes,
        comment_count=comments,
    )


def test_discover_trending_channels(monkeypatch):
    channels = {
        "UCa": ChannelInfo(
            channel_id="UCa",
            title="Alpha",
            description="no ai",
            subscriber_count=50_000,
            thumbnail_url="",
        ),
        "UCb": ChannelInfo(
            channel_id="UCb",
            title="Beta",
            description="chatgpt ai narration",
            subscriber_count=5_000,
        ),
    }

    def fake_search(query, max_results, days_recent, cookiefile, progress):
        a = [
            _make_raw_video(f"a{i}", "UCa", 100_000 + i, 5000 + i, 100 + i, i + 1, 600)
            for i in range(3)
        ]
        b = [
            _make_raw_video(f"b{i}", "UCb", 50_000 + i, 300 + i, 10 + i, i + 1, 700)
            for i in range(3)
        ]
        return a + b

    def fake_fetch_channels(channel_ids, cookiefile=None, uploads_limit=30, progress=None):
        return [channels[c] for c in channel_ids if c in channels]

    monkeypatch.setattr(te, "search_videos", fake_search)
    monkeypatch.setattr(te, "fetch_channels", fake_fetch_channels)

    result, searches = te.discover_trending_channels("longform", "tech_ai")
    assert searches == 4  # tech_ai has 4 queries, budget not hit
    assert len(result) == 2
    assert {c.channel_id for c in result} == {"UCa", "UCb"}
    # UCa: ~30 V/S + ~10 avg-views + ~12 engagement + 20 freshness ≈ 72
    assert result[0].channel_id == "UCa"
    assert result[0].viral_score > result[1].viral_score


def test_discover_duration_filters():
    long_video = _make_raw_video("v1", "UCa", 100, 5, 1, 1, 900)
    short_video = _make_raw_video("v2", "UCa", 200, 5, 1, 1, 30)
    videos = [long_video, short_video]

    def fake_search(query, max_results, days_recent, cookiefile, progress):
        return videos

    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(te, "search_videos", fake_search)
    monkeypatched.setattr(
        te,
        "fetch_channels",
        lambda *a, **k: [ChannelInfo(channel_id="UCa", description="")],
    )

    long_results, _ = te.discover_trending_channels("longform", "tech_ai")
    assert len(long_results) == 1
    assert long_results[0].recent_video_count == 1

    short_results, _ = te.discover_trending_channels("shortform", "faceless")
    assert len(short_results) == 1  # 30s passes; 900s excluded


def test_unknown_niche_returns_empty():
    result, searches = te.discover_trending_channels("longform", "does_not_exist")
    assert result == []
    assert searches == 0


def test_save_and_query_trending(monkeypatch):
    channel = te.TrendingChannel(
        channel_id="UCx",
        title="X",
        description="d",
        thumbnail_url="",
        subscriber_count=10,
        view_count=100,
        video_count=5,
        published_at="",
        video_format="longform",
        niche="tech_ai",
        category_name="Tech & AI",
        viral_score=80,
        growth_rate=60,
        view_sub_ratio=10,
        recent_video_count=3,
        avg_views_per_video=20,
        is_newly_created=True,
        is_rapidly_growing=True,
        ai_score=80,
    )
    te.save_trending_channels([channel])

    rows = te.get_trending_channels("longform", "tech_ai")
    assert len(rows) == 1
    assert rows[0].channel_id == "UCx"
    assert rows[0].is_newly_created is True
    assert rows[0].viral_score == 80

    assert te.get_trending_channel_count("longform") == 1
    assert te.get_trending_channel_count("shortform") == 0
    assert te.get_trending_channel_count(ai_only=True) == 1

    assert te.get_trending_channel_by_id("UCx").title == "X"
    assert te.get_trending_channel_by_id("UCmissing") is None


def test_save_updates_on_conflict():
    a = te.TrendingChannel(
        channel_id="UCx",
        title="Old",
        description="",
        thumbnail_url="",
        subscriber_count=0,
        view_count=0,
        video_count=0,
        published_at="",
        video_format="longform",
        niche="tech_ai",
        category_name="N",
        viral_score=10,
        growth_rate=0,
        view_sub_ratio=0,
        recent_video_count=0,
        avg_views_per_video=0,
        is_newly_created=False,
        is_rapidly_growing=False,
        ai_score=0,
    )
    b = te.TrendingChannel(
        channel_id="UCx",
        title="New",
        description="",
        thumbnail_url="",
        subscriber_count=0,
        view_count=0,
        video_count=0,
        published_at="",
        video_format="longform",
        niche="tech_ai",
        category_name="N",
        viral_score=90,
        growth_rate=0,
        view_sub_ratio=0,
        recent_video_count=0,
        avg_views_per_video=0,
        is_newly_created=False,
        is_rapidly_growing=False,
        ai_score=0,
    )
    te.save_trending_channels([a])
    te.save_trending_channels([b])
    assert te.get_trending_channel_by_id("UCx").title == "New"
    assert te.get_trending_channel_by_id("UCx").viral_score == 90


def test_discovery_log_and_cache():
    assert te.was_niche_discovered_recently("longform", "tech_ai") is False
    te.log_discovery("longform", "tech_ai", 5, 4)
    assert te.was_niche_discovered_recently("longform", "tech_ai") is True
    status = te.get_discovery_status()
    assert len(status) == 1
    assert {k: status[0][k] for k in ("video_format", "niche", "channels_found")} == {
        "video_format": "longform",
        "niche": "tech_ai",
        "channels_found": 5,
    }


def test_refresh_all_trending_skips_recently_discovered(monkeypatch):
    ran = []

    def fake_discover(video_format, niche_id, max_results, cookiefile=None, progress=None):
        ran.append((video_format, niche_id))
        return [
            te.TrendingChannel(
                channel_id=f"UC{len(ran)}",
                title="",
                description="",
                thumbnail_url="",
                subscriber_count=0,
                view_count=0,
                video_count=0,
                published_at="",
                video_format=video_format,
                niche=niche_id,
                category_name="N",
                viral_score=50,
                growth_rate=0,
                view_sub_ratio=0,
                recent_video_count=0,
                avg_views_per_video=0,
                is_newly_created=False,
                is_rapidly_growing=False,
                ai_score=0,
            )
        ], 1

    te.log_discovery("longform", "tech_ai", 3, 2)  # marks tech_ai as recently discovered

    monkeypatch.setattr(te, "discover_trending_channels", fake_discover)
    result = te.refresh_all_trending("longform", "tech_ai")

    assert result["discovered"] == 0
    assert result["niches"] == 0
    assert ("longform", "tech_ai") not in ran


def test_refresh_all_trending_force_bypasses_cache(monkeypatch):
    ran = []

    def fake_discover(video_format, niche_id, max_results, cookiefile=None, progress=None):
        ran.append((video_format, niche_id))
        return [
            te.TrendingChannel(
                channel_id="UCforce",
                title="",
                description="",
                thumbnail_url="",
                subscriber_count=0,
                view_count=0,
                video_count=0,
                published_at="",
                video_format=video_format,
                niche=niche_id,
                category_name="N",
                viral_score=50,
                growth_rate=0,
                view_sub_ratio=0,
                recent_video_count=0,
                avg_views_per_video=0,
                is_newly_created=False,
                is_rapidly_growing=False,
                ai_score=0,
            )
        ], 1

    te.log_discovery("longform", "tech_ai", 3, 2)  # marks tech_ai as recently discovered

    monkeypatch.setattr(te, "discover_trending_channels", fake_discover)
    result = te.refresh_all_trending("longform", "tech_ai", force=True)

    assert result["discovered"] == 1
    assert result["niches"] == 1
    assert ("longform", "tech_ai") in ran


def test_update_last_analyzed():
    channel = te.TrendingChannel(
        channel_id="UCx",
        title="X",
        description="",
        thumbnail_url="",
        subscriber_count=0,
        view_count=0,
        video_count=0,
        published_at="",
        video_format="longform",
        niche="tech_ai",
        category_name="N",
        viral_score=0,
        growth_rate=0,
        view_sub_ratio=0,
        recent_video_count=0,
        avg_views_per_video=0,
        is_newly_created=False,
        is_rapidly_growing=False,
        ai_score=0,
    )
    te.save_trending_channels([channel])
    te.update_last_analyzed("UCx", 12345)
    assert te.get_trending_channel_by_id("UCx").last_analyzed == 12345
