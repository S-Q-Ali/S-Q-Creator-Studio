# Todo — TikTok discovery via AI search grounding

Spec: `tasks/spec-tiktok-ai-discovery.md` · Plan: `tasks/plan-tiktok-ai-discovery.md`

## Phase 1 — The ask

### Task 1: prompt, parser, proposer
**Acceptance:** `TIKTOK_DISCOVERY_PROMPT` treats the niche as untrusted data
and asks for a JSON `creators` list; `_parse_creator_handles` keeps only
`tiktok.com/@handle` URLs (JSON or prose), strips `@`, dedupes; `_ask_searched`
accepts `parse=`; `propose_tiktok_creators` caps at `limit`.
**Verify:** new tests in `tests/test_social_judge.py` fail before, pass after.
**Files:** `agent/tools/social_judge.py`, `tests/test_social_judge.py`

- [x] Prompt added
- [x] Parser added
- [x] `parse` hook added
- [x] `propose_tiktok_creators` added

### Task 2: tests for the ask
**Acceptance:** JSON list, fenced JSON, prose with URLs, junk (`not a handle`)
rejected, dedupe, cap, fake provider answer returned in order.
**Verify:** the focused new tests pass.
**Files:** `tests/test_social_judge.py`

- [x] Parser tests
- [x] Proposer test with a fake provider

## Phase 2 — The fallback

### Task 3: proposer in the tool
**Acceptance:** `search_profiles(..., proposer=None)` calls the proposer only
when no seed and every listing tier is empty; handles join the same
dedupe/exclusion/enrichment path; `self.discovered_by` is `"listing"`, `"ai"`,
or `""`; the note says the AI was asked.
**Verify:** focused tests pass.
**Files:** `agent/tools/tiktok_search.py`

- [x] `proposer` keyword and call site
- [x] `discovered_by`
- [x] note wording

### Task 4: tool tests
**Acceptance:** fake proposer supplies handles; a seed query never calls the
proposer; `proposer=None` leaves the result and the note as today.
**Verify:** `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -q -m "not live"`
**Files:** `tests/test_tiktok_pipeline.py`

- [x] Proposer used
- [x] Seed skips proposer
- [x] `None` unchanged

## Checkpoint: Phases 1-2
- [x] Offline suite green
- [x] Review with the user before the wiring

## Phase 3 — The wiring

### Task 5: orchestrator proposer
**Acceptance:** the proposer goes through `ask_the_web` with
`budget=self.search_budget`; no AI key means no call; the run logs
`AI proposed N TikTok handle(s)` and the `tiktok.search` detail carries the
source; no key material in any line.
**Verify:** orchestrator tests pass.
**Files:** `agent/orchestrator.py`

- [x] Proposer built
- [x] Count and source logged
- [x] Passed into `search_profiles`

### Task 6: orchestrator tests
**Acceptance:** a tag run with a fake proposer yields the profiles and one
budget call; a spent budget still completes the run.
**Verify:** focused tests pass.
**Files:** `tests/test_tiktok_pipeline.py`, `tests/test_orchestrator.py`

- [x] Budget honoured
- [x] Spent budget survives

## Phase 4 — Text and docs

### Task 7: hint and changelog
**Acceptance:** the tab hint explains the AI fallback; `CHANGELOG.md` carries
one user-visible bullet; no invented version numbers.
**Verify:** ruff and a read-through.

- [x] `ui/agent_tab.py` hint
- [x] `CHANGELOG.md` bullet

## Phase 5 — Live verification and release (2026-10-30)

### Task 8: the search leg names a Groq model that can search
**Acceptance:** `GROQ_SEARCH_MODEL` is `openai/gpt-oss-20b`; every
search-grounded ask (proposer, YouTube search, discovery) defaults to it;
plain asks keep `DEFAULT_MODEL`; a test pins the payload model.
**Verify:** `pytest tests/test_social_judge.py`.
**Files:** `agent/tools/social_judge.py`, `tests/test_social_judge.py`

- [x] Constant and defaults
- [x] Test pins the payload model

### Task 9: live run with the stored key
**Acceptance:** a real `#ishowspeed` run proposes handles through the
configured providers and the log names the source; no key material in any
line.
**Verify:** `tasks/spike_tiktok_live.py` output.

- [ ] Stage A (grounded propose) returns handles
- [ ] Stage B (tool fallback) returns profiles

### Task 10: 2.9.1 artifact
**Acceptance:** EXE and installer built; bundle markers carry the new code;
bundled smoke passes.
**Verify:** `tasks/spike_verify_bundle.py`, release file timestamps.

- [x] Version bumped in `__init__.py` and `pyproject.toml`
- [ ] PyInstaller and Inno succeed
- [ ] Markers PASS on the frozen bundle

## Checkpoint: Complete

- [x] Offline suite and ruff clean
- [x] `graphify update .` run and committed
- [x] User asked before the EXE rebuild
