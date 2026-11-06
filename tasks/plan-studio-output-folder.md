# Plan: choosing where the Studio results are saved

Spec: `tasks/spec-studio-output-folder.md` · Tracker: `tasks/todo-studio-output-folder.md`

## The one idea

When the Studio has a results folder, each source file is **copied into that
folder under a unique name first**, and the run then works on the copy exactly
as it works on a dropped file today. `run_post_leg` never learns that a folder
exists: its outputs are still "beside the file", and that file now lives in
the folder the owner chose.

That is the whole mechanism. Everything else is a text field, one button and
one `QSettings` key.

## Why this shape and not the obvious one

The obvious change is to thread an `out_dir` through `engine.run_post_leg` →
`reframe.vertical_output_path` and `core/shorts.split_video`. Rejected:

- Two places then build output names instead of one, and both have to agree on
  the collision rule forever.
- `split_video` stages its clips in `original.parent`
  (`core/shorts.py:363`). Point the destination at another volume and the
  staging dir and the published file sit on different drives — slower, and one
  more failure to handle.
- The existing tests and the "outputs land beside each file" invariant stay
  true untouched.

The copy costs disk (the spec records the owner's choice) and buys a second
thing: the run reads the original from wherever it is — a phone, an SD card, a
read-only share — and writes only into a folder it can write to.

## Components and dependencies

| Piece | File | Depends on |
|---|---|---|
| `stage_for_folder(path, folder, report)` → the unique-named copy, or `None` with a reason | `engine.py` | `unique_basename` (already there, `engine.py:775`) |
| `LocalVideoThread(..., out_dir=None)` — copy, then the legs | `engine.py` | the above |
| The folder row: field + `Change…` + `Beside each file`, its load/save, its check before Run | `ui/vertical_studio_page.py` | the thread's `out_dir` |
| Wording: hint, `Done.` line, the folder in the log | `ui/vertical_studio_page.py` | — |
| `reframe.py`, `shorts.py` | — | **not touched** |

Build order: engine helper → thread → page row → wording. Each step is green
before the next starts.

## The rules the code has to hold

1. Empty field ⇒ no copy, no change of behaviour whatsoever (the default).
2. Source already inside the chosen folder (same normalised directory) ⇒ not
   copied; the run works on it where it is.
3. A name already taken in the folder ⇒ `unique_basename` gives `Film (2)`, so
   its results get `(2)_9x16.mp4` and `(2)_short01.mp4`. Nothing is ever
   overwritten — the collision answer the owner picked.
4. Copy fails (disk full, no permission, file vanished) ⇒ that file is named
   in the log and skipped; nothing is written halfway and the run continues
   with the next file. A partial copy is deleted.
5. The chosen folder cannot be made or written ⇒ the status line says so and
   Run does not start. No silent fallback to another folder.
6. The source is read, never modified — the existing promise, unchanged.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A 6 GB film copied doubles disk for the run | High | It is the owner's stated choice; the default stays beside-file. The log names the folder so it is obvious where the bytes went. |
| The copy takes minutes with the bar at 0% | Medium | `Working: file · copying to the folder` before it starts, then the normal bar. The copy is deliberately not priced into the percent — one honest sentence beats a wrong denominator. |
| Two sources with the same stem now silently produce two copies | Low | That is rule 3, and it is what "never overwrite" means in a flat folder; the log names each result. |
| `QSettings` gets a key the Settings page does not show | Low | Deliberate: the Studio owns it. Recorded in the spec so a future pass does not "helpfully" move it. |

## Verification checkpoints

- Per task: the focused pytest file, then ruff.
- After Tasks 1-2: full offline suite, one `@pytest.mark.live` run of a real
  file into a real folder — the file, its vertical and its shorts in the
  folder, the source folder clean.
- Before hand-off: `graphify update .` as its own `chore:` commit, then the
  rebuild and the shipped-bundle check. The version bump and the rebuild are
  the owner's go, not automatic.

## Open before code

Nothing blocking. The owner has approved the three decisions in the spec;
the plan adds one thing they should hear plainly: **the source is copied**, so
the folder holds a second copy of every video it processes.
