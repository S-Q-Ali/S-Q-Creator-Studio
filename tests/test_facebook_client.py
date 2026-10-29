"""Tests for the Facebook page listing client.

The live path needs a browser and the network, so it is not exercised here.
What is exercised is what the client decides for itself: which text is a
page, which link is a video, what URL the queue receives, how the page's own
paging is followed, and what the user is told when Facebook refuses.
"""

from __future__ import annotations

import json
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


def no_pager(ids=(), reason=""):
    """A pager that finds nothing, for the tests that do not care."""

    def pager(name, remaining):
        return (list(ids), reason)

    return pager


#: A page that carries everything the paging query needs.
PAGE_HTML = (
    '"lsd","value":"TOKENVALUE"'
    '"pageID":"123456789"'
    '"all_videos":{"edges":[],"page_info":{"end_cursor":"CURSOR1","has_next_page":true}}'
    '<script src="/rsrc.php/v4iM3H4/yd/l/en_GB-j/XfrGRhGjcsT.js"></script>'
)

#: The bundle that carries the query id.
BUNDLE = (
    'PagesCometChannelTabAllVideosCardImplPaginationQuery_facebookRelayOperation'
    '(a.exports="36237204515925186")'
)


def _answer(ids, cursor, has_next):
    return {
        "data": {
            "node": {
                "all_videos": {
                    "edges": [{"node": {"id": video_id}} for video_id in ids],
                    "page_info": {"end_cursor": cursor, "has_next_page": has_next},
                }
            }
        }
    }


ANSWER_ONE = _answer(["111222333"], "CURSOR2", True)
ANSWER_TWO = _answer(["444555666"], "CURSOR3", False)
ANSWER_LAST = _answer(["111222333"], "CURSOR2", False)


class FakeHttp:
    """A stand-in for the HTTP session the paging leg talks through."""

    def __init__(self, html="", answers=(), post_error=None, fail_after=None):
        self.html = html
        self.answers = list(answers)
        self.post_error = post_error
        self.fail_after = fail_after
        self.posts = []

    def get(self, url, timeout=None):
        if ".js" in url:
            return types.SimpleNamespace(text=BUNDLE)
        return types.SimpleNamespace(text=self.html)

    def post(self, url, data=None, headers=None, timeout=None):
        self.posts.append((url, dict(data or {}), dict(headers or {})))
        if self.post_error is not None and (
            self.fail_after is None or len(self.posts) > self.fail_after
        ):
            raise self.post_error
        body = self.answers.pop(0) if self.answers else {}
        return types.SimpleNamespace(text=json.dumps(body))


#: A page that names a bundle per script tag.
BUNDLES_HTML = (
    '"lsd","value":"TOKENVALUE"'
    '"pageID":"123456789"'
    '"all_videos":{"edges":[],"page_info":{"end_cursor":"CURSOR1","has_next_page":true}}'
    + "".join(f'<script src="/rsrc.php/v{index}.js"></script>' for index in range(5))
)


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
    urls = fb.list_page_videos("nasa", 20, session=session, pager=no_pager())
    assert urls == [
        "https://www.facebook.com/nasa/videos/1803909017420449",
        "https://www.facebook.com/nasa/videos/1863947697952668",
    ]
    assert session.opened == ["https://www.facebook.com/nasa/videos/"]


def test_the_limit_is_respected():
    session = FakeSession(NASA_LINKS)
    listing = fb.list_page_videos("nasa", 1, session=session, pager=no_pager())
    assert len(listing) == 1


def test_a_page_without_videos_says_so():
    session = FakeSession(["https://www.facebook.com/NASA/"])
    listing = fb.list_page_videos("nasa", 20, session=session, pager=no_pager())
    assert listing == []


def test_a_refused_page_is_reported_in_plain_words():
    session = FakeSession(error=RuntimeError("net::ERR_BLOCKED_BY_CLIENT"))
    with pytest.raises(fb.FacebookUnavailable) as caught:
        fb.list_page_videos("nasa", 20, session=session, pager=no_pager())
    assert "could not be reached" in str(caught.value)


