# Implementation Plan: stricter Social Discovery verification

**Spec:** `SPEC-social-verify.md` (updated 2026-10-27)
**Task list:** `tasks/todo-social-verification.md`
**Scope:** back-link target verification, strict name/handle matching, confidence tiers, and the UI/export that shows them. Thumbnails are out of scope.

## Overview

The current verifier counts `name_match`, `handle_match`, and a string
`back_link` as equal evidence. Two signals make `FOUND`. That lets a fan page
pass when it uses the creator's name and links to the creator's YouTube
channel. It also misses real back-links when Facebook wraps them in a redirect
and the URL uses `%40` instead of `@`.

This slice makes the ownership evidence stricter and more honest:

- resolve the actual YouTube target of a back-link (unwrap redirects, read the
  channel ID or `@handle`);
- reject fan/clip names unless the creator's own bio linked the account;
- reject a page whose only YouTube link is a different channel;
- attach a `confirmed` / `likely` tier so "Found" is not overstated.

## Architecture decisions

- **No new dependency and no thumbnail/vision work.** The link graph is the
  signal; images are weak ownership proof.
- **Resolve the back-link target from the URL, not a second browser tab.** The
  candidate page is already open; its links are read. Unwrapping the known
  redirects and reading the channel ID/handle is deterministic, fast, and
  testable offline. Video/short links that do not name a channel are not used.
- **Name matching is exact or explicitly neutral.** Word-subset matches only
  count when the extra words are neutral (`official`, `the`, `channel`, `tv`,
  `show`, `yt`, `youtube`). Fan/clip words are negative evidence.
- **The verdict stays `FOUND` / `NO_MATCH` / `UNKNOWN`; the tier is a new
  field.** This keeps the existing pipeline and table vocabulary while adding
  honesty.
- **The tier is computed from evidence, not from the AI's confidence.** Groq
  still only proposes candidates.
- **`CreatorRef` carries `channel_id`.** A social page may link to
  `/channel/UC...` while the input was `@handle`; both sides must be
  comparable.

## Task list

### Phase 1: Evidence

- [x] Task 1: Strict name evidence (`name_match`, `name_partial`,
  `name_conflict`) with tests.
- [x] Task 2: Back-link target resolver and `conflicting_back_link` with tests.

### Checkpoint: Evidence

- [x] Focused verifier tests pass.
- [x] Existing real/fake/blocked tests still pass.

### Phase 2: Decision

- [x] Task 3: Positive-evidence verdict rule, negative blockers, and
  `confirmed` / `likely` tier with tests.

### Checkpoint: Decision

- [x] `pytest tests/test_social_verify.py -q` passes.
- [x] A fan page with the creator's back-link is `NO_MATCH`.
- [x] A real page with name + handle + back-link is `confirmed`.

### Phase 3: Report

- [x] Task 4: Pass `channel_id` and `tier` through `social_discovery.py`;
  show tier/source in the UI and export; tests.

### Checkpoint: Complete

- [x] Focused social tests pass.
- [x] `ruff check src tests` passes.
- [x] Full suite has no new failures.
- [x] `graphify update .` run.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Strict name matching rejects an official page with an unusual suffix | A false negative | Neutral words are allowed; an exact handle or `bio_link` still finds it. The tier explains the strength. |
| A page links to a second official YouTube channel | It looks like a wrong back-link | If the creator's own bio linked the page, it can still be `FOUND` with tier `likely`; otherwise it is `NO_MATCH`. |
| A back-link is a video/short URL | No back-link evidence | Name/handle/bio signals still apply; the limitation is documented in the spec. |
| The UI grows a column or changes wording | Test churn | Add the tier to the existing cell text/tooltip/detail, not a new column. |
| Existing live tests assume the old loose rule | Flaky live results | The focused fixtures are the contract; live tests remain best-effort. |

## Open questions

- None blocking. If the user later wants video-link back-links, add a
  yt-dlp/YouTube-API resolver as a separate slice.
