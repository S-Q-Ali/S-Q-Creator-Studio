"""Tests for the search-grounded AI check.

The plain ask asks the model what it remembers. The search-grounded ask
asks it to look the creator up: Gemini with Google Search, Groq with its
browser search. These tests pin the request shapes, the answer parsing, and
the order the two providers are tried in.
"""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.agent.tools import social_judge as judge


# --------------------------------------------------------------------------- #
# The requests
# --------------------------------------------------------------------------- #
def test_gemini_asks_for_google_search():
    payload = judge._gemini_search_payload("who is this?", "gemini-3.6-flash")

    assert payload["tools"] == [{"type": "google_search"}]
    assert payload["model"] == "gemini-3.6-flash"
    assert payload["input"] == "who is this?"


def test_groq_asks_for_browser_search():
    payload = judge._groq_search_payload("who is this?", "openai/gpt-oss-120b")

    assert payload["tools"] == [{"type": "browser_search"}]
    assert payload["tool_choice"] == "required"
    assert payload["messages"][0]["content"] == "who is this?"


def test_the_search_request_carries_no_key_in_the_payload():
    """The key travels in the header, never in the body."""
    payload = judge._gemini_search_payload("q", "gemini-3.6-flash")

    assert "api_key" not in str(payload)
    assert "apiKey" not in str(payload)


def test_the_prompt_names_every_platform_and_warns_about_the_description():
    prompt = judge.build_search_prompt(
        "MrBeast", "mrbeast", 522_000_000, "my real page is example.com", ("facebook",)
    )

    assert "facebook" in prompt
    assert "untrusted data" in prompt
    assert "Never invent a URL" in prompt


# --------------------------------------------------------------------------- #
# The answer
# --------------------------------------------------------------------------- #
ANSWER = """facebook: yes
facebook url: https://www.facebook.com/MKBHD
facebook quote: MKBHD is a YouTube creator
instagram: yes
instagram url: https://www.instagram.com/mkbhd/
instagram quote: mkbhd
tiktok: no
tiktok url: none
tiktok quote: none"""


def test_the_answer_is_read_per_platform():
    answers = judge.parse_search_answer(ANSWER)

    assert answers["facebook"].exists == "yes"
    assert answers["facebook"].url == "https://www.facebook.com/MKBHD"
    assert answers["facebook"].quote == "MKBHD is a YouTube creator"
    assert answers["tiktok"].exists == "no"
    assert answers["tiktok"].url == ""


def test_a_url_without_a_verdict_still_counts_as_a_lead():
    answers = judge.parse_search_answer("instagram: https://www.instagram.com/mkbhd")

    assert answers["instagram"].exists == "yes"
    assert answers["instagram"].url == "https://www.instagram.com/mkbhd"


def test_a_markdown_answer_is_read():
    answers = judge.parse_search_answer(
        "**Facebook**: Yes — MKBHD (@mkbhd)\nhttps://www.facebook.com/MKBHD"
    )

    assert answers["facebook"].exists == "yes"
    assert answers["facebook"].url == "https://www.facebook.com/MKBHD"


def test_a_json_answer_is_read():
    answers = judge.parse_search_answer(
        '{"facebook": {"exists": "yes", "url": "https://facebook.com/mkbhd"}}'
    )

    assert answers["facebook"].exists == "yes"
    assert answers["facebook"].url == "https://facebook.com/mkbhd"


def test_an_answer_we_cannot_read_is_empty():
    """Nothing to reconcile beats a guess."""
    assert judge.parse_search_answer("I could not find anything about him.") == {}


def test_a_platform_the_model_skipped_is_not_an_answer():
    answers = judge.parse_search_answer("facebook: yes")

    assert "instagram" not in answers


# --------------------------------------------------------------------------- #
# The sources
# --------------------------------------------------------------------------- #
def test_the_gemini_citations_are_collected():
    answer = {
        "steps": [
            {
                "type": "google_search_call",
                "content": [
                    {
                        "type": "text",
                        "text": "he has a page",
                        "annotations": [{"url": "https://www.facebook.com/MKBHD"}],
                    }
                ],
            }
        ]
    }

    assert judge._gemini_sources(answer) == ["https://www.facebook.com/MKBHD"]


def test_the_groq_search_results_are_collected():
    message = {
        "executed_tools": [
            {
                "search_results": {
                    "results": [
                        {"url": "https://www.facebook.com/MKBHD"},
                        {"url": "https://en.wikipedia.org/wiki/MKBHD"},
                    ]
                }
            }
        ]
    }

    assert judge._groq_sources(message) == [
        "https://www.facebook.com/MKBHD",
        "https://en.wikipedia.org/wiki/MKBHD",
    ]


