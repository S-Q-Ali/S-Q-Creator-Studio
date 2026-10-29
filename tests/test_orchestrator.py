"""Tests for AgentOrchestrator control flow (no network: search stubbed)."""

from typing import ClassVar

from s_q_ali_media_downloader.agent.orchestrator import AgentOrchestrator


def test_run_discovery_no_channels_returns_empty(monkeypatch):
    captured = []

    def fake_search_channels(*args, **kwargs):
        return []

    orchestrator = AgentOrchestrator(progress_callback=lambda p, m: captured.append((p, m)))
    monkeypatch.setattr(orchestrator.search_tool, "search_channels", fake_search_channels)

    result = orchestrator.run_discovery("nothing interesting", max_channels=10)

    assert result.total_searched == 0
    assert result.channels_matching_filter == 0
    assert result.channels == []
    assert result.query == "nothing interesting"
    assert captured[0][1].startswith("Initializing Agent")
    assert captured[-1][0] == 100


def test_progress_callback_errors_are_swallowed():
    def bad_callback(percent, message):
        raise RuntimeError("ui gone")

    orchestrator = AgentOrchestrator(progress_callback=bad_callback)
    # _emit must never bubble the callback's failure into the pipeline
    orchestrator._emit(10, "started")
    orchestrator._emit(10, "started")
    assert True


def test_every_youtube_step_is_written_to_the_activity_log(monkeypatch):
    lines = []
    orchestrator = AgentOrchestrator(log_callback=lines.append)
    monkeypatch.setattr(
        orchestrator.search_tool, "search_channels", lambda **kwargs: []
    )

    orchestrator.run_discovery("nobody", max_channels=10)

    text = "\n".join(lines)
    assert "YouTube discovery" in text
    assert "yt-dlp" in text
    assert "Found 0 candidate channels" in text
    assert "0 channels found" in text


def test_every_tiktok_step_is_written_to_the_activity_log(monkeypatch):
    lines = []
    orchestrator = AgentOrchestrator(log_callback=lines.append)
    monkeypatch.setattr(
        orchestrator.tiktok_tool, "search_profiles", lambda *a, **k: []
    )

    orchestrator.run_tiktok_discovery("cats")

    text = "\n".join(lines)
    assert "TikTok discovery" in text
    assert "TikTok search" in text
    assert "Found 0 TikTok profiles" in text


def test_a_log_callback_error_does_not_stop_the_pipeline(monkeypatch):
    def bad_log(message):
        raise RuntimeError("log widget gone")

    orchestrator = AgentOrchestrator(log_callback=bad_log)
    monkeypatch.setattr(
        orchestrator.search_tool, "search_channels", lambda **kwargs: []
    )

    result = orchestrator.run_discovery("x")

    assert result.total_searched == 0


def test_run_discovery_without_callback(monkeypatch):
    from s_q_ali_media_downloader.agent.schema import AgentSearchResult as Result

    class FakeSearch:
        def search_channels(self, **kwargs):
            return []

    orchestrator = AgentOrchestrator()
    monkeypatch.setattr(orchestrator.search_tool, "search_channels", FakeSearch().search_channels)
    result = orchestrator.run_discovery("x")
    assert isinstance(result, Result)
    assert result.total_searched == 0


# --------------------------------------------------------------------------- #
# The AI step: the mode used to reuse the channel handle as its only guess
# --------------------------------------------------------------------------- #
def _channel(**kwargs):
    from s_q_ali_media_downloader.agent.schema import ChannelMetadata

    data = {
        "channel_id": "UC1",
        "title": "Marques Brownlee",
        "handle": "mkbhd",
        "subscribers": 21_000_000,
        "youtube_url": "https://www.youtube.com/@mkbhd",
        "description": "tech videos",
    }
    data.update(kwargs)
    return ChannelMetadata(**data)


def _fake_proposal(monkeypatch, candidates):
    from s_q_ali_media_downloader.agent.tools import social_judge as judge

    class FakeProposal:
        reason = "the model knows this creator"
        provider = "gemini"
        model = "gemini-3.6-flash"

    fake = FakeProposal()
    fake.candidates = candidates
    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(judge, "propose", lambda *a, **k: fake)
    return fake


