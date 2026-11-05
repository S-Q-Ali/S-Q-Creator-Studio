# Vertical 9:16 with subject tracking — task list

Plan: `tasks/plan-vertical-reframe.md` · Spec: `tasks/spec-vertical-reframe.md`

## Task 1: the crop path

**Description:** `core/reframe.py` gains the pure maths of the feature: the
crop width for a source frame, the clamp of the crop's x to the frame, the
smoothing of the sampled positions, and the `sendcmd` command file that hands
the path to ffmpeg.

**Acceptance criteria:**
- [x] The crop window for a 1920×1080 source is 594×1056 — 9:16 to the
      pixel, so the scale to 1080×1920 does not stretch the picture.
- [x] A crop x is clamped to `[0, width - crop_width]`.
- [x] The smoothing moves the window at most so far per sample, so a jump in
      detection does not snap the camera.
- [x] The command file holds one `crop@c x <value>` line per sample, in
      time order.

**Verification:** `pytest tests/test_reframe.py -q` green; the command file
and the clamp are asserted exactly. The generated command file was also run
through ffmpeg 9.0 with `sendcmd`/`crop@c` and produced a 1080×1920 file.

**Dependencies:** None · **Files:** `core/reframe.py`, `tests/test_reframe.py` ·
**S**

## Task 2: the ffmpeg render

**Description:** the render half of `core/reframe.py`: the filter chain
(`sendcmd` → `crop@c` → `scale` → `setsar`), the audio copy, the output name
(`<name>_9x16.mp4`), and the skips — a source that is already vertical, and
an audio-only download.

**Acceptance criteria:**
- [x] The filter string names the command file, the crop window and the
      9:16 output size.
- [x] The audio is copied, not re-encoded.
- [x] A vertical source is left alone and says so.
- [x] An audio-only download is left alone and says so.

**Verification:** `pytest tests/test_reframe.py -q` green; the filter string
is asserted exactly. The render was also run against real ffmpeg 9.0: a
1920×1080 clip came out 1080×1920 h264 with the original AAC track copied.

**Dependencies:** Task 1 · **Files:** `core/reframe.py`, `tests/test_reframe.py` ·
**S**

## Task 3: the detector

**Description:** the YuNet model (MIT, 233 KB) and the NanoDet fallback
(Apache-2.0, 1 MB) are downloaded into the package's `models/` folder, and a
detector is written that returns the subject's centre per sampled frame. The
model path is resolved through `sys._MEIPASS` so the frozen app finds it.

**Acceptance criteria:**
- [ ] Both model files are in the repository, with their licences.
- [ ] The detector returns a centre per sampled frame, and nothing when no
      subject is in the frame.
- [ ] A face is preferred when there is one; a body is used otherwise.

**Verification:** `pytest tests/test_reframe.py -q` green; the detector is
tested on a frame with a person and on an empty frame.

**Dependencies:** Task 1 · **Files:** `core/reframe.py`,
`models/*`, `tests/test_reframe.py` · **M**

## Task 4: the tracker

**Description:** the sampled centres become a crop path: the subject is
chosen (the largest and most central detection), the path is smoothed, and
the last known position is held through a frame where nothing was found.

**Acceptance criteria:**
- [ ] A detection that jumps does not move the crop window in one step.
- [ ] A frame with no detection keeps the previous position.
- [ ] A video with no detection at all falls back to the centred crop.

**Verification:** `pytest tests/test_reframe.py -q` green.

**Dependencies:** Task 3 · **Files:** `core/reframe.py`, `tests/test_reframe.py` ·
**S**

## Task 5: the cut points

**Description:** `core/shorts.py` finds the pauses in the speech
(`silencedetect`) and the scene changes, then picks the cut points that land
nearest each target length. A short that ends in the middle of a sentence is
worse than one a few seconds off its length.

**Acceptance criteria:**
- [ ] A silence in the speech is preferred over a scene change.
- [ ] The cut point for a 60 s target is within 15 s of 60 s when the video
      offers a pause there.
