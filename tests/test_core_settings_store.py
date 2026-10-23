"""Tests for the app's secret store."""

import os
import sys

import pytest

from s_q_ali_media_downloader.core import settings_store as db


@pytest.fixture(autouse=True)
def _isolated_db(isolated_appdata):
    db.configure(None)
    yield
    db.close_store()


def test_schema_creates_the_settings_table():
    # The connection is shared and module-owned: the fixture closes it.
    conn = db._connect()
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "settings" in tables


def test_a_key_written_by_the_older_module_still_reads_back():
    """The store moved out of the research package. The file, the table and
    the key are the same, so a key the user entered before the move still
    works — that is the whole point of not renaming the file."""
    conn = db._connect()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("youtube_api_key", "AIzaWrittenByTheOldModule"),
    )
    conn.commit()

    assert db.get_setting("youtube_api_key") == "AIzaWrittenByTheOldModule"


def test_the_database_file_keeps_its_name_and_place():
    """Renaming the file would orphan every stored key."""
    path = db.db_path()
    assert path.endswith("niche_research.db")
    assert path.endswith(os.path.join("S-Q-Ali Media Downloader", "storage", "niche_research.db"))


def test_settings_roundtrip():
    db.set_setting("youtube_api_key", "AIzaSyABC")
    assert db.get_setting("youtube_api_key") == "AIzaSyABC"


# --------------------------------------------------------------------------- #
# Regression (2026-10): a sealed key must never take the app down
# --------------------------------------------------------------------------- #
def test_get_setting_returns_none_when_a_sealed_key_cannot_be_decrypted(monkeypatch):
    """DPAPI is user-scoped: a database copied to another account cannot be
    decrypted. The Settings page reads every key while the window is being
    built, so an unhandled error here stopped the app from starting."""
    db.set_setting("groq_api_key", "gsk-secret")

    def boom(value):
        raise OSError("The data is invalid")

    monkeypatch.setattr(db, "_unseal", boom)

    assert db.get_setting("groq_api_key") is None


