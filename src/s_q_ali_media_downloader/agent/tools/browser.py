"""A real browser for the pages that only tell the truth when rendered.

Instagram, TikTok and Facebook answer a plain HTTP request with the same
shell for a real profile and for a made-up one — verified 2026-10-21: a
non-existent Instagram profile and a real one both returned the same
590 KB page. A rendered page does tell them apart ("Profile isn't
available", the login wall, "Couldn't find this account"), so the Social
Discovery feature drives a browser.

Two things make that practical in a desktop app:

* The browser this machine already has is used first — real Chrome, then
  Edge on Windows — so nothing has to be downloaded. The shipped Playwright
  Chromium is the fallback.
* The browser keeps a profile under the app's storage, so a sign-in survives
  between runs. A fresh profile would meet the same login wall every time.
* Playwright is an optional dependency. Without it the feature explains
  what to install instead of crashing the app.

Playwright's sync API cannot run inside an asyncio loop and is not
thread-safe, so one session belongs to exactly one worker thread.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from s_q_ali_media_downloader.agent.tools.stealth import STEALTH_ARGS, harden

logger = logging.getLogger(__name__)

#: Where the shipped browser lives, relative to the app.
BROWSER_DIR_NAME = "browsers"

#: The persistent profile, under the app's storage folder.
PROFILE_DIR_NAME = "browser-profile"

#: How long a single navigation may take.
DEFAULT_TIMEOUT_MS = 30_000

#: How long to let the page settle after the DOM is ready.
SETTLE_MS = 1500

CONSENT_TITLE = "Before you continue to YouTube"
CONSENT_SELECTORS = (
    "#accept-button",
    'button:has-text("Accept all")',
    'form[action*="consent"] button',
)

#: Collects every link and says whether it belongs to an item the page
#: *lists* (a video on a channel page, a post on a profile). Only the
#: links that do not belong to a listed item are the page's own — a
#: The links on a rendered page. A channel's About page carries the links of
#: the videos it lists, and those belong to other creators.
_LINK_JS = "els => els.map(e => e.href)"

#: Extracts external links stored inside YouTube's ytInitialData object even
#: when the channel header hides them behind the '...more links' modal button.
_YT_INITIAL_LINKS_JS = """() => {
  try {
    const raw = JSON.stringify(window.ytInitialData || {});
    const out = [];
    const redirectRe = /https?:\\\\?\\/\\\\?\\/(?:www\\.)?youtube\\.com\\\\?\\/redirect\\?[^"'\\s<>]+/gi;
    for (const m of raw.matchAll(redirectRe)) {
      out.push(m[0].replace(/\\\\\\//g, '/').replace(/\\\\u0026/g, '&'));
    }
    const bareRe = /(?:https?:\\\\?\\/\\\\?\\/)?(?:www\\.)?(?:instagram\\.com|facebook\\.com|fb\\.com|tiktok\\.com)\\/[A-Za-z0-9_.@\\/-]{2,80}/gi;
    for (const m of raw.matchAll(bareRe)) {
      let u = m[0].replace(/\\\\\\//g, '/');
      if (!u.startsWith('http')) u = 'https://' + u;
      out.push(u);
    }
    return out;
  } catch (e) {
    return [];
  }
}"""

#: The page's own description of itself. A rendered profile page carries the
#: account's name, its handle and its follower count here, which is far more
#: reliable than scraping the text.
_META_JS = """() => {
  const get = (sel) => {
    const el = document.querySelector(sel);
    return el ? (el.getAttribute('content') || '').trim() : '';
  };
  return {
    ogTitle: get('meta[property="og:title"]'),
    ogDescription: get('meta[property="og:description"]'),
    ogUrl: get('meta[property="og:url"]'),
    description: get('meta[name="description"]'),
  };
}"""


class BrowserError(RuntimeError):
    """Base class for everything this module raises."""


class BrowserUnavailable(BrowserError):
    """No usable browser could be started on this machine."""


class PageUnavailable(BrowserError):
    """The page could not be loaded.

    This is deliberately *not* "the account does not exist": a page that
    cannot be read is unknown, and unknown must never be reported as
    missing.
    """


@dataclass
class Page:
    """What a rendered page gave us."""

    url: str
    title: str = ""
    text: str = ""
    links: list[str] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)


def browser_channels() -> tuple[str | None, ...]:
    """The browsers to try on this machine, in order.

    Real Chrome, then on Windows Edge, then the Playwright Chromium the app
    ships. ``"chromium"`` is the full build (it runs both headless and
    windowed) and ``None`` its headless shell. Edge is skipped off Windows:
    it is preinstalled on Windows and almost nowhere else, and a failed
    attempt only lengthens the error the user ends up reading.
    """
    channels = ["chrome"]
    if sys.platform == "win32":
        channels.append("msedge")
    channels += ["chromium", None]
    return tuple(channels)


def _runs_as_root() -> bool:
    geteuid = getattr(os, "geteuid", None)
    return geteuid is not None and geteuid() == 0


def launch_args() -> list[str]:
    """The Chromium switches for this session.

    Run as root — a CI container, a headless box — Chromium refuses to start
    with its own sandbox enabled, so that one switch has to go. An ordinary
    user keeps it.
    """
    args = list(STEALTH_ARGS)
    if _runs_as_root():
        args.append("--no-sandbox")
    return args


def bundled_browsers_dir() -> Path | None:
    """The browser folder that ships with the app, if it is there.

    The installer carries the full Chromium, so the feature works on a
    machine that has no Edge and no Chrome, in both headless and windowed
    mode. Playwright looks for browsers in its own cache, so the
    environment variable has to point at the shipped copy before Playwright
    starts.

    The folder sits with the executable on Windows and Linux and in the
    bundle's resources folder on macOS, which is the same question
    ``engine.bundle_extra_roots`` already answers for ffmpeg.
    """
    from s_q_ali_media_downloader.engine import bundle_extra_roots

    if not getattr(sys, "frozen", False):
        return None
    for root in bundle_extra_roots():
        candidate = Path(root) / BROWSER_DIR_NAME
        if candidate.is_dir():
            return candidate
    return None


def use_bundled_browsers() -> Path | None:
    """Point Playwright at the shipped browser. Returns the folder used."""
    folder = bundled_browsers_dir()
    if folder is None:
        return None
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(folder)
    logger.info("using the bundled browser in %s", folder)
    return folder


def default_profile_dir() -> Path:
    """The persistent browser profile, next to the queue and the downloads."""
    from s_q_ali_media_downloader.engine import app_storage_dir

    return Path(app_storage_dir()) / PROFILE_DIR_NAME


def _playwright_cache_dir() -> Path | None:
    """Where Playwright keeps the browsers it downloaded on this OS."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        return Path(local) / "ms-playwright" if local else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "ms-playwright"


def _playwright_browser_roots() -> list[Path]:
    roots: list[Path] = []
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured:
        roots.append(Path(configured))
    bundled = bundled_browsers_dir()
    if bundled is not None:
        roots.append(bundled)
    default = _playwright_cache_dir()
    if default is not None:
        roots.append(default)
    return roots


#: Where the full Chromium sits inside a Playwright cache folder, for every
#: platform Playwright names. The POSIX names changed when it started
#: shipping "Google Chrome for Testing" instead of a plain Chromium, and the
#: architecture moved into the folder name, so the old spellings are kept.
CHROMIUM_LAYOUTS: tuple[str, ...] = (
    "chrome-win64/chrome.exe",
    "chrome-win/chrome.exe",
    "chrome-linux64/chrome",
    "chrome-linux-arm64/chrome",
    "chrome-linux/chrome",
    "chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
)


def _chromium_executable(root: Path) -> Path | None:
    """The full Chromium in a Playwright cache, not the headless shell."""
    for folder in sorted(root.glob("chromium-*")):
        if not folder.is_dir() or "headless_shell" in folder.name:
            continue
        for relative in CHROMIUM_LAYOUTS:
            exe = folder / relative
            if exe.is_file():
                return exe
    return None


def browser_executable() -> Path | None:
    """The browser the AI agent should launch.

    The same order as ``browser_channels()``: real Chrome, then Edge on
    Windows, then the full Playwright Chromium the app ships. ``None`` lets
    browser-use find its own browser.
    """
    if sys.platform == "win32":
        roots = (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        )
        for name in (
            "Google/Chrome/Application/chrome.exe",
            "Microsoft/Edge/Application/msedge.exe",
        ):
            for root in roots:
                if not root:
                    continue
                exe = Path(root) / name
                if exe.is_file():
                    return exe
    elif sys.platform == "darwin":
        for name in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ):
            exe = Path(name)
            if exe.is_file():
                return exe
    else:
        for name in ("google-chrome", "microsoft-edge", "chromium", "chromium-browser"):
            found = shutil.which(name)
            if found:
                return Path(found)
    for root in _playwright_browser_roots():
        exe = _chromium_executable(root)
        if exe is not None:
            return exe
    return None


class BrowserSession:
    """One browser, one context, many pages."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        settle_ms: int = SETTLE_MS,
        user_agent: str | None = None,
        locale: str = "en-US",
        profile_dir: str | os.PathLike | None = None,
        channel: str | None = None,
    ):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.settle_ms = settle_ms
        self.user_agent = user_agent
        self.locale = locale
        self.profile_dir = profile_dir
        self.channel = channel
        self._playwright = None
        self._browser = None
        self._context = None

    # ------------------------------------------------------------------ #
    # Life cycle
    # ------------------------------------------------------------------ #
    @property
    def browser(self):
        """The running browser, or None when the session is closed."""
        return self._browser

    def start(self) -> BrowserSession:
        """Start the browser. Raises BrowserUnavailable when there is none."""
        if self._context is not None:
            return self
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise BrowserUnavailable(
                "Playwright is not installed. Install it with "
                "'pip install playwright' and 'playwright install chromium' "
                "(or just use the browser this machine already has)."
            ) from exc

        self._playwright = sync_playwright().start()
        use_bundled_browsers()
        channels = (self.channel,) if self.channel else browser_channels()
        profile = Path(self.profile_dir) if self.profile_dir else None
        if profile is not None:
            profile.mkdir(parents=True, exist_ok=True)
        context_args = {
            "locale": self.locale,
            "viewport": {"width": 1280, "height": 900},
            **({"user_agent": self.user_agent} if self.user_agent else {}),
        }

        errors: list[str] = []
        for channel in channels:
            try:
                if profile is not None:
                    self._context = self._playwright.chromium.launch_persistent_context(
                        str(profile),
                        channel=channel,
                        headless=self.headless,
                        args=launch_args(),
                        **context_args,
                    )
                    self._browser = getattr(self._context, "browser", None)
                else:
                    self._browser = self._playwright.chromium.launch(
                        channel=channel,
                        headless=self.headless,
                        args=launch_args(),
                    )
                    self._context = self._browser.new_context(**context_args)
                harden(self._context)
                logger.info(
                    "browser started (channel=%r, profile=%s, headless=%s)",
                    channel,
                    profile,
                    self.headless,
                )
                break
            except Exception as exc:
                errors.append(f"{channel or 'chromium'}: {exc}")
        if self._context is None:
            self.close()
            raise BrowserUnavailable(
                "No usable browser was found. Tried: " + "; ".join(errors)
            )
        return self

    def close(self) -> None:
        """Close the browser. Safe to call twice."""
        for closer in (
            getattr(self._context, "close", None),
            getattr(self._browser, "close", None),
            getattr(self._playwright, "stop", None),
        ):
            if closer is None:
                continue
            try:
                closer()
            except Exception as exc:
                logger.debug("browser close failed: %s", exc)
        self._context = None
        self._browser = None
        self._playwright = None

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Pages
    # ------------------------------------------------------------------ #
    def open(self, url: str, *, wait_ms: int | None = None) -> Page:
        """Open a URL and read what the rendered page shows.

        Raises PageUnavailable when the page cannot be read — the caller
        turns that into "unknown", never into "not found".
        """
        if self._context is None:
            self.start()
        page = self._context.new_page()
        try:
            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )
            except Exception as exc:
                raise PageUnavailable(f"Could not open {url}: {exc}") from exc

            page.wait_for_timeout(self.settle_ms if wait_ms is None else wait_ms)
            self._pass_consent_wall(page, url)
            self._expand_youtube_about(page, url)
            return self._read(page, url)
        finally:
            try:
                page.close()
            except Exception as exc:
                logger.debug("closing the page failed: %s", exc)

    def _pass_consent_wall(self, page, url: str) -> None:
        """Get past YouTube's "Before you continue" wall.

        The wall appears on the first visit from a fresh browser profile.
        Accepting it sets a cookie, so the page can simply be re-read.
        """
        try:
            if CONSENT_TITLE.lower() not in (page.title() or "").lower():
                return
        except Exception:
            return
        for selector in CONSENT_SELECTORS:
            try:
                page.click(selector, timeout=4000)
            except Exception as exc:
                logger.debug("consent button %r not clickable: %s", selector, exc)
                continue
            page.wait_for_timeout(1500)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_timeout(self.settle_ms)
            except Exception as exc:
                raise PageUnavailable(f"Could not re-read {url}: {exc}") from exc
            return

    def _expand_youtube_about(self, page, url: str) -> None:
        """Open YouTube's channel About modal when visiting a channel /about URL."""
        if "youtube.com/" not in (url or "").lower():
            return
        for selector in (
            "yt-description-preview-view-model",
            "#page-header button[aria-label*='more']",
            "tp-yt-paper-button#more",
        ):
            try:
                page.click(selector, timeout=1500)
                page.wait_for_timeout(800)
                break
            except Exception:
                logger.debug("youtube about modal click skipped: %s", selector)

    def _read(self, page, url: str) -> Page:
        try:
            title = page.title()
        except Exception:
            title = ""
        try:
            text = page.inner_text("body")
        except Exception:
            text = ""
        links: list[str] = []
        try:
            hrefs = page.eval_on_selector_all("a[href]", _LINK_JS)
            for href in hrefs or []:
                links.append(str(href))
            if "youtube.com/" in (url or "").lower():
                for extra in page.evaluate(_YT_INITIAL_LINKS_JS) or []:
                    if extra and str(extra) not in links:
                        links.append(str(extra))
        except Exception:
            links = []
        meta: dict[str, str] = {}
        try:
            meta = {
                str(key): str(value)
                for key, value in (page.evaluate(_META_JS) or {}).items()
                if value
            }
        except Exception:
            meta = {}
        return Page(
            url=url,
            title=title or "",
            text=text or "",
            links=links,
            meta=meta,
        )


class RenderedProfileChecker:
    """A sync callable that reads one profile page in a persistent browser.

    The browser is started on first use, so a run whose HTTP probes are
    decisive never pays for it. The caller must use this from one thread;
    ``SocialVerifierTool`` gives it a single-worker executor.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        profile_dir: str | os.PathLike | None = None,
    ):
        self.headless = headless
        self.profile_dir = profile_dir
        self._session: BrowserSession | None = None

    def __call__(self, url: str) -> Page:
        if self._session is None:
            self._session = BrowserSession(
                headless=self.headless,
                profile_dir=self.profile_dir,
            ).start()
        return self._session.open(url)

    def close(self) -> None:
        session = self._session
        self._session = None
        if session is not None:
            session.close()
