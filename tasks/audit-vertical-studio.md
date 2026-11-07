# Audit: the Vertical Studio

Reviewed 2026-11-07 with `code-review-and-quality` (five axes) over the Studio
only — no other section is covered here, and nothing was changed.

Scope read in full: `ui/vertical_studio_page.py` (499 lines), the Studio's
engine path (`engine.py`: `LocalVideoThread` 1576-1661, `stage_for_folder`
1029-1058, `run_post_leg` 1061-1114, `split_pieces` 1117-1151, `make_vertical`
1154+), the two legs it borrows (`core/reframe.py`, `core/shorts.py`), its
tests (`test_vertical_studio_page.py`, `test_engine_local_video.py`, the live
cases in `test_engine_post_leg.py`) and `tasks/spec-studio-output-folder.md`.

Evidence for findings 1 and 2 was produced by running the exact
`run_post_leg` call the Studio makes, with real ffmpeg, against planted decoy
files in the results folder (scratch script and temp folders deleted after).

## Critical

**1. The vertical leg overwrites a file it did not make — proven.**
`build_command` passes `-y` (`core/reframe.py:331`) and
`render_vertical` writes to `vertical_output_path(path)`
(`core/reframe.py:221-223, 383`) with no existence check anywhere. A 53-byte
`Film_9x16.mp4` placed in the folder was replaced by a 306,046-byte render;
the log said only "The vertical version is beside the original." Nothing was
asked for and nothing was said about the file that was there.

The spec's decision 2 (never overwrite, give it a new name) is met only for
the staged **copy** (`stage_for_folder` → `unique_basename`,
`engine.py:1047-1049`). The outputs derive their names from that stem and are
never deduped, and the branch at `engine.py:1041-1042` — a source that already
lives in the results folder, which is exactly what "sab folder mai" invites —
skips staging entirely and works on the user's own file. So the claim in the
spec that the implementation "gets this for free" is false as written.

**2. The two legs disagree about overwriting, and the disagreement changes
what the user asked for.**
The shorts leg refuses: `split_video` checks every destination with
`os.path.lexists` and returns "A short output already exists; nothing was
overwritten." (`core/shorts.py:349-355`), `_publish_clip` creates with `"xb"`
(`core/shorts.py:387`). `split_pieces` then reports that note and hands back
`[path]` (`engine.py:1147-1149`) — so the vertical leg goes on to render the
**whole film**, not the clips. Proven: with `Film_short01.mp4` present and
Shorts = "N clips", clips = 2, the folder ended with `Film.mp4`,
`Film_9x16.mp4` (6.0 s = the whole film) and the decoy `Film_short01.mp4`;
`Film_short02.mp4` was never written. The user asked for two vertical shorts
and got one vertical feature, silently.

Remedy for both, in one place: decide the naming policy once. Either the
Studio refuses a run whose derived names (`<stem>_9x16.mp4`,
`<stem>_shortNN.mp4`) are taken and says which file is in the way — small,
honest, no change to the shared legs — or the outputs themselves get unique
names, which means an out-dir/naming argument through `vertical_output_path`
and a look at the download tail, because that tail shares the same two legs.
This is a decision for the owner, not for the implementation to make twice.

## Required

**3. A run with nothing chosen says versions were made.** `run()` starts the
thread whatever the options are (`ui/vertical_studio_page.py:413-446`), and
`_on_finished` always says "Done. The versions are in X." (`:484-490`) — so
vertical off + Shorts Off logs `Running 1 file: no vertical · shorts Off ·
into X`, then promises versions that do not exist. The checkbox is off by
default (`:273` reads `stored.value("vertical")` with no default), so the
first run in a fresh settings store is this run.

**4. Staging sits outside the per-file guard.** `engine.py:1632` calls
`stage_for_folder` before the `try` at `:1635`; `stage_for_folder` itself only
catches `OSError` (`:1050`). Anything else from the copy ends the whole loop —
the remaining files are never mentioned. The legs are individually wrapped
(`:1095-1097`, `:1111-1113`); the one step that can take minutes should be
guarded the same way. One-line move.

**5. The spec and plan say things the code does not do.**
`tasks/spec-studio-output-folder.md` decision 2 (see finding 1) and the
`LocalVideoThread` docstring's promise that "the folder ends up holding the
film, its vertical and its shorts" (`engine.py:1586-1589`) are both untested in
the offline suite. Update the document or the code — not neither.

**6. The test gaps that matter** (full map from the coverage pass):

- Nothing offline combines `split` with `out_dir`. Every staging test uses
  `DEFAULT_SPLIT` (`tests/test_engine_local_video.py:221-241`); only the
  `live` test would have caught finding 2, and it is deselected by default.
- No offline test proves a result physically appears in the folder — the fake
  legs create no files (`tests/test_engine_local_video.py:43-49`), so
  `:254` asserts names, not artefacts.
- No test for a collision on an **output** name; the collision test that does
  exist covers the copy only (`:257-273`).
- `can_write_to` is proven for "the path is a file"
  (`tests/test_vertical_studio_page.py:424-427`) and not for the read-only,
  no-space or create-a-new-folder cases its own docstring cites
  (`ui/vertical_studio_page.py:76-80`).
