"""TikTok Creator Discovery Engine (yt-dlp flat extraction, zero keys).

Two input modes (checked in order):
1. Seed profiles — @handle tokens or tiktok.com/@handle URLs in the query are
   used directly (always works, no listing needed).
2. Hashtag / keyword pages — best effort. Measured 2026-10-30, TikTok serves
   an empty JS shell and an empty signed API even with a logged-in
   cookies.txt, so this tier normally returns nothing and the note asks for
   the creators' own handles.
"""

import logging
import re

import yt_dlp

from s_q_ali_media_downloader.agent.schema import TikTokProfileMetadata
from s_q_ali_media_downloader.agent.tools.tiktok_api import EXCLUDED_HANDLES, TikTokApiSession
from s_q_ali_media_downloader.core.format import format_count

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.tiktok.com/search?q={query}"
TAG_URL = "https://www.tiktok.com/tag/{tag}"
PROFILE_URL = "https://www.tiktok.com/@{handle}"

# Seed profiles: @handle tokens or full profile URLs typed by the user.
SEED_URL_PATTERN = re.compile(r"tiktok\.com/@([A-Za-z0-9\._]{2,30})")
SEED_AT_PATTERN = re.compile(r"(?<![\w@])@([A-Za-z0-9\._]{2,30})")


def format_followers(count: int) -> str:
    return format_count(count)


