# Tasks: Review Fixes (Instagram & Facebook Expansion)

Plan: `tasks/plan-review-fixes.md`

## Phase 1: The Required defects

- [ ] Task 1 (R1): **the paging leg must not fail silently.**
      - [ ] `core/facebook_client.py::_ask` wraps `session.post` so a
            transport error becomes `PagingUnavailable`, not an arbitrary
            exception.
      - [ ] `core/facebook_client.py::paged_video_ids` lets that reach the
            caller as `PagingUnavailable`.
      - [ ] `engine.py::FacebookFetchThread.run` catches any unexpected
            exception and emits one sentence, so a QThread never dies quietly.
      - [ ] `tests/test_facebook_client.py`: a fake HTTP session whose `post`
            raises → `paged_video_ids` raises `PagingUnavailable`.
      - [ ] `tests/test_expand_threads.py`: a client that raises a
            non-`FacebookError` → the thread emits `failed` with one sentence.
      - **Verify:** the new tests fail on the old code and pass on the new.

- [ ] Task 2 (R2): **the paging budget must cover the whole leg.**
      - [ ] `core/facebook_client.py::_query_id` takes a deadline and stops
            the bundle harvest when it passes.
      - [ ] `core/facebook_client.py::paged_video_ids` passes the deadline it
            already computes.
      - [ ] `tests/test_facebook_client.py`: a fake session whose bundle
            fetch crosses the deadline → the harvest stops and the query id
            is not found.
      - **Verify:** the new test fails on the old code and passes on the new.

- [ ] Task 3 (R3): **a carousel must not be dropped by its typename.**
      - [ ] `core/instagram_client.py::_RawPost.get_is_videos` decides from
            `_CAROUSEL_TYPENAMES` instead of one hard-coded string.
      - [ ] `tests/test_instagram_client.py`: a `GraphSidecar` node whose
            metadata says it carries a video → the post is queued.
      - **Verify:** the new test fails on the old code and passes on the new.

### Checkpoint: Required

- [ ] Every Required defect has a regression test that fails without the fix.
- [ ] `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -q -m "not live"` passes.
- [ ] `./source/venv/Scripts/python.exe -m ruff check src tests` is clean.

## Phase 2: The Optional items

- [ ] Task 4 (O1): **one listing type.**
      - [ ] `core/listing.py` holds the single `Listing(list)` with `reason`.
      - [ ] Both clients import it; `PageListing` and the old `Listing` go.
      - [ ] `engine.py` and the tests import the one type.
      - **Verify:** the suite passes; no module defines a second listing class.

- [ ] Task 5 (O2): **the real checksum, pinned by a literal.**
      - [ ] `core/facebook_client.py::_checksum` computes
            `"2" + str(sum(ord(c) for c in token))`.
      - [ ] `tests/test_facebook_client.py` pins the literal for a known
            token instead of re-deriving the formula.
      - **Verify:** the test fails if the formula changes.

- [ ] Task 6 (O3): **the progress counter never counts backwards.**
      - [ ] One helper owns the count: it never decreases and never exceeds
            the limit.
      - [ ] `tests/test_facebook_client.py`: a pager that repeats a video the
            browser already found → the reported count never decreases.
      - **Verify:** the new test fails on the old code and passes on the new.

- [ ] Task 7 (O4): **`_default_pager` is tested.**
      - [ ] A test drives `list_page_videos` with no pager, with
            `paged_video_ids` replaced by a fake → the page name, the
            remaining count and the offset progress are all asserted.
      - **Verify:** the test passes.

- [ ] Task 8 (O5): **the operation line names the engine that did the work.**
      - [ ] `list_page_videos` reports how many videos came from the browser
            and how many from the page's own list.
      - [ ] `tests/test_facebook_client.py` asserts both counts appear.
      - **Verify:** the test passes.

- [ ] Task 9 (N1, N2): **no magic number, no repeated match.**
      - [ ] The request bound in `paged_video_ids` is a named constant.
      - [ ] The token is bound once, not re-matched every iteration.
      - **Verify:** the suite passes.

### Checkpoint: Complete

- [ ] The whole offline suite passes and ruff is clean.
- [ ] `graphify update .` has run and the graph is committed.
- [ ] The 2.9.0 EXE is rebuilt and the artifact is verified with
      `tasks/spike_verify_bundle.py` and `tasks/spike_smoke_bundle.py`.
- [ ] `CHANGELOG.md` mentions the fixes if they are user-visible.
