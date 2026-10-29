# Todo — TikTok seeds checked on YouTube + Instagram + Facebook

Spec: `tasks/spec-tiktok-seed-socials.md` · Plan: `tasks/plan-tiktok-seed-socials.md`

## Phase 1 — Listing truth

### Task 1: remove the session-user harvest
**Acceptance:** `TikTokApiSession` has no `_html_handles`; `fetch_tag_handles`
and `fetch_search_handles` call only the signed API; `_clean_handles` keeps
dotted handles such as `khaby.lame`.
**Verify:** focused API tests fail before, pass after.
**Files:** `agent/tools/tiktok_api.py`, `tests/test_tiktok_pipeline.py`

- [x] Harvest and patterns deleted
- [x] HTML tiers removed from both fetchers
- [x] Dotted handles kept

### Task 2: query parsing, note, shared finalize
**Acceptance:** comma/newline segments; `#word` or a bare single word is a tag;
multi-word segments are keywords; seeds skip discovery; the no-results note
says listing is blocked even with cookies and asks for `@handles`; seed and
listing paths share `_finalize_profiles`; a default nickname becomes the
handle after silent enrichment.
**Verify:** parsing and note tests pass.
**Files:** `agent/tools/tiktok_search.py`, `tests/test_tiktok_pipeline.py`

- [x] Segment parsing
- [x] Auto-`#`
- [x] Note wording
- [x] `_finalize_profiles`
- [x] HTML fallback call sites deleted

### Task 3: remove the AI listing proposer
**Acceptance:** `search_profiles` has no `proposer` keyword; the orchestrator
has no `_tiktok_proposer`; `propose_tiktok_creators`,
`TIKTOK_DISCOVERY_PROMPT`, `_parse_creator_handles` and
`MAX_DISCOVERY_PROPOSALS` are gone; no AI call is made for discovery.
**Verify:** no references in `src`; focused tests pass.
**Files:** `agent/tools/tiktok_search.py`, `agent/orchestrator.py`,
`agent/tools/social_judge.py`, tests

- [x] Tool plumbing removed
- [x] Orchestrator plumbing removed
- [x] Judge discovery functions removed
- [x] Tests updated

### Task 4: listing tests
**Acceptance:** a fake page shell whose only `uniqueId` is the session user
yields 0 profiles; `IShowSpeed edits, ishowspeedlive` yields tag
`ishowspeedlive` + keywords `IShowSpeed edits`; a seed query makes no listing
request; the blocked note names cookies and asks for handles.
**Verify:** `pytest tests/test_tiktok_pipeline.py`.
**Files:** `tests/test_tiktok_pipeline.py`

- [x] Session-shell regression
- [x] Parsing tests
- [x] Seed short-circuit
- [x] Note tests

## Checkpoint: Phase 1
- [x] Offline suite green
- [x] User reviews before Phase 2

## Phase 2 — Per-creator socials

### Task 5: schema
**Acceptance:** `TikTokProfileMetadata` carries `facebook` and `instagram`
`SocialPresence` fields with the right platform defaults.
**Verify:** schema test.
**Files:** `agent/schema.py`, `tests/test_agent_schema.py`

- [x] Fields added

### Task 6: one ask for FB / IG / YT
**Acceptance:** `propose_tiktok_socials(nickname, handle, followers, bio)`
asks for `facebook`, `instagram`, `youtube` in one JSON, treats creator text as
untrusted, returns a `Proposal`; `propose_youtube`, `YOUTUBE_SCHEMA` and
`build_youtube_prompt` are removed.
**Verify:** focused judge tests pass.
**Files:** `agent/tools/social_judge.py`, `tests/test_social_judge.py`

- [x] Prompt and schema
- [x] Function
- [x] Old YouTube-only ask removed
- [x] Tests

### Task 7: FB + IG verifier entry point
**Acceptance:** `verify_creator_socials(candidate_fb, candidate_ig,
channel_handle, candidate_sources, creator)` probes FB and IG in parallel,
applies the rendered and agent fallbacks, returns two presences, and never
probes TikTok.
**Verify:** verifier tests pass.
**Files:** `agent/tools/social_verifier.py`, `tests/test_social_verifier.py`

- [x] Method added
- [x] No TikTok probe
- [x] Tests

### Task 8: orchestrator wiring
**Acceptance:** for each profile: one plain ask (budget-capped), the YouTube
candidate goes to `check_youtube_presence`, `_second_check_youtube` stays,
FB/IG candidates or handle guesses go to `verify_creator_socials`; the log
names each platform's status; no session handle is ever added.
**Verify:** focused orchestrator tests pass.
**Files:** `agent/orchestrator.py`, `tests/test_orchestrator.py`

- [x] One ask per profile
- [x] YouTube candidate wired
- [x] FB / IG verified
- [x] Logs and budgets
- [x] Tests

## Checkpoint: Phase 2
- [x] Full offline suite green

## Phase 3 — UI and docs

### Task 9: table, export, copy, labels
**Acceptance:** TikTok table columns are Select / Nickname / Handle /
Followers / Facebook / Instagram / YouTube Status / YouTube Channel / Flag /
Action; CSV carries FB and IG status + URL; copy FB and copy IG work in this
mode; mode label and hint say pasted handles + three platforms.
**Verify:** `pytest tests/test_agent_tab.py tests/test_ui_layout.py`.
**Files:** `ui/agent_tab.py`, tests

- [x] Columns and population
- [x] CSV
- [x] Copy buttons
- [x] Label and hint

### Task 10: docs
**Acceptance:** README describes the seed-first TikTok mode without stale
claims; CHANGELOG has one user-visible bullet for the fix and the removed AI
listing leg.
**Verify:** read-through.
**Files:** `README.md`, `CHANGELOG.md`

- [x] README
- [x] CHANGELOG

## Phase 4 — Verification and release

### Task 11: checks
**Acceptance:** ruff clean; full offline suite green.
**Verify:** `./source/venv/Scripts/python.exe -m ruff check src tests` and
`pytest tests -q -m "not live"`.

- [x] Ruff
- [x] Offline suite

### Task 12: live seed run
**Acceptance:** with the user's cookies and two real handles, the run shows
both creators, no session handle, and a status for FB / IG / YT; no cookie
value or key material in the log.
**Verify:** `tasks/spike_tiktok_seed_run.py` output.

- [x] Two seeds listed
- [x] Session handle absent
- [x] Three platform statuses

### Task 13: artifact
**Acceptance:** version bumped in `__init__.py` and `pyproject.toml`;
PyInstaller and Inno succeed; bundle markers carry the new code; bundled smoke
passes.
**Verify:** `tasks/spike_verify_bundle.py`, `tasks/spike_smoke_bundle.py`.

- [x] Version bump
- [x] EXE + installer
- [x] Markers
- [x] Smoke

### Task 14: graph and commits
**Acceptance:** `graphify update .`; atomic commits for code, tests, docs and
graph.
**Verify:** `git log --oneline -5`.

- [x] Graph updated
- [x] Commits

## Checkpoint: Complete
- [x] Offline suite and ruff clean
- [x] User asked before the EXE rebuild
