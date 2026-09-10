"""Video/channel SEO scorecard + VPH engine — ported from S-Q Creator Studio.

- ``compute_seo_score``: vidIQ-style score, 50% "actionable" (title/description/
  tags/keyword placement) + 50% "performance" (engagement + growth velocity).
  Every check is transparent (label, passed, score, weight, detail).
- ``compute_vph``: views-per-hour from the video_snapshots history (vidIQ VPH is
  exactly a delta over cached history), plus the full series for charts.
- ``lookup_video`` / ``lookup_channel``: score a YouTube URL (yt-dlp), record the
  first snapshot, and report tracked state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.youtube_client import (
    ChannelInfo,
    VideoInfo,
    fetch_channel,
    fetch_video,
    parse_channel_id,
    parse_video_id,
)

logger = logging.getLogger(__name__)

ACTIONABLE_CHECK_IDS = {
    "titleLength",
    "descriptionLength",
    "tagCount",
    "keywordTitle",
    "keywordDescription",
    "keywordTags",
    "tripleKeyword",
}
PERFORMANCE_CHECK_IDS = {"engagement", "velocity"}


@dataclass
class SeoCheck:
    id: str
    label: str
    passed: bool
    score: int
    weight: int
    detail: str


@dataclass
class SeoResult:
    total: int
    actionable_pct: int
    performance_pct: int
    checks: list[SeoCheck] = field(default_factory=list)


@dataclass
class VphResult:
    vph: float | None
    window_hours: float
    points: list[dict] = field(default_factory=list)
    error: str = ""


@dataclass
class VideoLookupResult:
    kind: str = "video"
    video: dict = field(default_factory=dict)
    channel: dict | None = None
    seo: SeoResult | None = None
    vph: VphResult | None = None
    tracked: bool = False


@dataclass
class ChannelLookupResult:
    kind: str = "channel"
    channel: dict = field(default_factory=dict)
    seo: SeoResult | None = None
    recent_videos: list[dict] = field(default_factory=list)
    tracked: bool = False


# --------------------------------------------------------------------------- #
# Scorers
# --------------------------------------------------------------------------- #
def norm(s: str) -> str:
    return " ".join(s.lower().split())


def _clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def contains_keyword(haystack: str, keyword: str) -> bool:
    h = norm(haystack)
    k = norm(keyword)
    if not k:
        return False
    return k in h or any(w in h for w in k.split())


def score_char(n: float, good: float, perfect: float) -> int:
    """Linear ramp from 0 (at good/5) to 100 (at perfect)."""
    if n >= perfect:
        return 100
    if n <= good / 5:
        return 0
    return int(_clamp(round((n / perfect) * 100), 0, 100))


def compute_seo_score(input_data: dict) -> SeoResult:
    title = input_data.get("title") or ""
    description = input_data.get("description") or ""
    tags = input_data.get("tags") or []
    view_count = input_data.get("view_count") or 0
    like_count = input_data.get("like_count")
    comment_count = input_data.get("comment_count")
    published_at = input_data.get("published_at") or ""
    kw = input_data.get("focus_keyword")

    title_len = len(title.strip())
    desc_len = len(description.strip())
    tag_count = len(tags)

    checks: list[SeoCheck] = []

    title_score = 100 if 20 <= title_len <= 60 else score_char(title_len, 20, 40)
    checks.append(
        SeoCheck(
            id="titleLength",
            label="Title length (20–60 chars)",
            passed=20 <= title_len <= 60,
            score=title_score,
            weight=12,
            detail=f"{title_len} chars",
        )
    )

    desc_score = 100 if desc_len >= 300 else score_char(desc_len, 100, 300)
    checks.append(
        SeoCheck(
            id="descriptionLength",
            label="Description ≥ 300 chars",
            passed=desc_len >= 300,
            score=desc_score,
            weight=12,
            detail=f"{desc_len} chars",
        )
    )

    tag_score = 100 if tag_count >= 5 else score_char(tag_count, 2, 5)
    checks.append(
        SeoCheck(
            id="tagCount",
            label="At least 5 tags",
            passed=tag_count >= 5,
            score=tag_score,
            weight=12,
            detail=f"{tag_count} tags",
        )
    )

    if kw:
        kw_title = contains_keyword(title, kw)
        kw_desc = contains_keyword(description, kw)
        kw_tags = any(norm(t) == norm(kw) for t in tags)
        checks.append(
            SeoCheck(
                id="keywordTitle",
                label="Keyword in title",
                passed=bool(kw_title),
                score=100 if kw_title else 0,
                weight=10,
                detail=f'"{kw}" found in title' if kw_title else f'"{kw}" not in title',
            )
        )
        checks.append(
            SeoCheck(
                id="keywordDescription",
                label="Keyword in description",
                passed=bool(kw_desc),
                score=100 if kw_desc else 0,
                weight=8,
                detail=f'"{kw}" found in description' if kw_desc else f'"{kw}" not in description',
            )
        )
        checks.append(
            SeoCheck(
                id="keywordTags",
                label="Keyword in tags",
                passed=bool(kw_tags),
                score=100 if kw_tags else 0,
                weight=8,
                detail=f'"{kw}" present in a tag' if kw_tags else f'"{kw}" not in tags',
            )
        )
        triple = bool(kw_title and kw_desc and kw_tags)
        checks.append(
            SeoCheck(
                id="tripleKeyword",
                label="Triple keyword (title + desc + tags)",
                passed=triple,
                score=100 if triple else 0,
                weight=8,
                detail=(
                    "Keyword used in all three"
                    if triple
                    else "Use the keyword in title, description, and tags"
                ),
            )
        )

    likes = (like_count or 0) / max(1, view_count)
    comments = (comment_count or 0) / max(1, view_count)
    like_pct = min(100, (likes / 0.05) * 100)
    comment_pct = min(100, (comments / 0.01) * 100)
    engagement = round(like_pct * 0.6 + comment_pct * 0.4)
    checks.append(
        SeoCheck(
            id="engagement",
            label="Engagement (likes & comments / views)",
            passed=engagement >= 50,
            score=engagement,
            weight=30,
            detail=(
                f"{((like_count or 0) / max(1, view_count) * 100):.2f}% likes, "
                f"{((comment_count or 0) / max(1, view_count) * 100):.2f}% comments"
            ),
        )
    )

    age_days = _age_days(published_at) if published_at else 1
    views_per_day = view_count / max(1, age_days)
    velocity = round(min(100, (views_per_day / 5000) * 100))
    checks.append(
        SeoCheck(
            id="velocity",
            label="Growth velocity (views/day)",
            passed=velocity >= 50,
            score=velocity,
            weight=30,
            detail=_fmt_views_per_day(views_per_day),
        )
    )

    actionable = [c for c in checks if c.id in ACTIONABLE_CHECK_IDS]
    performance = [c for c in checks if c.id in PERFORMANCE_CHECK_IDS]

    def section_pct(section: list[SeoCheck]) -> float:
        total_w = sum(c.weight for c in section)
        if total_w == 0:
            return 0.0
        return sum(c.score * c.weight for c in section) / total_w

    actionable_pct = section_pct(actionable)
    performance_pct = section_pct(performance)
    total = round((actionable_pct + performance_pct) / 2)

    return SeoResult(
        total=total,
        actionable_pct=round(actionable_pct),
        performance_pct=round(performance_pct),
        checks=checks,
    )


def _age_days(published_at: str) -> int:
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        import time

        hours = (time.time() - dt.timestamp()) / 3600
        return max(1, int(hours / 24) or 1)
    except Exception:
        return 1


def _fmt_views_per_day(views_per_day: float) -> str:
    if views_per_day >= 1000:
        return f"{views_per_day / 1000:.1f}K views/day since publish"
    return f"{round(views_per_day)} views/day since publish"


def score_label(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 55:
        return "D"
    if score >= 40:
        return "E"
    return "F"


def compute_channel_seo_score(channel: ChannelInfo) -> SeoResult:
    return compute_seo_score(
        {
            "title": channel.title,
            "description": channel.description,
            "tags": channel.channel_tags or [],
            "view_count": max(1, channel.subscriber_count),
            "like_count": None,
            "comment_count": None,
            "published_at": "",
        }
    )


# --------------------------------------------------------------------------- #
# VPH
# --------------------------------------------------------------------------- #
def get_video_snapshots(video_id: str) -> list[dict]:
    return db.all(
        """
        SELECT video_id AS videoId, ts, view_count AS viewCount,
               like_count AS likeCount, comment_count AS commentCount
        FROM video_snapshots WHERE video_id = ? ORDER BY ts ASC
        """,
        (video_id,),
    )


def compute_vph(video_id: str, window_ms: int | None = None) -> VphResult:
    window_ms = window_ms or 24 * 60 * 60 * 1000
    snapshots = get_video_snapshots(video_id)
    points = [{"ts": s["ts"], "views": s["viewCount"]} for s in snapshots]

    if len(snapshots) < 2:
        return VphResult(
            vph=None,
            window_hours=0,
            points=points,
            error="Need at least two snapshots (the poller records one hourly). "
            "Add this video to your watchlist.",
        )

    import time

    now_ms = int(time.time() * 1000)
    in_window = [s for s in snapshots if now_ms - s["ts"] <= window_ms]
    series = in_window if len(in_window) >= 2 else snapshots

    first = series[0]
    last = series[-1]
    delta_views = last["viewCount"] - first["viewCount"]
    delta_hours = (last["ts"] - first["ts"]) / 3_600_000

    if delta_hours < 1:
        return VphResult(
            vph=None,
            window_hours=round(delta_hours * 10) / 10,
            points=points,
            error="Less than 1 hour between snapshots — give the poller more time.",
        )

    return VphResult(
        vph=round((delta_views / delta_hours) * 10) / 10,
        window_hours=round(delta_hours * 10) / 10,
        points=points,
    )


# --------------------------------------------------------------------------- #
# Persistence helpers (shared with the poller in a later phase)
# --------------------------------------------------------------------------- #
def save_video_snapshot(video: VideoInfo) -> None:
    db.run(
        """
        INSERT INTO videos (
            video_id, channel_id, title, description, published_at, duration_seconds,
            thumbnail_url, default_language, view_count, like_count, comment_count,
            tags, category_id, last_fetched
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            view_count = excluded.view_count,
            like_count = excluded.like_count,
            comment_count = excluded.comment_count,
            last_fetched = excluded.last_fetched
        """,
        (
            video.video_id,
            video.channel_id,
            video.title,
            video.description,
            video.published_at,
            video.duration_seconds,
            video.thumbnail_url,
            video.language or "",
            video.view_count,
            video.like_count,
            video.comment_count,
            json_dumps(video.tags),
            video.category_id,
            db.now(),
        ),
    )
    db.run(
        """
        INSERT INTO video_snapshots (video_id, ts, view_count, like_count, comment_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (video.video_id, db.now(), video.view_count, video.like_count, video.comment_count),
    )


def save_channel_snapshot(channel: ChannelInfo) -> None:
    db.run(
        """
        INSERT INTO channels (
            channel_id, title, description, thumbnail_url, custom_url, country,
            published_at, subscriber_count, video_count, view_count, channel_tags,
            topic_categories, last_fetched
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            title = excluded.title, description = excluded.description,
            thumbnail_url = excluded.thumbnail_url, subscriber_count = excluded.subscriber_count,
            video_count = excluded.video_count, view_count = excluded.view_count,
            channel_tags = excluded.channel_tags, last_fetched = excluded.last_fetched
        """,
        (
            channel.channel_id,
            channel.title,
            channel.description,
            channel.thumbnail_url,
            channel.custom_url,
            channel.country,
            channel.publish_date,
            channel.subscriber_count,
            channel.video_count,
            channel.view_count,
            json_dumps(channel.channel_tags),
            json_dumps(channel.topic_categories),
            db.now(),
        ),
    )
    db.run(
        """
        INSERT INTO channel_snapshots (channel_id, ts, subscriber_count, video_count, view_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            channel.channel_id,
            db.now(),
            channel.subscriber_count,
            channel.video_count,
            channel.view_count,
        ),
    )


def json_dumps(value: list) -> str:
    import json

    return json.dumps(value) if value else ""


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #
def _is_tracked(kind: str, ref_id: str) -> bool:
    return (
        db.get(
            "SELECT 1 FROM tracked_items WHERE kind=? AND ref_id=?",
            (kind, ref_id),
        )
        is not None
    )


def lookup_video(url: str, *, cookiefile: str | None = None) -> VideoLookupResult:
    video_id = parse_video_id(url)
    if not video_id:
        raise ValueError("Could not parse a YouTube video ID from that input")
    video = fetch_video(video_id, cookiefile=cookiefile)
    save_video_snapshot(video)

    seo = compute_seo_score(
        {
            "title": video.title,
            "description": video.description,
            "tags": video.tags,
            "view_count": video.view_count,
            "like_count": video.like_count,
            "comment_count": video.comment_count,
            "published_at": video.published_at,
        }
    )
    vph = compute_vph(video_id)

    channel = None
    if video.channel_id:
        try:
            info = fetch_channel(video.channel_id, cookiefile=cookiefile)
            channel = {
                "channel_id": info.channel_id,
                "title": info.title,
                "thumbnail_url": info.thumbnail_url,
                "subscriber_count": info.subscriber_count,
            }
        except Exception:
            logger.warning("Channel fetch failed for %s", video.channel_id, exc_info=True)

    return VideoLookupResult(
        video={
            "video_id": video.video_id,
            "channel_id": video.channel_id,
            "channel_title": video.channel_title,
            "title": video.title,
            "description": video.description,
            "published_at": video.published_at,
            "duration_seconds": video.duration_seconds,
            "thumbnail_url": video.thumbnail_url,
            "tags": video.tags,
            "view_count": video.view_count,
            "like_count": video.like_count,
            "comment_count": video.comment_count,
        },
        channel=channel,
        seo=seo,
        vph=vph,
        tracked=_is_tracked("video", video_id),
    )


def lookup_channel(url: str, *, cookiefile: str | None = None) -> ChannelLookupResult:
    channel_id = parse_channel_id(url)
    if not channel_id and (url.strip().startswith("@") or "youtube.com" in url.lower()):
        # Bare id not found but this looks like a channel reference (handle URL etc.)
        channel_id = url
    if not channel_id:
        raise ValueError("Could not parse a YouTube channel ID from that input")
    info = fetch_channel(channel_id, cookiefile=cookiefile)
    save_channel_snapshot(info)

    seo = compute_channel_seo_score(info)

    recent_videos = []
    for entry in info.uploads:
        recent_videos.append(
            {
                "video_id": entry.get("video_id", ""),
                "title": entry.get("title", ""),
                "published_at": _upload_date_to_iso(entry.get("upload_date", "")),
                "view_count": entry.get("view_count", 0),
                "duration_seconds": 0,
            }
        )

    return ChannelLookupResult(
        channel={
            "channel_id": info.channel_id,
            "title": info.title,
            "description": info.description,
            "thumbnail_url": info.thumbnail_url,
            "subscriber_count": info.subscriber_count,
            "video_count": info.video_count,
            "view_count": info.view_count,
        },
        seo=seo,
        recent_videos=recent_videos,
        tracked=_is_tracked("channel", channel_id),
    )


def _upload_date_to_iso(upload_date: str) -> str:
    if not upload_date:
        return ""
    try:
        from datetime import datetime, timezone

        return (
            datetime.strptime(str(upload_date), "%Y%m%d")
            .replace(tzinfo=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
    except ValueError:
        return ""
