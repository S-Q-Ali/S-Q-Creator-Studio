"""Engine helpers, presets and platform-specific download options."""

import pytest

from s_q_ali_media_downloader.engine import (
    DEFAULT_DELAY,
    DELAY_PRESETS,
    QUALITY_OPTIONS,
    DownloadThread,
    human_size,
    impersonation_summary,
    is_permanent,
    sanitize_filename,
    tidy_error,
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


def test_is_permanent():
    assert not is_permanent("rate limited")
    assert not is_permanent("TikTok refused the request — rate limited.")
    assert is_permanent("video not found")
    assert is_permanent("private video")


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
