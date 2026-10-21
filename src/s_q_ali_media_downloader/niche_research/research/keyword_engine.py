"""Keyword research engine — ported from the companion research web tool's lib/keywordEngine.ts.

Transparent scoring (no black box):
  - demand: 0-100 from YouTube autocomplete ordering (earlier suggestion = more
    searched). Max rank base across all expansion branches + small frequency bonus.
  - competition: 0-100 from live search results of the top candidates (share of
    videos with 100k+ views + log-scaled average of top-10 views).
  - overall ("opportunity"): (demand * (100 - competition)) / 100.

yt-dlp adaptation notes:
- ``search_videos`` already returns full view/like/comment stats, so ranking a
  keyword needs a single search call (the web tool needed a second ``fetchVideos``).
- Results are written back to the ``videos`` table so ``get_ranked_videos`` can
  JOIN the rankings snapshots, matching the original UX.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from typing import Literal

from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.autocomplete import (
    QUESTION_WORDS,
    fetch_suggestions,
)
from s_q_ali_media_downloader.niche_research.tools.youtube_client import VideoInfo, search_videos

logger = logging.getLogger(__name__)

KEYWORD_CACHE_MS = 24 * 60 * 60 * 1000  # 24h ranking cache per term
CompetitionLabel = Literal["Low", "Medium", "High"]


@dataclass
class KeywordResult:
    term: str
    display_term: str
    demand_score: int
    competition_score: int
    competition_label: CompetitionLabel
    overall_score: int
    source: str
    scored: bool


@dataclass
class ResearchOutput:
    seed: str
    results: list[KeywordResult]
    related_count: int
    matching_terms: list[str]
    questions: list[str]
    ranked: int
    truncated: bool


@dataclass
class ResearchOptions:
    hl: str = "en"
    gl: str = "us"
    rank_top: int = 5
    max_results: int = 60
    force_refresh: bool = False
    cookiefile: str | None = None




def compute_demand(rank_entries: list[dict[str, int]]) -> int:
    """0-100 demand from autocomplete ordering + reoccurrence."""
    if not rank_entries:
        return 0
    best = max(max(0, 100 - entry["rank"] * 7) for entry in rank_entries)
    occurrences = len(rank_entries)
    demand = best + (occurrences - 1) * 3
    return max(0, min(100, round(demand)))


def competition_from_views(views: list[int]) -> tuple[int, CompetitionLabel]:
    if not views:
        return (0, "Low")
    strong = sum(1 for v in views if v >= 100_000)
    strong_share = strong / len(views)
    avg_top10 = sum(views[:10]) / min(10, len(views))
    log_avg = math.log10(max(1, avg_top10)) / 9  # 0..1 for 1..1e9 views
    score = round((strong_share * 0.5 + log_avg * 0.5) * 100)
    score = max(0, min(100, score))
    return (score, competition_label(score))


def competition_label(score: int) -> CompetitionLabel:
    if score < 33:
        return "Low"
    if score < 66:
        return "Medium"
    return "High"


def overall_score(demand: int, competition: int) -> int:
    return max(0, min(100, round((demand * (100 - competition)) / 100)))


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def _upsert_keyword(
    term: str,
    display_term: str,
    score: int,
    demand_score: int,
    competition_score: int,
    competition_label: str,
    source: str,
    language: str | None,
    country: str | None,
    preserve_scored: bool = False,
) -> None:
    """Write a keyword row + a snapshot.

    `preserve_scored` keeps a keyword that was already scored against a live
    search: a later research run that only saw the term in its suggestion pool
    must not reset its competition score and score back to "unscored".
    """
    existing = db.get("SELECT * FROM keywords WHERE term = ?", (term,))
    first_seen = existing["first_seen"] if existing else db.now()
    if preserve_scored and existing and existing["competition_score"] > 0:
        competition_score = existing["competition_score"]
        competition_label = existing["competition_label"]
        score = existing["score"]
    db.run(
        """
        INSERT INTO keywords (
            term, display_term, score, demand_score, competition_score,
            competition_label, source, language, country, first_seen, last_checked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(term) DO UPDATE SET
            display_term = excluded.display_term,
            score = excluded.score,
            demand_score = excluded.demand_score,
            competition_score = excluded.competition_score,
            competition_label = excluded.competition_label,
            source = excluded.source,
            language = excluded.language,
            country = excluded.country,
            last_checked = excluded.last_checked
        """,
        (
            term,
            display_term,
            score,
            demand_score,
            competition_score,
            competition_label,
            source,
            language,
            country,
            first_seen,
            db.now(),
        ),
    )
    db.run(
        """
        INSERT OR IGNORE INTO keyword_snapshots (term, ts, demand_score, competition_score, score)
        VALUES (?, ?, ?, ?, ?)
        """,
        (term, db.now(), demand_score, competition_score, score),
    )


def _save_video_for_ranking(video: VideoInfo) -> None:
    db.run(
        """
        INSERT INTO videos (
            video_id, channel_id, channel_title, title, description, published_at,
            duration_seconds, thumbnail_url, default_language, view_count,
            like_count, comment_count, tags, category_id, last_fetched
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            view_count = excluded.view_count,
            like_count = excluded.like_count,
            comment_count = excluded.comment_count,
            channel_title = CASE
                WHEN excluded.channel_title <> '' THEN excluded.channel_title
                ELSE videos.channel_title
            END,
            last_fetched = excluded.last_fetched
        """,
        (
            video.video_id,
            video.channel_id,
            video.channel_title or "",
            video.title,
            video.description,
            video.published_at,
            video.duration_seconds,
            video.thumbnail_url,
            video.language or "",
            video.view_count,
            video.like_count,
            video.comment_count,
            json.dumps(video.tags) if video.tags else "",
            video.category_id,
            db.now(),
        ),
    )


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #
def rank_keyword(
    term: str, opts: ResearchOptions | None = None, *, demand: int | None = None
) -> KeywordResult | None:
    """Rank a single keyword against a live YouTube search. Cached 24h.

    `demand` is the demand computed from the autocomplete ranks. It is passed
    in by `research_keyword` so the ranking step cannot replace it with the
    "new term" default of 100.
    """
    opts = opts or ResearchOptions()
    existing = db.get(
        "SELECT * FROM keywords WHERE term = ? AND last_checked >= ?",
        (term, db.now() - KEYWORD_CACHE_MS),
    )
    if existing and existing["competition_score"] > 0 and not opts.force_refresh:
        return KeywordResult(
            term=existing["term"],
            display_term=existing["display_term"],
            demand_score=existing["demand_score"],
            competition_score=existing["competition_score"],
            competition_label=existing["competition_label"],
            overall_score=existing["score"],
            source=existing["source"],
            scored=True,
        )

    videos = search_videos(term, max_results=50, cookiefile=opts.cookiefile)
    views = sorted((v.view_count for v in videos if v.view_count), reverse=True)
    comp_score, comp_label = competition_from_views(views)

    if demand is not None:
        demand_score = demand
    elif existing:
        demand_score = existing["demand_score"]
    else:
        demand_score = compute_demand([{"rank": 0, "count": 1}])
    display_term = existing["display_term"] if existing else term
    source = existing["source"] if existing else "search"
    score = overall_score(demand_score, comp_score)
    _upsert_keyword(
        term,
        display_term,
        score,
        demand_score,
        comp_score,
        comp_label,
        source,
        opts.hl,
        opts.gl,
    )

    ts = db.now()
    params: list[tuple[str, str, int, int]] = []
    for position, video in enumerate(videos, start=1):
        if video.video_id:
            _save_video_for_ranking(video)
            params.append((term, video.video_id, position, ts))
    db.exec_many(
        "INSERT OR REPLACE INTO rankings (term, video_id, position, ts) VALUES (?, ?, ?, ?)",
        params,
    )

    return KeywordResult(
        term=term,
        display_term=display_term,
        demand_score=demand_score,
        competition_score=comp_score,
        competition_label=comp_label,
        overall_score=score,
        source=source,
        scored=True,
    )


# --------------------------------------------------------------------------- #
# Research flow
# --------------------------------------------------------------------------- #
def research_keyword(seed: str, opts: ResearchOptions | None = None) -> ResearchOutput:
    """Full research flow: collect suggestions, score demand, rank top candidates."""
    opts = opts or ResearchOptions()
    rank_top = min(opts.rank_top, 10)
    max_results = min(opts.max_results, 200)

    rank_by_term: dict[str, list[dict[str, int]]] = {}
    raw_pool: list[str] = []
    raw_seen: set[str] = set()

    def record_list(terms: list[str]) -> None:
        for idx, term in enumerate(terms):
            key = " ".join(term.lower().split())
            if not key:
                continue
            if key not in raw_seen:
                raw_seen.add(key)
                raw_pool.append(term)
            rank_by_term.setdefault(key, []).append({"rank": idx, "count": 1})

    record_list(_fetch_suggestions_safe(seed, opts))
    for prefix in "abcdefghijklmnopqrstuvwxyz0123456789":
        record_list(_fetch_suggestions_safe(f"{seed} {prefix}", opts))
    for qw in QUESTION_WORDS:
        record_list(_fetch_suggestions_safe(f"{qw} {seed}", opts))

    suggestion_pool = {seed, *raw_pool}
    results: list[KeywordResult] = []
    for term in suggestion_pool:
        norm = " ".join(term.lower().split())
        if not norm:
            continue
        entries = rank_by_term.get(norm) or [{"rank": 99, "count": 1}]
        demand_score = compute_demand(entries)
        source = "seed" if norm == seed.lower() else "autocomplete"
        results.append(
            KeywordResult(
                term=norm,
                display_term=term,
                demand_score=demand_score,
                competition_score=0,
                competition_label="Low",
                overall_score=demand_score,
                source=source,
                scored=False,
            )
        )

    results.sort(key=lambda r: r.demand_score, reverse=True)
    to_rank = [r.term for r in results[:rank_top]]
    demand_by_term = {r.term: r.demand_score for r in results}

    ranked_terms: dict[str, KeywordResult] = {}
    for term in to_rank:
        try:
            ranked = rank_keyword(term, opts, demand=demand_by_term.get(term))
            if ranked:
                ranked_terms[term] = ranked
        except Exception:
            logger.warning("Ranking failed for %r", term, exc_info=True)

    merged = [ranked_terms.get(r.term) or r for r in results]

    seed_lower = seed.lower()
    matching_terms = [
        r.display_term for r in merged if r.term != seed_lower and seed_lower in r.term
    ][:20]

    questions_part = [
        r.display_term for r in merged if any(r.term.startswith(f"{qw} ") for qw in QUESTION_WORDS)
    ][:20]

    for r in merged:
        _upsert_keyword(
            r.term,
            r.display_term,
            r.overall_score,
            r.demand_score,
            r.competition_score,
            r.competition_label,
            r.source,
            opts.hl,
            opts.gl,
            preserve_scored=not r.scored,
        )

    sorted_results = sorted(merged, key=lambda r: r.overall_score, reverse=True)
    truncated = len(sorted_results) > max_results

    return ResearchOutput(
        seed=seed,
        results=sorted_results[:max_results] if truncated else sorted_results,
        related_count=len(sorted_results),
        matching_terms=matching_terms,
        questions=questions_part,
        ranked=len(to_rank),
        truncated=truncated,
    )


def _fetch_suggestions_safe(query: str, opts: ResearchOptions) -> list[str]:
    try:
        return fetch_suggestions(query, hl=opts.hl, gl=opts.gl)
    except Exception:
        logger.warning("Autocomplete failed for %r", query, exc_info=True)
        return []


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #


def get_keyword(term: str) -> dict | None:
    return db.get("SELECT * FROM keywords WHERE term = ?", (term,))


def get_keyword_snapshots(term: str) -> list[dict]:
    return db.all(
        """
        SELECT ts, score, demand_score AS demand, competition_score AS competition
        FROM keyword_snapshots WHERE term = ? ORDER BY ts ASC
        """,
        (term,),
    )


def get_ranked_videos(term: str) -> list[dict]:
    """Ranked videos for the newest ranking snapshot of this term.

    `rankings` keeps every historical snapshot, so without the MAX(ts) filter
    a re-ranked term returns the same video once per run.
    """
    return db.all(
        """
        SELECT r.video_id, r.position, v.title, v.published_at, v.view_count,
               v.like_count, v.comment_count, v.channel_id
        FROM rankings r
        JOIN videos v ON v.video_id = r.video_id
        WHERE r.term = ?
          AND r.ts = (SELECT MAX(ts) FROM rankings WHERE term = ?)
        ORDER BY r.position ASC
        """,
        (term, term),
    )
