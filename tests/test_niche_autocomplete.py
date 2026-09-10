"""Tests for the keyless YouTube autocomplete (ported from the companion research web tool)."""

import httpx
import pytest

from s_q_ali_media_downloader.niche_research.tools.autocomplete import (
    ALPHABET,
    DIGITS,
    QUESTION_WORDS,
    AutocompleteError,
    expand_seed,
    fetch_suggestions,
)


def _fake_resp(text: str, status: int = 200):
    resp = httpx.Response(status, text=text, request=httpx.Request("GET", "https://x"))
    return resp


def test_fetch_suggestions_parses(monkeypatch):
    payload = '["skin care", ["skin care routine", "skin care for men"], {}, {"skoe": 1}]'
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_resp(payload))
    assert fetch_suggestions("skin c") == ["skin care routine", "skin care for men"]


def test_fetch_suggestions_error_mapping(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_resp("nope", status=500))
    with pytest.raises(AutocompleteError) as exc_info:
        fetch_suggestions("x", retries=0)
    assert exc_info.value.status == 500


def test_fetch_suggestions_retries_then_fails(monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    with pytest.raises(AutocompleteError):
        fetch_suggestions("x", retries=2)
    assert calls["n"] == 3


def test_expand_seed_dedup_and_alphabets(monkeypatch):
    suggestions_seen = []

    def fake_fetch(query, **kwargs):
        suggestions_seen.append(query)
        if query == "skin care":
            return ["skin care routine"]
        if query.startswith("skin care a"):
            return ["skin care aha"]
        if query == "what skin care":
            return ["what skin care products"]
        return []

    monkeypatch.setattr(
        "s_q_ali_media_downloader.niche_research.tools.autocomplete.fetch_suggestions", fake_fetch
    )
    results = expand_seed("skin care")
    assert results == ["skin care routine", "skin care aha", "what skin care products"]
    assert len(suggestions_seen) == 1 + len(ALPHABET) + len(DIGITS) + len(QUESTION_WORDS)


def test_expand_seed_deduplicates_case_and_space():
    items = ["  Skin CARE Routine ", "SKIN CARE routine", "other"]
    results: dict[str, str] = {}
    from s_q_ali_media_downloader.niche_research.tools.autocomplete import _add_dedup

    for item in items:
        _add_dedup(results, item)
    assert len(results) == 2
    assert "skin care routine" in results
