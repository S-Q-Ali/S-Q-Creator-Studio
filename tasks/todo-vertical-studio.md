# Task List: the Vertical Studio section

Plan: `tasks/plan-vertical-studio.md` · Spec: `tasks/spec-vertical-studio.md`
· Tracked here (not GitHub) until the work is approved.

## Task 1: lift the two legs out of the download worker

**Description:** `run_post_leg`, `split_pieces` and `make_vertical` become
module-level functions in `engine.py` taking (path, options, ffmpeg,
duration, report). `DownloadThread` keeps its three methods as thin callers
so the download flow changes nothing observable.

**Acceptance criteria:**

- [x] The existing recorder tests pass against the moved functions with their
      expectations unchanged.
- [x] A new test proves the moved legs report a failure and keep going
      instead of raising into the job result.
- [x] `DownloadThread` reads its own `self.vertical` / `self.split` /
      `self.clips` in one place only.

**Verification:**

- [x] `pytest tests/test_engine_post_leg.py -q`
- [ ] Offline suite green.

**Dependencies:** none · **Files:** `engine.py`, `tests/test_engine_post_leg.py` · **M**

## Task 2: the length of a file that was never downloaded

**Description:** the split plans cuts from a duration; a local file has no
yt-dlp info dict, so read the length from the container.

**Acceptance criteria:**

- [x] `reframe.duration_seconds(path)` returns seconds from the frame count
      over the frame rate, the same `cv2.VideoCapture` `frame_size` opens.
- [x] An unreadable or 0-fps file gives 0.0, not a crash.
- [x] `split_pieces` with duration 0 says it did not split, the same sentence
      the download leg uses.

**Verification:**

- [x] `pytest tests/test_reframe.py -q` over `tests/fixtures/tracker-clip.mp4`.
- [ ] Offline suite green.

**Dependencies:** none · **Files:** `core/reframe.py`, `tests/test_reframe.py`, `engine.py` · **XS**

## Task 3: a worker over local files

**Description:** `LocalVideoThread(QThread)` takes a list of paths plus the
run options and calls the shared legs in order, one file at a time, emitting
progress and a log line per file. Stop finishes the file in hand.

**Acceptance criteria:**

- [x] Signals the page can draw: `file_started(index, path)`,
      `progress(percent, stage)`, `log(text)`, `finished_all()`.
- [x] A non-video, an unreadable file and an already-vertical file each get
      one sentence and the run continues.
- [x] `stop()` ends the list after the current file, never mid-write.

**Verification:**

- [x] New `tests/test_engine_local_video.py` with the Task 1 recorders — no
      ffmpeg, no OpenCV.
- [x] Offline suite green.

**Dependencies:** Tasks 1, 2 · **Files:** `engine.py`, `tests/test_engine_local_video.py` · **M**

## Task 4: the page — drop, browse, run

**Description:** `ui/vertical_studio_page.py`: a drop zone that takes video
files by drag-and-drop and by a Browse button, the list it collected, the
three run options seeded from settings, Run and Stop, and a log line.

**Acceptance criteria:**

- [x] Files only (regular files whose suffix is in the video set); a folder
      or a URL in the drop is refused with a sentence.
- [x] Drops are accepted only while this page is the visible one.
- [x] Browse adds to the list, double-click or Remove takes an entry out.
- [x] Run disables itself while a worker is running; Stop returns it.

**Verification:**

- [x] `pytest tests/test_vertical_studio_page.py -q` — a synthesized
      `QMimeData` drop, a monkeypatched `QFileDialog`, a faked worker.
- [x] Offline suite green.

**Dependencies:** Task 3 · **Files:** `ui/vertical_studio_page.py`, `tests/test_vertical_studio_page.py` · **L**

## Task 5: put the section in the window

**Description:** the fifth nav button and the page in the workspace stack, in
the existing exclusive-button group, so the keyboard and the rail behave
like the other four.

**Acceptance criteria:**

- [x] `btn_nav_studio` joins `work_tab_group` with the id matching the page's
      index in `workspace_stack`.
- [x] The offscreen `MainWindow` smoke test reaches the section and back.
- [x] The theme sheet styles the new controls — no raw colours in the page.

**Verification:**

- [x] `pytest tests/test_gui.py -q`
- [x] `pytest tests -m "not live" -q` and `ruff check src tests release`.

**Dependencies:** Task 4 · **Files:** `ui/main_window.py`, `tests/test_gui.py`, `ui/theme.py` if needed · **S**

## Task 6: say what it does, then version it

**Description:** README gains the section — what to drop, what lands where,
and the measured cost — and the CHANGELOG gains the release entry.

