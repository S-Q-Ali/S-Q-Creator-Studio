"""Download engine for S-Q Creator Studio.

Work is handed to a small pool of worker threads — two by default, one
when there is only a single link. Each worker pulls the next link off a
shared list, so the order of completion varies but nothing is downloaded
twice.

Retry model:

1. Each video gets one attempt plus three more on the spot, 2-5 seconds
   apart.
2. Still failing, it is marked Waiting and the worker moves on.
3. End passes are off by default. Set 1-6 and the run sweeps the Waiting
   list that many more times once the main sequence is done.

Errors that can never succeed — deleted, private, region-blocked — skip
the retries and fail immediately.
"""

import logging
import os
import random
import re
import threading
import time
import unicodedata

import yt_dlp
from PySide6.QtCore import QStandardPaths, QThread, Signal

from s_q_ali_media_downloader.core import reframe, shorts
from s_q_ali_media_downloader.core.facebook_client import (
    FacebookError,
    list_page_videos,
)
from s_q_ali_media_downloader.core.facebook_client import (
    normalize_page as normalize_facebook_page,
)
from s_q_ali_media_downloader.core.instagram_client import (
    InstagramError,
    list_profile_media,
)
from s_q_ali_media_downloader.core.instagram_client import (
    normalize_profile as normalize_instagram_profile,
)

logger = logging.getLogger(__name__)

try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
except ImportError:
    ImpersonateTarget = None

APP_NAME = "S-Q-Ali Media Downloader"
APP_TITLE = "S-Q Creator Studio"
MAX_FILENAME_LENGTH = 150
TEMP_PREFIX = "__amd_"

INLINE_RETRIES = 3
INLINE_RETRY_WAIT = (2.0, 5.0)
PASS_COOLDOWN = (20.0, 35.0)
WORKER_STAGGER = 1.5

PARALLEL_OPTIONS = {
    "1 · sequential": 1,
    "2 · parallel": 2,
    "3 · parallel": 3,
}
DEFAULT_PARALLEL = "2 · parallel"

DELAY_PRESETS = {
    "Fast · 2-5s": (2.0, 5.0),
    "Normal · 4-9s": (4.0, 9.0),
    "Safe · 8-15s": (8.0, 15.0),
}
DEFAULT_DELAY = "Normal · 4-9s"

RETRY_PASSES = {
    "Off": 0,
    "1 pass": 1,
    "2 passes": 2,
    "3 passes": 3,
    "4 passes": 4,
    "5 passes": 5,
    "6 passes": 6,
}
DEFAULT_PASSES = "1 pass"

QUALITY_OPTIONS = {
    # The first entry is what a fresh install downloads at: the best the
    # source offers, up to 4K. "Best available" is the no-cap choice, for
    # the 8K streams that exist.
    "Best up to 4K": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "Best available": "bestvideo+bestaudio/best",
    "2K · 1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "Audio only": "bestaudio/best",
}
DEFAULT_QUALITY = "Best up to 4K"

#: The modes of the "Split into shorts" dropdown. Off and Auto have no
#: length of their own; the fixed lengths come from the split module; the
#: last one is where the user says how many clips and the app works out
#: what each one will be.
SPLIT_OFF = "Off"
SPLIT_AUTO = "Auto"
SPLIT_CLIPS = "N clips"
SPLIT_OPTIONS = (SPLIT_OFF, SPLIT_AUTO, *shorts.TARGETS, SPLIT_CLIPS)
DEFAULT_SPLIT = SPLIT_OFF
DEFAULT_CLIPS = 6

#: The video codecs that do not belong in an MP4. YouTube's 4K streams are
#: VP9 and AV1, and a file that carries them under an .mp4 name is refused by
#: half the players out there.
MKV_CODECS = ("vp8", "vp9", "vp09", "av01", "av1")

#: What each codec is called on the card.
CODEC_LABELS = {
    "avc1": "H.264",
    "avc3": "H.264",
    "h264": "H.264",
    "vp8": "VP8",
    "vp9": "VP9",
    "vp09": "VP9",
    "av01": "AV1",
    "av1": "AV1",
    "hev1": "HEVC",
    "hvc1": "HEVC",
}


def merge_container_for(vcodec):
    """The container a codec belongs in: MKV for VP9/AV1, MP4 for the rest.

    yt-dlp merges whatever `merge_output_format` allows into, and it falls
    back to that extension even when the codecs do not fit - so a 4K VP9
    stream muxed with Opus audio would land in an MP4 that many players
    refuse to open.
    """
    codec = (vcodec or "").split(".")[0].lower()
    return "mkv" if codec.startswith(MKV_CODECS) else "mp4"


def codec_aware_format_selector(spec, get_ydl):
    """A yt-dlp format callable that picks the container from the codec.

    `merge_output_format` is one fixed preference list, and MKV is
    compatible with every codec, so no format string can say "MKV for
    VP9/AV1, MP4 otherwise". The callable selects once to learn the video
    codec, sets the container that codec needs, and selects again - so
    yt-dlp's own merge code builds the file with the right one.
    """

    def selector(ctx):
        ydl = get_ydl()
        chosen = list(ydl.build_format_selector(spec)(ctx))
        if not chosen:
            return []
        ydl.params["merge_output_format"] = merge_container_for(chosen[0].get("vcodec"))
        return list(ydl.build_format_selector(spec)(ctx))

    return selector


def quality_label(height, vcodec):
    """What the card shows about the stream: `2160p · VP9`."""
    if not height or not vcodec or vcodec == "none":
        return ""
    codec = str(vcodec).split(".")[0].lower()
    return f"{int(height)}p · {CODEC_LABELS.get(codec, codec.upper())}"

MUSIC_FORMATS = {
    "FLAC · lossless container": "flac",
    "MP3 · 320 kbps": "mp3",
    "M4A · original AAC": "m4a",
    "Opus · smallest": "opus",
    "WAV · uncompressed": "wav",
}
DEFAULT_MUSIC_FORMAT = "FLAC · lossless container"

# Derive MAX_ACCOUNT_VIDEOS from ACCOUNT_LIMITS so changing the UI list
# automatically updates the cap.
ACCOUNT_LIMITS = [20, 40, 60, 80, 100, 120, 140, 160, 180, 200]
MAX_ACCOUNT_VIDEOS = max(ACCOUNT_LIMITS)

# YouTube's default player client ("web") needs a PO token that only a real
# browser can mint, so a single-video download from most non-residential IPs
# dies with "Sign in to confirm you're not a bot". The embedded and mobile-web
# clients answer without one, so they are tried first; "web" stays last as the
# fallback that works when browser cookies are supplied.
YOUTUBE_PLAYER_CLIENTS = ("web_embedded", "mweb", "web")

NON_MEDIA_HINTS = (
    "/tiktokstudio",
    "/upload",
    "/login",
    "/signup",
    "/settings",
    "/creator-center",
    "/business-suite",
    "/analytics",
    "/explore",
    "/foryou",
    "/following",
)

_IMPERSONATE_CACHE = None

PERMANENT_SIGNS = (
    "unavailable",
    "not found",
    "does not exist",
    "deleted",
    "private",
    "removed",
    "no longer",
    "account",
    "region",
    "copyright",
    "this format needs ffmpeg",
)


def _target_version(target):
    raw = str(getattr(target, "version", "") or "")
    match = re.match(r"(\d+)", raw)
    if match:
        return int(match.group(1))
    return -1


def js_runtime_opts():
    """yt-dlp 2026.x runs YouTube/TikTok web-extraction challenges through a
    JavaScript runtime (EJS) and enables only deno by default. Without a
    runtime YouTube downloads hit bot checks and TikTok profile fetches fail
    with "Unable to extract secondary user ID". Enabling every supported
    runtime lets yt-dlp use whichever one is installed."""
    return {"deno": {}, "node": {}, "bun": {}, "quickjs": {}}


