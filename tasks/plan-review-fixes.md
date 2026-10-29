# Implementation Plan: Review Fixes (Instagram & Facebook Expansion)

## Overview

A multi-axis code review of the shipped Instagram and Facebook expansion
found three Required defects and seven Optional/Nit items in two files:
`core/facebook_client.py` and `core/instagram_client.py`, plus the QThread
that calls them (`engine.py`).

The Required defects are all the same shape — **a failure that is invisible
to the user**:

- **R1** — the Facebook paging leg can die on a transport error, and the
  exception escapes the QThread, so the run stops with no message at all.
- **R2** — the paging budget (`MAX_PAGING_SECONDS = 120`) does not cover the
  harvest of the page's JavaScript bundles, which can take 25 × 30 s.
- **R3** — the Instagram carousel fast path hard-codes one typename, so a
  `GraphSidecar` node is silently dropped instead of being checked.

The Optional items are quality: one duplicated listing type, a tautological
test, a progress counter that can count backwards, an untested helper, an
operation line that credits the wrong engine, a magic number and a repeated
`re` match.

**Nothing here changes what the app does for the user** except that failures
become visible. No credential, no login and no session is involved.

## Architecture Decisions

**A1 — The fix is at the boundary, not at the symptom.**
R1 has two layers: the paging leg must not leak a transport error as an
arbitrary exception, and the thread must not swallow an arbitrary exception.
Both are fixed. Fixing only the thread would hide the error but leave the
listing half-done with no reason; fixing only the client would leave any
other unexpected error silent. The first layer produces the honest outcome
("first screen only", the videos already found kept); the second is the
backstop that turns anything else into one sentence.

**A2 — One listing type, not two.**
`core/instagram_client.py::Listing` and `core/facebook_client.py::PageListing`
are the same class with the same contract under two names. They move to
`core/listing.py` as one `Listing`, and both clients import it. The two
clients keep their own names for their own errors — the duplication that
matters is the data type, not the exception hierarchy.

**A3 — The checksum uses Facebook's own formula.**
The current `_checksum` double-counts a constant (`"2" + str(2 + sum)`).
Two independent maintained clients implement it as `"2" + str(sum(ord(c)))`:
[`instagrapi/utils/auth.py`](https://github.com/subzeroid/instagrapi/blob/master/instagrapi/utils/auth.py)
and
[`stupid-social/scripts/instagram-web-client.py`](https://github.com/stephancill/stupid-social/blob/master/scripts/instagram-web-client.py).
The formula is corrected to that and the test pins a **literal** value, so the
test can fail when the code changes.

*Note:* Facebook was measured ignoring the field entirely — four different
`jazoest` values returned the same six ids. The field is still sent, because
a browser sends one, but the formula is now the real one.

**A4 — The progress counter is monotonic and capped.**
The Facebook leg reports progress from two engines (the browser's first
screen and the page's own query). A page that repeats a video made the
counter report a larger number and then a smaller one. One helper now owns
the counter: it never decreases and never exceeds the limit.

**A5 — The operation line names the engine that did the work.**
`list_page_videos` reported every video under `"browser"`, even the ones the
page's own query found. The line now splits the two counts.

## Task List

### Phase 1: The Required defects

- [ ] Task 1 (R1): the paging leg turns a transport error into
      `PagingUnavailable`; the thread turns any unexpected error into one
      sentence.
- [ ] Task 2 (R2): the bundle harvest stops at the paging deadline.
- [ ] Task 3 (R3): the carousel check reads `_CAROUSEL_TYPENAMES`.

### Checkpoint: Required

- [ ] Each Required defect has a regression test that fails without the fix.
- [ ] The whole offline suite passes and ruff is clean.

### Phase 2: The Optional items

- [ ] Task 4 (O1): one `Listing` type in `core/listing.py`.
- [ ] Task 5 (O2): the real checksum formula, pinned by a literal test.
- [ ] Task 6 (O3): a monotonic, capped progress counter.
- [ ] Task 7 (O4): a test for `_default_pager`.
- [ ] Task 8 (O5): the operation line splits the two engines.
- [ ] Task 9 (N1, N2): a named request bound; the token bound once.

### Checkpoint: Complete

- [ ] The suite passes, ruff is clean, `graphify update .` has run.
- [ ] The 2.9.0 EXE is rebuilt and the artifact is verified.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| The `Listing` move breaks an importer | Low | Four import sites; the compiler and the suite find them |
| The deadline cuts the bundle harvest short and the query id is not found | Medium | The listing keeps the browser's videos and says "first screen only" — the same honest outcome as any other paging failure |
| The broader `except Exception` in the thread hides a real bug | Low | The exception is logged with its type and the user gets one sentence; the log keeps the detail |

## Open Questions

None. Every finding came from the review, and every fix has a test.
