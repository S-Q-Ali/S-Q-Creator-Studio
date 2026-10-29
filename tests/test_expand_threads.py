"""Tests for the Instagram and Facebook expansion threads.

The clients are replaced with fakes, so nothing here touches the network.
"""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader import engine
from s_q_ali_media_downloader.core.facebook_client import FacebookError, PageListing
from s_q_ali_media_downloader.core.instagram_client import InstagramError, Listing
from s_q_ali_media_downloader.engine import (
    MAX_ACCOUNT_VIDEOS,
    FacebookFetchThread,
    InstagramFetchThread,
)


def _collect(thread):
    """Run the thread and collect what it emits."""
    found = []
    failed = []
    progress = []
    thread.found.connect(lambda urls, label: found.append((urls, label)))
    thread.failed.connect(failed.append)
    thread.progress.connect(lambda current, total: progress.append((current, total)))
    thread.run()
    return found, failed, progress


def test_the_instagram_limit_is_clamped():
    assert InstagramFetchThread("https://www.instagram.com/nasa/", 9999).limit == (
        MAX_ACCOUNT_VIDEOS
    )
    assert InstagramFetchThread("https://www.instagram.com/nasa/", 0).limit == 1


def test_the_facebook_limit_is_clamped():
    assert FacebookFetchThread("https://www.facebook.com/nasa", 9999).limit == (
        MAX_ACCOUNT_VIDEOS
    )
    assert FacebookFetchThread("https://www.facebook.com/nasa", 0).limit == 1


def test_an_instagram_profile_expands_into_permalinks(monkeypatch):
    """The thread hands back page permalinks, never the CDN links."""
    calls = {}

    def fake_list(username, limit, progress=None):
        calls["username"] = username
        calls["limit"] = limit
        if progress is not None:
            progress(2)
        return Listing(
            [
                "https://www.instagram.com/p/AAA/",
                "https://www.instagram.com/p/BBB/",
            ]
        )

    monkeypatch.setattr(engine, "list_profile_media", fake_list)

    found, failed, progress = _collect(
        InstagramFetchThread("https://www.instagram.com/nasa/", 10)
    )

    assert not failed
    assert calls["username"] == "nasa"
    assert calls["limit"] == 10
    assert found[0][0] == [
        "https://www.instagram.com/p/AAA/",
        "https://www.instagram.com/p/BBB/",
    ]
    assert found[0][1] == "@nasa"
    assert progress == [(2, 10)]


def test_a_truncated_instagram_listing_says_so(monkeypatch):
    """Instagram cuts a long walk off. The label has to say the list is
    short, or a partial list reads like a complete one."""

    def fake_list(username, limit, progress=None):
        return Listing(
            ["https://www.instagram.com/p/AAA/"],
            "stopped early at the 180-second limit",
        )

    monkeypatch.setattr(engine, "list_profile_media", fake_list)

    found, failed, _ = _collect(
        InstagramFetchThread("https://www.instagram.com/nasa/", 10)
    )

    assert not failed
    assert found[0][1] == "@nasa — stopped early at the 180-second limit"


def test_an_instagram_failure_is_one_sentence(monkeypatch):
    def fake_list(username, limit, progress=None):
        raise InstagramError("Instagram is rate-limiting this machine.")

    monkeypatch.setattr(engine, "list_profile_media", fake_list)

    found, failed, _ = _collect(
        InstagramFetchThread("https://www.instagram.com/nasa/", 10)
    )

    assert not found
    assert failed == ["Instagram is rate-limiting this machine."]


def test_a_link_that_is_not_an_instagram_profile_fails(monkeypatch):
    def fake_list(username, limit, progress=None):  # pragma: no cover - not called
        raise AssertionError("the client must not be reached")

    monkeypatch.setattr(engine, "list_profile_media", fake_list)

    found, failed, _ = _collect(InstagramFetchThread("https://www.instagram.com/", 10))

    assert not found
    assert len(failed) == 1
    assert "profile" in failed[0].lower()


def test_a_facebook_page_expands_into_permalinks(monkeypatch):
    calls = {}

    def fake_list(page, limit, progress=None):
        calls["page"] = page
        calls["limit"] = limit
        if progress is not None:
            progress(1)
        return PageListing(["https://www.facebook.com/nasa/videos/123456789"])

    monkeypatch.setattr(engine, "list_page_videos", fake_list)

    found, failed, progress = _collect(
        FacebookFetchThread("https://www.facebook.com/nasa", 10)
    )

    assert not failed
    assert calls["page"] == "nasa"
    assert calls["limit"] == 10
    assert found[0][0] == ["https://www.facebook.com/nasa/videos/123456789"]
    assert found[0][1] == (
        "nasa — experimental: Facebook's own list, paged as far as it goes"
    )
    assert progress == [(1, 10)]


def test_a_facebook_listing_that_stops_short_says_why(monkeypatch):
    def fake_list(page, limit, progress=None):
        return PageListing(["https://www.facebook.com/nasa/videos/123456789"], "first screen only")

    monkeypatch.setattr(engine, "list_page_videos", fake_list)

    found, failed, _ = _collect(FacebookFetchThread("https://www.facebook.com/nasa", 10))

    assert not failed
    assert found[0][1].endswith("— first screen only")


def test_a_facebook_failure_is_one_sentence(monkeypatch):
    def fake_list(page, limit, progress=None):
        raise FacebookError("Facebook could not be reached.")

    monkeypatch.setattr(engine, "list_page_videos", fake_list)

    found, failed, _ = _collect(FacebookFetchThread("https://www.facebook.com/nasa", 10))

    assert not found
    assert failed == ["Facebook could not be reached."]


def test_a_link_that_is_not_a_facebook_page_fails(monkeypatch):
    def fake_list(page, limit, progress=None):  # pragma: no cover - not called
        raise AssertionError("the client must not be reached")

    monkeypatch.setattr(engine, "list_page_videos", fake_list)

    found, failed, _ = _collect(
        FacebookFetchThread("https://www.facebook.com/watch/?v=123", 10)
    )

    assert not found
    assert len(failed) == 1
    assert "page" in failed[0].lower()


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.instagram.com/nasa", True),
        ("https://www.instagram.com/nasa/", True),
        ("https://instagram.com/nasa", True),
        ("https://www.instagram.com/p/ABC123/", False),
        ("https://www.instagram.com/reel/ABC123/", False),
        ("https://www.instagram.com/", False),
        ("https://example.com/nasa", False),
        ("nasa", False),
    ],
)
def test_the_instagram_profile_detector(url, expected):
    assert engine.is_instagram_profile_url(url) is expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.facebook.com/nasa", True),
        ("https://www.facebook.com/nasa/", True),
        ("https://facebook.com/nasa/videos", True),
        ("https://www.facebook.com/nasa/videos/123456789", False),
        ("https://www.facebook.com/watch/?v=123", False),
        ("https://www.facebook.com/groups/12345", False),
        ("https://www.facebook.com/", False),
        ("https://example.com/nasa", False),
    ],
)
def test_the_facebook_page_detector(url, expected):
    assert engine.is_facebook_page_url(url) is expected
