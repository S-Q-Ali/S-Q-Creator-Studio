"""Engine helpers, presets and platform-specific download options."""

import types
from pathlib import Path
from unittest.mock import patch

import pytest
import yt_dlp
from packaging.version import Version

from s_q_ali_media_downloader.engine import (
    DEFAULT_DELAY,
    DELAY_PRESETS,
    QUALITY_OPTIONS,
    TEMP_PREFIX,
    AccountFetchThread,
    DownloadThread,
    YouTubeFetchThread,
    human_size,
    impersonation_summary,
    is_permanent,
    js_runtime_opts,
    sanitize_filename,
    tidy_error,
    tiktok_page_url,
    unique_basename,
)


def test_sanitize_filename():
    assert sanitize_filename("") == "untitled"
    assert sanitize_filename('a/b\\c:d*e?f"g<h>i|') == "abcdefghi"
    assert sanitize_filename("  hello   world  ") == "hello world"
    assert sanitize_filename("..") == "untitled"
    assert len(sanitize_filename("x" * 300)) <= 150


def test_unique_basename(tmp_path):
    assert unique_basename(str(tmp_path), "video") == "video"
    (tmp_path / "video.mp4").write_bytes(b"x")
    assert unique_basename(str(tmp_path), "video") == "video (2)"
    (tmp_path / "video (2).mp4").write_bytes(b"x")
    assert unique_basename(str(tmp_path), "video") == "video (3)"


def test_human_size():
    assert human_size(None) == "—"
    assert human_size(0) == "—"
    assert human_size(500) == "500 B"
    assert human_size(1536) == "1.5 KB"
    assert human_size(5 * 1024 * 1024) == "5.0 MB"


def test_tidy_error():
    assert (
        tidy_error(Exception("ERROR: [TikTok] 3: 404 not found"))
        == "Video is unavailable, private or deleted."
    )
    assert "rate limited" in tidy_error(Exception("rehydration failed")).lower()
    assert "ffmpeg" not in tidy_error(Exception("a strange problem")).lower()
    bot_check = tidy_error(
        Exception(
            "Sign in to confirm you're not a bot. Use --cookies-from-browser "
            "or --cookies for the authentication."
        )
    )
    assert "bot" in bot_check.lower() and "wait" in bot_check.lower()
    profile_flake = tidy_error(Exception("Unable to extract secondary user ID"))
    assert "profile" in profile_flake.lower() and "retry" in profile_flake.lower()
    assert not is_permanent(bot_check)
    assert not is_permanent(profile_flake)


def test_is_permanent():
    assert not is_permanent("rate limited")
    assert not is_permanent("TikTok refused the request — rate limited.")
    assert is_permanent("video not found")
    assert is_permanent("private video")
    assert is_permanent("this format needs ffmpeg to merge. pick a lower quality.")
    assert is_permanent(tidy_error(Exception("needs ffmpeg to merge audio and video")))


def test_download_temp_name_includes_job_uid(tmp_path, monkeypatch):
    """Two jobs downloading the same URL must not share one temp file."""
    import s_q_ali_media_downloader.engine as engine_module

    captured = {}

    class FakeYDL:
        def __init__(self, opts):
            captured["outtmpl"] = opts.get("outtmpl")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=True):
            raise RuntimeError("stop before downloading")

    thread = DownloadThread(
        jobs=[], output_dir=str(tmp_path), quality="1080p"
    )
    monkeypatch.setattr(
        engine_module,
        "yt_dlp",
        types.SimpleNamespace(YoutubeDL=FakeYDL),
    )
    try:
        thread._download_one(7, "https://www.youtube.com/watch?v=abc123")
    except RuntimeError:
        pass
    assert "-7." in captured["outtmpl"], captured["outtmpl"]


def test_failed_download_removes_only_its_own_temp_files(tmp_path, monkeypatch):
    thread = DownloadThread(
        jobs=[], output_dir=str(tmp_path), quality="1080p"
    )
    uid = 7
    other_uid = 99
    vid = "abc123"
    own = tmp_path / f"{TEMP_PREFIX}{vid}-{uid}.part"
    other = tmp_path / f"{TEMP_PREFIX}{vid}-{other_uid}.part"
    own.write_text("partial")
    other.write_text("partial")

    monkeypatch.setattr(
        thread,
        "_attempt",
        lambda uid_arg, url: (False, "\u2014", "boom"),
    )
    thread._try_with_inline(uid, "https://www.youtube.com/watch?v=abc123", "pass 1")

    assert not own.exists(), "this job's temp file should be removed on failure"
    assert other.exists(), "another job's temp file must not be touched"


