"""Tests for the AI agent that proposes candidates."""

from __future__ import annotations

import json

import httpx
import pytest

from s_q_ali_media_downloader.agent.tools import social_judge as sj


def test_the_description_is_cut_short_and_marked_as_data():
    """The description is written by whoever owns the channel, so it is
    data — and only the first part of it is sent."""
    prompt = sj.build_prompt("MrBeast", "MrBeast", 522_000_000, "#" * 2000)

    assert "<channel_description>" in prompt
    assert "untrusted data" in prompt
    assert prompt.count("#") == sj.DESCRIPTION_LIMIT


def test_a_good_answer_becomes_candidates():
    answer = json.dumps(
        {
            "facebook": ["MrBeast"],
            "instagram": ["mrbeast"],
            "tiktok": ["mrbeast"],
            "reason": "same handle everywhere",
            "confidence": "high",
        }
    )

    proposal = sj.parse_response(answer)

    assert proposal.candidates["facebook"] == ["MrBeast"]
    assert proposal.confidence == "high"
    assert proposal.reason == "same handle everywhere"


def test_an_unknown_creator_yields_no_candidates():
    """The model must be allowed to say 'I do not know' — that is what keeps
    the false-positive rate at zero."""
    answer = json.dumps(
        {
            "facebook": [],
            "instagram": [],
            "tiktok": [],
            "reason": "no information",
            "confidence": "none",
        }
    )

    proposal = sj.parse_response(answer)

    assert proposal.candidates == {}
    assert proposal.all_candidates() == {}


def test_a_malformed_answer_is_a_failure_not_a_candidate():
    with pytest.raises(sj.JudgeUnavailable):
        sj.parse_response("I think the handle is probably mrbeast?")


def test_an_empty_answer_is_a_failure():
    with pytest.raises(sj.JudgeUnavailable):
        sj.parse_response("   ")


def test_a_url_is_never_accepted_as_a_handle():
    answer = json.dumps(
        {
            "facebook": ["https://facebook.com/mrbeast"],
            "instagram": ["@mrbeast"],
            "tiktok": ["mr beast"],
            "reason": "",
            "confidence": "low",
        }
    )

    proposal = sj.parse_response(answer)

    assert proposal.candidates.get("facebook") is None
    assert proposal.candidates["instagram"] == ["mrbeast"]
    assert proposal.candidates.get("tiktok") is None


def test_the_candidates_become_urls_for_the_verifier():
    proposal = sj.Proposal(
        candidates={"facebook": ["MrBeast"], "tiktok": ["mrbeast"]}
    )

    urls = sj.candidate_urls(proposal)

    assert urls["facebook"] == ["https://www.facebook.com/MrBeast"]
    assert urls["tiktok"] == ["https://www.tiktok.com/@mrbeast"]


def test_without_a_key_the_agent_says_so(monkeypatch):
    monkeypatch.setattr(sj, "groq_key", lambda: None)

    with pytest.raises(sj.JudgeUnavailable) as excinfo:
        sj.propose("MrBeast", "MrBeast")

    assert "key" in str(excinfo.value).lower()


