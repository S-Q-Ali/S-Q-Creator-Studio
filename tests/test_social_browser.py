"""Tests for the browser session used by the Social Discovery feature.

The real pages (Instagram, TikTok, Facebook, the YouTube About page) only
tell the truth when they are rendered, so the feature drives a real browser.
These tests use a local HTML file so they need no network; a test that
needs a browser is skipped when the machine has none.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

from s_q_ali_media_downloader.agent.tools import browser as br


@pytest.fixture(scope="module")
def _browser():
    """Skip the whole module when no usable browser is installed."""
    try:
        session = br.BrowserSession()
        session.start()
    except br.BrowserUnavailable as exc:
        pytest.skip(f"no browser available: {exc}")
    session.close()
    return True


def test_open_reads_the_rendered_title_text_and_links(tmp_path, _browser):
    page_file = tmp_path / "page.html"
    page_file.write_text(
        "<html><head><title>Hello</title></head>"
        "<body><h1>Rendered heading</h1>"
        '<a href="https://social.test/handle">social</a></body></html>',
        encoding="utf-8",
    )

    with br.BrowserSession() as session:
        page = session.open(page_file.as_uri())

    assert page.title == "Hello"
    assert "Rendered heading" in page.text
    assert "https://social.test/handle" in page.links


def test_open_reports_a_page_it_cannot_load(tmp_path, _browser):
    """A page that cannot be opened is one error type, so the caller can
    turn it into "unknown" instead of "not found"."""
    missing = tmp_path / "does-not-exist.html"

    with br.BrowserSession() as session, pytest.raises(br.PageUnavailable):
        session.open(missing.as_uri())


def test_the_session_closes_the_browser_even_when_a_page_fails(_browser):
    session = br.BrowserSession()
    session.start()
    browser = session.browser
    assert browser is not None

    session.close()

    assert session.browser is None
    assert browser.is_connected() is False


def test_the_session_can_be_used_as_a_context_manager(_browser):
    with br.BrowserSession() as session:
        assert session.browser is not None
    assert session.browser is None


def test_a_missing_playwright_is_reported_clearly(monkeypatch):
    """Playwright is an optional dependency: the feature has to say what to
    install, not crash with an ImportError."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(br.BrowserUnavailable) as excinfo:
        br.BrowserSession().start()

    assert "playwright" in str(excinfo.value).lower()


# --------------------------------------------------------------------------- #
# The browser that ships with the app
# --------------------------------------------------------------------------- #
def test_the_browser_folder_is_looked_for_next_to_the_exe(tmp_path, monkeypatch):
    """The installer carries Chromium, so the feature works on a machine that
    has no Edge and no Chrome."""
    (tmp_path / "browsers").mkdir()
    monkeypatch.setattr(br.sys, "frozen", True, raising=False)
    monkeypatch.setattr(br.sys, "executable", str(tmp_path / "S-Q Creator Studio.exe"))

    assert br.bundled_browsers_dir() == tmp_path / "browsers"


def test_the_shipped_browser_is_pointed_at(monkeypatch, tmp_path):
    """Playwright looks for browsers in its own cache; the app has to point
    it at the copy it ships."""
    browsers = tmp_path / "browsers"
    (browsers / "chromium_headless_shell-1248").mkdir(parents=True)
    monkeypatch.setattr(br, "bundled_browsers_dir", lambda: browsers)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    assert br.use_bundled_browsers() == browsers
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(browsers)


def test_without_a_shipped_browser_the_environment_is_left_alone(monkeypatch):
    monkeypatch.setattr(br, "bundled_browsers_dir", lambda: None)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    assert br.use_bundled_browsers() is None
    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ


# --------------------------------------------------------------------------- #
# The persistent profile and the channel order (no real browser needed)
# --------------------------------------------------------------------------- #
class _FakeContext:
    def __init__(self):
        self.closed = False
        self.browser = None
        self.init_scripts = []

    def add_init_script(self, script):
        self.init_scripts.append(script)

    def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self):
        self.closed = False
        self.context_kwargs = None
        self.context = None

    def new_context(self, **kwargs):
        self.context_kwargs = kwargs
        self.context = _FakeContext()
        return self.context

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, fail_channels=()):
        self.fail_channels = set(fail_channels)
        self.launch_calls = []
        self.persistent_calls = []
        self.browser = _FakeBrowser()
        self.context = None

    def launch(self, **kwargs):
        self.launch_calls.append(kwargs)
        return self.browser

    def launch_persistent_context(self, user_data_dir, **kwargs):
        self.persistent_calls.append((user_data_dir, kwargs))
        if kwargs.get("channel") in self.fail_channels:
            raise RuntimeError("this channel is not installed")
        self.context = _FakeContext()
        return self.context


