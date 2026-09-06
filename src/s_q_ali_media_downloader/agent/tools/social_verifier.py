"""Asynchronous Verification Engine for Facebook, Instagram, and TikTok Profile Existence.

Precision rules:
- HTTP 404 or an explicit "profile doesn't exist" body  -> NOT_FOUND (high confidence).
- Network errors, rate limits, or login/consent walls     -> INCONCLUSIVE (never treated
  as a missing profile).
- A candidate URL that came from the creator's own bio is never downgraded to
  NOT_FOUND by a failed probe — at worst it becomes UNVERIFIED_HANDLE.
"""

import asyncio
import logging

import httpx

from s_q_ali_media_downloader.agent.schema import (
    SocialPlatform,
    SocialPresence,
    SocialStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

ALT_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    ),
}

FB_NOT_FOUND_SIGNATURES = [
    "this page isn't available",
    "the link you followed may be broken",
    "content not found",
    "this content isn't available right now",
]

FB_LOGIN_WALL_SIGNATURES = [
    "login/?next=",
    "you must log in to continue",
]

IG_NOT_FOUND_SIGNATURES = [
    "sorry, this page isn't available",
    "the link you followed may be broken",
    "user not found",
]

TIKTOK_NOT_FOUND_SIGNATURES = [
    "couldn't find this account",
    "account banned",
    "doesn't exist",
    "no content available",
]


