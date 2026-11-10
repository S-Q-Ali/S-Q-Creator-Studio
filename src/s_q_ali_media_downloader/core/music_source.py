"""Music link detection and metadata resolution.

Spotify links carry no audio this app can download — they are metadata plus a
DRM-protected stream. ``SpotipyFree`` reads that metadata anonymously, and the
titles it returns are matched to YouTube audio by yt-dlp's own search. No
Spotify account, login or client credential is involved.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SPOTIFY_URL_RE = re.compile(
    r"^https?://(?:open|play)\.spotify\.com/(?:intl-[a-z]{2}/)?"
    r"(?P<kind>track|album|playlist|artist)/(?P<id>[A-Za-z0-9]+)",
    re.IGNORECASE,
)
SPOTIFY_URI_RE = re.compile(
    r"^spotify:(?P<kind>track|album|playlist|artist):(?P<id>[A-Za-z0-9]+)",
    re.IGNORECASE,
)
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
YOUTUBE_CHANNEL_PATHS = ("/@", "/channel/", "/c/", "/user/", "/feed/", "/hashtag/")


class MusicSourceError(Exception):
    """A music link could not be resolved to anything downloadable."""


_SPOTIFY = None


@dataclass
class MusicTrack:
    """One downloadable song. ``url`` always points at a media site."""

    url: str
    title: str = ""
    artist: str = ""
    album: str = ""
    track_number: int = 0
    duration: int = 0
    cover_url: str = ""
    source: str = ""
    spotify_id: str = ""
    collection: str = ""  # the album or playlist this row came from


def _host(url: str) -> str:
    match = re.match(r"^https?://([^/]+)", url, re.IGNORECASE)
    return (match.group(1) if match else "").lower()


def _clean(url: str) -> str:
    return (url or "").strip().strip("<>").strip()


def spotify_kind(url: str) -> str | None:
    """Return ``track``/``album``/``playlist``/``artist`` for a Spotify URL or URI."""
    cleaned = _clean(url)
    match = SPOTIFY_URL_RE.match(cleaned) or SPOTIFY_URI_RE.match(cleaned)
    return match.group("kind").lower() if match else None


def classify_url(url: str) -> str | None:
    """Name the music service behind a URL, or None when it is not music."""
    cleaned = _clean(url)
    if not cleaned:
        return None
    if spotify_kind(cleaned):
        return "spotify"

    host = _host(cleaned)
    if host == "spotify.link" or host.endswith(".spotify.link"):
        return "spotify"
    if host == "music.youtube.com":
        return "ytmusic"
    if host.endswith(("youtube.com", "youtube-nocookie.com")) or host == "youtu.be":
        if any(part in cleaned for part in YOUTUBE_CHANNEL_PATHS):
            return None
        return "youtube"
    if host == "soundcloud.com" or host.endswith(".soundcloud.com"):
        return "soundcloud"
    return None


def is_music_url(url: str) -> bool:
    return classify_url(url) is not None


def is_playlist_url(url: str) -> bool:
    """True when the link is a collection: playlist, album or artist."""
    cleaned = _clean(url)
    kind = spotify_kind(cleaned)
    if kind:
        return kind in ("playlist", "album", "artist")
    if classify_url(cleaned) in ("youtube", "ytmusic"):
        return "list=" in cleaned or "/playlist" in cleaned
    return False


def build_yt_search(*parts: str) -> str:
    """A yt-dlp search pseudo-URL for when a direct media URL is missing."""
    query = " ".join(" ".join(part.split()) for part in parts if part and part.strip())
    return f"ytsearch1:{query}"


def track_label(track: MusicTrack) -> str:
    if track.artist and track.title:
        return f"{track.artist} — {track.title}"
    return track.title or "Untitled track"


def _entry_to_track(entry: dict, source: str, collection: str = "") -> MusicTrack | None:
    url = entry.get("webpage_url") or entry.get("url") or ""
    if not url:
        video_id = entry.get("id")
        if source in ("youtube", "ytmusic") and video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        else:
            return None
    if not str(url).startswith("http"):
        # Flat YouTube playlist entries sometimes carry the bare video id.
        if source in ("youtube", "ytmusic"):
            url = f"https://www.youtube.com/watch?v={url}"
        else:
            return None

    thumbnails = entry.get("thumbnails") or []
    cover = entry.get("thumbnail") or (thumbnails[-1].get("url") if thumbnails else "")
    artists = entry.get("artist") or entry.get("uploader") or entry.get("channel") or ""
    return MusicTrack(
        url=str(url),
        title=entry.get("track") or entry.get("title") or "",
        artist=str(artists),
        album=entry.get("album") or "",
        track_number=int(entry.get("track_number") or entry.get("playlist_index") or 0),
        duration=int(entry.get("duration") or 0),
        cover_url=str(cover or ""),
        source=source,
        collection=collection,
    )


def resolve_media(url: str, use_cookies: bool = False) -> list[MusicTrack]:
    """Expand a YouTube/SoundCloud link into tracks using yt-dlp metadata."""
    import yt_dlp

    from s_q_ali_media_downloader.engine import YOUTUBE_PLAYER_CLIENTS, js_runtime_opts

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": False,
        "js_runtimes": js_runtime_opts(),
        "extractor_args": {"youtube": {"player_client": list(YOUTUBE_PLAYER_CLIENTS)}},
    }
    if use_cookies:
        opts["cookiesfrombrowser"] = ("chrome",)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise MusicSourceError(str(exc)) from exc
    if not info:
        raise MusicSourceError("This link returned no audio.")

    source = classify_url(url) or "youtube"
    if info.get("_type") == "playlist":
        # Every row of a set or playlist files under the collection's own folder.
        collection = str(info.get("title") or "")
        entries = [entry for entry in (info.get("entries") or []) if entry]
        tracks = [
            track
            for entry in entries
            if (track := _entry_to_track(entry, source, collection))
        ]
    else:
        track = _entry_to_track(info, source)
        tracks = [track] if track else []
    if not tracks:
        raise MusicSourceError("No playable tracks were found at this link.")
    return tracks


def _spotify_client():
    """One anonymous Spotify client per process.

    SpotipyFree reads the same public metadata the web player shows, so no
    client credentials, login or account is involved. It is imported lazily:
    the rest of the app works when it is missing.
    """
    global _SPOTIFY
    if _SPOTIFY is not None:
        return _SPOTIFY

    try:
        # spotapi 1.2.8 unconditionally imports unused persistence backends
        # (redis, pymongo) in spotapi.utils.saver at import time without
        # declaring them as dependencies. Provide empty module stubs so
        # anonymous read-only Spotify resolution does not fail with ModuleNotFoundError.
        import sys
        import types

        sys.modules.setdefault("redis", types.ModuleType("redis"))
        sys.modules.setdefault("pymongo", types.ModuleType("pymongo"))
        from SpotipyFree import Spotify
    except ImportError as exc:
        raise MusicSourceError(
            "Spotify links need the SpotipyFree package. Run: pip install SpotipyFree"
        ) from exc
    try:
        _SPOTIFY = Spotify(login=False)
    except Exception as exc:
        raise MusicSourceError(f"Spotify could not be reached: {exc}") from exc
    return _SPOTIFY


def _spotify_ref(url: str) -> tuple[str, str]:
    """The ``(kind, id)`` pair a Spotify URL or URI points at."""
    cleaned = _clean(url)
    match = SPOTIFY_URL_RE.match(cleaned) or SPOTIFY_URI_RE.match(cleaned)
    if not match:
        raise MusicSourceError("That is not a Spotify track, album or playlist link.")
    return match.group("kind").lower(), match.group("id")


def _resolve_spotify_link(url: str) -> str:
    """Follow a spotify.link redirect to the canonical open.spotify.com URL."""
    cleaned = _clean(url)
    if "spotify.link" not in cleaned:
        return cleaned
    try:
        import httpx

        with httpx.Client(follow_redirects=True, timeout=5.0) as client:
            resp = client.head(cleaned)
            target = str(resp.url)
            if "spotify.link" not in target:
                return target
            resp = client.get(cleaned)
            return str(resp.url)
    except Exception as exc:
        logger.debug("Failed to resolve spotify.link redirect for %s: %s", cleaned, exc)
    return cleaned


def _as_int(value, default: int = 0) -> int:
    """A number from a payload we did not write."""
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _album_cover(album) -> str:
    images = album.get("images") if isinstance(album, dict) else None
    for image in images or []:
        url = image.get("url") if isinstance(image, dict) else None
        if url:
            return str(url)
    return ""


def _spotify_track(
    payload: dict, cover: str = "", album_name: str = "", collection: str = ""
) -> MusicTrack:
    """Spotify metadata plus a YouTube search URL.

    The ``ytsearch1:`` URL lets yt-dlp's own search — the engine that actually
    downloads — do the matching, instead of a separate resolver chain that can
    stall for minutes on a throttled network.

    Album rows and playlist rows carry no album of their own, so the caller
    passes the album and cover it already has.
    """
    title = str(payload.get("name") or "")
    artist = ", ".join(
        str(a.get("name"))
        for a in (payload.get("artists") or [])
        if isinstance(a, dict) and a.get("name")
    )
    album = payload.get("album")
    album = album if isinstance(album, dict) else {}
    return MusicTrack(
        url=build_yt_search(artist, title) if title else "",
        title=title,
        artist=artist,
        album=str(album.get("name") or album_name or ""),
        track_number=_as_int(payload.get("track_number")),
        duration=_as_int(payload.get("duration_ms")) // 1000,
        cover_url=_album_cover(album) or cover,
        source="spotify",
        spotify_id=str(payload.get("id") or ""),
        collection=collection,
    )


def _order_of(payload: dict) -> tuple[int, int]:
    """Where the track sits on the record.

    A deluxe set restarts its track numbers on disc two, so the disc has to be
    compared first or the two discs interleave.
    """
    return (_as_int(payload.get("disc_number"), 1), _as_int(payload.get("track_number")))


def _readable_rows(items) -> list[dict]:
    """Only the entries that are actually objects.

    The free API returns holes for a local file or a track taken down since the
    playlist was made; one hole must not cost the user the whole collection.
    """
    return [item for item in (items or []) if isinstance(item, dict)]


def _playlist_meta(client, ref: str) -> tuple[str, str]:
    """A playlist's (name, cover_url), or empty strings when it cannot be read.

    The rows are already in hand; failing to label the folder or read the cover
    is not a reason to throw away the playlist.
    """
    try:
        meta = client.playlist(ref)
    except Exception:
        return "", ""
    if not isinstance(meta, dict):
        return "", ""
    name = str(meta.get("name") or "")
    cover = _album_cover(meta)
    return name, cover


def _playlist_title(client, ref: str) -> str:
    """A playlist's name, or an empty string when it cannot be read."""
    return _playlist_meta(client, ref)[0]


