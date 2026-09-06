"""Tests for the keyword engine (ported from Niche-Scope's keywordEngine.ts)."""

from s_q_ali_media_downloader.niche_research.research import keyword_engine as ke
from s_q_ali_media_downloader.niche_research.storage import db
from s_q_ali_media_downloader.niche_research.tools.youtube_client import VideoInfo


def _video(video_id, views):
    return VideoInfo(
        video_id=video_id,
        channel_id="UCkw",
        title=f"Video {video_id}",
        published_at="2026-09-01T00:00:00Z",
        duration_seconds=600,
        view_count=views,
        like_count=10,
        comment_count=2,
        tags=[],
    )


# --------------------------------------------------------------------------- #
# Pure scoring
# --------------------------------------------------------------------------- #
def test_compute_demand_single_rank_zero():
    assert ke.compute_demand([{"rank": 0, "count": 1}]) == 100


def test_compute_demand_rank_twenty():
    assert ke.compute_demand([{"rank": 20, "count": 1}]) == 0  # 100 - 140 capped


def test_compute_demand_best_branch_plus_frequency():
    entries = [{"rank": 5, "count": 1}, {"rank": 9, "count": 1}]
    # best = 100 - 35 = 65, + (2-1)*3 = 68
    assert ke.compute_demand(entries) == 68


def test_compute_demand_empty():
    assert ke.compute_demand([]) == 0


def test_competition_from_views_empty():
    assert ke.competition_from_views([]) == (0, "Low")


def test_competition_from_views_all_strong():
    views = [900_000, 800_000, 200_000, 150_000, 120_000]
    score, label = ke.competition_from_views(views)
    assert label == "High"
    assert score > 80


def test_competition_labels_and_overall():
    assert ke.competition_label(32) == "Low"
    assert ke.competition_label(33) == "Medium"
    assert ke.competition_label(65) == "Medium"
    assert ke.competition_label(66) == "High"
    assert ke.overall_score(80, 50) == 40
    assert ke.overall_score(100, 0) == 100
    assert ke.overall_score(0, 50) == 0


def test_decode_term_url_encoded():
    assert ke.decode_term("ai%20tools") == "ai tools"


# --------------------------------------------------------------------------- #
# rank_keyword persistence + 24h cache
# --------------------------------------------------------------------------- #
def test_rank_keyword_scores_and_caches(isolated_appdata, monkeypatch):
    db.configure(None)
    calls = {"n": 0}

    def fake_search(query, max_results=50, cookiefile=None):
        calls["n"] += 1
        return [
            _video("v1", 2_000_000),
            _video("v2", 150_000),
            _video("v3", 800),
        ]

    monkeypatch.setattr(ke, "search_videos", fake_search)

    result = ke.rank_keyword("ai tools", ke.ResearchOptions())
    assert result is not None
    assert result.scored is True
    assert result.competition_label == "High"
    assert result.demand_score == 100  # default when no existing entry
    assert result.overall_score == ke.overall_score(100, result.competition_score)

    row = db.get("SELECT * FROM keywords WHERE term = ?", ("ai tools",))
    assert row["score"] == result.overall_score
    assert row["competition_label"] == "High"

    snap = db.all("SELECT * FROM keyword_snapshots WHERE term = ?", ("ai tools",))
    assert len(snap) == 1

    ranked = db.all("SELECT * FROM rankings WHERE term = ? ORDER BY position", ("ai tools",))
    assert [r["video_id"] for r in ranked] == ["v1", "v2", "v3"]
    assert db.get("SELECT * FROM videos WHERE video_id = ?", ("v1",))["view_count"] == 2_000_000

    # Second call hits the 24h cache -> no extra search
    again = ke.rank_keyword("ai tools")
    assert calls["n"] == 1
    assert again.scored is True
    db.close_db()


def test_rank_keyword_force_refresh_searches_again(isolated_appdata, monkeypatch):
    db.configure(None)
    calls = {"n": 0}

    def fake_search(query, max_results=50, cookiefile=None):
        calls["n"] += 1
        return [_video("v1", 500_000)]

    monkeypatch.setattr(ke, "search_videos", fake_search)

    ke.rank_keyword("term x", ke.ResearchOptions())
    ke.rank_keyword("term x", ke.ResearchOptions(force_refresh=True))
    assert calls["n"] == 2
    db.close_db()


