"""Unit tests for YouTubeSearchTool and YouTube channel URL normalization."""

from s_q_ali_media_downloader.agent.tools.youtube_search import YouTubeSearchTool
from s_q_ali_media_downloader.engine import is_youtube_channel_url, normalize_youtube_channel_url


def test_format_subs_helper():
    assert YouTubeSearchTool.format_subs(1820000) == "1.8M"
    assert YouTubeSearchTool.format_subs(64500) == "64.5K"
    assert YouTubeSearchTool.format_subs(450) == "450"


def test_youtube_search_initialization():
    tool_no_key = YouTubeSearchTool()
    assert tool_no_key.api_key is None

    tool_with_key = YouTubeSearchTool(api_key="  AIzaSyTESTKEY123  ")
    assert tool_with_key.api_key == "AIzaSyTESTKEY123"


def test_youtube_channel_shorthand_urls():
    shorthand_url = "https://youtube.com/UCisZ2efLJn1Dxvn4th6mwlA"
    assert is_youtube_channel_url(shorthand_url) is True

    normalized = normalize_youtube_channel_url(shorthand_url)
    assert normalized == "https://www.youtube.com/channel/UCisZ2efLJn1Dxvn4th6mwlA"


def test_youtube_channel_standard_urls():
    standard_url = "https://www.youtube.com/channel/UCisZ2efLJn1Dxvn4th6mwlA"
    assert is_youtube_channel_url(standard_url) is True
    assert normalize_youtube_channel_url(standard_url) == standard_url


def test_metadatum_maps_channel_info():
    from s_q_ali_media_downloader.niche_research.tools.youtube_client import ChannelInfo

    info = ChannelInfo(
        channel_id="UCisZ2efLJn1Dxvn4th6mwlA",
        title="Tester",
        description="About me",
        thumbnail_url="https://yt3.googleusercontent.com/avatar",
        custom_url="https://www.youtube.com/@tester",
        subscriber_count=123_000,
        uploads=[{"video_id": "abc123xyz99"}],
    )
    ch = YouTubeSearchTool._metadatum_from_channel_info(info)
    assert ch.channel_id == "UCisZ2efLJn1Dxvn4th6mwlA"
    assert ch.title == "Tester"
    assert ch.handle == "tester"
    assert ch.subscribers == 123_000
    assert ch.subscribers_formatted == "123.0K"
    assert ch.avatar_url == "https://yt3.googleusercontent.com/avatar"
    assert ch.description == "About me"
    assert ch.latest_video_url == "https://www.youtube.com/watch?v=abc123xyz99"


def test_metadatum_falls_back_to_channel_url():
    from s_q_ali_media_downloader.niche_research.tools.youtube_client import ChannelInfo

    info = ChannelInfo(channel_id="UCisZ2efLJn1Dxvn4th6mwlA", title="No Handle")
    ch = YouTubeSearchTool._metadatum_from_channel_info(info)
    assert ch.handle is None
    assert ch.youtube_url == "https://www.youtube.com/channel/UCisZ2efLJn1Dxvn4th6mwlA"
    assert ch.latest_video_url is None


def test_metadatum_empty_title_defaults():
    from s_q_ali_media_downloader.niche_research.tools.youtube_client import ChannelInfo

    info = ChannelInfo(channel_id="UCisZ2efLJn1Dxvn4th6mwlA")
    ch = YouTubeSearchTool._metadatum_from_channel_info(info)
    assert ch.title == "YouTube Creator"


def test_handle_from_custom_url_variants():
    assert YouTubeSearchTool._handle_from_custom_url("https://www.youtube.com/@tester") == "tester"
    assert YouTubeSearchTool._handle_from_custom_url("https://www.youtube.com/@tester/") == "tester"
    assert YouTubeSearchTool._handle_from_custom_url("tester") == "tester"
    assert YouTubeSearchTool._handle_from_custom_url("") is None
    assert YouTubeSearchTool._handle_from_custom_url(None) is None


def test_search_via_ytdlp_delegates_to_shared_client(monkeypatch):
    from s_q_ali_media_downloader.agent.tools import youtube_search as ys
    from s_q_ali_media_downloader.niche_research.tools.youtube_client import ChannelInfo

    captured = {}

    def fake_search_channels(query, max_results, **kwargs):
        captured["query"] = query
        captured["max_results"] = max_results
        captured["min_subscribers"] = kwargs.get("min_subscribers")
        captured["api_key"] = kwargs.get("api_key")
        return [ChannelInfo(channel_id="UCx", title="X", subscriber_count=99)]

    monkeypatch.setattr(ys, "search_channels", fake_search_channels)
    tool = YouTubeSearchTool(api_key="    ")
    results = tool._search_via_ytdlp("gaming", 50, 1000)
    assert captured["query"] == "gaming"
    assert captured["max_results"] == 50
    assert captured["min_subscribers"] == 1000
    assert captured["api_key"] is None
    assert len(results) == 1
    assert results[0].channel_id == "UCx"