def test_ytdlp_floor_guards_tiktok_account_fetch():
    """Regression: bundled yt-dlp must stay recent enough for TikTok profile
    (account) fetches. TikTok profile extraction broke in yt-dlp <=2026.8.19
    builds ("Unable to extract secondary user ID"); the 2026.8.19+ extractor
    fixed it. If the floor drops below that, or the installed copy falls below
    the documented floor, this test fails so the regression can't silently
    reappear. Note (2026-10): on yt-dlp 2026.8.19 the same "secondary user
    ID" error still appears INTERMITTENTLY on TikTok's side (fresh pages
    sometimes lack the SSR data) — the app retries and surfaces a friendly
    message; a permanent fix needs a newer yt-dlp release."""
    project_root = Path(__file__).resolve().parents[1]
    reqs = (project_root / "requirements.txt").read_text(encoding="utf-8")
    floor = None
    for line in reqs.splitlines():
        line = line.strip()
        if line.lower().startswith("yt-dlp"):
            floor = line.split(">=", 1)[1].strip().strip('"')
            break
    assert Version(floor) >= Version("2026.8.19"), (
        f"yt-dlp floor must stay at/above 2026.8.19 (TikTok account fetch fix); got {floor}"
    )

    installed = Version(yt_dlp.version.__version__)
    assert installed >= Version(floor), (
        f"Installed yt-dlp {installed} is older than the documented floor {floor}; "
        "run `pip install -U 'yt-dlp>=2026.8.19'` (TikTok account fetches break otherwise)."
    )


def test_presets_structure():
    assert "Best available" in QUALITY_OPTIONS
    assert "Audio only" in QUALITY_OPTIONS
    assert DEFAULT_DELAY in DELAY_PRESETS
    low, high = DELAY_PRESETS[DEFAULT_DELAY]
    assert low < high


def test_quality_formats_are_nonempty():
    for key, fmt in QUALITY_OPTIONS.items():
        assert key
        assert fmt
        assert "/" in fmt


def test_impersonation_available():
    try:
        import curl_cffi  # noqa: F401
        from yt_dlp.networking.impersonate import ImpersonateTarget  # noqa: F401
    except ImportError:
        pytest.skip("curl_cffi / ImpersonateTarget not installed")
    ok, label = impersonation_summary()
    assert ok, label


def test_base_opts_platform_behavior():
    thread = DownloadThread([], "out", "1080p")
    youtube = thread._base_opts("YouTube")
    tiktok = thread._base_opts("TikTok")
    assert "impersonate" not in youtube
    assert "impersonate" in tiktok
    assert youtube["noplaylist"] is True


def test_js_runtimes_enabled_in_download_opts():
    """Regression (2026-10): yt-dlp 2026.x runs YouTube web-extraction
    challenges through a JS runtime (EJS) and enables only deno by default.
    With no deno installed, every YouTube download died with "Sign in to
    confirm you're not a bot". All supported runtimes must stay enabled so
    node/bun get used when present."""
    runtimes = js_runtime_opts()
    assert {"deno", "node", "bun", "quickjs"} <= set(runtimes)
    thread = DownloadThread([], "out", "1080p")
    assert thread._base_opts("YouTube")["js_runtimes"] == runtimes
    assert thread._base_opts("TikTok")["js_runtimes"] == runtimes


def test_youtube_downloads_use_po_token_free_clients():
    """Regression (2026-10): YouTube's default "web" player client needs a
    PO token that only a browser can mint, so every single-video download
    died with "Sign in to confirm you're not a bot". The embedded and mobile
    web clients answer without one and must be tried first."""
    thread = DownloadThread([], "out", "1080p")
    opts = thread._base_opts("YouTube")
    clients = opts["extractor_args"]["youtube"]["player_client"]
    assert clients[0] == "web_embedded"
    assert "mweb" in clients
    assert "web" in clients
    assert "impersonate" not in opts
    assert "extractor_args" not in thread._base_opts("TikTok")


def test_tiktok_page_url_prefers_page_over_cdn():
    """Regression (2026-10): TikTok profile entries put a signed CDN media
    URL in "url" (HTTP 403 when downloaded). The page URL must be used."""
    entry = {
        "id": "7694797676306615583",
        "url": "https://v19-webapp-prime.tiktok.com/video/tos/alisg/x/?a=1988",
        "webpage_url": "https://www.tiktok.com/@tiktok/video/7694797676306615583",
    }
    assert (
        tiktok_page_url(entry, "tiktok")
        == "https://www.tiktok.com/@tiktok/video/7694797676306615583"
    )
    # No webpage_url — the id is rebuilt into a page URL.
    only_id = {"id": "7694797676306615583", "url": "https://v19-webapp-prime.tiktok.com/x"}
    assert (
        tiktok_page_url(only_id, "tiktok")
        == "https://www.tiktok.com/@tiktok/video/7694797676306615583"
    )
    # Nothing usable — no URL is invented.
    assert tiktok_page_url({"url": "https://v19-webapp-prime.tiktok.com/x"}, "tiktok") == ""


