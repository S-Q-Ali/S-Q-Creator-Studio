"""Tests for the Niche Research yt-dlp YouTube client."""

import pytest

from s_q_ali_media_downloader.core import settings_store as db
from s_q_ali_media_downloader.core import youtube_client as yc


@pytest.fixture(autouse=True)
def _isolated_db(isolated_appdata):
    db.configure(None)
    db.set_setting("youtube_api_key", "")
    yield
    db.close_store()




# --------------------------------------------------------------------------- #
# Regression (2026-10): uploads must be able to carry their real view count
# --------------------------------------------------------------------------- #
def test_fetch_channel_is_flat_by_default(monkeypatch):
    """Discovery scans many channels, so uploads stay flat (fast)."""
    captured: dict = {}

    def fake_extract(url, opts):
        captured.update(opts)
        return {"id": "UCx", "channel": "Chan", "entries": []}

    monkeypatch.setattr(yc, "_extract", fake_extract)

    yc.fetch_channel("UCx")

    assert captured.get("extract_flat") is True


def test_fetch_channel_can_include_upload_stats(monkeypatch):
    """The scorecard shows upload view counts, which flat extraction drops."""
    captured: dict = {}

    def fake_extract(url, opts):
        captured.update(opts)
        return {
            "id": "UCx",
            "channel": "Chan",
            "entries": [
                {"id": "v1", "title": "One", "view_count": 1234, "upload_date": "20260901"},
                {"id": "v2", "title": "Two", "view_count": 56, "upload_date": "20260801"},
            ],
        }

    monkeypatch.setattr(yc, "_extract", fake_extract)

    info = yc.fetch_channel("UCx", uploads_with_stats=True)

    assert captured.get("extract_flat") is False
    assert info.uploads[0]["view_count"] == 1234
    assert info.uploads[1]["view_count"] == 56