class _FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium
        self.stopped = False

    def stop(self):
        self.stopped = True


def _install_fake_playwright(monkeypatch, chromium):
    playwright = _FakePlaywright(chromium)
    module = types.SimpleNamespace(
        sync_playwright=lambda: types.SimpleNamespace(start=lambda: playwright)
    )
    monkeypatch.setitem(sys.modules, "playwright.sync_api", module)
    return playwright


def test_the_persistent_profile_is_used_and_chrome_is_tried_first(tmp_path, monkeypatch):
    chromium = _FakeChromium()
    _install_fake_playwright(monkeypatch, chromium)
    profile = tmp_path / "browser-profile"
    session = br.BrowserSession(profile_dir=profile, headless=False)

    session.start()

    assert profile.is_dir()
    assert len(chromium.persistent_calls) == 1
    used_dir, kwargs = chromium.persistent_calls[0]
    assert used_dir == str(profile)
    assert kwargs["channel"] == "chrome"
    assert kwargs["headless"] is False
    assert "--disable-blink-features=AutomationControlled" in kwargs["args"]
    assert chromium.context.init_scripts
    assert chromium.launch_calls == []
    session.close()


def test_edge_the_full_chromium_and_the_shell_are_the_fallbacks(tmp_path, monkeypatch):
    monkeypatch.setattr(br.sys, "platform", "win32")
    chromium = _FakeChromium(fail_channels={"chrome", "msedge", "chromium"})
    _install_fake_playwright(monkeypatch, chromium)
    session = br.BrowserSession(profile_dir=tmp_path / "profile")

    session.start()

    channels = [call[1]["channel"] for call in chromium.persistent_calls]
    assert channels == ["chrome", "msedge", "chromium", None]
    session.close()


def test_without_a_profile_a_fresh_context_is_used(monkeypatch):
    chromium = _FakeChromium()
    playwright = _install_fake_playwright(monkeypatch, chromium)
    session = br.BrowserSession()

    session.start()

    assert len(chromium.launch_calls) == 1
    assert chromium.launch_calls[0]["channel"] == "chrome"
    assert chromium.launch_calls[0]["headless"] is True
    assert "--disable-blink-features=AutomationControlled" in chromium.launch_calls[0]["args"]
    assert chromium.browser.context_kwargs["locale"] == "en-US"
    assert chromium.persistent_calls == []
    session.close()
    assert chromium.browser.closed is True
    assert playwright.stopped is True


def test_the_default_profile_lives_under_app_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert br.default_profile_dir() == (
        tmp_path / "S-Q-Ali Media Downloader" / "storage" / "browser-profile"
    )


def test_the_agent_browser_prefers_the_same_browser_as_the_session(tmp_path, monkeypatch):
    """The agent should read the page in the browser the user signed in to."""
    monkeypatch.setattr(br.sys, "platform", "win32")
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "pf"))
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "pf86"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    chrome = tmp_path / "pf" / "Google/Chrome/Application/chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.write_text("", encoding="utf-8")

    assert br.browser_executable() == chrome


def test_the_agent_browser_falls_back_to_the_shipped_chromium(tmp_path, monkeypatch):
    monkeypatch.setattr(br.sys, "platform", "win32")
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "empty"))
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "empty"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    browsers = tmp_path / "browsers"
    chromium = browsers / "chromium-1248" / "chrome-win64" / "chrome.exe"
    chromium.parent.mkdir(parents=True)
    chromium.write_text("", encoding="utf-8")
    (browsers / "chromium_headless_shell-1248").mkdir()
    monkeypatch.setattr(br, "bundled_browsers_dir", lambda: browsers)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    assert br.browser_executable() == chromium


def test_no_browser_for_the_agent_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(br.sys, "platform", "win32")
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "empty"))
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "empty"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(br, "bundled_browsers_dir", lambda: None)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    assert br.browser_executable() is None


