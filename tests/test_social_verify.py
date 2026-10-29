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
    channel_id="UC123",
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


def test_a_tiktok_bio_that_repeats_the_handle_keeps_the_profile_name():
    """The name is the text before the profile line, not before a later
    mention of the handle in the bio."""
    page = Page(
        url="https://www.tiktok.com/@mrbeast",
        title="TikTok - Make Your Day",
        text=(
            "MrBeast\nmrbeast\n346\nFollowing\n144.6M\nFollowers\n"
            "Follow me on mrbeast.com"
        ),
        links=[],
        meta={},
    )

    result = sv.verify_page(page, "tiktok", CREATOR)

    assert result.display_name == "MrBeast"
    assert result.verdict is sv.Verdict.FOUND


def test_a_tiktok_footer_above_the_name_is_not_part_of_the_name():
    """The page's own footer ("© 2026 TikTok") sits above the profile line.

    Reading it as the name gives "2026 MrBeast", which is then read as a
    different account — measured on the live page on 2026-10-29.
    """
    page = Page(
        url="https://www.tiktok.com/@mrbeast",
        title="MrBeast (@mrbeast) | TikTok",
        text=(
            "TikTok\nSearch\nFor You\nExplore\nFollowing\nShort dramas\n"
            "LIVE\nUpload\nProfile\nMore\nLog in\nCompany\nProgram\n"
            "Terms & Policies\n© 2026 TikTok\n"
            "MrBeast\nmrbeast\n346\nFollowing\n145.1M\nFollowers\n1.6B\nLikes\n"
            "Follow\nMessage\nCheckout My New Book!👇\n"
            "themostdangerousgames.com\n\nSuggested accounts\n\n"
            "Kanwalay🎶\n\n22M followers\n\nFollow"
        ),
        links=[],
        meta={},
    )

    result = sv.verify_page(page, "tiktok", CREATOR)

    assert result.display_name == "MrBeast"
    assert "name_match" in result.evidence
    assert result.verdict is sv.Verdict.FOUND


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


def test_a_page_that_renders_nothing_is_opened_once_more():
    """TikTok paints its profile in after the first paint."""
    empty = Page(
        url="https://www.tiktok.com/@mrbeast",
        title="",
        text="",
        links=[],
        meta={},
    )
    full = _page("tiktok_real")

    class _Session:
        def __init__(self):
            self.calls = []

        def open(self, url, *, wait_ms=None):
            self.calls.append(wait_ms)
            return empty if len(self.calls) == 1 else full

    session = _Session()

    result = sv.verify_candidate(
        session, "https://www.tiktok.com/@mrbeast", "tiktok", CREATOR
    )

    assert len(session.calls) == 2
    assert result.verdict is sv.Verdict.FOUND


def test_every_candidate_opened_is_reported():
    """The page count is per account tried, not per platform kept."""
    session = _FakeSession(
        {
            "https://www.facebook.com/CarolinaFordDealer": _page("facebook_other"),
            "https://www.facebook.com/MrBeast": _page("facebook_real"),
        }
    )
    seen: list[int] = []

    sv.verify_candidates(
        session,
        CREATOR,
        {
            "facebook": [
                "https://www.facebook.com/CarolinaFordDealer",
                "https://www.facebook.com/MrBeast",
            ]
        },
        on_check=lambda: seen.append(1),
    )

    assert len(seen) == 2