def impersonate_target():
    global _IMPERSONATE_CACHE
    if _IMPERSONATE_CACHE is not None:
        return _IMPERSONATE_CACHE

    result = (None, "unavailable — curl_cffi missing")
    if ImpersonateTarget is None:
        _impersonate_warn(result[1])
        _IMPERSONATE_CACHE = result
        return result

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as probe:
            raw = probe._get_available_impersonate_targets()
        targets = []
        for entry in raw or []:
            targets.append(entry[0] if isinstance(entry, (tuple, list)) else entry)
        chrome = [t for t in targets if str(getattr(t, "client", "")).lower() == "chrome"]
        chrome.sort(key=_target_version, reverse=True)
        best = chrome[0] if chrome else (targets[0] if targets else None)
        if best is not None:
            result = (best, str(best))
        else:
            result = (None, "unavailable — no impersonate targets")
    except Exception as exc:
        result = (None, f"unavailable ({exc})")
    if result[0] is None:
        _impersonate_warn(result[1])
    _IMPERSONATE_CACHE = result
    return result


def _impersonate_warn(label: str) -> None:
    logger.warning("Browser impersonation %s — TikTok downloads will rely on fallbacks.", label)


def impersonation_summary():
    target, label = impersonate_target()
    return (target is not None, label)


def app_storage_dir():
    """Where the app keeps its data: the queue, the settings, the downloads.

    One place decides this, so the folders cannot drift apart. Windows reads
    LOCALAPPDATA, which is also where Qt sends the generic data location, so
    its path is unchanged; Linux and macOS get their own data folder instead
    of the app name dropped into the home directory.
    """
    base = (
        os.environ.get("LOCALAPPDATA")
        or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
        or os.path.expanduser("~")
    )
    return os.path.join(base, APP_NAME, "storage")


def migrate_legacy_storage_dir():
    """Move the data folder an early POSIX run left in the home directory.

    With no LOCALAPPDATA, Linux and macOS used to fall back to
    ``~/S-Q-Ali Media Downloader/storage``, and the API keys are in it. Run
    once at startup, before anything opens a file.
    """
    legacy = os.path.join(os.path.expanduser("~"), APP_NAME, "storage")
    target = app_storage_dir()
    if not os.path.isdir(legacy) or os.path.exists(target):
        return
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.replace(legacy, target)
        logger.info("Moved the app data folder to %s", target)
    except OSError:
        # A folder in use or on another volume: the app starts on an empty
        # store and the user's own folder is left untouched.
        logger.warning("Could not move the app data folder to %s", target, exc_info=True)


def default_output_dir():
    return os.path.join(app_storage_dir(), "downloads")


def is_tiktok_url(url):
    low = url.strip().lower()
    if not low.startswith(("http://", "https://")):
        return False
    if not re.search(r"(^|[./])tiktok\.com", low):
        return False
    if any(hint in low for hint in NON_MEDIA_HINTS):
        return False
    if re.search(r"(vm|vt)\.tiktok\.com/", low):
        return True
    # A page URL carries the numeric video/photo id. TikTok's CDN media URLs
    # also contain "/video/" but the id segment is a token, and those links
    # answer HTTP 403 when downloaded, so they must not be queued.
    return re.search(r"/(?:video|photo)/\d+", low) is not None


def tiktok_page_url(entry, username):
    """Stable page URL for a TikTok profile entry.

    Profile entries carry a signed CDN media URL in "url" — those return
    HTTP 403 when downloaded. The page URL ("webpage_url", or rebuilt from
    the numeric video id) is what the downloader must queue.
    """
    page = str(entry.get("webpage_url") or "")
    if re.search(r"tiktok\.com/@[^/]+/(?:video|photo)/\d+", page):
        return page
    video_id = str(entry.get("id") or "")
    if video_id.isdigit():
        kind = "photo" if "/photo/" in page else "video"
        return f"https://www.tiktok.com/@{username}/{kind}/{video_id}"
    return ""


def is_profile_url(url):
    low = url.strip().lower()
    return ("tiktok.com/@" in low) and ("/video/" not in low) and ("/photo/" not in low)


def is_facebook_url(url):
    """A single Facebook video, reel or share link — not a profile or group."""
    low = url.strip().lower()
    if not low.startswith(("http://", "https://")):
        return False
    if re.search(r"(^|[./])fb\.watch/", low):
        return True
    if not re.search(r"(^|[./])facebook\.com", low):
        return False
    if re.search(r"facebook\.com/watch/?\?(?:[^#]*&)?v=\d+", low):
        return True
    if re.search(r"facebook\.com/(?:[^/]+/)?videos/(?:[^/]+/)?\d+", low):
        return True
    if re.search(r"facebook\.com/reel/\d+", low):
        return True
    return re.search(r"facebook\.com/share/[vr]/[a-z0-9_-]+", low) is not None


def is_instagram_url(url):
    """A single Instagram post, reel or IGTV video — not a profile or story."""
    low = url.strip().lower()
    if not low.startswith(("http://", "https://")):
        return False
    if not re.search(r"(^|[./])instagram\.com", low):
        return False
    return re.search(r"instagram\.com/(?:p|reel|reels|tv)/[a-z0-9_-]+", low) is not None


def is_instagram_profile_url(url):
    """An Instagram profile — the page whose posts get expanded."""
    if not (url or "").strip().lower().startswith(("http://", "https://")):
        return False
    name, _ = normalize_instagram_profile(url)
    return name is not None


def is_facebook_page_url(url):
    """A Facebook page — the page whose videos get expanded."""
    if not (url or "").strip().lower().startswith(("http://", "https://")):
        return False
    name, _ = normalize_facebook_page(url)
    return name is not None


def is_youtube_url(url):
    """Check if a URL is a YouTube video URL.

    Note: This is duplicated in youtube_client.py for import flexibility.
    Keep them in sync when updating the pattern.
    """
    low = url.strip().lower()
    if not low.startswith(("http://", "https://")):
        return False
    if re.search(r"(^|[./])youtu\.be/", low):
        return True
    if not re.search(r"(^|[./])youtube\.com", low):
        return False
    return re.search(r"/(watch\?|shorts/|live/|v/|embed/)", low) is not None


def is_youtube_playlist_url(url):
    low = url.strip().lower()
    if not low.startswith(("http://", "https://")):
        return False
    return re.search(r"(^|[./])youtube\.com", low) is not None and (
        "/playlist?" in low or "list=" in low
    )


def is_youtube_channel_url(url):
    low = url.strip().lower()
    if not low.startswith(("http://", "https://")):
        return False
    if not re.search(r"(^|[./])youtube\.com", low):
        return False
    if ("/@" in low) or ("/channel/" in low) or ("/c/" in low) or ("/user/" in low):
        return True
    # Support shorthand youtube.com/UC... channel ID format
    return re.search(r"youtube\.com/uc[a-z0-9_\-]{22}", low) is not None


def _is_video_id(value) -> bool:
    """A YouTube video id is exactly eleven characters.

    A channel id is twenty-four, and that is what a channel's tab entries
    carry — so this tells a video from a tab.
    """
    return isinstance(value, str) and len(value) == 11


def normalize_youtube_channel_url(url):
    """Ensures youtube.com/UC... shorthand URLs are normalized to youtube.com/channel/UC..."""
    url = url.strip()
    match = re.search(
        r"https?://(?:www\.)?youtube\.com/(UC[A-Za-z0-9_\-]{22})/?$", url, re.IGNORECASE
    )
    if match:
        return f"https://www.youtube.com/channel/{match.group(1)}"
    return url


def clean_youtube_channel_base(url: str) -> str:
    """Strips subpaths like /shorts, /videos, /featured, /streams from a channel URL."""
    url = normalize_youtube_channel_url(url.strip())
    return re.sub(
        r"/(shorts|videos|featured|streams|community|podcasts)/?$",
        "",
        url.rstrip("/"),
        flags=re.IGNORECASE,
    )


def platform_of(url):
    low = url.strip().lower()
    if re.search(r"(^|[./])tiktok\.com", low):
        return "TikTok"
    if re.search(r"(^|[./])youtu(?:\.be|be\.com)", low):
        return "YouTube"
    if re.search(r"(^|[./])(?:facebook\.com|fb\.watch)", low):
        return "Facebook"
    if re.search(r"(^|[./])instagram\.com", low):
        return "Instagram"
    return None