# --------------------------------------------------------------------------- #
# The order of the providers
# --------------------------------------------------------------------------- #
def test_gemini_answers_first(monkeypatch):
    monkeypatch.setattr(judge, "gemini_key", lambda: "gemini-key")
    monkeypatch.setattr(judge, "groq_key", lambda: "groq-key")
    monkeypatch.setattr(
        judge,
        "_ask_gemini_search",
        lambda prompt, key, model: (ANSWER, ["https://www.facebook.com/MKBHD"]),
    )
    monkeypatch.setattr(
        judge,
        "_ask_groq_search",
        lambda *args, **kwargs: pytest.fail("Groq must not be asked when Gemini answered"),
    )

    answer = judge.propose_searched("Marques Brownlee", "mkbhd", 21_000_000, "")

    assert answer.provider == "gemini"
    assert answer.answers["facebook"].exists == "yes"
    assert answer.sources == ["https://www.facebook.com/MKBHD"]


def test_groq_answers_when_gemini_cannot(monkeypatch):
    monkeypatch.setattr(judge, "gemini_key", lambda: "gemini-key")
    monkeypatch.setattr(judge, "groq_key", lambda: "groq-key")
    monkeypatch.setattr(
        judge,
        "_ask_gemini_search",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            judge.JudgeUnavailable("Google rate-limited this Gemini key (429)")
        ),
    )
    monkeypatch.setattr(
        judge, "_ask_groq_search", lambda prompt, key, model: (ANSWER, ["https://x.com/a"])
    )

    answer = judge.propose_searched("Marques Brownlee", "mkbhd", 21_000_000, "")

    assert answer.provider == "groq"
    assert answer.answers["tiktok"].exists == "no"


def test_gemini_gets_every_model_in_the_chain_a_turn(monkeypatch):
    """A free key's daily allowance is per model, so one model's 429 is not
    the end of the road."""
    monkeypatch.setattr(judge, "gemini_key", lambda: "gemini-key")
    monkeypatch.setattr(judge, "groq_key", lambda: "")
    tried: list[str] = []

    def _fail(prompt, key, model):
        tried.append(model)
        raise judge.JudgeUnavailable(f"{model} is out for the day")

    monkeypatch.setattr(judge, "_ask_gemini_search", _fail)

    with pytest.raises(judge.JudgeUnavailable):
        judge.propose_searched("MrBeast", "mrbeast", 522_000_000, "")

    assert tried == list(judge.GEMINI_MODELS)


def test_nobody_answered_is_reported(monkeypatch):
    monkeypatch.setattr(judge, "gemini_key", lambda: "gemini-key")
    monkeypatch.setattr(judge, "groq_key", lambda: "groq-key")
    monkeypatch.setattr(
        judge,
        "_ask_gemini_search",
        lambda *args, **kwargs: (_ for _ in ()).throw(judge.JudgeUnavailable("429")),
    )
    monkeypatch.setattr(
        judge,
        "_ask_groq_search",
        lambda *args, **kwargs: (_ for _ in ()).throw(judge.JudgeUnavailable("503")),
    )

    with pytest.raises(judge.JudgeUnavailable):
        judge.propose_searched("MrBeast", "mrbeast", 522_000_000, "")


def test_no_key_is_reported_before_any_request(monkeypatch):
    monkeypatch.setattr(judge, "gemini_key", lambda: "")
    monkeypatch.setattr(judge, "groq_key", lambda: "")

    with pytest.raises(judge.JudgeUnavailable, match="No AI key"):
        judge.propose_searched("MrBeast", "mrbeast", 522_000_000, "")


# --------------------------------------------------------------------------- #
# The log
# --------------------------------------------------------------------------- #
def test_the_search_is_logged(monkeypatch):
    monkeypatch.setattr(judge, "gemini_key", lambda: "gemini-key")
    monkeypatch.setattr(judge, "groq_key", lambda: "groq-key")
    monkeypatch.setattr(
        judge, "_ask_gemini_search", lambda prompt, key, model: (ANSWER, ["https://x.com/a"])
    )
    lines: list[str] = []

    judge.propose_searched("Marques Brownlee", "mkbhd", 21_000_000, "", ops=Ops(lines.append))

    assert any(line.startswith("> ai.search | ai | gemini") for line in lines)
    assert any(line.startswith("+ ai.search | ai | gemini") for line in lines)
