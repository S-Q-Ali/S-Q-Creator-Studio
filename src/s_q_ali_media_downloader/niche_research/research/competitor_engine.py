"""Competitor dashboard: tracked videos / channels / keywords + snapshot refresh.

Ported from the companion research web tool's lib/competitorEngine.ts (getTrackedVideos /
getTrackedChannels / getTrackedKeywords / getCompetitorDashboard) and the
``/api/competitors/refresh`` endpoint. The dashboard is a pure read over the
shared SQLite tables; the poller (ui/competitors_page) drives
``refresh_snapshots`` hourly or on demand.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from s_q_ali_media_downloader.niche_research.research import scorecard_engine as se
from s_q_ali_media_downloader.niche_research.research.keyword_engine import (
    ResearchOptions,
    get_keyword_snapshots,
    rank_keyword,
)
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.youtube_client import (
    fetch_channel,
    fetch_video,
)

logger = logging.getLogger(__name__)


SNAPSHOT_INTERVALS = (30, 60, 180)


def snapshot_interval_minutes() -> int:
    """How often the background poller records a snapshot."""
    raw = (db.get_setting("snapshot_interval_minutes") or "60").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 60
    return value if value in SNAPSHOT_INTERVALS else 60


def track_item(kind: str, ref_id: str, label: str = "") -> bool:
    """Track an item (video / channel / keyword).

    Returns True when the item was not tracked before.
    """
    if not ref_id:
        return False
    existing = db.get(
        "SELECT 1 FROM tracked_items WHERE kind=? AND ref_id=?", (kind, ref_id)
    )
    db.run(
        "INSERT OR IGNORE INTO tracked_items (kind, ref_id, label, added_at) VALUES (?, ?, ?, ?)",
        (kind, ref_id, label or ref_id, db.now()),
    )
    return existing is None


def untrack_item(kind: str, ref_id: str) -> None:
    db.run("DELETE FROM tracked_items WHERE kind=? AND ref_id=?", (kind, ref_id))


def is_tracked(kind: str, ref_id: str) -> bool:
    return (
        db.get(
            "SELECT 1 FROM tracked_items WHERE kind=? AND ref_id=?", (kind, ref_id)
        )
        is not None
    )


def get_tracked_videos() -> list[dict[str, Any]]:
    """Latest stats + VPH series for every tracked 'video' item."""
    rows = db.all(
        """
        SELECT t.ref_id AS videoId, t.label, t.added_at,
               v.title, v.thumbnail_url, v.channel_id, v.channel_title,
               v.published_at, v.view_count, v.like_count, v.comment_count
        FROM tracked_items t
        LEFT JOIN videos v ON v.video_id = t.ref_id
        WHERE t.kind = 'video'
        ORDER BY t.added_at DESC
        """
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        vph = se.compute_vph(r["videoId"])
        out.append(
            {
                "videoId": r["videoId"],
                "title": r["title"],
                "thumbnailUrl": r["thumbnail_url"],
                "channelTitle": r["channel_title"] or r["channel_id"] or "",
                "publishedAt": r["published_at"],
                "viewCount": r["view_count"] or 0,
                "likeCount": r["like_count"],
                "commentCount": r["comment_count"],
                "addedAt": r["added_at"],
                "vph": vph.vph,
                "vphWindowHours": vph.window_hours,
                "vphError": vph.error,
                "series": [{"ts": p["ts"], "value": p["views"]} for p in vph.points],
            }
        )
    return out


def get_tracked_channels() -> list[dict[str, Any]]:
    """Latest stats + subscriber series + 7-day growth for tracked channels."""
    rows = db.all(
        """
        SELECT t.ref_id AS channelId, t.label, t.added_at,
               c.title, c.thumbnail_url, c.subscriber_count, c.video_count, c.view_count
        FROM tracked_items t
        LEFT JOIN channels c ON c.channel_id = t.ref_id
        WHERE t.kind = 'channel'
        ORDER BY t.added_at DESC
        """
    )
    out: list[dict[str, Any]] = []
    week_ms = 7 * 24 * 60 * 60 * 1000
    for r in rows:
        snapshots = db.all(
            """
            SELECT ts, subscriber_count FROM channel_snapshots
            WHERE channel_id = ? ORDER BY ts ASC
            """,
            (r["channelId"],),
        )
        series = [{"ts": s["ts"], "value": s["subscriber_count"]} for s in snapshots]
        growth7d: int | None = None
        if snapshots:
            week_ago = db.now() - week_ms
            recent = [s for s in snapshots if s["ts"] >= week_ago]
            oldest = recent[0] if len(recent) >= 2 else snapshots[0]
            latest = snapshots[-1]
            if latest["subscriber_count"] is not None and oldest["subscriber_count"] is not None:
                growth7d = latest["subscriber_count"] - oldest["subscriber_count"]
        out.append(
            {
                "channelId": r["channelId"],
                "title": r["title"],
                "thumbnailUrl": r["thumbnail_url"],
                "subscriberCount": r["subscriber_count"] or 0,
                "videoCount": r["video_count"] or 0,
                "viewCount": r["view_count"] or 0,
                "addedAt": r["added_at"],
                "growth7d": growth7d,
                "series": series,
            }
        )
    return out


def get_tracked_keywords() -> list[dict[str, Any]]:
    """Score history + latest rankings for tracked keywords."""
    rows = db.all(
        """
        SELECT t.ref_id AS term, t.added_at,
               k.display_term, k.score, k.demand_score, k.competition_label
        FROM tracked_items t
        LEFT JOIN keywords k ON k.term = t.ref_id
        WHERE t.kind = 'keyword'
        ORDER BY t.added_at DESC
        """
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        term = r["term"]
        snapshots = get_keyword_snapshots(term)
        ranked = db.all(
            """
            SELECT video_id, position, ts FROM rankings
            WHERE term = ? AND ts = (SELECT MAX(ts) FROM rankings WHERE term = ?)
            ORDER BY position ASC
            """,
            (term, term),
        )
        titles = {
            row["video_id"]: row["title"]
            for row in db.all(
                """
                SELECT video_id, title FROM videos
                WHERE video_id IN ({})
                """.format(",".join("?" for _ in ranked)),
                [v["video_id"] for v in ranked],
            )
        }
        channel_titles = {
            row["video_id"]: row["channel_title"]
            for row in db.all(
                """
                SELECT video_id, channel_title FROM videos
                WHERE video_id IN ({})
                """.format(",".join("?" for _ in ranked)),
                [v["video_id"] for v in ranked],
            )
        }
        out.append(
            {
                "term": term,
                "displayTerm": r["display_term"] or term,
                "score": r["score"] or 0,
                "demandScore": r["demand_score"] or 0,
                "competitionLabel": r["competition_label"] or "Low",
                "addedAt": r["added_at"],
                "series": [{"ts": s["ts"], "value": s["score"] or 0} for s in snapshots],
                "rankedVideos": [
                    {
                        "videoId": v["video_id"],
                        "title": titles.get(v["video_id"], v["video_id"]),
                        "channelTitle": channel_titles.get(v["video_id"]) or "",
                        "position": v["position"] or 0,
                        "ts": v["ts"],
                    }
                    for v in ranked
                ],
            }
        )
    return out


def get_competitor_dashboard() -> dict[str, list[dict[str, Any]]]:
    return {
        "videos": get_tracked_videos(),
        "channels": get_tracked_channels(),
        "keywords": get_tracked_keywords(),
    }


# --------------------------------------------------------------------------- #
# Snapshot refresh (the poller's payload)
# --------------------------------------------------------------------------- #
def refresh_snapshots(
    *,
    cookiefile: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Re-fetch every tracked item and record a fresh snapshot row.

    Stores a video_snapshot / channel_snapshot / keyword_snapshot per tracked
    item so VPH and score history accumulate over time.

    The result reports both successes and failures per kind, so the UI can
    say "3 videos snapshotted, 1 failed" instead of silently skipping the
    items that could not be fetched.
    """
    counts = {"videos": 0, "channels": 0, "keywords": 0}
    failures = {"videos": 0, "channels": 0, "keywords": 0}

    video_ids = [
        r["ref_id"]
        for r in db.all("SELECT ref_id FROM tracked_items WHERE kind = 'video' ORDER BY added_at")
    ]
    for i, video_id in enumerate(video_ids, start=1):
        if progress:
            progress(f"Snapshoting video {i}/{len(video_ids)}")
        try:
            se.save_video_snapshot(fetch_video(video_id, cookiefile=cookiefile))
            counts["videos"] += 1
        except Exception as exc:
            failures["videos"] += 1
            logger.warning("video snapshot failed for %s: %s", video_id, exc)

    channel_ids = [
        r["ref_id"]
        for r in db.all("SELECT ref_id FROM tracked_items WHERE kind = 'channel' ORDER BY added_at")
    ]
    for i, channel_id in enumerate(channel_ids, start=1):
        if progress:
            progress(f"Snapshoting channel {i}/{len(channel_ids)}")
        try:
            se.save_channel_snapshot(fetch_channel(channel_id, cookiefile=cookiefile))
            counts["channels"] += 1
        except Exception as exc:
            failures["channels"] += 1
            logger.warning("channel snapshot failed for %s: %s", channel_id, exc)

    terms = [
        r["ref_id"]
        for r in db.all("SELECT ref_id FROM tracked_items WHERE kind = 'keyword' ORDER BY added_at")
    ]
    for i, term in enumerate(terms, start=1):
        if progress:
            progress(f"Re-ranking keyword {i}/{len(terms)}: {term}")
        try:
            rank_keyword(
                term,
                ResearchOptions(
                    cookiefile=cookiefile,
                    force_refresh=True,
                    max_results=50,
                ),
            )
            counts["keywords"] += 1
        except Exception as exc:
            failures["keywords"] += 1
            logger.warning("keyword snapshot failed for %s: %s", term, exc)

    counts["failed"] = sum(failures.values())
    counts["failures"] = failures  # type: ignore[assignment]
    return counts