def _spotify_tracks(client, kind: str, ref: str) -> list[MusicTrack]:
    if kind == "track":
        return [
            _spotify_track(payload) for payload in _readable_rows([client.track(ref)])
        ]
    if kind == "album":
        meta = client.album(ref)
        cover = _album_cover(meta)
        name = str(meta.get("name") or "") if isinstance(meta, dict) else ""
        rows = _readable_rows((client.album_tracks(ref) or {}).get("items"))
        rows.sort(key=_order_of)
        return [
            _spotify_track(row, cover=cover, album_name=name, collection=name)
            for row in rows
        ]
    if kind == "playlist":
        # The library pages a playlist itself, so one call holds every row.
        page = client.playlist_items(ref, limit=-1, offset=0) or {}
        rows = _readable_rows(page.get("items"))
        total = _as_int(page.get("total"))
        if total > 0 and len(rows) < total:
            logger.warning(
                "Spotify playlist %s reported %d total tracks, but returned %d rows.",
                ref,
                total,
                len(rows),
            )
            if not rows:
                raise MusicSourceError(
                    f"Spotify playlist reported {total} tracks, but none could be read."
                )
        collection, cover = _playlist_meta(client, ref)
        return [
            _spotify_track(row["track"], cover=cover, collection=collection)
            for row in rows
            if isinstance(row.get("track"), dict)
        ]
    raise MusicSourceError(
        f"Spotify {kind} links are not supported. Use a track, album or playlist link."
    )


def resolve_spotify(url: str) -> list[MusicTrack]:
    """Resolve a Spotify link or URI into tracks that carry YouTube search URLs."""
    resolved_url = _resolve_spotify_link(url)
    kind, ref = _spotify_ref(resolved_url)
    client = _spotify_client()
    try:
        tracks = _spotify_tracks(client, kind, ref)
    except MusicSourceError:
        raise
    except Exception as exc:
        raise MusicSourceError(
            f"Spotify could not read that {kind}. It may be private, taken down "
            f"or regional — or the free metadata endpoint is having a moment. ({exc})"
        ) from exc
    tracks = [track for track in tracks if track.url]
    if not tracks:
        raise MusicSourceError("Spotify returned no downloadable tracks.")
    return tracks


def resolve_url(url: str, use_cookies: bool = False) -> list[MusicTrack]:
    """Resolve any supported music URL into downloadable tracks."""
    source = classify_url(url)
    if source == "spotify":
        return resolve_spotify(url)
    if source in ("youtube", "ytmusic", "soundcloud"):
        return resolve_media(url, use_cookies=use_cookies)
    raise MusicSourceError("Not a music link. Use YouTube, YouTube Music, SoundCloud or Spotify.")
