"""Tests for the optional browser-use fallback.

These tests never launch a browser or call a model: they cover the rules
that keep the model honest, the provider order, and the per-run budget.
"""

from __future__ import annotations

import os

from s_q_ali_media_downloader.agent.tools import agent_browser as ab


def test_a_yes_with_a_name_is_accepted():
    answer = ab.parse_answer(
        {
            "exists": "yes",
            "display_name": "MrBeast",
            "handle": "@mrbeast",
            "followers": "522M followers",
            "reason": "the profile is visible",
        }
    )

    assert answer.exists == "yes"
    assert answer.display_name == "MrBeast"
    assert answer.handle == "mrbeast"
    assert answer.followers == "522M followers"


def test_a_yes_without_evidence_is_unknown():
    answer = ab.parse_answer({"exists": "yes", "reason": "it looks right"})

    assert answer.exists == "unknown"
    assert "without a name" in answer.reason


def test_a_no_without_a_quote_is_unknown():
    answer = ab.parse_answer({"exists": "no", "reason": "probably gone"})

    assert answer.exists == "unknown"
    assert "without quoting" in answer.reason


def test_a_no_with_a_login_wall_quote_is_unknown():
    answer = ab.parse_answer(
        {"exists": "no", "quote": "Log in to Instagram to continue"}
    )

    assert answer.exists == "unknown"
    assert "not a missing-account" in answer.reason


def test_a_no_with_a_missing_page_quote_is_accepted():
    answer = ab.parse_answer(
        {"exists": "no", "quote": "Sorry, this page isn't available."}
    )

    assert answer.exists == "no"
    assert answer.quote == "Sorry, this page isn't available."


def test_a_json_string_is_read():
    answer = ab.parse_answer(
        '{"exists": "yes", "display_name": "Creator", "handle": "creator"}'
    )

    assert answer.exists == "yes"
    assert answer.handle == "creator"


def test_a_fenced_json_string_is_read():
    answer = ab.parse_answer(
        '```json\n{"exists": "unknown", "reason": "the page is blank"}\n```'
    )

    assert answer.exists == "unknown"
    assert answer.reason == "the page is blank"


def test_garbage_is_unknown():
    answer = ab.parse_answer("I could not open the page")

    assert answer.exists == "unknown"
    assert "did not answer with JSON" in answer.reason


def test_an_agent_profile_is_read_back():
    original = ab.AgentProfile(exists="yes", display_name="Creator", handle="creator")

    answer = ab.parse_answer(original)

    assert answer.exists == "yes"
    assert answer.display_name == "Creator"
    assert answer.handle == "creator"


def test_gemini_is_first_and_groq_is_the_fallback(monkeypatch):
    monkeypatch.setattr(ab.judge, "groq_key", lambda: "groq-key")
    monkeypatch.setattr(ab.judge, "gemini_key", lambda: "gemini-key")

    choices = ab.provider_choices()

    assert [choice[0] for choice in choices] == ["gemini", "groq"]
    assert choices[0][2] == ab.judge.GEMINI_MODEL
    assert choices[1][2] == ab.judge.DEFAULT_MODEL


def test_gemini_alone_is_used_when_groq_has_no_key(monkeypatch):
    monkeypatch.setattr(ab.judge, "groq_key", lambda: None)
    monkeypatch.setattr(ab.judge, "gemini_key", lambda: "gemini-key")

    assert ab.provider_choice()[0] == "gemini"


def test_no_keys_means_no_provider(monkeypatch):
    monkeypatch.setattr(ab.judge, "groq_key", lambda: None)
    monkeypatch.setattr(ab.judge, "gemini_key", lambda: None)

    assert ab.provider_choices() == []
    assert ab.provider_choice() is None


def test_the_task_names_the_page_and_the_rules():
    task = ab.build_task("https://www.instagram.com/mrbeast/", "instagram")

    assert "https://www.instagram.com/mrbeast/" in task
    assert "instagram" in task
    assert "login wall" in task.lower()
    assert "never infer" in task.lower()


def test_the_checker_reports_an_install_it_does_not_have(monkeypatch):
    monkeypatch.setattr(ab, "available", lambda: False)
    checker = ab.AgentBrowserChecker()

    answer = checker("https://www.instagram.com/mrbeast/", "instagram")

    assert answer.exists == "unknown"
    assert "not installed" in answer.reason


def test_the_checker_reports_a_missing_key(monkeypatch):
    monkeypatch.setattr(ab, "available", lambda: True)
    monkeypatch.setattr(ab, "provider_choices", lambda *a, **k: [])
    checker = ab.AgentBrowserChecker()

    answer = checker("https://www.instagram.com/mrbeast/", "instagram")

    assert answer.exists == "unknown"
    assert "no AI key" in answer.reason


