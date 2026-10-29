"""Tests for the second check: ask the web, then let the browser confirm.

One question, two methods. The search-grounded AI reads the web and can
only propose a URL; the browser opens the page and reads what the account
says about itself, so the browser decides. These tests pin the shared
parts (the budget, the trigger, the ask) and the wiring of all three
discovery modes.
"""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.agent import social_discovery as sd
from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.agent.schema import (
    ChannelMetadata,
    SocialPlatform,
    SocialPresence,
    SocialStatus,
    TikTokProfileMetadata,
)
from s_q_ali_media_downloader.agent.tools import dual_check
from s_q_ali_media_downloader.agent.tools import social_judge as judge
from s_q_ali_media_downloader.agent.tools import social_resolve as sr
from s_q_ali_media_downloader.agent.tools import social_verify as sv


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _FakeSession:
    """A browser session that serves pages from a dict."""

    def __init__(self, pages=None):
        self.pages = pages or {}
        self.opened: list[str] = []

    def open(self, url, **kwargs):
        self.opened.append(url)
        page = self.pages.get(url)
        if page is None:
            raise sv.PageUnavailable("no page")
        return page


def _page(url, title="", text="", links=(), meta=None):
    from s_q_ali_media_downloader.agent.tools.browser import Page

    return Page(
        url=url,
        title=title,
        text=text,
        links=list(links),
        meta=dict(meta or {}),
    )


def _facebook_page(url="https://www.facebook.com/MrBeast", name="MrBeast"):
    return _page(
        url,
        title=f"{name} | Facebook",
        text=f"{name} 51M followers",
        meta={"ogTitle": name, "ogUrl": url},
    )


def _missing_facebook_page(url="https://www.facebook.com/MrBeast/"):
    """A page that says the account is not there."""
    return _page(url, title="Facebook", text="Sorry, this page isn't available.")


def _creator(title="MrBeast", handle="MrBeast"):
    return sv.CreatorRef(
        title=title,
        handle=handle,
        url=f"https://www.youtube.com/@{handle}",
        channel_id="UC123",
    )


def _record(bio_links=()):
    return sr.ResolvedChannel(
        channel_id="UC123",
        title="MrBeast",
        handle="MrBeast",
        url="https://www.youtube.com/@MrBeast",
        description="A channel",
        bio_links=list(bio_links),
        subscribers=522_000_000,
    )


def _search_answer(answers):
    """The answer a search-grounded model gives, per platform."""
    return judge.AiAnswer(
        answers={
            platform: judge.PlatformAnswer(
                platform=platform, exists=exists, url=url
            )
            for platform, (exists, url) in answers.items()
        },
        provider="gemini",
        model="gemini-3.6-flash",
    )


# --------------------------------------------------------------------------- #
# The budget
# --------------------------------------------------------------------------- #
def test_the_budget_starts_full():
    budget = dual_check.SearchBudget()

    assert budget.remaining == budget.limit
    assert budget.spent == 0


def test_a_call_spends_one_of_the_budget():
    budget = dual_check.SearchBudget(limit=2)

    assert budget.take() is True
    assert budget.remaining == 1
    assert budget.take() is True
    assert budget.remaining == 0


def test_a_spent_budget_gives_nothing():
    budget = dual_check.SearchBudget(limit=1)

    assert budget.take() is True
    assert budget.take() is False
    assert budget.remaining == 0


# --------------------------------------------------------------------------- #
# When the web is asked
# --------------------------------------------------------------------------- #
def test_a_confirmed_account_needs_no_second_check():
    assert not dual_check.needs_the_second_check(
        confirmed=True, from_bio=False, unreadable=False
    )


def test_a_creators_own_link_the_browser_read_needs_no_second_check():
    """The page is the judge: it read the link and it is the creator's."""
    assert not dual_check.needs_the_second_check(
        confirmed=False, from_bio=True, unreadable=False
    )


def test_a_creators_own_link_the_browser_could_not_read_is_asked_about():
    assert dual_check.needs_the_second_check(
        confirmed=False, from_bio=True, unreadable=True
    )