def test_the_environment_key_overrides_the_stored_one(monkeypatch):
    """A .env file is a deliberate local override and wins."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_from_env")
    monkeypatch.setattr(sj.settings_store, "get_setting", lambda key: "stored-key")

    assert sj.groq_key() == "gsk_from_env"


def test_the_stored_key_is_used_when_the_environment_has_none(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(sj.settings_store, "get_setting", lambda key: "stored-key")

    assert sj.groq_key() == "stored-key"


def test_the_gemini_key_comes_from_the_environment_first(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-from-env")
    monkeypatch.setattr(sj.settings_store, "get_setting", lambda key: "stored-gemini")

    assert sj.gemini_key() == "gemini-from-env"


def test_the_stored_gemini_key_is_used_when_the_environment_has_none(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(sj.settings_store, "get_setting", lambda key: "stored-gemini")

    assert sj.gemini_key() == "stored-gemini"


def test_groq_is_tried_first_and_gemini_is_not_called(monkeypatch):
    seen = {"gemini": False}

    def fake_groq(payload, key, timeout=60.0):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "facebook": ["MrBeast"],
                                "instagram": [],
                                "tiktok": [],
                                "reason": "known",
                                "confidence": "high",
                            }
                        )
                    }
                }
            ],
            "usage": {"total_tokens": 11},
        }

    def fake_gemini(payload, key, timeout=60.0):
        seen["gemini"] = True
        raise AssertionError("Gemini must not run when Groq answered")

    monkeypatch.setattr(sj, "_post_groq", fake_groq)
    monkeypatch.setattr(sj, "_post_gemini", fake_gemini)
    monkeypatch.setattr(sj, "groq_key", lambda: "gsk_test")
    monkeypatch.setattr(sj, "gemini_key", lambda: "gemini_test")

    proposal = sj.propose("MrBeast", "MrBeast")

    assert proposal.provider == "groq"
    assert proposal.candidates["facebook"] == ["MrBeast"]
    assert seen["gemini"] is False


def test_groq_failure_falls_back_to_gemini(monkeypatch):
    answer = json.dumps(
        {
            "facebook": [],
            "instagram": ["mrbeast"],
            "tiktok": [],
            "reason": "the model knows this creator",
            "confidence": "medium",
        }
    )

    def fake_groq(payload, key, timeout=60.0):
        raise sj.JudgeUnavailable("Groq answered 503: unavailable")

    def fake_gemini(payload, key, timeout=60.0):
        assert payload["model"] == sj.GEMINI_MODEL
        assert payload["response_format"]["mime_type"] == "application/json"
        return {
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": answer}],
                }
            ],
            "usage": {"total_tokens": 42},
        }

    monkeypatch.setattr(sj, "_post_groq", fake_groq)
    monkeypatch.setattr(sj, "_post_gemini", fake_gemini)
    monkeypatch.setattr(sj, "groq_key", lambda: "gsk_test")
    monkeypatch.setattr(sj, "gemini_key", lambda: "gemini_test")

    proposal = sj.propose("MrBeast", "MrBeast")

    assert proposal.provider == "gemini"
    assert proposal.model == sj.GEMINI_MODEL
    assert proposal.tokens == 42
    assert proposal.candidates["instagram"] == ["mrbeast"]


def test_without_a_groq_key_gemini_is_used(monkeypatch):
    def fake_gemini(payload, key, timeout=60.0):
        return {
            "steps": [
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "facebook": [],
                                    "instagram": [],
                                    "tiktok": ["mrbeast"],
                                    "reason": "known",
                                    "confidence": "high",
                                }
                            ),
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(sj, "groq_key", lambda: None)
    monkeypatch.setattr(sj, "gemini_key", lambda: "gemini_test")
    monkeypatch.setattr(sj, "_post_gemini", fake_gemini)

    proposal = sj.propose("MrBeast", "MrBeast")

    assert proposal.provider == "gemini"
    assert proposal.candidates["tiktok"] == ["mrbeast"]


def test_with_no_ai_key_at_all_both_providers_are_named(monkeypatch):
    monkeypatch.setattr(sj, "groq_key", lambda: None)
    monkeypatch.setattr(sj, "gemini_key", lambda: None)

    with pytest.raises(sj.JudgeUnavailable) as excinfo:
        sj.propose("MrBeast", "MrBeast")

    message = str(excinfo.value).lower()
    assert "groq" in message
    assert "gemini" in message


def test_both_provider_errors_are_reported(monkeypatch):
    monkeypatch.setattr(sj, "groq_key", lambda: "gsk_test")
    monkeypatch.setattr(sj, "gemini_key", lambda: "gemini_test")
    monkeypatch.setattr(
        sj,
        "_post_groq",
        lambda *a, **k: (_ for _ in ()).throw(sj.JudgeUnavailable("Groq 503")),
    )
    monkeypatch.setattr(
        sj,
        "_post_gemini",
        lambda *a, **k: (_ for _ in ()).throw(sj.JudgeUnavailable("Gemini 429")),
    )

    with pytest.raises(sj.JudgeUnavailable) as excinfo:
        sj.propose("MrBeast", "MrBeast")

    message = str(excinfo.value)
    assert "Groq 503" in message
    assert "Gemini 429" in message


def test_the_gemini_key_test_sends_one_small_request(monkeypatch):
    seen = {}

    def fake_post(payload, key, timeout=60.0):
        seen["payload"] = payload
        seen["key"] = key
        seen["timeout"] = timeout
        return {
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": "OK"}],
                }
            ]
        }

    monkeypatch.setattr(sj, "_post_gemini", fake_post)

    model = sj.test_gemini_key("gemini_test")

    assert model == sj.GEMINI_MODEL
    assert seen["key"] == "gemini_test"
    assert seen["payload"]["model"] == sj.GEMINI_MODEL
    assert seen["payload"]["generation_config"]["max_output_tokens"] <= 16
    assert seen["timeout"] <= 30


def test_the_key_test_sends_one_small_request(monkeypatch):
    seen = {}

    def fake_post(payload, key, timeout=60.0):
        seen["payload"] = payload
        seen["key"] = key
        seen["timeout"] = timeout
        return {"choices": [{"message": {"content": "OK"}}]}

    monkeypatch.setattr(sj, "_post_groq", fake_post)

    model = sj.test_key("gsk_test")

    assert model == sj.DEFAULT_MODEL
    assert seen["key"] == "gsk_test"
    assert seen["payload"]["model"] == sj.DEFAULT_MODEL
    assert seen["payload"]["max_completion_tokens"] <= 16
    assert seen["timeout"] <= 30


def test_without_a_key_the_key_test_says_so(monkeypatch):
    monkeypatch.setattr(sj, "groq_key", lambda: None)

    with pytest.raises(sj.JudgeUnavailable) as excinfo:
        sj.test_key()

    assert "key" in str(excinfo.value).lower()


def test_a_groq_error_is_shown_as_its_own_message():
    raw = '{"error":{"message":"Invalid API Key","type":"invalid_request_error"}}'

    assert sj._error_detail(raw) == "Invalid API Key"


def test_a_plain_error_is_kept_short():
    assert sj._error_detail("x" * 500) == "x" * 160


def test_a_network_error_is_reported_as_unavailable(monkeypatch):
    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            raise httpx.ConnectError("no route")

    monkeypatch.setattr(sj.httpx, "Client", BrokenClient)

    with pytest.raises(sj.JudgeUnavailable) as excinfo:
        sj._post_groq({}, "gsk_test")

    assert "reach" in str(excinfo.value).lower()
