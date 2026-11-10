"""Music URL classification — pure helpers, no network."""

import pytest

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


def _track_payload(
    track_id="0VjIjW4GlUZAMYd2vXMi3b",
    name="Blinding Lights",
    number=9,
    disc=1,
    artist="The Weeknd",
    album="After Hours",
    cover="https://i.scdn.co/image/abc",
):
    return {
        "id": track_id,
        "name": name,
        "disc_number": disc,
        "track_number": number,
        "duration_ms": 200040,
        "artists": [{"name": artist}, {"name": "Featured"}],
        "album": {"name": album, "images": [{"url": cover}]},
    }


def test_spotify_track_maps_the_free_api_payload():
    from s_q_ali_media_downloader.core.music_source import _spotify_track

    track = _spotify_track(_track_payload())
    assert track.url == "ytsearch1:The Weeknd, Featured Blinding Lights"
    assert track.title == "Blinding Lights"
    assert track.artist == "The Weeknd, Featured"
    assert track.album == "After Hours"
    assert track.track_number == 9
    assert track.duration == 200
    assert track.cover_url == "https://i.scdn.co/image/abc"
    assert track.spotify_id == "0VjIjW4GlUZAMYd2vXMi3b"
    assert track.source == "spotify"


def test_spotify_track_falls_back_to_the_album_cover():
    from s_q_ali_media_downloader.core.music_source import _spotify_track

    payload = _track_payload()
    payload["album"] = {"name": "After Hours"}  # some payloads carry no images
    track = _spotify_track(payload, cover="https://i.scdn.co/image/album")
    assert track.cover_url == "https://i.scdn.co/image/album"


def test_spotify_track_falls_back_to_the_parent_album():
    """album_tracks() rows carry no album at all — see the live test."""
    from s_q_ali_media_downloader.core.music_source import _spotify_track

    payload = _track_payload()
    del payload["album"]
    track = _spotify_track(payload, album_name="After Hours", cover="https://i.scdn.co/image/x")
    assert track.album == "After Hours"
    assert track.cover_url == "https://i.scdn.co/image/x"


class _FakeSpotify:
    """The anonymous Spotify client, stubbed at its JSON boundary."""

    def __init__(self, *, album=None, album_tracks=None, track=None, playlist_rows=(), playlist=None):
        self._album = album or {
            "name": "After Hours",
            "images": [{"url": "https://i.scdn.co/image/album"}],
        }
        self._album_tracks = album_tracks or []
        self._track = track
        self._playlist_rows = list(playlist_rows)
        self._playlist = playlist or {"name": "Classical Essentials"}

    def track(self, track_id):
        return self._track or _track_payload(track_id=track_id)

    def album(self, album_id):
        return self._album

    def album_tracks(self, album_id):
        # Real rows have no album key: the album is only on album()'s payload.
        rows = []
        for item in self._album_tracks:
            row = {key: value for key, value in item.items() if key != "album"}
            rows.append(row)
        return {"items": rows}

    def playlist(self, playlist_id):
        return self._playlist

    def playlist_items(self, playlist_id, limit=-1, offset=0):
        # The library pages internally, so one call holds the whole playlist.
        return {"items": [{"track": row} for row in self._playlist_rows], "next": False}

    def artist(self, artist_id):
        raise AssertionError("an artist link must not reach the client")