def test_a_platform_nobody_could_check_stays_unknown():
    session = _FakeSession({})

    results = sv.verify_candidates(
        session, CREATOR, {"facebook": ["https://www.facebook.com/MrBeast"]}
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.UNKNOWN


def test_one_evidence_is_not_enough():
    """The spec needs two signals. A substring used to count as one FOUND."""
    page = Page(
        url="https://www.facebook.com/other",
        title="Ali | Facebook",
        text="Ali 1K followers",
        links=[],
        meta={"ogTitle": "Ali", "ogUrl": "https://www.facebook.com/other"},
    )

    result = sv.verify_page(
        page, "facebook", sv.CreatorRef(title="Ali", handle="ali", url="")
    )

    assert result.evidence == ["name_match"]
    assert result.verdict is sv.Verdict.NO_MATCH


def test_a_page_of_somebody_else_is_kept_as_no_match():
    session = _FakeSession(
        {"https://www.facebook.com/CarolinaFordDealer": _page("facebook_other")}
    )

    results = sv.verify_candidates(
        session,
        CREATOR,
        {"facebook": ["https://www.facebook.com/CarolinaFordDealer"]},
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.NO_MATCH


def test_a_bio_link_that_cannot_be_read_is_found():
    session = _FakeSession({})
    url = "https://www.instagram.com/real_creator/"

    results = sv.verify_candidates(
        session, CREATOR, {"instagram": [url]}, bio_urls={url}
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.FOUND
    assert results[0].evidence == ["bio_link"]
    assert results[0].source == "bio"
    assert results[0].tier == "likely"


def test_a_readable_bio_link_that_does_not_match_stays_no_match():
    """The channel page also lists sponsors. A page that says it is somebody
    else must not be turned into the creator's account by the link alone."""
    session = _FakeSession(
        {"https://www.facebook.com/CarolinaFordDealer": _page("facebook_other")}
    )
    url = "https://www.facebook.com/CarolinaFordDealer"

    results = sv.verify_candidates(
        session, CREATOR, {"facebook": [url]}, bio_urls={url}
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.NO_MATCH
    assert "bio_link" not in results[0].evidence


def test_a_bio_link_with_one_match_becomes_found():
    """One signal from the page plus the creator's link is two signals."""
    page = Page(
        url="https://www.facebook.com/other",
        title="MrBeast | Facebook",
        text="MrBeast 1K followers",
        links=[],
        meta={"ogTitle": "MrBeast", "ogUrl": "https://www.facebook.com/other"},
    )
    session = _FakeSession({"https://www.facebook.com/other": page})
    url = "https://www.facebook.com/other"

    results = sv.verify_candidates(
        session, CREATOR, {"facebook": [url]}, bio_urls={url}
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.FOUND
    assert results[0].evidence == ["bio_link", "name_match"]
    assert results[0].tier == "confirmed"


# --------------------------------------------------------------------------- #
# Strict names and back-links
# --------------------------------------------------------------------------- #
def _facebook_page(name, handle, links=()):
    return Page(
        url=f"https://www.facebook.com/{handle}",
        title=f"{name} | Facebook",
        text=f"{name} 1K followers",
        links=list(links),
        meta={
            "ogTitle": name,
            "ogUrl": f"https://www.facebook.com/{handle}",
        },
    )


def test_a_fan_page_with_the_creators_back_link_is_not_found():
    """A fan page can copy the name and link to the real channel. That is not
    ownership; the name says what the page is."""
    page = _facebook_page(
        "MrBeast Fan",
        "MrBeastFan",
        ["https://www.youtube.com/@MrBeast"],
    )

    result = sv.verify_page(page, "facebook", CREATOR)

    assert "name_conflict" in result.evidence
    assert "back_link" in result.evidence
    assert result.verdict is sv.Verdict.NO_MATCH


def test_a_fan_page_cannot_hide_behind_the_creators_handle():
    """Even an exact handle does not rescue a page that calls itself a fan
    page, unless the creator's own bio linked it."""
    page = _facebook_page(
        "MrBeast Fan",
        "MrBeast",
        ["https://www.youtube.com/@MrBeast"],
    )

    result = sv.verify_page(page, "facebook", CREATOR)

    assert "name_conflict" in result.evidence
    assert "handle_match" in result.evidence
    assert result.verdict is sv.Verdict.NO_MATCH


def test_a_back_link_with_the_channel_id_is_evidence():
    creator = sv.CreatorRef(
        title="MrBeast",
        handle="MrBeast",
        url="https://www.youtube.com/@MrBeast",
        channel_id="UC123",
    )
    page = _facebook_page(
        "MrBeast",
        "other",
        ["https://www.youtube.com/channel/UC123"],
    )

    result = sv.verify_page(page, "facebook", creator)

    assert "back_link" in result.evidence
    assert result.verdict is sv.Verdict.FOUND


def test_a_back_link_with_the_handle_matches_a_channel_url_creator():
    creator = sv.CreatorRef(
        title="MrBeast",
        handle="MrBeast",
        url="https://www.youtube.com/channel/UC123",
    )
    page = _facebook_page(
        "MrBeast",
        "other",
        ["https://www.youtube.com/@MrBeast"],
    )

    result = sv.verify_page(page, "facebook", creator)

    assert "back_link" in result.evidence
    assert result.verdict is sv.Verdict.FOUND


def test_a_facebook_redirect_back_link_is_unwrapped():
    page = _facebook_page(
        "MrBeast",
        "other",
        [
            "https://l.facebook.com/l.php?u=https%3A%2F%2Fyoutube.com%2F%40mrbeast&h=abc"
        ],
    )

    result = sv.verify_page(page, "facebook", CREATOR)

    assert "back_link" in result.evidence
    assert result.verdict is sv.Verdict.FOUND


def test_a_link_to_a_different_channel_is_not_a_match():
    page = _facebook_page(
        "MrBeast",
        "mrbeast",
        ["https://www.youtube.com/@otherchannel"],
    )

    result = sv.verify_page(page, "facebook", CREATOR)

    assert "conflicting_back_link" in result.evidence
    assert "back_link" not in result.evidence
    assert result.verdict is sv.Verdict.NO_MATCH


def test_a_video_link_is_not_used_as_a_back_link():
    page = _facebook_page(
        "MrBeast",
        "other",
        ["https://youtu.be/dQw4w9WgXcQ"],
    )

    result = sv.verify_page(page, "facebook", CREATOR)

    assert "back_link" not in result.evidence
    assert "conflicting_back_link" not in result.evidence
    assert result.verdict is sv.Verdict.NO_MATCH


def test_an_official_suffix_still_matches_the_name():
    page = _facebook_page("MrBeast Official", "MrBeastOfficial")

    result = sv.verify_page(page, "facebook", CREATOR)

    assert "name_match" in result.evidence


def test_a_non_fan_suffix_is_partial_not_a_match():
    page = _facebook_page("MrBeast Vlogs", "MrBeastVlogs")

    result = sv.verify_page(page, "facebook", CREATOR)

    assert "name_partial" in result.evidence
    assert "name_match" not in result.evidence
    assert result.verdict is sv.Verdict.NO_MATCH


def test_name_and_handle_and_back_link_are_confirmed():
    page = _facebook_page(
        "MrBeast",
        "mrbeast",
        ["https://www.youtube.com/@MrBeast"],
    )

    result = sv.verify_page(page, "facebook", CREATOR)

    assert result.verdict is sv.Verdict.FOUND
    assert result.tier == "confirmed"


def test_name_and_handle_without_a_back_link_are_likely():
    page = _facebook_page("MrBeast", "mrbeast")

    result = sv.verify_page(page, "facebook", CREATOR)

    assert result.verdict is sv.Verdict.FOUND
    assert result.tier == "likely"


def test_a_bio_link_with_only_a_partial_name_stays_no_match():
    url = "https://www.facebook.com/MrBeastVlogs"
    page = _facebook_page("MrBeast Vlogs", "MrBeastVlogs")
    session = _FakeSession({url: page})

    results = sv.verify_candidates(
        session, CREATOR, {"facebook": [url]}, bio_urls={url}
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.NO_MATCH
    assert "bio_link" not in results[0].evidence


def test_a_bio_link_upgrades_a_likely_page_to_confirmed():
    """The tier and the detail must agree after the bio link is added."""
    url = "https://www.facebook.com/MrBeast"
    page = _facebook_page("MrBeast", "mrbeast")
    session = _FakeSession({url: page})

    results = sv.verify_candidates(
        session, CREATOR, {"facebook": [url]}, bio_urls={url}
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.FOUND
    assert results[0].tier == "confirmed"
    assert "not strong enough" not in results[0].detail
    assert "bio" in results[0].detail


def test_a_concatenated_fan_name_is_a_conflict():
    """Facebook display names often run the words together."""
    page = _facebook_page(
        "MrBeastFan",
        "MrBeastFan",
        ["https://www.youtube.com/@MrBeast"],
    )

    result = sv.verify_page(page, "facebook", CREATOR)

    assert "name_conflict" in result.evidence
    assert result.verdict is sv.Verdict.NO_MATCH


def test_a_name_and_back_link_do_not_claim_the_back_link_is_missing():
    """Name + back-link is likely, but the reason is not a missing link."""
    page = _facebook_page(
        "MrBeast",
        "MrBeastFan",
        ["https://www.youtube.com/@MrBeast"],
    )

    result = sv.verify_page(page, "facebook", CREATOR)

    assert result.verdict is sv.Verdict.FOUND
    assert result.tier == "likely"
    assert "not strong enough" in result.detail


def test_a_tiktok_not_found_message_in_the_body_is_not_found():
    """TikTok's missing-profile page has a generic title and no meta tags."""
    page = Page(
        url="https://www.tiktok.com/@thisdoesnotexist12345",
        title="TikTok - Make Your Day",
        text="Couldn't find this account\n\nLooking for videos? Try browsing.",
        links=[],
        meta={},
    )

    result = sv.verify_page(page, "tiktok", CREATOR)

    assert result.verdict is sv.Verdict.NOT_FOUND


# --------------------------------------------------------------------------- #
# The AI browser fallback
# --------------------------------------------------------------------------- #
class _Agent:
    def __init__(self, answer, remaining=3):
        self.answer = answer
        self.remaining = remaining
        self.configured = True
        self.calls = []

    def __call__(self, url, platform):
        self.calls.append((url, platform))
        return self.answer


def test_the_agent_confirms_a_page_the_browser_could_not_read():
    session = _FakeSession({})
    agent = _Agent(
        {
            "exists": "yes",
            "display_name": "MrBeast",
            "handle": "mrbeast",
            "reason": "the profile shows the name and handle",
        }
    )

    results = sv.verify_candidates(
        session,
        CREATOR,
        {"instagram": ["https://www.instagram.com/mrbeast/"]},
        agent_checker=agent,
    )

    assert len(results) == 1
    assert results[0].verdict is sv.Verdict.FOUND
    assert results[0].tier == "likely"
    assert agent.calls == [("https://www.instagram.com/mrbeast/", "instagram")]


def test_the_agent_cannot_erase_a_bio_link():
    session = _FakeSession({})
    url = "https://www.instagram.com/mrbeast/"
    agent = _Agent({"exists": "no", "quote": "Sorry, this page isn't available."})

    results = sv.verify_candidates(
        session,
        CREATOR,
        {"instagram": [url]},
        bio_urls={url},
        agent_checker=agent,
    )

    assert results[0].verdict is sv.Verdict.FOUND
    assert results[0].evidence == ["bio_link"]


def test_the_agent_can_mark_a_guessed_page_not_found():
    session = _FakeSession({})
    agent = _Agent({"exists": "no", "quote": "Sorry, this page isn't available."})

    results = sv.verify_candidates(
        session,
        CREATOR,
        {"instagram": ["https://www.instagram.com/mrbeast/"]},
        agent_checker=agent,
    )

    # A candidate that does not exist is dropped, exactly as it is when the
    # rendered page says so.
    assert results == []


def test_the_agent_is_not_called_when_its_budget_is_spent():
    session = _FakeSession({})
    agent = _Agent({"exists": "yes", "display_name": "MrBeast"}, remaining=0)

    results = sv.verify_candidates(
        session,
        CREATOR,
        {"instagram": ["https://www.instagram.com/mrbeast/"]},
        agent_checker=agent,
    )

    assert results[0].verdict is sv.Verdict.UNKNOWN
    assert agent.calls == []


def test_the_agent_does_not_confirm_a_different_account():
    session = _FakeSession({})
    agent = _Agent(
        {"exists": "yes", "display_name": "Somebody Else", "handle": "somebody"}
    )

    results = sv.verify_candidates(
        session,
        CREATOR,
        {"instagram": ["https://www.instagram.com/mrbeast/"]},
        agent_checker=agent,
    )

    assert results[0].verdict is sv.Verdict.NO_MATCH


def test_the_agent_closes_the_deterministic_browser_first():
    closed = []

    class _Session(_FakeSession):
        def close(self):
            closed.append(True)

    agent = _Agent({"exists": "unknown"})

    sv.verify_candidates(
        _Session({}),
        CREATOR,
        {"instagram": ["https://www.instagram.com/mrbeast/"]},
        agent_checker=agent,
    )

    assert closed == [True]