def normalize_account(text):
    raw = (text or "").strip()
    if not raw:
        return (None, None)
    match = re.search(r"tiktok\.com/@([A-Za-z0-9._]+)", raw, re.IGNORECASE)
    username = match.group(1) if match else raw.lstrip("@").strip("/ ")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username or ""):
        return (None, None)
    return (username, f"https://www.tiktok.com/@{username}")


class AccountFetchThread(QThread):
    """Lists a public account's newest videos without downloading them."""

    found = Signal(list, str)
    failed = Signal(str)
    note = Signal(str)

    def __init__(self, account_text, limit=MAX_ACCOUNT_VIDEOS, use_cookies=False, parent=None):
        super().__init__(parent)
        self.account_text = account_text
        self.limit = max(1, min(int(limit), MAX_ACCOUNT_VIDEOS))
        self.use_cookies = use_cookies

    def run(self):
        username, url = normalize_account(self.account_text)
        if not username:
            self.failed.emit("That doesn't look like a username or profile link.")
            return
        self.note.emit(f"Looking up @{username}…")
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            # 'extract_flat' is omitted because yt_dlp does not honor `playlistend` for TikTok profiles.
            "playlistend": self.limit,
            "ignoreerrors": True,
            "js_runtimes": js_runtime_opts(),
        }
        target, _label = impersonate_target()
        if target is not None:
            opts["impersonate"] = target
        if self.use_cookies:
            opts["cookiesfrombrowser"] = ("chrome",)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            self.failed.emit(tidy_error(exc))
            return
        if not info:
            self.failed.emit(
                "Nothing came back. The account may be private or the name may be wrong."
            )
            return
        urls = []
        for entry in info.get("entries") or []:
            if not entry:
                continue
            candidate = tiktok_page_url(entry, username)
            if candidate and candidate not in urls:
                urls.append(candidate)
            if len(urls) >= self.limit:
                break
        if not urls:
            self.failed.emit(
                f"No videos found for @{username}. Private accounts need the Chrome cookies option."
            )
            return
        logger.info("Fetched %d TikTok video URLs for @%s", len(urls), username)
        self.found.emit(urls, username)


class YouTubeFetchThread(QThread):
    """Expands a YouTube playlist or channel into individual video URLs.

    Emits progress updates so users know the app isn't frozen during large
    channel expansions (e.g., 500 videos).
    """

    found = Signal(list, str)
    failed = Signal(str)
    note = Signal(str)
    progress = Signal(int, int)  # (current, total)

    def __init__(
        self,
        url,
        limit=MAX_ACCOUNT_VIDEOS,
        parent=None,
        include_shorts=True,
        shorts_sort="latest",
        video_type="all",
    ):
        super().__init__(parent)
        self.url = url
        self.limit = max(1, min(int(limit), 500))
        self.include_shorts = include_shorts
        self.shorts_sort = (shorts_sort or "latest").strip().lower()
        self.video_type = (video_type or "all").strip().lower()

    def _fetch_sorted_shorts(self, base_url: str, sort_mode: str, limit: int) -> list[str]:
        """Fetch popular or oldest Shorts directly via YouTube InnerTube continuation chips."""
        import json
        import re
        import urllib.parse

        import httpx

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        clean_base = clean_youtube_channel_base(base_url)
        shorts_url = f"{clean_base}/shorts"
        try:
            resp = httpx.get(shorts_url, headers=headers, timeout=12.0, follow_redirects=True)
            if resp.status_code != 200:
                return []
            m_key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', resp.text)
            if not m_key:
                return []
            key = m_key.group(1)

            match = re.search(r'var ytInitialData = ({.*?});</script>', resp.text)
            if not match:
                return []
            data = json.loads(match.group(1))
            tabs = data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            shorts_tab = next(
                (t for t in tabs if "tabRenderer" in t and "shorts" in t["tabRenderer"].get("title", "").lower()),
                None,
            )
            if not shorts_tab:
                return []
            chips = (
                shorts_tab.get("tabRenderer", {})
                .get("content", {})
                .get("richGridRenderer", {})
                .get("header", {})
                .get("chipBarViewModel", {})
                .get("chips", [])
            )
            target_token = None
            for chip in chips:
                c_vm = chip.get("chipViewModel", {})
                text = (c_vm.get("text") or "").strip().lower()
                if (sort_mode == "popular" and "popular" in text) or (sort_mode == "oldest" and "oldest" in text):
                    raw_token = (
                        c_vm.get("tapCommand", {})
                        .get("innertubeCommand", {})
                        .get("continuationCommand", {})
                        .get("token")
                    )
                    if raw_token:
                        target_token = urllib.parse.unquote(raw_token)
                        break
            if not target_token:
                return []

            payload = {
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": "2.20241010.00.00",
                    }
                },
                "continuation": target_token,
            }
            api_resp = httpx.post(
                f"https://www.youtube.com/youtubei/v1/browse?key={key}",
                json=payload,
                headers=headers,
                timeout=12.0,
            )
            if api_resp.status_code != 200:
                return []
            api_data = api_resp.json()
            out_urls: list[str] = []
            for act in api_data.get("onResponseReceivedActions", []):
                cmd = act.get("reloadContinuationItemsCommand", {}) or act.get("appendContinuationItemsAction", {})
                for it in cmd.get("continuationItems", []):
                    reel = it.get("richItemRenderer", {}).get("content", {}).get("shortsLockupViewModel", {})
                    on_tap = reel.get("onTap", {}).get("innertubeCommand", {}).get("reelWatchEndpoint", {})
                    vid = on_tap.get("videoId") or it.get("richItemRenderer", {}).get("content", {}).get("reelItemRenderer", {}).get("videoId")
                    if vid and f"https://www.youtube.com/shorts/{vid}" not in out_urls:
                        out_urls.append(f"https://www.youtube.com/shorts/{vid}")
                        if len(out_urls) >= limit:
                            return out_urls
            return out_urls
        except Exception as exc:
            logger.debug("Failed to fetch sorted shorts via InnerTube: %s", exc)
            return []

    def _targets(self) -> list[str]:
        """The pages to read.

        A channel URL does not list the channel's videos: yt-dlp returns the
        channel's *tabs* (Videos, Live, Shorts) and every entry carries the
        channel id. Turning those into ``watch?v=UC...`` links queues
        something that is not a video. The tabs have to be visited one by
        one, and the Shorts tab is a page of its own.

        Verified live on 2026-10-21 for @mkbhd, @MrBeast and @veritasium:
        the channel URL returned two or three tab entries and no video.
        """
        if not is_youtube_channel_url(self.url):
            return [self.url]
        clean_url = self.url.rstrip("/")
        explicit_shorts = clean_url.lower().endswith("/shorts")
        explicit_videos = clean_url.lower().endswith("/videos")
        base = clean_youtube_channel_base(self.url)

        # Explicit sub-tab in URL overrides generic "all"
        if explicit_shorts or self.video_type == "shorts":
            return [f"{base}/shorts"]
        if explicit_videos or self.video_type in ("videos", "long", "long-form"):
            return [f"{base}/videos"]

        # Default "all": Videos first, then Shorts if include_shorts is True
        targets = [f"{base}/videos"]
        if self.include_shorts:
            targets.append(f"{base}/shorts")
        return targets

    def run(self):
        self.note.emit("Expanding YouTube link…")
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            # 'extract_flat' is omitted because yt_dlp does not honor `playlistend`
            # for YouTube channel / playlist URLs when it is set.
            "playlistend": self.limit,
            "ignoreerrors": True,
            "js_runtimes": js_runtime_opts(),
        }
        urls: list[str] = []
        label = ""
        base_channel = clean_youtube_channel_base(self.url)
        for target_idx, target in enumerate(self._targets()):
            if target.endswith("/shorts") and self.shorts_sort in ("popular", "oldest"):
                sorted_shorts = self._fetch_sorted_shorts(base_channel, self.shorts_sort, self.limit)
                if sorted_shorts:
                    for s_url in sorted_shorts:
                        if s_url not in urls:
                            urls.append(s_url)
                    continue
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(target, download=False)
            except Exception as exc:
                self.failed.emit(tidy_error(exc))
                return
            if not info:
                continue
            entries = info.get("entries")
            if not entries and info.get("_type") != "playlist":
                entries = [info]
            if not label:
                label = info.get("title") or "this YouTube source"
            # Each tab gets its own budget: the videos tab must not eat the
            # Shorts tab's share.
            taken = 0
            for entry in entries or []:
                vid = (entry or {}).get("id")
                if not _is_video_id(vid):
                    # A tab placeholder, not a video.
                    continue
                candidate = f"https://www.youtube.com/watch?v={vid}"
                if candidate not in urls:
                    urls.append(candidate)
                    # Emit progress for large expansions.
                    if taken % 50 == 0:
                        self.progress.emit(taken, self.limit)
                taken += 1
                if taken >= self.limit:
                    break
            # Progress between tabs.
            self.progress.emit(taken, self.limit)
        if not urls:
            self.failed.emit("No videos found in that playlist or channel.")
            return
        self.found.emit(urls, label)


