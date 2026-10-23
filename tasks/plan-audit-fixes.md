# Plan: audit fixes

**Source:** the repo audit (13 findings). **Spec:** the audit report in this
session. **Order:** most important first, each slice one commit, each with a
test that fails before the fix.

| # | Slice | Fixes | Test first |
|---|---|---|---|
| 1 | The queue file is safe to write | #2 atomic write, #3 two instances merge | a test that a failed write leaves the old queue readable |
| 2 | ffmpeg is not a temporary error | #4 | a test that the ffmpeg message is permanent |
| 3 | The temp files are cleaned up | #5, #6 | a test that a failed download leaves no `__amd_` file; that two jobs with one URL use different temp names |
| 4 | One list of TikTok names | #7 | a test that both modules filter the same names |
| 5 | The CI runs what it builds | #8 | the CI step itself |
| 6 | The build script does not hang a scheduler | #9 | the script's own test |
| 7 | Less code in `core/` | #10 | the existing tests are deleted with it |
| 8 | One verifier, one answer | #1 | a test that a guessed account name is not a missing account |
| 9 | Less duplication | #11, #12, #13 | the existing tests keep passing |

## Rules

- One finding per commit. The suite stays green after every commit.
- A fix that needs a product decision (finding #1) is flagged to the human
  instead of guessed at.
- Nothing outside the audit's scope is touched.

## Verification

After every slice: `pytest` (offscreen) and `ruff check src tests`.
At the end: the full suite, a release build, and the CI green.
