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
- [x] Both model files are in the repository, with their licences.
- [x] The detector returns a centre per sampled frame, and nothing when no
      subject is in the frame.
- [x] A face is preferred when there is one; a body is used otherwise.

**Verification:** `pytest tests/test_reframe.py -q` green; the detector is
tested on a frame with a person and on an empty frame. YuNet (MIT, 233 KB)
finds the face in 41 ms and NanoDet int8 (Apache-2.0, 1.0 MB) finds the body
in 103 ms on the test photo.

**Note:** the models are YuNet and NanoDet from the opencv_zoo, fetched with
their licences. OpenCV stays a development requirement until the packaging
step moves it into the runtime requirements.

**Dependencies:** Task 1 · **Files:** `core/reframe.py`,
`models/*`, `tests/test_reframe.py` · **M**

## Task 4: the tracker

**Description:** the sampled centres become a crop path: the subject is
chosen (the largest and most central detection), the path is smoothed, and
the last known position is held through a frame where nothing was found.

**Acceptance criteria:**
- [x] A detection that jumps does not move the crop window in one step.
- [x] A frame with no detection keeps the previous position.
- [x] A video with no detection at all falls back to the centred crop.

**Verification:** `pytest tests/test_reframe.py -q` green. The whole chain was
run on a real video of a person: 25 samples at 5 fps → the path → the render
→ a 630×1120 file (exact 9:16) with the original audio copied.

**Note:** the window may travel at most a quarter of its width per sample, so
the movement stays bounded instead of snapping to a new detection.

**Dependencies:** Task 3 · **Files:** `core/reframe.py`, `tests/test_reframe.py` ·
**S**

## Task 5: the cut points

**Description:** `core/shorts.py` finds the pauses in the speech
(`silencedetect`) and the scene changes, then picks the cut points that land
nearest each target length. A short that ends in the middle of a sentence is
worse than one a few seconds off its length.

**Acceptance criteria:**
- [x] A silence in the speech is preferred over a scene change.
- [x] The cut point for a 60 s target is within 15 s of 60 s when the video
      offers a pause there.
- [x] A video with neither pauses nor scene changes falls back to equal
      segments of the target length.
- [x] The `Auto` mode cuts on scene changes with no target length.
- [x] The *N clips* mode divides the duration by the clip count and reports
      the duration it will use before anything is written.
- [x] The report says when the duration is over YouTube Shorts' 3-minute
      limit, and how many clips would fit.

**Verification:** 44 focused tests passed, including a real ffmpeg 9.0
120-second clip whose pauses and scene changes were both detected near 40
and 80 seconds. The offline suite and ruff also passed after review fixes.

**Note:** N clips keeps exactly N parts; fixed targets keep even a short
final part. Reports show the average and actual planned duration range,
warn if any part exceeds 180 seconds, and round up the recommended count.
Pauses win over scene changes within non-overlapping target windows.
Silence detection cannot guarantee sentence boundaries; without a nearby
pause, scene changes or evenly spaced cuts are used.

**Dependencies:** None · **Files:** `core/shorts.py`, `tests/test_shorts.py` · **S**

## Task 6: the split

**Description:** `core/shorts.py` cuts the video into the segments with one
ffmpeg pass per short, keeping the audio, and names them
`<name>_short01.mp4`.

**Acceptance criteria:**
- [x] Each short carries the original audio.
- [x] The parts together cover the whole video, with no gap and no overlap.
- [x] A video shorter than one target length is not split at all.

**Verification:** 57 offline tests and 5 live tests green against ffmpeg 9.0.
A 120-second clip split at `40.3 / 80.7`, `40.35 / 80.75` and
`40.000005 / 80.000005` keeps all 1,200 decoded frames across the three
shorts and the copied audio packets are sha256-identical to the original.

**Note:** a fractional cut boundary silently dropped one frame until the
encoder was told to pass the source time base through
(`-fps_mode:v passthrough -enc_time_base:v demux`). The original is never
touched: every destination is checked before the first render, each clip is
staged in a temp dir and published with an exclusive create, and a failed
clip removes only the file that clip created.

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

- [x] The offline suite green.
- [x] A short video goes through detection → path → render and comes out
      9:16 with its audio.

## Checkpoint: after Task 6

- [x] The offline suite green.
- [ ] A two-minute video splits into three shorts, none of them cut in the
      middle of a sentence.

The live test splits a 120-second clip into three at the detected pauses
(near 40 s and 80 s), so the cut points land where the audio is silent. The
test media is a tone, not speech, so the sentence-boundary half of this
check is the owner's listening test on a real talking-head video.

## Checkpoint: after Task 8

- [ ] `ruff` clean, the offline suite green, `graphify update .` refreshed.
- [ ] The Windows installer builds and the app starts.
