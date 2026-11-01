"""Tag/artwork embedding and the quality report, against real ffmpeg output."""

import base64
import shutil
import subprocess

import pytest
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus

from s_q_ali_media_downloader.core.music_tagging import (
    embed_tags,
    read_report,
)

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is required")

# 1x1 transparent PNG — enough for the picture round-trip.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _tone(tmp_path, name, *codec_args):
    path = tmp_path / name
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.3",
            *codec_args,
            str(path),
        ],
        check=True,
    )
    return path


@needs_ffmpeg
def test_embed_tags_in_flac(tmp_path):
    path = _tone(tmp_path, "song.flac", "-c:a", "flac")
    embed_tags(
        str(path),
        title="Levitating",
        artist="Dua Lipa",
        album="Future Nostalgia",
        track_number=2,
        cover=PNG,
    )
    audio = FLAC(str(path))
    assert audio["title"] == ["Levitating"]
    assert audio["artist"] == ["Dua Lipa"]
    assert audio["album"] == ["Future Nostalgia"]
    assert audio["tracknumber"] == ["2"]
    assert len(audio.pictures) == 1
    assert audio.pictures[0].data == PNG


@needs_ffmpeg
def test_embed_tags_in_mp3(tmp_path):
    path = _tone(tmp_path, "song.mp3", "-c:a", "libmp3lame", "-b:a", "320k")
    embed_tags(str(path), title="Song", artist="Artist", album="Album", cover=PNG)
    tags = ID3(str(path))
    assert tags["TIT2"].text == ["Song"]
    assert tags["TPE1"].text == ["Artist"]
    assert len(tags.getall("APIC")) == 1


@needs_ffmpeg
def test_embed_tags_in_m4a(tmp_path):
    path = _tone(tmp_path, "song.m4a", "-c:a", "aac", "-b:a", "256k")
    embed_tags(str(path), title="Song", artist="Artist", album="Album", cover=PNG)
    tags = MP4(str(path)).tags
    assert tags["\xa9nam"] == ["Song"]
    assert tags["\xa9ART"] == ["Artist"]
    assert len(tags["covr"]) == 1


@needs_ffmpeg
def test_embed_tags_in_opus(tmp_path):
    path = _tone(tmp_path, "song.opus", "-c:a", "libopus", "-b:a", "96k")
    embed_tags(str(path), title="Song", artist="Artist", album="Album", cover=PNG)
    audio = OggOpus(str(path))
    assert audio["title"] == ["Song"]
    assert "metadata_block_picture" in audio


@needs_ffmpeg
def test_quality_report_reads_flac_facts(tmp_path):
    path = _tone(tmp_path, "song.flac", "-c:a", "flac")
    report = read_report(str(path), source="YouTube Opus 160kbps")
    assert report.codec == "FLAC"
    assert report.sample_rate == 44100
    assert report.bit_depth == 16
    assert report.channels == 1
    label = report.label()
    assert "FLAC" in label
    assert "44.1 kHz" in label
    assert "16-bit" in label
    assert "YouTube Opus 160kbps" in label


@needs_ffmpeg
def test_quality_report_reads_mp3_facts(tmp_path):
    path = _tone(tmp_path, "song.mp3", "-c:a", "libmp3lame", "-b:a", "192k")
    report = read_report(str(path))
    assert report.codec == "MP3"
    assert report.sample_rate == 44100
    assert report.bit_depth is None
    assert report.bitrate and report.bitrate >= 128
