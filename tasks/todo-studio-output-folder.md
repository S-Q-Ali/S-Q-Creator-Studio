# Tasks: where the Studio results are saved

Plan: `tasks/plan-studio-output-folder.md` · Spec: `tasks/spec-studio-output-folder.md`
Tested test-first; one offline gate per task; commit only when the gate is green.

## Task 1: put the file in the folder before the legs run

**Description:** one engine helper copies the source into the chosen folder
under a unique name and hands that copy to the legs, so `run_post_leg`,
`reframe` and `shorts` keep their "beside the file" rule and stay untouched.

**Acceptance criteria:**

- [x] `engine.stage_for_folder(path, folder, report)` returns the copy's path,
      names it uniquely when the name is taken, and returns `None` with one
      logged reason when the copy cannot be made.
- [x] A file that already sits in that folder is not copied.
- [x] `LocalVideoThread(files, ..., out_dir=None)`: with `out_dir` it works on
      the copy, without it the run is exactly today's run.
- [x] A file whose copy failed is skipped and the rest of the list still runs;
      no half-written copy is left behind.
- [x] `run_post_leg`, `core/reframe.py` and `core/shorts.py` are not modified.

**Verification:** `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_engine_local_video.py tests/test_engine_post_leg.py -m "not live" -q -p no:warnings`

**Dependencies:** none · **Files:** `engine.py`, `tests/test_engine_local_video.py` · **S/M**

## Task 2: the Studio gets a results folder

**Description:** a row under the options — the field, `Change…` on the app's
own folder picker, `Beside each file` to clear it — remembered between runs
and checked before a run starts.

**Acceptance criteria:**

- [x] The field shows the stored `studio_output_dir`, empty meaning "beside
      each file", and `Change…` writes the picked folder to that key at once.
- [x] `Beside each file` clears the field and the key.
- [x] `Run` passes the field to `LocalVideoThread`; an empty field starts the
      old behaviour.
- [x] A folder that cannot be created or written stops the run with its own
      status line, before any ffmpeg starts.
- [x] The picker is non-native, like the file Browse row.

**Verification:** `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_vertical_studio_page.py -m "not live" -q -p no:warnings`

**Dependencies:** Task 1 · **Files:** `ui/vertical_studio_page.py`, `tests/test_vertical_studio_page.py` · **M**

## Task 3: the page tells the truth about where things went

**Description:** the hint, the run line and the `Done.` line currently promise
"beside each file" in all cases; they have to name the folder when one is set.

**Acceptance criteria:**

- [x] The hint says both cases in one sentence, no filenames.
- [x] `Working: file · copying to the folder` appears before a long copy.
- [x] `Done.` names the folder when one was used, and keeps "beside each file"
      when one was not.
- [x] One `@pytest.mark.live` test: a real file, a real folder — the copy, its
      `_9x16.mp4` and its shorts all in the folder, the source folder clean.

**Verification:** `pytest tests/test_vertical_studio_page.py -q` then the live
test with the venv python.

**Dependencies:** Task 2 · **Files:** `ui/vertical_studio_page.py`, `engine.py`, `tests/test_vertical_studio_page.py` · **S**

## Checkpoint: the feature is done

- [x] Full offline suite green, ruff clean, `graphify update .` in its own
      commit.
- [x] Owner's go for the version bump and the rebuild, taken 2026-11-07; the
      release went to 2.16.0.
- [x] Owner's go before any README/CHANGELOG wording, taken 2026-11-07 ("agay
      barho"); the wording covers 2.15.0, 2.16.0 and 2.17.0 and the release
      went to 2.17.0, rebuilt portable + installer from it.
- [ ] Owner's live check on the new build: set a folder, run one file, everything in it;
      clear it, run again, everything beside the source.
- [ ] Owner's live check of what the audit fixes changed
      (`tasks/plan-studio-audit-fixes.md`): Run with the vertical unticked and
      Shorts on Off answers "Tick the vertical box or pick a shorts length,
      then Run." and starts nothing; Stop pressed during `copying to the
      folder` ends in seconds and leaves no part-copy behind; the error lines
      are the theme's own red; `Tab` reaches the results field from its label.
