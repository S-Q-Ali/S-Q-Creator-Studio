# Capability Map: Niche Research Completion

**Date:** 2026-10-20 · **Scope:** `src/s_q_ali_media_downloader/niche_research/` (25 files, ~5.6k LOC)
**Status:** approved by the human (functional only — no design unification, no brand sweep;
real similar-channel feature; CSV + JSON + Markdown export)

## Why this initiative

Niche Research works, but only in the happy path. A full audit of the engines
(`research/*`, `tools/*`) and every UI page (`ui/*`) found:

- **P0 correctness bugs** — keyword demand is always `100`, ranked-video lists
  duplicate across runs, `last_analyzed` is wiped on every re-discovery, the
  keyword-placement half of the SEO score (34 of 100 points) can never fire,
  tracked items show a channel ID instead of a title, channel uploads always
  show `0 views`.
- **P0 crashes** — the Agent tab's "Queue" button calls a method that does not
  exist (`add_links_to_queue`), the Scorecard crashes on the *second* failed
  lookup, the AnalysisModal can abort the process when closed mid-analysis,
  and the app does not stop the research poller on close.
- **Half-built features** — the Thumbnail generator is unreachable until an
  unrelated AI analysis exists; "Create Similar Channel" compares a channel to
  itself; the hourly poller only runs while the Competitors tab is open; the
  `cookies.txt` parameter exists in every engine but no UI supplies one; the
  Dashboard is a static intro card; no page except the thumbnail has an export.
- **Missing handoffs** — of ~16 plausible page-to-page handoffs, exactly one
  works (Niche Discovery → AI Analysis).

## Module ids and dependency direction

| Module id | Responsibility | Depends on |
|---|---|---|
| `core-fixes` | Engine data correctness (demand score, ranked videos, `last_analyzed`, `focus_keyword`, channel titles, upload view counts, `is_analyzed`, discovery ordering) | — |
| `stability` | Crash and abort fixes (queue bridge, Scorecard empty state, modal worker lifetime, app close, empty niche combo) | — |
| `handoffs` | Cross-page wiring: Discovery → queue / Scorecard / Track, Scorecard → Analysis, Competitors → drill-down | `core-fixes`, `stability` |
| `dashboard` | Real Research Dashboard — metrics, recent activity, quick actions | `core-fixes`, `handoffs` |
| `export` | CSV + JSON + Markdown export for discovery, scorecard, competitors, analysis | `core-fixes` |
| `auth-robustness` | `cookies.txt` setting wired through every engine; Data API key path completed | `core-fixes` |
| `poller` | App-wide hourly snapshot poller and real VPH series | `core-fixes` |
| `insights` | Thumbnail reachable without analysis, real similar-channel finder, AI-only filter, niche competition/difficulty, analysis progress | `core-fixes` |
| `polish` | Dead code removal, sparkline auto-scale, untrack labels, dead QSS rules | all |

Build order: `core-fixes` + `stability` → `handoffs` → `dashboard` / `export` /
`auth-robustness` / `poller` → `insights` → `polish`

No cycles: every arrow points from a later module to an earlier one.

## Shared commands

```bash
# Tests (offscreen Qt is configured in tests/conftest.py)
source\venv\Scripts\python.exe -m pytest -q
source\venv\Scripts\python.exe -m pytest tests/test_niche_*.py -q

# Lint
source\venv\Scripts\python.exe -m ruff check src tests

# Build
.\build_release.bat
```

## Shared code style

Existing project conventions, unchanged by this initiative:

- Type hints on public functions; `from __future__ import annotations` in UI modules.
- Logging via `logger = logging.getLogger(__name__)` with lazy `%s` args.
- Engines are pure-ish: they take primitives, return dataclasses/dicts, and
  never touch Qt. All Qt work lives in `ui/`.
- UI pages own their `QThread` workers; workers never touch widgets.
- Every engine function that writes to SQLite uses the shared
  `s_q_ali_media_downloader.niche_research.storage.db` helpers (`db.run`,
  `db.all`, `db.get`, `db.now`).

## Testing strategy

- pytest + PySide6 offscreen (`QT_QPA_PLATFORM=offscreen`, set in `tests/conftest.py`).
- Engines: unit tests with a temp SQLite DB (see `tests/test_niche_*_engine.py`).
- UI: offscreen widget tests that build the real page and assert on state.
- Every bug fixed in this initiative gets a regression test that fails without
  the fix (named after the bug).
- Full suite must stay green; `ruff check src tests` must stay clean.

## Boundaries

- **Always:** run the full test suite and ruff before declaring a module done;
  write a regression test with every fix; keep engines free of Qt imports.
- **Ask first:** adding a new third-party dependency; changing the SQLite
  schema in a way that drops user data; changing anything outside
  `niche_research/` except the two integration points in `ui/main_window.py`
  (the queue bridge and the close handler).
- **Never:** delete user data; rewrite git history; commit secrets; disable or
  delete an existing failing test to make the suite green.

## Success criteria

- Every P0 bug above has a regression test and is fixed.
- No page can reach a crash or an abort path (verified by offscreen tests).
- All ~16 page-to-page handoffs exist and work.
- Every page with data offers CSV + JSON + Markdown export.
- A `cookies.txt` can be configured in Settings and reaches every engine.
- The hourly poller runs app-wide, not only when the Competitors tab is open.
- The Thumbnail generator is reachable without running an AI analysis.
- "Create Similar Channel" returns a genuinely different, scored channel.
- `pytest` and `ruff` are green; the release build succeeds.

## Open questions

None — all scope questions were answered by the human on 2026-10-20.
