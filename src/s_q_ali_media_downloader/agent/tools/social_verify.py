"""Decide whether a social account exists, and whether it is this creator's.

A plain HTTP request cannot answer that. Verified 2026-10-21: Instagram
answered a real profile and a made-up one with the same 590 KB page,
TikTok with the same 1.4 KB script shell, and Facebook with the same
login wall. A rendered page answers it:

* Instagram: a real profile's title carries the handle ("MrBeast
  (@mrbeast) - Instagram photos and videos"), a missing one says
  "Profile isn't available".
* Facebook: a real page's title carries the page name ("MrBeast |
  Facebook") and the page shows its follower count; a page that does not
  exist shows the generic login wall — which is why a missing Facebook
  page is *unknown* and never "not found".
* TikTok: a real profile shows its name, handle and follower count; a
  missing one says "Couldn't find this account".

Ownership is decided from what the account says about itself — its display
name, its handle, and the links it lists. The channel's own page cannot
help: on MrBeast's About page his accounts and his sponsors' accounts sit
in the same description element.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import parse_qs, urlparse

from s_q_ali_media_downloader.agent.tools.browser import Page, PageUnavailable

logger = logging.getLogger(__name__)

#: A page that says the account does not exist.
NOT_FOUND_SIGNATURES = (
    "profile isn't available",
    "profile isn’t available",
    "this page isn't available",
    "this page isn’t available",
    "content isn't available",
    "couldn't find this account",
    "couldn’t find this account",
    "user not found",
    "page not found",
    "this account doesn't exist",
    "no content available",
)

#: A page that is a login wall — we cannot see what is behind it.
LOGIN_WALL_SIGNATURES = (
    "log in to facebook",
    "you must log in to continue",
    "login/?next=",
    "log in to continue",
)

#: The follower count, e.g. "51M followers" or "1,013 following".
_FOLLOWERS_RE = re.compile(r"([\d.,]+\s*[KMB]?)\s+followers", re.IGNORECASE)

#: The Instagram title: "MrBeast (@mrbeast) - Instagram photos and videos".
_IG_TITLE_RE = re.compile(r"^(?P<name>.+?)\s*\(@(?P<handle>[A-Za-z0-9_.]+)\)")

#: The Facebook title: "MrBeast | Facebook".
_FB_TITLE_RE = re.compile(r"^(?P<name>.+?)\s*\|\s*Facebook\s*$", re.IGNORECASE)

#: The TikTok profile line: "Veritasium veritasium 66 Following 1.8M Followers".
_TT_HANDLE_RE = re.compile(
    r"(?P<handle>[A-Za-z0-9_.]{2,30})\s+[\d.,]+\s*Following", re.IGNORECASE
)

#: The navigation words that sit in front of a profile line.
_NAV_WORDS = frozenset(
    {
        "log",
        "in",
        "search",
        "for",
        "you",
        "explore",
        "following",
        "short",
        "dramas",
        "live",
        "upload",
        "profile",
        "more",
        "company",
        "program",
        "terms",
        "policies",
        "tiktok",
        "and",
        "or",
        "the",
        "a",
        "an",
        "is",
        "are",
        "©",
    }
)


#: A name that says the page is not the creator's own account.
_NAME_NEGATIVE_WORDS = frozenset(
    {
        "fan",
        "fans",
        "fanpage",
        "clips",
        "clip",
        "edits",
        "edit",
        "updates",
        "update",
        "news",
        "parody",
        "fake",
        "unofficial",
        "community",
        "backup",
        "reupload",
        "reuploads",
        "archive",
        "archives",
        "highlights",
        "compilation",
        "compilations",
    }
)

#: Extra words that do not change whose name it is.
_NAME_NEUTRAL_WORDS = frozenset(
    {"official", "the", "channel", "tv", "show", "yt", "youtube"}
)

#: The evidence that can count toward a FOUND.
_POSITIVE_EVIDENCE = frozenset({"bio_link", "back_link", "name_match", "handle_match"})


class Verdict(str, Enum):
    """What the check found."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    NO_MATCH = "no_match"
    UNKNOWN = "unknown"