class InstagramFetchThread(QThread):
    """Expands an Instagram profile into individual post URLs.

    The listing is done by ``instaloader``: yt-dlp's own ``instagram:user``
    extractor is broken upstream (yt-dlp issue #4394).
    """

    found = Signal(list, str)
    failed = Signal(str)
    note = Signal(str)
    progress = Signal(int, int)

    def __init__(self, url, limit=MAX_ACCOUNT_VIDEOS, parent=None):
        super().__init__(parent)
        self.url = url
        self.limit = max(1, min(int(limit), MAX_ACCOUNT_VIDEOS))

    def run(self):
        username, _ = normalize_instagram_profile(self.url)
        if not username:
            self.failed.emit("That doesn't look like an Instagram profile.")
            return
        self.note.emit(f"Listing @{username}…")
        try:
            listing = list_profile_media(
                username,
                self.limit,
                progress=lambda found: self.progress.emit(found, self.limit),
            )
        except InstagramError as exc:
            self.failed.emit(str(exc))
            return
        except Exception:
            # An exception in a QThread ends the thread and prints to a
            # stderr that a windowed build never shows. The user would see
            # nothing at all, so the run says what happened.
            logger.exception("Listing @%s failed unexpectedly", username)
            self.failed.emit("Instagram could not be listed. See the log for the reason.")
            return
        if not listing:
            self.failed.emit(f"No video posts found for @{username}.")
            return
        logger.info("Fetched %d Instagram URLs for @%s", len(listing), username)
        label = f"@{username}"
        if listing.reason:
            label = f"{label} — {listing.reason}"
        self.found.emit(list(listing), label)


class FacebookFetchThread(QThread):
    """Expands a Facebook page into individual video URLs.

    Experimental: the page's Videos tab is read in the app's own browser,
    and the page's own query pages the list behind that tab. Both read a
    page Meta can change at any time.
    """

    found = Signal(list, str)
    failed = Signal(str)
    note = Signal(str)
    progress = Signal(int, int)

    def __init__(self, url, limit=MAX_ACCOUNT_VIDEOS, parent=None):
        super().__init__(parent)
        self.url = url
        self.limit = max(1, min(int(limit), MAX_ACCOUNT_VIDEOS))

    def run(self):
        page, _ = normalize_facebook_page(self.url)
        if not page:
            self.failed.emit("That doesn't look like a Facebook page.")
            return
        caveat = "experimental: Facebook's own list, paged as far as it goes"
        self.note.emit(f"Listing {page}'s videos — {caveat}.")
        try:
            listing = list_page_videos(
                page,
                self.limit,
                progress=lambda found: self.progress.emit(found, self.limit),
            )
        except FacebookError as exc:
            self.failed.emit(str(exc))
            return
        except Exception:
            # An exception in a QThread ends the thread and prints to a
            # stderr that a windowed build never shows. The user would see
            # nothing at all, so the run says what happened.
            logger.exception("Listing %s failed unexpectedly", page)
            self.failed.emit("Facebook could not be listed. See the log for the reason.")
            return
        if not listing:
            self.failed.emit(f"No videos found on {page}.")
            return
        logger.info("Fetched %d Facebook URLs for %s", len(listing), page)
        label = f"{page} — {caveat}"
        if listing.reason:
            label = f"{label} — {listing.reason}"
        self.found.emit(list(listing), label)


_EMOJI_PATTERN = re.compile(
    r"[😀-🙏🌀-🗿🚀-\U0001f6ff\U0001f1e0-🇿✀-➿🤀-🧿☀-⛿🩰-\U0001faff⬀-⯿]+",
    flags=re.UNICODE,
)


def remove_emojis(text):
    return _EMOJI_PATTERN.sub("", text)


def sanitize_filename(text):
    if not text:
        return "untitled"
    text = remove_emojis(text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = "".join(ch for ch in text if ch.isprintable())
    text = text.rstrip(". ")
    if not text:
        return "untitled"
    return text[:MAX_FILENAME_LENGTH]


def _listdir(folder):
    try:
        return os.listdir(folder)
    except OSError:
        return []


_NAME_LOCK = threading.Lock()


def unique_basename(folder, base):
    names = _listdir(folder)
    if not any(f.startswith(base + ".") for f in names):
        return base
    n = 2
    while any(f.startswith(f"{base} ({n}).") for f in names):
        n += 1
    return f"{base} ({n})"


def human_size(num):
    if not num:
        return "—"
    num = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(num)} B"
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return "—"


def bundle_extra_roots():
    """The folders a bundle may carry its own ffmpeg and browser in.

    Windows and Linux keep everything next to the executable, so that one
    folder answers for both. A macOS ``.app`` — what ``--windowed`` builds
    there — splits it: ``Contents/MacOS`` holds only the executable, and every
    other file has to live in ``Contents/Resources``, so the extras staged with
    the app are a sibling of the launcher's folder, not its neighbour.
    """
    import sys

    launcher = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
    roots = [os.path.dirname(os.path.abspath(launcher))]
    if os.path.basename(roots[0]) == "MacOS":
        roots.append(os.path.join(os.path.dirname(roots[0]), "Resources"))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(meipass)
    return roots


def find_ffmpeg():
    import shutil
    import sys

    # The bundle carries the binary this OS runs: ffmpeg.exe on Windows,
    # a plain ffmpeg on Linux and macOS.
    binary = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    for root in bundle_extra_roots():
        for candidate in (
            os.path.join(root, binary),
            os.path.join(root, "bin", binary),
        ):
            if os.path.isfile(candidate):
                return os.path.dirname(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return os.path.dirname(found)
    return None


def ffmpeg_binary():
    """The ffmpeg the app can run, as a command rather than a folder.

    ``find_ffmpeg`` answers where ffmpeg lives because yt-dlp wants the
    folder; the reframe and the split build their own command lines and
    want the file.
    """
    import sys

    directory = find_ffmpeg()
    if not directory:
        return "ffmpeg"
    binary = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    return os.path.join(directory, binary)


def build_music_opts(fmt, outtmpl, ffmpeg_dir=None, use_cookies=False):
    """yt-dlp options for one music track: best audio → requested codec.

    The FLAC file from YouTube is a lossless container around the best stream
    YouTube serves; it cannot restore detail the source never had. Embedding
    the artwork and the metadata is what makes the file usable in a library.
    """
    extract = {"key": "FFmpegExtractAudio", "preferredcodec": fmt}
    if fmt == "mp3":
        extract["preferredquality"] = "0"
    can_embed_thumb = fmt != "wav"  # RIFF WAV has no thumbnail container
    postprocessors = [extract, {"key": "FFmpegMetadata", "add_metadata": True}]
    if can_embed_thumb:
        postprocessors.append({"key": "EmbedThumbnail"})

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "writethumbnail": can_embed_thumb,
        "postprocessors": postprocessors,
        "js_runtimes": js_runtime_opts(),
        "extractor_args": {"youtube": {"player_client": list(YOUTUBE_PLAYER_CLIENTS)}},
        "retries": 0,
        "fragment_retries": 0,
        "overwrites": True,
        "ignoreerrors": False,
    }
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
    if use_cookies:
        opts["cookiesfrombrowser"] = ("chrome",)
    return opts