def test_a_guess_is_always_asked_about():
    assert dual_check.needs_the_second_check(
        confirmed=False, from_bio=False, unreadable=False
    )


# --------------------------------------------------------------------------- #
# The ask
# --------------------------------------------------------------------------- #
def test_the_web_is_not_asked_when_the_budget_is_spent():
    budget = dual_check.SearchBudget(limit=0)

    answer = dual_check.ask_the_web(
        lambda: pytest.fail("the web must not be asked"),
        budget=budget,
        platforms=("facebook",),
    )

    assert answer is None
    assert budget.spent == 0


def test_a_provider_that_does_not_answer_leaves_the_browsers_answer():
    def boom():
        raise judge.JudgeUnavailable("Groq answered 401: invalid_api_key")

    answer = dual_check.ask_the_web(
        boom, budget=dual_check.SearchBudget(), platforms=("facebook",)
    )

    assert answer is None


def test_the_answer_comes_back():
    expected = _search_answer({"facebook": ("yes", "https://www.facebook.com/x")})

    answer = dual_check.ask_the_web(
        lambda: expected,
        budget=dual_check.SearchBudget(),
        platforms=("facebook",),
    )

    assert answer is expected


def test_the_budget_is_written_to_the_log():
    lines: list[str] = []

    dual_check.ask_the_web(
        lambda: _search_answer({}),
        budget=dual_check.SearchBudget(limit=5),
        platforms=("facebook", "instagram"),
        ops=Ops(lines.append),
    )

    assert any(line.startswith("+ budget | ai | search") for line in lines)
    assert any("1/5 spent" in line for line in lines)


def test_a_spent_budget_is_written_to_the_log():
    lines: list[str] = []

    dual_check.ask_the_web(
        lambda: pytest.fail("the web must not be asked"),
        budget=dual_check.SearchBudget(limit=0),
        platforms=("facebook",),
        ops=Ops(lines.append),
    )

    assert any(line.startswith("? budget | ai | search") for line in lines)


# --------------------------------------------------------------------------- #
# The browser leg
# --------------------------------------------------------------------------- #
def test_the_browser_opens_the_url_the_web_named():
    from s_q_ali_media_downloader.agent.tools.social_verifier import (
        SocialVerifierTool,
    )

    lines: list[str] = []
    pages = {"https://www.facebook.com/MrBeast": _facebook_page()}
    tool = SocialVerifierTool(
        rendered_checker=lambda url: pages[url],
        log_callback=lines.append,
    )

    result = tool.verify_url(
        "https://www.facebook.com/MrBeast", "facebook", _creator()
    )

    assert result.verdict is sv.Verdict.FOUND
    assert result.display_name == "MrBeast"
    assert any(
        line.startswith("+ browser.open | browser | https://www.facebook.com/MrBeast")
        for line in lines
    )


def test_a_browser_that_cannot_read_the_page_is_unknown():
    from s_q_ali_media_downloader.agent.tools.social_verifier import (
        SocialVerifierTool,
    )

    def boom(url):
        raise RuntimeError("the browser closed")

    tool = SocialVerifierTool(rendered_checker=boom)

    result = tool.verify_url("https://www.facebook.com/MrBeast", "facebook", _creator())

    assert result.verdict is sv.Verdict.UNKNOWN
    assert "could not be read" in result.detail


def test_without_a_browser_the_verdict_is_unknown():
    from s_q_ali_media_downloader.agent.tools.social_verifier import (
        SocialVerifierTool,
    )

    tool = SocialVerifierTool()

    result = tool.verify_url("https://www.facebook.com/MrBeast", "facebook", _creator())

    assert result.verdict is sv.Verdict.UNKNOWN
    assert result.detail == "no browser is available"


# --------------------------------------------------------------------------- #
# The YouTube page
# --------------------------------------------------------------------------- #
def test_a_youtube_channel_page_names_the_channel():
    page = _page(
        "https://www.youtube.com/@mkbhd",
        title="Marques Brownlee - YouTube",
        text="Marques Brownlee",
        meta={
            "ogTitle": "Marques Brownlee - YouTube",
            "ogUrl": "https://www.youtube.com/@mkbhd",
        },
    )

    result = sv.verify_page(page, "youtube", _creator("Marques Brownlee", "mkbhd"))

    assert result.verdict is sv.Verdict.FOUND
    assert result.display_name == "Marques Brownlee"
    assert result.handle == "mkbhd"


