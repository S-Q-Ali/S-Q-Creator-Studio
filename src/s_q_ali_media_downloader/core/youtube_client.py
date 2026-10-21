"""YouTube fetch layer for Niche Research (yt-dlp primary, API-key hybrid optional).

Ported from the companion research web tool's lib/tools/youtubeClient + friends. The default path is
yt-dlp with curl_cffi impersonation — zero API key, zero quota, unlimited calls.
If the user configures a YouTube Data API v3 key (Settings → API Keys) the client
uses it where it produces better data (currently: search + video stats + channel
metadata).
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import yt_dlp
from yt_dlp.utils import DateRange

from s_q_ali_media_downloader.core import settings_store
from s_q_ali_media_downloader.engine import impersonate_target, js_runtime_opts

logger = logging.getLogger(__name__)

YT_BASE = "https://www.googleapis.com/youtube/v3"


def _api_headers(key: str) -> dict[str, str]:
    """Send the YouTube Data API key in a header.

    A key in the query string is part of the request URL: it shows up in
    every proxy log and in the httpx request log, which this app writes to
    disk next to the user's data.
    """
    return {"X-Goog-Api-Key": key}
VIDEO_ID_RE = re.compile(r"(?:v=|/shorts/|/v/|/embed/|youtu\.be/)([A-Za-z0-9_-]{11})")
CHANNEL_ID_RE = re.compile(r"(?:/channel/|channel_id=)(UC[A-Za-z0-9_-]{22})")


class YoutubeApiError(Exception):
    """Base error for all YouTube fetch failures."""


class RateLimitError(YoutubeApiError):
    """Exceeded quota or YouTube asked the scraper to sign in (bot check)."""


class NotFoundError(YoutubeApiError):
    """The requested video/channel does not exist or was removed."""


@dataclass
class VideoInfo:
    video_id: str = ""
    channel_id: str = ""
    title: str = ""
    description: str = ""
    published_at: str = ""  # ISO-8601; yt-dlp gives "YYYY-MM-DDTHH:MM:SSZ"
    duration_seconds: int = 0
    thumbnail_url: str = ""
    language: str | None = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    tags: list[str] = field(default_factory=list)
    category_id: str = ""
    channel_title: str = ""


@dataclass
class ChannelInfo:
    channel_id: str = ""
    title: str = ""
    description: str = ""
    thumbnail_url: str = ""
    custom_url: str = ""
    country: str = ""
    publish_date: str = ""  # best-effort channel join date (usually empty on yt-dlp)
    subscriber_count: int = 0
    video_count: int = 0
    view_count: int = 0
    channel_tags: list[str] = field(default_factory=list)
    topic_categories: list[str] = field(default_factory=list)
    uploads: list[dict[str, Any]] = field(default_factory=list)


def get_api_key() -> str | None:
    value = settings_store.get_setting("youtube_api_key")
    return (value or "").strip() or None


def get_cookies_file() -> str | None:
    """Path of the configured Netscape ``cookies.txt``, if it is usable.

    YouTube bot-checks ("Sign in to confirm you're not a bot") block the
    research pages on most IPs. A cookies.txt exported from a logged-in
    browser is the escape hatch — it is configured once in Settings and used
    by every request.
    """
    path = (settings_store.get_setting("youtube_cookies_file") or "").strip()
    if not path:
        return None
    if not os.path.isfile(path):
        logger.warning("Configured cookies file is missing: %s", path)
        return None
    return path


def parse_video_id(url_or_id: str) -> str | None:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    match = VIDEO_ID_RE.search(url_or_id)
    return match.group(1) if match else None


def parse_channel_id(url_or_id: str) -> str | None:
    if re.fullmatch(r"UC[A-Za-z0-9_-]{22}", url_or_id):
        return url_or_id
    match = CHANNEL_ID_RE.search(url_or_id)
    return match.group(1) if match else None


YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    }
)


def is_youtube_url(url: str) -> bool:
    """True for a YouTube URL or a yt-dlp search pseudo-URL.

    The host is compared exactly. A substring check would accept
    ``https://attacker.tld/?youtube.com`` — and the request carries the
    user's YouTube cookie jar.
    """
    text = (url or "").strip()
    if text.lower().startswith("ytsearch"):
        return True
    try:
        host = (urlparse(text).hostname or "").lower()
    except ValueError:
        return False
    return host in YOUTUBE_HOSTS


def _seconds_since(seconds: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


def _base_opts(cookiefile: str | None = None, extra: dict | None = None) -> dict:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "noplaylist": True,
        "ignoreerrors": True,
        "retries": 2,
        "socket_timeout": 30,
        "js_runtimes": js_runtime_opts(),
    }
    target, _label = impersonate_target()
    if target is not None:
        opts["impersonate"] = target
    cookies = cookiefile or get_cookies_file()
    if cookies:
        opts["cookiefile"] = cookies
    if extra:
        opts.update(extra)
    return opts


def _extract(url: str, opts: dict, attempts: int = 2) -> dict:
    """Run yt-dlp extraction with retry and error normalization.

    Only YouTube URLs are extracted. ``opts`` may carry the user's
    ``cookies.txt``, and that jar must never be handed to a host the user
    typed in.
    """
    if not is_youtube_url(url):
        raise ValueError(f"Refusing to fetch a non-YouTube URL: {url}")
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not isinstance(info, dict):
                raise YoutubeApiError(f"No data returned for {url}")
            return info
        except yt_dlp.utils.DownloadError as exc:
            message = str(exc)
            lowered = message.lower()
            if "sign in to confirm" in lowered or "log in to confirm" in lowered:
                raise RateLimitError(
                    "YouTube is asking the scraper to sign in (bot check). "
                    "Retry later or add a YouTube API key in Settings."
                ) from exc
            if "video unavailable" in lowered or "channel does not exist" in lowered:
                raise NotFoundError(message) from exc
            last_error = exc
            if attempt + 1 < attempts:
                delay = 1.5 * (attempt + 1)
                time.sleep(delay)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.0)
    raise YoutubeApiError(str(last_error) if last_error else f"Failed to extract {url}")


# --------------------------------------------------------------------------- #
# Normalizers
# --------------------------------------------------------------------------- #
def _to_video_info(d: dict) -> VideoInfo:
    views = d.get("view_count") or 0
    likes = d.get("like_count") or 0
    comments = d.get("comment_count") or 0
    duration = d.get("duration") or 0
    upload_date = d.get("upload_date")  # YYYYMMDD
    if upload_date:
        try:
            published = datetime.strptime(str(upload_date), "%Y%m%d").replace(tzinfo=timezone.utc)
            published_at = published.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            published_at = ""
    else:
        published_at = (
            d.get("timestamp")
            and datetime.fromtimestamp(int(d.get("timestamp")), tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            or d.get("upload_date")
            or ""
        )
    return VideoInfo(
        video_id=d.get("id") or d.get("video_id") or "",
        channel_id=d.get("channel_id") or d.get("uploader_id") or "",
        title=d.get("title") or "",
        description=d.get("description") or "",
        published_at=published_at,
        duration_seconds=int(duration) if duration else 0,
        thumbnail_url=d.get("thumbnail") or "",
        language=d.get("language") or d.get("default_language"),
        view_count=int(views) if views else 0,
        like_count=int(likes) if likes else 0,
        comment_count=int(comments) if comments else 0,
        tags=list(d.get("tags") or []),
        category_id=d.get("categories")[0] if d.get("categories") else "",
        channel_title=d.get("channel") or d.get("uploader") or "",
    )


def _channel_avatar(d: dict) -> str:
    """Pick the channel's display picture (not banner). Empty string = unknown.

    yt-dlp exposes avatars under ``thumbnails`` entries with ids like
    'avatar' / 'avatar_uncropped' and banners with 'banner*' ids. A banner
    is never a valid channel DP — the caller falls back to initials.
    """
    explicit = d.get("avatar") or ""
    if explicit:
        return explicit
    thumbs = [t for t in (d.get("thumbnails") or []) if isinstance(t, dict) and t.get("url")]
    for entry in thumbs:
        if "avatar" in str(entry.get("id") or "").lower():
            return entry["url"]
    for entry in thumbs:
        if "banner" not in str(entry.get("id") or "").lower():
            return entry["url"]
    thumb = d.get("thumbnail")
    if thumb and isinstance(thumb, str) and "banner" not in thumb.lower():
        return thumb
    return ""


def _to_channel_info(d: dict) -> ChannelInfo:
    tags = _parse_json_list(d.get("channel_tags") or d.get("tags"))
    categories = _parse_json_list(d.get("topic_categories") or d.get("categories"))
    subs = d.get("channel_follower_count") or d.get("subscriber_count") or 0
    views = d.get("view_count") or d.get("channel_view_count") or 0
    vids = d.get("channel_video_count") or d.get("playlist_count") or 0
    uploads: list[dict[str, Any]] = []
    for entry in d.get("entries") or []:
        if isinstance(entry, dict):
            thumbs = entry.get("thumbnails") or []
            thumb_url = entry.get("thumbnail") or (thumbs[0].get("url") if thumbs else "") or ""
            uploads.append(
                {
                    "video_id": entry.get("id") or "",
                    "title": entry.get("title") or "",
                    "view_count": int(entry.get("view_count") or 0),
                    "upload_date": entry.get("upload_date") or "",
                    "thumbnail_url": thumb_url,
                }
            )
    avatar = _channel_avatar(d)
    return ChannelInfo(
        channel_id=d.get("id") or d.get("channel_id") or d.get("uploader_id") or "",
        title=d.get("channel") or d.get("uploader") or d.get("title") or "",
        description=d.get("description") or "",
        thumbnail_url=avatar,
        custom_url=d.get("uploader_url") or "",
        country=d.get("country") or "",
        publish_date=d.get("channel_joined_date") or "",
        subscriber_count=int(subs) if subs else 0,
        video_count=int(vids) if vids else 0,
        view_count=int(views) if views else 0,
        channel_tags=tags,
        topic_categories=categories,
        uploads=uploads,
    )


def _parse_json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str) and raw:
        return [line.strip() for line in raw.split(",") if line.strip()]
    return []


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def search_videos(
    query: str,
    max_results: int = 30,
    *,
    days_recent: int | None = None,
    cookiefile: str | None = None,
    progress: Callable[[str], None] | None = None,
    api_key: str | None = None,
) -> list[VideoInfo]:
    """Search YouTube videos. Uses the API when a key is configured, else yt-dlp.

    ``api_key`` overrides the stored Settings key for this single call.
    """
    key = api_key or get_api_key()
    if key:
        try:
            return _search_via_api(
                query, max_results=max_results, days_recent=days_recent, api_key=key
            )
        except YoutubeApiError as exc:
            logger.warning("API search failed (%s); falling back to yt-dlp", exc)
    return _search_via_ytdlp(
        query,
        max_results=max_results,
        days_recent=days_recent,
        cookiefile=cookiefile,
        progress=progress,
    )


def _search_via_ytdlp(
    query: str,
    max_results: int,
    days_recent: int | None,
    cookiefile: str | None,
    progress: Callable[[str], None] | None = None,
) -> list[VideoInfo]:
    limit = max(1, min(max_results, 50))
    opts = _base_opts(
        cookiefile=cookiefile,
        extra={
            "extract_flat": False,
            # Pull a chunk of extra results so the recency window can trim old ones.
            "playlist_items": f"1-{max(limit, 50)}",
        },
    )
    if days_recent:
        start = (datetime.now(timezone.utc) - timedelta(days=days_recent)).strftime("%Y%m%d")
        opts["daterange"] = DateRange(start=start)
    if progress:
        progress(f"Searching YouTube: {query}")
    info = _extract(f"ytsearch{limit * 2}:{query}", opts)
    out: list[VideoInfo] = []
    for entry in info.get("entries") or []:
        if isinstance(entry, dict) and entry.get("id"):
            out.append(_to_video_info(entry))
    return out


def _search_via_api(
    query: str,
    max_results: int,
    days_recent: int | None,
    api_key: str | None = None,
) -> list[VideoInfo]:
    key = api_key or get_api_key()
    if not key:
        raise YoutubeApiError("No YouTube API key configured")
    published_after = (
        _seconds_since(days_recent * 86400).strftime("%Y-%m-%dT%H:%M:%SZ") if days_recent else None
    )
    params: dict[str, Any] = {
        "part": "snippet",
        "type": "video",
        "q": query,
        "maxResults": min(max_results, 50),
        "order": "viewCount",
    }
    if published_after:
        params["publishedAfter"] = published_after
    search_results = []
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(f"{YT_BASE}/search", params=params, headers=_api_headers(key))
        if resp.status_code in (403, 429):
            raise RateLimitError(resp.json().get("error", {}).get("message", resp.text))
        if resp.status_code != 200:
            raise YoutubeApiError(f"YouTube search failed: {resp.status_code} {resp.text}")
        search_results = resp.json().get("items", [])

        video_ids = [item["id"]["videoId"] for item in search_results]
        videos = _fetch_videos_via_api(client, video_ids, key)
    for v in videos:
        v.channel_title = next(
            (
                i["snippet"]["channelTitle"]
                for i in search_results
                if i["id"]["videoId"] == v.video_id
            ),
            v.channel_title,
        )
        v.channel_id = v.channel_id or next(
            (i["snippet"]["channelId"] for i in search_results if i["id"]["videoId"] == v.video_id),
            "",
        )
    return sorted(videos, key=lambda v: v.view_count, reverse=True)


def _fetch_videos_via_api(client: httpx.Client, video_ids: list[str], key: str) -> list[VideoInfo]:
    videos: list[VideoInfo] = []
    for chunk in _chunks(video_ids, 50):
        resp = client.get(
            f"{YT_BASE}/videos",
            params={
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(chunk),
            },
            headers=_api_headers(key),
        )
        if resp.status_code != 200:
            continue
        for item in resp.json().get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})
            duration = parse_iso8601_duration(content.get("duration"))
            videos.append(
                VideoInfo(
                    video_id=item["id"],
                    channel_id=snippet.get("channelId", ""),
                    channel_title=snippet.get("channelTitle", ""),
                    title=snippet.get("title", ""),
                    description=snippet.get("description", ""),
                    published_at=snippet.get("publishedAt", ""),
                    duration_seconds=duration,
                    thumbnail_url=(snippet.get("thumbnails") or {}).get("high", {}).get("url", ""),
                    language=snippet.get("defaultAudioLanguage"),
                    view_count=int(stats.get("viewCount", 0)),
                    like_count=int(stats.get("likeCount", 0)),
                    comment_count=int(stats.get("commentCount", 0)),
                    tags=list(snippet.get("tags") or []),
                    category_id=snippet.get("categoryId", ""),
                )
            )
    return videos


def _fetch_channel_uploads_via_api(
    client: httpx.Client, uploads_playlist_id: str, key: str, limit: int
) -> list[dict[str, Any]]:
    """Fetch a channel's newest uploads through the Data API.

    The uploads live in the channel's uploads playlist; the view counts
    need a second call because playlistItems carries no statistics.
    """
    resp = client.get(
        f"{YT_BASE}/playlistItems",
        params={
            "part": "contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": max(1, min(limit, 50)),
        },
        headers=_api_headers(key),
    )
    if resp.status_code != 200:
        return []
    video_ids = [
        (item.get("contentDetails") or {}).get("videoId")
        for item in resp.json().get("items", [])
        if (item.get("contentDetails") or {}).get("videoId")
    ]
    if not video_ids:
        return []
    return [
        {
            "video_id": v.video_id,
            "title": v.title,
            "view_count": v.view_count,
            "like_count": v.like_count,
            "upload_date": (v.published_at or "")[:10].replace("-", ""),
            "thumbnail_url": v.thumbnail_url,
        }
        for v in _fetch_videos_via_api(client, video_ids, key)
    ]


def _fetch_channels_via_api(
    client: httpx.Client,
    channel_ids: list[str],
    key: str,
    *,
    with_uploads: bool = False,
    uploads_limit: int = 30,
) -> list[ChannelInfo]:
    channels: list[ChannelInfo] = []
    for chunk in _chunks(channel_ids, 50):
        resp = client.get(
            f"{YT_BASE}/channels",
            params={
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(chunk),
            },
            headers=_api_headers(key),
        )
        if resp.status_code != 200:
            continue
        for item in resp.json().get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            uploads: list[dict[str, Any]] = []
            if with_uploads:
                playlist_id = (
                    (item.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads", "")
                )
                if playlist_id:
                    uploads = _fetch_channel_uploads_via_api(
                        client, playlist_id, key, uploads_limit
                    )
            channels.append(
                ChannelInfo(
                    channel_id=item["id"],
                    title=snippet.get("title", ""),
                    description=snippet.get("description", ""),
                    thumbnail_url=(snippet.get("thumbnails") or {}).get("high", {}).get("url", ""),
                    custom_url=snippet.get("customUrl", ""),
                    country=snippet.get("country", ""),
                    publish_date=snippet.get("publishedAt", ""),
                    subscriber_count=int(stats.get("subscriberCount", 0)),
                    video_count=int(stats.get("videoCount", 0)),
                    view_count=int(stats.get("viewCount", 0)),
                    topic_categories=list(snippet.get("topicCategories") or []),
                    uploads=uploads,
                )
            )
    return channels


def parse_iso8601_duration(value: str | None) -> int:
    """Convert an ISO-8601 duration (PT1H2M3S) to seconds."""
    if not value:
        return 0
    match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return 0
    days, hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def search_channels(
    query: str,
    max_results: int = 30,
    *,
    min_subscribers: int = 0,
    cookiefile: str | None = None,
    progress: Callable[[str], None] | None = None,
    api_key: str | None = None,
) -> list[ChannelInfo]:
    """Discover channels by query, enriched with full yt-dlp metadata.

    Runs a video search (pool), groups the hits by ``channel_id``, picks the
    most-viewed top ``max_results`` channels, then fetches full channel metadata
    (subscriber count, avatar, custom URL/handle) for each. ``min_subscribers``
    is applied after enrichment. Falls back to yt-dlp when no API key applies.
    """
    if max_results <= 0:
        return []

    if progress:
        progress(f"Searching YouTube channels for: {query}")

    pool = search_videos(
        query,
        max_results=min(max(2 * max_results, 20), 50),
        cookiefile=cookiefile,
        progress=progress,
        api_key=api_key,
    )

    by_channel: dict[str, tuple[str, int]] = {}
    for video in pool:
        cid = video.channel_id
        if not cid:
            continue
        title = video.channel_title or ""
        if cid not in by_channel or video.view_count > by_channel[cid][1]:
            by_channel[cid] = (title, video.view_count)

    ranked = sorted(by_channel.items(), key=lambda kv: kv[1][1], reverse=True)[:max_results]
    if not ranked:
        return []

    if progress:
        progress(f"Fetching metadata for {len(ranked)} candidate channels...")

    channels = fetch_channels(
        [cid for cid, _ in ranked],
        cookiefile=cookiefile,
        progress=progress,
        uploads_limit=1,
        api_key=api_key,
    )
    by_id = {c.channel_id: c for c in channels}
    out: list[ChannelInfo] = []
    for cid, (title, _views) in ranked:
        channel = by_id.get(cid)
        if channel is None:
            continue
        if not channel.title:
            channel.title = title
        if min_subscribers and channel.subscriber_count < min_subscribers:
            continue
        out.append(channel)
    return out


def fetch_video(video_id: str, *, cookiefile: str | None = None, api_key: str | None = None) -> VideoInfo:
    """Fetch full metadata for a single video."""
    key = api_key or get_api_key()
    if key:
        with httpx.Client(timeout=20.0) as client:
            try:
                videos = _fetch_videos_via_api(client, [video_id], key)
                if videos:
                    return videos[0]
            except YoutubeApiError as exc:
                logger.warning("API video fetch failed (%s); falling back", exc)
    info = _extract(
        f"https://www.youtube.com/watch?v={video_id}", _base_opts(cookiefile=cookiefile)
    )
    return _to_video_info(info)


def fetch_videos(
    video_ids: Iterable[str],
    *,
    cookiefile: str | None = None,
    progress: Callable[[str], None] | None = None,
    api_key: str | None = None,
) -> list[VideoInfo]:
    """Fetch many videos. Preservation of input order; per-item error tolerance."""
    ids = [v for v in dict.fromkeys(video_ids) if v]
    by_id: dict[str, VideoInfo] = {}
    key = api_key or get_api_key()
    if key:
        with httpx.Client(timeout=20.0) as client:
            try:
                for v in _fetch_videos_via_api(client, ids, key):
                    by_id[v.video_id] = v
            except YoutubeApiError as exc:
                logger.warning("API video batch failed (%s); falling back", exc)
    missing = [vid for vid in ids if vid not in by_id]
    for i, video_id in enumerate(missing, start=1):
        if progress:
            progress(f"Fetching video {i}/{len(missing)}: {video_id}")
        try:
            by_id[video_id] = fetch_video(video_id, cookiefile=cookiefile, api_key=key)
        except YoutubeApiError:
            logger.debug("Skipping un-fetchable video %s", video_id)
    return [by_id[vid] for vid in ids if vid in by_id]


def fetch_channel(
    channel_id: str,
    *,
    cookiefile: str | None = None,
    uploads_limit: int = 30,
    api_key: str | None = None,
    uploads_with_stats: bool = False,
    stats_limit: int = 10,
) -> ChannelInfo:
    """Fetch channel metadata plus its most recent uploads.

    Accepts either a bare channel id (``UC...``) or any full channel URL such as
    ``https://www.youtube.com/@handle`` or ``.../channel/UC...``.

    Uploads are extracted flat (one request per channel) because discovery
    scans hundreds of channels. Flat entries carry no view count, so callers
    that display upload statistics (the scorecard, the AI analysis) pass
    ``uploads_with_stats=True`` to extract the newest ``stats_limit`` uploads
    with their real numbers.
    """
    if channel_id.startswith("http") and not is_youtube_url(channel_id):
        raise ValueError(f"Not a YouTube URL: {channel_id}")
    if uploads_with_stats:
        items = max(1, min(stats_limit, uploads_limit))
    else:
        items = uploads_limit
    key = api_key or get_api_key()
    if key:
        with httpx.Client(timeout=20.0) as client:
            try:
                channels = _fetch_channels_via_api(
                    client, [channel_id], key, with_uploads=uploads_with_stats, uploads_limit=items
                )
                if channels:
                    return channels[0]
            except YoutubeApiError as exc:
                logger.warning("API channel fetch failed (%s); falling back", exc)
    if channel_id.startswith(("http", "@")):
        url = f"https://www.youtube.com/{channel_id}" if channel_id.startswith("@") else channel_id
    else:
        url = f"https://www.youtube.com/channel/{channel_id}"
    if uploads_with_stats:
        extra = {"extract_flat": False, "playlist_items": f"1-{items}"}
    else:
        extra = {"extract_flat": True, "playlist_items": f"1-{uploads_limit}"}
    opts = _base_opts(cookiefile=cookiefile, extra=extra)
    return _to_channel_info(_extract(url, opts))


def fetch_channels(
    channel_ids: Iterable[str],
    *,
    cookiefile: str | None = None,
    uploads_limit: int = 30,
    progress: Callable[[str], None] | None = None,
    api_key: str | None = None,
) -> list[ChannelInfo]:
    """Fetch many channels, deduped, preserving input order."""
    ids = [c for c in dict.fromkeys(channel_ids) if c]
    by_id: dict[str, ChannelInfo] = {}
    key = api_key or get_api_key()
    if key:
        with httpx.Client(timeout=20.0) as client:
            try:
                for c in _fetch_channels_via_api(client, ids, key):
                    by_id[c.channel_id] = c
            except YoutubeApiError as exc:
                logger.warning("API channel batch failed (%s); falling back", exc)
    missing = [cid for cid in ids if cid not in by_id]
    for i, channel_id in enumerate(missing, start=1):
        if progress:
            progress(f"Fetching channel {i}/{len(missing)}: {channel_id}")
        try:
            by_id[channel_id] = fetch_channel(
                channel_id, cookiefile=cookiefile, uploads_limit=uploads_limit, api_key=key
            )
        except (YoutubeApiError, RateLimitError, NotFoundError):
            logger.debug("Skipping un-fetchable channel %s", channel_id)
    return [by_id[cid] for cid in ids if cid in by_id]


def _chunks(seq: Sequence[str], size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
