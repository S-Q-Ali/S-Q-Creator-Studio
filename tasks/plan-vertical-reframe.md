# Plan: vertical 9:16 with subject tracking

## Overview

A downloaded landscape video is post-processed into a vertical one whose crop
window follows the person in the frame. Two passes: an analysis pass that
detects the subject and records where the crop should sit over time, and a
render pass that hands that path to ffmpeg.

## Architecture decisions

- **OpenCV only, no new ML runtime.** `mediapipe` and `onnxruntime` publish
  no macOS Intel wheels, and `ultralytics` is AGPL-3.0. `opencv-python-headless`
  has wheels for every platform the app ships on, and `cv2.dnn` runs the
  models.
- **YuNet first, NanoDet as the fallback.** YuNet finds a face in 233 KB and
  is fast; a full-body shot has no face to find, so NanoDet-Plus-S int8
  (1 MB, Apache-2.0) covers it. Neither is large enough to matter beside a
  1.4 GB build.
- **`sendcmd` drives the crop, not a long filtergraph.** ffmpeg's expression
  evaluator has a depth limit of 100, so a long nested `if`/`lerp` chain of
  tracked segments breaks around 100 points. `sendcmd` takes a command file
  of any length and `crop` accepts the `x` command, so the path is written as
  a file the worker writes next to the video.
- **The crop path is sampled, not per frame.** Detection runs at about 5 fps;
  between samples the window moves linearly, and the value is smoothed with
  an EMA so the camera does not jitter.
- **The original is never touched.** The vertical file is written beside it as
  `<name>_9x16.mp4`.
- **A centre crop is the floor.** If no subject is found at all, the video
  still gets a centred 9:16 version — the feature never fails a download.

## Task list

### Phase 1: the pure part

- [ ] **Task 1: the crop path.** `core/reframe.py` grows the maths: the crop
      width for a source, the clamp to the frame, the smoothing, and the
      `sendcmd` command file. Pure functions, no model, no ffmpeg.
- [ ] **Task 2: the ffmpeg render.** `core/reframe.py` grows the render: the
      filter chain, the audio copy, the output name, and the "already
      vertical" and "audio only" skips.

### Checkpoint: Phase 1

- [ ] `ruff check src tests release` clean.
- [ ] The offline suite green.
- [ ] The command file and the filter string are covered by tests that assert
      the exact text.

### Phase 2: the subject

- [ ] **Task 3: the detection.** The YuNet model (MIT) and the NanoDet
      fallback (Apache-2.0) are downloaded into
      `src/s_q_ali_media_downloader/models/`, the detector is written, and the
      subject's centre per sampled frame is produced.
- [ ] **Task 4: the tracker.** The sampled centres become a crop path: pick
      the subject (largest, most central), smooth it, and hold the last
      known position through a frame where nothing was found.

### Checkpoint: Phase 2

- [ ] The offline suite green.
- [ ] A short video goes through detection → path → render and comes out
      1080×1920 with its audio.

### Phase 3: in the app

- [ ] **Task 5: the option.** A checkbox on the download page — "Also make a
      vertical 9:16 version" — and the reframe leg in the download worker,
      after the file is on disk.
- [ ] **Task 6: the packaging.** `opencv-python-headless` moves into the
      runtime requirements, the models are copied into the bundle by the
      PyInstaller spec, and the CI matrix proves the app still starts on all
      four platforms.

### Checkpoint: Phase 3

- [ ] `ruff` clean, the offline suite green, `graphify update .` refreshed.
- [ ] The Windows installer builds and the app starts.

### Phase 4: ship

- [ ] **Task 7:** the README and the CHANGELOG say what the feature does and
      what it costs (time per minute of video, and the ~90 MB the app grows
      by); the version is bumped; the release is tagged.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The subject is lost mid-clip | The camera lags or jumps | The path is smoothed, the last known position is held, and a centre crop is the floor |
| Detection is slow on a long video | A 30-minute clip takes minutes | Sample at ~5 fps and run detection on the smaller of the two axes; the render pass is the real cost and is shown as progress |
| `opencv-python-headless` adds ~90 MB | A bigger download | It is one wheel, it is headless (no GUI libs), and the build is already 1.4 GB |
| The app stops starting on a platform | A broken release | The CI matrix runs the built app on all four platforms, and the reframe is off by default so a missing OpenCV cannot break a download |
| The model files are not in the bundle | The feature silently does nothing | The bundle path is resolved through `sys._MEIPASS`, and the app logs which model it loaded and where |

## Open questions

The three questions in the spec are open: the output size, whether blurred
padding is a second mode, and where the option lives. They are answered
before Task 5 starts, not during it.
