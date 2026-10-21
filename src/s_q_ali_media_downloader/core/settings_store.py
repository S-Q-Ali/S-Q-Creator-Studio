"""The app's secret store: the API keys and the cookies file, kept in one
SQLite table, with the secrets sealed at rest by Windows DPAPI.

This module used to live in the research package. The research feature is
gone from the desktop app, but the Social Discovery feature reads the Groq
key from here, so the store stayed and moved up into ``core/``.

The database file keeps its old name and its old location on purpose: the
keys a user entered yesterday are in that file, sealed with an entropy value
that must never change. Renaming the file or the entropy would make every
stored key unreadable and the user would have to enter them again.

Override the location with the ``SQ_DB_PATH`` environment variable (or the
older ``NICHE_DB_PATH``); otherwise it lives next to the app's own storage
folder under ``LOCALAPPDATA\\S-Q-Ali Media Downloader\\storage``.
"""

from __future__ import annotations

import base64
import ctypes
import logging
import os
import sqlite3
import sys
import threading
import time
from collections.abc import Iterable, Sequence
from ctypes import wintypes
from typing import Any

logger = logging.getLogger(__name__)

# Secrets (``*_api_key`` settings) are sealed at rest with Windows DPAPI and
# stored as ``dpapi1:<base64>`` blobs. On non-Windows platforms they fall back
# to plaintext so the app stays portable. Everything is transparent through
# set_setting()/get_setting(); legacy plaintext rows are re-sealed on first read.
SEAL_PREFIX = "dpapi1:"
# Never change this: every key already sealed with it would become
# undecryptable and the user would have to re-enter all of them.
_SEAL_ENTROPY = b"S-Q-Ali Media Downloader\x00app\x00v1"

SCHEMA: str = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

_env_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_db_path: str | None = None


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_protect(data: bytes, protect: bool) -> bytes:
    raw = ctypes.create_string_buffer(data, len(data))
    blob = _DATA_BLOB(len(data), ctypes.cast(raw, ctypes.POINTER(ctypes.c_char)))
    ent = ctypes.create_string_buffer(_SEAL_ENTROPY, len(_SEAL_ENTROPY))
    entropy = _DATA_BLOB(
        len(_SEAL_ENTROPY), ctypes.cast(ent, ctypes.POINTER(ctypes.c_char))
    )
    out = _DATA_BLOB()
    # use_last_error: the error code has to come from the call that failed.
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    # CRYPTPROTECT_UI_FORBIDDEN (0x1): never prompt the user
    ok = fn(ctypes.byref(blob), None, ctypes.byref(entropy), None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    result = ctypes.string_at(out.pbData, out.cbData)
    ctypes.windll.kernel32.LocalFree(out.pbData)
    return result


def _seal(value: str) -> str:
    if sys.platform == "win32":
        try:
            sealed = _dpapi_protect(value.encode("utf-8"), protect=True)
        except OSError:
            # Fail closed: storing the secret in plain text would defeat the
            # sealing, and doing it silently would tell the user nothing.
            logger.error(
                "Windows refused to protect a secret setting — it was not stored. "
                "The user profile may be damaged."
            )
            raise
        return SEAL_PREFIX + base64.b64encode(sealed).decode("ascii")
    return value


def _unseal(value: str) -> str:
    if value.startswith(SEAL_PREFIX):
        if sys.platform != "win32":
            raise RuntimeError("Cannot decrypt DPAPI-sealed setting on this platform")
        raw = base64.b64decode(value[len(SEAL_PREFIX) :])
        return _dpapi_protect(raw, protect=False).decode("utf-8")
    return value


def _is_secret_key(key: str) -> bool:
    return key.endswith("_api_key")


def db_path() -> str:
    """Resolve the SQLite database file path."""
    global _db_path
    with _env_lock:
        if _db_path is None:
            env = os.environ.get("SQ_DB_PATH") or os.environ.get("NICHE_DB_PATH")
            if env:
                _db_path = env
            else:
                base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
                # The file name is the legacy one. The keys in it were sealed
                # for this exact file; a rename would only orphan them.
                _db_path = os.path.join(
                    base, "S-Q-Ali Media Downloader", "storage", "niche_research.db"
                )
        return _db_path


def configure(path: str | None) -> None:
    """Point the store at a specific file, or at ``None`` to resolve it again."""
    global _conn, _db_path
    with _env_lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        _db_path = path


def _connect() -> sqlite3.Connection:
    """Return the shared connection, opening it once.

    The lock is taken here as well: two worker threads reaching the store at
    the same time used to both see ``_conn is None``, open a second
    connection and race each other.
    """
    global _conn
    with _env_lock:
        if _conn is None:
            path = db_path()
            folder = os.path.dirname(path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            _conn = sqlite3.connect(path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode = WAL;")
            _conn.execute("PRAGMA busy_timeout = 5000;")
            _conn.executescript(SCHEMA)
        return _conn


def _run(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    conn = _connect()
    with _env_lock:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def set_setting(key: str, value: str) -> None:
    """Store a setting. A key that ends in ``_api_key`` is sealed at rest."""
    _run(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, _seal(value) if _is_secret_key(key) else value),
    )


def get_setting(key: str) -> str | None:
    """Read a setting. A sealed secret comes back in plain text, or ``None``
    when this account cannot unseal it."""
    row = _run("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    value: str = row["value"]
    if _is_secret_key(key):
        if not value.startswith(SEAL_PREFIX):
            # Legacy plaintext row — seal it now and keep returning plaintext.
            try:
                sealed = _seal(value)
                if sealed != value:
                    _run("UPDATE settings SET value = ? WHERE key = ?", (sealed, key))
            except Exception:
                logger.warning("Failed to seal legacy setting %s", key, exc_info=True)
            return value
        try:
            return _unseal(value)
        except Exception as exc:
            # DPAPI is user-scoped: a database copied from another account
            # cannot be decrypted. Returning None asks the user to re-enter
            # the key; raising here would stop the app from starting.
            logger.error("Stored secret %s cannot be decrypted on this account", key)
            logger.debug("Decrypt failure for %s: %s", key, exc)
            return None
    return value


def secret_is_unreadable(key: str) -> bool:
    """True when a sealed secret exists but cannot be decrypted on this account.

    The Settings page uses this to ask for the key again instead of showing
    an empty field with no explanation.
    """
    if not _is_secret_key(key):
        return False
    row = _run("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return False
    value = row["value"]
    if not value.startswith(SEAL_PREFIX):
        return False
    try:
        _unseal(value)
    except Exception:
        return True
    return False


def close_store() -> None:
    """Close the connection and forget the resolved path."""
    global _conn, _db_path
    with _env_lock:
        if _conn is not None:
            try:
                _conn.close()
            except sqlite3.Error:
                pass
            _conn = None
        _db_path = None


# --------------------------------------------------------------------------
# The plain SQL helpers. The store owns the connection, so anything that needs
# to read or write a row goes through here rather than opening its own.
# --------------------------------------------------------------------------


def run(sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
    """Run a statement and commit it."""
    conn = _connect()
    with _env_lock:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def all(sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Run a query and return every row as a dict."""
    conn = _connect()
    with _env_lock:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get(sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    """Run a query and return the first row as a dict, or ``None``."""
    conn = _connect()
    with _env_lock:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def exec_many(sql: str, seq: Iterable[Sequence[Any]]) -> None:
    """Run one statement for every item in ``seq``."""
    conn = _connect()
    with _env_lock:
        conn.executemany(sql, seq)
        conn.commit()


def now() -> int:
    """Current unix time in milliseconds."""
    return int(time.time() * 1000)
