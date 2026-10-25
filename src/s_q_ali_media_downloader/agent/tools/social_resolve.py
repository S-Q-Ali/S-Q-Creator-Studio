"""Resolve a channel from a URL, a handle or a name — and read its own links.

The channel's own social links are the only evidence that is a self-claim.
They live in two places on the About page, and they must not be confused
with the links of the *videos* that are listed there:

* the "Links" section — the links the creator added to the channel. On the
  page they are wrapped in a redirect carrying ``event=channel_header``.
* the channel description — its links also carry ``event=video_description``,
  but so do the links of every listed video, and those belong to other
  creators (verified 2026-10-21: MrBeast's About page lists videos whose
  descriptions link to ifit, johnpeelfitness and a car dealership).

So only the ``channel_header`` links are taken from the page; the
description's links are read from the creator's *own* video, where the
ownership can be checked.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse

from s_q_ali_media_downloader.agent.tools.browser import Page, PageUnavailable
from s_q_ali_media_downloader.agent.tools.youtube_existence import name_similarity
from s_q_ali_media_downloader.core.youtube_client import (
    fetch_channel,
    search_channels,
)

logger = logging.getLogger(__name__)

#: Hosts that are never a creator's own social account.
_NOT_SOCIAL_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "google.com",
        "www.google.com",
        "support.google.com",
        "policies.google.com",
        "accounts.google.com",
    }
)

#: The platforms a creator's account can live on.
_SOCIAL_MARKERS = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
)

#: A handle in the page text: ``@mkbhd``.
_HANDLE_RE = re.compile(r"(?:^|\s)@([A-Za-z0-9_.\-]{2,40})")

#: ``21.4M subscribers``
_SUBS_RE = re.compile(r"([\d.,]+\s*[KMB]?)\s+subscribers", re.IGNORECASE)

_COUNT_RE = re.compile(r"([\d.,]+)\s*([KMB]?)", re.IGNORECASE)


class ChannelUnresolved(RuntimeError):
    """The channel could not be resolved from what the user gave."""


@dataclass
class ResolvedChannel:
    """One channel, as far as we could get to know it."""

    channel_id: str = ""
    title: str = ""
    handle: str = ""
    url: str = ""
    description: str = ""
    bio_links: list[str] = field(default_factory=list)
    subscribers: int = 0
    source: str = "url"

    def platform_candidates(self) -> dict[str, list[str]]:
        """The candidate links per platform.

        Every link is a candidate: the channel page can hold a sponsor's
        account next to the creator's own (verified 2026-10-21 on MrBeast's
        page), so the verifier checks them all and decides.
        """
        out: dict[str, list[str]] = {"facebook": [], "instagram": [], "tiktok": []}
        for link in self.bio_links:
            host = (urlparse(link).hostname or "").lower()
            if "facebook.com" in host or "fb.com" in host:
                key = "facebook"
            elif "instagram.com" in host:
                key = "instagram"
            elif "tiktok.com" in host:
                key = "tiktok"
            else:
                continue
            if link not in out[key]:
                out[key].append(link)
        return {platform: links for platform, links in out.items() if links}


# --------------------------------------------------------------------------- #
# Which links are the creator's own
# --------------------------------------------------------------------------- #
def _unwrap_redirect(link: str) -> str:
    """Turn a YouTube redirect into the URL it points at."""
    if "youtube.com" not in link:
        return link
    query = parse_qs(urlparse(link).query)
    target = query.get("q")
    if target:
        return unquote(target[0])
    return link


def _as_https(link: str) -> str:
    """Force the https scheme.

    The links on a channel page are a mix of http and https; the platform
    accounts are all https, and a probe should not spend a redirect on it.
    """
    if link.startswith("http://"):
        return "https://" + link[len("http://") :]
    return link


def _is_social_link(link: str) -> bool:
    try:
        host = (urlparse(link).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    if host in _NOT_SOCIAL_HOSTS:
        return False
    return any(marker in host for marker in _SOCIAL_MARKERS)


def social_link_candidates(links: list[str]) -> list[str]:
    """Every social link the channel's page shows, as candidates.

    The page cannot tell us whose links they are. On MrBeast's About page
    his own accounts (facebook.com/MrBeast, instagram.com/mrbeast) sit in
    the same description element as the sponsors he mentions
    (johnpeelfitness, a car dealership) — verified 2026-10-21. Deciding
    which is whose is the verifier's job: it opens the account and looks
    at what the account says about itself.
    """
    candidates: list[str] = []
    for raw in links or []:
        target = _unwrap_redirect(raw)
        if not _is_social_link(target):
            continue
        target = _as_https(target)
        if target not in candidates:
            candidates.append(target)
    return candidates


# --------------------------------------------------------------------------- #
# Reading the page
# --------------------------------------------------------------------------- #
def parse_channel_page(page: Page) -> tuple[str, str]:
    """The channel's display name and handle, as the page shows them."""
    name = ""
    title = (page.title or "").strip()
    if title:
        name = re.sub(r"\s*-\s*YouTube\s*$", "", title).strip()
    if not name:
        # The first line of the page text that looks like a name.
        for line in (page.text or "").splitlines():
            line = line.strip()
            if len(line) > 1 and not line.startswith(("@", "|", "•")):
                name = line
                break
    handle = ""
    match = _HANDLE_RE.search(page.text or "")
    if match:
        handle = match.group(1)
    return name, handle


