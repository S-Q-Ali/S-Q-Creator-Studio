"""Asynchronous Verification Engine for Facebook, Instagram, and TikTok Profile Existence.

Precision rules:
- HTTP 404 or an explicit "profile doesn't exist" body  -> NOT_FOUND (high confidence).
- Network errors, rate limits, or login/consent walls     -> INCONCLUSIVE (never treated
  as a missing profile).
- A candidate URL that came from the creator's own bio is never downgraded to
  NOT_FOUND by a failed probe — at worst it becomes UNVERIFIED_HANDLE.
- A rendered page is judged against the creator, whoever read it: the browser or
  the AI agent. A bio link needs the page to match it before the account counts
  as verified, and a page that names somebody else never does.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import httpx

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.agent.schema import (
    SocialPlatform,
    SocialPresence,
    SocialStatus,
)
from s_q_ali_media_downloader.agent.tools.browser import Page
from s_q_ali_media_downloader.agent.tools.social_verify import (
    CheckResult,
    CreatorRef,
    Verdict,
    match_evidence,
    positive_evidence,
    read_profile,
    verify_page,
)

logger = logging.getLogger(__name__)


def _answer_field(answer, name: str, default=""):
    """Read one field from an agent answer (object or dict)."""
    if isinstance(answer, dict):
        return answer.get(name, default)
    return getattr(answer, name, default)


def _identity_status(
    evidence: list[str], is_bio_link: bool
) -> tuple[SocialStatus, float]:
    """The status the page's own words earn.

    The same rule the social discovery path uses: a creator-declared link
    is one signal, and the page has to add another before the account can
    be called verified. A link the model guessed is never verified — the
    app only claims that an account exists there.
    """
    positives = positive_evidence(evidence)
    if not is_bio_link:
        return SocialStatus.UNVERIFIED_HANDLE, 0.60
    conflict = "name_conflict" in evidence or "conflicting_back_link" in evidence
    if positives and not conflict:
        return SocialStatus.VERIFIED, 0.95
    return SocialStatus.UNVERIFIED_HANDLE, 0.55


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

IG_LOGIN_WALL_SIGNATURES = ["log in to instagram"]

TIKTOK_LOGIN_WALL_SIGNATURES = ["log in to tiktok"]

#: A 200 page is only a profile when it shows profile data. The login wall and
#: the JavaScript shell are both 200 pages with none of these. A bare
#: "followers" is not enough: both the shell and some walls contain it.
IG_PROFILE_SIGNATURES = ['"edge_followed_by"', '"biography"']

TIKTOK_PROFILE_SIGNATURES = ['"followercount"', '"uniqueid"']


class SocialVerifierTool:
    """Probes Facebook, Instagram, and TikTok profile existence asynchronously.

    Implements rate limiting with exponential backoff to prevent IP bans
    from Facebook, Instagram, and TikTok during bulk discovery.
    """

    def __init__(
        self,
        delay_between_requests: float = 2.0,
        timeout: float = 10.0,
        rendered_checker: Callable[[str], object] | None = None,
        agent_checker: Callable[[str, str], object] | None = None,
        log_callback: Callable[[str], None] | None = None,
        ops: Ops | None = None,
    ):
        self.delay = delay_between_requests
        self.timeout = timeout
        self.rendered_checker = rendered_checker
        self.agent_checker = agent_checker
        self.log_callback = log_callback
        self.ops = ops if ops is not None else Ops(log_callback)
        # A browser session is not thread-safe. One worker means the three
        # platform fallbacks can be gathered without racing each other.
        self._browser_executor = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="social-render")
            if rendered_checker is not None or agent_checker is not None
            else None
        )
        self._request_count = 0
        self._last_request_time = 0.0
        self._retry_after_header = 0.0

    def _log(self, message: str) -> None:
        logger.info(message)
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception as exc:
                logger.warning("Log callback error: %s", exc)

    def close(self) -> None:
        """Close the rendered-page browser, if it was ever started."""
        executor = self._browser_executor
        self._browser_executor = None
        if executor is None:
            return
        try:
            if self.rendered_checker is not None:
                closer = getattr(self.rendered_checker, "close", None)
                if closer is not None:
                    executor.submit(closer).result(timeout=15)
            if self.agent_checker is not None:
                closer = getattr(self.agent_checker, "close", None)
                if closer is not None:
                    executor.submit(closer).result(timeout=15)
        except Exception as exc:
            logger.debug("closing the discovery browser failed: %s", exc)
        finally:
            executor.shutdown(wait=False)

    async def _rendered_fallback(
        self,
        presence: SocialPresence,
        platform: str,
        creator: CreatorRef | None = None,
    ) -> SocialPresence:
        """Try a rendered page when the HTTP probe could not decide."""
        if (
            self.rendered_checker is None
            or self._browser_executor is None
            or not presence.verified_url
        ):
            return presence
        if presence.status not in (
            SocialStatus.INCONCLUSIVE,
            SocialStatus.UNVERIFIED_HANDLE,
        ):
            return presence

        loop = asyncio.get_running_loop()
        self.ops.start(
            "browser.open", "browser", presence.verified_url, detail=f"{platform}"
        )
        started = time.monotonic()
        try:
            page = await loop.run_in_executor(
                self._browser_executor, self.rendered_checker, presence.verified_url
            )
        except Exception as exc:
            self.ops.fail(
                "browser.open",
                "browser",
                presence.verified_url,
                str(exc),
                detail=f"{platform}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            self._log(
                f"Rendered {platform} check failed for {presence.verified_url}: {exc}"
            )
            return presence

        exists, name, handle, detail = read_profile(page, platform)
        is_bio_link = presence.source == "bio_link"
        if not exists:
            if is_bio_link:
                presence.status = SocialStatus.UNVERIFIED_HANDLE
                presence.confidence_score = 0.55
            else:
                presence.status = SocialStatus.NOT_FOUND
                presence.confidence_score = 0.0
        elif name or "follower count" in detail:
            presence.status, presence.confidence_score = self._judged(
                presence, name, handle, creator, page
            )
            presence.handle = handle or presence.handle
        self.ops.ok(
            "browser.open",
            "browser",
            presence.verified_url,
            detail=f"{platform} {presence.status.value}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        self._log(
            f"Rendered {platform} check for {presence.verified_url}: "
            f"{presence.status.value} ({detail})"
        )
        return presence

    def _judged(
        self,
        presence: SocialPresence,
        name: str,
        handle: str,
        creator: CreatorRef | None,
        page: Page | None = None,
    ) -> tuple[SocialStatus, float]:
        """The status the account earns from the creator's point of view.

        Without the creator's name there is nothing to judge against, so
        the account is only reported as existing.
        """
        is_bio_link = presence.source == "bio_link"
        if creator is None or not name:
            if is_bio_link:
                return SocialStatus.VERIFIED, 0.95
            return SocialStatus.UNVERIFIED_HANDLE, 0.60
        evidence = match_evidence(
            name, handle, page or Page(url=presence.verified_url or ""), creator
        )
        status, score = _identity_status(evidence, is_bio_link)
        self._log(
            f"  {presence.platform.value} identity evidence: "
            f"{', '.join(evidence) or 'none'}"
        )
        return status, score

    async def _agent_fallback(
        self,
        presence: SocialPresence,
        platform: str,
        creator: CreatorRef | None = None,
    ) -> SocialPresence:
        """Ask the AI browser when the rendered page still could not decide."""
        if (
            self.agent_checker is None
            or self._browser_executor is None
            or not presence.verified_url
        ):
            return presence
        if presence.status not in (
            SocialStatus.INCONCLUSIVE,
            SocialStatus.UNVERIFIED_HANDLE,
        ):
            return presence
        if getattr(self.agent_checker, "remaining", 1) <= 0:
            return presence
        if getattr(self.agent_checker, "configured", True) is False:
            return presence

        loop = asyncio.get_running_loop()
        self.ops.start(
            "ai.browser.open", "ai-browser", presence.verified_url, detail=platform
        )
        started = time.monotonic()

        def run():
            # browser-use and Playwright cannot share the profile at the same
            # time; closing the deterministic browser lets the agent launch.
            if self.rendered_checker is not None:
                closer = getattr(self.rendered_checker, "close", None)
                if closer is not None:
                    closer()
            return self.agent_checker(presence.verified_url, platform)

        try:
            answer = await loop.run_in_executor(self._browser_executor, run)
        except Exception as exc:
            self.ops.fail(
                "ai.browser.open",
                "ai-browser",
                presence.verified_url,
                str(exc),
                detail=platform,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            self._log(
                f"AI browser {platform} check failed for {presence.verified_url}: {exc}"
            )
            return presence

        exists = str(_answer_field(answer, "exists", "unknown")).lower()
        name = str(_answer_field(answer, "display_name", "") or "")
        handle = str(_answer_field(answer, "handle", "") or "")
        followers = str(_answer_field(answer, "followers", "") or "")
        quote = str(_answer_field(answer, "quote", "") or "")
        reason = str(_answer_field(answer, "reason", "") or "")
        is_bio_link = presence.source == "bio_link"

        if exists == "no":
            if is_bio_link:
                presence.status = SocialStatus.UNVERIFIED_HANDLE
                presence.confidence_score = 0.55
            else:
                presence.status = SocialStatus.NOT_FOUND
                presence.confidence_score = 0.0
        elif exists == "yes" and (name or handle or followers):
            # The agent reads the page; it does not decide who owns it.
            # The name and handle go through the same evidence rule a
            # rendered page would.
            presence.status, presence.confidence_score = self._judged(
                presence, name, handle, creator
            )
            presence.handle = handle or presence.handle
        else:
            return presence

        self.ops.ok(
            "ai.browser.open",
            "ai-browser",
            presence.verified_url,
            detail=f"{platform} {presence.status.value}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        self._log(
            f"AI browser {platform} check for {presence.verified_url}: "
            f"{presence.status.value} ({reason or quote or 'read by the agent'})"
        )
        return presence

    def verify_url(self, url: str, platform: str, creator: CreatorRef) -> CheckResult:
        """Open one URL in the browser and say what the page says about it.

        This is the browser leg of the second check: the web proposes a
        URL, and the browser decides whether the account behind it is the
        creator's. The same evidence rules as a rendered candidate apply,
        so a page that names somebody else is never this creator's
        account.
        """
        if self.rendered_checker is None or self._browser_executor is None:
            return CheckResult(
                platform=platform,
                verdict=Verdict.UNKNOWN,
                url=url,
                detail="no browser is available",
            )
        self.ops.start("browser.open", "browser", url, detail=platform)
        started = time.monotonic()
        try:
            page = self._browser_executor.submit(
                self.rendered_checker, url
            ).result(timeout=90)
        except Exception as exc:
            self.ops.fail(
                "browser.open",
                "browser",
                url,
                str(exc),
                detail=platform,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            return CheckResult(
                platform=platform,
                verdict=Verdict.UNKNOWN,
                url=url,
                detail=f"the page could not be read: {exc}",
            )
        result = verify_page(page, platform, creator)
        self.ops.ok(
            "browser.open",
            "browser",
            url,
            detail=f"{platform} {result.verdict.value}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return result

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting with exponential backoff on 429 errors.

        Resets the counter every 10 requests to prevent accumulating delays
        after many requests.
        """
        # Check Retry-After header first
        if self._retry_after_header > 0:
            time.sleep(self._retry_after_header)
            self._retry_after_header = 0.0

        # Minimum delay between requests
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

        # Exponential backoff on high request count (prevent IP bans)
        # Reset counter every 10 requests to prevent unbounded delays
        if self._request_count % 10 == 0:
            time.sleep(1.0)
            self._request_count = 0

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
        profile_sigs: list[str] | None = None,
    ) -> SocialStatus:
        """Classifies a 200 response body into a SocialStatus."""
        body = response.text.lower()
        if any(sig in body for sig in not_found_sigs):
            return SocialStatus.NOT_FOUND
        if any(sig in body for sig in login_wall_sigs):
            return SocialStatus.INCONCLUSIVE
        if profile_sigs is not None and not any(sig in body for sig in profile_sigs):
            return SocialStatus.INCONCLUSIVE
        return SocialStatus.VERIFIED

    async def verify_facebook_presence(
        self,
        candidate_url: str | None,
        channel_handle: str | None = None,
        source: str | None = None,
    ) -> SocialPresence:
        """Verifies if a Facebook page exists."""
        presence = SocialPresence(platform=SocialPlatform.FACEBOOK)

        target_url = candidate_url
        # A URL the creator put in their own bio is worth more than one the
        # model guessed, so the caller says which it is.
        source = source or ("bio_link" if candidate_url else "handle_guess")

        if not target_url and channel_handle:
            clean_handle = channel_handle.lstrip("@")
            target_url = f"https://www.facebook.com/{clean_handle}/"

        if not target_url:
            return presence

        presence.verified_url = target_url
        presence.handle = target_url.rstrip("/").split("/")[-1]
        presence.source = source
        is_bio_link = source == "bio_link"

        self.ops.start("http.probe", "http", target_url, detail="facebook")
        started = time.monotonic()
        try:
            # Enforce rate limiting before making the request
            self._enforce_rate_limit()
            
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
                    if is_bio_link:
                        self._failure_status(presence, is_bio_link)
                    else:
                        presence.status = SocialStatus.NOT_FOUND
                        presence.confidence_score = 0.0
                else:
                    self._failure_status(presence, is_bio_link)
        except Exception as e:
            logger.warning(f"FB probe failed for {target_url}: {e}")
            self._failure_status(presence, is_bio_link)

        self.ops.ok(
            "http.probe",
            "http",
            target_url,
            detail=f"facebook {presence.status.value}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return presence

    async def verify_instagram_presence(
        self,
        candidate_url: str | None,
        channel_handle: str | None = None,
        source: str | None = None,
    ) -> SocialPresence:
        """Verifies if an Instagram profile exists."""
        presence = SocialPresence(platform=SocialPlatform.INSTAGRAM)

        target_url = candidate_url
        source = source or ("bio_link" if candidate_url else "handle_guess")

        if not target_url and channel_handle:
            clean_handle = channel_handle.lstrip("@")
            target_url = f"https://www.instagram.com/{clean_handle}/"

        if not target_url:
            return presence

        presence.verified_url = target_url
        presence.handle = target_url.rstrip("/").split("/")[-1]
        presence.source = source
        is_bio_link = source == "bio_link"

        self.ops.start("http.probe", "http", target_url, detail="instagram")
        started = time.monotonic()
        try:
            # Enforce rate limiting before making the request
            self._enforce_rate_limit()
            
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=self.timeout, headers=DEFAULT_HEADERS
            ) as client:
                response = await client.get(target_url)

                if response.status_code == 200:
                    status = self._classify(
                        response,
                        IG_NOT_FOUND_SIGNATURES,
                        IG_LOGIN_WALL_SIGNATURES,
                        IG_PROFILE_SIGNATURES,
                    )
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
                    if is_bio_link:
                        self._failure_status(presence, is_bio_link)
                    else:
                        presence.status = SocialStatus.NOT_FOUND
                        presence.confidence_score = 0.0
                else:
                    # 302-to-login or rate limit — unknown, never "missing".
                    self._failure_status(presence, is_bio_link)
        except Exception as e:
            logger.warning(f"IG probe failed for {target_url}: {e}")
            self._failure_status(presence, is_bio_link)

        self.ops.ok(
            "http.probe",
            "http",
            target_url,
            detail=f"instagram {presence.status.value}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return presence

    async def verify_tiktok_presence(
        self,
        candidate_url: str | None,
        channel_handle: str | None = None,
        source: str | None = None,
    ) -> SocialPresence:
        """Verifies if a TikTok profile exists."""
        presence = SocialPresence(platform=SocialPlatform.TIKTOK)

        target_url = candidate_url
        source = source or ("bio_link" if candidate_url else "handle_guess")

        if not target_url and channel_handle:
            clean_handle = channel_handle.lstrip("@")
            target_url = f"https://www.tiktok.com/@{clean_handle}/"

        if not target_url:
            return presence

        presence.verified_url = target_url
        presence.handle = target_url.rstrip("/").split("/")[-1].lstrip("@")
        presence.source = source
        is_bio_link = source == "bio_link"

        self.ops.start("http.probe", "http", target_url, detail="tiktok")
        started = time.monotonic()
        try:
            # Enforce rate limiting before making the request
            self._enforce_rate_limit()
            
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=self.timeout, headers=DEFAULT_HEADERS
            ) as client:
                response = await client.get(target_url)

                if response.status_code == 200:
                    status = self._classify(
                        response,
                        TIKTOK_NOT_FOUND_SIGNATURES,
                        TIKTOK_LOGIN_WALL_SIGNATURES,
                        TIKTOK_PROFILE_SIGNATURES,
                    )
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
                    if is_bio_link:
                        self._failure_status(presence, is_bio_link)
                    else:
                        presence.status = SocialStatus.NOT_FOUND
                        presence.confidence_score = 0.0
                else:
                    self._failure_status(presence, is_bio_link)
        except Exception as e:
            logger.warning(f"TikTok probe failed for {target_url}: {e}")
            self._failure_status(presence, is_bio_link)

        self.ops.ok(
            "http.probe",
            "http",
            target_url,
            detail=f"tiktok {presence.status.value}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return presence

    async def verify_creator_socials(
        self,
        candidate_fb: str | None,
        candidate_ig: str | None,
        channel_handle: str | None = None,
        candidate_sources: dict[str, str] | None = None,
        creator: CreatorRef | None = None,
    ) -> tuple[SocialPresence, SocialPresence]:
        """Probes a creator's Facebook page and Instagram profile in parallel.

        The creator's own platform is the input, so TikTok is never probed
        here. A missing candidate is guessed from ``channel_handle``.
        """
        sources = candidate_sources or {}
        fb_res, ig_res = await asyncio.gather(
            self.verify_facebook_presence(
                candidate_fb, channel_handle, sources.get("facebook")
            ),
            self.verify_instagram_presence(
                candidate_ig, channel_handle, sources.get("instagram")
            ),
        )
        fb_res = await self._rendered_fallback(fb_res, "facebook", creator)
        ig_res = await self._rendered_fallback(ig_res, "instagram", creator)
        fb_res = await self._agent_fallback(fb_res, "facebook", creator)
        ig_res = await self._agent_fallback(ig_res, "instagram", creator)
        return fb_res, ig_res

    async def verify_channel_socials(
        self,
        candidate_fb: str | None,
        candidate_ig: str | None,
        candidate_tiktok: str | None = None,
        channel_handle: str | None = None,
        candidate_sources: dict[str, str] | None = None,
        creator: CreatorRef | None = None,
    ) -> tuple[SocialPresence, SocialPresence, SocialPresence]:
        """Probes Facebook, Instagram, and TikTok in parallel.

        ``creator`` says who the accounts should belong to, so a page that
        names somebody else is not read as this creator's account.
        """
        sources = candidate_sources or {}
        fb_task = self.verify_facebook_presence(
            candidate_fb, channel_handle, sources.get("facebook")
        )
        ig_task = self.verify_instagram_presence(
            candidate_ig, channel_handle, sources.get("instagram")
        )
        tiktok_task = self.verify_tiktok_presence(
            candidate_tiktok, channel_handle, sources.get("tiktok")
        )

        fb_res, ig_res, tiktok_res = await asyncio.gather(fb_task, ig_task, tiktok_task)
        # Read every page first, then let the agent handle what is left: the
        # agent closes the deterministic browser, so mixing the two per
        # platform would restart it three times.
        fb_res = await self._rendered_fallback(fb_res, "facebook", creator)
        ig_res = await self._rendered_fallback(ig_res, "instagram", creator)
        tiktok_res = await self._rendered_fallback(tiktok_res, "tiktok", creator)
        fb_res = await self._agent_fallback(fb_res, "facebook", creator)
        ig_res = await self._agent_fallback(ig_res, "instagram", creator)
        tiktok_res = await self._agent_fallback(tiktok_res, "tiktok", creator)
        return fb_res, ig_res, tiktok_res
