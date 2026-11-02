"""The app's secret store: the API keys and the cookies file, kept in one
SQLite table, with the secrets sealed at rest by the operating system.

This module used to live in the research package. The research feature is
gone from the desktop app, but the Social Discovery feature reads the Groq
key from here, so the store stayed and moved up into ``core/``.

Three sealing backends, chosen once per process by ``_secret_backend()``:

``dpapi``     Windows. The blob stays in the row, tied to this user account.
``keyring``   Linux and macOS. The secret goes to the OS keychain through the
              ``keyring`` package; the row keeps only the item's name.
``plain``     No secret store on this machine (a headless Linux box without a
              keyring daemon, for instance). The value is stored with a
              ``plain:`` marker and a warning is logged — naming the key, never
              the value — so the row is honest about what it holds.

The database file keeps its old name and its old location on purpose: the
keys a user entered yesterday are in that file, sealed with an entropy value
that must never change. Renaming the file or the entropy would make every
stored key unreadable and the user would have to enter them again.

Override the location with the ``SQ_DB_PATH`` environment variable (or the
older ``NICHE_DB_PATH``); otherwise it lives in the app's own storage folder,
which ``engine.app_storage_dir()`` resolves for the running OS.
"""

from __future__ import annotations

import base64
import logging
import os
import sqlite3
import sys
import threading

logger = logging.getLogger(__name__)

# Secrets (``*_api_key`` settings) are sealed at rest and stored with a marker
# that says which backend sealed them: ``dpapi1:<base64>`` blob,
# ``keyring1:<item name>`` or ``plain:<value>``. Everything is transparent
# through set_setting()/get_setting(); a legacy unmarked plaintext row is
# re-sealed on the first read.
SEAL_DPAPI = "dpapi1:"
SEAL_KEYRING = "keyring1:"
SEAL_PLAIN = "plain:"
SEALS = (SEAL_DPAPI, SEAL_KEYRING, SEAL_PLAIN)

# The service name the OS keychain files this app's secrets under. The per-key
# item name is built from the setting key, so a row says where to look for its
# secret without holding it.
KEYRING_SERVICE = "S-Q-Ali Media Downloader"

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
_backend_choice: str | None = None


if sys.platform == "win32":
    # ctypes.wintypes raises on Linux and macOS, and importing it at module
    # level used to make the whole store — and the Settings page with it —
    # unimportable off Windows.
    import ctypes
    from ctypes import wintypes

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


def _keyring_available() -> bool:
    """True when the ``keyring`` package found a usable OS secret store.

    A headless Linux session with no Secret Service daemon raises here, and a
    machine without the package raises at import; both mean no keychain.
    """
    try:
        import keyring

        # A frozen (PyInstaller) build loses keyring's entry-point discovery,
        # so the backend this OS uses is imported by name before asking for it
        # (jaraco/keyring#324).
        if sys.platform == "darwin":
            import keyring.backends.macOS
        elif sys.platform.startswith("linux"):
            import keyring.backends.SecretService
        keyring.get_keyring()
    except Exception:
        return False
    return True


def _detect_secret_backend() -> str:
    if sys.platform == "win32":
        return "dpapi"
    if _keyring_available():
        return "keyring"
    return "plain"


def _secret_backend() -> str:
    """The backend this machine gets, decided once and cached."""
    global _backend_choice
    with _env_lock:
        if _backend_choice is None:
            _backend_choice = _detect_secret_backend()
        return _backend_choice


def secret_backend_name() -> str:
    """Which sealing backend this machine uses: ``dpapi``, ``keyring`` or
    ``plain``. The Settings page words its notices with this."""
    return _secret_backend()


def _keyring_store(username: str, value: str) -> None:
    import keyring

    keyring.set_password(KEYRING_SERVICE, username, value)


def _keyring_fetch(username: str) -> str:
    import keyring

    secret = keyring.get_password(KEYRING_SERVICE, username)
    if secret is None:
        raise RuntimeError(f"no keychain item for {username}")
    return secret


