# Spec: `poller` — snapshots that actually accumulate

**Objective:** VPH (views per hour) and 7-day growth need two snapshots an hour
apart. Today the poller only refreshes while the Competitors tab happens to be
the visible page, so most users never get a second snapshot and the charts stay
flat.

## Acceptance criteria

1. **The poller runs app-wide.**
   - `NichePoller` must trigger a snapshot refresh regardless of which
     research page (or app page) is visible.
   - The refresh must be cancellable and must never run twice concurrently.
2. **It does not fight the user.** A manual "Refresh now" cancels or supersedes
   the automatic one; the UI shows which is running.
3. **The default interval is 60 minutes**, and it is configurable in Settings
   (30 / 60 / 180 minutes).
4. **Snapshots accumulate correctly.**
   - A tracked video/channel/keyword gets a new snapshot row per refresh, so
     VPH and 7-day growth become real.
   - The Competitors page copy must match the behaviour ("The poller records a
     snapshot hourly" is currently false in most sessions).
5. **The poller is stopped on app close** and never leaves a thread behind.
6. **Failures are counted.** A refresh must report how many items succeeded and
   how many failed, instead of "Snapshotted N videos" with silent skips.
7. **Polling is cheap when there is nothing to track** — no network calls when
   the tracked list is empty.

## Verification

- Offscreen tests with a fake clock: the poller fires, produces a snapshot,
   does not double-fire, and stops on close.
- Engine test: `refresh_snapshots` reports success and failure counts.
- `pytest -q` green; `ruff check src tests` clean.

## Boundaries

- The poller must not block the GUI thread; all network work stays in workers.
- The refresh interval is stored in `settings` (`snapshot_interval_minutes`).
