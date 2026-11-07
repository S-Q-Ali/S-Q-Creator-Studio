# Plan: the rest of the Vertical Studio audit

Closes what [audit-vertical-studio.md](audit-vertical-studio.md) left standing
after the naming fix: Required 3, 4, 5, 6 and Consider 7, 9, 11, 13.
Finding 10 is the accepted cost of the Part N rule (documented in
[plan-output-names-never-overwrite.md](plan-output-names-never-overwrite.md)),
and 8 and 12 were fixed with the naming change.

Nothing here changes a shared default. The Studio borrows `vertical`/`split`
read-only and the app-wide default stays Off, so the honest place for the
"nothing chosen" answer is the Run button.

## The changes

**A. A run with nothing chosen does not start** (3).
`run()` refuses before the thread is built, with a sentence naming what to
tick, and the tests that expect a run tick the box. After the guard every run
that starts has requested at least one version, so the closing
"Done. The versions are in X." is no longer a promise about nothing.

**B. The copy is guarded like the legs** (4).
`stage_for_folder` catches `Exception`, not just `OSError`, and everything it
does is inside that guard, so a surprise from the copy names the file, says
why, and hands the loop to the next one. The thread also calls it inside the
per-file `try`, so nothing outside the function can end the run.

**C. Only the create decides whether a folder is usable** (7).
`can_write_to` returns False when the probe cannot be *made*; a probe it
cannot take back out (an antivirus holding it for a moment) is left alone and
answered True.

**D. The status names the file the writes go into** (9).
`file_started` fires again with the staged name once the copy has a folder of
its own, so "Working:" never describes writes that never touch the dropped
file. The first emit stays: it is what names the file during the copy.

**E. Stop ends a copy** (11).
The copy is chunked and checks the run's stop flag between chunks; a copy
stopped halfway is taken back out and the file is skipped, the same way a copy
that died is. `COPY_CHUNK` is 4 MB — the buffer is what the check rides on.

**F. The two accessibility/theme nits** (13).
"Save results to" gets `setBuddy` for its field, and `_say` switches the
label's `role` between `meta` and `error` and re-polishes it, so the colour
comes from the theme like everywhere else.

## Tests the audit says are missing (5, 6)

- An offline run with `split` **and** `out_dir` whose legs really write: the
  folder ends up holding the copy, its parts and each part's vertical — the
  docstring promise proved by artefacts, not names.
- `can_write_to`: a missing folder is made and answered yes; a create that
  fails answers no; a delete that fails still answers yes.
- Branches with no test: `clear`, `dragMoveEvent`, the re-entry guard in
  `run()`, the running no-ops in `_remove_row`/`clear`, `stop()` with no
  thread, the folder the results picker opens at, the sentence
  `_set_results_folder` speaks.
- Assertions strengthened: the no-folder log line in full instead of
  `"into" not in log`, and the blocker path checked by its contents instead of
  `is_file()`.
- Engine option hygiene: whitespace-only `out_dir`, an invalid `split` string,
  the `clips` clamp.
- `_NAME_LOCK`: threads staging the same name into one folder each get their
  own file, with their own bytes in it.

## Gate

One ruff run and one full offline suite per slice; `graphify update .` and the
audit note at the end. Commits stay atomic: A/B/C/D/E/F, then the tests that
stand on their own, then docs + graph.

## Verified

- `ruff check src tests release` clean; the offline suite at **1156 passed,
  28 deselected** (from 1133 before: 23 tests added).
- E is not only unit-tested — `test_stop_ends_a_copy_under_way` drops
  `COPY_CHUNK` to 4 bytes and proves the file is gone afterwards.
- `_NAME_LOCK` proved by taking it out: with `engine._NAME_LOCK` replaced by a
  `nullcontext()` and the copy slowed, both workers chose `clip.mp4`, the
  folder held one file, and the second film's bytes were the first's. With the
  lock: `clip.mp4` and `clip (2).mp4`, each with its own bytes.
- F checked against the theme itself, not a screenshot: the error line comes
  from `QLabel[role="error"]` and the widget's own `styleSheet()` stays empty.
- Not checked here: the live Studio run over real ffmpeg with a folder set —
  that stays with the owner in
  [todo-studio-output-folder.md](todo-studio-output-folder.md). Nothing was
  pushed, tagged or rebuilt, and the version is still **2.16.0**, so the
  portable build open on the desktop still has the old behaviour.
