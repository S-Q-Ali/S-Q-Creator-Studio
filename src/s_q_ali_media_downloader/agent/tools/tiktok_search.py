"""TikTok Creator Discovery Engine (yt-dlp flat extraction + HTML fallback, zero keys).

Three input modes (checked in order):
1. Seed profiles — @handle tokens or tiktok.com/@handle URLs in the query are
   used directly (always works, no scraping of listings needed).
2. Hashtag pages — '#tag' queries hit https://www.tiktok.com/tag/<tag> via
   yt-dlp (search pages are NOT supported by yt-dlp and TikTok serves empty
   JS shells to anonymous visitors, so tags need cookies to yield data).
3. Keyword search — last resort; subject to the same TikTok restrictions.

All tiers use the app's curl_cffi Chrome impersonation and an optional
cookies.txt file (exported from a logged-in browser) to unlock listing data.
"""

import logging
import re

import yt_dlp

from s_q_ali_media_downloader.agent.schema import TikTokProfileMetadata

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.tiktok.com/search?q={query}"
TAG_URL = "https://www.tiktok.com/tag/{tag}"
PROFILE_URL = "https://www.tiktok.com/@{handle}"

# Handles harvested from embedded JSON (works even without yt-dlp).
UNIQUE_ID_PATTERN = re.compile(r'"uniqueId"\s*:\s*"([A-Za-z0-9\._]{2,30})"')
AT_HANDLE_PATTERN = re.compile(r"tiktok\.com/@([A-Za-z0-9\._]{2,30})/")

# Seed profiles: @handle tokens or full profile URLs typed by the user.
SEED_URL_PATTERN = re.compile(r"tiktok\.com/@([A-Za-z0-9\._]{2,30})")
SEED_AT_PATTERN = re.compile(r"(?<![\w@])@([A-Za-z0-9\._]{2,30})")

# Non-profile handles that appear in embedded payloads.
EXCLUDED_HANDLES = {
    "tiktok",
    "foryou",
    "following",
    "explore",
    "live",
    "upload",
    "login",
    "signup",
    "discover",
}


def format_followers(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


class TikTokSearchTool:
    """Discovers TikTok creator profiles by niche keyword, tag, or name."""

    def __init__(self, timeout: float = 20.0, cookiefile: str | None = None):
        self.timeout = timeout
        self.cookiefile = cookiefile

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search_profiles(self, query: str, max_profiles: int = 50) -> list[TikTokProfileMetadata]:
        """Entry point: seed profiles > tag pages > keyword search."""
        seeds = self._parse_seed_handles(query)
        if seeds:
            logger.info(f"Query contains {len(seeds)} seed profile(s); skipping discovery.")
            return self._build_profiles(seeds, max_profiles)

        handles: list[str] = []
        tags = [t.lstrip("#").strip(".").lower() for t in query.split() if t.startswith("#")]
        keywords = " ".join(w for w in query.split() if not w.startswith("#")).strip()

        # 2. Tag pages (yt-dlp supports /tag/<tag>, not /search?q=...)
        for tag in tags:
            handles += self._discover_via_ytdlp(TAG_URL.format(tag=tag))
            if not handles:
                handles += self._discover_via_html(TAG_URL.format(tag=tag))
            if len(handles) >= max_profiles:
                break

        # 3. Keyword search (subject to TikTok's anonymous-access restrictions)
        if not handles:
            base = keywords or query
            handles = self._discover_via_ytdlp(SEARCH_URL.format(query=base))
            if not handles:
                logger.info("yt-dlp TikTok search empty; trying HTML harvest fallback...")
                handles = self._discover_via_html(SEARCH_URL.format(query=base))
            if not handles and tags:
                logger.warning(
                    "No results. TikTok blocks anonymous listing access; "
                    "provide a cookies.txt file (exported from a logged-in browser) "
                    "or paste profile URLs / @handles instead."
                )

        # Dedupe, filter, cap
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

        # Enrich each profile with bio / follower data (best effort)
        for idx, profile in enumerate(profiles):
            try:
                self.enrich_profile(profile)
            except Exception as e:
                logger.warning(f"TikTok profile enrichment failed for @{profile.handle}: {e}")

        return profiles

    # ------------------------------------------------------------------
    # Tier 1: yt-dlp
    # ------------------------------------------------------------------
    def _ydl_opts(self, flat: bool = True) -> dict:
        """Common yt-dlp options: impersonation + optional cookies file."""
        from s_q_ali_media_downloader.engine import impersonate_target

        opts: dict = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "socket_timeout": self.timeout,
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

    def _build_profiles(self, handles: list[str], max_profiles: int) -> list[TikTokProfileMetadata]:
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
        return profiles

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
    # Tier 2: HTML harvest
    # ------------------------------------------------------------------
    def _discover_via_html(self, url: str) -> list[str]:
        """Scrapes uniqueId / @handle tokens from a TikTok listing page HTML."""
        import httpx

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            with httpx.Client(
                timeout=self.timeout, follow_redirects=True, headers=headers
            ) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return []
                html = resp.text
        except Exception as e:
            logger.warning(f"TikTok HTML harvest failed: {e}")
            return []

        handles = UNIQUE_ID_PATTERN.findall(html)
        handles += AT_HANDLE_PATTERN.findall(html)
        return handles

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
