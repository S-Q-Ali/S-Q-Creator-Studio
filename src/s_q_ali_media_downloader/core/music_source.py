"""Music link detection and metadata resolution.

Spotify links carry no audio this app can download — they are metadata plus a
DRM-protected stream. ``spotdl`` resolves a Spotify track/album/playlist to the
matching YouTube audio, which yt-dlp then downloads. No paid account is used.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SPOTIFY_URL_RE = re.compile(
    r"^https?://(?:open|play)\.spotify\.com/(?:intl-[a-z]{2}/)?"
    r"(?P<kind>track|album|playlist|artist)/(?P<id>[A-Za-z0-9]+)",
    re.IGNORECASE,
)
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
YOUTUBE_CHANNEL_PATHS = ("/@", "/channel/", "/c/", "/user/", "/feed/", "/hashtag/")


class MusicSourceError(Exception):
    """A music link could not be resolved to anything downloadable."""


_SPOTDL = None


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


def _host(url: str) -> str:
    match = re.match(r"^https?://([^/]+)", url, re.IGNORECASE)
    return (match.group(1) if match else "").lower()


def _clean(url: str) -> str:
    return (url or "").strip().strip("<>").strip()


def spotify_kind(url: str) -> str | None:
    """Return ``track``/``album``/``playlist``/``artist`` for a Spotify URL."""
    match = SPOTIFY_URL_RE.match(_clean(url))
    return match.group("kind").lower() if match else None


def classify_url(url: str) -> str | None:
    """Name the music service behind a URL, or None when it is not music."""
    cleaned = _clean(url)
    if not cleaned:
        return None
    if spotify_kind(cleaned):
        return "spotify"

    host = _host(cleaned)
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


def _entry_to_track(entry: dict, source: str) -> MusicTrack | None:
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
        entries = [entry for entry in (info.get("entries") or []) if entry]
        tracks = [track for entry in entries if (track := _entry_to_track(entry, source))]
    else:
        track = _entry_to_track(info, source)
        tracks = [track] if track else []
    if not tracks:
        raise MusicSourceError("No playable tracks were found at this link.")
    return tracks


def _spotdl_client():
    """One Spotdl client per process: spotdl refuses a second init.

    spotdl 4.6 defaults to its free Spotify backend, which takes anonymous
    metadata. Client credentials are optional and only used when the user
    supplied them (official-API deployments and future spotdl releases where
    the free backend needs an app).
    """
    global _SPOTDL
    if _SPOTDL is not None:
        return _SPOTDL

    try:
        from spotdl import Spotdl
    except ImportError as exc:
        raise MusicSourceError(
            "Spotify links need the spotdl package. Run: pip install spotdl"
        ) from exc

    client_id = (os.environ.get("SPOTIPY_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("SPOTIPY_CLIENT_SECRET") or "").strip()
    try:
        _SPOTDL = Spotdl(client_id=client_id, client_secret=client_secret)
    except Exception as exc:
        text = str(exc).lower()
        if "client" in text or "credential" in text:
            raise MusicSourceError(
                "Spotify wants a client ID. Create a free app at "
                "developer.spotify.com/dashboard and set SPOTIPY_CLIENT_ID "
                "and SPOTIPY_CLIENT_SECRET, then retry."
            ) from exc
        raise MusicSourceError(str(exc)) from exc
    return _SPOTDL


def _spotdl_track(song) -> MusicTrack:
    """Spotify metadata plus a YouTube search URL.

    spotdl's own downloader search is a provider chain that can hang for
    minutes on a throttled network; a ``ytsearch1:`` URL lets yt-dlp's own
    search (the engine that actually downloads) do the matching instead.
    """
    artists = getattr(song, "artists", None) or []
    artist = ", ".join(str(a) for a in artists) if artists else ""
    title = str(getattr(song, "name", "") or getattr(song, "title", "") or "")
    return MusicTrack(
        url=build_yt_search(artist, title) if title else "",
        title=title,
        artist=artist,
        album=str(getattr(song, "album_name", "") or ""),
        track_number=int(getattr(song, "track_number", 0) or 0),
        duration=int(getattr(song, "duration", 0) or 0),
        cover_url=str(getattr(song, "cover_url", "") or ""),
        source="spotify",
        spotify_id=str(getattr(song, "song_id", "") or ""),
    )


def resolve_spotify(url: str) -> list[MusicTrack]:
    """Resolve Spotify metadata to the matching YouTube tracks via spotdl.

    spotdl is imported lazily: the rest of the app works when it is missing.
    """
    client = _spotdl_client()
    try:
        songs = client.search([_clean(url)])
    except Exception as exc:
        raise MusicSourceError(f"Spotify search failed: {exc}") from exc

    tracks = [_spotdl_track(song) for song in (songs or [])]
    tracks = [track for track in tracks if track.url]
    if not tracks:
        raise MusicSourceError("Spotify returned no downloadable tracks.")
    if spotify_kind(_clean(url)) == "album":
        # Spotify returns album tracks in no fixed order; an album should
        # download and queue in the order the artist put it in.
        tracks.sort(key=lambda track: track.track_number or len(tracks) + 1)
    return tracks


def resolve_url(url: str, use_cookies: bool = False) -> list[MusicTrack]:
    """Resolve any supported music URL into downloadable tracks."""
    source = classify_url(url)
    if source == "spotify":
        return resolve_spotify(url)
    if source in ("youtube", "ytmusic", "soundcloud"):
        return resolve_media(url, use_cookies=use_cookies)
    raise MusicSourceError("Not a music link. Use YouTube, YouTube Music, SoundCloud or Spotify.")
