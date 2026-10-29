"""Unit tests for agent schema data models."""

from s_q_ali_media_downloader.agent.schema import (
    AgentSearchResult,
    ChannelMetadata,
    SocialPlatform,
    SocialPresence,
    SocialStatus,
)


def test_social_presence_defaults():
    presence = SocialPresence(platform=SocialPlatform.FACEBOOK)
    assert presence.platform == SocialPlatform.FACEBOOK
    assert presence.status == SocialStatus.NOT_FOUND
    assert presence.confidence_score == 0.0


def test_channel_metadata_serialization():
    channel = ChannelMetadata(
        channel_id="UC123456",
        title="Test Creator",
        handle="@testcreator",
        subscribers=15000,
        subscribers_formatted="15.0K",
        youtube_url="https://www.youtube.com/channel/UC123456",
    )
    assert channel.channel_id == "UC123456"
    assert channel.facebook.status == SocialStatus.NOT_FOUND
    assert channel.instagram.status == SocialStatus.NOT_FOUND

    data = channel.model_dump()
    assert data["title"] == "Test Creator"
    assert data["subscribers"] == 15000


def test_agent_search_result_dump():
    result = AgentSearchResult(query="IShowSpeed edits", total_searched=10)
    assert result.query == "IShowSpeed edits"
    assert result.total_searched == 10
    assert len(result.channels) == 0


def test_a_tiktok_profile_carries_all_three_platforms():
    from s_q_ali_media_downloader.agent.schema import TikTokProfileMetadata

    profile = TikTokProfileMetadata(profile_id="1", handle="creator")

    assert profile.facebook.platform == SocialPlatform.FACEBOOK
    assert profile.instagram.platform == SocialPlatform.INSTAGRAM
    assert profile.youtube.platform == SocialPlatform.YOUTUBE
    assert profile.facebook.status == SocialStatus.NOT_FOUND
    assert profile.instagram.status == SocialStatus.NOT_FOUND
