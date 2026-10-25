"""Agent Orchestrator controller for YouTube discovery and cross-platform social verification."""

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from s_q_ali_media_downloader.agent.schema import (
    AgentSearchResult,
    ChannelMetadata,
    SocialStatus,
    TikTokProfileMetadata,
    TikTokSearchResult,
)
from s_q_ali_media_downloader.agent.tools.metadata_extractor import MetadataExtractorTool
from s_q_ali_media_downloader.agent.tools.social_verifier import SocialVerifierTool
from s_q_ali_media_downloader.agent.tools.tiktok_search import TikTokSearchTool
from s_q_ali_media_downloader.agent.tools.youtube_existence import YouTubeExistenceTool
from s_q_ali_media_downloader.agent.tools.youtube_search import YouTubeSearchTool

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates multi-tool execution DAG for channel discovery & social presence verification.

    Uses a persistent event loop (not asyncio.run()) so it can be called from a QThread
    without nested event loop conflicts.
    """

    def __init__(
        self,
        api_key: str | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ):
        self.search_tool = YouTubeSearchTool(api_key=api_key)
        self.extractor_tool = MetadataExtractorTool()
        self.verifier_tool = SocialVerifierTool()
        self.tiktok_tool = TikTokSearchTool()
        self.youtube_existence_tool = YouTubeExistenceTool(api_key=api_key)
        self.progress_callback = progress_callback
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
            pass

    def _emit(self, percent: int, message: str) -> None:
        if self.progress_callback:
            try:
                self.progress_callback(percent, message)
            except Exception as e:
                logger.warning("Progress callback error: %s", e)

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
        self._emit(5, f"Initializing Agent... Searching YouTube for '{query}'...")

        # 1. YouTube Discovery
        raw_channels = self.search_tool.search_channels(
            query=query, max_results=max_channels, min_subscribers=min_subscribers
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

        # 3. Social Presence Verification
        self._emit(60, "Verifying Facebook, Instagram & TikTok presences...")
        verified_channels = self._loop.run_until_complete(
            self._verify_all_socials(
                enriched_channels, check_facebook, check_instagram, check_tiktok
            )
        )

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
            )

            if check_facebook:
                ch.facebook = fb_pres
            if check_instagram:
                ch.instagram = ig_pres
            if check_tiktok:
                ch.tiktok = tiktok_pres

            # Pacing delay to prevent IP rate-limiting
            await asyncio.sleep(0.5)

        return channels

    def run_tiktok_discovery(
        self,
        query: str,
        max_profiles: int = 30,
        only_no_youtube: bool = False,
        cookiefile: str | None = None,
    ) -> TikTokSearchResult:
        """TikTok-first mode: find creators, flag those WITHOUT a YouTube channel."""
        start_time = time.time()
        self._emit(5, f"Initializing TikTok Agent... Searching TikTok for '{query}'...")

        self.tiktok_tool.cookiefile = cookiefile
        raw_profiles = self.tiktok_tool.search_profiles(query, max_profiles=max_profiles)
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

            presence = self.youtube_existence_tool.check_youtube_presence(profile)
            profile.youtube = presence
            profile.has_youtube = presence.status in (
                SocialStatus.VERIFIED,
                SocialStatus.UNVERIFIED_HANDLE,
            )

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
