# Spec: vertical 9:16 with subject tracking, and long-form into shorts

## Objective

**What:** turn a landscape (16:9) download into vertical (9:16) clips that
follow the person in the frame, and cut a long video into shorts — the two
together are what a creator actually publishes.

**Who:** the app's user, who downloads a creator's videos and wants the same
content in short-form form for TikTok, Reels and Shorts.

**Success looks like:** a downloaded 4-minute landscape video also lands as
vertical shorts, 1080×1920, in which the speaker stays centred from the
first second to the last, each short cut at a natural pause.

## Expected output (what the user actually gets)

Input — one download, `How to cook.mp4`, 1920×1080, 4:12, with audio, in the
download folder.

**Vertical only** (the "Also make a vertical 9:16 version" box ticked):

```
How to cook.mp4            1920×1080   4:12   ← original, untouched
How to cook_9x16.mp4        608×1080 → 1080×1920   4:12   ← new
```

- The output height follows the source: a 1080p source gives 1080×1920, a
  720p source gives 720×1280. Nothing is upscaled to look better than it is.
- The audio is the original track, copied — not re-encoded, so it does not
  drift and it is not degraded.
- The crop window follows the subject: it moves when the speaker moves, it
  never jumps, and it is centred when nothing is found.

**With shorts split** (the dropdown set to 60 s):

```
How to cook.mp4                    1920×1080   4:12   ← original, untouched
How to cook_short01_9x16.mp4        1080×1920   0:58
How to cook_short02_9x16.mp4        1080×1920   0:59
How to cook_short03_9x16.mp4        1080×1920   1:04
How to cook_short04_9x16.mp4        1080×1920   1:11
How to cook_short05_9x16.mp4        1080×1920   1:00
```

- Each short is cut at a natural pause — a silence in the speech, or a
  change of scene — never in the middle of a sentence.
- Each short is then reframed to 9:16 with the subject tracked, so the
  shorts are vertical as well as the long version.
- With the vertical box unticked, the shorts are 16:9 and keep the original
  shape.

## The problem, stated honestly

A hard centre crop of a 16:9 frame into 9:16 keeps 56% of the width. If the
subject is not standing in the middle, the crop cuts them in half or cuts them
out. "Follow the subject" therefore means: find the person in each frame,
keep them inside the crop window, and move the window as they move.

## Tech stack

- **Detection:** OpenCV's DNN module (`opencv-python-headless`, pinned
  `4.14.0.94`) with **YuNet** (MIT, 233 KB) for faces, falling back to
  **NanoDet-Plus-S int8** (Apache-2.0, 1.0 MB) for full-body shots.
- **Tracking:** a small EMA/centroid tracker written in the app, not a
  separate library — OpenCV's CSRT tracker lives in `opencv-contrib`, which is
  a bigger dependency for one algorithm.
- **Rendering:** the ffmpeg the app already ships.
  `sendcmd` → `crop@c` → `scale` → `setsar=1`, audio copied.
- **Splitting:** ffmpeg only — `silencedetect` and the `scene` score for the
  cut points, then one `-ss`/`-t` pass per short.
- **Licence:** all Apache-2.0 or MIT. **Ultralytics YOLO is AGPL-3.0 and is
  not used** — the app ships closed.

### Why not the alternatives (researched, not guessed)

| Option | Why not |
|---|---|
| Ultralytics YOLO | AGPL-3.0 weights; no macOS Intel wheels for torch |
| MediaPipe Tasks | no macOS Intel wheel at all |
| ONNX Runtime | no macOS Intel wheel (stops at cp313) |
| `cv2` HOG people detector | too coarse to keep a person centred |
| Chromium / onnxruntime-web | strictly worse than native Python in a desktop app |
| ffmpeg `cropdetect` | finds black bars, has no idea what the subject is |

`opencv-python-headless` is the only one of these with wheels for **Windows
x86_64, macOS Intel + Apple Silicon and Linux x86_64** on Python 3.14.

## The controls

Two, both on the download page, both applying to the whole queue:

| Control | Values | Default |
|---|---|---|
| "Also make a vertical 9:16 version" | on / off | off |
| "Split into shorts" | Off · 30 s · 45 s · 60 s · 90 s · Auto (scene changes) | Off |

`Auto` cuts wherever the scene changes, with no target length.

## Commands

- Tests: `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -m "not live" -q`
- Lint: `./source/venv/Scripts/python.exe -m ruff check src tests release --output-format concise`
- Graph: `graphify update .`
- The reframe and the split: the app's own ffmpeg, found by
  `engine.find_ffmpeg()`.

## Project structure

```
src/s_q_ali_media_downloader/core/reframe.py     ← new: detection, tracking, crop path
src/s_q_ali_media_downloader/core/shorts.py      ← new: the cut points and the split
src/s_q_ali_media_downloader/engine.py           ← the post-download leg
src/s_q_ali_media_downloader/ui/main_window.py   ← the two controls
tests/test_reframe.py                            ← new: the crop path and the command
tests/test_shorts.py                             ← new: the cut points
```

Model files live in `src/s_q_ali_media_downloader/models/` and are copied into
the bundle by the PyInstaller spec as data.

## Code style

```python
def crop_path(points, width, crop_width):
    """The x of the crop window per sampled frame, clamped to the frame."""
    limit = max(0, width - crop_width)
    return [max(0, min(limit, int(round(x)))) for x in points]
```

One idea per function, no classes where a function does, and a comment only
where the *why* is not in the code.

## Testing strategy

- **Unit** (fast, no model): the crop-path maths, the clamping, the command
  file that `sendcmd` reads, the cut-point choice, the "already vertical" and
  "audio only" skips, and the ffmpeg filter strings.
- **Integration** (marked `live`, off by default): one real video through
  detection → crop path → ffmpeg, and one through the split, asserting the
  output sizes and the audio.
- **Manual** (the owner's machine): a two-minute talking-head video — the
  subject must stay in frame from the first second to the last, and the
  shorts must not cut mid-sentence.

## Boundaries

- **Always:** keep the original file; write the new files beside it with
  clear names; fall back to a centred crop when no subject is found; never
  touch the audio of the original; never cut in the middle of a detected
  speech.
- **Ask first:** adding `opencv-python-headless` to the runtime requirements
  (it adds ~90 MB to the shipped app); publishing a release; writing to the
  public tracker.
- **Never:** ship AGPL weights; make the reframe mandatory; delete the
  landscape original; overwrite a file the user already had.

## Success criteria

- [ ] A landscape download also produces a vertical file at the source's
      height × 9/16, with the original audio.
- [ ] The subject stays inside the crop window for a talking-head video.
- [ ] A video with no detectable person still gets a centred 9:16 version.
- [ ] A video that is already vertical is left alone.
- [ ] The dropdown cuts a long video into shorts of the chosen length, at a
      pause where one is near.
- [ ] Both features are off by default and apply to the whole queue.
- [ ] The app still builds and runs on Windows, macOS Intel, macOS Apple
      Silicon and Linux.

## Open questions

- **The naming of the short files.** `_short01_` follows the long file's
  name; `_short_01_` would sort the same. Nothing depends on it.
- **Whether a short that is shorter than half the target is dropped.** A
  4-second leftover at the end of a 60-second split is usually noise.
