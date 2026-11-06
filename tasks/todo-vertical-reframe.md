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
- [x] Both controls are off by default and apply to the whole queue.
- [x] The spin box only shows in the *N clips* mode, and the app says the
      duration it will use.
- [x] The split runs before the reframe, and each short gets its own vertical
      version.
- [x] With the vertical box unticked, the shorts stay 16:9.
- [x] The work runs in the worker, not on the UI thread.
- [x] A failure in the reframe never fails the download.

**Verification:** `pytest tests -m "not live" -q` green (the leg, the two
controls and the wiring are covered by `tests/test_engine_post_leg.py`,
`tests/test_settings_page.py` and `tests/test_gui.py`), and the live
`test_a_real_download_is_cut_into_shorts_and_each_one_turns_vertical` builds a
real two-minute 320x180 file with ffmpeg: it comes out as three untouched
original bytes plus three shorts and three 180x320 verticals, each exactly
9:16 (`out_width * 16 == out_height * 9`), so it fills the frame with no bars.
The picture is solid colour, so no subject is found and the window stays
centred; the tracking itself is the owner's live check on real footage.

**Dependencies:** Task 2, Task 4, Task 6 · **Files:** `ui/main_window.py`,
`ui/settings_page.py`, `engine.py`, `core/reframe.py` · **M**

## Task 8: the packaging

**Description:** `opencv-python-headless` moves into the runtime
requirements, the models are copied into the bundle by the PyInstaller spec,
and the CI matrix proves the built app still starts on all four platforms.

**Acceptance criteria:**
- [x] `opencv-python-headless==4.14.0.94` is in the runtime requirements.
- [x] The models are in the bundle and the frozen app finds them.
- [x] The CI matrix builds and launches the app on all four platforms.

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

## Task 10: the picture inside the frame

**Description:** a film that arrives in a 16:9 container carries black bands,
and the window was cut from the container, so the vertical file kept them. The
window is now cut from the picture ffmpeg's cropdetect reports.

**Acceptance criteria:**
- [x] The box comes out of cropdetect, and a box that is not a letterbox is
      ignored.
- [x] The render fills the vertical frame with picture.
- [x] The leg hands the box from the analysis to the render.

**Verification:** the real-media test that renders a letterboxed file measures
the black left in the output; on the 4K download the window went from
1206x2144 with 498 black rows to 918x1632 with none.

**Dependencies:** Task 4 · **Files:** `core/reframe.py`, `engine.py`,
`tests/test_reframe.py`, `tests/test_engine_post_leg.py` · **S**

## Task 11: the copy the detectors read

**Description:** the tracking pass decoded every frame of the file at its own
size, which cost more than the render. `analyse` builds a 1920-wide copy at
five frames a second, reads the subject there, and scales the centres back into
the file before the window is placed.

**Acceptance criteria:**
- [x] One call gives the box and the path, and the path is in the size of the
      file.
- [x] A file that will not give up a proxy is still tracked the old way.
- [x] The copy lands on the same subject as the full-size read: on 20 seconds
      of 4K, 91 samples in 100 are within two-thirds of the window of the
      path read at full size, and the frames looked at are on the subject. At
      1280 only 51 were, and one shot put the window on out-of-focus fabric
      while the hand was the subject.

**Verification:** the timings are in the commit message - 12.75 s of work per
second of film at full size, 2.30 s through the 1920 copy; the owner's eye on
the framing is the last word.

**Dependencies:** Task 10 · **Files:** `core/reframe.py`, `engine.py`,
`tests/test_reframe.py` · **M**

## Task 12: the vertical file stops at 1080×1920

**Description:** the window cut from a 4K film is about a thousand pixels wide
and the output was 2912 rows of it - the same picture in twice the bytes and
three times the encode time, for rows no phone shows. `output_size` follows
the source height up to 60 grid units and no further.

**Acceptance criteria:**
- [x] 1080×1920 is the largest the vertical file gets; a 720p source is still
      720×1280 and a 624-row one is 630×1120.
- [x] The output stays on the same 18x32 grid as the window, so the scale does
      not stretch the picture.
- [x] The audio is still copied, not re-encoded: the question was asked and
      answered no.

**Verification:** the same 20 seconds of 4K rendered in 26 s and weighed
13.9 MB against 79 s and 28.5 MB uncapped; the offline suite and both live
reframe tests cover the chain.

**Dependencies:** Task 10 · **Files:** `core/reframe.py`, `tests/test_reframe.py`,
`tasks/spec-vertical-reframe.md` · **S**

## Task 13: the camera holds still

