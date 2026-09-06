"""Tool for fetching deep channel bio, banner outbound links, and video descriptions."""

import logging

import httpx

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from s_q_ali_media_downloader.agent.schema import ChannelMetadata
from s_q_ali_media_downloader.agent.tools.link_parser import LinkParserTool

logger = logging.getLogger(__name__)


class MetadataExtractorTool:
    """Enriches ChannelMetadata by parsing About bios, banner links, and latest video descriptions."""

    def enrich_channel_metadata(self, channel: ChannelMetadata) -> ChannelMetadata:
        """Deeply inspects YouTube channel page and latest video descriptions to extract social links."""
        # 1. Parse description & raw links
        fb_url, ig_url, tiktok_url = LinkParserTool.extract_social_links(
            channel.description, channel.banner_links
        )

        # 2. If any social link is missing, inspect the channel about page
        if not fb_url or not ig_url or not tiktok_url:
            extra_fb, extra_ig, extra_tiktok = self._scrape_channel_about(channel.youtube_url)
            fb_url = fb_url or extra_fb
            ig_url = ig_url or extra_ig
            tiktok_url = tiktok_url or extra_tiktok

        # 3. Store extracted candidate URLs in channel metadata (source = bio_link)
        if fb_url:
            channel.facebook.verified_url = fb_url
            channel.facebook.handle = LinkParserTool.extract_handle_from_url(fb_url)
            channel.facebook.source = "bio_link"
        if ig_url:
            channel.instagram.verified_url = ig_url
            channel.instagram.handle = LinkParserTool.extract_handle_from_url(ig_url)
            channel.instagram.source = "bio_link"
        if tiktok_url:
            channel.tiktok.verified_url = tiktok_url
            channel.tiktok.handle = LinkParserTool.extract_handle_from_url(tiktok_url)
            channel.tiktok.source = "bio_link"

        return channel

    def _scrape_channel_about(self, channel_url: str) -> tuple[str | None, str | None, str | None]:
        """Light HTML scrape of channel landing page to extract external links."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            }
            about_url = channel_url.rstrip("/") + "/about"
            with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(about_url)
                if resp.status_code == 200:
                    html = resp.text
                    return LinkParserTool.extract_social_links(html)
        except Exception as e:
            logger.warning(f"Failed to scrape channel about page {channel_url}: {e}")

        return None, None, None