def music_output_path(output_dir, track, ext, position=1):
    """Collection links file flat into the collection's folder; a lone link into Artist/Album.

    A playlist's rows come from many artists, so one Artist/Album folder per row
    scatters a single download across the library.
    """
    number = track.track_number or position
    title = sanitize_filename(track.title) if track.title else "Untitled"
    base = f"{number:02d} - {title}" if number else title
    if track.collection:
        folder = os.path.join(output_dir, sanitize_filename(track.collection))
    else:
        artist = sanitize_filename(track.artist) if track.artist else "Unknown Artist"
        album = sanitize_filename(track.album) if track.album else "Singles"
        folder = os.path.join(output_dir, artist, album)
    os.makedirs(folder, exist_ok=True)
    with _NAME_LOCK:
        return os.path.join(folder, unique_basename(folder, base) + ext)


def music_quality_label(info):
    """Human label for the source stream, shown next to the downloaded file."""
    codec = str((info or {}).get("acodec") or "").lower()
    if codec.startswith("opus"):
        name = "Opus"
    elif codec.startswith("mp4a") or codec == "aac":
        name = "AAC"
    elif codec.startswith("flac"):
        name = "FLAC"
    elif codec.startswith("vorbis"):
        name = "Vorbis"
    elif codec in ("", "none"):
        return "best available"
    else:
        name = codec.split(".")[0].upper()
    abr = (info or {}).get("abr") or (info or {}).get("tbr")
    return f"{name} {round(abr)}kbps" if abr else name


def tidy_error(exc):
    message = str(exc).replace("\n", " ").strip()
    message = re.sub(r"\s*;?\s*please report this issue on.*", "", message, flags=re.IGNORECASE)
    message = re.sub(
        r"\s*confirm you are on the latest version.*", "", message, flags=re.IGNORECASE
    )
    message = re.sub(r"^ERROR:\s*", "", message)
    message = re.sub(r"^\[TikTok\]\s*\d+:\s*", "", message)
    message = re.sub(r"\s+", " ", message).strip()
    lowered = message.lower()
    if "rehydration" in lowered or "unexpected response" in lowered:
        return "TikTok refused the request — rate limited."
    if "secondary user id" in lowered:
        return "TikTok didn't return the profile page — retry in a few minutes."
    if (
        "login required" in lowered
        or "login to continue" in lowered
        or "only available to registered users" in lowered
    ):
        return (
            "Facebook or Instagram needs a login. Sign in to Chrome, close it, "
            "then enable Chrome cookies."
        )
    if "sign in to confirm" in lowered or "use --cookies" in lowered:
        return (
            "YouTube asked to verify you're not a bot. Wait 10-30 minutes and "
            "retry, or enable Chrome cookies (close Chrome first)."
        )
    if "unavailable" in lowered or "not found" in lowered:
        return "Video is unavailable, private or deleted."
    if "403" in lowered and "forbidden" in lowered:
        return "TikTok's media link expired — re-fetch the profile for fresh links."
    if "ffmpeg" in lowered:
        return "This format needs ffmpeg to merge. Pick a lower quality."
    if not message:
        return "Unknown error"
    return message[:200]


def is_permanent(message):
    lowered = message.lower()
    if "rate limited" in lowered or "refused the request" in lowered:
        return False
    return any(sign in lowered for sign in PERMANENT_SIGNS)


class _Stopped(Exception):
    pass


class _Meter:
    """One file's bar, priced in reads of the film before the first of them runs.

    The work is the passes the run has said it will make, each worth the
    length of the file it reads: a five-minute film takes the same shape of
    bar as a one-minute one, just longer. Every pass reports the share of
    itself it has finished against that priced whole, so work found late -
    the pieces of a split, which only exist once it has cut - fills the bar
    instead of pushing it back.
    """

    def __init__(self, report=None, seconds=0.0):
        self._report = report
        self._total = max(seconds, 0.0)
        self._weights = []
        self._done = []
        self._shown = 0.0

    def price(self, seconds):
        """The callback one pass over ``seconds`` of film calls with how far
        over itself it has got. With nobody listening for the bar there is no
        callback, and the pass runs exactly as it always did."""
        if self._report is None:
            return None
        self._weights.append(max(seconds, 0.0))
        self._done.append(0.0)
        leg = len(self._weights) - 1
        return lambda fraction: self._tick(leg, fraction)

    def _tick(self, leg, fraction):
        self._done[leg] = max(self._done[leg], min(max(fraction, 0.0), 1.0))
        if not self._total:
            return
        done = sum(w * d for w, d in zip(self._weights, self._done, strict=True))
        share = min(done / self._total, 1.0)
        if share > self._shown:
            self._shown = share
            self._report(round(share * 100, 1))

    def finish(self):
        """The file is as done as it is going to get."""
        if self._report is not None and self._shown < 1.0:
            self._shown = 1.0
            self._report(100.0)


#: The size of a copy's read: what Stop is checked against. A whole-film
#: copy has no cancel of its own, and minutes of it would go on running
#: after the user pressed the button.
COPY_CHUNK = 4 * 1024 * 1024


def _take_back(target):
    """A file this run started and did not finish is not a result."""
    try:
        os.remove(target)
    except OSError:
        pass


def _copy_file(source, target, stopped):
    """The source's bytes, into the target, in chunks. False means Stop was
    pressed partway and what is on disk is part of a film."""
    with open(source, "rb") as src, open(target, "wb") as dst:
        while True:
            if stopped():
                return False
            data = src.read(COPY_CHUNK)
            if not data:
                return True
            dst.write(data)


def stage_for_folder(path, folder, report, stopped=None):
    """The file the legs work on: a copy of the source, inside the folder.

    The legs write every output beside the file they were given, so putting
    the file there puts its results there too - and the source the user
    dropped stays exactly where it was. None means this file is skipped and
    ``report`` has already said why; a copy that died halfway is not a
    result and is taken back out.

    Everything the copy does is guarded, and guarded against more than the
    ``OSError`` it says it will raise: this step can take minutes over a big
    film, and it ending the run on a surprise would leave the rest of the
    list unnamed. ``stopped`` is asked between the chunks so a Stop is
    answered in seconds, not after the whole film has come over.
    """
    stop_ = stopped or (lambda: False)
    name = os.path.basename(str(path))
    target = None
    try:
        source = os.path.abspath(path)
        destination = os.path.abspath(folder)
        if os.path.normcase(os.path.dirname(source)) == os.path.normcase(destination):
            return source
        os.makedirs(destination, exist_ok=True)
        base, ext = os.path.splitext(name)
        with _NAME_LOCK:
            target = os.path.join(destination, unique_basename(destination, base) + ext)
            copied = _copy_file(source, target, stop_)
    except Exception as exc:
        logger.warning("The copy into the results folder failed for %s", path, exc_info=True)
        if target is not None:
            _take_back(target)
        report(f"{name} could not be copied to the results folder: {exc}")
        return None
    if not copied:
        _take_back(target)
        report(f"{name} was left uncopied: the run was stopped.")
        return None
    return target


def run_post_leg(
    path, *, vertical, split, clips, ffmpeg, duration, report, stage=None, hold=None, progress=None
):
    """The shorts and the vertical versions of one file that is on disk.

    Nothing here may lose the file it started from: a step that cannot run
    says why in one sentence and moves on. The download worker hands over its
    own log, progress and pause; the Vertical Studio hands over the same three
    for a file nobody downloaded — so the legs exist once, here.

    ``progress`` is told the percent of this file's work that is done, priced
    here as the three reads of a split plus the four of a reframe. It is worth
    handing over: minutes of ffmpeg say nothing on their own, and a bar that
    only moves between the passes looks broken.
    """
    stage_ = stage or (lambda _name: None)
    hold_ = hold or (lambda: None)
    reads = 3 * (split != DEFAULT_SPLIT) + (reframe.ANALYSIS_PASSES + 1) * bool(vertical)
    meter = _Meter(progress, reads * duration)

    pieces = [path]
    if split != DEFAULT_SPLIT:
        try:
            pieces = split_pieces(
                path,
                split=split,
                clips=clips,
                ffmpeg=ffmpeg,
                duration=duration,
                report=report,
                stage=stage_,
                hold=hold_,
                meter=meter,
            )
        except Exception as exc:
            logger.warning("The split failed for %s", path, exc_info=True)
            report(f"The split could not run: {exc}")
    if vertical:
        share = duration / len(pieces)
        for piece in pieces:
            try:
                make_vertical(
                    piece,
                    ffmpeg=ffmpeg,
                    report=report,
                    stage=stage_,
                    hold=hold_,
                    meter=meter,
                    share=share,
                )
            except Exception as exc:
                logger.warning("The vertical version failed for %s", piece, exc_info=True)
                report(f"The vertical version could not be made: {exc}")
    meter.finish()


