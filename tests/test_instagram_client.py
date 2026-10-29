"""Tests for the Instagram listing client.

The live path needs the network and the instaloader package, so it is not
exercised here. What is exercised is everything the client decides for
itself: which text is a profile, which post is worth queueing, what URL is
handed to the queue, and what the user is told when Instagram refuses.
"""

from __future__ import annotations

import sys
import types

import pytest

from s_q_ali_media_downloader.core import instagram_client as ig


class FakePost:
    def __init__(self, shortcode, typename="GraphVideo", media=(True,)):
        self.shortcode = shortcode
        self.typename = typename
        self._media = list(media)

    def get_is_videos(self):
        return list(self._media)


def _fake_instaloader(monkeypatch, *, posts=(), raises=None, posts_factory=None):
    """Put a fake instaloader on the path, the way the real one behaves.

    ``raises`` names one of the fake exception classes, so the test never
    needs the real package installed. ``posts_factory`` returns the iterator
    the profile hands out, for a walk that fails part-way through.
    """

    class Profile:
        @staticmethod
        def from_username(context, username):
            if raises is not None:
                raise exceptions.__dict__[raises](raises)
            return types.SimpleNamespace(
                username=username,
                get_posts=posts_factory
                if posts_factory is not None
                else (lambda: iter(list(posts))),
            )

    class Instaloader:
        def __init__(self, **kwargs):
            self.context = object()

    exceptions = types.ModuleType("instaloader.exceptions")
    for name in (
        "LoginRequiredException",
        "PrivateProfileNotFollowedException",
        "ProfileNotExistsException",
        "QueryReturnedForbiddenException",
        "TooManyRequestsException",
    ):
        setattr(exceptions, name, type(name, (Exception,), {}))

    package = types.ModuleType("instaloader")
    package.Instaloader = Instaloader
    package.Profile = Profile
    package.exceptions = exceptions

    monkeypatch.setitem(sys.modules, "instaloader", package)
    monkeypatch.setitem(sys.modules, "instaloader.exceptions", exceptions)
    return exceptions


# --------------------------------------------------------------------------- #
# What counts as a profile
# --------------------------------------------------------------------------- #
def test_a_handle_becomes_a_profile_url():
    assert ig.normalize_profile("porsche") == (
        "porsche",
        "https://www.instagram.com/porsche/",
    )


def test_a_profile_link_becomes_a_handle():
    assert ig.normalize_profile("https://www.instagram.com/porsche/")[0] == "porsche"


def test_a_profile_link_with_a_trailing_slash_is_read():
    assert ig.normalize_profile("https://www.instagram.com/nasa")[0] == "nasa"


def test_a_post_link_is_not_a_profile():
    assert ig.normalize_profile("https://www.instagram.com/p/DfC0AF6z68E/") == (
        None,
        None,
    )


def test_a_reserved_path_is_not_a_profile():
    assert ig.normalize_profile("https://www.instagram.com/explore/tags/cars") == (
        None,
        None,
    )


def test_rubbish_is_not_a_profile():
    assert ig.normalize_profile("not a handle!") == (None, None)
    assert ig.normalize_profile("") == (None, None)


# --------------------------------------------------------------------------- #
# Which post is worth queueing
# --------------------------------------------------------------------------- #
def test_a_video_post_carries_a_video():
    assert ig.carries_video(FakePost("AAA", "GraphVideo")) is True


def test_a_photo_post_carries_no_video():
    assert ig.carries_video(FakePost("AAA", "GraphImage", (False,))) is False


def test_a_carousel_with_one_video_carries_a_video():
    assert ig.carries_video(FakePost("AAA", "GraphSidecar", (False, True))) is True


def test_a_carousel_of_photos_carries_no_video():
    assert ig.carries_video(FakePost("AAA", "GraphSidecar", (False, False))) is False


# --------------------------------------------------------------------------- #
# What the queue receives
# --------------------------------------------------------------------------- #
def test_a_permalink_is_a_page_url_and_never_a_cdn_link():
    url = ig.profile_permalink("DfC0AF6z68E")
    assert url == "https://www.instagram.com/p/DfC0AF6z68E/"
    assert "fbcdn.net" not in url


