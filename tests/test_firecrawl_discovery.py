"""Tests for Firecrawl primary discovery, fallback chain, Settings UI, and P1–P5 accuracy fixes."""

from __future__ import annotations

import httpx

from s_q_ali_media_downloader.agent.schema import (
    SocialStatus,
    TikTokProfileMetadata,
)
from s_q_ali_media_downloader.agent.tools import social_judge as judge
from s_q_ali_media_downloader.agent.tools import social_resolve as resolve
from s_q_ali_media_downloader.agent.tools import social_verify as verify
from s_q_ali_media_downloader.agent.tools.browser import Page
from s_q_ali_media_downloader.agent.tools.social_verifier import (
    _identity_status,
)
from s_q_ali_media_downloader.agent.tools.tiktok_search import TikTokSearchTool
from s_q_ali_media_downloader.agent.tools.youtube_existence import YouTubeExistenceTool
from s_q_ali_media_downloader.core import settings_store
from s_q_ali_media_downloader.core.youtube_client import ChannelInfo


def test_firecrawl_key_sealed_and_env_override(monkeypatch, tmp_path):
    from s_q_ali_media_downloader.agent.tools import firecrawl_client

    settings_store.configure(str(tmp_path / "test.db"))
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    assert firecrawl_client.firecrawl_key() is None

    settings_store.set_setting("firecrawl_api_key", "fc-stored-secret")
    assert firecrawl_client.firecrawl_key() == "fc-stored-secret"

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-env-override")
    assert firecrawl_client.firecrawl_key() == "fc-env-override"