- [ ] A video with neither pauses nor scene changes falls back to equal
      segments of the target length.
- [ ] The `Auto` mode cuts on scene changes with no target length.
- [ ] The *N clips* mode divides the duration by the clip count and reports
      the duration it will use before anything is written.
- [ ] The report says when the duration is over YouTube Shorts' 3-minute
      limit, and how many clips would fit.

**Verification:** `pytest tests/test_shorts.py -q` green.

**Dependencies:** None · **Files:** `core/shorts.py`, `tests/test_shorts.py` · **S**

## Task 6: the split

**Description:** `core/shorts.py` cuts the video into the segments with one
ffmpeg pass per short, keeping the audio, and names them
`<name>_short01.mp4`.

**Acceptance criteria:**
- [ ] Each short carries the original audio.
- [ ] The parts together cover the whole video, with no gap and no overlap.
- [ ] A video shorter than one target length is not split at all.

**Verification:** `pytest tests/test_shorts.py -q` green.

**Dependencies:** Task 5 · **Files:** `core/shorts.py`, `tests/test_shorts.py` ·
**S**

## Task 7: the two controls in the app

**Description:** a checkbox on the download page — "Also make a vertical 9:16
version" — and a dropdown beside it — "Split into shorts" (Off, Auto, 30 s,
45 s, 60 s, 90 s, *N clips*) with a spin box for the clip count. The
post-download leg in the worker runs the split first, then the reframe on
each piece.

**Acceptance criteria:**
- [ ] Both controls are off by default and apply to the whole queue.
- [ ] The spin box only shows in the *N clips* mode, and the app says the
      duration it will use.
- [ ] The split runs before the reframe, and each short gets its own vertical
      version.
- [ ] With the vertical box unticked, the shorts stay 16:9.
- [ ] The work runs in the worker, not on the UI thread.
- [ ] A failure in the reframe never fails the download.

**Verification:** `pytest tests -m "not live" -q` green.

**Dependencies:** Task 2, Task 4, Task 6 · **Files:** `ui/main_window.py`,
`engine.py` · **M**

## Task 8: the packaging

**Description:** `opencv-python-headless` moves into the runtime
requirements, the models are copied into the bundle by the PyInstaller spec,
and the CI matrix proves the built app still starts on all four platforms.

**Acceptance criteria:**
- [ ] `opencv-python-headless==4.14.0.94` is in the runtime requirements.
- [ ] The models are in the bundle and the frozen app finds them.
- [ ] The CI matrix builds and launches the app on all four platforms.

**Verification:** the release build runs on the CI matrix.

**Dependencies:** Task 3, Task 7 · **Files:** `requirements.txt`, `pyproject.toml`,
the PyInstaller spec, `.github/workflows/ci.yml` · **M**

## Task 9: the docs and the release

**Description:** the README and the CHANGELOG say what the feature does and
what it costs, the version is bumped, and the release is tagged.

**Acceptance criteria:**
- [ ] The README describes the feature and the extra weight the app carries.
- [ ] The CHANGELOG entry is dated and written for a user.
- [ ] The version is bumped and the release is tagged.

**Verification:** `gh release view <tag> --json assets`.

**Dependencies:** Task 8 · **Files:** `README.md`, `CHANGELOG.md`,
`pyproject.toml` · **XS**

## Checkpoint: after Task 2

- [ ] `ruff check src tests release` clean.
- [ ] The offline suite green.

## Checkpoint: after Task 4

- [ ] The offline suite green.
- [ ] A short video goes through detection → path → render and comes out
      9:16 with its audio.

## Checkpoint: after Task 6

- [ ] The offline suite green.
- [ ] A two-minute video splits into three shorts, none of them cut in the
      middle of a sentence.

## Checkpoint: after Task 8

- [ ] `ruff` clean, the offline suite green, `graphify update .` refreshed.
- [ ] The Windows installer builds and the app starts.
