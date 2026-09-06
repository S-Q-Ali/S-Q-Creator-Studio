"""Dual-mode YouTube Discovery Engine (YouTube Data API v3 + yt-dlp Zero-Key Scraper)."""

import logging

import httpx
import yt_dlp

from s_q_ali_media_downloader.agent.schema import ChannelMetadata

logger = logging.getLogger(__name__)


class YouTubeSearchTool:
    """Discovers YouTube channels by prompt, tag/hashtag, or channel name."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key.strip() if api_key else None

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

        logger.info("Using yt-dlp Zero-Key search scraper...")
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
        """Zero-Key search using yt-dlp ytsearch engine."""
        results: list[ChannelMetadata] = []
        search_term = f"ytsearch{min(max_results, 30)}:{query}"

        ydl_opts = {
            "extract_flat": True,
            "skip_download": True,
            "quiet": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(search_term, download=False)
                if not info or "entries" not in info:
                    return []

                seen_channels = set()
                for entry in info.get("entries", []):
                    if not entry or not isinstance(entry, dict):
                        continue

                    channel_id = entry.get("channel_id") or entry.get("uploader_id")
                    channel_name = entry.get("channel") or entry.get("uploader")
                    channel_url = entry.get("channel_url") or entry.get("uploader_url")

                    if not channel_id or channel_id in seen_channels:
                        continue

                    seen_channels.add(channel_id)
                    # NOTE: do NOT fabricate a handle from the channel display
                    # name — a name with spaces stripped is rarely the real
                    # YouTube handle, and probing FB/IG with it produces false
                    # matches. Leave handle=None; enrichment fills it in when a
                    # real canonical handle can be confirmed.
                    results.append(
                        ChannelMetadata(
                            channel_id=channel_id,
                            title=channel_name or "YouTube Creator",
                            handle=None,
                            subscribers=0,
                            subscribers_formatted="N/A",
                            youtube_url=channel_url
                            or f"https://www.youtube.com/channel/{channel_id}",
                            description=entry.get("description") or "",
                            latest_video_url=entry.get("url") or entry.get("webpage_url"),
                        )
                    )
            except Exception as e:
                logger.error(f"yt-dlp search failed: {e}")

        return results

    @staticmethod
    def format_subs(subs: int) -> str:
        """Formats integer subscriber count (e.g. 1820000 -> 1.8M)."""
        if subs >= 1_000_000:
            return f"{subs / 1_000_000:.1f}M"
        if subs >= 1_000:
            return f"{subs / 1_000:.1f}K"
        return str(subs)
