"""A real browser for the pages that only tell the truth when rendered.

Instagram, TikTok and Facebook answer a plain HTTP request with the same
shell for a real profile and for a made-up one — verified 2026-10-21: a
non-existent Instagram profile and a real one both returned the same
590 KB page. A rendered page does tell them apart ("Profile isn't
available", the login wall, "Couldn't find this account"), so the Social
Discovery feature drives a browser.

Two things make that practical in a desktop app:

* The browser Windows already has is used first — real Chrome, then Edge —
  so nothing has to be downloaded. The shipped Playwright Chromium is the
  fallback.
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

#: The browsers to try, in order. Real Chrome and Edge keep the sign-in the
#: user already has; ``"chromium"`` is the full Playwright Chromium (it runs
#: both headless and windowed), and ``None`` is its headless shell.
BROWSER_CHANNELS: tuple[str | None, ...] = ("chrome", "msedge", "chromium", None)

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


def bundled_browsers_dir() -> Path | None:
    """The browser folder that ships with the app, if it is there.

    The installer carries the full Chromium, so the feature works on a
    machine that has no Edge and no Chrome, in both headless and windowed
    mode. Playwright looks for browsers in its own cache, so the
    environment variable has to point at the shipped copy before Playwright
    starts.
    """
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / BROWSER_DIR_NAME)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / BROWSER_DIR_NAME)
    for candidate in candidates:
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


def _playwright_browser_roots() -> list[Path]:
    roots: list[Path] = []
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured:
        roots.append(Path(configured))
    bundled = bundled_browsers_dir()
    if bundled is not None:
        roots.append(bundled)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "ms-playwright")
    return roots


def _chromium_executable(root: Path) -> Path | None:
    """The full Chromium in a Playwright cache, not the headless shell."""
    for folder in sorted(root.glob("chromium-*")):
        if not folder.is_dir() or "headless_shell" in folder.name:
            continue
        for relative in (
            "chrome-win64/chrome.exe",
            "chrome-win/chrome.exe",
            "chrome-linux/chrome",
            "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
        ):
            exe = folder / relative
            if exe.is_file():
                return exe
    return None


def browser_executable() -> Path | None:
    """The browser the AI agent should launch.

    The same order as ``BROWSER_CHANNELS``: real Chrome, then Edge, then the
    full Playwright Chromium the app ships. ``None`` lets browser-use find
    its own browser.
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
                "(or just use the browser Windows already has)."
            ) from exc

        self._playwright = sync_playwright().start()
        use_bundled_browsers()
        channels = (self.channel,) if self.channel else BROWSER_CHANNELS
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
                        args=list(STEALTH_ARGS),
                        **context_args,
                    )
                    self._browser = getattr(self._context, "browser", None)
                else:
                    self._browser = self._playwright.chromium.launch(
                        channel=channel,
                        headless=self.headless,
                        args=list(STEALTH_ARGS),
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