**Acceptance criteria:**

- [ ] The README's new text states the 4 s per second of film cost and that
      the source file is not touched.
- [ ] No stale claim anywhere: the download flow wording still matches the
      code.
- [ ] Version bump and CHANGELOG heading dated on the day of the tag, not
      before.

**Verification:**

- [ ] Offline suite green, `ruff` clean, `graphify update .` committed
      separately.
- [ ] Live check (the owner): drop a real landscape video, watch the
      `_9x16.mp4`, judge the camera.

**Dependencies:** Task 5 · **Files:** `README.md`, `CHANGELOG.md`, `pyproject.toml`, `__init__.py` · **XS**

## Checkpoint: after Tasks 1-2

- [ ] The download flow still produces a vertical file and the recorder tests
      are unchanged in what they assert.

## Checkpoint: after Task 5

- [ ] The section is reachable, a real drop runs, and the app stays
      responsive with a file in hand.

## Checkpoint: complete

- [ ] Definition of Done: suite green, ruff clean, docs true, live check by
      the owner.

## Live check of the 2.15.0 portable — what the owner found

Dropped one long video with Shorts Auto and got a blank terminal beside the
window, a bar that never moved, and a plan of 29 clips running from 2 s to
9 min 19 s. Browse opened nothing at all. Each one is a defect with a root
cause in the code, not a setting.

## Task 7: stop ffmpeg from opening a window per call

**Description:** a `--windowed` build has no console, so Windows gives every
ffmpeg child its own. One place spawns ffmpeg and hides the child window.

**Acceptance criteria:**

- [ ] `core/ffmpeg_process.py` owns the spawn and the Windows no-console kwargs.
- [ ] Both detection passes, the split render and the vertical render go through it.
- [ ] No `subprocess.run` for ffmpeg is left in `core/reframe.py` or `core/shorts.py`.

**Verification:** `pytest tests/test_ffmpeg_process.py tests/test_shorts.py tests/test_reframe.py -q`

**Dependencies:** Fix from the live check · **Files:** `core/ffmpeg_process.py`, `core/reframe.py`, `core/shorts.py`, `tests/test_ffmpeg_process.py` · **S**

## Task 8: bound the plan the app chooses itself

**Description:** Auto cut at every scene change, so a long film came out as a
2 s clip beside a 9 min one. When the app picks the cuts it must pick cuts a
Short can be; when the user asks for a number of clips they still get it.

**Acceptance criteria:**

- [ ] Auto and the 30/45/60/90 targets never plan a clip under `MIN_CLIP` or over
      `SHORTS_LIMIT`.
- [ ] The `N clips` mode keeps the requested count whatever the lengths.
- [ ] The tests that asked for a 2 s tail now ask for it merged into its neighbour.

**Verification:** `pytest tests/test_shorts.py -q`

**Dependencies:** none · **Files:** `core/shorts.py`, `tests/test_shorts.py` · **S**

## Task 9: a bar that moves inside one file

**Description:** the thread reported a constant 99.0 and the bar counted files,
so a single long video showed nothing for minutes. ffmpeg can say how far it
got; the app should use it.

**Acceptance criteria:**

- [ ] The passes and the render report how much of the film they have processed.
- [ ] `run_post_leg` turns those into one percent for the file and says the step.
- [ ] The studio bar and status show that percent; the file count stays in the text.

**Verification:** `pytest tests/test_engine_post_leg.py tests/test_engine_local_video.py tests/test_vertical_studio_page.py -q`

**Dependencies:** Task 7 · **Files:** `core/ffmpeg_process.py`, `core/reframe.py`, `core/shorts.py`, `engine.py`, `ui/vertical_studio_page.py`, the three tests · **M**

## Task 10: Browse shows a picker

**Description:** the native shell dialog did not appear at all in the packaged
build, so the picker is Qt's own — the same one on every machine, styled by
the app's sheet, and one a test can reach.

**Acceptance criteria:**

- [ ] The studio's Browse passes `DontUseNativeDialog`.
- [ ] Files chosen through it land in the list the same way a drop does.

**Verification:** `pytest tests/test_vertical_studio_page.py -q`

**Dependencies:** none · **Files:** `ui/vertical_studio_page.py`, `tests/test_vertical_studio_page.py` · **S**

## Checkpoint: the four fixes

- [ ] Offline suite green, ruff clean, graph refreshed.
- [ ] 2.15.0 portable and installer rebuilt, and the frozen bundle carries the fixes.
- [ ] Owner's live check: no terminal window, the bar moves, the Auto plan is sane,
      Browse opens a picker.
