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


def test_youtube_video_resolves_metadata():
    tracks = resolve_media("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert tracks
    assert tracks[0].title
    assert tracks[0].url.startswith("https://")