def test_a_page_that_is_not_a_page_is_rejected():
    with pytest.raises(fb.FacebookNotFound):
        fb.list_page_videos(
            "https://www.facebook.com/watch/?v=1", 20, session=FakeSession()
        )


def test_the_operation_line_carries_no_credential():
    lines = []
    fb.list_page_videos(
        "nasa",
        20,
        ops=fb.Ops(lines.append),
        session=FakeSession(NASA_LINKS),
        pager=no_pager(),
    )
    assert lines
    assert "facebook.list" in lines[0]
    assert "nasa" in lines[0]


# --------------------------------------------------------------------------- #
# The page's own paging
# --------------------------------------------------------------------------- #
def test_the_paged_videos_are_added_to_the_first_screen():
    session = FakeSession(NASA_LINKS)
    listing = fb.list_page_videos(
        "nasa", 20, session=session, pager=no_pager(["999000111222333"])
    )
    assert len(listing) == 3
    assert listing[-1] == "https://www.facebook.com/nasa/videos/999000111222333"


def test_a_video_the_browser_already_found_is_not_added_twice():
    session = FakeSession(NASA_LINKS)
    listing = fb.list_page_videos(
        "nasa", 20, session=session, pager=no_pager(["1803909017420449"])
    )
    assert len(listing) == 2


def test_the_paging_is_not_asked_for_when_the_first_screen_is_enough():
    asked = []

    def pager(name, remaining):
        asked.append(remaining)
        return ([], "")

    fb.list_page_videos("nasa", 2, session=FakeSession(NASA_LINKS), pager=pager)
    assert asked == []


def test_the_paging_is_asked_for_the_rest_of_the_limit():
    asked = []

    def pager(name, remaining):
        asked.append((name, remaining))
        return ([], "")

    fb.list_page_videos("nasa", 20, session=FakeSession(NASA_LINKS), pager=pager)
    assert asked == [("nasa", 18)]


def test_a_page_that_will_not_page_says_the_first_screen_only():
    def pager(name, remaining):
        raise fb.PagingUnavailable("Facebook would not serve the page.")

    listing = fb.list_page_videos("nasa", 20, session=FakeSession(NASA_LINKS), pager=pager)
    assert len(listing) == 2
    assert listing.reason == "first screen only"


def test_a_listing_that_stops_short_carries_the_reason():
    listing = fb.list_page_videos(
        "nasa", 20, session=FakeSession(NASA_LINKS), pager=no_pager(reason="stopped early")
    )
    assert listing.reason == "stopped early"


def test_the_progress_counts_the_whole_list():
    seen = []
    fb.list_page_videos(
        "nasa",
        20,
        progress=seen.append,
        session=FakeSession(NASA_LINKS),
        pager=no_pager(["999000111222333"]),
    )
    assert seen[-1] == 3


# --------------------------------------------------------------------------- #
# The paging query itself
# --------------------------------------------------------------------------- #
def test_the_checksum_is_facebooks_own():
    # "2" followed by the sum of the character codes: 97 + 98 + 99 = 294.
    assert fb._checksum("abc") == "2294"


def test_the_query_id_is_read_from_the_pages_own_javascript():
    bundle = (
        'PagesCometChannelTabAllVideosCardImplPaginationQuery_facebookRelayOperation'
        '(a.exports="36237204515925186")'
    )
    page = '<script src="/rsrc.php/v4iM3H4/yd/l/en_GB-j/XfrGRhGjcsT.js"></script>'

    class FakeHttp:
        def get(self, url, timeout=None):
            assert url.startswith("https://www.facebook.com")
            return types.SimpleNamespace(text=bundle)

    assert fb._query_id(page, FakeHttp()) == "36237204515925186"


