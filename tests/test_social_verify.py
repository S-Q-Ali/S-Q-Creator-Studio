"""Tests for the social verifier.

The fixtures are real rendered pages, captured on 2026-10-21 from a real
Instagram, Facebook and TikTok profile and from a made-up one. They are
the whole point of the module: a plain HTTP request cannot tell those
apart, a rendered page can.
"""

from __future__ import annotations

import json
from pathlib import Path

from s_q_ali_media_downloader.agent.tools import social_verify as sv
from s_q_ali_media_downloader.agent.tools.browser import Page

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "social_pages.json").read_text(encoding="utf-8")
)


def _page(name: str) -> Page:
    data = FIXTURES[name]
    return Page(
        url=data["url"],
        title=data["title"],
        text=data["text"],
        links=data["links"],
        meta=data.get("meta", {}),
    )


CREATOR = sv.CreatorRef(
    title="MrBeast",
    handle="MrBeast",
    url="https://www.youtube.com/@MrBeast",
)


# --------------------------------------------------------------------------- #
# The real accounts
# --------------------------------------------------------------------------- #
def test_a_real_instagram_profile_is_found():
    result = sv.verify_page(_page("instagram_real"), "instagram", CREATOR)

    assert result.verdict is sv.Verdict.FOUND
    assert "handle_match" in result.evidence
    assert result.display_name


def test_a_real_facebook_page_is_found():
    result = sv.verify_page(_page("facebook_real"), "facebook", CREATOR)

    assert result.verdict is sv.Verdict.FOUND
    assert "name_match" in result.evidence


def test_a_real_tiktok_profile_is_found():
    result = sv.verify_page(_page("tiktok_real"), "tiktok", CREATOR)

    assert result.verdict is sv.Verdict.FOUND
    assert "name_match" in result.evidence or "handle_match" in result.evidence


# --------------------------------------------------------------------------- #
# The made-up ones
# --------------------------------------------------------------------------- #
def test_a_made_up_instagram_profile_is_not_found():
    result = sv.verify_page(_page("instagram_fake"), "instagram", CREATOR)

    assert result.verdict is sv.Verdict.NOT_FOUND


def test_a_made_up_tiktok_profile_is_not_found():
    result = sv.verify_page(_page("tiktok_fake"), "tiktok", CREATOR)

    assert result.verdict is sv.Verdict.NOT_FOUND


def test_a_facebook_page_that_does_not_exist_is_not_found():
    """Facebook says it plainly when the page is not there."""
    result = sv.verify_page(_page("facebook_fake"), "facebook", CREATOR)

    assert result.verdict is sv.Verdict.NOT_FOUND


def test_a_facebook_page_of_somebody_else_is_not_this_creator():
    """The page exists — it is just not his."""
    result = sv.verify_page(_page("facebook_other"), "facebook", CREATOR)

    assert result.verdict is sv.Verdict.NO_MATCH


def test_a_facebook_page_behind_a_login_wall_is_unknown():
    """Facebook shows the same wall for a page that does not exist and for
    a page that is gated, so a wall is unknown — never "not found"."""
    wall = Page(
        url="https://www.facebook.com/someone",
        title="Facebook",
        text="Explore the things you love. Log in to Facebook Email address or mobile number",
    )

    result = sv.verify_page(wall, "facebook", CREATOR)

    assert result.verdict is sv.Verdict.UNKNOWN


# --------------------------------------------------------------------------- #
# The unhappy paths
# --------------------------------------------------------------------------- #
def test_a_page_that_cannot_be_opened_is_unknown():
    class BrokenSession:
        def open(self, url, **kwargs):
            raise sv.PageUnavailable("boom")

    result = sv.verify_candidate(
        BrokenSession(), "https://www.instagram.com/x", "instagram", CREATOR
    )

    assert result.verdict is sv.Verdict.UNKNOWN


def test_the_verdict_of_a_page_that_is_not_readable_is_unknown():
    result = sv.verify_page(
        Page(url="https://x.test", title="", text=""), "instagram", CREATOR
    )

    assert result.verdict is sv.Verdict.UNKNOWN


# --------------------------------------------------------------------------- #
# The batch
# --------------------------------------------------------------------------- #
class _FakeSession:
    def __init__(self, pages):
        self.pages = pages

    def open(self, url, **kwargs):
        page = self.pages.get(url)
        if page is None:
            raise sv.PageUnavailable("no page")
        return page


def test_the_verifier_picks_the_candidate_that_matches():
    """MrBeast's page lists a sponsor's account next to his own — the one
    that says 'MrBeast' is the answer."""
    session = _FakeSession(
        {
            "https://www.facebook.com/CarolinaFordDealer": _page("facebook_other"),
            "https://www.facebook.com/MrBeast": _page("facebook_real"),
        }
    )

    results = sv.verify_candidates(
        session,
        CREATOR,
        {
            "facebook": [
                "https://www.facebook.com/CarolinaFordDealer",
                "https://www.facebook.com/MrBeast",
            ]
        },
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.FOUND
    assert results[0].url == "https://www.facebook.com/MrBeast"


def test_a_candidate_that_does_not_exist_is_dropped():
    session = _FakeSession(
        {"https://www.instagram.com/mrbeast/": _page("instagram_real")}
    )

    results = sv.verify_candidates(
        session,
        CREATOR,
        {
            "instagram": [
                "https://www.instagram.com/mrbeast_fan_99x",
                "https://www.instagram.com/mrbeast/",
            ]
        },
    )

    assert [r.url for r in results] == ["https://www.instagram.com/mrbeast/"]


def test_a_platform_nobody_could_check_stays_unknown():
    session = _FakeSession({})

    results = sv.verify_candidates(
        session, CREATOR, {"facebook": ["https://www.facebook.com/MrBeast"]}
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.UNKNOWN
