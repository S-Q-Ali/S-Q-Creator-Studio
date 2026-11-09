"""Tests for YouTube Shorts sorting (Latest, Popular, Oldest)."""

import pytest

from s_q_ali_media_downloader.engine import YouTubeFetchThread


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