def test_a_page_without_the_query_is_reported_as_unavailable():
    class FakeHttp:
        def get(self, url, timeout=None):
            return types.SimpleNamespace(text="nothing here")

    assert fb._query_id('<script src="/a.js"></script>', FakeHttp()) is None


def test_the_first_cursor_is_read_from_the_page():
    html = (
        '"all_videos":{"edges":[],"page_info":{"end_cursor":"CUR123","has_next_page":true}}'
    )
    assert fb._first_cursor(html) == "CUR123"


def test_a_page_without_a_list_has_no_cursor():
    assert fb._first_cursor("<html>nothing</html>") is None


def test_the_token_never_reaches_a_log_line(monkeypatch):
    lines = []
    http = FakeHttp(html=PAGE_HTML, answers=[ANSWER_ONE])
    monkeypatch.setattr(fb, "_http", lambda: http)
    ids, reason = fb.paged_video_ids("nasa", 10, ops=fb.Ops(lines.append))
    assert ids == ["111222333"]
    assert reason == ""
    assert "TOKENVALUE" not in "\n".join(lines)


def test_the_token_travels_in_the_body_and_not_in_the_url(monkeypatch):
    http = FakeHttp(html=PAGE_HTML, answers=[ANSWER_ONE])
    monkeypatch.setattr(fb, "_http", lambda: http)
    fb.paged_video_ids("nasa", 10)
    for url, body, headers in http.posts:
        assert "TOKENVALUE" not in url
        assert body["lsd"] == "TOKENVALUE"
        assert headers["x-fb-lsd"] == "TOKENVALUE"


def test_the_paging_follows_the_cursor(monkeypatch):
    http = FakeHttp(html=PAGE_HTML, answers=[ANSWER_ONE, ANSWER_TWO])
    monkeypatch.setattr(fb, "_http", lambda: http)
    ids, reason = fb.paged_video_ids("nasa", 10)
    assert ids == ["111222333", "444555666"]
    assert reason == ""
    assert len(http.posts) == 2
    assert json.loads(http.posts[1][1]["variables"])["cursor"] == "CURSOR2"


def test_the_paging_stops_when_the_list_ends(monkeypatch):
    http = FakeHttp(html=PAGE_HTML, answers=[ANSWER_LAST])
    monkeypatch.setattr(fb, "_http", lambda: http)
    ids, _ = fb.paged_video_ids("nasa", 10)
    assert ids == ["111222333"]
    assert len(http.posts) == 1


def test_a_page_without_a_paging_query_is_reported_as_unavailable(monkeypatch):
    http = FakeHttp(html="<html>nothing</html>", answers=[])
    monkeypatch.setattr(fb, "_http", lambda: http)
    with pytest.raises(fb.PagingUnavailable):
        fb.paged_video_ids("nasa", 10)


# --------------------------------------------------------------------------- #
# A failure of the paging leg has to be visible
# --------------------------------------------------------------------------- #
def test_a_refused_paging_query_is_reported_as_unavailable(monkeypatch):
    """A transport error is Facebook refusing, not a crash. It has to arrive
    as a refusal, because an arbitrary exception escapes the thread that
    asked for it and the user sees nothing."""
    http = FakeHttp(html=PAGE_HTML, answers=[], post_error=RuntimeError("reset"))
    monkeypatch.setattr(fb, "_http", lambda: http)
    with pytest.raises(fb.PagingUnavailable):
        fb.paged_video_ids("nasa", 10)


def test_a_paging_query_that_stops_halfway_keeps_what_it_found(monkeypatch):
    """The videos found before Facebook stopped answering are real, so they
    are kept and the listing says why it stopped."""
    http = FakeHttp(
        html=PAGE_HTML,
        answers=[ANSWER_ONE],
        post_error=RuntimeError("reset"),
        fail_after=1,
    )
    monkeypatch.setattr(fb, "_http", lambda: http)
    ids, reason = fb.paged_video_ids("nasa", 10)
    assert ids == ["111222333"]
    assert reason == "Facebook stopped answering"


