"""Music URL classification — pure helpers, no network."""

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
    artist="The Weeknd",
    album="After Hours",
    cover="https://i.scdn.co/image/abc",
):
    return {
        "id": track_id,
        "name": name,
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

    def __init__(self, *, album=None, album_tracks=None, track=None, playlist_rows=()):
        self._album = album or {
            "name": "After Hours",
            "images": [{"url": "https://i.scdn.co/image/album"}],
        }
        self._album_tracks = album_tracks or []
        self._track = track
        self._playlist_rows = list(playlist_rows)

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


def test_resolve_spotify_playlist_reads_every_row(monkeypatch):
    from s_q_ali_media_downloader.core import music_source

    rows = [_track_payload(name="One", number=1), _track_payload(name="Two", number=2)]
    client = _FakeSpotify(playlist_rows=rows)
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/playlist/abc")
    assert [track.title for track in tracks] == ["One", "Two"]


def test_resolve_spotify_playlist_skips_empty_rows(monkeypatch):
    """A deleted or local row arrives as an empty entry, not a track."""
    from s_q_ali_media_downloader.core import music_source

    client = _FakeSpotify(playlist_rows=[None, _track_payload(name="Only")])
    monkeypatch.setattr(music_source, "_spotify_client", lambda: client)
    tracks = music_source.resolve_spotify("https://open.spotify.com/playlist/abc")
    assert [track.title for track in tracks] == ["Only"]


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
            raise RuntimeError("Spotify said no")

    monkeypatch.setattr(music_source, "_spotify_client", lambda: Broken())
    try:
        music_source.resolve_spotify("https://open.spotify.com/track/abc")
        raise AssertionError("a failed lookup should raise")
    except MusicSourceError as exc:
        assert "Spotify" in str(exc)