@dataclass
class CreatorRef:
    """Who we are looking for."""

    title: str = ""
    handle: str = ""
    url: str = ""
    channel_id: str = ""


@dataclass
class CheckResult:
    """The outcome for one account."""

    platform: str
    verdict: Verdict
    url: str = ""
    display_name: str = ""
    handle: str = ""
    evidence: list[str] = field(default_factory=list)
    detail: str = ""
    source: str = ""
    tier: str = ""

    @property
    def confidence(self) -> float:
        """How sure we are. Only a found account is ever sure."""
        return {"confirmed": 0.9, "likely": 0.7}.get(self.tier, 0.0)


# --------------------------------------------------------------------------- #
# Reading a profile
# --------------------------------------------------------------------------- #
def _norm(value: str) -> str:
    """A comparable form of a name: lower case, letters and digits only."""
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _handle_from_url(url: str) -> str:
    match = re.search(r"(?:/|@)([A-Za-z0-9_.\-]+)/?$", url or "")
    return match.group(1) if match else ""


def _meta(page: Page, key: str) -> str:
    return (page.meta or {}).get(key, "") or ""


def _name_before(text: str, position: int) -> str:
    """The display name in front of the handle, without the navigation."""
    words = [
        word
        for word in text[:position].split()
        if word.lower().strip(".,·•") not in _NAV_WORDS
    ]
    return " ".join(words[-3:]).strip(" .,·•")


def _instagram_profile(page: Page) -> tuple[bool, str, str, str]:
    """(exists, display name, handle, detail)"""
    og_title = _meta(page, "ogTitle")
    og_desc = _meta(page, "ogDescription")
    if og_title:
        match = _IG_TITLE_RE.match(og_title)
        name = match.group("name").strip() if match else og_title.split("•")[0].strip()
        handle = match.group("handle") if match else _handle_from_url(page.url)
        return True, name, handle, "the profile page describes the account"
    if any(sig in (page.title or "").lower() for sig in NOT_FOUND_SIGNATURES):
        return False, "", "", "the page says the profile is not available"
    if _FOLLOWERS_RE.search(og_desc or ""):
        return True, "", _handle_from_url(page.url), "the page shows a follower count"
    if any(sig in (page.text or "").lower() for sig in LOGIN_WALL_SIGNATURES):
        return True, "", "", "the page is behind a login wall"
    return True, "", "", "the page shows nothing about an account"


def _facebook_profile(page: Page) -> tuple[bool, str, str, str]:
    """(exists, display name, handle, detail)"""
    og_title = _meta(page, "ogTitle")
    og_desc = _meta(page, "ogDescription")
    if og_title:
        name = og_title.strip()
        handle = _handle_from_url(_meta(page, "ogUrl") or page.url)
        return True, name, handle, "the page describes the account"
    if any(sig in (page.text or "").lower() for sig in NOT_FOUND_SIGNATURES):
        return False, "", "", "the page says the account is not available"
    title = (page.title or "").strip()
    if title.lower() in ("facebook", "log in", ""):
        # The generic wall: the same answer for a page that does not exist
        # and for a page that is gated. That is unknown, not "not found".
        return True, "", "", "the page shows only the login wall"
    if _FOLLOWERS_RE.search(og_desc or page.text or ""):
        return True, title, _handle_from_url(page.url), "the page shows a follower count"
    return True, "", "", "the page shows nothing about an account"


def _tiktok_profile(page: Page) -> tuple[bool, str, str, str]:
    """(exists, display name, handle, detail)"""
    og_title = _meta(page, "ogTitle")
    text = page.text or ""
    haystack = f"{og_title} {page.title or ''} {text}".lower()
    if "couldn't find this account" in haystack or "couldn’t find this account" in haystack:
        return False, "", "", "the page says the account could not be found"
    match = _TT_HANDLE_RE.search(text)
    if match:
        handle = match.group("handle")
        return (
            True,
            _name_before(text, match.start()),
            handle,
            "the profile page shows the account",
        )
    if og_title:
        return (
            True,
            og_title.strip(),
            _handle_from_url(page.url),
            "the page describes the account",
        )
    return True, "", "", "the page shows nothing about an account"