def split_pieces(path, *, split, clips, ffmpeg, duration, report, stage, hold, meter=None):
    """Cut the file into shorts at the pauses. The whole file back when there
    is nothing to cut or nothing to cut it with."""
    meter = meter or _Meter()
    if not duration:
        report("This file did not report its length, so it was not split.")
        return [path]

    # The three reads are priced together: a plan that turns out to need no
    # cut is told about by the sentence, not by a bar stuck at two thirds.
    pauses = meter.price(duration)
    scan = meter.price(duration)
    cutting = meter.price(duration)

    target = shorts.TARGETS.get(split)
    wanted = clips if split == SPLIT_CLIPS else None
    hold()
    stage("finding the pauses")
    silences = shorts.detect_silences(path, ffmpeg=ffmpeg, duration=duration, progress=pauses)
    hold()
    stage("finding the scenes")
    scenes = shorts.detect_scene_changes(path, ffmpeg=ffmpeg, duration=duration, progress=scan)
    plan = shorts.plan_cuts(duration, target=target, silences=silences, scenes=scenes, clips=wanted)
    if plan.note:
        report(plan.note)
    if not plan.segments:
        return [path]

    stage("splitting")
    result = shorts.split_video(path, plan, ffmpeg=ffmpeg, progress=cutting)
    report(result.note)
    return result.outputs or [path]


def make_vertical(path, *, ffmpeg, report, stage, hold, meter=None, share=0.0):
    """The 9:16 version of one file, beside it, with the subject tracked.

    ``share`` is how much of the parent film's length this file is, so the two
    passes here - three reads of it to find the subject, one to write the
    vertical - are priced into the same bar the split spent itself on. Each
    pass measures its own file for how far over it has got.
    """
    meter = meter or _Meter()
    width, height, _fps = reframe.frame_size(path)
    if not width or not height:
        report("This file has no picture to reframe.")
        return
    if not reframe.is_landscape(width, height):
        report("This video is already vertical.")
        return

    read = meter.price(reframe.ANALYSIS_PASSES * share)
    write = meter.price(share)

    hold()
    stage("finding the subject")
    box, samples = reframe.analyse(path, ffmpeg=ffmpeg, progress=read)
    hold()
    stage("writing the vertical")
    result = reframe.render_vertical(
        path,
        reframe.vertical_output_path(path),
        width,
        height,
        samples,
        ffmpeg=ffmpeg,
        box=box,
        progress=write,
    )
    report(result.note)


