"""Tests for MetadataExtractorTool (bio-link enrichment, no network)."""

from s_q_ali_media_downloader.agent.schema import (
    ChannelMetadata,
    SocialPlatform,
)
from s_q_ali_media_downloader.agent.tools.metadata_extractor import MetadataExtractorTool


def _channel(**overrides):
    defaults = {
        "channel_id": "UCtest",
        "title": "Test Channel",
        "handle": "@testchannel",
        "youtube_url": "https://www.youtube.com/@testchannel",
    }
    return ChannelMetadata(**{**defaults, **overrides})


def test_enrich_from_description_links():
    channel = _channel(
        description=(
            "Follow me everywhere! "
            "https://www.facebook.com/testpage "
            "https://instagram.com/testgram "
            "https://www.tiktok.com/@testtok"
        )
    )
    tool = MetadataExtractorTool()
    enriched = tool.enrich_channel_metadata(channel)

    assert enriched.facebook.platform == SocialPlatform.FACEBOOK
    assert enriched.facebook.verified_url is not None
    assert enriched.facebook.verified_url.endswith("facebook.com/testpage/")
    assert enriched.facebook.source == "bio_link"

    assert enriched.instagram.verified_url is not None
    assert enriched.instagram.verified_url.endswith("instagram.com/testgram/")
    assert enriched.instagram.handle == "testgram"
    assert enriched.instagram.source == "bio_link"

    assert enriched.tiktok.verified_url is not None
    assert enriched.tiktok.verified_url.endswith("tiktok.com/@testtok/")
    assert enriched.tiktok.handle == "testtok"
    assert enriched.tiktok.source == "bio_link"


def test_enrich_partial_links_keep_missing():
    # No Facebook URL present: scrape path is skipped too since we do not want
    # network in tests, and the remaining presence stays NOT_FOUND.
    channel = _channel(description="https://instagram.com/testgram")
    tool = MetadataExtractorTool()
    enriched = tool.enrich_channel_metadata(channel)

    assert enriched.instagram.verified_url is not None
    assert enriched.instagram.verified_url.endswith("instagram.com/testgram/")
    assert enriched.facebook.status.value == "not_found"
    assert enriched.tiktok.status.value == "not_found"
    assert enriched.instagram.source == "bio_link"


def test_enrich_empty_description_is_noop():
    channel = _channel(description="")
    tool = MetadataExtractorTool()
    enriched = tool.enrich_channel_metadata(channel)
    for presence in (enriched.facebook, enriched.instagram, enriched.tiktok):
        assert presence.verified_url is None
        assert presence.source != "bio_link" or presence.verified_url is None