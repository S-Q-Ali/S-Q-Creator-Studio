"""URL classification and account normalisation."""

from s_q_ali_media_downloader.engine import (
    is_profile_url,
    is_tiktok_url,
    is_youtube_channel_url,
    is_youtube_playlist_url,
    is_youtube_url,
    normalize_account,
    platform_of,
)


def test_tiktok_video_urls():
    assert is_tiktok_url("https://www.tiktok.com/@user/video/1234567890123456789")
    assert is_tiktok_url("https://www.tiktok.com/@user/photo/1234567890123456789")
    assert is_tiktok_url("https://vm.tiktok.com/AbCdEfGh")
    assert is_tiktok_url("https://vt.tiktok.com/AbCdEfGh/")


def test_tiktok_non_media_rejected():
    assert not is_tiktok_url("https://www.tiktok.com/@user")
    assert not is_tiktok_url("https://www.tiktok.com/explore")
    assert not is_tiktok_url("https://www.tiktok.com/login")
    assert not is_tiktok_url("https://www.tiktok.com/analytics")
    assert not is_tiktok_url("https://example.com/video/123")


def test_tiktok_cdn_media_urls_rejected():
    """Regression (2026-10): TikTok profile listings hand out signed CDN
    media URLs. They contain "/video/" but answer HTTP 403 when downloaded,
    so they must never reach the download queue."""
    cdn = (
        "https://v19-webapp-prime.tiktok.com/video/tos/alisg/tos-alisg-ve-37c799/"
        "oERJRrAyfAIQJlbgQDRqNiBecEEVFEyR0WHEjy/?a=1988&mime_type=video_mp4"
        "&expire=1792620888&signature=54266c3f9d21a91434259e17410722f0"
    )
    assert not is_tiktok_url(cdn)
    # The page URL for the same video is still accepted.
    assert is_tiktok_url("https://www.tiktok.com/@user/video/7694797676306615583")


def test_profile_urls():
    assert is_profile_url("https://www.tiktok.com/@user")
    assert is_profile_url("https://www.tiktok.com/@user?lang=en")
    assert not is_profile_url("https://www.tiktok.com/@user/video/123")


def test_youtube_video_urls():
    assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert is_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert is_youtube_url("https://www.youtube.com/live/abc")
    assert is_youtube_url("https://www.youtube.com/v/abc")
    assert is_youtube_url("https://www.youtube.com/embed/abc")
    assert not is_youtube_url("https://www.youtube.com/feed/trending")
    assert not is_youtube_url("https://example.com/watch?v=x")


def test_youtube_playlist_and_channel():
    assert is_youtube_playlist_url("https://www.youtube.com/playlist?list=PLabc")
    assert not is_youtube_playlist_url("https://www.youtube.com/watch?v=x")
    assert is_youtube_channel_url("https://www.youtube.com/@channel")
    assert is_youtube_channel_url("https://www.youtube.com/channel/UCabc")
    assert is_youtube_channel_url("https://www.youtube.com/c/ChannelName")
    assert is_youtube_channel_url("https://www.youtube.com/user/legacy")
    assert not is_youtube_channel_url("https://www.youtube.com/watch?v=x")


def test_platform_of():
    assert platform_of("https://www.tiktok.com/@u/video/1") == "TikTok"
    assert platform_of("https://youtu.be/x") == "YouTube"
    assert platform_of("https://www.youtube.com/watch?v=x") == "YouTube"
    assert platform_of("https://example.com") is None


def test_normalize_account():
    assert normalize_account("@user") == ("user", "https://www.tiktok.com/@user")
    assert normalize_account("https://www.tiktok.com/@user") == (
        "user",
        "https://www.tiktok.com/@user",
    )
    assert normalize_account("") == (None, None)
    assert normalize_account("not a valid @@@name") == (None, None)
