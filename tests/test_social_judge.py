"""Tests for the AI agent that proposes candidates."""

from __future__ import annotations

import json

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
    monkeypatch.setattr(sj.db, "get_setting", lambda key: "stored-key")

    assert sj.groq_key() == "gsk_from_env"


def test_the_stored_key_is_used_when_the_environment_has_none(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(sj.db, "get_setting", lambda key: "stored-key")

    assert sj.groq_key() == "stored-key"
