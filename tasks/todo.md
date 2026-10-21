# Niche Research Completion — Task List

Plan: `tasks/plan.md` · Specs: `SPEC-niche-research.md` + `SPEC-<module>.md`

Run before every checkpoint:
`source\venv\Scripts\python.exe -m pytest -q` and
`source\venv\Scripts\python.exe -m ruff check src tests`

> **Note (2026-10-21):** every box below was ticked before the release was
> reviewed, and the review found that six of them were not actually true: the
> analysis progress never named the provider and there was no cancel button,
> `analysis_json` held only the strategy, `channel_scripts.idea_id` was never
> written, the Competitors export dropped two of its three groups, and six of
> the eighteen handoffs did not exist. All of them are implemented now, each
> with a regression test — see the commits after the checkpoint commit.

---

## Task 1: Keyword demand, ranked-video duplicates, score preservation

**Description:** `rank_keyword` overwrites the computed demand with 100 for
every new term; `get_ranked_videos` returns every historical snapshot; and a
later research run resets previously scored keywords to "unscored".

**Acceptance criteria:**
- [x] A keyword's stored `demand_score` equals the value computed from the
      autocomplete ranks (never a constant 100).
- [x] `get_ranked_videos` returns only the newest snapshot per term.
- [x] A keyword scored in an earlier run keeps its `competition_score` and
      `score` when an unrelated run upserts it.

**Verification:**
- [x] `pytest tests/test_niche_keyword_engine.py -q`
- [x] Regression tests fail on the pre-fix code.

**Dependencies:** None · **Scope:** M (2 files + tests)

## Task 2: Trending `last_analyzed` + discovery ordering

**Description:** re-discovery resets the analysed marker to 0, and
`get_discovery_status` has no ORDER BY so "Last discovered" is arbitrary.

**Acceptance criteria:**
- [x] Saving trending channels never clears `last_analyzed` on an analysed row.
- [x] `get_discovery_status` returns the newest discovery first.

**Verification:** `pytest tests/test_niche_trending_engine.py -q`

**Dependencies:** None · **Scope:** S

## Task 3: Reachable SEO focus keyword

**Description:** the four keyword-placement checks (34 of 100 actionable points)
can never fire because no caller passes `focus_keyword`.

**Acceptance criteria:**
- [x] `lookup_video` / `lookup_channel` accept and forward a focus keyword.
- [x] With a focus keyword set, the result contains `keywordTitle`,
      `keywordDescription`, `keywordTags` and `tripleKeyword` checks.
- [x] The Scorecard page has a focus-keyword input wired to the lookup.

**Verification:** `pytest tests/test_niche_scorecard_engine.py tests/test_niche_scorecard_ui.py -q`

**Dependencies:** None · **Scope:** M

## Task 4: Tracked-item titles and upload view counts

**Description:** tracked videos show the channel id as the title, tracked
keywords show an empty title, and channel uploads always show 0 views because
the flat-extraction path drops `view_count`.

**Acceptance criteria:**
- [x] Tracked video/channel cards show a real channel title.
- [x] Recent uploads show their real view count.

**Verification:** `pytest tests/test_niche_competitor_engine.py tests/test_niche_youtube_client.py -q`

**Dependencies:** None · **Scope:** M

## Task 5: `is_analyzed` + analysis-modal worker lifecycle

**Description:** a channel with zero scripts is reported as not analysed; closing
the modal mid-analysis aborts the process because `reject()` skips `closeEvent`.

**Acceptance criteria:**
- [x] A stored analysis makes `is_analyzed` true even with 0 scripts.
- [x] Closing the modal during analysis / thumbnail generation / loading exits
      cleanly, with no "QThread: Destroyed while thread is still running".

**Verification:** `pytest tests/test_niche_analysis_ui.py -q`

**Dependencies:** None · **Scope:** M

## Task 6: Queue bridge, Scorecard empty state, app close

**Description:** `MainWindow._handle_agent_urls` calls a non-existent
`add_links_to_queue`; the Scorecard crashes on the second failed lookup; the
app does not stop the research poller on close; the niche filter combo is empty
at startup.

**Acceptance criteria:**
- [x] The Agent tab's queue action adds jobs to the download queue.
- [x] Failing the same Scorecard lookup repeatedly, and switching modes
      repeatedly, never raises.
- [x] Closing the app stops the poller and joins research workers.
- [x] The Niche Discovery niche filter is populated at startup.

**Verification:** `pytest tests/test_niche_scorecard_ui.py tests/test_niche_research_container.py tests/test_gui.py -q`

**Dependencies:** None · **Scope:** M

### Checkpoint: Truth and stability
- [x] Full suite green, ruff clean

## Task 7: Research → queue bridge + discovery card actions

**Description:** the trending card has one action; there is no path from the
research tab to the download queue.

