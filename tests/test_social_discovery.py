"""Tests for the Social Discovery pipeline."""

from __future__ import annotations

from s_q_ali_media_downloader.agent import social_discovery as sd
from s_q_ali_media_downloader.agent.tools import social_judge as judge
from s_q_ali_media_downloader.agent.tools import social_resolve as sr
from s_q_ali_media_downloader.agent.tools import social_verify as sv


class _FakeChannel:
    channel_id = "UC123"
    title = "MrBeast"
    description = "A channel"
    subscriber_count = 522_000_000
    custom_url = "https://www.youtube.com/@MrBeast"
    uploads = ()


def _record(bio_links):
    return sr.ResolvedChannel(
        channel_id="UC123",
        title="MrBeast",
        handle="MrBeast",
        url="https://www.youtube.com/@MrBeast",
        description="A channel",
        bio_links=bio_links,
        subscribers=522_000_000,
    )


class _FakeSession:
    def __init__(self, pages=None):
        self.pages = pages or {}

    def open(self, url, **kwargs):
        page = self.pages.get(url)
        if page is None:
            raise sv.PageUnavailable("no page")
        return page


def _found_page(url, name="MrBeast", handle="MrBeast"):
    from s_q_ali_media_downloader.agent.tools.browser import Page

    return Page(
        url=url,
        title=f"{name} | Facebook",
        text=f"{name} 51M followers",
        links=[],
        meta={"ogTitle": name, "ogUrl": url},
    )


def test_a_channel_with_a_bio_link_is_checked(monkeypatch):
    monkeypatch.setattr(sr, "fetch_channel", lambda *a, **k: _FakeChannel())
    monkeypatch.setattr(
        sd,
        "resolve_channel",
        lambda text, session=None: _record(["https://www.facebook.com/MrBeast/"]),
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast/": _found_page("https://www.facebook.com/MrBeast/")}
    )

    result = sd.discover(session, "@MrBeast")

    assert result.error == ""
    assert result.found_count == 1
    outcome = result.outcome("facebook")
    assert outcome.is_found
    assert outcome.source == sd.SOURCE_BIO


def test_an_empty_bio_asks_the_agent(monkeypatch):
    monkeypatch.setattr(
        sd,
        "resolve_channel",
        lambda text, session=None: _record([]),
    )

    class FakeProposal:
        candidates = {"facebook": ["MrBeast"]}
        reason = "the model knows this creator"

    monkeypatch.setattr(
        judge, "propose", lambda *a, **k: FakeProposal()
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast": _found_page("https://www.facebook.com/MrBeast")}
    )

    result = sd.discover(session, "@MrBeast")

    assert result.reason == "the model knows this creator"
    assert result.found_count == 1
    assert result.outcome("facebook").source == sd.SOURCE_MODEL


def test_a_channel_that_cannot_be_resolved_reports_why(monkeypatch):
    def boom(text, session=None):
        raise sr.ChannelUnresolved("that is not a channel")

    monkeypatch.setattr(sd, "resolve_channel", boom)

    result = sd.discover(_FakeSession(), "@nobody")

    assert result.error
    assert result.platforms == []


def test_a_missing_agent_key_is_reported(monkeypatch):
    monkeypatch.setattr(
        sd,
        "resolve_channel",
        lambda text, session=None: _record([]),
    )

    def boom(*a, **k):
        raise judge.JudgeUnavailable("No Groq API key configured.")

    monkeypatch.setattr(judge, "propose", boom)

    result = sd.discover(_FakeSession(), "@MrBeast")

    assert "key" in result.error.lower()


def test_the_progress_is_reported(monkeypatch):
    monkeypatch.setattr(
        sd,
        "resolve_channel",
        lambda text, session=None: _record(["https://www.facebook.com/MrBeast/"]),
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast/": _found_page("https://www.facebook.com/MrBeast/")}
    )
    lines: list[str] = []

    sd.discover(session, "@MrBeast", progress=lines.append)

    assert lines
    assert any("facebook" in line.lower() for line in lines)


def test_a_platform_with_no_candidate_is_not_in_the_result(monkeypatch):
    monkeypatch.setattr(
        sd,
        "resolve_channel",
        lambda text, session=None: _record(["https://www.facebook.com/MrBeast/"]),
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast/": _found_page("https://www.facebook.com/MrBeast/")}
    )

    result = sd.discover(session, "@MrBeast")

    assert result.outcome("tiktok") is None