def test_account_fetch_thread_returns_page_urls():
    """The profile expansion must queue downloadable page URLs, not the
    signed CDN media URLs TikTok puts in each entry."""
    captured = {}

    class FakeYDL:
        def __init__(self, opts=None):
            captured.update(opts or {})

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            return {
                "_type": "playlist",
                "entries": [
                    {
                        "id": "7694797676306615583",
                        "url": "https://v19-webapp-prime.tiktok.com/video/tos/x/?a=1988",
                        "webpage_url": (
                            "https://www.tiktok.com/@tiktok/video/7694797676306615583"
                        ),
                    }
                ],
            }

    with patch("yt_dlp.YoutubeDL", FakeYDL):
        thread = AccountFetchThread("tiktok", limit=5)
        found = []
        thread.found.connect(lambda urls, name: found.append(urls))
        thread.run()

    assert found == [["https://www.tiktok.com/@tiktok/video/7694797676306615583"]]


# --------------------------------------------------------------------------- #
# Expanding a YouTube channel
# --------------------------------------------------------------------------- #
class _FakeChannelYDL:
    """Mimics yt-dlp 2026.8.19 on a channel URL.

    A channel URL does not list the channel's videos — it lists the
    channel's TABS, and every entry carries the channel id. Verified live on
    2026-10-21 for @mkbhd, @MrBeast and @veritasium: three entries, no
    video among them.
    """

    def __init__(self, opts=None):
        self.opts = opts or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        if url.endswith("/videos"):
            return {
                "_type": "playlist",
                "entries": [
                    {"id": "vidAAAAAAAA", "title": "A long video"},
                    {"id": "vidBBBBBBBB", "title": "Another video"},
                ],
            }
        if url.endswith("/shorts"):
            return {
                "_type": "playlist",
                "entries": [
                    {"id": "shoAAAAAAAA", "title": "A short"},
                    {"id": "shoBBBBBBBB", "title": "Another short"},
                ],
            }
        return {
            "_type": "playlist",
            "entries": [
                {"id": "UCabcdefghijklmnopqrstuv", "title": "Chan - Videos"},
                {"id": "UCabcdefghijklmnopqrstuv", "title": "Chan - Shorts"},
            ],
        }


def test_a_channel_expands_into_its_videos_not_its_tabs():
    """Regression (2026-10): the expansion queued watch?v=UC<channel id> —
    a channel id is not a video, so nothing downloaded."""
    with patch("yt_dlp.YoutubeDL", _FakeChannelYDL):
        thread = YouTubeFetchThread("https://www.youtube.com/@chan")
        found = []
        thread.found.connect(lambda urls, name: found.append(urls))
        thread.run()

    assert found == [
        [
            "https://www.youtube.com/watch?v=vidAAAAAAAA",
            "https://www.youtube.com/watch?v=vidBBBBBBBB",
        ]
    ]


def test_the_shorts_tab_is_fetched_when_asked_for():
    """A channel's Shorts live in their own tab, which the app never visited."""
    with patch("yt_dlp.YoutubeDL", _FakeChannelYDL):
        thread = YouTubeFetchThread(
            "https://www.youtube.com/@chan", include_shorts=True
        )
        found = []
        thread.found.connect(lambda urls, name: found.append(urls))
        thread.run()

    assert found == [
        [
            "https://www.youtube.com/watch?v=vidAAAAAAAA",
            "https://www.youtube.com/watch?v=vidBBBBBBBB",
            "https://www.youtube.com/watch?v=shoAAAAAAAA",
            "https://www.youtube.com/watch?v=shoBBBBBBBB",
        ]
    ]


def test_a_playlist_is_still_expanded_as_it_was():
    """A playlist URL is not a channel: it lists its videos directly."""

    class _FakePlaylistYDL(_FakeChannelYDL):
        def extract_info(self, url, download=False):
            return {
                "_type": "playlist",
                "entries": [{"id": "vidAAAAAAAA", "title": "A long video"}],
            }

    with patch("yt_dlp.YoutubeDL", _FakePlaylistYDL):
        thread = YouTubeFetchThread("https://www.youtube.com/playlist?list=PLabc")
        found = []
        thread.found.connect(lambda urls, name: found.append(urls))
        thread.run()

    assert found == [["https://www.youtube.com/watch?v=vidAAAAAAAA"]]


def test_download_error_is_not_swallowed():
    """Regression (2026-10): the extractor error used to be discarded, so
    every failure surfaced as "Download finished but the file is missing"
    and the app log never recorded a reason."""

    class Boom(Exception):
        pass

    class FakeYDL:
        def __init__(self, opts=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            raise Boom("ERROR: [youtube] abc: Sign in to confirm you're not a bot.")

    thread = DownloadThread([], "out", "Best available")
    with patch("yt_dlp.YoutubeDL", FakeYDL), pytest.raises(Boom):
        thread._download_one(1, "https://www.youtube.com/watch?v=abc")
