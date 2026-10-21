"""Tests for the AI analysis + thumbnail engine."""

from __future__ import annotations

import json

import pytest

from s_q_ali_media_downloader.niche_research.research import ai_analysis_engine as ai
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.youtube_client import (
    ChannelInfo,
    VideoInfo,
)

SAMPLE_JSON = """{"strategy":{"contentType":["educational","tech reviews"],"postingSchedule":"2-3 videos per week","thumbnailStyle":"Bold text, camera angle","titleFormula":"How to X","tagStrategy":["tech","tutorial"],"uniqueSellingPoints":["Shorts clips","Deep dives"]},"contentIdeas":[{"title":"Best AI tools","description":"Roundup of tools","contentType":"video","estimatedViews":"high","difficulty":"medium"},{"title":"Quick tip","description":"Short tip","contentType":"short","estimatedViews":"low","difficulty":"easy"}],"scripts":[{"title":"Best AI tools","hook":"Stop wasting money","intro":"In this video...","bodySections":["Section one","Section two"],"outro":"Thanks for watching","estimatedDuration":900}],"growthBlueprint":{"30day":{"goals":["10 videos"],"actions":["Post weekly"],"metrics":["views"]},"60day":{"goals":[],"actions":[],"metrics":[]},"90day":{"goals":[],"actions":[],"metrics":[]}}}"""


@pytest.fixture(autouse=True)
def _db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


def test_providers_priority_from_settings(isolated_appdata):
    assert ai.get_providers() == []
    db.set_setting("groq_api_key", "k-groq")
    db.set_setting("aihubmix_api_key", "k-ai")
    providers = ai.get_providers()
    assert [p["name"] for p in providers] == ["aihubmix", "groq"]
    for provider in providers:
        assert provider["api_key"].startswith("k-")


def test_get_providers_includes_google_ai_key(isolated_appdata):
    """Regression: Settings stores google_ai_api_key but get_providers read
    google_api_key, hiding a configured Google AI key from channel analysis."""
    db.set_setting("google_ai_api_key", "k-google")
    providers = ai.get_providers()
    assert [p["name"] for p in providers] == ["google"]
    assert providers[0]["api_key"] == "k-google"


@pytest.mark.parametrize(
    "name, model",
    [
        ("groq", "openai/gpt-oss-20b"),
        ("aihubmix", "gpt-5.5-free"),
        ("openrouter", "openrouter/free"),
        ("google", "gemini-2.0-flash"),
    ],
)
def test_provider_defs_carry_api_key(name, model, isolated_appdata):
    provider = ai._provider_def(name, "sk-test-123")
    assert provider["api_key"] == "sk-test-123"
    assert provider["model"] == model


def test_provider_def_unknown_raises(isolated_appdata):
    with pytest.raises(ValueError, match="Unknown provider"):
        ai._provider_def("nonexistent", "k")


class _StatusResponse:
    status_code = 200
    text = ""

    def json(self):
        return {"choices": [{"message": {"content": "OK"}}]}


class _SeqClient:
    def __init__(self, statuses):
        self._queue = list(statuses)
        self.posts: list = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def post(self, url, headers=None, json=None):
        self.posts.append(url)
        res = _StatusResponse()
        res.status_code = self._queue.pop(0)
        return res


def test_call_provider_no_retry_on_client_error(isolated_appdata, monkeypatch):
    client = _SeqClient([401, 401, 401])
    monkeypatch.setattr(ai.httpx, "Client", lambda *a, **k: client)
    monkeypatch.setattr("time.sleep", lambda *a: None)
    with pytest.raises(RuntimeError, match="401"):
        ai.call_provider(ai._provider_def("openrouter", "k"), "hi")
    assert len(client.posts) == 1


def test_call_provider_retries_rate_limit(isolated_appdata, monkeypatch):
    client = _SeqClient([429, 429, 429])
    monkeypatch.setattr(ai.httpx, "Client", lambda *a, **k: client)
    monkeypatch.setattr("time.sleep", lambda *a: None)
    with pytest.raises(RuntimeError, match="rate limited"):
        ai.call_provider(ai._provider_def("openrouter", "k"), "hi")
    assert len(client.posts) == 3


def test_call_provider_retries_server_error(isolated_appdata, monkeypatch):
    client = _SeqClient([500, 500, 500])
    monkeypatch.setattr(ai.httpx, "Client", lambda *a, **k: client)
    monkeypatch.setattr("time.sleep", lambda *a: None)
    with pytest.raises(RuntimeError, match="500"):
        ai.call_provider(ai._provider_def("openrouter", "k"), "hi")
    assert len(client.posts) == 3


