"""Tests for the reconciliation of the two checks.

The AI reads the web; the browser opens the page. Every combination of
their verdicts has one answer, and this is where those answers are pinned
down — no live site, no network.
"""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.agent.tools import social_verify as sv


def _browser(verdict: sv.Verdict) -> sv.CheckResult:
    return sv.CheckResult(platform="facebook", verdict=verdict)


# --------------------------------------------------------------------------- #
# The AI says yes
# --------------------------------------------------------------------------- #
def test_both_agree_the_account_is_the_creator_s():
    result = sv.reconcile("yes", "https://facebook.com/mkbhd", _browser(sv.Verdict.FOUND))

    assert result.status is sv.Reconciled.VERIFIED
    assert result.confidence == 0.95
    assert result.source == "both"


def test_the_browser_outranks_the_ai_when_the_page_names_somebody_else():
    result = sv.reconcile("yes", "https://facebook.com/mkbhd", _browser(sv.Verdict.NO_MATCH))

    assert result.status is sv.Reconciled.WEAK
    assert result.confidence == 0.55
    assert result.source == "browser"


def test_the_ai_lead_is_kept_when_the_page_could_not_be_read():
    result = sv.reconcile("yes", "https://facebook.com/mkbhd", _browser(sv.Verdict.UNKNOWN))

    assert result.status is sv.Reconciled.UNCONFIRMED
    assert result.confidence == 0.60
    assert result.source == "model"


def test_the_ai_lead_is_kept_when_the_page_is_not_there():
    result = sv.reconcile("yes", "https://facebook.com/mkbhd", _browser(sv.Verdict.NOT_FOUND))

    assert result.status is sv.Reconciled.UNCONFIRMED
    assert result.confidence == 0.60
    assert result.source == "model"


# --------------------------------------------------------------------------- #
# The AI says no
# --------------------------------------------------------------------------- #
def test_the_browser_wins_when_it_found_the_account():
    result = sv.reconcile("no", "", _browser(sv.Verdict.FOUND))

    assert result.status is sv.Reconciled.VERIFIED
    assert result.confidence == 0.95
    assert result.source == "browser"


def test_both_say_the_account_is_missing():
    result = sv.reconcile("no", "", _browser(sv.Verdict.NOT_FOUND))

    assert result.status is sv.Reconciled.MISSING
    assert result.confidence == 0.0
    assert result.source == "both"


def test_a_page_we_could_not_read_is_not_a_missing_account():
    result = sv.reconcile("no", "", _browser(sv.Verdict.UNKNOWN))

    assert result.status is sv.Reconciled.UNKNOWN
    assert result.confidence == 0.0
    assert result.source == "browser"


# --------------------------------------------------------------------------- #
# The AI did not answer
# --------------------------------------------------------------------------- #
def test_the_browser_answers_alone_when_the_ai_is_silent():
    result = sv.reconcile("unknown", "", _browser(sv.Verdict.FOUND))

    assert result.status is sv.Reconciled.VERIFIED
    assert result.source == "browser"


def test_the_browser_answers_alone_when_the_account_is_missing():
    result = sv.reconcile("unknown", "", _browser(sv.Verdict.NOT_FOUND))

    assert result.status is sv.Reconciled.MISSING
    assert result.source == "browser"


def test_the_browser_answers_alone_when_the_page_could_not_be_read():
    result = sv.reconcile("unknown", "", _browser(sv.Verdict.UNKNOWN))

    assert result.status is sv.Reconciled.UNKNOWN
    assert result.source == "browser"


# --------------------------------------------------------------------------- #
# No page was opened at all
# --------------------------------------------------------------------------- #
def test_the_ai_alone_never_proves_an_account_is_missing():
    """The AI's word is not a page."""
    result = sv.reconcile("no", "", None)

    assert result.status is sv.Reconciled.UNKNOWN
    assert result.confidence == 0.0


def test_the_ai_alone_is_only_a_lead():
    result = sv.reconcile("yes", "https://facebook.com/mkbhd", None)

    assert result.status is sv.Reconciled.UNCONFIRMED
    assert result.source == "model"


def test_nothing_at_all_is_unknown():
    result = sv.reconcile()

    assert result.status is sv.Reconciled.UNKNOWN


# --------------------------------------------------------------------------- #
# The words each mode uses
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "status, expected",
    [
        (sv.Reconciled.VERIFIED, "verified"),
        (sv.Reconciled.WEAK, "unverified_handle"),
        (sv.Reconciled.UNCONFIRMED, "unverified_handle"),
        (sv.Reconciled.MISSING, "not_found"),
        (sv.Reconciled.UNKNOWN, "inconclusive"),
    ],
)
def test_the_social_presence_words(status, expected):
    assert sv.RECONCILED_TO_SOCIAL_STATUS[status].value == expected


@pytest.mark.parametrize(
    "status, expected",
    [
        (sv.Reconciled.VERIFIED, "found"),
        (sv.Reconciled.WEAK, "no_match"),
        (sv.Reconciled.UNCONFIRMED, "unknown"),
        (sv.Reconciled.MISSING, "not_found"),
        (sv.Reconciled.UNKNOWN, "unknown"),
    ],
)
def test_the_discovery_words(status, expected):
    assert sv.RECONCILED_TO_VERDICT[status].value == expected
