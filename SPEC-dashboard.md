# Spec: `dashboard` — a real Research Dashboard

**Objective:** the Dashboard tab currently shows a static marketing card. It
must answer "what is going on in my research?" at a glance.

## Acceptance criteria

1. **Metric tiles** (live from SQLite, no network):
   - Channels discovered (total) + last-discovery age.
   - Tracked videos / channels / keywords.
   - Keywords researched (total) + tracked keyword count.
   - Videos and channels scored (snapshot counts).
   - Best viral score seen and its channel.
2. **Top channels / top keywords** lists (5 rows each, clickable → the page
   that owns them).
3. **Recent activity feed** — the newest entries of `discovery_log`,
   `keyword_snapshots` and `channel_snapshots`, merged and time-ordered, with
   relative timestamps.
4. **Quick actions** — buttons that actually navigate: Open Niche Discovery,
   Open Scorecard, Open Competitors, Open Settings (the existing three guide
   cards are inert labels today and must become buttons).
5. The Dashboard must refresh when it becomes visible and after any refresh
   elsewhere in the research tab.
6. Empty state: with an empty database the tiles show zeros and a short hint
   on how to start — never a blank page or an exception.

## Verification

- Offscreen tests asserting tile values against a seeded temp DB, the quick
  action buttons, and the empty-DB state.
- `pytest -q` green; `ruff check src tests` clean.

## Boundaries

- Dashboard reads SQLite only — no network calls on the dashboard.
- Reuse the existing widget vocabulary (`statTileValue`, `statTileLabel`,
  `card`, `panel`, `emptyState`); no new theme rules required.