class DownloadThread(QThread):
    """Runs a pool of workers over the queue."""

    job_started = Signal(int, str)
    job_meta = Signal(int, str, str)
    job_quality = Signal(int, str)
    job_progress = Signal(int, float, str, str)
    job_retrying = Signal(int, int, int)
    job_result = Signal(int, str, str, str)
    log = Signal(str)
    countdown = Signal(float)
    finished_all = Signal()

    def __init__(
        self,
        jobs,
        output_dir,
        quality,
        use_cookies=False,
        delay_key=DEFAULT_DELAY,
        extra_passes=0,
        parallel=2,
        vertical=False,
        split=DEFAULT_SPLIT,
        clips=DEFAULT_CLIPS,
        parent=None,
    ):
        super().__init__(parent)
        self.jobs = jobs
        self.output_dir = output_dir
        self.quality = quality
        self.use_cookies = use_cookies
        self.delay_range = DELAY_PRESETS.get(delay_key, DELAY_PRESETS[DEFAULT_DELAY])
        self.extra_passes = extra_passes
        self.parallel = max(1, int(parallel))
        self.vertical = bool(vertical)
        self.split = split if split in SPLIT_OPTIONS else DEFAULT_SPLIT
        self.clips = max(1, int(clips))
        self._resume = threading.Event()
        self._resume.set()
        self._stop = False
        self._impersonate = True
        self._ffmpeg_dir = find_ffmpeg()
        self._ffmpeg = ffmpeg_binary()

    def pause(self):
        self._resume.clear()

    def resume(self):
        self._resume.set()

    def stop(self):
        self._stop = True
        self._resume.set()

    def is_paused(self):
        return not self._resume.is_set()

    def _gate(self):
        if self._stop:
            raise _Stopped()
        while not self._resume.wait(timeout=0.2):
            if self._stop:
                raise _Stopped()
        if self._stop:
            raise _Stopped()

    def _sleep(self, seconds):
        ends = time.time() + seconds
        while time.time() < ends:
            self._gate()
            time.sleep(0.1)

    def _base_opts(self, platform="TikTok"):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "js_runtimes": js_runtime_opts(),
        }
        if platform == "TikTok":
            target, _label = impersonate_target()
            if self._impersonate and target is not None:
                opts["impersonate"] = target
        elif platform == "YouTube":
            opts["extractor_args"] = {
                "youtube": {"player_client": list(YOUTUBE_PLAYER_CLIENTS)}
            }
        if self.use_cookies:
            opts["cookiesfrombrowser"] = ("chrome",)
        if self._ffmpeg_dir:
            opts["ffmpeg_location"] = self._ffmpeg_dir
        return opts

    def _hook_factory(self, uid, seen, platform="TikTok"):
        reported = set()

        def hook(d):
            self._gate()
            meta = d.get("info_dict") or {}
            if not seen:
                caption = meta.get("description") or meta.get("title")
                if caption:
                    seen.add(True)
                    self.job_meta.emit(uid, sanitize_filename(caption), platform)
            label = quality_label(meta.get("height"), meta.get("vcodec"))
            if label and label not in reported:
                reported.add(label)
                self.job_quality.emit(uid, label)
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                got = d.get("downloaded_bytes") or 0
                pct = (got / total) * 100.0 if total else 0.0
                speed = d.get("speed")
                self.job_progress.emit(
                    uid,
                    min(pct, 99.0),
                    human_size(total),
                    (human_size(speed) + "/s") if speed else "—",
                )
            if d.get("status") == "finished":
                self.job_progress.emit(uid, 99.0, "—", "finishing")

        return hook

    def _download_one(self, uid, url):
        os.makedirs(self.output_dir, exist_ok=True)
        platform = platform_of(url) or "TikTok"
        opts = self._base_opts(platform)
        spec = QUALITY_OPTIONS[self.quality]
        holder = {}
        opts.update(
            {
                "format": spec,
                "outtmpl": os.path.join(
                    self.output_dir, f"{TEMP_PREFIX}%(id)s-{uid}.%(ext)s"
                ),
                "merge_output_format": "mp4",
                "ignoreerrors": False,
                "retries": 0,
                "fragment_retries": 0,
                "progress_hooks": [self._hook_factory(uid, set(), platform)],
                "overwrites": True,
            }
        )
        if self.quality == "Audio only":
            opts["merge_output_format"] = None
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            # The container follows the codec, and only the download knows
            # which codec it picked - so the selection is a callable that
            # decides the container once it knows.
            opts["format"] = codec_aware_format_selector(spec, lambda: holder["ydl"])
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                holder["ydl"] = ydl
                info = ydl.extract_info(url, download=True)
                if info is None:
                    raise RuntimeError("No video found at this link")
                if info.get("_type") == "playlist":
                    entries = [e for e in (info.get("entries") or []) if e]
                    if not entries:
                        raise RuntimeError("This link is a page, not a single video")
                    info = entries[0]
                downloaded = None
                for item in info.get("requested_downloads") or []:
                    downloaded = item.get("filepath") or item.get("_filename")
                    if downloaded:
                        break
                if not downloaded:
                    try:
                        downloaded = ydl.prepare_filename(info)
                    except Exception:
                        downloaded = None
        except Exception:
            # Never swallow the extractor/HTTP error — it is the only thing
            # that tells the user why the download failed.
            logger.exception("Download failed: %s", url)
            raise
        if downloaded and not os.path.isfile(downloaded):
            vid = str(info.get("id") or "")
            for name in _listdir(self.output_dir):
                if vid and name.startswith(TEMP_PREFIX + vid):
                    downloaded = os.path.join(self.output_dir, name)
                    break
        if not downloaded or not os.path.isfile(downloaded):
            raise RuntimeError("Download finished but the file is missing")
        caption = info.get("description") or info.get("title") or ""
        safe = sanitize_filename(caption)
        base = safe if safe != "untitled" else f"video_{info.get('id') or 'unknown'}"
        ext = os.path.splitext(downloaded)[1] or ".mp4"
        with _NAME_LOCK:
            target = os.path.join(self.output_dir, unique_basename(self.output_dir, base) + ext)
            try:
                os.replace(downloaded, target)
            except OSError:
                target = downloaded
        self.job_meta.emit(uid, os.path.splitext(os.path.basename(target))[0], platform)
        self._post_leg(uid, target, info)
        try:
            return human_size(os.path.getsize(target))
        except OSError:
            return "—"

    def _post_leg(self, uid, path, info):
        """The shorts and the vertical versions, once the download has landed.

        The download is already won by the time this runs, so nothing here
        may fail it. The legs themselves are in run_post_leg, shared with the
        Vertical Studio; this hands over the worker's own log, progress and
        pause.
        """
        if self._stop or self.quality == "Audio only":
            return
        run_post_leg(
            path,
            vertical=self.vertical,
            split=self.split,
            clips=self.clips,
            ffmpeg=self._ffmpeg,
            duration=float(info.get("duration") or 0.0),
            report=self.log.emit,
            stage=lambda name: self.job_progress.emit(uid, 99.0, "—", name),
            hold=self._wait_while_paused,
        )

    def _wait_while_paused(self):
        """Hold between the ffmpeg passes. A pause never cancels a job whose
        file is already on disk, so this waits instead of raising."""
        while self.is_paused() and not self._stop:
            time.sleep(0.1)

    def _attempt(self, uid, url):
        """Attempt a single download.

        Handles impersonation failures by retrying without impersonation once.
        This is merged into the inline retry loop to avoid duplicate logic.
        """
        try:
            return (True, self._download_one(uid, url), "")
        except _Stopped:
            raise
        except Exception as exc:
            raw = str(exc).lower()
            if self._impersonate and "impersonat" in raw:
                # Retry once without impersonation if the failure was due to
                # impersonation being unavailable.
                self._impersonate = False
                self.log.emit("Browser impersonation unavailable — continuing without it.")
                try:
                    return (True, self._download_one(uid, url), "")
                except _Stopped:
                    raise
                except Exception as exc2:
                    logger.warning("Download failed: %s — %s", url, exc2)
                    return (False, "—", tidy_error(exc2))
            logger.warning("Download failed: %s — %s", url, exc)
            return (False, "—", tidy_error(exc))

    def _try_with_inline(self, uid, url, position):
        tries = 1 + INLINE_RETRIES
        error = "Unknown error"
        try:
            for n in range(1, tries + 1):
                ok, size, error = self._attempt(uid, url)
                if ok:
                    return (True, size, "", False)
                if is_permanent(error):
                    return (False, "—", error, True)
                if n < tries:
                    self.job_retrying.emit(uid, n, INLINE_RETRIES)
                    self.log.emit(f"{position} failed — retry {n} of {INLINE_RETRIES}…")
                    self._sleep(random.uniform(*INLINE_RETRY_WAIT))
            return (False, "—", error, False)
        finally:
            # A failed download may leave __amd_<id>-<uid>.part behind.
            # Remove only this job's temp files; a parallel job's files
            # have a different uid in the name.
            for name in _listdir(self.output_dir):
                if name.startswith(TEMP_PREFIX) and f"-{uid}." in name:
                    try:
                        os.remove(os.path.join(self.output_dir, name))
                    except OSError:
                        pass

    def _run_pool(self, items, inline, label, final):
        total = len(items)
        workers = 1 if total <= 1 else max(1, min(self.parallel, total))
        cursor = {"i": 0}
        cursor_lock = threading.Lock()
        leftovers = []
        leftovers_lock = threading.Lock()

        def worker(slot):
            try:
                if slot:
                    self._sleep(slot * WORKER_STAGGER)
                while True:
                    with cursor_lock:
                        index = cursor["i"]
                        if index >= total:
                            return
                        cursor["i"] += 1
                    uid, url = items[index]
                    self._gate()
                    self.job_started.emit(uid, url)
                    position = f"{label} · [{index + 1}/{total}]"
                    self.log.emit(f"{position} {url}")
                    if inline:
                        ok, size, error, permanent = self._try_with_inline(uid, url, position)
                    else:
                        ok, size, error = self._attempt(uid, url)
                        permanent = (not ok) and is_permanent(error)
                    if ok:
                        self.job_result.emit(uid, "Completed", size, "")
                    elif permanent or final:
                        self.job_result.emit(uid, "Failed", "—", error)
                    else:
                        self.job_result.emit(uid, "Waiting", "—", error)
                        with leftovers_lock:
                            leftovers.append((index, (uid, url)))
                    gap = random.uniform(*self.delay_range)
                    if workers == 1:
                        self.countdown.emit(gap)
                    self._sleep(gap)
            except _Stopped:
                return

        threads = [threading.Thread(target=worker, args=(k,), daemon=True) for k in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if self._stop:
            raise _Stopped()

        leftovers.sort(key=lambda pair: pair[0])
        return [pair[1] for pair in leftovers]

    def run(self):
        try:
            ok, label = impersonation_summary()
            self.log.emit(
                ("Browser identity: " + label) if ok else ("No browser impersonation — " + label)
            )

            items = list(self.jobs)
            workers = 1 if len(items) <= 1 else max(1, min(self.parallel, len(items)))
            self.log.emit(
                f"Starting {len(items)} link{'s' if len(items) != 1 else ''} across "
                f"{workers} worker{'s' if workers != 1 else ''}."
            )

            waiting = self._run_pool(items, True, "Pass 1", final=(self.extra_passes == 0))

            for pass_no in range(1, self.extra_passes + 1):
                if not waiting:
                    break
                wait = random.uniform(*PASS_COOLDOWN)
                self.log.emit(
                    f"{len(waiting)} waiting — cooling down {wait:.0f}s before pass "
                    f"{pass_no} of {self.extra_passes}…"
                )
                self._sleep(wait)
                waiting = self._run_pool(
                    waiting, False, f"Pass {pass_no}", final=(pass_no >= self.extra_passes)
                )

            if waiting:
                self.log.emit(f"{len(waiting)} could not be downloaded.")
        except _Stopped:
            self.log.emit("Run stopped.")
        finally:
            self.finished_all.emit()


class LocalVideoThread(QThread):
    """The vertical and shorts passes over files the user points at.

    One file at a time: a reframe costs about four seconds of work per second
    of film, so two at once only make both slower. Stop ends the run after the
    ffmpeg pass in hand - a write started is a write finished - but a copy is
    stopped where it stands and taken back out.

    ``progress`` is the file in hand: how far its priced work has got, and the
    name of the pass doing it.

    ``out_dir`` is the results folder the Studio was shown: each file is
    copied into it and worked on there, so the folder ends up holding the
    film, its vertical and its shorts - under names of its own when the same
    film has been run before. Empty means leave the files where the user put
    them.
    """

    file_started = Signal(int, str)
    progress = Signal(float, str)
    log = Signal(str)
    finished_all = Signal()

    def __init__(
        self,
        files,
        vertical=False,
        split=DEFAULT_SPLIT,
        clips=DEFAULT_CLIPS,
        out_dir=None,
        parent=None,
    ):
        super().__init__(parent)
        self.files = list(files)
        self.vertical = bool(vertical)
        self.split = split if split in SPLIT_OPTIONS else DEFAULT_SPLIT
        self.clips = max(1, int(clips))
        self.out_dir = (out_dir or "").strip() or None
        self._stop = False
        self._percent = 0.0
        self._stage = ""
        self._ffmpeg = ffmpeg_binary()

    def stop(self):
        self._stop = True

    def run(self):
        try:
            for index, path in enumerate(self.files):
                if self._stop:
                    self.log.emit(f"{len(self.files) - index} left unworked.")
                    break
                self._percent = 0.0
                self._stage = ""
                self.file_started.emit(index, path)
                try:
                    work = path
                    if self.out_dir:
                        self._named("copying to the folder")
                        work = stage_for_folder(
                            path, self.out_dir, self.log.emit, stopped=lambda: self._stop
                        )
                        if work is None:
                            continue
                        if work != path:
                            # The writes from here on go into the copy, so the
                            # file in hand is the copy - not what the user dropped.
                            self.file_started.emit(index, work)
                    run_post_leg(
                        work,
                        vertical=self.vertical,
                        split=self.split,
                        clips=self.clips,
                        ffmpeg=self._ffmpeg,
                        duration=reframe.duration_seconds(work),
                        report=self.log.emit,
                        stage=self._named,
                        progress=self._count,
                    )
                except Exception as exc:
                    logger.warning("Nothing could be read from %s", path, exc_info=True)
                    self.log.emit(f"This file could not be read: {exc}")
        finally:
            self.finished_all.emit()

    def _named(self, name):
        """A pass has started: the bar keeps the place it had reached."""
        self._stage = name
        self.progress.emit(self._percent, name)

    def _count(self, percent):
        """A pass has moved: the name it belongs to is already known."""
        self._percent = percent
        self.progress.emit(percent, self._stage)


class MusicResolveThread(QThread):
    """Expand pasted music links into a flat list of downloadable tracks."""

    resolved = Signal(list)
    failed = Signal(str)
    note = Signal(str)

    def __init__(self, urls, use_cookies=False, parent=None):
        super().__init__(parent)
        self.urls = [url for url in urls if str(url).strip()]
        self.use_cookies = use_cookies
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        from s_q_ali_media_downloader.core.music_source import resolve_url

        tracks = []
        errors = []
        for url in self.urls:
            if self._stop:
                break
            try:
                found = resolve_url(url, use_cookies=self.use_cookies)
            except Exception as exc:
                logger.warning("Music resolve failed: %s — %s", url, exc)
                errors.append(tidy_error(exc))
                continue
            tracks.extend(found)
            self.note.emit(
                f"{len(found)} track{'s' if len(found) != 1 else ''} found: {url}"
            )
        if tracks:
            self.resolved.emit(tracks)
        else:
            self.failed.emit(errors[0] if errors else "No tracks found.")


class MusicDownloadThread(QThread):
    """Download a resolved track list one song at a time.

    Sequential on purpose: YouTube bot checks punish bursts, and a music album
    is small enough that the wait costs less than a failed run.
    """

    track_started = Signal(int, str)
    track_progress = Signal(int, float, str, str)
    track_result = Signal(int, str, str, str)
    log = Signal(str)
    finished_all = Signal()

    def __init__(self, tracks, output_dir, fmt, use_cookies=False, parent=None):
        super().__init__(parent)
        self.tracks = list(tracks)
        self.output_dir = output_dir
        self.fmt = fmt
        self.use_cookies = use_cookies
        self._stop = False
        self._ffmpeg_dir = find_ffmpeg()

    def stop(self):
        self._stop = True

    def _hook_factory(self, uid):
        def hook(d):
            if self._stop:
                raise _Stopped()
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                got = d.get("downloaded_bytes") or 0
                pct = (got / total) * 100.0 if total else 0.0
                speed = d.get("speed")
                self.track_progress.emit(
                    uid,
                    min(pct, 99.0),
                    human_size(total),
                    (human_size(speed) + "/s") if speed else "—",
                )
            elif status == "finished":
                self.track_progress.emit(uid, 99.0, "—", "finishing")

        return hook

    def _find_downloaded(self, ydl, info, temp_prefix):
        for item in info.get("requested_downloads") or []:
            filepath = item.get("filepath") or item.get("_filename")
            if filepath and os.path.isfile(filepath):
                return filepath
        try:
            candidate = ydl.prepare_filename(info)
        except Exception:
            candidate = None
        if candidate and os.path.isfile(candidate):
            return candidate
        for name in _listdir(self.output_dir):
            if name.startswith(temp_prefix) and not name.endswith((".jpg", ".png", ".webp")):
                return os.path.join(self.output_dir, name)
        return None

    def _download_one(self, uid, track, position):
        from s_q_ali_media_downloader.core.music_tagging import read_report

        os.makedirs(self.output_dir, exist_ok=True)
        temp_prefix = f"{TEMP_PREFIX}{position}-"
        opts = build_music_opts(
            self.fmt,
            os.path.join(self.output_dir, temp_prefix + "%(id)s.%(ext)s"),
            self._ffmpeg_dir,
            self.use_cookies,
        )
        opts["progress_hooks"] = [self._hook_factory(uid)]

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(track.url, download=True)
            if info is None:
                raise RuntimeError("This link returned no audio")
            if info.get("_type") == "playlist":
                entries = [entry for entry in (info.get("entries") or []) if entry]
                if not entries:
                    raise RuntimeError("This playlist has no tracks")
                info = entries[0]
            downloaded = self._find_downloaded(ydl, info, temp_prefix)
        if not downloaded:
            raise RuntimeError("Download finished but the file is missing")

        ext = os.path.splitext(downloaded)[1] or f".{self.fmt}"
        target = music_output_path(self.output_dir, track, ext, position)
        try:
            os.replace(downloaded, target)
        except OSError:
            target = downloaded

        source_label = music_quality_label(info)
        if track.source == "spotify":
            from s_q_ali_media_downloader.core.music_tagging import embed_tags, fetch_cover

            cover = fetch_cover(track.cover_url) if track.cover_url else None
            try:
                embed_tags(
                    target,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    track_number=track.track_number,
                    cover=cover,
                )
            except Exception as exc:
                # Keep the audio; a tag failure is not worth losing the file.
                logger.warning("Tagging failed for %s — %s", target, exc)
                self.log.emit(f"Tags could not be written: {exc}")
        report = read_report(target, source=source_label)
        return target, report.label()

    def _attempt(self, uid, track, position):
        try:
            return (True, *self._download_one(uid, track, position))
        except _Stopped:
            raise
        except Exception as exc:
            logger.warning("Music download failed: %s — %s", track.url, exc)
            return (False, "—", tidy_error(exc))

    def run(self):
        from s_q_ali_media_downloader.core.music_source import track_label

        total = len(self.tracks)
        self.log.emit(f"Downloading {total} track{'s' if total != 1 else ''}.")
        try:
            for index, track in enumerate(self.tracks, start=1):
                if self._stop:
                    break
                uid = index
                self.track_started.emit(uid, track_label(track))
                ok = False
                size = "—"
                detail = "Unknown error"
                for attempt in range(1, INLINE_RETRIES + 2):
                    if self._stop:
                        break
                    ok, size, detail = self._attempt(uid, track, index)
                    if ok:
                        break
                    if attempt <= INLINE_RETRIES:
                        self.log.emit(f"Retry {attempt}/{INLINE_RETRIES}: {track_label(track)}")
                        time.sleep(1.5)
                if self._stop:
                    break
                if ok:
                    self.track_result.emit(uid, "Done", size, detail)
                else:
                    self.track_result.emit(uid, "Failed", "—", detail)
                    self.log.emit(f"Failed: {track_label(track)} — {detail}")
        except _Stopped:
            self.log.emit("Music run stopped.")
        finally:
            self.finished_all.emit()
