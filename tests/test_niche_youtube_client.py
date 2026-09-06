"""Tests for the Niche Research yt-dlp YouTube client."""

import pytest
import yt_dlp
import yt_dlp.utils as ydl_utils

from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools import youtube_client as yc


@pytest.fixture(autouse=True)
def _isolated_db(isolated_appdata):
    db.configure(None)
    db.set_setting("youtube_api_key", "")
    yield
    db.close_db()


def test_parse_video_id():
    cases = {
        "dQw4w9WgXcQ": "dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ": "dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=30": "dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ": "dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ": "dQw4w9WgXcQ",
        "not a video": None,
    }
    for url, expected in cases.items():
        assert yc.parse_video_id(url) == expected


def test_parse_channel_id():
    cid = "UCisZ2efLJn1Dxvn4th6mwlA"
    assert yc.parse_channel_id(cid) == cid
    assert yc.parse_channel_id(f"https://www.youtube.com/channel/{cid}") == cid
    assert yc.parse_channel_id(f"https://www.youtube.com/channel/{cid}/videos") == cid
    assert yc.parse_channel_id("UCtooshort") is None
    assert yc.parse_channel_id("https://www.youtube.com/@handle") is None


def test_parse_iso8601_duration():
    assert yc.parse_iso8601_duration("PT1H2M3S") == 3723
    assert yc.parse_iso8601_duration("PT2M30S") == 150
    assert yc.parse_iso8601_duration("PT45S") == 45
    assert yc.parse_iso8601_duration(None) == 0
    assert yc.parse_iso8601_duration("junk") == 0


def test_to_video_info_normalizes_entry():
    entry = {
        "id": "abc123def45",
        "channel_id": "UCxyz",
        "uploader_id": "UCxyz",
        "title": "Test Video",
        "description": "hello",
        "upload_date": "20260601",
        "duration": 600,
        "thumbnail": "https://img.url",
        "view_count": 1_000_000,
        "like_count": 50_000,
        "comment_count": 1_234,
        "tags": ["a", "b"],
        "channel": "Some Channel",
    }
    info = yc._to_video_info(entry)
    assert info.video_id == "abc123def45"
    assert info.channel_id == "UCxyz"
    assert info.duration_seconds == 600
    assert info.view_count == 1_000_000
    assert info.published_at == "2026-06-01T00:00:00Z"
    assert info.channel_title == "Some Channel"


def test_to_channel_info_with_flat_uploads():
    data = {
        "id": "UCxyz",
        "channel": "My Channel",
        "channel_follower_count": 123_000,
        "description": "About",
        "thumbnail": "https://avatar.url",
        "entries": [
            {"id": "aaaa", "title": "one", "view_count": 10},
            {"id": "bbbb", "title": "two", "view_count": 20},
        ],
    }
    info = yc._to_channel_info(data)
    assert info.channel_id == "UCxyz"
    assert info.title == "My Channel"
    assert info.subscriber_count == 123_000
    assert len(info.uploads) == 2
    assert info.uploads[1]["video_id"] == "bbbb"


def test_to_channel_info_falls_back_to_avatar_thumbnail():
    data = {
        "id": "UCxyz",
        "channel": "My Channel",
        "avatar": "https://avatar.url",
        "entries": [],
    }
    info = yc._to_channel_info(data)
    assert info.thumbnail_url == "https://avatar.url"


def test_to_channel_info_thumbnail_from_thumbnails_list():
    data = {
        "id": "UCxyz",
        "channel": "My Channel",
        "thumbnails": [{"url": "https://t.url", "id": "0"}],
        "entries": [],
    }
    info = yc._to_channel_info(data)
    assert info.thumbnail_url == "https://t.url"


def test_search_videos_ytdlp_dispatch(monkeypatch):
    fetched = {}

    def fake_extract(url, opts):
        fetched["url"] = url
        fetched["opts"] = opts
        return {
            "entries": [
                {
                    "id": "aaa",
                    "title": "Old vid",
                    "upload_date": "20200101",
                    "duration": 500,
                    "view_count": 1,
                },
                {
                    "id": "bbb",
                    "title": "New vid",
                    "upload_date": "20260901",
                    "duration": 700,
                    "view_count": 5,
                },
            ]
        }

    monkeypatch.setattr(yc, "_extract", fake_extract)
    results = yc.search_videos("tech review", max_results=10, days_recent=7)
    assert [v.video_id for v in results] == ["aaa", "bbb"]
    assert "ytsearch20:tech review" in fetched["url"]
    assert fetched["opts"].get("daterange") is not None


def test_daterange_skipped_when_no_window(monkeypatch):
    captured = {}

    def fake_extract(url, opts):
        captured["opts"] = opts
        return {"entries": []}

    monkeypatch.setattr(yc, "_extract", fake_extract)
    yc.search_videos("plain query")
    assert "daterange" not in captured["opts"]


def test_rate_limit_mapping_for_bot_check(monkeypatch):
    class BoomYDL:
        def __init__(self, opts):
            self.opts = opts

        def extract_info(self, url, download=False):
            raise ydl_utils.DownloadError("ERROR: [youtube] Sign in to confirm you're not a bot")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(yt_dlp, "YoutubeDL", BoomYDL)
    with pytest.raises(yc.RateLimitError):
        yc.fetch_video("abc")


def test_not_found_mapping(monkeypatch):
    class NotFoundYDL:
        def __init__(self, opts):
            self.opts = opts

        def extract_info(self, url, download=False):
            raise ydl_utils.DownloadError("ERROR: [youtube] abc: Video unavailable")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(yt_dlp, "YoutubeDL", NotFoundYDL)
    with pytest.raises(yc.NotFoundError):
        yc.fetch_video("abc")


def test_search_via_api_path_used_when_key_set(monkeypatch):
    called = {}

    def fake_api(query, max_results, days_recent):
        called["hit"] = True
        return [yc.VideoInfo(video_id="api1", view_count=99)]

    monkeypatch.setattr(yc, "_search_via_api", fake_api)
    db.set_setting("youtube_api_key", "my-key")
    results = yc.search_videos("query")
    assert called.get("hit")
    assert results[0].video_id == "api1"


def test_fetch_videos_preserves_order(monkeypatch):
    def fake_fetch_video(video_id, cookiefile=None):
        return yc.VideoInfo(video_id=video_id, view_count=len(video_id))

    monkeypatch.setattr(yc, "fetch_video", fake_fetch_video)
    results = yc.fetch_videos(["z", "a", "m", "z"])
    assert [v.video_id for v in results] == ["z", "a", "m"]


def test_chunks():
    assert list(yc._chunks(["1", "2", "3", "4", "5"], 2)) == [
        ["1", "2"],
        ["3", "4"],
        ["5"],
    ]
