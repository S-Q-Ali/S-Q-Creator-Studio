"""Tests for the sealing backends of the secret store (Phase C).

The store sealed keys with Windows DPAPI and, off Windows, wrote them in plain
text with no marker and no warning. These tests pin the three-backend design:
DPAPI on Windows, the OS keychain through `keyring` on Linux and macOS, and a
marked plain-text fallback when neither is available — plus the rule that a key
never reaches a log line.
"""

import base64
import importlib
import logging
import sys

import pytest

from s_q_ali_media_downloader.core import settings_store as db

SECRET = "gsk_live_SuperSecretKeyValue1234"


@pytest.fixture(autouse=True)
def _isolated_db(isolated_appdata):
    db.configure(None)
    yield
    db.close_store()


def raw_value(key: str) -> str:
    """The stored row, with no unsealing applied."""
    return db._run("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()["value"]


def use_keyring(monkeypatch, store: dict, errors: Exception | None = None):
    """A stand-in OS keychain: set_setting writes through it, get_setting reads."""

    def save(username, value):
        if errors is not None:
            raise errors
        store[username] = value

    def fetch(username):
        if username not in store:
            raise RuntimeError("no such item in the keyring")
        return store[username]

    monkeypatch.setattr(db, "_secret_backend", lambda: "keyring")
    monkeypatch.setattr(db, "_keyring_store", save)
    monkeypatch.setattr(db, "_keyring_fetch", fetch)


# --------------------------------------------------------------------------- #
# the keyring backend (Linux + macOS)
# --------------------------------------------------------------------------- #
def test_a_keyring_sealed_key_is_not_in_the_database_row(monkeypatch):
    store: dict[str, str] = {}
    use_keyring(monkeypatch, store)

    db.set_setting("groq_api_key", SECRET)

    assert raw_value("groq_api_key").startswith(db.SEAL_KEYRING)
    assert SECRET not in raw_value("groq_api_key")
    assert SECRET in store.values()


def test_a_keyring_sealed_key_reads_back(monkeypatch):
    store: dict[str, str] = {}
    use_keyring(monkeypatch, store)

    db.set_setting("groq_api_key", SECRET)

    assert db.get_setting("groq_api_key") == SECRET


def test_a_keyring_row_whose_item_is_gone_asks_for_the_key_again(monkeypatch):
    """The keychain entry can be deleted while the row survives — a new machine,
    a wiped login session. The app must ask, not crash and not store a blank."""
    monkeypatch.setattr(db, "_secret_backend", lambda: "keyring")
    monkeypatch.setattr(db, "_keyring_store", lambda username, value: None)
    monkeypatch.setattr(db, "_keyring_fetch", lambda username: (_ for _ in ()).throw(RuntimeError("gone")))

    db.set_setting("groq_api_key", SECRET)

    assert db.get_setting("groq_api_key") is None
    assert db.secret_is_unreadable("groq_api_key") is True


def test_a_keyring_that_refuses_to_store_falls_back_to_a_marked_row(monkeypatch):
    """Saving must not fail because the OS secret store is broken; the user
    gets the key saved and told, rather than an error dialog."""
    monkeypatch.setattr(db, "_secret_backend", lambda: "keyring")
    monkeypatch.setattr(db, "_keyring_store", lambda username, value: (_ for _ in ()).throw(RuntimeError("locked")))

    db.set_setting("groq_api_key", SECRET)

    assert raw_value("groq_api_key") == db.SEAL_PLAIN + SECRET


# --------------------------------------------------------------------------- #
# no secret store at all
# --------------------------------------------------------------------------- #
def test_a_key_is_marked_plain_when_there_is_no_secret_store(monkeypatch, caplog):
    monkeypatch.setattr(db, "_secret_backend", lambda: "plain")

    with caplog.at_level(logging.WARNING):
        db.set_setting("groq_api_key", SECRET)

    assert raw_value("groq_api_key") == db.SEAL_PLAIN + SECRET
    assert db.get_setting("groq_api_key") == SECRET
    assert any("groq_api_key" in record.getMessage() for record in caplog.records)


def test_the_plain_fallback_warns_without_repeating_the_key(monkeypatch, caplog):
    monkeypatch.setattr(db, "_secret_backend", lambda: "plain")

    with caplog.at_level(logging.DEBUG):
        db.set_setting("groq_api_key", SECRET)
        assert db.get_setting("groq_api_key") == SECRET

    assert SECRET not in caplog.text


# --------------------------------------------------------------------------- #
# DPAPI, the backend Windows already uses
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_a_dpapi_sealed_key_still_round_trips():
    db.set_setting("groq_api_key", SECRET)

    assert raw_value("groq_api_key").startswith(db.SEAL_DPAPI)
    assert SECRET not in raw_value("groq_api_key")
    assert db.get_setting("groq_api_key") == SECRET


def test_a_dpapi_row_from_another_machine_reports_unreadable():
    """DPAPI blobs are user- and machine-scoped. A database copied from another
    account can never decrypt, and the store says so instead of returning the
    blob as if it were the key."""
    blob = base64.b64encode(b"not-a-real-dpapi-blob").decode("ascii")
    db._run(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("groq_api_key", db.SEAL_DPAPI + blob),
    )

    assert db.get_setting("groq_api_key") is None
    assert db.secret_is_unreadable("groq_api_key") is True


# --------------------------------------------------------------------------- #
# legacy rows and non-secret settings
# --------------------------------------------------------------------------- #
def test_a_legacy_plaintext_row_is_sealed_on_the_first_read(monkeypatch):
    store: dict[str, str] = {}
    db._run(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("youtube_api_key", SECRET),
    )
    use_keyring(monkeypatch, store)

    assert db.get_setting("youtube_api_key") == SECRET
    assert raw_value("youtube_api_key").startswith(db.SEAL_KEYRING)
    assert SECRET not in raw_value("youtube_api_key")


def test_a_plain_row_is_upgraded_once_a_keychain_appears(monkeypatch):
    """A headless first run has no keychain and marks the row `plain:`. When the
    same database is later opened somewhere that does have one, the key moves
    into the keychain and the row stops carrying it."""
    db._run(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("youtube_api_key", db.SEAL_PLAIN + SECRET),
    )
    store: dict[str, str] = {}
    use_keyring(monkeypatch, store)

    assert db.get_setting("youtube_api_key") == SECRET
    assert raw_value("youtube_api_key").startswith(db.SEAL_KEYRING)
    assert SECRET not in raw_value("youtube_api_key")


def test_ordinary_settings_are_stored_as_they_are_given():
    """Only keys that end in _api_key are secrets. A folder path must stay
    readable in the row, or the app cannot show it in Settings."""
    db.set_setting("music_output_dir", r"E:\Videos\Music")

    assert raw_value("music_output_dir") == r"E:\Videos\Music"


# --------------------------------------------------------------------------- #
# which backend this machine gets
# --------------------------------------------------------------------------- #
def test_windows_keeps_using_dpapi(monkeypatch):
    monkeypatch.setattr(db, "_keyring_available", lambda: True)
    assert db._detect_secret_backend() == "dpapi"


def test_a_machine_with_a_keychain_uses_it(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(db, "_keyring_available", lambda: True)
    assert db._detect_secret_backend() == "keyring"


def test_a_machine_without_a_keychain_says_plain(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(db, "_keyring_available", lambda: False)
    assert db._detect_secret_backend() == "plain"


def test_the_store_can_be_imported_without_windows_ctypes(monkeypatch):
    """`from ctypes import wintypes` raises on Linux and macOS, so the whole
    module — the settings page included — failed to import off Windows. The
    Windows-specific structures must be built only when the OS has DPAPI."""
    blocker = _BlockWindowsCtypes()
    db.close_store()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delitem(sys.modules, "ctypes.wintypes", raising=False)
    sys.meta_path.insert(0, blocker)
    try:
        module = importlib.reload(db)
        assert module._detect_secret_backend() == "plain"
    finally:
        sys.meta_path.remove(blocker)
        monkeypatch.undo()
        db.close_store()
        importlib.reload(db)


class _BlockWindowsCtypes:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "ctypes.wintypes":
            raise ImportError("ctypes.wintypes is Windows-only")