def _parse_subscribers(text: str) -> int:
    match = _SUBS_RE.search(text or "")
    if not match:
        return 0
    raw, suffix = _COUNT_RE.match(match.group(1).replace(" ", "")).groups() if _COUNT_RE.match(match.group(1).replace(" ", "")) else (match.group(1), "")
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return 0
    factor = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(
        suffix.upper(), 1
    )
    return int(value * factor)


# --------------------------------------------------------------------------- #
# Resolving
# --------------------------------------------------------------------------- #
def _channel_url(text: str) -> str | None:
    """Turn whatever the user typed into a channel URL, or None for a name."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise ChannelUnresolved("Nothing to look up.")
    if cleaned.startswith("@"):
        return f"https://www.youtube.com/{cleaned}"
    if "youtube.com" in cleaned:
        return cleaned if cleaned.startswith("http") else f"https://{cleaned}"
    if "/" not in cleaned and " " not in cleaned:
        return f"https://www.youtube.com/@{cleaned}"
    # A plain name: YouTube search picks the channel.
    return None


def _best_match(query: str):
    """The channel whose name is closest to the query, not the most viewed."""
    try:
        matches = search_channels(query, max_results=5)
    except Exception as exc:
        raise ChannelUnresolved(f"Could not search for that channel: {exc}") from exc
    matches = [match for match in matches if match.channel_id]
    if not matches:
        return None
    return max(matches, key=lambda match: name_similarity(query, match.title))


def resolve_channel(text: str, session=None) -> ResolvedChannel:
    """Resolve a channel and read the creator's own links.

    ``session`` is a :class:`browser.BrowserSession`; when it is None the
    About page is not read and only the metadata is returned.
    """
    url = _channel_url(text)
    searched = url is None
    if searched:
        channel = _best_match((text or "").strip())
        if channel is None:
            raise ChannelUnresolved(f"No channel found for '{text.strip()}'.")
        url = f"https://www.youtube.com/channel/{channel.channel_id}"
    else:
        channel = None
        try:
            channel = fetch_channel(url)
        except Exception as exc:
            # A single word is usually a handle, but it can be a channel name
            # whose handle is different. Search once before giving up.
            # Note: _looks_like_plain_word was removed, so we skip this check.
            # The channel search will handle this case naturally.
            if channel is None:
                raise ChannelUnresolved(f"Could not read that channel: {exc}") from exc

    record = ResolvedChannel(
        channel_id=channel.channel_id,
        title=channel.title,
        handle=(channel.custom_url or "").rstrip("/").rsplit("/", 1)[-1].lstrip("@"),
        url=url,
        description=channel.description or "",
        subscribers=channel.subscriber_count or 0,
        source=(
            "url"
            if "/" in (text or "")
            else "name"
            if searched or " " in (text or "").strip()
            else "handle"
        ),
    )

    if session is None:
        return record

    try:
        page = session.open(f"{url}/about" if not url.endswith("/about") else url)
    except PageUnavailable as exc:
        raise ChannelUnresolved(f"Could not read the channel page: {exc}") from exc

    name, handle = parse_channel_page(page)
    if name:
        record.title = name
    if handle:
        record.handle = handle
    if record.subscribers == 0:
        record.subscribers = _parse_subscribers(page.text)

    record.bio_links = social_link_candidates(page.links)
    return record