def test_firecrawl_test_key_and_scrape(monkeypatch):
    from s_q_ali_media_downloader.agent.tools import firecrawl_client

    def fake_get(self, url, **kwargs):
        assert "credit-usage" in url
        return httpx.Response(
            200,
            json={"success": True, "data": {"remainingCredits": 485}},
        )

    def fake_post(self, url, **kwargs):
        if url.endswith("/scrape"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "markdown": "MrBeast (@mrbeast) • 60M followers",
                        "links": ["https://www.youtube.com/@MrBeast"],
                        "metadata": {
                            "title": "MrBeast (@mrbeast) • Instagram photos and videos",
                            "ogTitle": "MrBeast (@mrbeast) - Instagram photos and videos",
                            "ogDescription": "60M Followers, 100 Following",
                            "sourceURL": "https://www.instagram.com/mrbeast/",
                        },
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {
                        "url": "https://www.instagram.com/mrbeast/",
                        "title": "MrBeast (@mrbeast)",
                        "description": "Official Instagram of MrBeast",
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    summary = firecrawl_client.test_firecrawl_key("fc-test-123")
    assert "485" in summary

    page = firecrawl_client.scrape_page("https://www.instagram.com/mrbeast/", api_key="fc-test-123")
    assert page.meta.get("ogTitle") == "MrBeast (@mrbeast) - Instagram photos and videos"
    assert "https://www.youtube.com/@MrBeast" in page.links

    verdict = verify.verify_page(
        page,
        "instagram",
        verify.CreatorRef(title="MrBeast", handle="MrBeast", url="https://www.youtube.com/@MrBeast"),
    )
    assert verdict.verdict is verify.Verdict.FOUND


def test_settings_page_has_firecrawl_key_first(qapp, tmp_path, monkeypatch):
    from s_q_ali_media_downloader.ui.settings_page import FIRECRAWL_KEY, SettingsPage

    settings_store.configure(str(tmp_path / "settings.db"))
    monkeypatch.setenv("SQ_SETTINGS_FILE", str(tmp_path / "prefs.ini"))

    page = SettingsPage()
    page.load()
    assert hasattr(page, "firecrawl_edit")
    assert hasattr(page, "btn_test_firecrawl")

    page.firecrawl_edit.setText("fc-my-key-999")
    assert settings_store.get_setting(FIRECRAWL_KEY) == "fc-my-key-999"


def test_propose_searched_uses_firecrawl_first_then_falls_back(monkeypatch):
    from s_q_ali_media_downloader.agent.tools import firecrawl_client

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-primary")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-fallback")

    calls: list[str] = []

    def fake_fc_search(query: str, *, limit: int = 5, api_key: str | None = None):
        calls.append("firecrawl")
        return [
            firecrawl_client.SearchHit(
                url="https://www.instagram.com/mkbhd/",
                title="Marques Brownlee (@mkbhd)",
                description="Official Instagram of Marques Brownlee MKBHD",
            ),
            firecrawl_client.SearchHit(
                url="https://www.tiktok.com/@mkbhd",
                title="Marques Brownlee (@mkbhd) Official TikTok",
                description="MKBHD on TikTok",
            ),
        ]

    monkeypatch.setattr(firecrawl_client, "search", fake_fc_search)

    answer = judge.propose_searched(
        "Marques Brownlee",
        "mkbhd",
        20_000_000,
        "Tech videos",
        platforms=("instagram", "tiktok"),
    )
    assert calls == ["firecrawl"]
    assert answer.provider == "firecrawl"
    assert answer.get("instagram").is_yes
    assert "instagram.com/mkbhd" in answer.get("instagram").url

    # Now make Firecrawl fail and verify automatic fallback to Gemini
    def failing_fc_search(query: str, *, limit: int = 5, api_key: str | None = None):
        calls.append("firecrawl_fail")
        raise firecrawl_client.FirecrawlUnavailable("402 credits exhausted")

    def fake_gemini_search(prompt: str, key: str, model: str):
        calls.append("gemini")
        return (
            "instagram: yes\ninstagram url: https://www.instagram.com/mkbhd/\ninstagram quote: MKBHD",
            ["https://www.instagram.com/mkbhd/"],
        )

    monkeypatch.setattr(firecrawl_client, "search", failing_fc_search)
    monkeypatch.setattr(judge, "_ask_gemini_search", fake_gemini_search)

    fallback = judge.propose_searched(
        "Marques Brownlee",
        "mkbhd",
        20_000_000,
        "Tech videos",
        platforms=("instagram",),
    )
    assert "gemini" in calls
    assert fallback.provider == "gemini"
    assert fallback.get("instagram").is_yes


def test_tiktok_search_uses_firecrawl_first_then_ai_fallback(monkeypatch):
    from s_q_ali_media_downloader.agent.tools import firecrawl_client

    tool = TikTokSearchTool()
    monkeypatch.setattr(tool.api_session, "fetch_tag_handles", lambda *a, **k: [])
    monkeypatch.setattr(tool.api_session, "fetch_search_handles", lambda *a, **k: [])
    monkeypatch.setattr(tool, "_discover_via_ytdlp", lambda *a, **k: [])
    monkeypatch.setattr(tool, "enrich_profile", lambda p: p)

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
    monkeypatch.setattr(
        firecrawl_client,
        "search",
        lambda q, **kw: [
            firecrawl_client.SearchHit(
                url="https://www.tiktok.com/@speededits99/video/123",
                title="Speed Edits (@speededits99)",
                description="Best IShowSpeed edits",
            )
        ],
    )

    profiles = tool.search_profiles("ishowspeed edits", max_profiles=5)
    assert [p.handle for p in profiles] == ["speededits99"]
    assert tool.discovered_by == "firecrawl"


def test_p1_subscriber_tiebreaker_beats_impersonator(monkeypatch):
    clone = ChannelInfo(
        channel_id="UC_CLONE",
        title="CarryMinati",
        custom_url="https://www.youtube.com/@carryminati_fan12",
        subscriber_count=15,
    )
    official = ChannelInfo(
        channel_id="UC_OFFICIAL",
        title="CarryMinati Official",
        custom_url="https://www.youtube.com/@CarryMinati",
        subscriber_count=45_000_000,
    )
    monkeypatch.setattr(resolve, "search_channels", lambda *a, **k: [clone, official])
    picked = resolve._best_match("CarryMinati")
    assert picked is not None
    assert picked.channel_id == "UC_OFFICIAL"


def test_p2_resolve_channel_extracts_bio_links_from_description(monkeypatch):
    info = ChannelInfo(
        channel_id="UC_TEST",
        title="Test Creator",
        custom_url="https://www.youtube.com/@testcreator",
        subscriber_count=100_000,
        description="Follow me on IG: @testcreator_ig and https://www.tiktok.com/@testcreator_tt",
        uploads=[{"video_id": "vid123", "title": "Latest Video"}],
    )
    monkeypatch.setattr(resolve, "fetch_channel", lambda url: info)
    monkeypatch.setattr(
        resolve,
        "fetch_video_description",
        lambda vid: "Follow my Facebook: https://www.facebook.com/testcreator_fb",
    )

    class DummySession:
        def open(self, url):
            return Page(url=url, title="Test Creator - YouTube", links=[])

    record = resolve.resolve_channel("https://www.youtube.com/@testcreator", session=DummySession())
    assert "https://www.instagram.com/testcreator_ig/" in record.bio_links
    assert "https://www.tiktok.com/@testcreator_tt/" in record.bio_links
    assert "https://www.facebook.com/testcreator_fb/" in record.bio_links


def test_link_parser_handles_youtube_ytinitialdata_encodings():
    from s_q_ali_media_downloader.agent.tools.link_parser import LinkParserTool

    raw_about_script = (
        r'{"url":"https://www.youtube.com/redirect?event=channel_header&q=https%3A%2F%2Fwww.instagram.com%2Fmrbeast",'
        r'"tiktok":"https:\/\/www.tiktok.com\/@mrbeast",'
        r'"link":{"content":"facebook.com/MrBeast"}}'
    )
    fb, ig, tt = LinkParserTool.extract_social_links(raw_about_script, creator_text=False)
    assert fb == "https://www.facebook.com/MrBeast/"
    assert ig == "https://www.instagram.com/mrbeast/"
    assert tt == "https://www.tiktok.com/@mrbeast/"


def test_p3_identity_status_verifies_strong_model_match():
    status, score = _identity_status(
        ["name_match", "handle_match", "back_link"], is_bio_link=False
    )
    assert status is SocialStatus.VERIFIED
    assert score >= 0.85


def test_p4_youtube_existence_unquotes_percent40_backlink_and_reads_yt_text(monkeypatch):
    tool = YouTubeExistenceTool()

    def fake_get(self, url, **kwargs):
        return httpx.Response(
            200,
            text='<a href="https://www.youtube.com/redirect?q=https%3A%2F%2Fwww.tiktok.com%2F%40khaby.lame">TikTok</a>',
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    assert tool._channel_links_to_tiktok("https://www.youtube.com/@KhabyLame", "khaby.lame") is True

    profile = TikTokProfileMetadata(
        profile_id="creator1",
        handle="creator1",
        nickname="Creator One",
        profile_url="https://www.tiktok.com/@creator1",
        bio="Business inquiries only | YT: @CreatorOneOfficial",
    )
    presence = tool.check_youtube_presence(profile)
    assert presence.status is SocialStatus.VERIFIED
    assert presence.verified_url == "https://www.youtube.com/@CreatorOneOfficial"


def test_p5_parse_search_answer_uses_cited_sources_when_url_missing():
    text = "instagram: yes\ninstagram url: none\ninstagram quote: Official Instagram"
    answers = judge.parse_search_answer(
        text,
        platforms=("instagram",),
        sources=["https://www.instagram.com/realcreator/"],
    )
    assert answers["instagram"].is_yes
    assert answers["instagram"].url == "https://www.instagram.com/realcreator/"
