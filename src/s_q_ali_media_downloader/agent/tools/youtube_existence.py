"""YouTube Presence Detector for TikTok Creators (bio links + bidirectional search match).

Determines whether a TikTok creator already has a YouTube channel:
1. Bio link scan — a youtube.com/youtu.be link inside the TikTok bio is the
   strongest signal (VERIFIED, 0.95).
2. Bidirectional search — find YouTube channels matching the creator's
   handle/nickname, then confirm by checking whether the candidate channel's
   own pages link back to the TikTok profile (VERIFIED, 0.90) or accept a
   strong name-similarity match (UNVERIFIED_HANDLE, 0.60).
"""

import logging
import re
import time
from collections.abc import Callable
from difflib import SequenceMatcher
from typing import ClassVar

import httpx

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.agent.schema import (
    SocialPlatform,
    SocialPresence,
    SocialStatus,
)
from s_q_ali_media_downloader.agent.tools.link_parser import LinkParserTool
from s_q_ali_media_downloader.agent.tools.youtube_search import YouTubeSearchTool

logger = logging.getLogger(__name__)

YOUTUBE_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/(?:@|c/|user/|channel/)[A-Za-z0-9\._\-]{2,60}|youtu\.be/[A-Za-z0-9\._\-]{2,60})/?",
    re.IGNORECASE,
)


