# Plan: vertical 9:16 with subject tracking, and long-form into shorts

## Overview

A downloaded landscape video is turned into vertical clips whose crop window
follows the person in the frame, and a long video is cut into shorts first if
the user asks for it. Three passes, all after the download, all in the worker
thread:

```
original.mp4
   │
   ├─ (split)      → short01.mp4 … shortNN.mp4        ← ffmpeg, at a pause
   │
   └─ (reframe)    → short01_9x16.mp4 … 9x16.mp4      ← detect, track, crop
```

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
  between samples the window moves linearly, and the value is smoothed so the
  camera does not jitter.
- **The detectors read a copy, not the file.** A 1920-wide, five-frame-per-
  second copy of the film costs a fifth of what the file itself costs to
  decode. It cannot be much smaller: measured on a 4K download, a 1280-wide
  copy put the window more than half a window away from the full-size path on
  49 samples in 100, and 1920 on 9. The centres are scaled back and the window
  is placed in the size of the file, so the smoothing limit and the edges are
  still the file's own.
- **The vertical file stops at 1080×1920.** The first choice was the source
  height × 9/16, which on a 4K download means 2912 rows out of a window a
  thousand pixels wide: the same picture in four times the bytes and four
  times the encode time. Below full HD the height still follows the source.
- **The window is cut from the picture, not the container.** A film that
  arrives in a 16:9 file carries black bands, and a window cut from the
  container keeps them: the point of the feature is a frame that is full.
  ffmpeg's `cropdetect` says where the picture is, and it is cheap. A box less
  than half the frame is not a letterbox and the whole frame is cut instead.
- **The crop window is 9:16 to the pixel.** A 1920×1080 source is cut to
  594×1056 - the largest whole 16-row band that keeps the ratio exact - and
  scaled to 1080×1920. A window of 608×1080 would be 0.08% off the ratio and
  the scale would stretch the picture by that much.
- **The window may only travel a quarter of its width per sample.** The
  movement is bounded rather than smoothed with an EMA, so a detection that
  jumps cannot snap the camera no matter how the smoothing is tuned.
- **Cut points come from silence first, scene change second.** A short that
  ends in the middle of a sentence is worse than one that is a few seconds
  off its target length, so `silencedetect` is asked first and the scene
  score is the fallback.
- **The *N clips* mode recommends, it does not decide.** The app says the
  duration it would use — and says when that duration is over a platform's
  limit — and the user picks the number of clips.
- **The original is never touched.** Everything new is written beside it.
- **A centre crop is the floor.** If no subject is found at all, the video
  still gets a centred 9:16 version — the feature never fails a download.

## Task list

### Phase 1: the pure part

- [x] **Task 1: the crop path.** `core/reframe.py` grows the maths: the crop
      width for a source, the clamp to the frame, the smoothing, and the
      `sendcmd` command file. Pure functions, no model, no ffmpeg.
- [x] **Task 2: the ffmpeg render.** `core/reframe.py` grows the render: the
      filter chain, the audio copy, the output name, and the "already
      vertical" and "audio only" skips.

### Checkpoint: Phase 1

- [x] `ruff check src tests release` clean.
- [x] The offline suite green.
- [x] The command file and the filter string are covered by tests that assert
      the exact text.

### Phase 2: the subject

- [x] **Task 3: the detection.** The YuNet model (MIT) and the NanoDet
      fallback (Apache-2.0) are downloaded into
      `src/s_q_ali_media_downloader/models/`, the detector is written, and the
      subject's centre per sampled frame is produced.
- [x] **Task 4: the tracker.** The sampled centres become a crop path: pick
      the subject (largest, most central), smooth it, and hold the last
      known position through a frame where nothing was found.

### Checkpoint: Phase 2

- [x] The offline suite green.
- [x] A short video goes through detection → path → render and comes out
      9:16 with its audio.

### Phase 3: the split