# --------------------------------------------------------------------------- #
# Regression (2026-10): the cookies.txt escape hatch must exist
# --------------------------------------------------------------------------- #
def test_configured_cookie_file_reaches_every_request(isolated_appdata, tmp_path, monkeypatch):
    """YouTube bot-checks blocked the research pages; a cookies.txt is the
    escape hatch — every engine has to pick it up."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    db.set_setting("youtube_cookies_file", str(cookies))

    captured: dict = {}

    def fake_extract(url, opts):
        captured.update(opts)
        return {"id": "UCx", "channel": "Chan", "entries": []}

    monkeypatch.setattr(yc, "_extract", fake_extract)

    yc.fetch_channel("UCx")

    assert captured.get("cookiefile") == str(cookies)


def test_missing_cookie_file_is_ignored(isolated_appdata, monkeypatch):
    """A cookie file that was deleted must not break the requests."""
    db.set_setting("youtube_cookies_file", "C:/definitely/missing/cookies.txt")

    captured: dict = {}

    def fake_extract(url, opts):
        captured.update(opts)
        return {"id": "UCx", "channel": "Chan", "entries": []}

    monkeypatch.setattr(yc, "_extract", fake_extract)

    yc.fetch_channel("UCx")

    assert "cookiefile" not in captured


def test_explicit_cookiefile_wins_over_the_setting(isolated_appdata, tmp_path, monkeypatch):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("x", encoding="utf-8")
    db.set_setting("youtube_cookies_file", str(cookies))

    captured: dict = {}

    def fake_extract(url, opts):
        captured.update(opts)
        return {"id": "UCx", "channel": "Chan", "entries": []}

    monkeypatch.setattr(yc, "_extract", fake_extract)

    yc.fetch_channel("UCx", cookiefile="C:/explicit/cookies.txt")

    assert captured.get("cookiefile") == "C:/explicit/cookies.txt"




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


def test_to_channel_info_uses_playlist_count_for_video_count():
    data = {
        "id": "UCxyz",
        "channel": "My Channel",
        "playlist_count": 15,
        "entries": [],
    }
    info = yc._to_channel_info(data)
    assert info.video_count == 15
    assert info.title == "My Channel"


def test_to_channel_info_no_playlist_count_is_zero_unknown():
    info = yc._to_channel_info({"id": "UCxyz", "channel": "X", "entries": []})
    assert info.video_count == 0


def test_to_channel_info_prefers_avatar_id_thumbnail_over_banner():
    data = {
        "id": "UCxyz",
        "channel": "My Channel",
        "thumbnails": [
            {"url": "https://banner.url", "id": "banner_uncropped"},
            {"url": "https://avatar.url", "id": "avatar"},
        ],
        "entries": [],
    }
    info = yc._to_channel_info(data)
    assert info.thumbnail_url == "https://avatar.url"


def test_to_channel_info_skips_banner_when_no_avatar_available():
    data = {
        "id": "UCxyz",
        "channel": "My Channel",
        "thumbnails": [{"url": "https://banner.url", "id": "banner"}],
        "entries": [],
    }
    info = yc._to_channel_info(data)
    assert info.thumbnail_url == ""


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




def test_search_via_api_path_used_when_key_set(monkeypatch):
    called = {}

    def fake_api(query, max_results, days_recent, **kwargs):
        called["hit"] = True
        return [yc.VideoInfo(video_id="api1", view_count=99)]

    monkeypatch.setattr(yc, "_search_via_api", fake_api)
    db.set_setting("youtube_api_key", "my-key")
    results = yc.search_videos("query")
    assert called.get("hit")
    assert results[0].video_id == "api1"


def test_chunks():
    assert list(yc._chunks(["1", "2", "3", "4", "5"], 2)) == [
        ["1", "2"],
        ["3", "4"],
        ["5"],
    ]


# ---------------------------------------------------------------------------
# search_channels — grouping, ranking, enrichment, min_subscribers
# ---------------------------------------------------------------------------


def _fake_channel(cid, subs=1000, title=""):
    return yc.ChannelInfo(channel_id=cid, subscriber_count=subs, title=title or f"Ch {cid}")


def test_search_channels_groups_by_channel_and_enriches(monkeypatch):
    def fake_search_videos(query, max_results, **kwargs):
        return [
            yc.VideoInfo(video_id="v1", channel_id="UCa", channel_title="Alpha", view_count=50),
            yc.VideoInfo(video_id="v2", channel_id="UCb", channel_title="Beta", view_count=900),
            yc.VideoInfo(video_id="v3", channel_id="UCa", channel_title="Alpha", view_count=800),
        ]

    def fake_fetch_channels(ids, **kwargs):
        by_id = {"UCa": _fake_channel("UCa", 10_000, "Alpha"), "UCb": _fake_channel("UCb", 5_000, "Beta")}
        return [by_id[cid] for cid in ids if cid in by_id]

    monkeypatch.setattr(yc, "search_videos", fake_search_videos)
    monkeypatch.setattr(yc, "fetch_channels", fake_fetch_channels)

    results = yc.search_channels("alpha beta", max_results=10)
    assert [c.channel_id for c in results] == ["UCb", "UCa"]  # ranked by best video views
    assert results[0].subscriber_count == 5_000
    assert results[1].subscriber_count == 10_000


def test_search_channels_dedupes_same_channel(monkeypatch):
    def fake_search_videos(query, max_results, **kwargs):
        return [
            yc.VideoInfo(video_id="v1", channel_id="UCa", channel_title="Alpha", view_count=1),
            yc.VideoInfo(video_id="v2", channel_id="UCa", channel_title="Alpha", view_count=9),
        ]

    def fake_fetch_channels(ids, **kwargs):
        return [_fake_channel("UCa", 7_777) for cid in ids if cid == "UCa"]

    monkeypatch.setattr(yc, "search_videos", fake_search_videos)
    monkeypatch.setattr(yc, "fetch_channels", fake_fetch_channels)
    results = yc.search_channels("alpha", max_results=10)
    assert len(results) == 1
    assert results[0].channel_id == "UCa"


def test_search_channels_min_subscribers_filters(monkeypatch):
    def fake_search_videos(query, max_results, **kwargs):
        return [
            yc.VideoInfo(video_id="v1", channel_id="UCa", channel_title="Alpha", view_count=9),
            yc.VideoInfo(video_id="v2", channel_id="UCb", channel_title="Beta", view_count=5),
        ]

    def fake_fetch_channels(ids, **kwargs):
        by_id = {"UCa": _fake_channel("UCa", 10_000), "UCb": _fake_channel("UCb", 1_000)}
        return [by_id[cid] for cid in ids if cid in by_id]

    monkeypatch.setattr(yc, "search_videos", fake_search_videos)
    monkeypatch.setattr(yc, "fetch_channels", fake_fetch_channels)

    results = yc.search_channels("q", max_results=10, min_subscribers=5_000)
    assert [c.channel_id for c in results] == ["UCa"]


def test_search_channels_empty_pool(monkeypatch):
    monkeypatch.setattr(yc, "search_videos", lambda *a, **k: [])
    assert yc.search_channels("nope", max_results=10) == []


def test_search_channels_zero_max_results(monkeypatch):
    assert yc.search_channels("q", max_results=0) == []


def test_base_opts_enable_js_runtimes():
    """Regression (2026-10): research scans hit YouTube bot checks when no JS
    runtime is enabled (yt-dlp 2026.x defaults to deno-only)."""
    runtimes = yc._base_opts()["js_runtimes"]
    assert {"deno", "node", "bun", "quickjs"} <= set(runtimes)


# --------------------------------------------------------------------------- #
# Regression (2026-10): the cookie jar must never travel to a foreign host
# --------------------------------------------------------------------------- #
def test_is_youtube_url_matches_the_host_not_the_text():
    """A substring check on 'youtube.com' accepts any host that mentions it."""
    assert yc.is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert yc.is_youtube_url("https://youtu.be/dQw4w9WgXcQ") is True
    assert yc.is_youtube_url("https://www.youtube.com/@handle") is True
    assert yc.is_youtube_url("ytsearch10:python") is True

    assert yc.is_youtube_url("https://youtube.com.attacker.tld/watch?v=x") is False
    assert yc.is_youtube_url("https://attacker.tld/?youtube.com") is False
    assert yc.is_youtube_url("https://www.youtube.com.evil.tld/x") is False
    assert yc.is_youtube_url("not a url") is False


def test_extract_refuses_a_non_youtube_url_before_any_request(
    isolated_appdata, tmp_path, monkeypatch
):
    """The configured cookies.txt holds a logged-in YouTube session — it must
    never be sent to a host the user pasted in."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    db.set_setting("youtube_cookies_file", str(cookies))

    def boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("yt-dlp was called for a non-YouTube URL")

    monkeypatch.setattr(yc.yt_dlp, "YoutubeDL", boom)

    with pytest.raises(ValueError):
        yc._extract("https://attacker.tld/?youtube.com", yc._base_opts())


