"""Live music resolution checks. Opt-in: pytest -m live. No downloads."""

import pytest

from s_q_ali_media_downloader.core.music_source import resolve_media, resolve_spotify

pytestmark = pytest.mark.live


def test_spotify_track_resolves_anonymously():
    tracks = resolve_spotify("https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b")
    assert tracks
    assert tracks[0].title
    assert tracks[0].artist
    assert tracks[0].url.startswith("ytsearch1:")


def test_spotify_album_resolves_in_track_order():
    tracks = resolve_spotify("https://open.spotify.com/album/4yP0hdKOZPNshxUOjY0cZj")
    assert len(tracks) > 5
    assert [track.track_number for track in tracks] == sorted(
        track.track_number for track in tracks
    )
    # The rows themselves carry no album: it comes from the album payload.
    assert all(track.title for track in tracks)
    assert {track.album for track in tracks} == {"After Hours"}
    assert all(track.cover_url.startswith("https://") for track in tracks)


def test_spotify_playlist_resolves_every_row():
    # A playlist longer than one page: the library pages it internally.
    tracks = resolve_spotify("https://open.spotify.com/playlist/37i9dQZF1DWWEJlAGA9gs0")
    assert len(tracks) > 50
    assert all(track.url.startswith("ytsearch1:") for track in tracks)
    assert all(track.title and track.artist for track in tracks)
    assert all(track.duration > 0 for track in tracks)


def test_youtube_video_resolves_metadata():
    tracks = resolve_media("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert tracks
    assert tracks[0].title
    assert tracks[0].url.startswith("https://")
