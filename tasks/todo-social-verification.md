# Task List: stricter Social Discovery verification

Plan: `tasks/plan-social-verification.md` · Spec: `SPEC-social-verify.md`

**Rule for every task:** the test comes first and must fail before the fix.
A test that passes before the change proves nothing.

Run before every checkpoint:

```
$env:PYTHONPATH="src"; source\venv\Scripts\python.exe -m pytest tests/test_social_verify.py -q
$env:PYTHONPATH="src"; source\venv\Scripts\python.exe -m ruff check src tests
```

---

## Task 1: Strict name evidence

**Description:** replace the loose word-subset `name_match` with three
outcomes: exact/neutral `name_match`, informational `name_partial`, and
negative `name_conflict` for fan/clip/parody names.

**Acceptance:**
- [x] `MrBeast` vs `Mr Beast` → `name_match`.
- [x] `MrBeast Official` vs `MrBeast` → `name_match`.
- [x] `MrBeast Fan` vs `MrBeast` → `name_conflict`.
- [x] `MrBeast Clips` vs `MrBeast` → `name_conflict`.
- [x] `MrBeast Vlogs` vs `MrBeast` → `name_partial` (not positive).
- [x] A `name_conflict` page cannot become `FOUND` without `bio_link`.

**Verify:** focused tests fail before the change, pass after.

**Dependencies:** none.

**Files likely touched:**
- `src/s_q_ali_media_downloader/agent/tools/social_verify.py`
- `tests/test_social_verify.py`

**Estimated scope:** Small.

---

## Task 2: Back-link target resolution

**Description:** resolve the actual YouTube target of a link. Unwrap Facebook
`l.php`, YouTube `redirect`, TikTok `link/v2`, and Instagram `l.php`; read
`/channel/UC...`, `/@handle`, `/c/name`, and `/user/name`. A matching target
is `back_link`; a different target is `conflicting_back_link`.

**Acceptance:**
- [x] `youtube.com/channel/UC123` matches `channel_id="UC123"`.
- [x] `youtube.com/@MrBeast` matches `handle="MrBeast"` even when the creator
  URL is a `/channel/` URL.
- [x] A Facebook `l.php?u=...%40mrbeast` redirect is unwrapped and counts.
- [x] A link to `@otherchannel` is `conflicting_back_link`, not `back_link`.
- [x] A page that links only to a different channel is `NO_MATCH` without
  `bio_link`.
- [x] Video/short links do not create false evidence.

**Verify:** focused tests fail before the change, pass after.

**Dependencies:** Task 1 (shared evidence list).

**Files likely touched:**
- `src/s_q_ali_media_downloader/agent/tools/social_verify.py`
- `tests/test_social_verify.py`

**Estimated scope:** Small.

---

## Task 3: Positive-evidence verdict and confidence tiers

**Description:** count only positive evidence, apply the negative blockers,
and attach `confirmed` / `likely` / `unclear` to each result. Keep the
existing verdict vocabulary.

**Acceptance:**
- [x] Two positive signals → `FOUND`.
- [x] One positive signal → `NO_MATCH`.
- [x] `name_conflict` or `conflicting_back_link` without `bio_link` →
  `NO_MATCH` even with two other signals.
- [x] `bio_link` + one positive → `confirmed`.
- [x] `bio_link` alone on an unreadable page → `FOUND`, tier `likely`.
- [x] `name_match` + `handle_match` + `back_link` → `confirmed`.
- [x] `name_match` + `handle_match` without a back-link → `likely`.
- [x] `UNKNOWN`/`NOT_FOUND`/`NO_MATCH` never get a positive tier.

**Verify:** `pytest tests/test_social_verify.py -q`.

**Dependencies:** Tasks 1 and 2.

**Files likely touched:**
- `src/s_q_ali_media_downloader/agent/tools/social_verify.py`
- `tests/test_social_verify.py`

**Estimated scope:** Small.

---

## Task 4: Carry the tier through discovery and the UI

**Description:** pass `channel_id` into `CreatorRef`, copy `tier` into
`PlatformOutcome`, and show it in the table cell, tooltip, detail line,
status, and export. Add the source (`bio` / `model`) to the detail and export.

**Acceptance:**
- [x] `discover()` passes `record.channel_id` to `CreatorRef`.
- [x] A channel-ID back-link can confirm a page when the input was `@handle`.
- [x] `PlatformOutcome.tier` is populated.
- [x] The table cell still contains "Found"; the tooltip/detail show the tier.
- [x] The detail shows the source and the tier.
- [x] The export carries `*_tier` and `*_source`.
- [x] The status says how many found accounts are confirmed vs likely.

**Verify:**
`pytest tests/test_social_discovery.py tests/test_social_discovery_ui.py -q`.

**Dependencies:** Task 3.

**Files likely touched:**
- `src/s_q_ali_media_downloader/agent/social_discovery.py`
- `src/s_q_ali_media_downloader/ui/social_discovery_page.py`
- `tests/test_social_discovery.py`
- `tests/test_social_discovery_ui.py`

**Estimated scope:** Medium.

---

## Checkpoint: Complete

- [x] Focused social tests pass.
- [x] `ruff check src tests` passes.
- [x] Full suite has no new failures (the 3 async rate-limit tests need
  `pytest-asyncio`; live TikTok tests are best-effort and passed on the last run).
- [x] `graphify update .` run.
- [x] Code review with `code-review-and-quality`.
