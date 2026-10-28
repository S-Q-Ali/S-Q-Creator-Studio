"""URL classification and account normalisation."""

from s_q_ali_media_downloader.engine import (
    is_facebook_url,
    is_instagram_url,
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


def test_a_shorts_link_is_a_single_video_not_a_channel_or_playlist():
    """A Shorts link has to reach the download queue as one video. If it were
    read as a channel or a playlist, the app would try to expand it and the
    Short would never download.

    Verified live on 2026-10-21: a 59-second Short downloaded through
    DownloadThread._download_one as a 2.6 MB mp4 with its audio.
    """
    shorts = "https://www.youtube.com/shorts/6t-6ha1EVyA"

    assert is_youtube_url(shorts)
    assert not is_youtube_playlist_url(shorts)
    assert not is_youtube_channel_url(shorts)
    assert not is_profile_url(shorts)
    assert platform_of(shorts) == "YouTube"


def test_facebook_video_urls():
    assert is_facebook_url("https://www.facebook.com/watch/?v=1234567890")
    assert is_facebook_url("https://www.facebook.com/watch?v=1234567890")
    assert is_facebook_url("https://www.facebook.com/MrBeast/videos/1234567890/")
    assert is_facebook_url("https://www.facebook.com/reel/1234567890")
    assert is_facebook_url("https://fb.watch/abc123/")
    assert is_facebook_url("https://m.facebook.com/watch/?v=1234567890")


def test_facebook_non_media_rejected():
    assert not is_facebook_url("https://www.facebook.com/MrBeast")
    assert not is_facebook_url("https://www.facebook.com/profile.php?id=123")
    assert not is_facebook_url("https://www.facebook.com/login")
    assert not is_facebook_url("https://www.facebook.com/groups/123")
    assert not is_facebook_url("https://www.facebook.com/")
    assert not is_facebook_url("https://example.com/watch?v=123")


def test_instagram_post_urls():
    assert is_instagram_url("https://www.instagram.com/p/Cabc123/")
    assert is_instagram_url("https://www.instagram.com/reel/Cabc123/")
    assert is_instagram_url("https://www.instagram.com/reels/Cabc123/")
    assert is_instagram_url("https://www.instagram.com/tv/Cabc123/")


def test_instagram_non_media_rejected():
    assert not is_instagram_url("https://www.instagram.com/mrbeast/")
    assert not is_instagram_url("https://www.instagram.com/")
    assert not is_instagram_url("https://www.instagram.com/explore/")
    assert not is_instagram_url("https://www.instagram.com/stories/mrbeast/123")
    assert not is_instagram_url("https://example.com/p/Cabc123/")


def test_platform_of():
    assert platform_of("https://www.tiktok.com/@u/video/1") == "TikTok"
    assert platform_of("https://youtu.be/x") == "YouTube"
    assert platform_of("https://www.youtube.com/watch?v=x") == "YouTube"
    assert platform_of("https://www.youtube.com/shorts/x") == "YouTube"
    assert platform_of("https://www.facebook.com/reel/123") == "Facebook"
    assert platform_of("https://www.instagram.com/p/Cabc123/") == "Instagram"
    assert platform_of("https://example.com") is None


def test_normalize_account():
    assert normalize_account("@user") == ("user", "https://www.tiktok.com/@user")
    assert normalize_account("https://www.tiktok.com/@user") == (
        "user",
        "https://www.tiktok.com/@user",
    )
    assert normalize_account("") == (None, None)
    assert normalize_account("not a valid @@@name") == (None, None)