class TikTokSearchTool:
    """Discovers TikTok creator profiles by niche keyword, tag, or name."""

    def __init__(self, timeout: float = 20.0, cookiefile: str | None = None):
        self.timeout = timeout
        self.api_session = TikTokApiSession(timeout=timeout)
        self._cookiefile: str | None = None
        self.search_note: str | None = None
        #: Where the last result's handles came from: seed, listing, or none.
        self.discovered_by = ""
        self.cookie_count = 0
        if cookiefile:
            self.cookiefile = cookiefile

    @property
    def cookiefile(self) -> str | None:
        """Path to the Netscape cookies.txt in use (or None)."""
        return self._cookiefile

    @cookiefile.setter
    def cookiefile(self, value: str | None) -> None:
        """(Re)builds the API session so signed listings carry the cookies."""
        self._cookiefile = value
        self.api_session = TikTokApiSession(cookiefile=value, timeout=self.timeout)
        self.cookie_count = self.api_session.cookie_count

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search_profiles(self, query: str, max_profiles: int = 50) -> list[TikTokProfileMetadata]:
        """Entry point: seed profiles > tag pages > keyword search.

        TikTok blocks listing for an anonymous visitor, and measured
        2026-10-30 it blocks it for a logged-in one too. The listing tiers
        stay as a best effort; when they all come back empty the note asks
        for the creators' own @handles, which always work.
        """
        self.search_note = None
        self.discovered_by = ""
        seeds = self._parse_seed_handles(query)
        if seeds:
            logger.info(f"Query contains {len(seeds)} seed profile(s); skipping discovery.")
            self.discovered_by = "seed"
            return self._finalize_profiles(seeds, max_profiles)

        tags, keywords = self._parse_query(query)
        handles: list[str] = []

        for tag in tags:
            handles += self.api_session.fetch_tag_handles(tag, limit=max_profiles)
            if len(handles) >= max_profiles:
                break
            handles += self._discover_via_ytdlp(TAG_URL.format(tag=tag))
            if len(handles) >= max_profiles:
                break

        if not handles:
            base = keywords or " ".join(tags)
            handles += self.api_session.fetch_search_handles(base, limit=max_profiles)
            if not handles:
                handles += self._discover_via_ytdlp(SEARCH_URL.format(query=base))

        if handles:
            self.discovered_by = "listing"
        else:
            self.search_note = self._build_no_results_note(tags)
            logger.warning(self.search_note)

        return self._finalize_profiles(handles, max_profiles)

    # ------------------------------------------------------------------
    # Tier 1: yt-dlp
    # ------------------------------------------------------------------
    def _ydl_opts(self, flat: bool = True) -> dict:
        """Common yt-dlp options: impersonation + optional cookies file."""
        from s_q_ali_media_downloader.engine import impersonate_target, js_runtime_opts

        opts: dict = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "socket_timeout": self.timeout,
            "js_runtimes": js_runtime_opts(),
        }
        if flat:
            opts["extract_flat"] = True
        target, _label = impersonate_target()
        if target is not None:
            opts["impersonate"] = target
        if self.cookiefile:
            opts["cookiefile"] = self.cookiefile
        return opts

    @staticmethod
    def _parse_seed_handles(query: str) -> list[str]:
        """Extracts @handles / profile URLs typed directly into the query."""
        seeds = SEED_URL_PATTERN.findall(query)
        seeds += SEED_AT_PATTERN.findall(query)
        out, seen = [], set()
        for handle in seeds:
            handle = handle.strip(".").lower()
            if handle in seen or handle in EXCLUDED_HANDLES or len(handle) < 2:
                continue
            seen.add(handle)
            out.append(handle)
        return out

    @staticmethod
    def _parse_query(query: str) -> tuple[list[str], str]:
        """Splits a comma/newline query into tags and keyword phrases.

        A ``#word`` is a tag; so is a bare single word (``ishowspeedlive``),
        because that is how a hashtag is typed. A segment with spaces stays a
        keyword phrase, so ``IShowSpeed edits, ishowspeedlive`` searches the
        tag and keeps the phrase for the keyword leg.
        """
        tags: list[str] = []
        keywords: list[str] = []
        for raw in re.split(r"[,\n]+", query):
            segment = raw.strip()
            if not segment:
                continue
            if segment.startswith("#"):
                tag = segment.lstrip("#").strip(".").lower()
                if tag:
                    tags.append(tag)
            elif len(segment.split()) == 1:
                tag = segment.strip(".").lower()
                if tag:
                    tags.append(tag)
            else:
                keywords.append(segment)
        return list(dict.fromkeys(tags)), " ".join(keywords)

    def _finalize_profiles(
        self, handles: list[str], max_profiles: int
    ) -> list[TikTokProfileMetadata]:
        """Dedupes handles into profiles and enriches them (best effort)."""
        seen: set[str] = set()
        profiles: list[TikTokProfileMetadata] = []
        for handle in handles:
            handle = handle.strip(".").lower()
            if handle in seen or handle in EXCLUDED_HANDLES or len(handle) < 2:
                continue
            seen.add(handle)
            profiles.append(
                TikTokProfileMetadata(
                    profile_id=handle,
                    handle=handle,
                    profile_url=PROFILE_URL.format(handle=handle),
                )
            )
            if len(profiles) >= max_profiles:
                break

        for profile in profiles:
            try:
                self.enrich_profile(profile)
            except Exception as e:
                logger.warning(f"TikTok profile enrichment failed for @{profile.handle}: {e}")
            if profile.nickname == "TikTok Creator":
                # A walled profile read leaves the default; the handle is
                # the only true name we have.
                profile.nickname = profile.handle
        return profiles

    def _build_no_results_note(self, tags: list[str]) -> str:
        note = (
            "TikTok returned 0 profiles. TikTok blocks #tag and search listing "
            "even with a logged-in cookies.txt; the signed listing API was empty too."
        )
        if not self.cookiefile:
            note += " No cookies.txt was provided."
        elif self.cookie_count:
            note += (
                f" A cookies.txt with {self.cookie_count} cookies was used but the "
                "listing stayed blocked."
            )
        else:
            note += " A cookies.txt path was set but it failed to load (0 cookies)."
        note += (
            " Paste the creators' @handles or profile URLs; each one is then "
            "checked on YouTube, Instagram and Facebook."
        )
        return note

    def _discover_via_ytdlp(self, url: str) -> list[str]:
        """Flat-extracts a TikTok listing URL, collecting uploader handles."""
        handles: list[str] = []

        with yt_dlp.YoutubeDL(self._ydl_opts(flat=True)) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                logger.warning(f"yt-dlp TikTok search failed: {e}")
                return handles

            entries = (info or {}).get("entries") or []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                handle = self._handle_from_entry(entry)
                if handle:
                    handles.append(handle)

        return handles

    @staticmethod
    def _handle_from_entry(entry: dict) -> str | None:
        """Pulls the creator handle out of a flat TikTok video entry."""
        url = str(entry.get("webpage_url") or entry.get("url") or "")
        match = re.search(r"tiktok\.com/@([A-Za-z0-9\._]{2,30})", url)
        if match:
            return match.group(1)

        uploader = str(entry.get("uploader") or entry.get("creator") or "")
        uploader = uploader.lstrip("@").replace(" ", "")
        if re.fullmatch(r"[A-Za-z0-9\._]{2,30}", uploader):
            return uploader
        return None

    # ------------------------------------------------------------------
    # Profile enrichment
    # ------------------------------------------------------------------
    def enrich_profile(self, profile: TikTokProfileMetadata) -> TikTokProfileMetadata:
        """Best-effort enrichment of bio, follower count, and video count."""
        opts = self._ydl_opts(flat=False)
        opts["playlist_items"] = "1-5"
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(profile.profile_url, download=False)
        if not info or not isinstance(info, dict):
            return profile

        profile.nickname = info.get("uploader") or info.get("channel") or profile.nickname
        bio = info.get("description") or ""
        if bio:
            profile.bio = str(bio)[:500]
        count = info.get("channel_follower_count")
        if isinstance(count, int):
            profile.followers = count
            profile.followers_formatted = format_followers(count)
        entries = info.get("entries") or []
        if entries:
            profile.video_count = max(profile.video_count, len(entries))
        return profile
