"""Tests for the channel resolver: the record and the creator's own links."""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.agent.tools import social_resolve as sr

# Captured from the live About pages on 2026-10-21. The links of the videos
# a channel lists are marked separately: they belong to other creators, and
# the browser tells them apart by the element they live in — not by a
# parameter in the URL (a channel's own links section also lists sponsors).
MKBHD_ABOUT_LINKS = [
    "https://www.youtube.com/redirect?event=channel_header&redir_token=AAA&q=http%3A%2F%2Ftwitter.com%2FMKBHD",
    "https://www.youtube.com/redirect?event=video_description&redir_token=BBB&q=http%3A%2F%2Finstagram.com%2FMKBHD",
    "https://www.youtube.com/redirect?event=video_description&redir_token=CCC&q=http%3A%2F%2Ftwitter.com%2FMKBHD",
    "https://www.youtube.com/redirect?event=video_description&redir_token=DDD&q=http%3A%2F%2Ffacebook.com%2FMKBHD",
]

MRBEAST_ABOUT_LINKS = [
    "https://www.youtube.com/redirect?event=channel_header&redir_token=EEE&q=https%3A%2F%2Fwww.instagram.com%2Fjohnpeelfitness%2F",
    "https://www.youtube.com/redirect?event=channel_header&redir_token=FFF&q=https%3A%2F%2Fwww.facebook.com%2FCarolinaFordDealer%2F",
    "https://www.youtube.com/redirect?event=channel_header&redir_token=GGG&q=https%3A%2F%2Fwww.facebook.com%2FMrBeast%2F",
    "https://www.youtube.com/redirect?event=video_description&redir_token=HHH&q=https%3A%2F%2Fwww.instagram.com%2Fmrbeast",
]


# --------------------------------------------------------------------------- #
# Which links are candidates
# --------------------------------------------------------------------------- #
def test_every_social_link_on_the_page_is_a_candidate():
    """The page cannot say whose link is whose — MrBeast's own accounts and
    the sponsors he mentions sit in the same description. Deciding is the
    verifier's job."""
    links = sr.social_link_candidates(MKBHD_ABOUT_LINKS)

    assert "https://twitter.com/MKBHD" in links
    assert "https://instagram.com/MKBHD" in links
    assert "https://facebook.com/MKBHD" in links


def test_a_sponsors_link_is_a_candidate_too():
    """It is a candidate, not a finding — the account page decides."""
    links = sr.social_link_candidates(MRBEAST_ABOUT_LINKS)

    assert "https://www.facebook.com/MrBeast/" in links
    assert "https://www.instagram.com/johnpeelfitness/" in links


def test_a_plain_external_link_counts():
    links = sr.social_link_candidates(["https://www.instagram.com/mrbeast"])

    assert links == ["https://www.instagram.com/mrbeast"]


def test_youtube_links_are_never_social_links():
    links = sr.social_link_candidates(
        ["https://www.youtube.com/watch?v=abc", "https://twitter.com/x"]
    )

    assert links == ["https://twitter.com/x"]


# --------------------------------------------------------------------------- #
# The record
# --------------------------------------------------------------------------- #
def test_parse_channel_page_reads_the_name_and_the_handle():
    page = sr.Page(
        url="https://www.youtube.com/@veritasium/about",
        title="Veritasium - YouTube",
        text=(
            "GB | Skip navigation | Sign in | Home | Shorts | Subscriptions | You | "
            "Veritasium | @veritasium | • | 21.4M subscribers | • | 541 videos |"
        ),
        links=[],
    )

    name, handle = sr.parse_channel_page(page)

    assert name == "Veritasium"
    assert handle == "veritasium"


def test_resolve_channel_merges_the_record(monkeypatch):
    """The record carries the metadata, the rendered handle and the creator's
    own links."""

    class FakeChannel:
        channel_id = "UC123"
        title = "Marques Brownlee"
        description = "Tech channel"
        subscriber_count = 21_400_000
        custom_url = "https://www.youtube.com/@mkbhd"
        uploads = ()

    monkeypatch.setattr(sr, "fetch_channel", lambda *a, **k: FakeChannel())

    class FakeSession:
        def open(self, url, **kwargs):
            return sr.Page(
                url=url,
                title="Marques Brownlee - YouTube",
                text="Marques Brownlee | @mkbhd | • | 21.4M subscribers |",
                links=MKBHD_ABOUT_LINKS,
            )

    record = sr.resolve_channel("@mkbhd", session=FakeSession())

    assert record.title == "Marques Brownlee"
    assert record.handle == "mkbhd"
    assert record.subscribers == 21_400_000
    assert record.source == "handle"
    assert "https://twitter.com/MKBHD" in record.bio_links
    assert record.url == "https://www.youtube.com/@mkbhd"


