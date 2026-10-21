"""Tests for YouTubeFetchThread — verifies playlistend is honored without extract_flat."""

from unittest.mock import patch

from s_q_ali_media_downloader.engine import YouTubeFetchThread


def test_limit_is_clamped():
    thread = YouTubeFetchThread("https://www.youtube.com/@somechannel", limit=9999)
    assert thread.limit == 500
    thread = YouTubeFetchThread("https://www.youtube.com/@somechannel", limit=0)
    assert thread.limit == 1


@patch("yt_dlp.YoutubeDL")
def test_extract_flat_is_not_passed(mock_ydl_cls):
    """The key regression: 'extract_flat' must NOT be in the opts passed to yt-dlp."""
    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts=None):
            captured_opts.update(opts or {})
            self.opts = opts or {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            return {
                "_type": "playlist",
                "title": "Test Channel",
                # A real video id is eleven characters; the expansion drops
                # anything else (a channel's tab entries carry a 24-character
                # channel id).
                "entries": [{"id": f"vid{i:08d}"} for i in range(30)],
            }

    mock_ydl_cls.side_effect = FakeYDL

    thread = YouTubeFetchThread("https://www.youtube.com/@somechannel", limit=20)
    found_urls = []
    found_label = []

    def on_found(urls, label):
        found_urls.append(urls)
        found_label.append(label)

    thread.found.connect(on_found)
    thread.run()

    assert "extract_flat" not in captured_opts
    assert captured_opts.get("playlistend") == 20
    assert len(found_urls[0]) == 20
    assert all(url.startswith("https://www.youtube.com/watch?v=") for url in found_urls[0])
    assert found_label[0] == "Test Channel"


@patch("yt_dlp.YoutubeDL")
def test_js_runtimes_enabled(mock_ydl_cls):
    """Regression (2026-10): without an enabled JS runtime (node/bun here,
    deno absent) yt-dlp 2026.x bot-checks YouTube extraction, so channel /
    playlist expansion must pass js_runtimes."""
    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts=None):
            captured_opts.update(opts or {})

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            return {"_type": "playlist", "title": "T", "entries": [{"id": "abc"}]}

    mock_ydl_cls.side_effect = FakeYDL

    thread = YouTubeFetchThread("https://www.youtube.com/@somechannel", limit=5)
    thread.run()

    runtimes = captured_opts.get("js_runtimes") or {}
    assert {"deno", "node", "bun", "quickjs"} <= set(runtimes)
