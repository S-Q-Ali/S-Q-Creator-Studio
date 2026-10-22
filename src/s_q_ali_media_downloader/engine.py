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
from PySide6.QtCore import QThread, Signal

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
    "Best available": "bestvideo+bestaudio/best",
    "4K · 2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "2K · 1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "Audio only": "bestaudio/best",
}

MAX_ACCOUNT_VIDEOS = 200
ACCOUNT_LIMITS = [20, 40, 60, 80, 100, 120, 140, 160, 180, 200]

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

    One place decides this, so the folders cannot drift apart.
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME, "storage")


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


def is_youtube_url(url):
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


def platform_of(url):
    low = url.strip().lower()
    if re.search(r"(^|[./])tiktok\.com", low):
        return "TikTok"
    if re.search(r"(^|[./])youtu(?:\.be|be\.com)", low):
        return "YouTube"
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
    """Expands a YouTube playlist or channel into individual video URLs."""

    found = Signal(list, str)
    failed = Signal(str)
    note = Signal(str)

    def __init__(self, url, limit=MAX_ACCOUNT_VIDEOS, parent=None, include_shorts=False):
        super().__init__(parent)
        self.url = url
        self.limit = max(1, min(int(limit), 500))
        self.include_shorts = include_shorts

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
        base = self.url.rstrip("/")
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
        for target in self._targets():
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
                taken += 1
                if taken >= self.limit:
                    break
        if not urls:
            self.failed.emit("No videos found in that playlist or channel.")
            return
        self.found.emit(urls, label)


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


def find_ffmpeg():
    import shutil
    import sys

    roots = [os.path.dirname(os.path.abspath(sys.argv[0]))]
    if getattr(sys, "frozen", False):
        roots.append(os.path.dirname(sys.executable))
        roots.append(getattr(sys, "_MEIPASS", ""))
    for root in roots:
        if not root:
            continue
        for candidate in (
            os.path.join(root, "ffmpeg.exe"),
            os.path.join(root, "bin", "ffmpeg.exe"),
        ):
            if os.path.isfile(candidate):
                return os.path.dirname(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return os.path.dirname(found)
    return None


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


class DownloadThread(QThread):
    """Runs a pool of workers over the queue."""

    job_started = Signal(int, str)
    job_meta = Signal(int, str, str)
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
        self._resume = threading.Event()
        self._resume.set()
        self._stop = False
        self._impersonate = True
        self._ffmpeg_dir = find_ffmpeg()

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
        def hook(d):
            self._gate()
            if not seen:
                meta = d.get("info_dict") or {}
                caption = meta.get("description") or meta.get("title")
                if caption:
                    seen.add(True)
                    self.job_meta.emit(uid, sanitize_filename(caption), platform)
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
        opts.update(
            {
                "format": QUALITY_OPTIONS[self.quality],
                "outtmpl": os.path.join(self.output_dir, TEMP_PREFIX + "%(id)s.%(ext)s"),
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
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
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
        try:
            return human_size(os.path.getsize(target))
        except OSError:
            return "—"

    def _attempt(self, uid, url):
        try:
            return (True, self._download_one(uid, url), "")
        except _Stopped:
            raise
        except Exception as exc:
            raw = str(exc).lower()
            if self._impersonate and "impersonat" in raw:
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
