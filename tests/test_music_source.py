"""Music URL classification — pure helpers, no network."""

from types import SimpleNamespace
from typing import ClassVar

from s_q_ali_media_downloader.core.music_source import (
    MusicTrack,
    build_yt_search,
    classify_url,
    is_music_url,
    is_playlist_url,
    spotify_kind,
    track_label,
)


def test_classify_url_platforms():
    assert classify_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert classify_url("https://youtu.be/dQw4w9WgXcQ") == "youtube"
    assert classify_url("https://music.youtube.com/watch?v=dQw4w9WgXcQ") == "ytmusic"
    assert classify_url("https://soundcloud.com/artist/track") == "soundcloud"
    assert classify_url("https://open.spotify.com/track/abc123") == "spotify"


def test_classify_url_rejects_noise():
    assert classify_url("") is None
    assert classify_url("not a url") is None
    assert classify_url("https://example.com/song") is None
    assert classify_url("https://www.youtube.com/@channel") is None
    assert classify_url("https://www.youtube.com/playlist?list=PL123") == "youtube"


def test_is_music_url():
    assert is_music_url("https://youtu.be/dQw4w9WgXcQ")
    assert is_music_url("https://open.spotify.com/album/abc")
    assert not is_music_url("https://www.tiktok.com/@user/video/1")


def test_spotify_kind():
    assert spotify_kind("https://open.spotify.com/track/abc") == "track"
    assert spotify_kind("https://open.spotify.com/album/abc") == "album"
    assert spotify_kind("https://open.spotify.com/playlist/abc") == "playlist"
    assert spotify_kind("https://open.spotify.com/artist/abc") == "artist"
    assert spotify_kind("https://open.spotify.com/intl-de/track/abc") == "track"
    assert spotify_kind("https://open.spotify.com/") is None


def test_is_playlist_url():
    assert is_playlist_url("https://open.spotify.com/playlist/abc")
    assert is_playlist_url("https://open.spotify.com/album/abc")
    assert is_playlist_url("https://open.spotify.com/artist/abc")
    assert not is_playlist_url("https://open.spotify.com/track/abc")
    assert is_playlist_url("https://www.youtube.com/playlist?list=PL123")
    assert is_playlist_url("https://www.youtube.com/watch?v=x&list=PL123")
    assert not is_playlist_url("https://www.youtube.com/watch?v=x")


def test_build_yt_search():
    assert build_yt_search("  Dua   Lipa ", "Levitating") == "ytsearch1:Dua Lipa Levitating"
    assert build_yt_search("", "Song") == "ytsearch1:Song"


def test_track_label_prefers_artist_and_title():
    track = MusicTrack(url="u", title="Levitating", artist="Dua Lipa")
    assert track_label(track) == "Dua Lipa — Levitating"
    assert track_label(MusicTrack(url="u", title="Levitating")) == "Levitating"
    assert track_label(MusicTrack(url="u")) == "Untitled track"


def test_spotdl_track_builds_a_youtube_search_url():
    from s_q_ali_media_downloader.core.music_source import _spotdl_track

    class Song:
        name = "Blinding Lights"
        artists: ClassVar[list[str]] = ["The Weeknd"]
        album_name = "After Hours"
        track_number = 9
        duration = 200
        cover_url = "https://i.scdn.co/image/abc"
        song_id = "0VjIjW4GlUZAMYd2vXMi3b"

    track = _spotdl_track(Song())
    assert track.url == "ytsearch1:The Weeknd Blinding Lights"
    assert track.album == "After Hours"
    assert track.source == "spotify"


def test_album_tracks_are_returned_in_track_order(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    def song(number, name):
        return SimpleNamespace(
            name=name,
            artists=["Artist"],
            album_name="Album",
            track_number=number,
            duration=100,
            cover_url="",
            song_id=str(number),
        )

    class Client:
        def search(self, urls):
            return [song(2, "Second"), song(1, "First")]

    monkeypatch.setattr(music_source, "_spotdl_client", lambda: Client())
    tracks = music_source.resolve_spotify("https://open.spotify.com/album/abc")
    assert [track.title for track in tracks] == ["First", "Second"]