def test_resolve_spotify_track_reads_one_track(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    client = _FakeSpotify()
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/track/abc123")
    assert [track.title for track in tracks] == ["Blinding Lights"]
    assert tracks[0].url.startswith("ytsearch1:")


def test_resolve_spotify_album_returns_tracks_in_order(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    client = _FakeSpotify(
        album_tracks=[
            _track_payload(name="Second", number=2),
            _track_payload(name="First", number=1),
        ]
    )
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/album/abc")
    assert [track.title for track in tracks] == ["First", "Second"]
    assert [track.track_number for track in tracks] == [1, 2]
    assert [track.album for track in tracks] == ["After Hours", "After Hours"]
    assert [track.cover_url for track in tracks] == ["https://i.scdn.co/image/album"] * 2


def test_resolve_spotify_album_keeps_the_discs_in_order(monkeypatch):
    """A deluxe set repeats track numbers per disc."""
    from s_q_ali_media_downloader.core import music_source

    client = _FakeSpotify(
        album_tracks=[
            _track_payload(name="D2-2", disc=2, number=2),
            _track_payload(name="D1-2", disc=1, number=2),
            _track_payload(name="D2-1", disc=2, number=1),
            _track_payload(name="D1-1", disc=1, number=1),
        ]
    )
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/album/abc")
    assert [track.title for track in tracks] == ["D1-1", "D1-2", "D2-1", "D2-2"]


def test_resolve_spotify_skips_rows_it_cannot_read(monkeypatch):
    """A deleted, local or half-formed row must not cost the other 205 tracks."""
    from s_q_ali_media_downloader.core import music_source

    client = _FakeSpotify(
        playlist_rows=[_track_payload(name="Good"), "junk", None, {"id": "no-name"}]
    )
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/playlist/abc")
    assert [track.title for track in tracks] == ["Good"]


def test_resolve_spotify_reads_garbage_numbers_as_zero():
    from s_q_ali_media_downloader.core.music_source import _spotify_track

    payload = _track_payload()
    payload["duration_ms"] = "soon"
    payload["track_number"] = None
    track = _spotify_track(payload)
    assert track.duration == 0
    assert track.track_number == 0


def test_resolve_spotify_playlist_reads_every_row(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    rows = [_track_payload(name="One", number=1), _track_payload(name="Two", number=2)]
    client = _FakeSpotify(playlist_rows=rows)
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/playlist/abc")
    assert [track.title for track in tracks] == ["One", "Two"]


def test_resolve_spotify_playlist_stamps_the_collection(monkeypatch):
    """A playlist link files its rows under the playlist, not per-artist folders."""
    from s_q_ali_media_downloader.core import music_source

    rows = [_track_payload(name="One", number=1), _track_payload(name="Two", number=2)]
    client = _FakeSpotify(playlist_rows=rows)
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/playlist/abc")
    assert [track.collection for track in tracks] == ["Classical Essentials"] * 2


def test_resolve_spotify_album_stamps_the_collection(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    client = _FakeSpotify(album_tracks=[_track_payload(name="First", number=1)])
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/album/abc")
    assert tracks[0].collection == "After Hours"


def test_resolve_spotify_track_has_no_collection(monkeypatch):
    """A lone link keeps the Artist/Album layout."""
    from s_q_ali_media_downloader.core import music_source

    client = _FakeSpotify()
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/track/abc")
    assert tracks[0].collection == ""


def test_resolve_spotify_keeps_the_tracks_when_the_title_lookup_fails(monkeypatch):
    """Rows already in hand are not lost over a playlist name we cannot read."""
    from s_q_ali_media_downloader.core import music_source

    class NoTitle(_FakeSpotify):
        def playlist(self, playlist_id):
            raise KeyError("name")

    client = NoTitle(playlist_rows=[_track_payload(name="One", number=1)])
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/playlist/abc")
    assert [track.title for track in tracks] == ["One"]
    assert tracks[0].collection == ""


def _fake_yt_dlp(monkeypatch, info):
    """resolve_media's yt-dlp call, stubbed at the same boundary as Spotify."""
    import sys
    from types import SimpleNamespace

    class FakeYdl:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            return info

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYdl))


def test_resolve_media_playlist_stamps_the_collection(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    _fake_yt_dlp(
        monkeypatch,
        {
            "_type": "playlist",
            "title": "Chill Lo-Fi",
            "entries": [{"url": "https://soundcloud.com/a/one", "title": "One"}],
        },
    )
    tracks = music_source.resolve_media("https://soundcloud.com/a/sets/chill")
    assert tracks[0].collection == "Chill Lo-Fi"


def test_resolve_media_single_link_has_no_collection(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    _fake_yt_dlp(
        monkeypatch,
        {"_type": "url", "title": "One", "url": "https://soundcloud.com/a/one"},
    )
    tracks = music_source.resolve_media("https://soundcloud.com/a/one")
    assert tracks[0].collection == ""


def test_resolve_spotify_artist_is_declared_unsupported(monkeypatch):
    from s_q_ali_media_downloader.core import music_source
    from s_q_ali_media_downloader.core.music_source import MusicSourceError

    monkeypatch.setattr(music_source, "_spotify_client", lambda: _FakeSpotify())
    try:
        music_source.resolve_spotify("https://open.spotify.com/artist/abc")
        raise AssertionError("an artist link should not resolve")
    except MusicSourceError as exc:
        assert "artist" in str(exc).lower()


def test_resolve_spotify_reports_a_failed_lookup(monkeypatch):
    from s_q_ali_media_downloader.core import music_source
    from s_q_ali_media_downloader.core.music_source import MusicSourceError

    class Broken:
        def track(self, track_id):
            raise KeyError("content")

    monkeypatch.setattr(music_source, "_spotify_client", lambda: Broken())
    try:
        music_source.resolve_spotify("https://open.spotify.com/track/abc")
        raise AssertionError("a failed lookup should raise")
    except MusicSourceError as exc:
        # The library's own KeyError text is not something to show a user
        # on its own: say which link failed and what they can do.
        assert "Spotify" in str(exc)
        assert "track" in str(exc).lower()


def test_spotify_uri_classification_and_resolution(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    assert music_source.spotify_kind("spotify:track:0VjIjW4GlUZAMYd2vXMi3b") == "track"
    assert music_source.spotify_kind("spotify:album:abc") == "album"
    assert music_source.spotify_kind("spotify:playlist:abc") == "playlist"
    assert music_source.classify_url("spotify:track:0VjIjW4GlUZAMYd2vXMi3b") == "spotify"
    assert music_source.classify_url("https://spotify.link/AbCdEf") == "spotify"

    client = _FakeSpotify()
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("spotify:track:0VjIjW4GlUZAMYd2vXMi3b")
    assert [t.title for t in tracks] == ["Blinding Lights"]


def test_spotify_short_link_redirect(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    # Mock redirect from spotify.link to open.spotify.com
    monkeypatch.setattr(
        music_source,
        "_resolve_spotify_link",
        lambda url: "https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b"
        if "spotify.link" in url
        else url,
    )
    client = _FakeSpotify()
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://spotify.link/AbCdEf")
    assert [t.title for t in tracks] == ["Blinding Lights"]


def test_spotify_playlist_gives_tracks_playlist_artwork(monkeypatch):
    """Issue #12: Playlist tracks fall back to the playlist's artwork, but not album tag."""
    from s_q_ali_media_downloader.core import music_source

    playlist_cover = "https://i.scdn.co/image/playlist_cover_123"
    client = _FakeSpotify(
        playlist={"name": "Pop Hits", "images": [{"url": playlist_cover}]},
        playlist_rows=[
            {
                "id": "trk1",
                "name": "Hit Song",
                "artists": [{"name": "Artist A"}],
                "album": {"name": "", "images": []},  # No album image on track payload
            }
        ],
    )
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/playlist/p123")
    assert len(tracks) == 1
    track = tracks[0]
    assert track.title == "Hit Song"
    assert track.cover_url == playlist_cover
    assert track.collection == "Pop Hits"
    assert track.album == ""  # Never put playlist name in ALBUM tag


def test_spotify_playlist_truncation_warning_and_empty_check(monkeypatch, caplog):
    """Issue #10: Warning logged when total > len(rows), raises when 0 rows despite total > 0."""
    import logging

    from s_q_ali_media_downloader.core import music_source

    # 1. Total > rows, but has some rows -> logs warning
    class PagingClient(_FakeSpotify):
        def playlist_items(self, playlist_id, limit=-1, offset=0):
            return {
                "items": [{"track": _track_payload(name="OnlyOne")}],
                "total": 100,
                "next": False,
            }

    monkeypatch.setattr(music_source, "_spotify_client", lambda: PagingClient())
    with caplog.at_level(logging.WARNING):
        tracks = music_source.resolve_spotify("https://open.spotify.com/playlist/p123")
    assert len(tracks) == 1
    assert any("reported 100 total tracks, but returned 1 rows" in msg for msg in caplog.messages)

    # 2. Total > 0 but 0 rows returned -> raises MusicSourceError
    class EmptyClient(_FakeSpotify):
        def playlist_items(self, playlist_id, limit=-1, offset=0):
            return {"items": [], "total": 50, "next": False}

    monkeypatch.setattr(music_source, "_spotify_client", lambda: EmptyClient())
    with pytest.raises(music_source.MusicSourceError, match="none could be read"):
        music_source.resolve_spotify("https://open.spotify.com/playlist/p123")