_READERS = {
    "instagram": _instagram_profile,
    "facebook": _facebook_profile,
    "tiktok": _tiktok_profile,
}


def read_profile(page: Page, platform: str) -> tuple[bool, str, str, str]:
    """Read one rendered profile page: (exists, name, handle, detail).

    ``exists`` means the page did not say the account is missing. It does
    not mean the page identifies the account: a login wall returns True
    with an empty name, and the caller must not treat that as evidence.
    """
    reader = _READERS.get(platform)
    if reader is None:
        return False, "", "", "unknown platform"
    return reader(page)


# --------------------------------------------------------------------------- #
# Deciding
# --------------------------------------------------------------------------- #
def _compact(value: str) -> str:
    """A name with no punctuation or spacing, for an exact comparison."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _name_evidence(profile_name: str, creator_title: str) -> str:
    """How the display name relates to the creator's name.

    Only an exact name, or one with neutral words added, is a match. A name
    with a fan/clip word is a conflict; any other extra word is partial.
    """
    profile = _norm(profile_name)
    title = _norm(creator_title)
    if not profile or not title:
        return ""
    profile_compact = _compact(profile)
    title_compact = _compact(title)
    if profile_compact == title_compact:
        return "name_match"

    # Display names often run the words together ("MrBeastFan").
    if profile_compact.startswith(title_compact):
        suffix = profile_compact[len(title_compact) :]
        if any(word in suffix for word in _NAME_NEGATIVE_WORDS):
            return "name_conflict"
        if suffix in _NAME_NEUTRAL_WORDS:
            return "name_match"
        return "name_partial"

    profile_words, title_words = set(profile.split()), set(title.split())
    if not (profile_words <= title_words or title_words <= profile_words):
        return ""
    extra = (profile_words - title_words) | (title_words - profile_words)
    if extra & _NAME_NEGATIVE_WORDS:
        return "name_conflict"
    if extra <= _NAME_NEUTRAL_WORDS:
        return "name_match"
    return "name_partial"


def _unwrap_link(link: str) -> str:
    """Unwrap the redirects the social pages use for outbound links."""
    for _ in range(3):
        parsed = urlparse(link)
        host = (parsed.hostname or "").lower()
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)
        target = ""
        if host.endswith("facebook.com") and path == "/l.php":
            target = (query.get("u") or [""])[0]
        elif host.endswith("youtube.com") and path in ("/redirect", "/attribution_link"):
            target = (query.get("q") or query.get("u") or [""])[0]
        elif host.endswith("tiktok.com") and parsed.path.startswith("/link/"):
            target = (query.get("target") or [""])[0]
        elif host.endswith("instagram.com") and path in ("/l.php", ""):
            target = (query.get("u") or [""])[0]
        if not target:
            break
        link = target
    return link


def _youtube_target(link: str) -> tuple[str, str]:
    """The (channel id, handle) a YouTube link names, or ("", "").

    A video/short link names no channel here; it is not back-link evidence.
    """
    parsed = urlparse(_unwrap_link(link))
    host = (parsed.hostname or "").lower()
    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        return "", ""
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return "", ""
    if parts[0] == "channel" and len(parts) > 1:
        return parts[1], ""
    if parts[0].startswith("@") and len(parts[0]) > 1:
        return "", parts[0][1:]
    if parts[0] in {"c", "user"} and len(parts) > 1:
        return "", parts[1]
    return "", ""


def _creator_targets(creator: CreatorRef) -> tuple[str, str]:
    """The channel id and handle to compare a back-link against."""
    channel_id = (creator.channel_id or "").strip()
    handle = (creator.handle or "").strip().lstrip("@")
    if creator.url:
        url_channel_id, url_handle = _youtube_target(creator.url)
        channel_id = channel_id or url_channel_id
        handle = handle or url_handle
    return channel_id, handle


def _link_matches_creator(link: str, channel_id: str, handle: str) -> tuple[bool, bool]:
    """(is a YouTube channel link, does it name this creator)."""
    if not channel_id and not handle:
        return False, False
    target_id, target_handle = _youtube_target(link)
    if not target_id and not target_handle:
        return False, False
    if channel_id and target_id and target_id.lower() == channel_id.lower():
        return True, True
    if handle and target_handle and target_handle.lower() == handle.lower():
        return True, True
    return True, False


def positive_evidence(evidence: list[str]) -> list[str]:
    """The evidence items that count toward a FOUND."""
    return [item for item in evidence if item in _POSITIVE_EVIDENCE]


def confidence_tier(evidence: list[str]) -> str:
    """How strong the evidence is, once a page has been found."""
    positives = set(positive_evidence(evidence))
    if not positives:
        return ""
    if "name_conflict" in evidence:
        return "likely" if "bio_link" in positives else "unclear"
    if "conflicting_back_link" in evidence and "bio_link" in positives:
        return "likely"
    if "bio_link" in positives and len(positives) >= 2:
        return "confirmed"
    if {"name_match", "handle_match", "back_link"} <= positives:
        return "confirmed"
    if len(positives) >= 2:
        return "likely"
    if "bio_link" in positives:
        return "likely"
    return "unclear"


def match_evidence(profile_name: str, profile_handle: str, page: Page, creator: CreatorRef) -> list[str]:
    """Why we believe the account is this creator's."""
    evidence: list[str] = []
    name = _name_evidence(profile_name, creator.title)
    if name:
        evidence.append(name)
    channel_id, handle = _creator_targets(creator)
    page_handle = (profile_handle or "").lower().lstrip("@")
    if page_handle and handle and page_handle == handle.lower():
        evidence.append("handle_match")
    saw_match = False
    saw_conflict = False
    for link in page.links or []:
        is_youtube, matches = _link_matches_creator(link, channel_id, handle)
        if not is_youtube:
            continue
        if matches:
            saw_match = True
        else:
            saw_conflict = True
    if saw_match:
        evidence.append("back_link")
    elif saw_conflict:
        evidence.append("conflicting_back_link")
    return evidence