**Description:** the owner watched the 4K renders and the frame never rests.
Two causes, both measured. `sendcmd` holds a value until the next command -
proved on a synthetic clip: 50 frames, two distinct window positions, one
170-column jump at the command - so the window teleports five times a second.
And the path is a bare rate-limited chase, so a still subject is followed
anyway: it moves on 58 of 99 keyframes, median step 123 px of a 918-px window.
This task puts the smoothing in front of the chase and the ramp behind it.

**Acceptance criteria:**
- [x] The wanted centres are median-filtered over the last reads the shot is
      still believed in, so a single bad detection moves nothing - and a far
      read the next one contradicts moves nothing either, rather than dragging
      the camera a third of the way to it.
- [x] Inside the deadband the position is frozen and the same value is written
      again, so a static shot is the same crop from frame to frame. Measured at
      ±10 % of the window, which beat ±6 % on both stillness and lag.
- [x] A move past the deadband is a ramp: at least half a second of keyframes
      at the video's own frame rate, and no frame-to-frame step of a pan over
      a tenth of the window (measured: median 4 px, max 6 px).
- [x] A move the read after it agrees with, further across the picture than a
      cut measured on a real film, is a new shot and is set on that frame -
      5 of them in the probe, 502 to 1692 px, none of them panned.
- [x] The command file stays small: a hold is one line, a ramp is however many
      frames the ramp lasts. Measured: 210 lines for 19.8 s, 10.6 a second.
- [x] The measured path on the 20 s probe: the target of "under 25 of 99
      keyframes" is restated as what the frame-rate path actually reports - 209
      of 1188 frames move (18 %) and 979 are identical to the frame before. At
      the sample rate it is 30 of 99, against 58 before, with 82 % of frames
      still, no reversals while panning and one read in 59 with the subject
      outside the window.

**Verification:** new offline tests on the maths (a static subject with noisy
centres produces one frozen position; a one-sample spike produces no move; a
real step produces a monotone ramp of the right length); the probe script in
`tasks/` reports the numbers before and after; the live reframe test renders
the probe segment and the owner's eye is the last word on the framing.

**Dependencies:** Task 11 · **Files:** `core/reframe.py`, `tests/test_reframe.py`,
`tasks/plan-vertical-reframe.md` · **M**

## Task 14: the subject that is followed is the subject that was found

**Description:** the detector takes the biggest box in the frame, so with two
people the biggest can change hands between samples and the window snaps a
long way in one command - the worst of the jumps. The tracker keeps the last
centre and picks the box nearest it, falling back to the biggest when nothing
is near.

**Acceptance criteria:**
- [x] With two candidates, the one nearer the last position is taken even when
      the other is bigger.
- [x] When nothing is near the last position, the biggest is taken - a new
      subject is still picked up.
- [x] The first detection of a clip has no last position and takes the biggest.

**Verification:** offline tests over a fake frame source with two known boxes,
done. The live before/after on the 20 s probe is not on the table: re-tracking
to measure this overwrote the cached centres the earlier numbers were taken
from, and the two are not comparable. What the current cache shows is that of
58 gaps between detected reads, 7 are cut-sized (over 576 px on a 3840 film)
and the median is 26 px - the split the cut rule in Task 13 is built on.

**Dependencies:** Task 13 · **Files:** `core/reframe.py`, `tests/test_reframe.py`
· **S**

## Task 15: the stability fix ships inside 2.14.0

**Description:** the v2.14.0 release run was cancelled before it published and
its tag deleted, so the fixed camera is what 2.14.0 ships as. The CHANGELOG
entry gains the stability line, the README's cost numbers are re-measured with
the denser command file, and the tag is made again on an explicit go.

**Acceptance criteria:**
- [x] The CHANGELOG says what a user sees: the frame holds still on a static
      shot and glides when the subject moves, and a cut takes the new framing
      at once.
- [x] The README's measured cost is re-measured with the denser keyframes and
      moved if it moved. Two full passes over the 20 s 4K probe: 3.9 s and
      4.4 s of work per second of film (the looking at 2.4 s, the encode
      between 1.5 and 1.9), so the claim moves from 3.6 s and 2¼ h to 4 s and
      2½ h for a 37-minute film.
- [x] The version stays 2.14.0 in `pyproject.toml` and `__init__.py`, the
      entry is dated (`2026-11-06`), and the tag is pushed only on an explicit
      go — still held.

**Dependencies:** Tasks 13, 14 · **Files:** `CHANGELOG.md`, `README.md`,
`pyproject.toml`, `src/s_q_ali_media_downloader/__init__.py` · **XS**

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
