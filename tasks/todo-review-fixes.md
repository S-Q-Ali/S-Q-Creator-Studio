# Tasks: Review Fixes (Instagram & Facebook Expansion)

Plan: `tasks/plan-review-fixes.md`

## Phase 1: The Required defects

- [x] Task 1 (R1): **the paging leg must not fail silently.**
      - [x] `core/facebook_client.py::_ask` wraps `session.post` so a
            transport error becomes `PagingUnavailable`, not an arbitrary
            exception.
      - [x] `core/facebook_client.py::paged_video_ids` keeps the ids it
            already found and reports "Facebook stopped answering"; it raises
            only when it has nothing.
      - [x] `engine.py` catches any unexpected exception in both fetch
            threads and emits one sentence, so a QThread never dies quietly.
      - [x] `tests/test_facebook_client.py`: a fake HTTP session whose `post`
            raises → `paged_video_ids` raises `PagingUnavailable`; a failure
            after the first answer keeps what it found.
      - [x] `tests/test_expand_threads.py`: a client that raises a
            non-`FacebookError` → the thread emits `failed` with one
            sentence. Same for Instagram.
      - **Verify:** all six new tests fail on the old code (confirmed by
            stashing the source and re-running) and pass on the new.

- [x] Task 2 (R2): **the paging budget must cover the whole leg.**
      - [x] `core/facebook_client.py::_query_id` takes a deadline and stops
            the bundle harvest when it passes; each fetch is capped by the
            time left.
      - [x] `core/facebook_client.py::paged_video_ids` passes the deadline it
            already computes.
      - [x] `tests/test_facebook_client.py`: a page that names five bundles
            and a clock that eats 100 s per bundle → the harvest stops after
            two, and the listing reports paging as unavailable.
      - **Verify:** confirmed — the old code read all five bundles.

- [x] Task 3 (R3): **a carousel must not be dropped by its typename.**
      - [x] `core/instagram_client.py::_RawPost.get_is_videos` decides from
            `_CAROUSEL_TYPENAMES` instead of one hard-coded string.
      - [x] `tests/test_instagram_client.py`: a `GraphSidecar` node whose
            metadata says it carries a video → the post is queued.
      - **Verify:** confirmed — the old code dropped it.

### Checkpoint: Required

- [x] Every Required defect has a regression test that fails without the fix.
- [x] `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -q -m "not live"` → 625 passed, 15 deselected.
- [x] `./source/venv/Scripts/python.exe -m ruff check src tests` → all checks passed.

## Phase 2: The Optional items

- [x] Task 4 (O1): **one listing type.**
      - [x] `core/listing.py` holds the single `Listing(list)` with `reason`.
      - [x] Both clients import it; `PageListing` and the old `Listing` are
            gone.
      - [x] `engine.py` never named the type; the thread tests now import the
            one type.
      - **Verify:** no module defines a second listing class.

- [x] Task 5 (O2): **the real checksum, pinned by a literal.**
      - [x] `core/facebook_client.py::_checksum` computes
            `"2" + str(sum(ord(c) for c in token))` — the formula two
            maintained clients use (instagrapi, stupid-social). The old one
            added an extra constant.
      - [x] `tests/test_facebook_client.py` pins `"abc"` → `"2294"` instead
            of re-deriving the formula.
      - **Verify:** confirmed — the old formula fails the literal.

- [x] Task 6 (O3): **the progress counter never counts backwards.**
      - [x] `_Progress` owns the count: monotonic and capped at the limit.
      - [x] The pager is told which videos the browser already found
            (`known`), so a video both engines name is counted once.
      - [x] `tests/test_facebook_client.py`: a pager naming a video the
            browser already found → the count never decreases and ends at
            the true total.
      - **Verify:** confirmed — the old code reported 4 and then 3.

- [x] Task 7 (O4): **`_default_pager` is tested.**
      - [x] `test_the_default_pager_asks_the_page_for_the_rest` drives
            `list_page_videos` with no pager and the page name, the remaining
            count, the known videos and the offset progress are all asserted.
      - **Verify:** the test passes.

- [x] Task 8 (O5): **the operation line names the engine that did the work.**
      - [x] `list_page_videos` reports `browser+relay` and both counts when
            the page's own list contributed.
      - [x] `tests/test_facebook_client.py` asserts both counts appear.
      - **Verify:** the test passes.

- [x] Task 9 (N1, N2): **no magic number, no repeated match.**
      - [x] The request bound is `_MAX_REQUESTS`; the bundle timeout is
            `_BUNDLE_TIMEOUT`.
      - [x] The token and page id are matched once and bound.
      - **Verify:** the suite passes.

### Checkpoint: Complete

- [x] The whole offline suite passes and ruff is clean.
- [x] `graphify update .` has run and the graph is committed.
- [ ] The 2.9.0 EXE is rebuilt and the artifact is verified with
      `tasks/spike_verify_bundle.py` and `tasks/spike_smoke_bundle.py`.
- [x] `CHANGELOG.md` carries the user-visible part under 2.9.0 / Fixed.