- Untested branches: `clear`/`Clear` (`:375-382`), `dragMoveEvent`
  (`:399-403`), `run()`'s re-entry guard (`:414-415`), the running no-ops in
  `_remove_row`/`clear` (`:368`, `:376`), `stop()` with no thread (`:449`),
  the folder the picker opens at (`:299`), and the sentence
  `_set_results_folder` speaks (`:320-322`).
- Weak assertions: `"into" not in log` (`tests/test_vertical_studio_page.py:484`)
  passes when nothing logs at all; `blocker.is_file()` (`:433`) restates `:425`;
  `paths == []` (`:133`) only proves enter-drag does not add.
- Engine option hygiene: whitespace-only `out_dir`, an invalid `split` string,
  and the `clips` clamp (`engine.py:1609-1611`) are untested.
- `_NAME_LOCK` (`engine.py:1047`) has no concurrent test — the reservation is
  correct by inspection, unproven by suite.

## Consider

**7. `can_write_to` can say no about a folder it can write.** A failed
`os.remove(probe)` (`ui/vertical_studio_page.py:86`) returns False — an
antivirus or indexer holding `.sq-studio-probe` for a moment blocks the run
with "Nothing could be written to X." Only the create should decide the answer.

**8. The legs' log sentences are wrong in folder mode.** "…saved beside the
original" (`engine.py:1150`, `core/shorts.py:380`) and "The vertical version is
beside the original" (`core/reframe.py:392`) are true of the staged copy and
misleading to whoever reads the Studio log after choosing a folder.

**9. The status names the dropped file, not the file being worked.**
`file_started.emit(index, path)` (`engine.py:1628`) fires before
`stage_for_folder` renames it to `Film (2).mp4` (`:1632`), so "Working: Film.mp4"
can describe writes that never touch `Film.mp4`.

**10. Re-running doubles the film every time.** With a folder set, each run of
the same source stages `Film (2).mp4`, `Film (3).mp4`… and their full result
sets. There is no re-render-in-place answer, and the disk cost is already in
the spec.

**11. Stop cannot interrupt a copy.** `_stop` is read only at the top of the
loop (`engine.py:1622-1625`) and `shutil.copyfile` has no cancel, so a 6 GB
film on a slow disk keeps going after the user pressed Stop, which says
"Stopping after the file in hand…".

**12. A failed render leaves a truncated file behind.** `render_vertical`
checks `code != 0 or not isfile` and returns a note without removing the
output (`core/reframe.py:390-391`) — unlike `stage_for_folder`'s half-copy
cleanup (`engine.py:1051-1055`) and `_publish_clip`'s unroll
(`core/shorts.py:391-394`).

**13. Two accessibility/theme nits.** `QLabel("Save results to")` has no
`setBuddy(self.results)` (`ui/vertical_studio_page.py:197`), and `_say` paints
errors with an inline stylesheet (`:493-495`) while the rest of the app renders
from the theme's roles and `kind` properties.

## FYI — checked and sound

- **Security.** Every ffmpeg spawn is an argv list with `shell=False`
  (`core/ffmpeg_process.py:31-66`); no `shell=True`/`os.system` in `src`. User
  paths never enter a filter string — `sendcmd=f=crop.cmd` is a bare relative
  name resolved against a temp `cwd` (`core/reframe.py:379, 386-388`), and
  `write_command_file` writes only ASCII crop lines (`:202-207`). Spaces,
  quotes and non-ASCII names travel as argv. No key, cookie or header appears
  anywhere in the Studio's paths or messages.
- **Odd input.** Portrait and square decline with a sentence
  (`engine.py:1167-1169`), no-picture likewise (`:1163-1166`), a frame too
  small for a 9:16 window raises `ValueError` inside `crop_window`
  (`core/reframe.py:111-117`) and is caught into that sentence (`:379-381`);
  odd dimensions go through `_even` (`:241-242, 810-813`).
- **Zero duration** does not crash: the split bails with its own line
  (`engine.py:1121-1123`) and `_Meter` with `_total == 0` simply reports
  nothing until `finish()` snaps the bar to 100 (`engine.py:1014-1026`).
- **Silence detection** on an audio-less file is swallowed to `""`
  (`core/shorts.py:273-290, 426-435`) — the plan falls back to scene changes.
  It works; the user is just not told why "Auto" picked what it picked.
- **The staged copy is atomic** — `unique_basename` and the `copyfile` are both
  inside `_NAME_LOCK` (`engine.py:1047-1049`), so two threads cannot claim the
  same name.
- **Architecture.** Staging a copy and reusing the legs left
  `core/reframe.py` and `core/shorts.py` untouched, which was the point of the
  design. The price is now visible: naming lives in three places (one
  deduped, two hardcoded suffixes), and that split is exactly what produced
  findings 1 and 2.

## Verdict

**Request changes.** Finding 1 destroys a user's file without asking and
contradicts a decision written into the spec; finding 2 answers a request for
shorts with a full-length vertical and says nothing about it. Both are reachable
through the folder the owner chose on purpose. The verdict does not touch the
rest of the app, and no fix was attempted as part of this audit.

**After the audit.** Findings 1 and 2 are fixed: the owner chose the new-name
rule with the `Part N` spelling, and
[plan-output-names-never-overwrite.md](plan-output-names-never-overwrite.md)
holds the naming now in `core/output_names.py` (commits `183001f`, `e3f067b`).
Findings 3 to 6 still stand.
