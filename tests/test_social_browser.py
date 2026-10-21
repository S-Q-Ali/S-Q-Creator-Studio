"""Tests for the browser session used by the Social Discovery feature.

The real pages (Instagram, TikTok, Facebook, the YouTube About page) only
tell the truth when they are rendered, so the feature drives a real browser.
These tests use a local HTML file so they need no network; a test that
needs a browser is skipped when the machine has none.
"""

from __future__ import annotations

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
