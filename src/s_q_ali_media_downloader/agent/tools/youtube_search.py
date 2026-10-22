"""Dual-mode YouTube Discovery Engine (YouTube Data API v3 + yt-dlp Zero-Key Scraper)."""

import logging

import httpx

from s_q_ali_media_downloader.agent.schema import ChannelMetadata
from s_q_ali_media_downloader.core.format import format_count
from s_q_ali_media_downloader.core.youtube_client import (
    ChannelInfo,
    search_channels,
)

logger = logging.getLogger(__name__)


class YouTubeSearchTool:
    """Discovers YouTube channels by prompt, tag/hashtag, or channel name."""

    def __init__(self, api_key: str | None = None):
        stripped = api_key.strip() if api_key else ""
        self.api_key = stripped or None

    def search_channels(
        self, query: str, max_results: int = 50, min_subscribers: int = 0
    ) -> list[ChannelMetadata]:
        """Entry point: Uses YouTube Data API if key is available, else yt-dlp scraper."""
        if self.api_key:
            try:
                logger.info("Using YouTube Data API v3 for search...")
                return self._search_via_api(query, max_results, min_subscribers)
            except Exception as e:
                logger.warning(f"YouTube API error: {e}. Falling back to yt-dlp scraper.")

        logger.info("Using yt-dlp shared search client...")
        return self._search_via_ytdlp(query, max_results, min_subscribers)

    def _search_via_api(
        self, query: str, max_results: int, min_subscribers: int
    ) -> list[ChannelMetadata]:
        """Queries YouTube Data API v3 search.list and channels.list."""
        results: list[ChannelMetadata] = []
        base_url = "https://www.googleapis.com/youtube/v3"

        # 1. Search for channels / videos matching query
        params = {
            "key": self.api_key,
            "part": "snippet",
            "q": query,
            "type": "channel",
            "maxResults": min(max_results, 50),
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.get(f"{base_url}/search", params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"YouTube API returned status {resp.status_code}: {resp.text}")

            data = resp.json()
            items = data.get("items", [])
            channel_ids = [item["snippet"]["channelId"] for item in items if "snippet" in item]

            if not channel_ids:
                # If no direct channel matches, search videos to extract creator channels
                params["type"] = "video"
                v_resp = client.get(f"{base_url}/search", params=params)
                if v_resp.status_code == 200:
                    v_items = v_resp.json().get("items", [])
                    channel_ids = list(
                        {
                            item["snippet"]["channelId"]
                            for item in v_items
                            if "snippet" in item and "channelId" in item["snippet"]
                        }
                    )

            if not channel_ids:
                return []

            # 2. Batch fetch channel metadata (`channels.list`)
            c_params = {
                "key": self.api_key,
                "part": "snippet,statistics,brandingSettings",
                "id": ",".join(channel_ids[:50]),
            }

            c_resp = client.get(f"{base_url}/channels", params=c_params)
            if c_resp.status_code != 200:
                raise RuntimeError(f"Channels API error: {c_resp.text}")

            c_data = c_resp.json()
            for item in c_data.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})

                subs = int(stats.get("subscriberCount", 0))
                if subs < min_subscribers:
                    continue

                ch_id = item["id"]
                custom_url = snippet.get("customUrl")
                handle = (
                    custom_url if custom_url else f"@{snippet.get('title', '').replace(' ', '')}"
                )

                # Extract banner links if present
                banner_links = []
                description = snippet.get("description", "")

                results.append(
                    ChannelMetadata(
                        channel_id=ch_id,
                        title=snippet.get("title", "Unknown Channel"),
                        handle=handle,
                        subscribers=subs,
                        subscribers_formatted=self.format_subs(subs),
                        youtube_url=f"https://www.youtube.com/channel/{ch_id}",
                        avatar_url=snippet.get("thumbnails", {}).get("default", {}).get("url"),
                        description=description,
                        banner_links=banner_links,
                    )
                )

        return results

    def _search_via_ytdlp(
        self, query: str, max_results: int, min_subscribers: int
    ) -> list[ChannelMetadata]:
        """Zero-Key channel discovery via the shared yt-dlp client (impersonation + enrich)."""
        channels = search_channels(
            query,
            max_results=max_results,
            min_subscribers=min_subscribers,
            api_key=self.api_key,
        )
        return [self._metadatum_from_channel_info(ch) for ch in channels]

    @staticmethod
    def _handle_from_custom_url(custom_url: str) -> str | None:
        if not custom_url:
            return None
        handle = custom_url.rstrip("/").split("/")[-1].lstrip("@")
        return handle or None

    @staticmethod
    def _metadatum_from_channel_info(info: ChannelInfo) -> ChannelMetadata:
        """Maps a shared ChannelInfo into the Agent's ChannelMetadata schema."""
        channel_url = (
            info.custom_url
            if info.custom_url.startswith(("http://", "https://"))
            else f"https://www.youtube.com/channel/{info.channel_id}"
        )
        latest_url = ""
        if info.uploads:
            latest_url = info.uploads[0].get("video_id", "") or ""
            if latest_url:
                latest_url = f"https://www.youtube.com/watch?v={latest_url}"
        return ChannelMetadata(
            channel_id=info.channel_id,
            title=info.title or "YouTube Creator",
            handle=YouTubeSearchTool._handle_from_custom_url(info.custom_url),
            subscribers=info.subscriber_count,
            subscribers_formatted=YouTubeSearchTool.format_subs(info.subscriber_count),
            youtube_url=channel_url,
            avatar_url=info.thumbnail_url or None,
            description=info.description or "",
            latest_video_url=latest_url or None,
        )

    @staticmethod
    def format_subs(subs: int) -> str:
        """Formats integer subscriber count (e.g. 1820000 -> 1.8M)."""
        return format_count(subs)
