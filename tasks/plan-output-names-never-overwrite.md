# Plan: the legs never write over a name that is taken

**Found by:** [audit-vertical-studio.md](audit-vertical-studio.md) findings 1 and 2,
plus [spec-studio-output-folder.md](spec-studio-output-folder.md) decision 2, which
promised "a new name, never an overwrite" and does not get it.

**Owner's decision (2026-11-07):** option **B** — a collision makes a new name, it
never refuses and never overwrites — with the **`Part N`** spelling, applied to the
shorts (which are the parts) and to the vertical's collision suffix. The copy of the
source keeps its existing `(2)` scheme.

## The naming, in one place

| What | First | When that name is taken |
|---|---|---|
| A copy of the source in the results folder | `Film.mp4` | `Film (2).mp4` — `engine.unique_basename`, **unchanged** |
| The vertical of a file | `Film_9x16.mp4` | `Film_9x16 Part 2.mp4`, `Part 3`, … |
| A short | `Film Part 1.mp4` | numbered by its place in the cut; a new cut into a folder that already holds `Part 1-5` continues at `Film Part 6.mp4` |
| The vertical of a short | `Film Part 1_9x16.mp4` | `Film Part 1_9x16 Part 2.mp4` |

Two rules behind all three output rows:

1. **The name is chosen, then held.** The writer creates the file exclusively
   (`open(path, "xb")`) before any work, so ffmpeg's `-y` overwrites a placeholder the
   app made and never a file the user put there. If the exclusive create fails, the
   name was taken between looking and writing: say so and move on — no retry loop,
   there is one writer per folder in this app.
2. **A failed render takes its own file back out.** Same code path that fixes audit
   finding 12 (a truncated `_9x16.mp4` left in the folder claiming to be a result).

Shorts keep publishing with `"xb"` as they do today, so their reservation rule is only
about *which* name is picked, not about how the bytes land.

## Tasks

### 1. `core/output_names.py` (new, ~20 lines) + its tests

The policy the audit found split across three places, in one module with no
dependencies of its own (so `reframe` and `shorts` can both use it; `engine` imports
both, so it cannot host the shared rule).

- `next_part_path(folder, base, ext=".mp4") -> str` — `base`, else `base Part 2`,
  `Part 3`, … the first not already in the folder.
- `next_part_start(folder, stem, ext=".mp4") -> int` — one past the highest
  `stem Part N ext` in the folder, `1` when there are none. Gaps are not filled:
  `Part 1, Part 3` → `4`.

Test-first, `tests/test_output_names.py`: free name, one taken, two taken, no such
folder, and the gapped/highest start.

### 2. `core/reframe.py` — the vertical leg

- `vertical_output_path` ([:221](../src/s_q_ali_media_downloader/core/reframe.py))
  returns the next free part instead of the derived name.
- `render_vertical` ([:356](../src/s_q_ali_media_downloader/core/reframe.py)) holds the
  name before it runs (rule 1), removes what it made when ffmpeg fails or writes
  nothing (rule 2), and its note names the file it wrote — the current
  "The vertical version is beside the original." is a lie about a name the user cannot
  see. `-y` stays: the name is ours, and a prompt would hang the thread.

**Regression test that fails without the fix:** plant a file the user cares about at
`Film_9x16.mp4`, run the leg, assert the user's bytes are still there and the render
landed at `Film_9x16 Part 2.mp4`. Plus: a runner that returns non-zero leaves no
`_9x16` file behind.

### 3. `core/shorts.py` — the shorts leg

- destinations become `{stem} Part {n}` with `n` from `next_part_start`, one per
  segment in order ([:350](../src/s_q_ali_media_downloader/core/shorts.py)).
- The whole-run refusal — "A short output already exists; nothing was overwritten."
  ([:354](../src/s_q_ali_media_downloader/core/shorts.py)) — is deleted. This is the
  half of audit finding 2 that made the legs disagree.

**Regression test:** a folder holding `Film Part 1-2` gets a three-clip cut →
`Part 3, 4, 5`, and the two existing files are untouched.

### 4. `engine.py` — the sentence the user reads

`split_pieces` reports "N shorts saved beside the original."
([:1150](../src/s_q_ali_media_downloader/engine.py)) even when the results folder is
somewhere else and the names are new. Reworded to what happened, in the same place.
No control flow changes here — `stage_for_folder` staying outside the per-file guard is
audit finding 4, a different decision.

### 5. The tests the names are already in

`tests/test_shorts.py` (7 refs), `test_engine_post_leg.py` (16), `test_reframe.py` (6),
`test_engine_local_video.py` (3) — assertions move to the new names. Nothing else in
`src` reads an output filename back: `vertical_output_path` has exactly one caller
(`engine.make_vertical:1181`) and no code greps for `_9x16` or `_short` to find a result.

### 6. Docs that state the names as current fact

- [README.md:55-56](../README.md) and the settings table at :198 — the shipped names.
- [spec-studio-output-folder.md](../spec-studio-output-folder.md) decision 2 — it
  claims the copy's `unique_basename` covers outputs. It does not; corrected to say who
  holds the rule now.
- The `[2.14.0]` CHANGELOG entry keeps `<name>_short01.mp4`: that release shipped that
  name and history is not rewritten. The new names get their own entry, in the version
  bump below.

## Verification

1. `./source/venv/Scripts/python.exe -m ruff check src tests release --output-format concise`
2. One full offline gate:
   `QT_QPA_PLATFORM=offscreen PYTHONIOENCODING=utf-8 ./source/venv/Scripts/python.exe -m pytest tests -m "not live" -q -p no,warnings -o addopts=""`
3. `graphify update .` in its own `chore:` commit.
4. The audit's two proofs re-run against the fixed code: the planted 53-byte
   `Film_9x16.mp4` survives with its bytes, and a re-run in a folder with existing
   parts writes new ones instead of refusing.
5. Owner's live check on a rebuilt portable (below, needs its own go).

## Not in this change (each needs its own go)

- Audit findings 3-6: the default-off vertical checkbox, "Run" with no job chosen,
  `stage_for_folder` outside the per-file guard, and the untested branches
  (`clear`, drag, re-entry, `stop()`, `can_write_to` beyond "path is a file").
- Consider 7-11 and 13: false negative on `os.remove`, Stop not interrupting a copy,
  the second copy of the film on every re-run, `setBuddy`, the inline error stylesheet.
- Version bump (`2.17.0` — user-visible behaviour, nothing broken for a consumer of the
  API), rebuild, tag, push, and the still-open README/CHANGELOG wording for 2.15/2.16.
