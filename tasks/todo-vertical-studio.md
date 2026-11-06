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