def test_build_prompt_contains_channel_and_top_videos(isolated_appdata):
    channel = ChannelInfo(
        channel_id="UC1",
        title="Test Channel",
        subscriber_count=1000,
        view_count=50_000,
        video_count=10,
        description="Long desc a" * 50,
    )
    videos = [
        VideoInfo(video_id=f"v{i}", title=f"Video {i}", view_count=100 * i, like_count=10 * i)
        for i in range(1, 8)
    ]
    prompt = ai.build_analysis_prompt(channel, videos)
    assert "Test Channel" in prompt
    assert "Subscribers: 1,000" in prompt
    assert "Video 1" in prompt
    assert "Video 5" in prompt
    assert "Video 6" not in prompt  # only top 5
    assert "(channel.description" not in prompt


def test_parse_analysis_response_full(isolated_appdata):
    analysis = ai.parse_analysis_response(SAMPLE_JSON)
    assert analysis.strategy.contentType == ["educational", "tech reviews"]
    assert analysis.strategy.postingSchedule == "2-3 videos per week"
    assert len(analysis.contentIdeas) == 2
    assert analysis.contentIdeas[0].estimatedViews == "high"
    assert analysis.contentIdeas[1].contentType == "short"
    assert analysis.scripts[0].bodySections == ["Section one", "Section two"]
    assert analysis.scripts[0].estimatedDuration == 900
    assert analysis.growthBlueprint["30day"].goals == ["10 videos"]
    assert analysis.growthBlueprint["90day"].goals == []


def test_parse_analysis_response_defaults_with_garbage(isolated_appdata):
    analysis = ai.parse_analysis_response('{"contentIdeas":[{"title":"x"}]}')
    assert analysis.strategy.contentType  # falls back to defaults
    assert analysis.contentIdeas[0].title == "x"
    assert analysis.contentIdeas[0].difficulty == "medium"
    assert analysis.growthBlueprint["30day"].goals == []


def test_parse_analysis_response_rejects_non_json(isolated_appdata):
    with pytest.raises(RuntimeError):
        ai.parse_analysis_response("no json here")


def test_save_and_get_analysis_roundtrip(isolated_appdata):
    analysis = ai.parse_analysis_response(SAMPLE_JSON)
    ai.save_analysis("UCabc", analysis)

    assert ai.is_analyzed("UCabc") is True
    assert ai.is_analyzed("UCother") is False

    got = ai.get_analysis("UCabc")
    assert got["strategy"]["contentType"] == ["educational", "tech reviews"]
    assert len(got["contentIdeas"]) == 2
    assert got["scripts"][0]["bodySections"] == ["Section one", "Section two"]
    assert got["growthBlueprint"]["30day"]["goals"] == ["10 videos"]
    assert got["growthBlueprint"]["60day"]["goals"] == []


def test_save_analysis_overwrites_previous(isolated_appdata):
    ai.save_analysis("UCabc", ai.parse_analysis_response(SAMPLE_JSON))
    empty = ai.parse_analysis_response('{"contentIdeas":[]}')
    empty.contentIdeas = []
    empty.scripts = []
    ai.save_analysis("UCabc", empty)
    got = ai.get_analysis("UCabc")
    assert got["contentIdeas"] == []
    assert got["scripts"] == []


def test_analyze_channel_runs_and_persists(isolated_appdata, monkeypatch):
    monkeypatch.setattr(
        ai,
        "get_providers",
        lambda: [{"name": "fake", "base_url": "", "model": "m", "max_tokens": 1, "api_key": "k"}],
    )
    monkeypatch.setattr(ai, "call_provider", lambda provider, prompt: SAMPLE_JSON)
    monkeypatch.setattr(
        ai,
        "fetch_channel",
        lambda channel_id, cookiefile=None, **kwargs: ChannelInfo(
            channel_id=channel_id,
            title="Analyzable",
            subscriber_count=5,
            uploads=[
                {"video_id": "v1"},
                {"video_id": "v2"},
                {"video_id": "v3"},
            ],
        ),
    )
    captured_ids: list = []

    def fake_fetch_videos(ids, cookiefile=None, progress=None):
        captured_ids.extend(ids)
        return [VideoInfo(video_id=i, title=f"Video {i}", view_count=100) for i in ids]

    monkeypatch.setattr(ai, "fetch_videos", fake_fetch_videos)

    analysis = ai.analyze_channel("UCxyz")
    assert analysis.strategy.contentType
    assert ai.is_analyzed("UCxyz") is True
    # upload ids (real key video_id) must reach fetch_videos, not an empty list
    assert sorted(captured_ids) == ["v1", "v2", "v3"]