def test_a_youtube_channel_that_is_not_there_is_not_found():
    page = _page(
        "https://www.youtube.com/@nobody",
        title="404",
        meta={"ogTitle": "404"},
    )

    result = sv.verify_page(page, "youtube", _creator())

    assert result.verdict is sv.Verdict.NOT_FOUND


def test_a_youtube_page_is_not_held_against_its_own_links():
    """A channel page links to other channels by design, so a link that does
    not name the creator is not a conflict there."""
    page = _page(
        "https://www.youtube.com/@mkbhd",
        title="Marques Brownlee - YouTube",
        text="Marques Brownlee",
        links=["https://www.youtube.com/channel/UCsomebodyelse"],
        meta={
            "ogTitle": "Marques Brownlee - YouTube",
            "ogUrl": "https://www.youtube.com/@mkbhd",
        },
    )

    result = sv.verify_page(page, "youtube", _creator("Marques Brownlee", "mkbhd"))

    assert result.verdict is sv.Verdict.FOUND
    assert "conflicting_back_link" not in result.evidence


# --------------------------------------------------------------------------- #
# Mode 1: YouTube -> socials
# --------------------------------------------------------------------------- #
def _mode_one_channel():
    channel = ChannelMetadata(
        channel_id="UC1",
        title="Marques Brownlee",
        handle="mkbhd",
        subscribers=21_000_000,
        youtube_url="https://www.youtube.com/@mkbhd",
        description="tech videos",
    )
    channel.facebook.source = "model"
    channel.facebook.verified_url = "https://www.facebook.com/mkbhd"
    channel.facebook.status = SocialStatus.INCONCLUSIVE
    return channel


def _orchestrator(monkeypatch, lines=None):
    from s_q_ali_media_downloader.agent.orchestrator import AgentOrchestrator

    return AgentOrchestrator(log_callback=lines.append if lines is not None else None)


def test_mode_one_asks_the_web_when_the_browser_could_not_confirm(monkeypatch):
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: _search_answer(
            {"facebook": ("yes", "https://www.facebook.com/MKBHD")}
        ),
    )
    orchestrator = _orchestrator(monkeypatch)
    monkeypatch.setattr(
        orchestrator.verifier_tool,
        "verify_url",
        lambda url, platform, creator: sv.CheckResult(
            platform=platform,
            verdict=sv.Verdict.FOUND,
            url=url,
            display_name="Marques Brownlee",
            handle="mkbhd",
            evidence=["name_match", "handle_match"],
            tier="likely",
        ),
    )
    channel = _mode_one_channel()

    orchestrator._second_check(channel, {"facebook": channel.facebook})

    assert channel.facebook.status is SocialStatus.VERIFIED
    assert channel.facebook.confidence_score == 0.95
    assert channel.facebook.verified_url == "https://www.facebook.com/MKBHD"


def test_mode_one_does_not_ask_the_web_about_a_confirmed_account(monkeypatch):
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: pytest.fail("a confirmed account needs no second check"),
    )
    channel = _mode_one_channel()
    channel.facebook.status = SocialStatus.VERIFIED

    _orchestrator(monkeypatch)._second_check(channel, {"facebook": channel.facebook})

    assert channel.facebook.status is SocialStatus.VERIFIED


def test_mode_one_does_not_accuse_a_creator_the_browser_never_read(monkeypatch):
    """The browser could not open the page and the web found nothing: that is
    not proof that the account is missing."""
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: _search_answer({"facebook": ("no", "")}),
    )
    channel = _mode_one_channel()

    _orchestrator(monkeypatch)._second_check(channel, {"facebook": channel.facebook})

    assert channel.facebook.status is SocialStatus.INCONCLUSIVE


