"""Tests for the Research Settings page."""

import pytest
from PySide6.QtWidgets import QApplication

from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.ui import settings_page as sp


@pytest.fixture(autouse=True)
def _isolated_db(isolated_appdata):
    db.configure(None)
    yield
    db.close_db()


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def test_settings_page_reports_a_key_that_cannot_be_protected(_app, monkeypatch):
    """If Windows refuses to encrypt the key, the user has to be told — the
    value is not stored at all."""

    def boom(data, protect):
        raise OSError("The data is invalid")

    monkeypatch.setattr(db, "_dpapi_protect", boom)

    page = sp.SettingsPage()
    page._keys["groq_api_key"].setText("gsk-secret")
    page._save()

    assert "protect" in page._status.text().lower()
    assert db.get("SELECT value FROM settings WHERE key = 'groq_api_key'") is None


def test_settings_page_says_saved_when_the_key_is_protected(_app):
    page = sp.SettingsPage()
    page._keys["groq_api_key"].setText("gsk-secret")
    page._save()

    assert "saved" in page._status.text().lower()
    assert db.get_setting("groq_api_key") == "gsk-secret"
