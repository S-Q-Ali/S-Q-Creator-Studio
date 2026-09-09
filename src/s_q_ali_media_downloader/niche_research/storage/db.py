"""SQLite persistence for the Niche Research suite.

Schema is mirrored from the S-Q-Ali research web tool's lib/db.ts (node:sqlite) using the stdlib
sqlite3 module. Thread-safe: a single shared connection guarded by a lock.

Override the database location with the ``NICHE_DB_PATH`` environment variable
(used heavily by tests); otherwise it lives next to the app's own storage
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
# to plaintext so the suite stays portable. Everything is transparent through
# set_setting()/get_setting(); legacy plaintext rows are re-sealed on first read.
SEAL_PREFIX = "dpapi1:"
_SEAL_ENTROPY = b"S-Q-Ali Media Downloader\x00app\x00v1"


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
    crypt32 = ctypes.windll.crypt32
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
            return SEAL_PREFIX + base64.b64encode(sealed).decode("ascii")
        except (OSError, ctypes.WinError):
            return value
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

SCHEMA: str = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS keywords (
  term TEXT PRIMARY KEY,
  display_term TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  demand_score INTEGER NOT NULL DEFAULT 0,
  competition_score INTEGER NOT NULL DEFAULT 0,
  competition_label TEXT NOT NULL DEFAULT 'Low',
  source TEXT NOT NULL DEFAULT 'autocomplete',
  language TEXT,
  country TEXT,
  first_seen INTEGER NOT NULL,
  last_checked INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS keyword_snapshots (
  term TEXT NOT NULL,
  ts INTEGER NOT NULL,
  demand_score INTEGER,
  competition_score INTEGER,
  score INTEGER,
  PRIMARY KEY (term, ts)
);

CREATE TABLE IF NOT EXISTS channels (
  channel_id TEXT PRIMARY KEY,
  title TEXT,
  description TEXT,
  thumbnail_url TEXT,
  custom_url TEXT,
  country TEXT,
  published_at TEXT,
  subscriber_count INTEGER,
  video_count INTEGER,
  view_count INTEGER,
  channel_tags TEXT,
  topic_categories TEXT,
  last_fetched INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS channel_snapshots (
  channel_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  subscriber_count INTEGER,
  video_count INTEGER,
  view_count INTEGER,
  PRIMARY KEY (channel_id, ts)
);

CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY,
  channel_id TEXT,
  title TEXT,
  description TEXT,
  published_at TEXT,
  duration_seconds INTEGER,
  thumbnail_url TEXT,
  default_language TEXT,
  view_count INTEGER,
  like_count INTEGER,
  comment_count INTEGER,
  tags TEXT,
  category_id TEXT,
  last_fetched INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS video_snapshots (
  video_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  view_count INTEGER,
  like_count INTEGER,
  comment_count INTEGER,
  PRIMARY KEY (video_id, ts)
);

CREATE TABLE IF NOT EXISTS tracked_items (
  kind TEXT NOT NULL,
  ref_id TEXT NOT NULL,
  label TEXT,
  added_at INTEGER NOT NULL,
  PRIMARY KEY (kind, ref_id)
);

CREATE TABLE IF NOT EXISTS rankings (
  term TEXT NOT NULL,
  video_id TEXT NOT NULL,
  position INTEGER,
  ts INTEGER NOT NULL,
  PRIMARY KEY (term, video_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_video_snapshots_video ON video_snapshots(video_id);
CREATE INDEX IF NOT EXISTS idx_channel_snapshots_channel ON channel_snapshots(channel_id);
CREATE INDEX IF NOT EXISTS idx_keyword_snapshots_term ON keyword_snapshots(term);
CREATE INDEX IF NOT EXISTS idx_rankings_term ON rankings(term);

CREATE TABLE IF NOT EXISTS trending_channels (
  channel_id TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  thumbnail_url TEXT NOT NULL DEFAULT '',
  subscriber_count INTEGER NOT NULL DEFAULT 0,
  view_count INTEGER NOT NULL DEFAULT 0,
  video_count INTEGER NOT NULL DEFAULT 0,
  published_at TEXT NOT NULL DEFAULT '',
  video_format TEXT NOT NULL DEFAULT 'longform',
  niche TEXT NOT NULL DEFAULT '',
  category_name TEXT NOT NULL,
  discovered_at INTEGER NOT NULL,
  viral_score REAL NOT NULL DEFAULT 0,
  growth_rate REAL NOT NULL DEFAULT 0,
  view_sub_ratio REAL NOT NULL DEFAULT 0,
  recent_video_count INTEGER NOT NULL DEFAULT 0,
  avg_views_per_video REAL NOT NULL DEFAULT 0,
  is_newly_created INTEGER NOT NULL DEFAULT 0,
  is_rapidly_growing INTEGER NOT NULL DEFAULT 0,
  ai_score INTEGER NOT NULL DEFAULT 0,
  last_analyzed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS discovery_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_format TEXT NOT NULL,
  niche TEXT NOT NULL,
  channels_found INTEGER NOT NULL DEFAULT 0,
  searches_used INTEGER NOT NULL DEFAULT 0,
  discovered_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_discovery_log_format_niche ON discovery_log(video_format, niche);
CREATE INDEX IF NOT EXISTS idx_discovery_log_time ON discovery_log(discovered_at DESC);

CREATE TABLE IF NOT EXISTS similar_channel_analysis (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_channel_id TEXT NOT NULL,
  target_channel_id TEXT NOT NULL,
  similarity_score REAL NOT NULL DEFAULT 0,
  analysis_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE(source_channel_id, target_channel_id)
);

CREATE TABLE IF NOT EXISTS channel_content_ideas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id TEXT NOT NULL,
  idea_title TEXT NOT NULL,
  idea_description TEXT NOT NULL,
  content_type TEXT NOT NULL,
  estimated_views TEXT,
  difficulty TEXT,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS channel_scripts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id TEXT NOT NULL,
  idea_id INTEGER,
  script_title TEXT NOT NULL,
  hook TEXT NOT NULL,
  intro TEXT NOT NULL,
  body_sections TEXT NOT NULL,
  outro TEXT NOT NULL,
  estimated_duration INTEGER,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS channel_growth_blueprints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id TEXT NOT NULL,
  phase TEXT NOT NULL,
  goals TEXT NOT NULL,
  actions TEXT NOT NULL,
  metrics TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trending_channels_category ON trending_channels(video_format, niche);
CREATE INDEX IF NOT EXISTS idx_trending_channels_viral_score ON trending_channels(viral_score DESC);
CREATE INDEX IF NOT EXISTS idx_trending_channels_discovered ON trending_channels(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_similar_analysis_source ON similar_channel_analysis(source_channel_id);
CREATE INDEX IF NOT EXISTS idx_content_ideas_channel ON channel_content_ideas(channel_id);
CREATE INDEX IF NOT EXISTS idx_scripts_channel ON channel_scripts(channel_id);
CREATE INDEX IF NOT EXISTS idx_blueprints_channel ON channel_growth_blueprints(channel_id);
"""