def verify_page(page: Page, platform: str, creator: CreatorRef) -> CheckResult:
    """Decide what a rendered page says about one account."""
    reader = _READERS.get(platform)
    if reader is None:
        return CheckResult(
            platform=platform,
            verdict=Verdict.UNKNOWN,
            url=page.url,
            detail=f"no reader for {platform}",
        )

    if not (page.title or "").strip() and not (page.text or "").strip():
        # Nothing was rendered at all: we could not read the page.
        return CheckResult(
            platform=platform,
            verdict=Verdict.UNKNOWN,
            url=page.url,
            detail="the page rendered nothing",
        )

    exists, name, handle, detail = reader(page)
    if not exists:
        return CheckResult(
            platform=platform,
            verdict=Verdict.NOT_FOUND,
            url=page.url,
            detail=detail,
        )

    evidence = match_evidence(name, handle, page, creator)
    positives = positive_evidence(evidence)

    if not name and not handle:
        return CheckResult(
            platform=platform,
            verdict=Verdict.UNKNOWN,
            url=page.url,
            detail=detail,
        )

    if "name_conflict" in evidence or "conflicting_back_link" in evidence:
        reasons = []
        if "name_conflict" in evidence:
            reasons.append("the page's name marks it as a fan or unofficial account")
        if "conflicting_back_link" in evidence:
            reasons.append("the page links to a different YouTube channel")
        return CheckResult(
            platform=platform,
            verdict=Verdict.NO_MATCH,
            url=page.url,
            display_name=name,
            handle=handle,
            evidence=evidence,
            detail="; ".join(reasons),
        )

    if len(positives) >= 2:
        tier = confidence_tier(evidence)
        if tier == "likely":
            detail = f"{detail}; found, but the evidence is not strong enough to confirm it"
        return CheckResult(
            platform=platform,
            verdict=Verdict.FOUND,
            url=page.url,
            display_name=name,
            handle=handle,
            evidence=evidence,
            detail=detail,
            tier=tier,
        )

    detail = (
        "only one signal ties the account to the creator; two are needed"
        if positives
        else f"the account is '{name or handle}', not '{creator.title or creator.handle}'"
    )
    return CheckResult(
        platform=platform,
        verdict=Verdict.NO_MATCH,
        url=page.url,
        display_name=name,
        handle=handle,
        evidence=evidence,
        detail=detail,
    )