def _keyring_item(key: str) -> str:
    return f"s-q-ali-media-downloader/{key}"


def _seal(key: str, value: str) -> str:
    backend = _secret_backend()
    if backend == "dpapi":
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
        return SEAL_DPAPI + base64.b64encode(sealed).decode("ascii")
    if backend == "keyring":
        item = _keyring_item(key)
        try:
            _keyring_store(item, value)
        except Exception:
            # A locked or missing keychain is not a reason to lose the key the
            # user just typed: store it, mark the row, and say what happened.
            logger.warning(
                "The OS keychain refused to store %s; it was saved unencrypted "
                "in the settings database.",
                key,
            )
            return SEAL_PLAIN + value
        return SEAL_KEYRING + item
    logger.warning(
        "%s was saved unencrypted in the settings database: this OS has no "
        "secret store available.",
        key,
    )
    return SEAL_PLAIN + value


def _unseal(value: str) -> str:
    if value.startswith(SEAL_DPAPI):
        if sys.platform != "win32":
            raise RuntimeError("Cannot decrypt a DPAPI-sealed setting on this platform")
        raw = base64.b64decode(value[len(SEAL_DPAPI) :])
        return _dpapi_protect(raw, protect=False).decode("utf-8")
    if value.startswith(SEAL_KEYRING):
        return _keyring_fetch(value[len(SEAL_KEYRING) :])
    if value.startswith(SEAL_PLAIN):
        return value[len(SEAL_PLAIN) :]
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
                # The storage folder is the engine's decision, so the database,
                # the downloads and the log all live in one place on every OS.
                from s_q_ali_media_downloader.engine import app_storage_dir

                # The file name is the legacy one. The keys in it were sealed
                # for this exact file; a rename would only orphan them.
                _db_path = os.path.join(app_storage_dir(), "niche_research.db")
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
        (key, _seal(key, value) if _is_secret_key(key) else value),
    )


def get_setting(key: str) -> str | None:
    """Read a setting. A sealed secret comes back in plain text, or ``None``
    when this account cannot unseal it.

    Always returns a value or None; never raises. This is critical because
    the Settings page reads every key during startup, and an exception would
    prevent the app from launching.
    """
    try:
        row = _run("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        value: str = row["value"]
        if _is_secret_key(key):
            if not value.startswith(SEALS):
                # Legacy plaintext row — seal it now and keep returning plaintext.
                try:
                    sealed = _seal(key, value)
                    if sealed != value:
                        _run("UPDATE settings SET value = ? WHERE key = ?", (sealed, key))
                except Exception:
                    logger.warning("Failed to seal legacy setting %s", key, exc_info=True)
                return value
            secret = _unseal(value)
            if value.startswith(SEAL_PLAIN) and _secret_backend() != "plain":
                # This machine has a secret store now — the key was saved plain
                # on a headless first run. Move it in and stop the row carrying it.
                try:
                    _run(
                        "UPDATE settings SET value = ? WHERE key = ?",
                        (_seal(key, secret), key),
                    )
                except Exception:
                    logger.warning(
                        "Failed to move %s out of the settings database", key, exc_info=True
                    )
            return secret
        return value
    except Exception as exc:
        # A sealed row can be unreadable: a DPAPI blob is tied to the Windows
        # account that made it, and a keychain item does not travel with the
        # database file. Returning None asks the user to re-enter the key;
        # raising here would stop the app from starting.
        if _is_secret_key(key):
            logger.error("Stored secret %s cannot be read on this machine", key)
            logger.debug("Unseal failure for %s: %s", key, exc)
            return None
        # Non-secret key failed to read — log and return None.
        logger.error("Failed to read setting %s: %s", key, exc)
        return None


def secret_is_unreadable(key: str) -> bool:
    """True when a sealed secret exists but cannot be read on this machine.

    The Settings page uses this to ask for the key again instead of showing
    an empty field with no explanation.
    """
    if not _is_secret_key(key):
        return False
    row = _run("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return False
    value = row["value"]
    if not value.startswith(SEALS):
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