_env_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_db_path: str | None = None


def db_path() -> str:
    """Resolve the SQLite database file path."""
    global _db_path
    with _env_lock:
        if _db_path is None:
            env = os.environ.get("NICHE_DB_PATH")
            if env:
                _db_path = env
            else:
                base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
                _db_path = os.path.join(
                    base, "S-Q-Ali Media Downloader", "storage", "niche_research.db"
                )
        return _db_path


def configure(path: str) -> None:
    """Point the database at a specific file (used by tests)."""
    global _conn, _db_path
    with _env_lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        _db_path = path


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = db_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode = WAL;")
        _conn.execute("PRAGMA busy_timeout = 5000;")
        _conn.execute("PRAGMA foreign_keys = ON;")
        _conn.executescript(SCHEMA)
    return _conn


def run(sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
    conn = _connect()
    with _env_lock:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def all(sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    conn = _connect()
    with _env_lock:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get(sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    conn = _connect()
    with _env_lock:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def exec_many(sql: str, seq: Iterable[Sequence[Any]]) -> None:
    conn = _connect()
    with _env_lock:
        conn.executemany(sql, seq)
        conn.commit()


def set_setting(key: str, value: str) -> None:
    run(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, _seal(value) if _is_secret_key(key) else value),
    )


def get_setting(key: str) -> str | None:
    row = get("SELECT value FROM settings WHERE key = ?", (key,))
    if row is None:
        return None
    value: str = row["value"]
    if _is_secret_key(key):
        if not value.startswith(SEAL_PREFIX):
            # Legacy plaintext row — seal it now and keep returning plaintext.
            try:
                sealed = _seal(value)
                if sealed != value:
                    run("UPDATE settings SET value = ? WHERE key = ?", (sealed, key))
            except Exception:
                logger.warning("Failed to seal legacy setting %s", key, exc_info=True)
            return value
        return _unseal(value)
    return value


def now() -> int:
    """Current unix time in milliseconds (mirrors the research web tool's now())."""
    return int(time.time() * 1000)


def vacuum() -> None:
    conn = _connect()
    with _env_lock:
        conn.execute("VACUUM;")
        conn.commit()


def close_db() -> None:
    global _conn, _db_path
    with _env_lock:
        if _conn is not None:
            try:
                _conn.close()
            except sqlite3.Error:
                pass
            _conn = None
        _db_path = None