def test_every_candidate_per_platform_is_kept(monkeypatch):
    """The channel page can hold a sponsor's account next to the creator's
    own, so all of them are candidates — the verifier picks."""

    class FakeChannel:
        channel_id = "UC123"
        title = "MrBeast"
        description = ""
        subscriber_count = 522_000_000
        custom_url = "https://www.youtube.com/@MrBeast"
        uploads = ()

    monkeypatch.setattr(sr, "fetch_channel", lambda *a, **k: FakeChannel())

    class FakeSession:
        def open(self, url, **kwargs):
            return sr.Page(
                url=url,
                title="MrBeast - YouTube",
                text="MrBeast | @MrBeast |",
                links=MRBEAST_ABOUT_LINKS,
            )

    record = sr.resolve_channel("@MrBeast", session=FakeSession())
    candidates = record.platform_candidates()

    assert "https://www.facebook.com/MrBeast/" in candidates["facebook"]
    assert "https://www.facebook.com/CarolinaFordDealer/" in candidates["facebook"]
    assert "https://www.instagram.com/mrbeast" in candidates["instagram"]
    assert "https://www.instagram.com/johnpeelfitness/" in candidates["instagram"]


def test_a_plain_name_is_searched(monkeypatch):
    class FakeChannel:
        channel_id = "UC123"
        title = "Marques Brownlee"
        description = ""
        subscriber_count = 21_400_000
        custom_url = "https://www.youtube.com/@mkbhd"
        uploads = ()

    calls = []

    def fake_search(query, max_results=1):
        calls.append((query, max_results))
        return [FakeChannel()]

    def fail_fetch(*a, **k):
        raise AssertionError("the name path must not fetch the channel twice")

    monkeypatch.setattr(sr, "search_channels", fake_search)
    monkeypatch.setattr(sr, "fetch_channel", fail_fetch)

    record = sr.resolve_channel("Marques Brownlee")

    assert calls == [("Marques Brownlee", 5)]
    assert record.url == "https://www.youtube.com/channel/UC123"
    assert record.source == "name"


def test_the_closest_name_wins(monkeypatch):
    class FakeChannel:
        def __init__(self, channel_id, title):
            self.channel_id = channel_id
            self.title = title
            self.description = ""
            self.subscriber_count = 0
            self.custom_url = ""
            self.uploads = ()

    def fail_fetch(*a, **k):
        raise AssertionError("the name path must not fetch the channel twice")

    monkeypatch.setattr(
        sr,
        "search_channels",
        lambda *a, **k: [FakeChannel("UC1", "Alibaba"), FakeChannel("UC2", "Ali Khan")],
    )
    monkeypatch.setattr(sr, "fetch_channel", fail_fetch)

    record = sr.resolve_channel("Ali Khan")

    assert record.channel_id == "UC2"
    assert record.title == "Ali Khan"


def test_a_single_word_name_falls_back_to_search(monkeypatch):
    class FakeChannel:
        channel_id = "UC123"
        title = "Tech Reviews"
        description = ""
        subscriber_count = 0
        custom_url = "https://www.youtube.com/@techreviews"
        uploads = ()

    def fail_fetch(*a, **k):
        raise RuntimeError("no such handle")

    monkeypatch.setattr(sr, "fetch_channel", fail_fetch)
    monkeypatch.setattr(sr, "search_channels", lambda *a, **k: [FakeChannel()])

    record = sr.resolve_channel("Tech")

    assert record.channel_id == "UC123"
    assert record.title == "Tech Reviews"
    assert record.source == "name"


def test_a_failed_handle_is_not_searched_as_a_name(monkeypatch):
    def fail_fetch(*a, **k):
        raise RuntimeError("no such handle")

    def fail_search(*a, **k):
        raise AssertionError("a handle must not be searched as a name")

    monkeypatch.setattr(sr, "fetch_channel", fail_fetch)
    monkeypatch.setattr(sr, "search_channels", fail_search)

    with pytest.raises(sr.ChannelUnresolved):
        sr.resolve_channel("@nobody")


def test_resolve_channel_reports_a_channel_it_cannot_open(monkeypatch):
    class FakeChannel:
        channel_id = "UC123"
        title = "Nobody"
        description = ""
        subscriber_count = 0
        custom_url = ""
        uploads = ()

    monkeypatch.setattr(sr, "fetch_channel", lambda *a, **k: FakeChannel())

    class BrokenSession:
        def open(self, url, **kwargs):
            raise sr.PageUnavailable("boom")

    with pytest.raises(sr.ChannelUnresolved):
        sr.resolve_channel("@nobody", session=BrokenSession())
