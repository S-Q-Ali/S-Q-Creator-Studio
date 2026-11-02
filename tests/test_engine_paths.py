"""Where the app keeps its data, on every OS it runs on.

The storage folder is one decision shared by the downloads, the settings
database and the log file. The log resolved its own location, which is how it
ended up in a different folder from the data the user is asking about.
"""

import logging
import os

import pytest

from s_q_ali_media_downloader import engine
from s_q_ali_media_downloader.core import settings_store as db


@pytest.fixture(autouse=True)
def _store_resolves_from_the_environment():
    """Undo the suite-wide store pin so ``db_path()`` really resolves a path."""
    db.configure(None)
    yield
    db.configure(None)
    db.close_store()


def _fake_home(tmp_path, monkeypatch):
    """Point the home directory at a temp folder on Windows and POSIX alike."""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


# --------------------------------------------------------------------------- #
# The path itself
# --------------------------------------------------------------------------- #
def test_the_storage_dir_is_the_local_app_data_folder(isolated_appdata):
    """The shipped Windows path, byte for byte."""
    assert engine.app_storage_dir() == os.path.join(
        os.environ["LOCALAPPDATA"], engine.APP_NAME, "storage"
    )


def test_the_settings_database_lives_in_the_storage_dir(isolated_appdata):
    assert db.db_path() == os.path.join(
        engine.app_storage_dir(), "niche_research.db"
    )


def test_the_database_path_override_is_still_honoured(tmp_path, monkeypatch):
    target = tmp_path / "elsewhere.db"
    monkeypatch.setenv("SQ_DB_PATH", str(target))
    db.configure(None)
    assert db.db_path() == str(target)


def test_the_storage_dir_follows_the_os_data_folder(isolated_appdata, tmp_path, monkeypatch):
    """With no LOCALAPPDATA the folder sits in the OS data location.

    Falling back to the home directory, as it used to, left the data next to
    the user's documents on Linux and macOS.
    """
    from PySide6.QtCore import QStandardPaths

    _fake_home(tmp_path, monkeypatch)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    os_data = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericDataLocation
    )
    assert engine.app_storage_dir() == os.path.join(os_data, engine.APP_NAME, "storage")


# --------------------------------------------------------------------------- #
# A folder an early POSIX run left behind
# --------------------------------------------------------------------------- #
def test_a_data_folder_left_in_the_home_directory_is_moved(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, monkeypatch)
    legacy = home / engine.APP_NAME / "storage"
    legacy.mkdir(parents=True)
    (legacy / "niche_research.db").write_text("the stored keys")
    base = tmp_path / "osdata"
    base.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(base))

    engine.migrate_legacy_storage_dir()

    assert not legacy.exists()
    moved = base / engine.APP_NAME / "storage" / "niche_research.db"
    assert moved.read_text() == "the stored keys"


def test_the_move_leaves_a_current_folder_alone(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, monkeypatch)
    legacy = home / engine.APP_NAME / "storage"
    legacy.mkdir(parents=True)
    (legacy / "niche_research.db").write_text("old")
    base = tmp_path / "osdata"
    current = base / engine.APP_NAME / "storage"
    current.mkdir(parents=True)
    (current / "niche_research.db").write_text("current")
    monkeypatch.setenv("LOCALAPPDATA", str(base))

    engine.migrate_legacy_storage_dir()

    assert (legacy / "niche_research.db").read_text() == "old"
    assert (current / "niche_research.db").read_text() == "current"


# --------------------------------------------------------------------------- #
# The log lives with the data
# --------------------------------------------------------------------------- #
def test_the_log_file_lands_in_the_storage_dir(isolated_appdata):
    from s_q_ali_media_downloader import app as app_module

    root = logging.getLogger()
    before = list(root.handlers)
    level = root.level
    added = []
    try:
        app_module.setup_logging()
        added = [h for h in root.handlers if h not in before]
        assert os.path.isfile(os.path.join(engine.app_storage_dir(), "app.log"))
    finally:
        for handler in added:
            root.removeHandler(handler)
            handler.close()
        root.setLevel(level)