def test_the_ai_names_the_accounts_the_bio_does_not_list(monkeypatch):
    _fake_proposal(
        monkeypatch,
        {"facebook": ["mkbhd"], "instagram": ["mkbhd"], "tiktok": ["mkbhd"]},
    )
    channel = _channel()

    AgentOrchestrator()._propose_socials([channel], True, True, True)

    assert channel.facebook.verified_url == "https://www.facebook.com/mkbhd"
    assert channel.instagram.verified_url == "https://www.instagram.com/mkbhd/"
    assert channel.tiktok.verified_url == "https://www.tiktok.com/@mkbhd"
    assert channel.facebook.source == "model"


def test_the_creators_own_link_wins_over_the_models_guess(monkeypatch):
    _fake_proposal(monkeypatch, {"facebook": ["guess"], "instagram": ["mkbhd"]})
    channel = _channel()
    channel.facebook.verified_url = "https://www.facebook.com/realMKBHD"
    channel.facebook.source = "bio_link"

    AgentOrchestrator()._propose_socials([channel], True, True, False)

    assert channel.facebook.verified_url == "https://www.facebook.com/realMKBHD"
    assert channel.facebook.source == "bio_link"
    assert channel.instagram.verified_url == "https://www.instagram.com/mkbhd/"


def test_a_channel_that_links_everything_is_not_asked_about(monkeypatch):
    from s_q_ali_media_downloader.agent.tools import social_judge as judge

    def boom(*args, **kwargs):
        raise AssertionError("the AI must not be asked about a complete channel")

    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(judge, "propose", boom)
    channel = _channel()
    channel.facebook.verified_url = "https://www.facebook.com/mkbhd"
    channel.facebook.source = "bio_link"
    channel.instagram.verified_url = "https://www.instagram.com/mkbhd/"
    channel.instagram.source = "bio_link"

    AgentOrchestrator()._propose_socials([channel], True, True, False)

    assert channel.facebook.verified_url == "https://www.facebook.com/mkbhd"


def test_the_tiktok_mode_asks_for_the_youtube_channel(monkeypatch):
    from s_q_ali_media_downloader.agent.schema import TikTokProfileMetadata
    from s_q_ali_media_downloader.agent.tools import social_judge as judge

    class FakeProposal:
        candidates: ClassVar[dict[str, list[str]]] = {"youtube": ["mkbhd"]}
        reason = "known"
        provider = "gemini"
        model = "gemini-3.6-flash"

    monkeypatch.setattr(judge, "any_key", lambda: True)
    monkeypatch.setattr(judge, "propose_youtube", lambda *a, **k: FakeProposal())
    profile = TikTokProfileMetadata(
        profile_id="1",
        handle="mkbhd",
        nickname="Marques Brownlee",
        followers=1000,
    )

    handle = AgentOrchestrator()._suggest_youtube_handle(profile)

    assert handle == "mkbhd"


def test_the_tiktok_mode_copes_without_an_ai_key(monkeypatch):
    from s_q_ali_media_downloader.agent.schema import TikTokProfileMetadata
    from s_q_ali_media_downloader.agent.tools import social_judge as judge

    monkeypatch.setattr(judge, "any_key", lambda: False)
    profile = TikTokProfileMetadata(profile_id="1", handle="mkbhd")

    assert AgentOrchestrator()._suggest_youtube_handle(profile) is None


def test_the_verifier_is_told_who_the_creator_is(monkeypatch):
    """The pages are judged against this creator, so the verifier has to
    know who that is."""
    from s_q_ali_media_downloader.agent.schema import (
        SocialPlatform,
        SocialPresence,
    )

    captured = {}

    async def fake_verify(**kwargs):
        captured.update(kwargs)
        presence = SocialPresence(platform=SocialPlatform.FACEBOOK)
        return presence, presence, presence

    orchestrator = AgentOrchestrator()
    monkeypatch.setattr(
        orchestrator.verifier_tool, "verify_channel_socials", fake_verify
    )

    orchestrator._loop.run_until_complete(
        orchestrator._verify_all_socials([_channel()], True, True, False)
    )

    creator = captured["creator"]
    assert creator.title == "Marques Brownlee"
    assert creator.handle == "mkbhd"
    assert creator.channel_id == "UC1"
    assert creator.url == "https://www.youtube.com/@mkbhd"