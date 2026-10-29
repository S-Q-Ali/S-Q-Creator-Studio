"""Tool for extracting Facebook, Instagram, TikTok, and YouTube URLs and handles from text/URLs."""

import re
from typing import ClassVar


class LinkParserTool:
    """Extracts social URLs and handles from channel metadata, descriptions, and link lists."""

    # FB Regex patterns
    FB_URL_PATTERN = re.compile(
        r"https?://(?:[\w\-]+\.)*(?:facebook\.com|fb\.com|fb\.watch)/(?:pages/[^/\s\"']+/(\d+)|groups/[^/\s\"']+|people/[^/\s\"']+/\d+|profile\.php\?id=\d+|[A-Za-z0-9\._\-]+)/?",
        re.IGNORECASE,
    )
    FB_PROFILE_ID_PATTERN = re.compile(
        r"(?:facebook|fb)\.com/profile\.php\?id=(\d+)",
        re.IGNORECASE,
    )

    # IG Regex patterns
    IG_URL_PATTERN = re.compile(
        r"https?://(?:www\.)?(?:instagram\.com|instagr\.am)/([A-Za-z0-9\._\-]+)/?",
        re.IGNORECASE,
    )
    # Word-boundary anchored so "config: myname" / "navigation:" cannot match,
    # and needing an explicit marker (@ or :) so a plain word after the name is
    # not read as a handle: "When Will Instagram Pay their Creators?" is a
    # video title, not an account.
    IG_TEXT_HANDLE_PATTERN = re.compile(
        r"\b(?:ig|instagram|insta)\b\s*[:@]\s*@?([A-Za-z0-9][A-Za-z0-9\._]{2,29})",
        re.IGNORECASE,
    )

    # TikTok pattern (profiles only: tiktok.com/@handle)
    TIKTOK_URL_PATTERN = re.compile(
        r"https?://(?:www\.|m\.)?tiktok\.com/@([A-Za-z0-9\._]{2,30})/?",
        re.IGNORECASE,
    )
    # Same marker rule as Instagram: "TikTok Pay" is not a handle.
    TIKTOK_TEXT_HANDLE_PATTERN = re.compile(
        r"\btiktok\b\s*[:@]\s*@?([A-Za-z0-9\._]{2,30})",
        re.IGNORECASE,
    )

    # Excluded common non-profile path segments for Facebook and Instagram
    EXCLUDED_SEGMENTS: ClassVar[set[str]] = {
        "sharer",
        "share",
        "dialog",
        "intent",
        "p",
        "reel",
        "reels",
        "stories",
        "explore",
        "direct",
        "tv",
        "developer",
        "legal",
        "about",
        "privacy",
        "help",
        "terms",
        "accounts",
        "graphql",
        "api",
        "watch",
        "hashtag",
        "login",
        "signup",
        "policy",
        "support",
        "business",
        "events",
        "marketplace",
        "gaming",
        "jobs",
    }

    @classmethod
    def extract_social_links(
        r,
        text: str,
        links: list[str] | None = None,
        *,
        creator_text: bool = True,
    ) -> tuple[str | None, str | None, str | None]:
        """Extracts primary (facebook_url, instagram_url, tiktok_url) from raw text and links.

        Facebook matches are priority-ranked: vanity page > profile.php > people/ >
        pages/ > groups/, so a group link never shadows the creator's actual page.

        ``creator_text`` says whether ``text`` is the creator's own words. A
        channel page is not: its video titles say "Instagram Pay", and that is
        a title, not an account. A URL is a URL wherever it is found, so the
        URL patterns always run.
        """
        fb_url = None
        ig_url = None
        tiktok_url = None

        all_input = text + " " + " ".join(links or [])

        # ---- TikTok (profile URLs only, @handle form) ----
        for handle in r.TIKTOK_URL_PATTERN.findall(all_input):
            handle = handle.strip(".")
            if handle.lower() not in r.EXCLUDED_SEGMENTS and len(handle) >= 2:
                tiktok_url = f"https://www.tiktok.com/@{handle}/"
                break
        if not tiktok_url and creator_text:
            tiktok_text_match = r.TIKTOK_TEXT_HANDLE_PATTERN.search(text)
            if tiktok_text_match:
                handle = tiktok_text_match.group(1).strip().strip(".")
                if (
                    handle.lower() not in r.EXCLUDED_SEGMENTS
                    and not handle.lower().startswith("http")
                    and len(handle) >= 2
                ):
                    tiktok_url = f"https://www.tiktok.com/@{handle}/"

        # ---- Facebook (ranked) ----
        fb_candidates: list[tuple[int, str]] = []
        for match in r.FB_URL_PATTERN.finditer(all_input):
            clean_url = r._clean_url(match.group(0))
            if clean_url and r._is_valid_fb_url(clean_url):
                fb_candidates.append((r._fb_url_priority(clean_url), clean_url))
        if fb_candidates:
            fb_candidates.sort(key=lambda pair: pair[0])
            fb_url = fb_candidates[0][1]

        # ---- Instagram (explicit URLs) ----
        for match in r.IG_URL_PATTERN.finditer(all_input):
            handle = match.group(1).strip(".")
            if handle.lower() not in r.EXCLUDED_SEGMENTS and len(handle) >= 3:
                ig_url = f"https://www.instagram.com/{handle}/"
                break

        # 2. Text handle fallback for IG (e.g. "Follow on IG: @myhandle")
        if not ig_url and creator_text:
            ig_text_match = r.IG_TEXT_HANDLE_PATTERN.search(text)
            if ig_text_match:
                handle = ig_text_match.group(1).strip().strip(".")
                if (
                    handle.lower() not in r.EXCLUDED_SEGMENTS
                    and not handle.lower().startswith("http")
                    and len(handle) >= 3
                ):
                    ig_url = f"https://www.instagram.com/{handle}/"

        return fb_url, ig_url, tiktok_url

    @classmethod
    def extract_handle_from_url(r, url: str) -> str | None:
        """Extracts handle string from a FB/IG/TikTok URL."""
        if not url:
            return None

        # Numeric FB profile (profile.php?id=123) — keep the numeric id.
        profile_match = r.FB_PROFILE_ID_PATTERN.search(url)
        if profile_match:
            return profile_match.group(1)

        clean = url.rstrip("/")
        parts = clean.split("/")
        if parts:
            last = parts[-1]
            if "?" in last:
                last = last.split("?")[0]
            last = last.removeprefix("@")
            if last.lower() not in r.EXCLUDED_SEGMENTS and len(last) >= 2:
                return last
        return None

    @classmethod
    def _clean_url(r, url: str) -> str:
        """Strips tracking params but preserves profile.php?id= payloads."""
        url = url.strip().rstrip("/")
        if "profile.php?id=" in url.lower():
            match = r.FB_PROFILE_ID_PATTERN.search(url)
            if match:
                return f"https://www.facebook.com/profile.php?id={match.group(1)}"
        if "?" in url:
            url = url.split("?")[0]
        return url + "/"

    @classmethod
    def _fb_url_priority(r, url: str) -> int:
        """Lower = higher priority. Vanity pages first, groups last."""
        lowered = url.lower()
        if "/groups/" in lowered:
            return 9
        if "/pages/" in lowered:
            return 2
        if "/people/" in lowered:
            return 1
        if "profile.php?id=" in lowered:
            return 2
        return 0  # vanity /username — strongest signal

    @classmethod
    def _is_valid_fb_url(r, url: str) -> bool:
        handle = r.extract_handle_from_url(url)
        if not handle:
            return False
        return handle.lower() not in r.EXCLUDED_SEGMENTS and len(handle) >= 3