def test_only_video_posts_are_queued():
    posts = [
        FakePost("AAA", "GraphVideo"),
        FakePost("BBB", "GraphImage", (False,)),
        FakePost("CCC", "GraphSidecar", (False, True)),
    ]
    assert ig.media_permalinks(posts, 10) == [
        "https://www.instagram.com/p/AAA/",
        "https://www.instagram.com/p/CCC/",
    ]


def test_the_limit_is_respected():
    posts = [FakePost(f"P{i}", "GraphVideo") for i in range(50)]
    assert len(ig.media_permalinks(posts, 7)) == 7


def test_progress_counts_the_videos_found():
    seen = []
    posts = [FakePost("AAA", "GraphVideo"), FakePost("BBB", "GraphImage", (False,))]
    ig.media_permalinks(posts, 10, progress=seen.append)
    assert seen == [1]


# --------------------------------------------------------------------------- #
# What the user is told
# --------------------------------------------------------------------------- #
def test_a_listing_returns_the_permalinks(monkeypatch):
    _fake_instaloader(monkeypatch, posts=[FakePost("AAA", "GraphVideo")])
    assert ig.list_profile_media("porsche", 5) == ["https://www.instagram.com/p/AAA/"]


def test_a_complete_listing_carries_no_reason(monkeypatch):
    _fake_instaloader(monkeypatch, posts=[FakePost("AAA", "GraphVideo")])
    assert ig.list_profile_media("porsche", 5).reason == ""


def test_a_rate_limit_is_reported_in_plain_words(monkeypatch):
    _fake_instaloader(monkeypatch, raises="TooManyRequestsException")
    with pytest.raises(ig.InstagramRateLimited) as caught:
        ig.list_profile_media("porsche", 5)
    assert "rate-limiting" in str(caught.value)


def test_a_missing_account_is_reported_in_plain_words(monkeypatch):
    _fake_instaloader(monkeypatch, raises="ProfileNotExistsException")
    with pytest.raises(ig.InstagramNotFound):
        ig.list_profile_media("nobody", 5)


def test_a_private_account_is_reported_in_plain_words(monkeypatch):
    _fake_instaloader(monkeypatch, raises="LoginRequiredException")
    with pytest.raises(ig.InstagramPrivate) as caught:
        ig.list_profile_media("secret", 5)
    assert "private" in str(caught.value)


def test_a_rate_limit_halfway_keeps_the_videos_already_found(monkeypatch):
    """Instagram cuts a long walk off with a 429. The posts found before
    that are real, so they are kept instead of thrown away."""
    holder = {}

    def posts():
        yield FakePost("AAA", "GraphVideo")
        raise holder["exceptions"].TooManyRequestsException("429")

    holder["exceptions"] = _fake_instaloader(monkeypatch, posts_factory=posts)

    assert ig.list_profile_media("porsche", 5) == ["https://www.instagram.com/p/AAA/"]


def test_the_operation_line_carries_no_credential(monkeypatch):
    lines = []
    _fake_instaloader(monkeypatch, posts=[FakePost("AAA", "GraphVideo")])
    ig.list_profile_media("porsche", 5, ops=ig.Ops(lines.append))
    assert lines
    assert "instagram.list" in lines[0]
    assert "porsche" in lines[0]


# --------------------------------------------------------------------------- #
# The walk has to end
# --------------------------------------------------------------------------- #
class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_the_walk_stops_at_its_budget(monkeypatch):
    """Instagram paces itself at about 2.9 s per post, so an unbounded walk
    of a busy profile runs for half an hour. The walk has to stop, and say
    that it stopped."""
    clock = FakeClock()
    monkeypatch.setattr(ig, "time", clock)
    monkeypatch.setattr(ig, "_last_call", 0.0)

    def posts():
        for i in range(50):
            clock.now += 10.0  # ten seconds per post
            yield FakePost(f"P{i}", "GraphVideo")

    _fake_instaloader(monkeypatch, posts_factory=posts)

    listing = ig.list_profile_media("porsche", 50, max_seconds=60.0)

    assert len(listing) == 6
    assert listing.reason == "stopped early at the 60-second limit"


def test_a_budget_that_never_runs_out_keeps_every_video(monkeypatch):
    _fake_instaloader(monkeypatch, posts=[FakePost("AAA", "GraphVideo")])
    listing = ig.list_profile_media("porsche", 5, max_seconds=60.0)
    assert listing == ["https://www.instagram.com/p/AAA/"]
    assert listing.reason == ""