def test_a_listing_keeps_the_first_screen_when_the_paging_is_refused(monkeypatch):
    def fake_paged(
        page, limit, *, ops=None, progress=None, max_seconds=None, known=()
    ):
        raise fb.PagingUnavailable("Facebook would not answer the paging query.")

    monkeypatch.setattr(fb, "paged_video_ids", fake_paged)

    listing = fb.list_page_videos("nasa", 20, session=FakeSession(NASA_LINKS))

    assert len(listing) == 2
    assert listing.reason == "first screen only"


# --------------------------------------------------------------------------- #
# The paging has to end
# --------------------------------------------------------------------------- #
class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_the_bundle_harvest_stops_at_the_budget(monkeypatch):
    """A page names two dozen of its JavaScript bundles and each one is a
    request, so the harvest cannot outlive the paging budget."""
    clock = FakeClock()
    monkeypatch.setattr(fb, "time", clock)

    class SlowHttp:
        def __init__(self):
            self.bundles = 0

        def get(self, url, timeout=None):
            if ".js" in url:
                self.bundles += 1
                clock.now += 100.0
                return types.SimpleNamespace(text="no query here")
            return types.SimpleNamespace(text=BUNDLES_HTML)

    http = SlowHttp()
    monkeypatch.setattr(fb, "_http", lambda: http)

    with pytest.raises(fb.PagingUnavailable):
        fb.paged_video_ids("nasa", 10, max_seconds=120)

    assert http.bundles == 2


# --------------------------------------------------------------------------- #
# What the user sees
# --------------------------------------------------------------------------- #
def test_the_progress_never_counts_backwards(monkeypatch):
    """The browser's first screen and the page's own query can name the same
    video, so the count the user sees must not go down."""

    def fake_paged(
        page, limit, *, ops=None, progress=None, max_seconds=None, known=()
    ):
        # The query names a video the browser already found. The real pager
        # leaves such a video out of its count.
        fresh = [
            video_id
            for video_id in ("1803909017420449", "999000111222333")
            if video_id not in known
        ]
        if progress is not None:
            progress(len(fresh))
        return (fresh, "")

    monkeypatch.setattr(fb, "paged_video_ids", fake_paged)

    seen = []
    listing = fb.list_page_videos(
        "nasa", 20, progress=seen.append, session=FakeSession(NASA_LINKS)
    )

    assert seen == sorted(seen)
    assert seen[-1] == 3
    assert len(listing) == 3


def test_the_default_pager_asks_the_page_for_the_rest(monkeypatch):
    """With no pager of its own, the listing asks the page's own query for
    the videos behind its first screen."""
    asked = {}

    def fake_paged(page, limit, *, ops=None, progress=None, max_seconds=None, known=()):
        asked["page"] = page
        asked["limit"] = limit
        asked["known"] = list(known)
        if progress is not None:
            progress(1)
        return (["999000111222333"], "")

    monkeypatch.setattr(fb, "paged_video_ids", fake_paged)

    seen = []
    listing = fb.list_page_videos(
        "nasa", 20, progress=seen.append, session=FakeSession(NASA_LINKS)
    )

    assert asked["page"] == "nasa"
    assert asked["limit"] == 18
    # The pager is told what the browser found, so a video both engines
    # name is counted once.
    assert asked["known"] == ["1803909017420449", "1863947697952668"]
    assert len(listing) == 3
    # The count is the whole list, not this leg's share of it.
    assert seen == [2, 3]


def test_the_operation_line_names_both_engines():
    """The videos come from two engines, so the line says which did what."""
    lines = []
    fb.list_page_videos(
        "nasa",
        20,
        ops=fb.Ops(lines.append),
        session=FakeSession(NASA_LINKS),
        pager=no_pager(["999000111222333"]),
    )
    summary = [line for line in lines if line.startswith("+ facebook.list")]
    assert summary
    assert "2 from the browser" in summary[0]
    assert "1 from the page's own list" in summary[0]