def test_the_rendered_checker_reuses_one_session(tmp_path, monkeypatch):
    created = []
    closed = []

    class FakeSession:
        def __init__(self, **kwargs):
            created.append(kwargs)

        def start(self):
            return self

        def open(self, url):
            return br.Page(url=url)

        def close(self):
            closed.append(True)

    monkeypatch.setattr(br, "BrowserSession", FakeSession)
    checker = br.RenderedProfileChecker(headless=False, profile_dir=tmp_path)

    checker("https://example.com/a")
    checker("https://example.com/b")

    assert len(created) == 1
    assert created[0] == {"headless": False, "profile_dir": tmp_path}
    checker.close()
    assert closed == [True]


# --------------------------------------------------------------------------- #
# The browser this OS has, and the cache this OS keeps
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("win32", ("chrome", "msedge", "chromium", None)),
        ("darwin", ("chrome", "chromium", None)),
        ("linux", ("chrome", "chromium", None)),
    ],
)
def test_edge_is_only_tried_where_it_comes_preinstalled(monkeypatch, platform, expected):
    """Windows ships Edge; Linux and macOS usually do not.

    Asking for it anyway costs a failed launch whose message is then part of
    the "No usable browser was found" line the user has to read.
    """
    monkeypatch.setattr(br.sys, "platform", platform)

    assert br.browser_channels() == expected


@pytest.mark.parametrize(
    ("platform", "relative"),
    [("linux", ".cache/ms-playwright"), ("darwin", "Library/Caches/ms-playwright")],
)
def test_the_os_playwright_cache_is_searched_off_windows(
    tmp_path, monkeypatch, platform, relative
):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(br.sys, "platform", platform)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr(br, "bundled_browsers_dir", lambda: None)

    assert br._playwright_browser_roots() == [home / relative]


def test_the_xdg_cache_location_is_honoured(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setattr(br.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr(br, "bundled_browsers_dir", lambda: None)

    assert br._playwright_browser_roots() == [cache / "ms-playwright"]


def test_a_chromium_in_the_linux_cache_is_the_one_used(tmp_path, monkeypatch):
    """The browser the agent launches, found where Linux keeps it."""
    monkeypatch.setattr(br.sys, "platform", "linux")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr(br, "bundled_browsers_dir", lambda: None)
    monkeypatch.setattr(br.shutil, "which", lambda name: None)
    exe = tmp_path / ".cache/ms-playwright/chromium-1248/chrome-linux/chrome"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")

    assert br.browser_executable() == exe


@pytest.mark.parametrize(
    ("platform", "layout"),
    [
        ("linux", "chrome-linux64/chrome"),
        ("linux", "chrome-linux-arm64/chrome"),
        (
            "darwin",
            "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        ),
        (
            "darwin",
            "chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        ),
        ("win32", "chrome-win64/chrome.exe"),
    ],
)
def test_the_full_chromium_of_this_platform_is_found(
    tmp_path, monkeypatch, platform, layout
):
    """Playwright names the folder and the binary per platform, and the names
    changed when it started shipping "Google Chrome for Testing"."""
    monkeypatch.setattr(br.sys, "platform", platform)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    cache = tmp_path / "browsers"
    exe = cache / "chromium-1248" / layout
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(br, "bundled_browsers_dir", lambda: cache)

    assert br._chromium_executable(cache) == exe


# --------------------------------------------------------------------------- #
# Chromium's sandbox, for the sessions that cannot use it
# --------------------------------------------------------------------------- #
def test_a_root_session_gives_up_the_chromium_sandbox(monkeypatch):
    """CI containers and headless boxes run as root, where Chromium's sandbox
    refuses to start and the browser dies before it opens a page."""
    chromium = _FakeChromium()
    _install_fake_playwright(monkeypatch, chromium)
    monkeypatch.setattr(br.os, "geteuid", lambda: 0, raising=False)

    br.BrowserSession().start()

    assert "--no-sandbox" in chromium.launch_calls[0]["args"]


def test_an_ordinary_session_keeps_the_chromium_sandbox(monkeypatch):
    chromium = _FakeChromium()
    _install_fake_playwright(monkeypatch, chromium)
    monkeypatch.setattr(br.os, "geteuid", lambda: 1000, raising=False)

    br.BrowserSession().start()

    assert "--no-sandbox" not in chromium.launch_calls[0]["args"]