def test_the_next_provider_is_tried_when_the_first_fails(monkeypatch):
    monkeypatch.setattr(ab, "available", lambda: True)
    monkeypatch.setattr(
        ab,
        "provider_choices",
        lambda *a, **k: [("groq", "g", "gm"), ("gemini", "m", "mm")],
    )
    seen = []
    checker = ab.AgentBrowserChecker(log_callback=seen.append)
    calls = []

    async def fake_run(provider, key, model, url, platform):
        calls.append(provider)
        if provider == "groq":
            raise RuntimeError("Error code: 413 - Request too large")
        return ab.AgentProfile(exists="yes", display_name="Creator", handle="creator")

    monkeypatch.setattr(checker, "_run", fake_run)

    answer = checker("https://example.test/creator", "instagram")

    assert answer.exists == "yes"
    assert calls == ["groq", "gemini"]
    assert any("free tier" in line for line in seen)


def test_the_next_gemini_model_gets_a_turn_when_one_is_spent(monkeypatch):
    """A free Gemini key has a daily allowance per model. One model being
    out for the day must not hand the whole browser run to Groq."""
    monkeypatch.setattr(ab, "available", lambda: True)
    monkeypatch.setattr(
        ab,
        "provider_choices",
        lambda *a, **k: [("gemini", "m", ab.judge.GEMINI_MODEL)],
    )
    calls = []

    async def fake_run(provider, key, model, url, platform):
        calls.append(model)
        if len(calls) < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
        return ab.AgentProfile(exists="yes", display_name="Creator", handle="creator")

    checker = ab.AgentBrowserChecker()
    monkeypatch.setattr(checker, "_run", fake_run)

    answer = checker("https://example.test/creator", "instagram")

    assert answer.exists == "yes"
    assert calls == ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]


def test_a_spent_gemini_quota_is_explained(monkeypatch):
    monkeypatch.setattr(ab, "available", lambda: True)
    monkeypatch.setattr(
        ab,
        "provider_choices",
        lambda *a, **k: [("gemini", "m", ab.judge.GEMINI_MODEL)],
    )
    seen = []
    checker = ab.AgentBrowserChecker(log_callback=seen.append)

    async def fake_run(provider, key, model, url, platform):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")

    monkeypatch.setattr(checker, "_run", fake_run)

    answer = checker("https://example.test/creator", "instagram")

    assert answer.exists == "unknown"
    assert any("daily allowance" in line for line in seen)


def test_the_checker_caps_itself(monkeypatch):
    monkeypatch.setattr(ab, "available", lambda: True)
    monkeypatch.setattr(ab, "provider_choices", lambda *a, **k: [("groq", "key", "model")])
    checker = ab.AgentBrowserChecker(max_checks=1)

    async def fake_check(url, platform):
        return ab.AgentProfile(exists="yes", display_name="Creator", handle="creator")

    monkeypatch.setattr(checker, "_check", fake_check)

    first = checker("https://www.instagram.com/creator/", "instagram")
    second = checker("https://www.instagram.com/creator/", "instagram")

    assert first.exists == "yes"
    assert second.exists == "unknown"
    assert "limit" in second.reason
    assert checker.remaining == 0


def test_the_step_log_is_visible():
    seen = []
    checker = ab.AgentBrowserChecker(log_callback=seen.append)

    class Output:
        next_goal = "read the profile name"

    class State:
        url = "https://www.instagram.com/creator/"

    checker._on_step(State(), Output(), 1)

    assert any("step 1" in line and "read the profile name" in line for line in seen)


def test_the_copied_profile_is_removed(tmp_path):
    copy = tmp_path / "browser-use-user-data-dir-abc"
    copy.mkdir()
    (copy / "Cookies").write_text("secret", encoding="utf-8")
    checker = ab.AgentBrowserChecker(profile_dir=tmp_path / "profile")

    class Profile:
        user_data_dir = str(copy)

    checker._remove_profile_copy(Profile())

    assert not copy.exists()


def test_the_real_profile_is_never_removed(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    checker = ab.AgentBrowserChecker(profile_dir=profile)

    class Profile:
        user_data_dir = str(profile)

    checker._remove_profile_copy(Profile())

    assert profile.exists()


def test_the_environment_is_local(monkeypatch):
    monkeypatch.delenv("ANONYMIZED_TELEMETRY", raising=False)
    monkeypatch.delenv("BROWSER_USE_CLOUD_SYNC", raising=False)

    ab._prepare_environment()

    assert os.environ["ANONYMIZED_TELEMETRY"] == "false"
    assert os.environ["BROWSER_USE_CLOUD_SYNC"] == "false"
