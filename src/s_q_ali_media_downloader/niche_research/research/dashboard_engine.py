"""Dashboard data for the research suite — SQLite only, no network.

Answers "what is going on in my research?" at a glance: how much has been
discovered, what is being tracked, what scored best and what happened last.
"""

from __future__ import annotations

from typing import Any

from s_q_ali_media_downloader.niche_research.storage import db

TOP_LIMIT = 5
ACTIVITY_LIMIT = 12


def _count(sql: str, params: tuple = ()) -> int:
    row = db.get(sql, params)
    return int((row or {}).get("count") or 0)


def get_metrics() -> dict[str, Any]:
    """Headline counters for the dashboard tiles."""
    tracked_rows = db.all("SELECT kind, COUNT(*) AS count FROM tracked_items GROUP BY kind")
    tracked = {r["kind"]: int(r["count"]) for r in tracked_rows}
    best = db.get(
        "SELECT title, channel_id, viral_score FROM trending_channels "
        "ORDER BY viral_score DESC LIMIT 1"
    )
    last_discovery = db.get("SELECT MAX(discovered_at) AS ts FROM discovery_log")
    return {
        "channelsDiscovered": _count("SELECT COUNT(*) AS count FROM trending_channels"),
        "keywordsResearched": _count("SELECT COUNT(*) AS count FROM keywords"),
        "videosScored": _count("SELECT COUNT(*) AS count FROM videos"),
        "channelsScored": _count("SELECT COUNT(*) AS count FROM channels"),
        "trackedVideos": tracked.get("video", 0),
        "trackedChannels": tracked.get("channel", 0),
        "trackedKeywords": tracked.get("keyword", 0),
        "bestViralScore": int(best["viral_score"]) if best else 0,
        "bestViralChannel": (best["title"] if best else ""),
        "bestViralChannelId": (best["channel_id"] if best else ""),
        "lastDiscoveryAt": (last_discovery or {}).get("ts"),
    }


def get_top_channels(limit: int = TOP_LIMIT) -> list[dict[str, Any]]:
    return db.all(
        """
        SELECT channel_id, title, subscriber_count, view_count, video_count,
               viral_score, growth_rate, niche, video_format
        FROM trending_channels
        ORDER BY viral_score DESC, subscriber_count DESC
        LIMIT ?
        """,
        (limit,),
    )


def get_top_keywords(limit: int = TOP_LIMIT) -> list[dict[str, Any]]:
    return db.all(
        """
        SELECT term, display_term, score, demand_score, competition_score,
               competition_label
        FROM keywords
        ORDER BY score DESC, demand_score DESC
        LIMIT ?
        """,
        (limit,),
    )


def get_activity(limit: int = ACTIVITY_LIMIT) -> list[dict[str, Any]]:
    """The newest events across discovery, keywords and channel snapshots."""
    events: list[dict[str, Any]] = []

    for row in db.all(
        "SELECT video_format, niche, channels_found, discovered_at FROM discovery_log "
        "ORDER BY discovered_at DESC LIMIT ?",
        (limit,),
    ):
        events.append(
            {
                "ts": row["discovered_at"],
                "kind": "discovery",
                "label": (
                    f"Discovered {row['channels_found'] or 0} channels "
                    f"in {row['niche'] or row['video_format']}"
                ),
            }
        )

    for row in db.all(
        "SELECT term, score, ts FROM keyword_snapshots ORDER BY ts DESC LIMIT ?",
        (limit,),
    ):
        events.append(
            {
                "ts": row["ts"],
                "kind": "keyword",
                "label": f"Keyword “{row['term']}” scored {row['score']}",
            }
        )

    for row in db.all(
        "SELECT channel_id, subscriber_count, ts FROM channel_snapshots "
        "ORDER BY ts DESC LIMIT ?",
        (limit,),
    ):
        subs = row["subscriber_count"]
        events.append(
            {
                "ts": row["ts"],
                "kind": "channel",
                "label": (
                    f"Channel snapshot — {row['channel_id']}"
                    + (f" ({int(subs):,} subs)" if subs is not None else "")
                ),
            }
        )

    events.sort(key=lambda e: e["ts"] or 0, reverse=True)
    return events[:limit]


def get_dashboard_data() -> dict[str, Any]:
    """Everything the dashboard page renders."""
    return {
        "metrics": get_metrics(),
        "topChannels": get_top_channels(),
        "topKeywords": get_top_keywords(),
        "activity": get_activity(),
    }
