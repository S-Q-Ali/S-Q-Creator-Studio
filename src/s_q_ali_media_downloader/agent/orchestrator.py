"""Agent Orchestrator controller for YouTube discovery and cross-platform social verification."""

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
from functools import partial

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.agent.schema import (
    AgentSearchResult,
    ChannelMetadata,
    SocialPresence,
    SocialStatus,
    TikTokProfileMetadata,
    TikTokSearchResult,
)
from s_q_ali_media_downloader.agent.tools import social_judge as judge
from s_q_ali_media_downloader.agent.tools.agent_browser import AgentBrowserChecker
from s_q_ali_media_downloader.agent.tools.browser import (
    RenderedProfileChecker,
    browser_executable,
    default_profile_dir,
)
from s_q_ali_media_downloader.agent.tools.dual_check import (
    YOUTUBE_RECONCILED_TO_STATUS,
    SearchBudget,
    ask_the_web,
    needs_the_second_check,
)
from s_q_ali_media_downloader.agent.tools.link_parser import LinkParserTool
from s_q_ali_media_downloader.agent.tools.metadata_extractor import MetadataExtractorTool
from s_q_ali_media_downloader.agent.tools.social_verifier import SocialVerifierTool
from s_q_ali_media_downloader.agent.tools.social_verify import (
    AI_UNKNOWN,
    AI_YES,
    RECONCILED_TO_SOCIAL_STATUS,
    STATUS_TO_VERDICT,
    CheckResult,
    CreatorRef,
    Verdict,
    reconcile,
)
from s_q_ali_media_downloader.agent.tools.tiktok_search import TikTokSearchTool
from s_q_ali_media_downloader.agent.tools.youtube_existence import YouTubeExistenceTool
from s_q_ali_media_downloader.agent.tools.youtube_search import YouTubeSearchTool

logger = logging.getLogger(__name__)

#: How many accounts one run may put to the AI. A free Gemini key gets a
#: daily allowance per model, and every proposal is one request: without a
#: cap a run with 50 channels spends the whole day on the first one.
MAX_AI_PROPOSALS = 15


