"""Tests for the link routing in the main window.

A pasted Instagram profile or Facebook page expands into downloads; a pasted
single post or video still queues one download. Nothing here reaches the
network — the expansion thread is captured, not started.
"""

from __future__ import annotations

from s_q_ali_media_downloader.engine import (
    AccountFetchThread,
    FacebookFetchThread,
    InstagramFetchThread,
    YouTubeFetchThread,
)
from s_q_ali_media_downloader.ui.main_window import MainWindow


def _window_with_captured_expansions(qapp, isolated_appdata, monkeypatch):
    """A window whose expansion queue is captured instead of run."""
    window = MainWindow()
    captured = []
    monkeypatch.setattr(window, "_enqueue_expand", captured.append)
    return window, captured


def test_an_instagram_profile_gets_the_instagram_thread(qapp, isolated_appdata):
    window = MainWindow()

    thread = window._expand_thread_for("https://www.instagram.com/nasa/")

    assert isinstance(thread, InstagramFetchThread)
    window.close()


def test_a_facebook_page_gets_the_facebook_thread(qapp, isolated_appdata):
    window = MainWindow()

    thread = window._expand_thread_for("https://www.facebook.com/nasa")

    assert isinstance(thread, FacebookFetchThread)
    window.close()


def test_a_tiktok_profile_still_gets_the_tiktok_thread(qapp, isolated_appdata):
    window = MainWindow()

    thread = window._expand_thread_for("https://www.tiktok.com/@nasa")

    assert isinstance(thread, AccountFetchThread)
    window.close()


def test_a_youtube_channel_still_gets_the_youtube_thread(qapp, isolated_appdata):
    window = MainWindow()

    thread = window._expand_thread_for("https://www.youtube.com/@nasa")

    assert isinstance(thread, YouTubeFetchThread)
    window.close()


def test_profiles_and_pages_are_expanded(qapp, isolated_appdata, monkeypatch):
    window, captured = _window_with_captured_expansions(qapp, isolated_appdata, monkeypatch)

    window.links.setPlainText(
        "https://www.instagram.com/nasa\n"
        "https://www.facebook.com/nasa\n"
        "https://www.tiktok.com/@nasa"
    )
    window.add_links()

    assert captured == [
        [
            "https://www.instagram.com/nasa",
            "https://www.facebook.com/nasa",
            "https://www.tiktok.com/@nasa",
        ]
    ]
    assert window.jobs == []
    window.close()


def test_a_single_post_and_a_single_video_are_queued(qapp, isolated_appdata, monkeypatch):
    window, captured = _window_with_captured_expansions(qapp, isolated_appdata, monkeypatch)

    window.links.setPlainText(
        "https://www.instagram.com/p/ABC123/\n"
        "https://www.facebook.com/nasa/videos/123456789"
    )
    window.add_links()

    assert captured == []
    assert [job.url for job in window.jobs] == [
        "https://www.instagram.com/p/ABC123/",
        "https://www.facebook.com/nasa/videos/123456789",
    ]
    window.close()


def test_the_status_names_the_expansion(qapp, isolated_appdata, monkeypatch):
    window, _ = _window_with_captured_expansions(qapp, isolated_appdata, monkeypatch)

    window.links.setPlainText("https://www.instagram.com/nasa")
    window.add_links()

    assert "Expanding 1" in window.status_bar.text()
    window.close()
