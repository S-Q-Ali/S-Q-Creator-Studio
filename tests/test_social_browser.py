"""Tests for the browser session used by the Social Discovery feature.

The real pages (Instagram, TikTok, Facebook, the YouTube About page) only
tell the truth when they are rendered, so the feature drives a real browser.
These tests use a local HTML file so they need no network; a test that
needs a browser is skipped when the machine has none.
"""

from __future__ import annotations

import os

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
