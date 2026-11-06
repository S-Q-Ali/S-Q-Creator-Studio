# Tasks: where the Studio results are saved

Plan: `tasks/plan-studio-output-folder.md` · Spec: `tasks/spec-studio-output-folder.md`
Tested test-first; one offline gate per task; commit only when the gate is green.

## Task 1: put the file in the folder before the legs run

**Description:** one engine helper copies the source into the chosen folder
under a unique name and hands that copy to the legs, so `run_post_leg`,
`reframe` and `shorts` keep their "beside the file" rule and stay untouched.

**Acceptance criteria:**

- [ ] `engine.stage_for_folder(path, folder, report)` returns the copy's path,
      names it uniquely when the name is taken, and returns `None` with one
      logged reason when the copy cannot be made.
- [ ] A file that already sits in that folder is not copied.
- [ ] `LocalVideoThread(files, ..., out_dir=None)`: with `out_dir` it works on
      the copy, without it the run is exactly today's run.
- [ ] A file whose copy failed is skipped and the rest of the list still runs;
      no half-written copy is left behind.
- [ ] `run_post_leg`, `core/reframe.py` and `core/shorts.py` are not modified.

**Verification:** `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_engine_local_video.py tests/test_engine_post_leg.py -m "not live" -q -p no:warnings`

**Dependencies:** none · **Files:** `engine.py`, `tests/test_engine_local_video.py` · **S/M**

## Task 2: the Studio gets a results folder

**Description:** a row under the options — the field, `Change…` on the app's
own folder picker, `Beside each file` to clear it — remembered between runs
and checked before a run starts.

**Acceptance criteria:**

- [ ] The field shows the stored `studio_output_dir`, empty meaning "beside
      each file", and `Change…` writes the picked folder to that key at once.
- [ ] `Beside each file` clears the field and the key.
- [ ] `Run` passes the field to `LocalVideoThread`; an empty field starts the
      old behaviour.
- [ ] A folder that cannot be created or written stops the run with its own
      status line, before any ffmpeg starts.
- [ ] The picker is non-native, like the file Browse row.

**Verification:** `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_vertical_studio_page.py -m "not live" -q -p no:warnings`

**Dependencies:** Task 1 · **Files:** `ui/vertical_studio_page.py`, `tests/test_vertical_studio_page.py` · **M**

## Task 3: the page tells the truth about where things went

**Description:** the hint, the run line and the `Done.` line currently promise
"beside each file" in all cases; they have to name the folder when one is set.

**Acceptance criteria:**

- [ ] The hint says both cases in one sentence, no filenames.
- [ ] `Working: file · copying to the folder` appears before a long copy.
- [ ] `Done.` names the folder when one was used, and keeps "beside each file"
      when one was not.
- [ ] One `@pytest.mark.live` test: a real file, a real folder — the copy, its
      `_9x16.mp4` and its shorts all in the folder, the source folder clean.

**Verification:** `pytest tests/test_vertical_studio_page.py -q` then the live
test with the venv python.

**Dependencies:** Task 2 · **Files:** `ui/vertical_studio_page.py`, `engine.py`, `tests/test_vertical_studio_page.py` · **S**

## Checkpoint: the feature is done

- [ ] Full offline suite green, ruff clean, `graphify update .` in its own
      commit.
- [ ] Owner's go before the version bump, the rebuild and any
      README/CHANGELOG wording (the 2.15.0 docs task is still unauthorised).
- [ ] Owner's live check: set a folder, run one file, everything in it;
      clear it, run again, everything beside the source.
