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
- **The crop path is sampled at 5 fps and written one line per sample.** What
  it does *between* samples was assumed - ffmpeg's `sendcmd` holds a value
  until the next command, it does not interpolate, so this premise was wrong
  and Phase 7 is the correction.
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
- **The window travels at most half its own width in a second, and never less
  than half a second to a new framing.** The movement is bounded rather than
  smoothed with an EMA, so no glide is a snap and none is a blur. It was once
  the only stabiliser in the shipped path, which is why the path still
  crawled: a bound is not a filter. Phase 7 keeps it as the ceiling of a
  glide, and takes the glide off anything that measures as a cut.
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

## Phase 7: the camera holds still (2.14.1)

The owner watched the 4K renders and the window never rests: it crawls and
twitches on static shots. Measured on 20 s of the same film (3840×2160,
picture 1646 rows, window 918 px wide, 100 samples at 5 fps):

| Path | moves | still | median step | max step | reversals/s | travel/s |
|---|---|---|---|---|---|---|
| what ships today (chase at ¼ window per sample) | 58/99 | 41 % | 123 px (13 % of window) | 228 px | 0.81 | 368 px/s |
| median 5 + low-pass α=0.1 | 57/99 | 42 % | 48 px | 162 px | 0.30 | 165 px/s |
| median 5 + low-pass + deadband 0.08 | 41/99 | 59 % | **228 px** | 228 px | 0.30 | 374 px/s |

Three things the table says:

1. **The steps are the twitch.** `sendcmd` values hold until the next command —
   ffmpeg does not interpolate them (`crop` is not among the filters that
   accept `slerp`/`lerp`). One keyframe per 0.2 s therefore means the window
   *teleports* up to 228 px, five times a second. The plan's original
   assumption that "between samples the window moves linearly" is false, and
   it is the main defect.
2. **The chase has no floor.** With only a rate limit and no filter, a subject
   that stands still is chased anyway, because YuNet's box centre moves a few
   pixels every sample and the window follows it forever.
3. **A deadband alone makes it worse.** Holding until the target is outside the
   band and then chasing at the old rate turns small crawls into 228-px snaps.
   A deadband is only safe once the move it releases is a *glide*, not a step.

### Decisions

- **Keyframes are written at the frame rate, not the detection rate.** The
  detection stays at 5 fps (it is the expensive half); the path between two
  detections is a ramp, emitted as one command per frame the ramp lasts. A
  stretch where the window does not move emits one line, so the file stays
  small: 210 lines for the 20 s probe, 10.6 for each second of film, against
  one a frame at 60.
- **Median 5, then a low-pass, then a deadband, then a glide.** The shipped
  filter is the fixed α=0.35 low-pass, not the adaptive one-Euro of Casiez et
  al. 2012: the adaptive cutoff was the idea worth stealing, and a fixed α
  measured the same stillness for a third of the code.
- **A cut is not a pan.** The first version panned everything, and the
  measurement said the model was wrong: between two samples inside a shot the
  subject moves a median of 17 px, and a thousand at a cut. A 576 px glide
  across a cut takes two seconds, so the camera spends most of the film
  crossing cuts and never settles. Two reads more than `CUT_RATIO` of the
  source apart, when the read after them agrees, are a new shot: the window is
  set to the new framing on that frame and the median starts again. A read the
  next one contradicts is a bad detection and moves nothing at all.
- **The deadband is ±10 % of the window, not ±6 %.** Swept on the probe at
  fixed cut and α: 6 % left 72 % of frames still and 3 samples with the
  subject outside the window, 10 % left 82 % still and 1, for a lag that grew
  by two pixels. A tenth of the window is still a subject in the middle of a
  9:16 frame.
- **The subject is sticky.** `SubjectDetector` today takes the biggest box in
  the frame, so with two people the biggest can change hands between samples
  and the camera snaps across the shot. The tracker keeps the last centre and
  takes the box nearest it (score-gated, with the biggest box as the fallback
  when nothing is near). This is ordinary nearest-neighbour association, not a
  new model, and it is likely the source of the largest single jumps.
- **Rejected: a DP crop path (smart-crop / VideoReforge) and optical-flow
  tracking.** The DP formulation scores every candidate window at every frame
  — that is the cost the proxy was introduced to avoid; flow tracking adds a
  per-frame tracker that drifts and must be re-seeded. Both are better tools
  for a product whose whole job is reframing; here they are more machine than
  the feature is worth.
- **The v2.14.0 tag is held, not patched over.** The release run was cancelled
  before it published anything and the tag is deleted, so the fix lands inside
  2.14.0 and no one ever gets the stepped camera. The CHANGELOG entry gains the
  stability line instead of a new release gaining one.

### Measured, after

The same 20 s of the same film, the path the module now writes:

| | what ships today | now |
|---|---|---|
| keyframes | one per 0.2 s | 1189 for 19.8 s (one a frame) |
| frames identical to the one before | — | **979 of 1188 = 82 %** |
| a pan step | 123 px median, 228 px max (a teleport) | 4 px median, 6 px max |
| reversals a second while moving | 0.81 | 0.00 |
| travel while panning | 368 px/s | 36 px/s |
| cuts | panned, 2-4 s each | 5 set at once: 502-1692 px in one frame |
| samples in a run of three with the window in one place | — | 24 of 59 |
| lag from the subject, median / p90 | — | 117 px / 329 px (window 918) |
| reads with the subject outside the window | — | 1 of 59 |
| command file | one line per sample | 210 lines, 10.6 per second of film |

The one remaining lost read is the 8.8 s sample the next read contradicts: the
camera holds the framing it had, which is the rule working as designed rather
than a defect - the alternative is a 1833 px snap to whichever detection is
right, and the detector cannot tell from one read.


## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The subject is lost mid-clip | The camera lags or jumps | The path is smoothed, the last known position is held, and a centre crop is the floor |
| Detection is slow on a long video | A 30-minute clip takes minutes | Measured on a 4K download: 12.75 s of work per s of film tracking the file itself, against 4.2 s through the 1920-wide five-frame copy and the render at the 1080×1920 cap — 2½ h for a 37.6-minute film against 10½ h before both changes. The two runs gave 3.9 s and 4.4 s, the looking half steady at 2.4 s and the encode between 1.5 and 1.9. The render is shown as progress |
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