def test_mode_one_writes_both_engines_to_the_log(monkeypatch):
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: _search_answer(
            {"facebook": ("yes", "https://www.facebook.com/MKBHD")}
        ),
    )
    lines: list[str] = []
    orchestrator = _orchestrator(monkeypatch, lines)
    monkeypatch.setattr(
        orchestrator.verifier_tool,
        "verify_url",
        lambda url, platform, creator: sv.CheckResult(
            platform=platform, verdict=sv.Verdict.FOUND, url=url, tier="likely"
        ),
    )
    channel = _mode_one_channel()

    orchestrator._second_check(channel, {"facebook": channel.facebook})

    text = "\n".join(lines)
    assert "+ budget | ai | search" in text
    assert "+ reconcile | both | facebook" in text
    assert "ai yes + browser found -> verified" in text


# --------------------------------------------------------------------------- #
# Mode 2: TikTok -> YouTube
# --------------------------------------------------------------------------- #
def _tiktok_profile():
    return TikTokProfileMetadata(
        profile_id="1",
        handle="mkbhd",
        nickname="Marques Brownlee",
        followers=1000,
        profile_url="https://www.tiktok.com/@mkbhd",
    )


def test_mode_two_asks_the_web_for_the_youtube_channel(monkeypatch):
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(
        judge,
        "propose_youtube_searched",
        lambda *a, **k: _search_answer(
            {"youtube": ("yes", "https://www.youtube.com/@mkbhd")}
        ),
    )
    orchestrator = _orchestrator(monkeypatch)
    monkeypatch.setattr(
        orchestrator.verifier_tool,
        "verify_url",
        lambda url, platform, creator: sv.CheckResult(
            platform=platform,
            verdict=sv.Verdict.FOUND,
            url=url,
            display_name="Marques Brownlee",
            handle="mkbhd",
            evidence=["name_match", "handle_match"],
            tier="likely",
        ),
    )
    presence = SocialPresence(
        platform=SocialPlatform.YOUTUBE, status=SocialStatus.NOT_FOUND
    )

    result = orchestrator._second_check_youtube(_tiktok_profile(), presence)

    assert result.status is SocialStatus.VERIFIED
    assert result.confidence_score == 0.95
    assert result.verified_url == "https://www.youtube.com/@mkbhd"
    assert result.handle == "mkbhd"


def test_mode_two_leaves_a_found_channel_alone(monkeypatch):
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(
        judge,
        "propose_youtube_searched",
        lambda *a, **k: pytest.fail("the web must not be asked again"),
    )
    presence = SocialPresence(
        platform=SocialPlatform.YOUTUBE, status=SocialStatus.VERIFIED
    )

    result = _orchestrator(monkeypatch)._second_check_youtube(
        _tiktok_profile(), presence
    )

    assert result.status is SocialStatus.VERIFIED


def test_mode_two_does_not_claim_a_channel_the_browser_could_not_confirm(
    monkeypatch,
):
    """The web proposed a channel but the page did not confirm it: the
    creator is put in the review bucket, not counted as having a channel."""
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(
        judge,
        "propose_youtube_searched",
        lambda *a, **k: _search_answer(
            {"youtube": ("yes", "https://www.youtube.com/@mkbhd")}
        ),
    )
    orchestrator = _orchestrator(monkeypatch)
    monkeypatch.setattr(
        orchestrator.verifier_tool,
        "verify_url",
        lambda url, platform, creator: sv.CheckResult(
            platform=platform,
            verdict=sv.Verdict.UNKNOWN,
            url=url,
            detail="the page could not be read",
        ),
    )
    presence = SocialPresence(
        platform=SocialPlatform.YOUTUBE, status=SocialStatus.NOT_FOUND
    )

    result = orchestrator._second_check_youtube(_tiktok_profile(), presence)

    assert result.status is SocialStatus.INCONCLUSIVE


# --------------------------------------------------------------------------- #
# Mode 3: social discovery
# --------------------------------------------------------------------------- #
def _no_plain_proposal(monkeypatch):
    monkeypatch.setattr(
        judge, "propose", lambda *a, **k: judge.Proposal(candidates={})
    )


