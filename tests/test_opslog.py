"""Tests for the operation log.

The log answers a different question from the progress line: not "where is
the run" but "what was attempted, on what, by which engine, and what came
back". These tests pin the line format and the wiring of every engine that
writes to it.
"""

from __future__ import annotations

from s_q_ali_media_downloader.agent.opslog import FAIL, OK, SKIP, START, Op, Ops, format_op
from s_q_ali_media_downloader.agent.tools import social_verify as sv
from s_q_ali_media_downloader.agent.tools.browser import Page


# --------------------------------------------------------------------------- #
# The line
# --------------------------------------------------------------------------- #
def test_a_successful_operation_reads_as_one_line():
    line = format_op(
        Op(
            stage="browser.open",
            engine="browser",
            target="https://instagram.com/mrbeast/",
            outcome=OK,
            detail="instagram found",
            duration_ms=1200,
        )
    )

    assert line == (
        "+ browser.open | browser | https://instagram.com/mrbeast/ | instagram found | 1.2s"
    )


def test_a_failure_carries_the_error():
    line = format_op(
        Op(
            stage="ai.ask",
            engine="ai",
            target="gemini",
            outcome=FAIL,
            error="429 — too many requests",
        )
    )

    assert line == "! ai.ask | ai | gemini | error: 429 — too many requests"


def test_the_marker_tells_the_outcomes_apart():
    assert format_op(Op(stage="s", engine="e", target="t", outcome=START)).startswith("> ")
    assert format_op(Op(stage="s", engine="e", target="t", outcome=SKIP)).startswith("? ")
    assert format_op(Op(stage="s", engine="e", target="t", outcome=OK)).startswith("+ ")
    assert format_op(Op(stage="s", engine="e", target="t", outcome=FAIL)).startswith("! ")


# --------------------------------------------------------------------------- #
# The sink
# --------------------------------------------------------------------------- #
def test_every_operation_reaches_the_sink():
    lines: list[str] = []
    ops = Ops(lines.append)

    ops.start("ai.ask", "ai", "gemini")
    ops.ok("ai.ask", "ai", "gemini", detail="3 candidate(s)")

    assert len(lines) == 2
    assert lines[0].startswith("> ai.ask | ai | gemini")
    assert lines[1].startswith("+ ai.ask | ai | gemini")


def test_the_operation_keeps_what_it_was_given():
    ops = Ops()

    op = ops.fail("ai.ask", "ai", "groq", "no key", detail="proposing")

    assert op.stage == "ai.ask"
    assert op.engine == "ai"
    assert op.target == "groq"
    assert op.outcome == FAIL
    assert op.detail == "proposing"
    assert op.error == "no key"


def test_a_broken_sink_does_not_stop_the_run():
    """The sink is the UI. A UI that raises must not fail the operation."""

    def broken(message: str) -> None:
        raise RuntimeError("the panel is gone")

    ops = Ops(broken)

    assert ops.ok("ai.ask", "ai", "groq").outcome == OK


def test_no_sink_writes_nothing():
    ops = Ops()

    assert ops.ok("ai.ask", "ai", "groq").outcome == OK


# --------------------------------------------------------------------------- #
# The engines
# --------------------------------------------------------------------------- #
CREATOR = sv.CreatorRef(
    title="MrBeast",
    handle="MrBeast",
    url="https://www.youtube.com/@MrBeast",
    channel_id="UC123",
)

PAGE = Page(
    url="https://www.instagram.com/mrbeast/",
    title="MrBeast (@mrbeast) - Instagram photos and videos",
    text="MrBeast 144.6M Followers",
    links=[],
    meta={"ogTitle": "MrBeast (@mrbeast) - Instagram photos and videos"},
)


class _Session:
    def __init__(self, pages):
        self.pages = pages

    def open(self, url, **kwargs):
        page = self.pages.get(url)
        if page is None:
            raise sv.PageUnavailable("no page")
        return page


def test_the_browser_check_is_logged_with_the_link_it_opened():
    lines: list[str] = []
    session = _Session({"https://www.instagram.com/mrbeast/": PAGE})

    sv.verify_candidates(
        session,
        CREATOR,
        {"instagram": ["https://www.instagram.com/mrbeast/"]},
        ops=Ops(lines.append),
    )

    assert any("browser.open" in line for line in lines)
    assert any("https://www.instagram.com/mrbeast/" in line for line in lines)


def test_a_page_that_cannot_be_read_is_logged_as_a_failure():
    lines: list[str] = []
    session = _Session({})

    sv.verify_candidates(
        session,
        CREATOR,
        {"instagram": ["https://www.instagram.com/mrbeast/"]},
        ops=Ops(lines.append),
    )

    assert any(line.startswith("! browser.open") for line in lines)
    assert any("no page" in line for line in lines)


def test_the_ai_browser_check_is_logged_separately():
    lines: list[str] = []
    session = _Session({})

    class _Agent:
        remaining = 1
        configured = True

        def __call__(self, url, platform):
            return {"exists": "unknown"}

    sv.verify_candidates(
        session,
        CREATOR,
        {"instagram": ["https://www.instagram.com/mrbeast/"]},
        agent_checker=_Agent(),
        ops=Ops(lines.append),
    )

    assert any("ai.browser.open" in line for line in lines)
    assert any("ai-browser" in line for line in lines)


def test_the_judge_logs_which_provider_answered(monkeypatch):
    from s_q_ali_media_downloader.agent.tools import social_judge as judge

    lines: list[str] = []
    monkeypatch.setattr(judge, "gemini_key", lambda: "")
    monkeypatch.setattr(judge, "groq_key", lambda: "test-key")
    monkeypatch.setattr(
        judge,
        "_propose_with_groq",
        lambda prompt, key, model, schema=None, platforms=judge.PLATFORMS: judge.Proposal(
            candidates={"instagram": ["mrbeast"]},
            provider="groq",
            model=model,
        ),
    )

    judge.propose("MrBeast", "MrBeast", 100, "", ops=Ops(lines.append))

    assert any(line.startswith("> ai.ask | ai | groq") for line in lines)
    assert any(line.startswith("+ ai.ask | ai | groq") for line in lines)
