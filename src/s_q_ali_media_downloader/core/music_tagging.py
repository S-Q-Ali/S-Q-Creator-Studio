"""Tag/cover embedding and the quality report for downloaded music.

yt-dlp already embeds the YouTube thumbnail and metadata; Spotify matches carry
better tags and a square cover, so this module writes those over the top. The
quality report tells the user what the source stream really was — a FLAC file
made from a 160 kbps Opus stream is a lossless container, not new detail.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TPE2, TRCK
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

logger = logging.getLogger(__name__)


@dataclass
class AudioReport:
    codec: str = "unknown"
    sample_rate: int | None = None
    bit_depth: int | None = None
    channels: int | None = None
    bitrate: int | None = None
    source: str = ""

    def label(self, source: str = "") -> str:
        parts = [self.codec]
        if self.sample_rate:
            parts.append(f"{self.sample_rate / 1000:g} kHz")
        if self.bit_depth:
            parts.append(f"{self.bit_depth}-bit")
        if self.bitrate:
            parts.append(f"{self.bitrate} kbps")
        if self.channels == 1:
            parts.append("mono")
        elif self.channels == 2:
            parts.append("stereo")
        if source or self.source:
            parts.append(source or self.source)
        return " · ".join(parts)


def fetch_cover(url: str, timeout: float = 20.0) -> bytes | None:
    """Download a cover image; a broken cover must not fail the download."""
    if not url:
        return None
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return response.content or None
    except Exception as exc:
        logger.warning("Cover download failed: %s — %s", url, exc)
        return None


def _mime(cover: bytes) -> str:
    if cover.startswith(b"\x89PNG"):
        return "image/png"
    if cover.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if cover[:4] == b"RIFF" and cover[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _flac_picture(cover: bytes) -> Picture:
    picture = Picture()
    picture.type = 3  # front cover
    picture.mime = _mime(cover)
    picture.desc = "Cover"
    picture.data = cover
    return picture


def _embed_flac(path: str, tags: dict, cover: bytes | None) -> None:
    audio = FLAC(path)
    for key, value in tags.items():
        audio[key] = [str(value)]
    if cover:
        audio.clear_pictures()
        audio.add_picture(_flac_picture(cover))
    audio.save()


def _embed_mp3(path: str, tags: dict, cover: bytes | None) -> None:
    audio = MP3(path, ID3=ID3)
    if audio.tags is None:
        audio.add_tags()
    id3 = audio.tags
    id3.setall("TIT2", [TIT2(encoding=3, text=tags.get("title", ""))])
    id3.setall("TPE1", [TPE1(encoding=3, text=tags.get("artist", ""))])
    id3.setall("TPE2", [TPE2(encoding=3, text=tags.get("artist", ""))])
    id3.setall("TALB", [TALB(encoding=3, text=tags.get("album", ""))])
    if tags.get("tracknumber"):
        id3.setall("TRCK", [TRCK(encoding=3, text=str(tags["tracknumber"]))])
    if tags.get("date"):
        id3.setall("TDRC", [TDRC(encoding=3, text=str(tags["date"]))])
    if cover:
        id3.delall("APIC")
        id3.add(
            APIC(encoding=3, mime=_mime(cover), type=3, desc="Cover", data=cover)
        )
    audio.save()


def _embed_m4a(path: str, tags: dict, cover: bytes | None) -> None:
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    mp4 = audio.tags
    mp4["\xa9nam"] = [tags.get("title", "")]
    mp4["\xa9ART"] = [tags.get("artist", "")]
    mp4["\xa9alb"] = [tags.get("album", "")]
    if tags.get("tracknumber"):
        mp4["trkn"] = [(int(tags["tracknumber"]), 0)]
    if cover and _mime(cover) in ("image/png", "image/jpeg"):
        fmt = MP4Cover.FORMAT_PNG if _mime(cover) == "image/png" else MP4Cover.FORMAT_JPEG
        mp4["covr"] = [MP4Cover(cover, imageformat=fmt)]
    audio.save()


def _embed_ogg(audio, tags: dict, cover: bytes | None) -> None:
    for key, value in tags.items():
        audio[key] = [str(value)]
    if cover:
        audio["metadata_block_picture"] = [
            base64.b64encode(_flac_picture(cover).write()).decode("ascii")
        ]
    audio.save()


def _embed_wav(path: str, tags: dict, cover: bytes | None) -> None:
    audio = WAVE(path)
    if audio.tags is None:
        audio.add_tags()
    id3 = audio.tags
    id3.setall("TIT2", [TIT2(encoding=3, text=tags.get("title", ""))])
    id3.setall("TPE1", [TPE1(encoding=3, text=tags.get("artist", ""))])
    id3.setall("TALB", [TALB(encoding=3, text=tags.get("album", ""))])
    if cover:
        id3.delall("APIC")
        id3.add(APIC(encoding=3, mime=_mime(cover), type=3, desc="Cover", data=cover))
    audio.save()


def embed_tags(
    path: str,
    *,
    title: str = "",
    artist: str = "",
    album: str = "",
    track_number: int = 0,
    cover: bytes | None = None,
) -> None:
    """Write Spotify-style tags and cover art onto a downloaded audio file."""
    suffix = Path(path).suffix.lower()
    tags = {
        "title": title,
        "artist": artist,
        "albumartist": artist,
        "album": album,
        "tracknumber": track_number or "",
    }
    tags = {key: value for key, value in tags.items() if value not in ("", None, 0)}
    if suffix == ".flac":
        _embed_flac(path, tags, cover)
    elif suffix == ".mp3":
        _embed_mp3(path, tags, cover)
    elif suffix in (".m4a", ".mp4"):
        _embed_m4a(path, tags, cover)
    elif suffix == ".opus":
        _embed_ogg(OggOpus(path), tags, cover)
    elif suffix == ".ogg":
        _embed_ogg(OggVorbis(path), tags, cover)
    elif suffix == ".wav":
        _embed_wav(path, tags, cover)
    else:
        raise ValueError(f"Unsupported audio container: {suffix}")


def _codec_name(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".flac": "FLAC",
        ".mp3": "MP3",
        ".m4a": "AAC",
        ".mp4": "AAC",
        ".aac": "AAC",
        ".opus": "Opus",
        ".ogg": "Vorbis",
        ".wav": "WAV",
        ".aiff": "AIFF",
    }.get(suffix, suffix.lstrip(".").upper() or "unknown")


def read_report(path: str, source: str = "") -> AudioReport:
    """Read codec/sample rate/bit depth back from the finished file."""
    try:
        audio = MutagenFile(path)
    except Exception as exc:
        logger.warning("Could not read audio facts from %s — %s", path, exc)
        return AudioReport()
    if audio is None or getattr(audio, "info", None) is None:
        return AudioReport(codec=_codec_name(path))

    info = audio.info
    bitrate = getattr(info, "bitrate", None)
    return AudioReport(
        codec=_codec_name(path),
        sample_rate=getattr(info, "sample_rate", None) or None,
        bit_depth=getattr(info, "bits_per_sample", None) or None,
        channels=getattr(info, "channels", None) or None,
        bitrate=round(bitrate / 1000) if bitrate else None,
        source=source,
    )