def test_fetch_channel_rejects_a_non_youtube_reference(monkeypatch):
    def boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("yt-dlp was called for a non-YouTube URL")

    monkeypatch.setattr(yc.yt_dlp, "YoutubeDL", boom)

    with pytest.raises(ValueError):
        yc.fetch_channel("https://attacker.tld/?youtube.com")


# --------------------------------------------------------------------------- #
# Regression (2026-10): the API key must not ride in the query string
# --------------------------------------------------------------------------- #
def test_api_key_travels_in_a_header_not_the_query_string(monkeypatch):
    """httpx logs every request URL at INFO and the app log is a rotating file
    next to the user's data — a key in ?key= ended up in cleartext there."""
    calls: list[dict] = []

    class FakeResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return {"items": []}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, params=None, headers=None):
            calls.append({"url": url, "params": params or {}, "headers": headers or {}})
            return FakeResponse()

    monkeypatch.setattr(yc.httpx, "Client", FakeClient)

    yc._search_via_api("cats", 5, None, api_key="AIzaSECRET")

    assert calls, "no API request was made"
    for call in calls:
        assert "AIzaSECRET" not in call["url"]
        assert "key" not in call["params"]
        assert call["headers"].get("X-Goog-Api-Key") == "AIzaSECRET"


# --------------------------------------------------------------------------- #
# Regression (2026-10): the Data API path has to carry the same data as yt-dlp
# --------------------------------------------------------------------------- #
class _ApiResponse:
    def __init__(self, payload):
        self.status_code = 200
        self.text = "{}"
        self._payload = payload

    def json(self):
        return self._payload


class _ApiClient:
    """A Data API client that answers the three calls the client makes."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None, headers=None):
        if url.endswith("/channels"):
            return _ApiResponse(
                {
                    "items": [
                        {
                            "id": "UCx",
                            "snippet": {
                                "title": "Chan",
                                "description": "d",
                                "customUrl": "@chan",
                                "publishedAt": "2020-01-01T00:00:00Z",
                            },
                            "statistics": {
                                "subscriberCount": "100",
                                "videoCount": "2",
                                "viewCount": "500",
                            },
                            "contentDetails": {"relatedPlaylists": {"uploads": "UUx"}},
                        }
                    ]
                }
            )
        if url.endswith("/playlistItems"):
            return _ApiResponse(
                {
                    "items": [
                        {"contentDetails": {"videoId": "v1"}},
                        {"contentDetails": {"videoId": "v2"}},
                    ]
                }
            )
        if url.endswith("/videos"):
            return _ApiResponse(
                {
                    "items": [
                        {
                            "id": "v1",
                            "snippet": {
                                "title": "One",
                                "channelId": "UCx",
                                "channelTitle": "Chan",
                                "publishedAt": "2026-01-02T00:00:00Z",
                            },
                            "statistics": {"viewCount": "11", "likeCount": "1"},
                        },
                        {
                            "id": "v2",
                            "snippet": {
                                "title": "Two",
                                "channelId": "UCx",
                                "channelTitle": "Chan",
                                "publishedAt": "2026-01-01T00:00:00Z",
                            },
                            "statistics": {"viewCount": "22", "likeCount": "2"},
                        },
                    ]
                }
            )
        return _ApiResponse({"items": []})


def test_api_channel_fetch_includes_the_uploads_with_their_view_counts(monkeypatch):
    """With a Data API key the scorecard showed "No uploads fetched" and the
    AI prompt got no videos at all."""
    monkeypatch.setattr(yc.httpx, "Client", _ApiClient)
    db.set_setting("youtube_api_key", "AIzaTEST")

    info = yc.fetch_channel("UCx", uploads_with_stats=True)

    assert [u["video_id"] for u in info.uploads] == ["v1", "v2"]
    assert info.uploads[0]["view_count"] == 11
    assert info.uploads[0]["title"] == "One"


def test_api_video_fetch_carries_the_channel_title(monkeypatch):
    """A tracked video fell back to the channel id because the API path
    never read snippet.channelTitle."""
    monkeypatch.setattr(yc.httpx, "Client", _ApiClient)

    with yc.httpx.Client(timeout=20.0) as client:
        videos = yc._fetch_videos_via_api(client, ["v1"], "AIzaTEST")

    assert videos[0].channel_title == "Chan"