def name_similarity(a: str, b: str) -> float:
    """Normalized similarity in [0, 1] between two creator names/handles."""

    def norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    a_norm, b_norm = norm(a), norm(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    ratio = SequenceMatcher(None, a_norm, b_norm).ratio()
    # Token containment bonus: "speed edits" vs "speededits" style matches.
    tokens_a = {t for t in re.split(r"[^a-z0-9]+", a.lower()) if len(t) >= 3}
    tokens_b = {t for t in re.split(r"[^a-z0-9]+", b.lower()) if len(t) >= 3}
    if tokens_a and tokens_b and tokens_a & tokens_b:
        ratio = max(ratio, 0.8)
    return ratio


def page_name(html: str) -> str:
    """The channel's display name, as the page shows it."""
    match = re.search(
        r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).split(" - YouTube")[0].strip()
    return ""


class YouTubeExistenceTool:
    """Checks whether TikTok profiles already run a YouTube channel."""

    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 8.0,
        ops: Ops | None = None,
    ):
        self.search_tool = YouTubeSearchTool(api_key=api_key)
        self.timeout = timeout
        self.ops = ops if ops is not None else Ops()

    def check_youtube_presence(
        self, profile, suggested_handle: Callable[[], str | None] | None = None
    ) -> SocialPresence:
        """Synchronous presence check for one TikTok profile.

        ``suggested_handle`` is a callable so the AI is only asked when the
        bio has not already answered the question.
        """
        presence = SocialPresence(platform=SocialPlatform.YOUTUBE)

        # ---- 1. Bio link scan (strongest signal) ----
        bio = profile.bio or ""
        yt_matches = YOUTUBE_URL_PATTERN.findall(bio)
        if yt_matches:
            url = yt_matches[0].rstrip("/")
            presence.verified_url = url if url.startswith("http") else f"https://{url}"
            presence.handle = LinkParserTool.extract_handle_from_url(presence.verified_url)
            presence.source = "bio_link"
            presence.status = SocialStatus.VERIFIED
            presence.confidence_score = 0.95
            self.ops.ok(
                "bio.link",
                "http",
                presence.verified_url,
                detail="youtube channel linked in the TikTok bio",
            )
            return presence

        # ---- 2. The handle the AI proposed ----
        if suggested_handle is not None:
            handle = (suggested_handle() or "").lstrip("@").strip()
            if handle:
                url = f"https://www.youtube.com/@{handle}"
                self.ops.start("http.probe", "http", url, detail="youtube (AI handle)")
                started = time.monotonic()
                exists, name = self._channel_page(url)
                self.ops.ok(
                    "http.probe",
                    "http",
                    url,
                    detail=f"youtube {'found' if exists else 'no channel'}",
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
                if exists and self._belongs_to(profile, name):
                    presence.verified_url = url
                    presence.handle = handle
                    presence.source = "model"
                    if self._channel_links_to_tiktok(url, profile.handle):
                        presence.status = SocialStatus.VERIFIED
                        presence.confidence_score = 0.90
                    else:
                        presence.status = SocialStatus.UNVERIFIED_HANDLE
                        presence.confidence_score = 0.60
                    return presence
                # The model's handle names somebody else's channel. The
                # search below gets its turn.

        # ---- 3. YouTube search for the handle / nickname ----
        query = profile.handle.replace("_", " ") or profile.nickname
        self.ops.start("youtube.search", "youtube", query, detail="channel search")
        started = time.monotonic()
        try:
            candidates = self.search_tool.search_channels(
                query=query,
                max_results=10,
            )
        except Exception as e:
            logger.warning(f"YouTube existence search failed for @{profile.handle}: {e}")
            self.ops.fail(
                "youtube.search", "youtube", query, str(e),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            presence.status = SocialStatus.INCONCLUSIVE
            presence.confidence_score = 0.5
            return presence
        self.ops.ok(
            "youtube.search",
            "youtube",
            query,
            detail=f"{len(candidates)} candidate(s)",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

        if not candidates:
            presence.status = SocialStatus.NOT_FOUND
            presence.confidence_score = 0.0
            return presence

        # Rank candidates by name similarity against the TikTok handle/nickname
        best, best_score = None, 0.0
        for channel in candidates:
            score = max(
                name_similarity(profile.handle, channel.title),
                name_similarity(profile.nickname, channel.title),
                name_similarity(profile.handle, channel.handle or ""),
            )
            if score > best_score:
                best, best_score = channel, score

        if best is None or best_score < 0.6:
            presence.status = SocialStatus.NOT_FOUND
            presence.confidence_score = 0.0
            return presence

        presence.verified_url = best.youtube_url
        presence.handle = best.handle
        presence.source = "name_match"

        # ---- 3. Bidirectional confirmation: does the candidate link back? ----
        if self._channel_links_to_tiktok(best.youtube_url, profile.handle):
            presence.status = SocialStatus.VERIFIED
            presence.confidence_score = 0.90
        elif best_score >= 0.9:
            presence.status = SocialStatus.UNVERIFIED_HANDLE
            presence.confidence_score = 0.65
        else:
            presence.status = SocialStatus.UNVERIFIED_HANDLE
            presence.confidence_score = round(0.4 + best_score * 0.2, 2)

        return presence

    def _channel_page(self, channel_url: str) -> tuple[bool, str]:
        """(YouTube serves a channel page, the name that page shows)."""
        try:
            with httpx.Client(
                timeout=self.timeout, follow_redirects=True, headers=self.HEADERS
            ) as client:
                resp = client.get(channel_url)
            if resp.status_code != 200:
                return False, ""
            return True, page_name(resp.text)
        except Exception as e:
            logger.debug(f"Channel probe failed for {channel_url}: {e}")
            return False, ""

    @staticmethod
    def _belongs_to(profile, channel_name: str) -> bool:
        """True when the channel's own name looks like this creator's.

        A handle that exists is not enough: the model can name a channel
        that belongs to somebody else, and that would hide a creator who
        really has no channel.
        """
        if not channel_name:
            return False
        return (
            name_similarity(profile.handle, channel_name) >= 0.6
            or name_similarity(profile.nickname, channel_name) >= 0.6
        )

    def _channel_links_to_tiktok(self, channel_url: str, tiktok_handle: str) -> bool:
        """True if the YouTube channel page references the TikTok profile."""
        try:
            with httpx.Client(
                timeout=self.timeout, follow_redirects=True, headers=self.HEADERS
            ) as client:
                resp = client.get(channel_url.rstrip("/") + "/about")
                if resp.status_code != 200:
                    return False
                html = resp.text.lower()
                return f"tiktok.com/@{tiktok_handle.lower()}" in html
        except Exception as e:
            logger.debug(f"Backlink check failed for {channel_url}: {e}")
            return False