def verify_candidate(session, url: str, platform: str, creator: CreatorRef) -> CheckResult:
    """Open one account and decide what it is.

    A profile that renders late is read once more before it is called
    unknown — TikTok paints its profile in after the first paint.
    """
    try:
        page = session.open(url)
    except PageUnavailable as exc:
        return CheckResult(
            platform=platform,
            verdict=Verdict.UNKNOWN,
            url=url,
            detail=f"the page could not be read: {exc}",
        )
    result = verify_page(page, platform, creator)
    if result.verdict is Verdict.UNKNOWN and (
        "rendered nothing" in result.detail or "nothing about an account" in result.detail
    ):
        try:
            page = session.open(url, wait_ms=5000)
        except PageUnavailable as exc:
            return CheckResult(
                platform=platform,
                verdict=Verdict.UNKNOWN,
                url=url,
                detail=f"the page could not be read: {exc}",
            )
        result = verify_page(page, platform, creator)
    return result


def verify_candidates(
    session,
    creator: CreatorRef,
    candidates: dict[str, list[str]],
    bio_urls: set[str] | frozenset[str] = frozenset(),
    *,
    on_check: Callable[[], None] | None = None,
) -> list[CheckResult]:
    """Check every candidate and keep the ones worth showing.

    A candidate that does not exist is dropped; the one that matches wins;
    a platform we could not check stays unknown; one that exists but belongs
    to somebody else is kept as ``NO_MATCH``. A URL from the channel page is
    ``FOUND`` with ``bio_link`` when the page cannot be read, or when it has
    at least one match. A readable page with no match stays ``NO_MATCH``: the
    channel page also lists sponsors, so it cannot overrule the account page.

    ``on_check`` is called before each account is opened.
    """
    results: list[CheckResult] = []
    for platform, urls in (candidates or {}).items():
        unknown: CheckResult | None = None
        no_match: CheckResult | None = None
        for url in urls:
            if on_check is not None:
                on_check()
            result = verify_candidate(session, url, platform, creator)
            is_bio = url in bio_urls
            result.source = "bio" if is_bio else "model"
            if is_bio:
                if result.verdict is Verdict.UNKNOWN:
                    # The page could not be read; the link is the evidence.
                    result.verdict = Verdict.FOUND
                    result.evidence.insert(0, "bio_link")
                    result.detail = "the channel bio linked it, but the page could not be read"
                elif result.verdict is Verdict.NO_MATCH and positive_evidence(result.evidence):
                    # One positive signal from the page plus the link is two.
                    result.verdict = Verdict.FOUND
                    result.evidence.insert(0, "bio_link")
                    if "name_conflict" in result.evidence:
                        result.detail = (
                            "the channel bio linked it, but the page's name marks "
                            "it as a fan or unofficial account"
                        )
                    elif "conflicting_back_link" in result.evidence:
                        result.detail = (
                            "the channel bio linked it, but the page links to "
                            "a different YouTube channel"
                        )
                    else:
                        result.detail = (
                            "the channel bio linked it, and the page matches one signal"
                        )
                elif result.verdict is Verdict.FOUND and "bio_link" not in result.evidence:
                    result.evidence.insert(0, "bio_link")
                    result.detail = (
                        "the channel bio linked it, and the page matches the creator"
                    )
            if result.verdict is Verdict.FOUND:
                result.tier = confidence_tier(result.evidence)
                results.append(result)
                break
            if result.verdict is Verdict.UNKNOWN and unknown is None:
                # Keep looking: another candidate may still be the answer.
                unknown = result
            if result.verdict is Verdict.NO_MATCH and no_match is None:
                no_match = result
        else:
            # Nothing matched. Say we could not read one before saying the
            # account belongs to somebody else.
            if unknown is not None:
                results.append(unknown)
            elif no_match is not None:
                results.append(no_match)
    return results