def test_mode_three_asks_the_web_about_a_platform_with_no_result(monkeypatch):
    monkeypatch.setattr(sd, "resolve_channel", lambda text, session=None: _record())
    monkeypatch.setattr(judge, "any_key", lambda: True)
    _no_plain_proposal(monkeypatch)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: _search_answer(
            {"facebook": ("yes", "https://www.facebook.com/MrBeast")}
        ),
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast": _facebook_page()}
    )

    result = sd.discover(session, "@MrBeast")

    outcome = result.outcome("facebook")
    assert outcome.verdict == sv.Verdict.FOUND.value
    assert outcome.source == "both"


def test_mode_three_keeps_the_browsers_not_found_verdict(monkeypatch):
    """The page said the account is not there, and the web agreed."""
    monkeypatch.setattr(
        sd,
        "resolve_channel",
        lambda text, session=None: _record(["https://www.facebook.com/MrBeast/"]),
    )
    monkeypatch.setattr(judge, "any_key", lambda: True)
    _no_plain_proposal(monkeypatch)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: _search_answer({"facebook": ("no", "")}),
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast/": _missing_facebook_page()}
    )

    result = sd.discover(session, "@MrBeast")

    outcome = result.outcome("facebook")
    assert outcome.verdict == sv.Verdict.NOT_FOUND.value
    assert outcome.source == "both"
    assert "neither the AI nor the browser" in outcome.detail


def test_mode_three_does_not_ask_the_web_when_the_budget_is_spent(monkeypatch):
    monkeypatch.setattr(
        sd,
        "resolve_channel",
        lambda text, session=None: _record(["https://www.facebook.com/MrBeast/"]),
    )
    monkeypatch.setattr(judge, "any_key", lambda: True)
    _no_plain_proposal(monkeypatch)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: pytest.fail("the web must not be asked"),
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast/": _missing_facebook_page()}
    )

    result = sd.discover(
        session, "@MrBeast", budget=dual_check.SearchBudget(limit=0)
    )

    assert result.outcome("facebook") is None


def test_mode_three_writes_the_reconciliation_to_the_log(monkeypatch):
    monkeypatch.setattr(sd, "resolve_channel", lambda text, session=None: _record())
    monkeypatch.setattr(judge, "any_key", lambda: True)
    _no_plain_proposal(monkeypatch)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: _search_answer(
            {"facebook": ("yes", "https://www.facebook.com/MrBeast")}
        ),
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast": _facebook_page()}
    )
    lines: list[str] = []

    sd.discover(session, "@MrBeast", ops=Ops(lines.append))

    text = "\n".join(lines)
    assert "+ reconcile | both | facebook" in text
    assert "+ budget | ai | search" in text


# --------------------------------------------------------------------------- #
# The log never carries a secret
# --------------------------------------------------------------------------- #
def test_the_key_never_reaches_the_operation_log(monkeypatch):
    monkeypatch.setattr(judge, "gemini_key", lambda: "super-secret-key")
    monkeypatch.setattr(judge, "groq_key", lambda: "")
    monkeypatch.setattr(
        judge,
        "_ask_gemini_search",
        lambda prompt, key, model: (
            "facebook: yes\nfacebook url: https://www.facebook.com/MKBHD",
            [],
        ),
    )
    lines: list[str] = []

    judge.propose_searched(
        "Marques Brownlee", "mkbhd", 21_000_000, "", ops=Ops(lines.append)
    )

    assert lines
    assert "super-secret-key" not in "\n".join(lines)


def test_the_log_of_a_full_run_carries_no_key(monkeypatch):
    monkeypatch.setattr(sd, "resolve_channel", lambda text, session=None: _record())
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(judge, "gemini_key", lambda: "super-secret-key")
    monkeypatch.setattr(judge, "groq_key", lambda: "")
    _no_plain_proposal(monkeypatch)
    monkeypatch.setattr(
        judge,
        "propose_searched",
        lambda *a, **k: _search_answer(
            {"facebook": ("yes", "https://www.facebook.com/MrBeast")}
        ),
    )
    session = _FakeSession(
        {"https://www.facebook.com/MrBeast": _facebook_page()}
    )
    lines: list[str] = []

    sd.discover(session, "@MrBeast", ops=Ops(lines.append))

    text = "\n".join(lines)
    assert text
    assert "super-secret-key" not in text
    assert "Authorization" not in text