**Acceptance criteria:**
- [x] `ResearchContainer` exposes `send_to_queue_requested(list[str])`.
- [x] The trending card offers Queue videos / Open in Scorecard / Track
      channel / Open channel, each wired and each disabled-with-reason when
      it cannot run.
- [x] `MainWindow` connects the bridge to the download queue.

**Verification:** `pytest tests/test_niche_ui.py tests/test_niche_research_container.py -q`

**Dependencies:** 1-6 · **Scope:** L

## Task 8: Scorecard → Analysis + Competitors drill-down

**Description:** the Scorecard resolves a channel but cannot analyse it; the
Competitors cards are inert.

**Acceptance criteria:**
- [x] The Scorecard offers "Analyze channel" → AnalysisModal for that channel.
- [x] A Competitors video/channel row opens the Scorecard for that item.
- [x] A Competitors keyword row opens the keyword detail.

**Verification:** `pytest tests/test_niche_scorecard_ui.py tests/test_niche_competitor_ui.py -q`

**Dependencies:** 7 · **Scope:** M

## Task 9: Cookie-file setting

**Description:** every engine accepts `cookiefile`, no UI supplies one, so the
YouTube bot-check escape hatch does not exist.

**Acceptance criteria:**
- [x] Settings stores and validates a `cookies.txt` path.
- [x] The path reaches discovery, keyword research, scorecard, competitors
      refresh, AI analysis and the research YouTube client.
- [x] A missing file produces a clear message, not a traceback.
- [x] Cookie values never reach the log.

**Verification:** `pytest tests/test_niche_*.py -q`

**Dependencies:** 1-6 · **Scope:** L

## Task 10: Exporter + export buttons

**Description:** no page except the thumbnail can export.

**Acceptance criteria:**
- [x] `niche_research/tools/exporter.py` serialises to CSV, JSON and Markdown.
- [x] Discovery, Scorecard, Competitors, Keyword Research and AI Analysis each
      have an export button with all three formats.
- [x] Empty data disables the button with a tooltip.
- [x] Write errors are reported in the page status line.

**Verification:** `pytest tests/test_niche_exporter.py -q` (+ page tests)

**Dependencies:** 1-6 · **Scope:** L

## Task 11: Real Research Dashboard

**Description:** the Dashboard is a static intro card.

**Acceptance criteria:**
- [x] Metric tiles, top channels, top keywords, recent activity feed.
- [x] The three guide cards become working navigation buttons.
- [x] Refreshes on visibility; empty DB shows zeros + a hint.

**Verification:** `pytest tests/test_niche_dashboard.py -q`

**Dependencies:** 1-6, 7 · **Scope:** M

## Task 12: App-wide hourly poller

**Description:** the poller only refreshes while the Competitors tab is open.

**Acceptance criteria:**
- [x] Snapshots refresh app-wide, cancellably, never concurrently.
- [x] Interval configurable (30/60/180 min).
- [x] Refresh reports success and failure counts.
- [x] No network calls when nothing is tracked.
- [x] The poller stops on app close.

**Verification:** `pytest tests/test_niche_competitor_ui.py tests/test_niche_research_container.py -q`

**Dependencies:** 1-6 · **Scope:** M

## Task 13: Thumbnail without analysis + real similar channel

**Description:** the Thumbnail tab is gated behind an AI analysis; "Create
Similar Channel" compares a channel to itself.

**Acceptance criteria:**
- [x] The Thumbnail tab is reachable on a fresh channel.
- [x] The similar-channel finder returns a different channel with a real
      0-100 score, or an explicit "none found".
- [x] The full analysis (not just the strategy) is stored in `analysis_json`.
- [x] Scripts are linked to the ideas they came from.

**Verification:** `pytest tests/test_niche_analysis_ui.py tests/test_niche_ai_engine.py -q`

**Dependencies:** 1-6 · **Scope:** L

## Task 14: AI-only filter, niche badges, analysis progress

**Description:** `ai_only` is unreachable, `Niche.competition` /
`Niche.difficulty` are never rendered, and the analysis has no progress or
cancel.

**Acceptance criteria:**
- [x] The discovery toolbar exposes an AI-only filter and the grid honours it.
- [x] The trending card shows niche competition and difficulty.
- [x] The modal shows provider progress and offers cancel.

**Verification:** `pytest tests/test_niche_ui.py tests/test_niche_analysis_ui.py -q`

**Dependencies:** 1-6, 13 · **Scope:** M

### Checkpoint: Capability
- [x] Full suite green, ruff clean

## Task 15: Polish

**Description:** dead code, flat sparklines, a lying button label, dead QSS.

**Acceptance criteria:** everything listed in `SPEC-polish.md`.

**Verification:** `pytest -q`, `ruff check src tests`

**Dependencies:** 1-14 · **Scope:** M

### Checkpoint: Complete
- [x] Full suite green, ruff clean
- [x] `build_release.bat` succeeds
- [x] `graphify update .` run
- [x] CHANGELOG updated
