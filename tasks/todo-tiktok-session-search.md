# Todo — Session search (spike, then feature if it passes)

Spec: `tasks/spec-tiktok-session-search.md` · Plan: `tasks/plan-tiktok-session-search.md`

## Phase 0 — measurement

### Task 1: the spike script
**Acceptance:** `tasks/spike_session_search.py` takes three cookie paths and a
query list, searches each platform's search bar with those cookies, prints a
table of attempts / loaded / unique creators / walls / seconds, and prints no
cookie name or value.
**Verify:** `python tasks/spike_session_search.py --help`; a dry run with a
nonexistent path fails with a readable message.
**Files:** `tasks/spike_session_search.py`

- [ ] Cookie loader
- [ ] Three platform searchers
- [ ] Wall detection
- [ ] Metrics table + JSON
- [ ] No secret in output

### Task 2: run it with burner cookies
**Acceptance:** three real burner cookie files; table filled; no checkpoint.
**Verify:** the printed table and JSON.
**Files:** none

- [ ] TikTok
- [ ] Instagram
- [ ] Facebook

### Task 3: gate review
**Acceptance:** user confirms the threshold (≥2 of 3 queries with ≥1 real
creator, no checkpoint) and which platforms continue.
**Verify:** decision written into the spec.

- [ ] Numbers reviewed
- [ ] Platforms chosen

## Checkpoint: Phase 0
- [ ] Gate decided; stop if no platform passes

## Phase 1 — feature (only for platforms that passed)

### Task 4: the searcher module
**Acceptance:** `search_creators(platform, query, cookie_file)` returns a
`SearchOutcome`; per-platform extractors drop product paths and the session
handle; a wall returns a reason instead of raising.
**Verify:** `pytest tests/test_session_search.py`.
**Files:** `agent/tools/session_search.py`, `tests/test_session_search.py`

- [ ] Outcome type and loader
- [ ] Three extractors
- [ ] Wall reasons
- [ ] Tests

### Task 5: the last tier
**Acceptance:** `search_profiles` runs seeds → signed API → yt-dlp → session,
and only the platforms whose cookie file is set; a failed platform leaves the
others working; at most 3 queries per run.
**Verify:** `pytest tests/test_tiktok_pipeline.py`.
**Files:** `agent/tools/tiktok_search.py`, `tests/test_tiktok_pipeline.py`

- [ ] Tier order
- [ ] Per-platform guard
- [ ] Caps
- [ ] Tests

### Task 6: settings and wiring
**Acceptance:** three cookie-file fields in Settings with the burner warning;
paths reach the tool; the log names each platform with its count or wall.
**Verify:** `pytest tests/test_agent_tab.py tests/test_settings_page.py`.
**Files:** `ui/settings_page.py`, `ui/agent_tab.py`, orchestrator wiring

- [ ] Three fields
- [ ] Pass-through
- [ ] Logs
- [ ] Tests

### Task 7: docs and release
**Acceptance:** README and CHANGELOG describe the opt-out-by-empty-field
behaviour and the burner warning; version bumped; bundle verified.
**Verify:** ruff, offline suite, `tasks/spike_verify_bundle.py`,
`tasks/spike_smoke_bundle.py`.

- [ ] README + CHANGELOG
- [ ] Version + build
- [ ] Bundle checks
- [ ] Live run
- [ ] Commits

## Open questions
- Gate threshold confirmation.
- Burner cookies for all three platforms.
- Visible window acceptable during runs?
