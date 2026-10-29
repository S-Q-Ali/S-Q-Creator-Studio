"""Tests for the Facebook page listing client.

The live path needs a browser and the network, so it is not exercised here.
What is exercised is what the client decides for itself: which text is a
page, which link is a video, what URL the queue receives, and what the user
is told when Facebook refuses.
"""

from __future__ import annotations

import types

import pytest

from s_q_ali_media_downloader.core import facebook_client as fb


class FakeSession:
    """A stand-in for BrowserSession that renders a fixed list of links."""

    def __init__(self, links=(), error=None):
        self.links = list(links)
        self.error = error
        self.opened = []
        self.closed = False

    def open(self, url, *, wait_ms=None):
        self.opened.append(url)
        if self.error is not None:
            raise self.error
        return types.SimpleNamespace(url=url, title="A page", text="", links=self.links)

    def close(self):
        self.closed = True


NASA_LINKS = [
    "https://www.facebook.com/100044561550831/videos/1803909017420449",
    "https://www.facebook.com/NASA/videos/artemis-acceleration/1803909017420449/",
    "https://www.facebook.com/NASA/videos/nasa-moon-base/1863947697952668/",
    "https://www.facebook.com/NASA/photos/a.123456",
    "https://www.facebook.com/NASA/",
]


# --------------------------------------------------------------------------- #
# What counts as a page
# --------------------------------------------------------------------------- #
def test_a_page_name_becomes_a_videos_url():
    assert fb.normalize_page("nasa") == (
        "nasa",
        "https://www.facebook.com/nasa/videos/",
    )


def test_a_page_link_becomes_a_page_name():
    assert fb.normalize_page("https://www.facebook.com/NASA/videos/")[0] == "NASA"


def test_a_video_link_is_not_a_page():
    assert fb.normalize_page("https://www.facebook.com/NASA/videos/1803909017420449") == (
        None,
        None,
    )


def test_a_watch_link_is_not_a_page():
    assert fb.normalize_page("https://www.facebook.com/watch/?v=123456789")[0] != "watch"


def test_rubbish_is_not_a_page():
    assert fb.normalize_page("") == (None, None)
    assert fb.normalize_page("not a page!") == (None, None)


# --------------------------------------------------------------------------- #
# Which link is a video
# --------------------------------------------------------------------------- #
def test_video_ids_are_read_from_the_links():
    ids = fb.video_ids_from_links(NASA_LINKS)
    assert ids == ["1803909017420449", "1863947697952668"]


def test_the_same_video_is_listed_once():
    ids = fb.video_ids_from_links(NASA_LINKS)
    assert len(ids) == len(set(ids))


def test_a_permalink_carries_the_video_id():
    url = fb.video_permalink("nasa", "1803909017420449")
    assert url == "https://www.facebook.com/nasa/videos/1803909017420449"


# --------------------------------------------------------------------------- #
# What the queue receives
# --------------------------------------------------------------------------- #
def test_a_listing_returns_the_permalinks():
    session = FakeSession(NASA_LINKS)
    urls = fb.list_page_videos("nasa", 20, session=session)
    assert urls == [
        "https://www.facebook.com/nasa/videos/1803909017420449",
        "https://www.facebook.com/nasa/videos/1863947697952668",
    ]
    assert session.opened == ["https://www.facebook.com/nasa/videos/"]


def test_the_limit_is_respected():
    session = FakeSession(NASA_LINKS)
    assert len(fb.list_page_videos("nasa", 1, session=session)) == 1


def test_a_page_without_videos_says_so():
    session = FakeSession(["https://www.facebook.com/NASA/"])
    assert fb.list_page_videos("nasa", 20, session=session) == []


def test_a_refused_page_is_reported_in_plain_words():
    session = FakeSession(error=RuntimeError("net::ERR_BLOCKED_BY_CLIENT"))
    with pytest.raises(fb.FacebookUnavailable) as caught:
        fb.list_page_videos("nasa", 20, session=session)
    assert "could not be reached" in str(caught.value)


def test_a_page_that_is_not_a_page_is_rejected():
    with pytest.raises(fb.FacebookNotFound):
        fb.list_page_videos("https://www.facebook.com/watch/?v=1", 20, session=FakeSession())


def test_the_operation_line_carries_no_credential():
    lines = []
    fb.list_page_videos("nasa", 20, ops=fb.Ops(lines.append), session=FakeSession(NASA_LINKS))
    assert lines
    assert "facebook.list" in lines[0]
    assert "nasa" in lines[0]
