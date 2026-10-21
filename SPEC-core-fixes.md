# Spec: `core-fixes` — Niche Research engine correctness

**Objective:** the numbers Niche Research shows must be true. Today several
displayed values are wrong by construction, not by flakiness.

## Acceptance criteria

1. **Keyword demand is the computed value, never a constant 100.**
   - `keyword_engine.rank_keyword` currently computes
     `demand = existing["demand_score"] if existing else compute_demand([{"rank": 0, "count": 1}])`,
     which yields 100 for every new term and overwrites the demand that
     `research_keyword` computed at the autocomplete stage.
   - After the fix: a term whose true demand is 37 is stored and displayed as 37.
   - `rank_keyword` accepts an optional pre-computed demand (e.g.
     `opts.demand_override`) and uses it when supplied.
2. **Ranked-video lists contain no duplicates.**
   - `get_ranked_videos` must return only the latest snapshot (`ts = MAX(ts)` for
     the term), mirroring `competitor_engine.get_tracked_keywords`.
3. **Re-discovery never wipes the analysed marker.**
   - `save_trending_channels` must not reset `last_analyzed` to 0 for rows that
     are already analysed.
4. **The keyword-placement half of the SEO score is reachable.**
   - `compute_seo_score` reads `focus_keyword`; `lookup_video` / `lookup_channel`
     must supply it when the caller provides one, and the four checks
     (`keywordTitle`, `keywordDescription`, `keywordTags`, `tripleKeyword`)
     must appear in the result when a focus keyword is present.
5. **Tracked items show a real channel title.**
   - `competitor_engine.get_tracked_videos` / `get_tracked_keywords` must return
     the channel title, not the channel ID and not an empty string.
6. **Channel uploads show their real view count.**
   - `youtube_client.fetch_channel` must not lose `view_count` on uploads
     (the `extract_flat` path drops it).
7. **`is_analyzed` reflects a stored analysis, not the script count.**
   - A channel whose AI response contained 0 scripts must still count as
     analysed.
8. **"Last discovered" shows the newest discovery.**
   - `trending_engine.get_discovery_status` must order by `discovered_at DESC`.
9. **Re-ranked keywords do not lose a previously computed score.**
   - A keyword that was scored in an earlier run must keep its competition
     score when a later, unrelated research run upserts it.

## Verification

- New regression tests in `tests/test_niche_keyword_engine.py`,
  `tests/test_niche_trending_engine.py`, `tests/test_niche_scorecard_engine.py`,
  `tests/test_niche_competitor_engine.py`, `tests/test_niche_youtube_client.py`.
- Each new test fails on the pre-fix code and passes after.
- `pytest -q` green; `ruff check src tests` clean.

## Boundaries

- Engines only — no Qt changes in this module.
- Schema changes are additive only (a new column may be added with a default);
  no table may be dropped or renamed.
- Ask first: any change to how the YouTube Data API key is read.