# --------------------------------------------------------------------------- #
# research_keyword flow
# --------------------------------------------------------------------------- #
def test_research_keyword_sorts_and_classifies(isolated_appdata, monkeypatch):
    db.configure(None)

    # Controlled suggestion behavior:
    #  direct suggestions for "ai" come sorted
    #  prefixes only return terms involving ai
    def fake_suggestions(query, hl="en", gl="us"):
        if query == "ai":
            return ["ai tools", "ai in education", "ai for beginners"]
        if query == "what ai":
            return ["what is ai"]
        if query == "ai a":
            return ["ai apps"]
        if query == "how ai":
            return ["how ai works"]
        return []

    def fake_search(search_term, max_results=50, cookiefile=None):
        views = 2_000_000 if search_term in ("ai tools", "ai for beginners") else 900
        return [_video(f"{search_term[:3]}{i}", views) for i in range(2)]

    monkeypatch.setattr(ke, "fetch_suggestions", fake_suggestions)
    monkeypatch.setattr(ke, "search_videos", fake_search)

    out = ke.research_keyword("ai", ke.ResearchOptions(rank_top=3, max_results=10))

    assert out.seed == "ai"
    assert out.ranked == 3
    terms = [r.term for r in out.results]
    assert "ai" in terms
    assert out.results == sorted(out.results, key=lambda r: r.overall_score, reverse=True)
    scored = [r for r in out.results if r.scored]
    assert scored and all(r.competition_score > 0 for r in scored)

    questions = out.questions
    assert "what is ai" in questions
    assert "how ai works" in questions

    matching = out.matching_terms
    assert all("ai" in t for t in matching)
    assert "ai" not in matching

    assert out.truncated is False
    db.close_db()


def test_research_keyword_handles_bad_suggestions(isolated_appdata, monkeypatch):
    db.configure(None)

    def boom(query, hl="en", gl="us"):
        raise RuntimeError("down")

    def fake_search(search_term, max_results=50, cookiefile=None):
        return [_video("v", 1_000)]

    monkeypatch.setattr(ke, "fetch_suggestions", boom)
    monkeypatch.setattr(ke, "search_videos", fake_search)

    out = ke.research_keyword("seed", ke.ResearchOptions(rank_top=1))
    assert out.seed == "seed"
    assert out.ranked == 1
    assert out.results  # at least the seed itself ranked
    db.close_db()


def test_research_keyword_survives_ranking_failure(isolated_appdata, monkeypatch):
    db.configure(None)

    def fake_suggestions(query, hl="en", gl="us"):
        return ["alpha", "beta"] if query == "seed" else []

    def fake_search(search_term, max_results=50, cookiefile=None):
        if search_term == "alpha":
            raise RuntimeError("boom")
        return [_video("v", 9_000)]

    monkeypatch.setattr(ke, "fetch_suggestions", fake_suggestions)
    monkeypatch.setattr(ke, "search_videos", fake_search)

    out = ke.research_keyword("seed", ke.ResearchOptions())
    assert out.ranked == 3
    alpha = next(r for r in out.results if r.term == "alpha")
    assert alpha.scored is False
    assert alpha.competition_score == 0
    assert any(r.scored for r in out.results)
    db.close_db()


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def test_keyword_reads(isolated_appdata):
    db.configure(None)
    ke._upsert_keyword(
        "great term",
        "Great Term",
        score=70,
        demand_score=80,
        competition_score=30,
        competition_label="Low",
        source="autocomplete",
        language="en",
        country="us",
    )

    cached = ke.get_cached_keywords()
    assert len(cached) == 1
    assert cached[0]["term"] == "great term"

    by_search = ke.get_cached_keywords("great")
    assert len(by_search) == 1

    single = ke.get_keyword("great term")
    assert single["score"] == 70

    snaps = ke.get_keyword_snapshots("great term")
    assert len(snaps) == 1
    assert snaps[0]["demand"] == 80

    db.close_db()


def test_get_ranked_videos_joins_videos(isolated_appdata):
    db.configure(None)
    video = _video("vid01", 777)
    ke._save_video_for_ranking(video)
    db.exec_many(
        "INSERT OR REPLACE INTO rankings (term, video_id, position, ts) VALUES (?, ?, ?, ?)",
        [("kw", "vid01", 1, db.now())],
    )
    rows = ke.get_ranked_videos("kw")
    assert len(rows) == 1
    assert rows[0]["view_count"] == 777
    assert rows[0]["position"] == 1
    db.close_db()
