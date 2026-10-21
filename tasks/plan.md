# Implementation Plan: Niche Research Completion

**Spec:** `SPEC-niche-research.md` (capability map) + one `SPEC-<module>.md` per module.
**Status:** planned, human-approved scope (functional only · real similar-channel · CSV+JSON+MD export).

## Overview

Niche Research is functionally rich but unreliable: several displayed numbers are
wrong by construction, five reachable paths crash or abort the process, half the
promised features (thumbnail without analysis, similar channel, app-wide poller,
cookie escape hatch, exports, dashboard) are stubs, and only one of ~16
page-to-page handoffs works.

The work is split into nine modules. Two of them (`core-fixes`, `stability`)
are prerequisites for everything else — they make the data true and stop the
crashes. The rest add capability. `polish` runs last because it touches code
the other modules also touch.

## Architecture Decisions

- **Engines stay Qt-free.** All new logic that computes data lives in
  `niche_research/research/*` and `niche_research/tools/*`; the `ui/` layer only
  renders and wires signals. This is the existing split and it is what makes
  the bugs testable without a display.
- **One shared queue bridge.** `ResearchContainer.send_to_queue_requested(list[str])`
  is the single path from the research tab to the download queue. `MainWindow`
  connects it to the same slot the Agent tab uses — so a bug in the bridge is
  fixed once, for both sources.
- **Engine-first vertical slices.** Each task lands an engine change *and* the
  UI that exposes it, plus its regression test — never engine-only batches.
- **Additive schema only.** New columns (e.g. `videos.channel_title`,
  `channel_scripts.idea_id` population) are added with defaults; nothing is
  dropped or renamed, and user data in `%LOCALAPPDATA%` is never deleted.
- **Cookies are a setting, not a secret.** The `cookies.txt` path is stored in
  `settings`; the file is read at request time and never copied into the DB.
- **No new dependencies.** Export uses stdlib `csv`/`json`; the exporter is a
  new module `niche_research/tools/exporter.py`.
- **Explicit user request beats silent failure.** Where a feature cannot
  complete (no similar channel, empty export), the UI says so — no dead
  buttons, no fake values.

## Task List

### Phase 1: Truth and stability (prerequisites)

- [ ] Task 1: Fix keyword demand + ranked-video duplication + score preservation
- [ ] Task 2: Fix trending `last_analyzed` wipe and discovery ordering
- [ ] Task 3: Make the SEO focus-keyword path reachable (engine + Scorecard input)
- [ ] Task 4: Fix tracked-item channel titles and channel-upload view counts
- [ ] Task 5: Fix `is_analyzed` and the analysis-modal worker lifecycle
- [ ] Task 6: Fix the Agent-tab queue bridge, the Scorecard empty state, app close

### Checkpoint: Truth and stability
- [ ] Full suite green, ruff clean
- [ ] Each of the six fixes has a regression test that fails without the fix

### Phase 2: Capability

- [ ] Task 7: Wire the research → download queue bridge + discovery card actions
- [ ] Task 8: Scorecard → Analysis handoff + Competitors drill-down
- [ ] Task 9: Cookie-file setting threaded through every engine
- [ ] Task 10: Exporter module + export buttons on the five data pages
- [ ] Task 11: Real Research Dashboard (metrics, activity, quick actions)
- [ ] Task 12: App-wide hourly poller + real snapshot/VPH accumulation
- [ ] Task 13: Thumbnail without analysis + real similar-channel finder
- [ ] Task 14: AI-only filter, niche competition/difficulty, analysis progress

### Checkpoint: Capability
- [ ] Every handoff in the matrix works (offscreen tests)
- [ ] Export works in all three formats on all five pages
- [ ] Cookies reach every engine; poller accumulates snapshots app-wide

### Phase 3: Polish

- [ ] Task 15: Remove dead code, fix sparkline scaling, labels, QSS rules

### Checkpoint: Complete
- [ ] `pytest -q` green, `ruff check src tests` clean
- [ ] `build_release.bat` produces a working portable build
- [ ] `graphify update .` run
- [ ] CHANGELOG updated

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Schema change breaks an existing user's DB | High | Additive columns only; a `PRAGMA table_info` check adds missing columns at open time |
| Engine rewrites change numbers users already saw | Medium | Each fix lands with a regression test that encodes the correct value |
| The research theme and the app theme disagree | Low | Out of scope by decision — no visual work in this initiative |
| Offscreen GUI tests are flaky around threads | Medium | Workers are joined/destroyed deterministically in the fixes themselves |
| Cookie handling leaks secrets into logs | Medium | Log the path only; never the file contents |
| Scope grows past one session | Medium | Nine modules with explicit checkpoints; each is independently shippable |

## Open Questions

None. Scope, similar-channel behaviour and export formats were confirmed by the
human on 2026-10-20.