class SocialVerifierTool:
    """Probes Facebook, Instagram, and TikTok profile existence asynchronously."""

    def __init__(self, delay_between_requests: float = 2.0, timeout: float = 10.0):
        self.delay = delay_between_requests
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _failure_status(presence: SocialPresence, is_bio_link: bool) -> SocialPresence:
        """Applies the bio-link downgrade rule on a failed/ambiguous probe."""
        if is_bio_link:
            presence.status = SocialStatus.UNVERIFIED_HANDLE
            presence.confidence_score = 0.55
        else:
            presence.status = SocialStatus.INCONCLUSIVE
            presence.confidence_score = 0.5
        return presence

    def _classify(
        self,
        response: httpx.Response,
        not_found_sigs: list[str],
        login_wall_sigs: list[str],
    ) -> SocialStatus:
        """Classifies a 200 response body into a SocialStatus."""
        body = response.text.lower()
        if any(sig in body for sig in not_found_sigs):
            return SocialStatus.NOT_FOUND
        if any(sig in body for sig in login_wall_sigs):
            return SocialStatus.INCONCLUSIVE
        return SocialStatus.VERIFIED

    async def verify_facebook_presence(
        self, candidate_url: str | None, channel_handle: str | None = None
    ) -> SocialPresence:
        """Verifies if a Facebook page exists."""
        presence = SocialPresence(platform=SocialPlatform.FACEBOOK)

        target_url = candidate_url
        source = "bio_link" if candidate_url else "handle_guess"

        if not target_url and channel_handle:
            clean_handle = channel_handle.lstrip("@")
            target_url = f"https://www.facebook.com/{clean_handle}/"

        if not target_url:
            return presence

        presence.verified_url = target_url
        presence.handle = target_url.rstrip("/").split("/")[-1]
        presence.source = source
        is_bio_link = source == "bio_link"

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=self.timeout, headers=DEFAULT_HEADERS
            ) as client:
                response = await client.get(target_url)

                if response.status_code == 200:
                    status = self._classify(
                        response, FB_NOT_FOUND_SIGNATURES, FB_LOGIN_WALL_SIGNATURES
                    )
                    if status == SocialStatus.NOT_FOUND:
                        # One retry with a mobile UA — desktop FB sometimes serves a
                        # bogus "content not found" shell to plain HTTP clients.
                        retry = await client.get(target_url, headers=ALT_HEADERS)
                        if retry.status_code == 200:
                            status = self._classify(
                                retry, FB_NOT_FOUND_SIGNATURES, FB_LOGIN_WALL_SIGNATURES
                            )
                    if status == SocialStatus.VERIFIED:
                        presence.status = (
                            SocialStatus.VERIFIED if is_bio_link else SocialStatus.UNVERIFIED_HANDLE
                        )
                        presence.confidence_score = 0.95 if is_bio_link else 0.60
                    elif status == SocialStatus.NOT_FOUND and is_bio_link:
                        # Bio link exists but the page shell looks missing — keep it,
                        # flagged, rather than erasing a creator-declared link.
                        presence.status = SocialStatus.UNVERIFIED_HANDLE
                        presence.confidence_score = 0.55
                    elif status == SocialStatus.NOT_FOUND:
                        presence.status = SocialStatus.NOT_FOUND
                        presence.confidence_score = 0.0
                    else:  # INCONCLUSIVE — login wall / ambiguous body
                        self._failure_status(presence, is_bio_link)
                elif response.status_code == 404:
                    presence.status = SocialStatus.NOT_FOUND
                    presence.confidence_score = 0.0
                else:
                    self._failure_status(presence, is_bio_link)
        except Exception as e:
            logger.warning(f"FB probe failed for {target_url}: {e}")
            self._failure_status(presence, is_bio_link)

        return presence

    async def verify_instagram_presence(
        self, candidate_url: str | None, channel_handle: str | None = None
    ) -> SocialPresence:
        """Verifies if an Instagram profile exists."""
        presence = SocialPresence(platform=SocialPlatform.INSTAGRAM)

        target_url = candidate_url
        source = "bio_link" if candidate_url else "handle_guess"

        if not target_url and channel_handle:
            clean_handle = channel_handle.lstrip("@")
            target_url = f"https://www.instagram.com/{clean_handle}/"

        if not target_url:
            return presence

        presence.verified_url = target_url
        presence.handle = target_url.rstrip("/").split("/")[-1]
        presence.source = source
        is_bio_link = source == "bio_link"

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=self.timeout, headers=DEFAULT_HEADERS
            ) as client:
                response = await client.get(target_url)

                if response.status_code == 200:
                    status = self._classify(response, IG_NOT_FOUND_SIGNATURES, [])
                    if status == SocialStatus.VERIFIED:
                        presence.status = (
                            SocialStatus.VERIFIED if is_bio_link else SocialStatus.UNVERIFIED_HANDLE
                        )
                        presence.confidence_score = 0.95 if is_bio_link else 0.60
                    elif status == SocialStatus.NOT_FOUND and is_bio_link:
                        presence.status = SocialStatus.UNVERIFIED_HANDLE
                        presence.confidence_score = 0.55
                    elif status == SocialStatus.NOT_FOUND:
                        presence.status = SocialStatus.NOT_FOUND
                        presence.confidence_score = 0.0
                    else:
                        self._failure_status(presence, is_bio_link)
                elif response.status_code == 404:
                    presence.status = SocialStatus.NOT_FOUND
                    presence.confidence_score = 0.0
                else:
                    # 302-to-login or rate limit — unknown, never "missing".
                    self._failure_status(presence, is_bio_link)
        except Exception as e:
            logger.warning(f"IG probe failed for {target_url}: {e}")
            self._failure_status(presence, is_bio_link)

        return presence

    async def verify_tiktok_presence(
        self, candidate_url: str | None, channel_handle: str | None = None
    ) -> SocialPresence:
        """Verifies if a TikTok profile exists."""
        presence = SocialPresence(platform=SocialPlatform.TIKTOK)

        target_url = candidate_url
        source = "bio_link" if candidate_url else "handle_guess"

        if not target_url and channel_handle:
            clean_handle = channel_handle.lstrip("@")
            target_url = f"https://www.tiktok.com/@{clean_handle}/"

        if not target_url:
            return presence

        presence.verified_url = target_url
        presence.handle = target_url.rstrip("/").split("/")[-1].lstrip("@")
        presence.source = source
        is_bio_link = source == "bio_link"

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=self.timeout, headers=DEFAULT_HEADERS
            ) as client:
                response = await client.get(target_url)

                if response.status_code == 200:
                    status = self._classify(response, TIKTOK_NOT_FOUND_SIGNATURES, [])
                    if status == SocialStatus.VERIFIED:
                        presence.status = (
                            SocialStatus.VERIFIED if is_bio_link else SocialStatus.UNVERIFIED_HANDLE
                        )
                        presence.confidence_score = 0.95 if is_bio_link else 0.60
                    elif status == SocialStatus.NOT_FOUND and is_bio_link:
                        presence.status = SocialStatus.UNVERIFIED_HANDLE
                        presence.confidence_score = 0.55
                    elif status == SocialStatus.NOT_FOUND:
                        presence.status = SocialStatus.NOT_FOUND
                        presence.confidence_score = 0.0
                    else:
                        self._failure_status(presence, is_bio_link)
                elif response.status_code == 404:
                    presence.status = SocialStatus.NOT_FOUND
                    presence.confidence_score = 0.0
                else:
                    self._failure_status(presence, is_bio_link)
        except Exception as e:
            logger.warning(f"TikTok probe failed for {target_url}: {e}")
            self._failure_status(presence, is_bio_link)

        return presence

    async def verify_channel_socials(
        self,
        candidate_fb: str | None,
        candidate_ig: str | None,
        candidate_tiktok: str | None = None,
        channel_handle: str | None = None,
    ) -> tuple[SocialPresence, SocialPresence, SocialPresence]:
        """Probes Facebook, Instagram, and TikTok in parallel."""
        fb_task = self.verify_facebook_presence(candidate_fb, channel_handle)
        ig_task = self.verify_instagram_presence(candidate_ig, channel_handle)
        tiktok_task = self.verify_tiktok_presence(candidate_tiktok, channel_handle)

        fb_res, ig_res, tiktok_res = await asyncio.gather(fb_task, ig_task, tiktok_task)
        return fb_res, ig_res, tiktok_res