class AgentOrchestrator:
    """Orchestrates multi-tool execution DAG for channel discovery & social presence verification.

    Uses a persistent event loop (not asyncio.run()) so it can be called from a QThread
    without nested event loop conflicts.
    """

    def __init__(
        self,
        api_key: str | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
        show_browser: bool = True,
    ):
        self.search_tool = YouTubeSearchTool(api_key=api_key)
        self.extractor_tool = MetadataExtractorTool()
        # One operation log for the whole run: every engine writes to it, so
        # the activity panel reads as one story of what was attempted.
        self.ops = Ops(self._log)
        profile_dir = default_profile_dir()
        self.verifier_tool = SocialVerifierTool(
            rendered_checker=RenderedProfileChecker(
                headless=not show_browser,
                profile_dir=profile_dir,
            ),
            agent_checker=AgentBrowserChecker(
                headless=not show_browser,
                profile_dir=profile_dir,
                executable_path=browser_executable(),
                log_callback=self._log,
                ops=self.ops,
            ),
            log_callback=self._log,
            ops=self.ops,
        )
        self.tiktok_tool = TikTokSearchTool()
        self.youtube_existence_tool = YouTubeExistenceTool(api_key=api_key, ops=self.ops)
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        # How many AI proposals this run may still make.
        self._ai_proposals = 0
        # How many search-grounded calls this run may still make.
        self.search_budget = SearchBudget()
        # Persistent event loop for reuse across calls.
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

    def __del__(self):
        # Clean up the event loop when the orchestrator is destroyed.
        try:
            if hasattr(self, "_loop") and self._loop:
                if self._loop.is_running():
                    self._loop.stop()
                self._loop.close()
        except Exception:
            # Silent cleanup failure is acceptable here — we're in a destructor
            # where exceptions cannot be propagated and the app is shutting down.
            pass

    def _emit(self, percent: int, message: str) -> None:
        if self.progress_callback:
            try:
                self.progress_callback(percent, message)
            except Exception as e:
                logger.warning("Progress callback error: %s", e)
        self._log(message)

    def _log(self, message: str) -> None:
        """Write a line to the file log and the visible activity log."""
        logger.info(message)
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception as e:
                logger.warning("Log callback error: %s", e)

    def run_discovery(
        self,
        query: str,
        max_channels: int = 50,
        min_subscribers: int = 0,
        check_facebook: bool = True,
        check_instagram: bool = True,
        check_tiktok: bool = False,
        only_no_socials: bool = False,
    ) -> AgentSearchResult:
        """Executes full autonomous agent pipeline."""
        start_time = time.time()
        backend = "YouTube Data API v3" if self.search_tool.api_key else "yt-dlp scraper"
        self._log(
            f"YouTube discovery: {query!r}; backend {backend}; "
            f"up to {max_channels} channels; minimum {min_subscribers} subscribers."
        )
        self._emit(5, f"Initializing Agent... Searching YouTube for '{query}'...")

        # 1. YouTube Discovery
        self.ops.start("youtube.search", "youtube", query, detail=f"up to {max_channels} channels")
        started = time.monotonic()
        raw_channels = self.search_tool.search_channels(
            query=query, max_results=max_channels, min_subscribers=min_subscribers
        )
        self.ops.ok(
            "youtube.search",
            "youtube",
            query,
            detail=f"{len(raw_channels)} channel(s)",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        total_found = len(raw_channels)
        self._emit(25, f"Found {total_found} candidate channels. Extracting metadata...")

        if not raw_channels:
            self._emit(100, "Discovery complete. 0 channels found.")
            return AgentSearchResult(
                query=query,
                total_searched=0,
                channels_matching_filter=0,
                execution_time_seconds=round(time.time() - start_time, 2),
                timestamp=datetime.now(timezone.utc).isoformat(),
                channels=[],
            )

        # 2. Enrich channel metadata
        enriched_channels: list[ChannelMetadata] = []
        for idx, ch in enumerate(raw_channels):
            percent = 25 + int((idx / max(total_found, 1)) * 30)
            self._emit(percent, f"Parsing metadata for {ch.title} ({idx + 1}/{total_found})...")
            enriched = self.extractor_tool.enrich_channel_metadata(ch)
            enriched_channels.append(enriched)

        # 2b. The AI names the accounts the channel's own bio does not list.
        self._propose_socials(
            enriched_channels, check_facebook, check_instagram, check_tiktok
        )

        # 3. Social Presence Verification
        self._emit(60, "Verifying Facebook, Instagram & TikTok presences...")
        try:
            verified_channels = self._loop.run_until_complete(
                self._verify_all_socials(
                    enriched_channels, check_facebook, check_instagram, check_tiktok
                )
            )
        finally:
            self.verifier_tool.close()

        # 4. Filter & Flag Opportunities
        # Only platforms the user actually enabled may count toward "missing".
        checked: list[str] = []
        if check_facebook:
            checked.append("facebook")
        if check_instagram:
            checked.append("instagram")
        if check_tiktok:
            checked.append("tiktok")

        final_channels: list[ChannelMetadata] = []
        no_socials_count = 0

        for ch in verified_channels:
            statuses = {
                "facebook": ch.facebook.status,
                "instagram": ch.instagram.status,
                "tiktok": ch.tiktok.status,
            }

            # A platform counts as "missing" only when it was probed and
            # definitively found to be absent. INCONCLUSIVE / unchecked
            # platforms never mark a channel as a target.
            truly_missing = [p for p in checked if statuses[p] == SocialStatus.NOT_FOUND]
            ch.has_no_socials = bool(checked) and len(truly_missing) == len(checked)

            if ch.has_no_socials:
                no_socials_count += 1
                ch.opportunity_flag = "TARGET_NO_SOCIALS"
            elif truly_missing:
                ch.opportunity_flag = "PARTIAL_SOCIALS"
            else:
                ch.opportunity_flag = "FULL_SOCIALS"

            if only_no_socials:
                if ch.has_no_socials:
                    final_channels.append(ch)
            else:
                final_channels.append(ch)

        elapsed = round(time.time() - start_time, 2)
        self._emit(
            100,
            f"Agent completed in {elapsed}s. {len(final_channels)} channels displayed ({no_socials_count} missing checked socials).",
        )

        return AgentSearchResult(
            query=query,
            total_searched=total_found,
            channels_matching_filter=len(final_channels),
            execution_time_seconds=elapsed,
            timestamp=datetime.now(timezone.utc).isoformat(),
            channels=final_channels,
            checked_platforms=checked,
        )

    def _take_ai_budget(self) -> bool:
        """Take one AI proposal from the run's budget.

        False when the run has asked the AI enough: the rest of the run
        then works from the creators' own bio links alone.
        """
        if self._ai_proposals >= MAX_AI_PROPOSALS:
            if self._ai_proposals == MAX_AI_PROPOSALS:
                self._log(
                    f"The AI budget for this run is spent ({MAX_AI_PROPOSALS} "
                    "proposals). The rest use their bio links only."
                )
                self._ai_proposals += 1
            return False
        self._ai_proposals += 1
        return True

    def _propose_socials(
        self,
        channels: list[ChannelMetadata],
        check_facebook: bool,
        check_instagram: bool,
        check_tiktok: bool,
    ) -> None:
        """Let the AI name the accounts a channel's own bio does not list.

        Only the platforms the user asked for are proposed, and only where the
        bio is silent: a creator's own link always wins over a model's guess.
        """
        wanted = [
            platform
            for platform, enabled in (
                ("facebook", check_facebook),
                ("instagram", check_instagram),
                ("tiktok", check_tiktok),
            )
            if enabled
        ]
        if not wanted or not judge.any_key():
            return

        total = len(channels)
        for idx, channel in enumerate(channels):
            missing = [
                platform for platform in wanted if not getattr(channel, platform).verified_url
            ]
            if not missing:
                continue
            if not self._take_ai_budget():
                return
            percent = 55 + int((idx / max(total, 1)) * 5)
            self._emit(
                percent,
                f"AI: proposing accounts for {channel.title} ({idx + 1}/{total}) ...",
            )
            try:
                proposal = judge.propose(
                    channel.title,
                    channel.handle or "",
                    channel.subscribers,
                    channel.description,
                    ops=self.ops,
                )
            except judge.JudgeUnavailable as exc:
                self._log(f"  AI step skipped for {channel.title}: {exc}")
                continue

            proposed = judge.candidate_urls(proposal)
            for platform in missing:
                urls = proposed.get(platform) or []
                if not urls:
                    continue
                presence = getattr(channel, platform)
                presence.verified_url = urls[0]
                presence.handle = LinkParserTool.extract_handle_from_url(urls[0])
                presence.source = "model"
                self._log(
                    f"  AI ({proposal.provider}) proposed {platform} "
                    f"{urls[0]} for {channel.title}."
                )

    async def _verify_all_socials(
        self,
        channels: list[ChannelMetadata],
        check_facebook: bool,
        check_instagram: bool,
        check_tiktok: bool = False,
    ) -> list[ChannelMetadata]:
        """Runs async verification probes for list of channels."""
        total = len(channels)
        for idx, ch in enumerate(channels):
            percent = 60 + int((idx / max(total, 1)) * 35)
            self._emit(
                percent,
                f"Probing FB/IG/TikTok for @{ch.handle or ch.title} ({idx + 1}/{total})...",
            )

            candidate_fb = ch.facebook.verified_url if check_facebook else None
            candidate_ig = ch.instagram.verified_url if check_instagram else None
            candidate_tiktok = ch.tiktok.verified_url if check_tiktok else None

            fb_pres, ig_pres, tiktok_pres = await self.verifier_tool.verify_channel_socials(
                candidate_fb=candidate_fb,
                candidate_ig=candidate_ig,
                candidate_tiktok=candidate_tiktok,
                channel_handle=ch.handle,
                candidate_sources={
                    "facebook": ch.facebook.source,
                    "instagram": ch.instagram.source,
                    "tiktok": ch.tiktok.source,
                },
                creator=CreatorRef(
                    title=ch.title,
                    handle=ch.handle or "",
                    url=ch.youtube_url,
                    channel_id=ch.channel_id,
                ),
            )

            if check_facebook:
                ch.facebook = fb_pres
            if check_instagram:
                ch.instagram = ig_pres
            if check_tiktok:
                ch.tiktok = tiktok_pres

            # The second check: the web is asked about the platforms the
            # browser could not confirm.
            self._second_check(
                ch,
                {
                    "facebook": fb_pres if check_facebook else None,
                    "instagram": ig_pres if check_instagram else None,
                    "tiktok": tiktok_pres if check_tiktok else None,
                },
            )

            probed = []
            if check_facebook:
                probed.append(f"Facebook {fb_pres.status.value}")
            if check_instagram:
                probed.append(f"Instagram {ig_pres.status.value}")
            if check_tiktok:
                probed.append(f"TikTok {tiktok_pres.status.value}")
            self._log(f"  {ch.title}: " + ", ".join(probed) + ".")

            # Pacing delay to prevent IP rate-limiting
            await asyncio.sleep(0.5)

        return channels

    def _second_check(
        self,
        channel: ChannelMetadata,
        presences: dict[str, SocialPresence | None],
    ) -> None:
        """Ask the web about the platforms the browser could not confirm.

        The first check is the browser's: it opened the page the creator's
        own bio — or the plain AI's guess — named. Where that page could
        not confirm the account, the web is asked as well: Gemini grounds
        its answer with Google Search, Groq with its browser search. The
        URL the web names is opened in the browser too, and the two
        answers are reconciled into one status.
        """
        wanted = [
            platform
            for platform, presence in presences.items()
            if presence is not None
            and needs_the_second_check(
                confirmed=presence.status is SocialStatus.VERIFIED,
                from_bio=presence.source == "bio_link",
                unreadable=presence.status is SocialStatus.INCONCLUSIVE,
            )
        ]
        if not wanted or not judge.any_key():
            return

        answer = ask_the_web(
            lambda: judge.propose_searched(
                channel.title,
                channel.handle or "",
                channel.subscribers,
                channel.description,
                platforms=tuple(wanted),
                ops=self.ops,
            ),
            budget=self.search_budget,
            platforms=wanted,
            ops=self.ops,
        )
        if answer is None:
            return

        creator = CreatorRef(
            title=channel.title,
            handle=channel.handle or "",
            url=channel.youtube_url,
            channel_id=channel.channel_id,
        )
        for platform in wanted:
            presence = presences[platform]
            item = answer.get(platform)
            ai_exists = item.exists if item is not None else AI_UNKNOWN
            ai_url = item.url if item is not None else ""
            browser = self._browser_verdict(
                ai_exists, ai_url, presence, platform, creator
            )
            result = reconcile(
                ai_exists,
                ai_url,
                browser,
                is_bio_link=presence.source == "bio_link",
            )
            presence.status = RECONCILED_TO_SOCIAL_STATUS[result.status]
            presence.confidence_score = result.confidence
            if ai_url and presence.source != "bio_link":
                presence.verified_url = ai_url
                presence.handle = LinkParserTool.extract_handle_from_url(ai_url)
            self._log(
                f"  {platform}: the AI said {ai_exists}, the browser said "
                f"{browser.verdict.value if browser else 'no page'} — "
                f"{presence.status.value} ({result.confidence})."
            )
            self.ops.ok(
                "reconcile",
                "both",
                platform,
                detail=(
                    f"ai {ai_exists} + browser "
                    f"{browser.verdict.value if browser else 'no page'} -> "
                    f"{presence.status.value}"
                ),
            )

    def _browser_verdict(
        self,
        ai_exists: str,
        ai_url: str,
        presence: SocialPresence,
        platform: str,
        creator: CreatorRef,
    ) -> CheckResult:
        """The browser's answer for one platform.

        The URL the web named is opened when the candidate did not come
        from the creator's own bio: a bio link is the creator's own word,
        and no URL from the web overrules it. Otherwise the URL is opened
        and read like any other candidate.
        """
        if ai_exists == AI_YES and ai_url and presence.source != "bio_link":
            return self.verifier_tool.verify_url(ai_url, platform, creator)
        return CheckResult(
            platform=platform,
            verdict=STATUS_TO_VERDICT.get(presence.status, Verdict.UNKNOWN),
            url=presence.verified_url or "",
            detail=presence.status.value,
        )

    def _suggest_youtube_handle(self, profile: TikTokProfileMetadata) -> str | None:
        """Ask the AI for the creator's YouTube handle.

        Without it a creator who spells their name differently on YouTube is
        flagged as having no channel at all.
        """
        if not judge.any_key():
            return None
        if not self._take_ai_budget():
            return None
        try:
            proposal = judge.propose_youtube(
                profile.nickname,
                profile.handle,
                profile.followers,
                profile.bio,
                ops=self.ops,
            )
        except judge.JudgeUnavailable as exc:
            self._log(f"  AI step skipped for @{profile.handle}: {exc}")
            return None
        handles = proposal.candidates.get("youtube") or []
        if handles:
            self._log(
                f"  AI ({proposal.provider}) proposed YouTube @{handles[0]} "
                f"for @{profile.handle}."
            )
        return handles[0] if handles else None

    def _second_check_youtube(
        self, profile: TikTokProfileMetadata, presence: SocialPresence
    ) -> SocialPresence:
        """Ask the web for the YouTube channel when the first check found none.

        The plain AI was asked for a handle and the YouTube search was
        run. When neither produced a channel, the web is asked with a
        search-grounded model, and the URL it names is opened in the
        browser before it is believed.
        """
        if presence.status in (SocialStatus.VERIFIED, SocialStatus.UNVERIFIED_HANDLE):
            return presence
        if not judge.any_key():
            return presence

        answer = ask_the_web(
            lambda: judge.propose_youtube_searched(
                profile.nickname,
                profile.handle,
                profile.followers,
                profile.bio,
                ops=self.ops,
            ),
            budget=self.search_budget,
            platforms=("youtube",),
            ops=self.ops,
        )
        if answer is None:
            return presence

        item = answer.get("youtube")
        ai_exists = item.exists if item is not None else AI_UNKNOWN
        ai_url = item.url if item is not None else ""
        creator = CreatorRef(
            title=profile.nickname,
            handle=profile.handle,
            url=profile.profile_url,
        )
        if ai_exists == AI_YES and ai_url:
            browser = self.verifier_tool.verify_url(ai_url, "youtube", creator)
        else:
            browser = CheckResult(
                platform="youtube",
                verdict=STATUS_TO_VERDICT.get(presence.status, Verdict.UNKNOWN),
                url=presence.verified_url or "",
                detail=presence.status.value,
            )
        result = reconcile(
            ai_exists,
            ai_url,
            browser,
            is_bio_link=presence.source == "bio_link",
        )
        status, confidence = YOUTUBE_RECONCILED_TO_STATUS[result.status]
        presence.status = status
        presence.confidence_score = confidence
        if ai_url:
            presence.verified_url = ai_url
            presence.handle = LinkParserTool.extract_handle_from_url(ai_url)
            presence.source = "model"
        self._log(
            f"  YouTube: the AI said {ai_exists}, the browser said "
            f"{browser.verdict.value} — {status.value} ({confidence})."
        )
        self.ops.ok(
            "reconcile",
            "both",
            "youtube",
            detail=(
                f"ai {ai_exists} + browser {browser.verdict.value} -> "
                f"{status.value}"
            ),
        )
        return presence

    def run_tiktok_discovery(
        self,
        query: str,
        max_profiles: int = 30,
        only_no_youtube: bool = False,
        cookiefile: str | None = None,
    ) -> TikTokSearchResult:
        """TikTok-first mode: find creators, flag those WITHOUT a YouTube channel."""
        start_time = time.time()
        self._log(
            f"TikTok discovery: {query!r}; backend TikTok search "
            f"(yt-dlp + HTML fallback); cookies {'yes' if cookiefile else 'no'}."
        )
        self._emit(5, f"Initializing TikTok Agent... Searching TikTok for '{query}'...")

        self.tiktok_tool.cookiefile = cookiefile
        self.ops.start("tiktok.search", "tiktok", query, detail=f"up to {max_profiles} profiles")
        started = time.monotonic()
        raw_profiles = self.tiktok_tool.search_profiles(query, max_profiles=max_profiles)
        self.ops.ok(
            "tiktok.search",
            "tiktok",
            query,
            detail=f"{len(raw_profiles)} profile(s)",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        total_found = len(raw_profiles)
        self._emit(35, f"Found {total_found} TikTok profiles. Checking YouTube presence...")

        final_profiles: list[TikTokProfileMetadata] = []
        no_youtube_count = 0

        for idx, profile in enumerate(raw_profiles):
            percent = 35 + int((idx / max(total_found, 1)) * 60)
            self._emit(
                percent,
                f"Checking YouTube presence of @{profile.handle} ({idx + 1}/{total_found})...",
            )

            presence = self.youtube_existence_tool.check_youtube_presence(
                profile,
                suggested_handle=partial(self._suggest_youtube_handle, profile),
            )
            presence = self._second_check_youtube(profile, presence)
            profile.youtube = presence
            profile.has_youtube = presence.status in (
                SocialStatus.VERIFIED,
                SocialStatus.UNVERIFIED_HANDLE,
            )
            self._log(f"  @{profile.handle}: YouTube {presence.status.value}.")

            if profile.has_youtube:
                profile.opportunity_flag = "HAS_YOUTUBE"
            elif presence.status == SocialStatus.INCONCLUSIVE:
                profile.opportunity_flag = "NEEDS_REVIEW"
            else:
                no_youtube_count += 1
                profile.opportunity_flag = "TARGET_NO_YOUTUBE"

            if only_no_youtube:
                if profile.opportunity_flag == "TARGET_NO_YOUTUBE":
                    final_profiles.append(profile)
            else:
                final_profiles.append(profile)

            # Pacing delay between YouTube searches
            time.sleep(0.5)

        elapsed = round(time.time() - start_time, 2)
        if not final_profiles and self.tiktok_tool.search_note:
            self._emit(100, self.tiktok_tool.search_note)
        else:
            self._emit(
                100,
                f"TikTok Agent completed in {elapsed}s. {len(final_profiles)} profiles displayed ({no_youtube_count} without YouTube).",
            )

        return TikTokSearchResult(
            query=query,
            total_searched=total_found,
            profiles_matching_filter=len(final_profiles),
            no_youtube_count=no_youtube_count,
            execution_time_seconds=elapsed,
            timestamp=datetime.now(timezone.utc).isoformat(),
            profiles=final_profiles,
        )