def test_load_channel_analysis_data_recent_videos(isolated_appdata, monkeypatch):
    monkeypatch.setattr(
        ai,
        "fetch_channel",
        lambda channel_id, cookiefile=None, **kwargs: ChannelInfo(
            channel_id=channel_id,
            title="Recent-y",
            uploads=[
                {
                    "video_id": f"u{i}",
                    "title": f"Upload {i}",
                    "view_count": 1000 * i,
                    "upload_date": "2026080" + str(i),
                    "thumbnail_url": f"https://x/u{i}.jpg",
                }
                for i in range(3)
            ],
        ),
    )
    data = ai.load_channel_analysis_data("UCabc")
    recent = data["recentVideos"]
    assert len(recent) == 3
    assert recent[0]["videoId"] == "u0"
    assert recent[0]["title"] == "Upload 0"
    assert recent[0]["viewCount"] == 0
    assert recent[1]["viewCount"] == 1000
    assert recent[0]["thumbnailUrl"] == "https://x/u0.jpg"
    assert recent[1]["publishedAt"] == "2026-08-01"


def test_analyze_channel_no_providers_raises(isolated_appdata, monkeypatch):
    monkeypatch.setattr(ai, "get_providers", list)
    with pytest.raises(RuntimeError, match="No AI providers"):
        ai.analyze_channel("UCxyz")


def test_generate_thumbnail_no_image_provider_messages_settings(isolated_appdata):
    result = ai.generate_thumbnail("My video")
    assert result["success"] is False
    assert "Settings" in result["error"]
    assert "No AI image provider" in result["error"]


def test_image_provider_defs_honor_primary_and_keys(isolated_appdata):
    assert ai._image_provider_defs() == []
    db.set_setting("google_ai_api_key", "k-google")
    db.set_setting("openrouter_api_key", "k-or")
    defs = ai._image_provider_defs()
    assert [d["name"] for d in defs] == ["google", "openrouter"]
    db.set_setting("ai_primary_provider", "openrouter")
    defs = ai._image_provider_defs()
    assert [d["name"] for d in defs] == ["openrouter", "google"]


def test_parse_gemini_image_response_finds_inline_data(isolated_appdata):
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Here is your thumbnail"},
                        {"inlineData": {"mimeType": "image/png", "data": "QUJD"}},
                    ]
                }
            }
        ]
    }
    result = ai._parse_image_response("google", "gemini_content", data)
    assert result["success"] is True
    assert result["imageData"] == "data:image/png;base64,QUJD"


def test_parse_gemini_image_response_no_inline_data(isolated_appdata):
    data = {"candidates": [{"content": {"parts": [{"text": "only text"}]}}]}
    result = ai._parse_image_response("google", "gemini_content", data)
    assert result["success"] is False
    assert "No image" in result["error"]


def test_parse_openai_image_response_b64(isolated_appdata):
    result = ai._parse_image_response(
        "aihubmix", "openai_images", {"data": [{"b64_json": "YWJj"}]}
    )
    assert result["success"] is True
    assert result["imageData"] == "data:image/png;base64,YWJj"


def test_parse_image_response_error_field(isolated_appdata):
    result = ai._parse_image_response(
        "openrouter", "openrouter_images", {"error": {"message": "bad request"}}
    )
    assert result["success"] is False
    assert "bad request" in result["error"]


def test_generate_thumbnail_falls_back_across_providers(isolated_appdata, monkeypatch):
    db.set_setting("aihubmix_api_key", "k1")
    db.set_setting("google_ai_api_key", "k2")
    calls = []

    def fake_call(provider, prompt):
        calls.append(provider["name"])
        if provider["name"] == "aihubmix":
            return {"success": False, "error": "boom 401"}
        return {"success": True, "imageData": "data:image/png;base64,QUJD"}

    monkeypatch.setattr(ai, "_call_image_provider", fake_call)
    result = ai.generate_thumbnail("T")
    assert result["success"] is True
    assert calls == ["aihubmix", "google"]


def test_generate_thumbnail_all_providers_fail_is_clear(isolated_appdata, monkeypatch):
    db.set_setting("aihubmix_api_key", "k1")

    def fake_call(provider, prompt):
        return {"success": False, "error": "nope"}

    monkeypatch.setattr(ai, "_call_image_provider", fake_call)
    result = ai.generate_thumbnail("T")
    assert result["success"] is False
    assert "aihubmix" in result["error"]


def test_generate_thumbnail_styles_build_prompt_shape(isolated_appdata, monkeypatch):
    db.set_setting("aihubmix_api_key", "key")
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": [{"b64_json": "abc123"}]}

        @property
        def text(self):
            return ""

    class FakeCtx:
        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return FakeCtx()

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(ai.httpx, "Client", FakeClient)
    result = ai.generate_thumbnail("Big title", style="vibrant", niche="Tech")
    assert result["success"] is True
    assert result["imageData"].startswith("data:image/png;base64,")
    assert captured["url"].endswith("/v1/images/generations")
    assert captured["payload"]["size"] == "1536x1024"
    assert captured["payload"]["response_format"] == "b64_json"
    assert "vibrant" in captured["payload"]["prompt"]
    assert "Niche: Tech" in captured["payload"]["prompt"]


