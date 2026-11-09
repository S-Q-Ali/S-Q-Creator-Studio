"""Tests for YouTube Shorts sorting (Latest, Popular, Oldest)."""

import pytest

from s_q_ali_media_downloader.engine import (
    YouTubeFetchThread,
    clean_youtube_channel_base,
)


def test_clean_youtube_channel_base():
    assert clean_youtube_channel_base("https://www.youtube.com/@realadamrose/shorts") == "https://www.youtube.com/@realadamrose"
    assert clean_youtube_channel_base("https://www.youtube.com/@realadamrose/videos/") == "https://www.youtube.com/@realadamrose"
    assert clean_youtube_channel_base("https://www.youtube.com/@realadamrose/featured") == "https://www.youtube.com/@realadamrose"
    assert clean_youtube_channel_base("https://www.youtube.com/@realadamrose") == "https://www.youtube.com/@realadamrose"
    assert clean_youtube_channel_base("https://www.youtube.com/channel/UC1234567890123456789012/shorts") == "https://www.youtube.com/channel/UC1234567890123456789012"


def test_youtube_fetch_thread_video_type_targets():
    # video_type="shorts" targets ONLY /shorts
    t_shorts = YouTubeFetchThread("https://www.youtube.com/@realadamrose", limit=10, video_type="shorts")
    assert t_shorts._targets() == ["https://www.youtube.com/@realadamrose/shorts"]

    # video_type="long" targets ONLY /videos
    t_long = YouTubeFetchThread("https://www.youtube.com/@realadamrose", limit=10, video_type="long")
    assert t_long._targets() == ["https://www.youtube.com/@realadamrose/videos"]

    # video_type="all" targets both /videos and /shorts
    t_all = YouTubeFetchThread("https://www.youtube.com/@realadamrose", limit=10, video_type="all")
    assert t_all._targets() == [
        "https://www.youtube.com/@realadamrose/videos",
        "https://www.youtube.com/@realadamrose/shorts",
    ]

    # Explicit /shorts URL in url automatically targets /shorts
    t_explicit_shorts = YouTubeFetchThread("https://www.youtube.com/@realadamrose/shorts", limit=10, video_type="all")
    assert t_explicit_shorts._targets() == ["https://www.youtube.com/@realadamrose/shorts"]

    # Explicit /videos URL in url automatically targets /videos
    t_explicit_videos = YouTubeFetchThread("https://www.youtube.com/@realadamrose/videos", limit=10, video_type="all")
    assert t_explicit_videos._targets() == ["https://www.youtube.com/@realadamrose/videos"]


def test_youtube_fetch_thread_stores_shorts_sort():
    thread = YouTubeFetchThread("https://www.youtube.com/@mrbeast", limit=10, include_shorts=True, shorts_sort="popular")
    assert thread.shorts_sort == "popular"
    assert thread.include_shorts is True

    thread_old = YouTubeFetchThread("https://www.youtube.com/@mrbeast", limit=10, include_shorts=True, shorts_sort="Oldest")
    assert thread_old.shorts_sort == "oldest"


def test_fetch_sorted_shorts_returns_empty_on_invalid_url():
    thread = YouTubeFetchThread("https://invalid.url/channel", limit=5, shorts_sort="popular")
    results = thread._fetch_sorted_shorts("https://invalid.url/channel", "popular", 5)
    assert results == []


def test_fetch_sorted_shorts_popular_live():
    """Live smoke test fetching top 3 popular shorts of @mrbeast via InnerTube."""
    thread = YouTubeFetchThread("https://www.youtube.com/@mrbeast", limit=3, shorts_sort="popular")
    urls = thread._fetch_sorted_shorts("https://www.youtube.com/@mrbeast", "popular", 3)
    if not urls:
        pytest.skip("YouTube InnerTube is unreachable or blocked in this environment.")
    assert len(urls) <= 3
    assert all("youtube.com/shorts/" in u for u in urls)
