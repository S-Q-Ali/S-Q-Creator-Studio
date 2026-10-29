"""Tests for the browser hardening.

The pages the app opens are read by platforms that check for automation, so
the browser must not say it is automated. These tests use a local HTML file,
so they need no network; a test that needs a browser is skipped when the
machine has none.
"""

from __future__ import annotations

import pytest

from s_q_ali_media_downloader.agent.tools import browser as br
from s_q_ali_media_downloader.agent.tools import stealth


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


def test_the_launch_flags_hide_the_automation_tell():
    """Chrome sets navigator.webdriver from this flag; without it the flag
    is exactly what a bot check reads first."""
    assert "--disable-blink-features=AutomationControlled" in stealth.STEALTH_ARGS


def test_the_init_script_hides_the_automation_tell():
    assert "webdriver" in stealth.STEALTH_INIT_JS


def test_harden_installs_the_script_on_the_context():
    class FakeContext:
        def __init__(self):
            self.scripts = []

        def add_init_script(self, script):
            self.scripts.append(script)

    context = FakeContext()
    stealth.harden(context)

    assert len(context.scripts) == 1
    assert "webdriver" in context.scripts[0]


def test_the_session_starts_with_the_hardened_flags(tmp_path, monkeypatch):
    """The flags and the script reach the browser, not just the module."""
    launched = {}

    class FakeContext:
        def __init__(self):
            self.scripts = []

        def add_init_script(self, script):
            self.scripts.append(script)

    class FakeChromium:
        def launch_persistent_context(self, profile, **kwargs):
            launched.update(kwargs)
            return FakeContext()

        def launch(self, **kwargs):
            launched.update(kwargs)
            return FakeContext()

    class FakePlaywright:
        def __init__(self):
            self.chromium = FakeChromium()

        def stop(self):
            pass

    class FakeContextManager:
        def start(self):
            return FakePlaywright()

    monkeypatch.setattr(
        "playwright.sync_api.sync_playwright", lambda: FakeContextManager()
    )

    session = br.BrowserSession(profile_dir=tmp_path / "profile")
    session.start()
    try:
        assert list(stealth.STEALTH_ARGS) == launched["args"]
        assert session._context.scripts == [stealth.STEALTH_INIT_JS]
    finally:
        session.close()


def test_a_page_cannot_tell_the_browser_is_automated(tmp_path, _browser):
    """The whole point: a page must not see the automation tell."""
    from playwright import sync_api

    page_file = tmp_path / "page.html"
    page_file.write_text("<html><body><h1>hello</h1></body></html>", encoding="utf-8")

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome", headless=False, args=list(stealth.STEALTH_ARGS)
        )
        try:
            context = browser.new_context()
            stealth.harden(context)
            page = context.new_page()
            page.goto(page_file.as_uri())
            webdriver = page.evaluate("() => navigator.webdriver")
        finally:
            browser.close()

    assert webdriver is not True
