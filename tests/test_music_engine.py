"""Music download options and paths — pure helpers, no network."""

from pathlib import Path

from s_q_ali_media_downloader.core.music_source import MusicTrack
from s_q_ali_media_downloader.engine import (
    DEFAULT_MUSIC_FORMAT,
    MUSIC_FORMATS,
    build_music_opts,
    music_output_path,
    music_quality_label,
)


def test_music_formats_cover_the_five_targets():
    assert set(MUSIC_FORMATS.values()) == {"flac", "mp3", "m4a", "opus", "wav"}
    assert DEFAULT_MUSIC_FORMAT in MUSIC_FORMATS
    assert MUSIC_FORMATS[DEFAULT_MUSIC_FORMAT] == "flac"


def test_build_music_opts_extracts_flac_and_embeds():
    opts = build_music_opts("flac", "out/%(id)s.%(ext)s")
    assert opts["format"] == "bestaudio/best"
    assert opts["noplaylist"] is True
    assert opts["writethumbnail"] is True
    keys = [item["key"] for item in opts["postprocessors"]]
    assert keys.index("FFmpegExtractAudio") < keys.index("FFmpegMetadata")
    assert "EmbedThumbnail" in keys
    extract = opts["postprocessors"][keys.index("FFmpegExtractAudio")]
    assert extract["preferredcodec"] == "flac"


def test_build_music_opts_mp3_uses_best_vbr():
    opts = build_music_opts("mp3", "x.%(ext)s")
    extract = next(
        item for item in opts["postprocessors"] if item["key"] == "FFmpegExtractAudio"
    )
    assert extract["preferredquality"] == "0"


def test_build_music_opts_wav_skips_thumbnail():
    opts = build_music_opts("wav", "x.%(ext)s")
    assert opts["writethumbnail"] is False
    keys = [item["key"] for item in opts["postprocessors"]]
    assert "EmbedThumbnail" not in keys


def test_build_music_opts_carries_ffmpeg_and_cookies():
    opts = build_music_opts("m4a", "x.%(ext)s", ffmpeg_dir="C:/ffmpeg", use_cookies=True)
    assert opts["ffmpeg_location"] == "C:/ffmpeg"
    assert opts["cookiesfrombrowser"] == ("chrome",)


def test_music_output_path_organises_by_artist_album(tmp_path):
    track = MusicTrack(
        url="u", title="Levitating", artist="Dua Lipa", album="Future Nostalgia", track_number=2
    )
    path = music_output_path(str(tmp_path), track, ".flac")
    assert path.replace("\\", "/").endswith(
        "Dua Lipa/Future Nostalgia/02 - Levitating.flac"
    )


def test_music_output_path_files_a_collection_in_one_folder(tmp_path):
    """Rows from an album or playlist link share that collection's folder."""
    first = music_output_path(
        str(tmp_path),
        MusicTrack(url="u", title="Teardrops", artist="Wheeler Jr.", track_number=3,
                   collection="Throwback Vibes"),
        ".flac",
    )
    second = music_output_path(
        str(tmp_path),
        MusicTrack(url="u", title="Say So", artist="Doja Cat", track_number=4,
                   collection="Throwback Vibes"),
        ".flac",
    )
    assert first.replace("\\", "/").endswith("Throwback Vibes/03 - Teardrops.flac")
    assert Path(first).parent == Path(second).parent


def test_music_output_path_sanitises_the_collection_folder(tmp_path):
    """A playlist title is a folder name as much as the artist is."""
    path = music_output_path(
        str(tmp_path),
        MusicTrack(url="u", title="Song", collection="Best of: 2024"),
        ".flac",
        position=1,
    )
    assert path.replace("\\", "/").endswith("Best of 2024/01 - Song.flac")


def test_music_output_path_defaults_and_sanitises(tmp_path):
    track = MusicTrack(url="u", title='a/b:c*?"', artist="", album="")
    path = music_output_path(str(tmp_path), track, ".mp3", position=7)
    assert path.replace("\\", "/").endswith("Unknown Artist/Singles/07 - abc.mp3")


def test_music_output_path_avoids_overwrite(tmp_path):
    track = MusicTrack(url="u", title="Song", artist="A", album="B", track_number=1)
    first = music_output_path(str(tmp_path), track, ".flac")
    Path(first).write_bytes(b"x")
    second = music_output_path(str(tmp_path), track, ".flac")
    assert second != first


def test_music_quality_label():
    assert music_quality_label({"acodec": "opus", "abr": 160.4}) == "Opus 160kbps"
    assert music_quality_label({"acodec": "mp4a.40.2", "abr": 256}) == "AAC 256kbps"
    assert music_quality_label({}) == "best available"