- [x] **Task 5: the cut points.** `core/shorts.py` finds the pauses
      (`silencedetect`) and the scene changes, and picks the cut points that
      land nearest each target length. The *N clips* mode divides the
      duration by the clip count, moves each boundary to the nearest pause,
      and reports the duration it will use — including when that duration is
      over YouTube Shorts' 3-minute limit.
- [x] **Task 6: the split.** `core/shorts.py` cuts the video into the
      segments with one ffmpeg pass per short, keeping the audio.

### Checkpoint: Phase 3

- [x] The offline suite green.
- [ ] A two-minute video splits into three shorts, none of them cut in the
      middle of a sentence. (The live test cuts at the detected pauses; the
      listening check on real speech is the owner's.)

### Phase 4: in the app

- [x] **Task 7: the two controls.** A checkbox on the download page — "Also
      make a vertical 9:16 version" — and the dropdown beside it — "Split
      into shorts" (Off, Auto, 30 s, 45 s, 60 s, 90 s, *N clips*) with a
      spin box for the clip count, and the post-download leg in the worker
      that runs the split, then the reframe on each piece.
- [x] **Task 8: the packaging.** `opencv-python-headless` moves into the
      runtime requirements, the models are copied into the bundle by the
      PyInstaller spec, and the CI matrix proves the app still starts on all
      four platforms.

### Checkpoint: Phase 4

- [x] `ruff` clean, the offline suite green, `graphify update .` refreshed.
- [ ] The Windows installer builds and the app starts.

### Phase 5: on real film

The first run of the feature was on a 37.6-minute 4K download, and it found
two things the synthetic tests could not.

- [x] **Task 10: the picture inside the frame.** The film is 2.33:1 inside a
      16:9 container, so the window cut from the container carried 498 rows of
      black. It is cut from the picture `cropdetect` reports instead.
- [x] **Task 11: the copy the detectors read.** Tracking every frame of the
      file at 3840×2160 cost more than the render. `analyse` tracks a
      1920-wide, five-frame copy and scales the centres back.
- [x] **Task 12: the file stops at 1080×1920.** The window cut from a 4K film
      is a thousand pixels wide; the output was 2912 rows of it. Capped, the
      same 20 seconds render in 26 s instead of 79 and weigh 13.9 MB instead
      of 28.5.

### Checkpoint: Phase 5

- [x] The offline suite green, and the real-media test measures what is left of
      the vertical file after the bands are cut out: nothing.

### Phase 6: ship

- [ ] **Task 9:** the README and the CHANGELOG say what the feature does and
      what it costs (time per minute of video, and the ~90 MB the app grows
      by); the version is bumped; the release is tagged.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The subject is lost mid-clip | The camera lags or jumps | The path is smoothed, the last known position is held, and a centre crop is the floor |
| Detection is slow on a long video | A 30-minute clip takes minutes | Measured on a 4K download: 12.75 s of work per s of film tracking the file, 2.30 s through the 1920-wide five-frame copy, and 1.29 s for the render at the 1080×1920 cap - 2¼ h for a 37.6-minute film against 10½ h before both changes. The render is shown as progress |
| `opencv-python-headless` adds ~90 MB | A bigger download | It is one wheel, it is headless (no GUI libs), and the build is already 1.4 GB |
| The app stops starting on a platform | A broken release | The CI matrix runs the built app on all four platforms, and the feature is off by default so a missing OpenCV cannot break a download |
| A short ends mid-sentence | An unusable clip | Silence is asked for first; the scene change is the fallback |
| The model files are not in the bundle | The feature silently does nothing | The bundle path is resolved through `sys._MEIPASS`, and the app logs which model it loaded and where |

## Open questions

Both are answered, and the answers are in the shipped code.

- **The naming of the short files:** `<stem>_short01.mp4`, `<stem>_short02.mp4`
  beside the original, and the vertical of each one `<stem>_short01_9x16.mp4`.
- **A trailing short shorter than half the target:** kept. The clips cover the
  whole video end to end, so nothing is silently thrown away, and the note the
  app shows names the shortest and the longest planned length before it cuts.