# --------------------------------------------------------------------------- #
# Regression (2026-10): a cancelled analysis must not buy another provider call
# --------------------------------------------------------------------------- #
def test_analyze_channel_stops_before_calling_a_provider_when_cancelled(monkeypatch):
    db.set_setting("groq_api_key", "k-groq")
    calls: list[str] = []

    def fake_call(provider, prompt):
        calls.append(provider["name"])
        return SAMPLE_JSON

    monkeypatch.setattr(ai, "call_provider", fake_call)
    monkeypatch.setattr(
        ai, "fetch_channel", lambda *a, **kw: ChannelInfo(channel_id="UCx", title="T")
    )
    monkeypatch.setattr(ai, "fetch_videos", lambda *a, **kw: [])

    with pytest.raises(RuntimeError, match="cancel"):
        ai.analyze_channel("UCx", cancel=lambda: True)

    assert calls == []


# --------------------------------------------------------------------------- #
# Regression (2026-10): the whole analysis has to be stored, not just the plan
# --------------------------------------------------------------------------- #
def test_the_full_analysis_is_stored_not_just_the_strategy(isolated_appdata):
    """analysis_json held only the strategy, so the stored analysis could
    never be read back as a whole."""
    analysis = ai.parse_analysis_response(SAMPLE_JSON)
    ai.save_analysis("UCx", analysis)

    row = db.get(
        "SELECT analysis_json FROM similar_channel_analysis WHERE source_channel_id = 'UCx'"
    )
    stored = json.loads(row["analysis_json"])

    assert stored["strategy"]["contentType"] == analysis.strategy.contentType
    assert len(stored["contentIdeas"]) == len(analysis.contentIdeas)
    assert len(stored["scripts"]) == len(analysis.scripts)
    assert "growthBlueprint" in stored


def test_get_analysis_reads_the_stored_analysis_back(isolated_appdata):
    analysis = ai.parse_analysis_response(SAMPLE_JSON)
    ai.save_analysis("UCx", analysis)

    result = ai.get_analysis("UCx")

    assert result["strategy"]["contentType"] == analysis.strategy.contentType
    assert len(result["contentIdeas"]) == len(analysis.contentIdeas)
    assert len(result["scripts"]) == len(analysis.scripts)


def test_get_analysis_still_reads_a_legacy_strategy_only_row(isolated_appdata):
    """Rows written by the previous release hold the strategy on its own."""
    db.run(
        "INSERT OR REPLACE INTO similar_channel_analysis "
        "(source_channel_id, target_channel_id, similarity_score, analysis_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("UCx", "UCx", 100, json.dumps({"contentType": ["educational"]}), db.now()),
    )

    result = ai.get_analysis("UCx")

    assert result["strategy"] == {"contentType": ["educational"]}


def test_scripts_are_linked_to_the_idea_they_came_from(isolated_appdata):
    """channel_scripts.idea_id existed in the schema but was never written."""
    payload = json.dumps(
        {
            "strategy": {"contentType": ["educational"]},
            "contentIdeas": [
                {"title": "Best AI tools", "description": "Roundup", "contentType": "video"},
                {"title": "Quick tip", "description": "Short", "contentType": "short"},
            ],
            "scripts": [
                {
                    "title": "Best AI tools",
                    "ideaTitle": "Best AI tools",
                    "hook": "Stop wasting money",
                    "intro": "In this video...",
                    "bodySections": ["Section one"],
                    "outro": "Thanks",
                    "estimatedDuration": 600,
                }
            ],
            "growthBlueprint": {},
        }
    )
    analysis = ai.parse_analysis_response(payload)
    ai.save_analysis("UCx", analysis)

    script = db.get("SELECT idea_id FROM channel_scripts WHERE channel_id = 'UCx'")
    idea = db.get(
        "SELECT id FROM channel_content_ideas WHERE channel_id = 'UCx' AND idea_title = ?",
        ("Best AI tools",),
    )

    assert idea is not None
    assert script["idea_id"] == idea["id"]


def test_a_script_without_an_idea_link_is_still_saved(isolated_appdata):
    """The model does not always name the idea — the script must survive."""
    analysis = ai.parse_analysis_response(SAMPLE_JSON)
    ai.save_analysis("UCx", analysis)

    script = db.get("SELECT idea_id FROM channel_scripts WHERE channel_id = 'UCx'")

    assert script is not None
    assert script["idea_id"] is None
