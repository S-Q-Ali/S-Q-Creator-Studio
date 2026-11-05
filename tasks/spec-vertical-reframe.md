# Spec: vertical 9:16 with subject tracking

## Objective

**What:** Turn a landscape (16:9) download into a vertical (9:16) video that
follows the person in the frame, so a two-minute YouTube video becomes a
TikTok/Reel/Shorts clip without the subject being cut out of the picture.

**Who:** the app's user, who already downloads a creator's videos and wants
the same content in vertical form for short-form platforms.

**Success looks like:** a downloaded landscape video also lands as
`<name>_9x16.mp4`, 1080×1920, in which the speaker stays centred through the
clip, with the original audio intact.

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
  `sendcmd` → `crop@c` → `scale=1080:1920` → `setsar=1`, audio copied.
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

## Commands

- Tests: `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -m "not live" -q`
- Lint: `./source/venv/Scripts/python.exe -m ruff check src tests release --output-format concise`
- Graph: `graphify update .`
- The reframe itself (worker thread): the app's own ffmpeg, found by
  `engine.find_ffmpeg()`.

## Project structure

```
src/s_q_ali_media_downloader/core/reframe.py     ← new: detection, tracking, crop path
src/s_q_ali_media_downloader/engine.py           ← the post-download reframe leg
src/s_q_ali_media_downloader/ui/main_window.py   ← the option in the UI
src/s_q_ali_media_downloader/ui/widgets.py       ← nothing
tests/test_reframe.py                            ← new: the crop path and the command
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
  file that `sendcmd` reads, the "already vertical / audio only" skips, and
  the ffmpeg filter string.
- **Integration** (marked `live`, off by default): one real video through
  detection → crop path → ffmpeg, asserting the output is 1080×1920 and
  carries the original audio.
- **Manual** (the owner's machine): a two-minute talking-head video — the
  subject must stay in frame from the first second to the last.

## Boundaries

- **Always:** keep the original file; write the vertical one beside it as
  `<name>_9x16.mp4`; fall back to a centre crop when no subject is found;
  never touch the audio.
- **Ask first:** adding `opencv-python-headless` to the runtime requirements
  (it adds ~90 MB to the shipped app); publishing a release; writing to the
  public tracker.
- **Never:** ship AGPL weights; make the reframe mandatory; delete the
  landscape original.

## Success criteria

- [ ] A landscape download also produces a 1080×1920 file with the audio
      intact.
- [ ] The subject stays inside the crop window for a talking-head video.
- [ ] A video with no detectable person still gets a centred 9:16 version.
- [ ] A video that is already vertical is left alone.
- [ ] The feature is off by default and can be turned on for the whole
      queue.
- [ ] The app still builds and runs on Windows, macOS Intel, macOS Apple
      Silicon and Linux.

## Open questions

- **Output size:** the vertical file is 1080×1920 always, or the source
  height × 9/16 (a 720p source gives 720×1280)? The second keeps the file
  small and the quality honest.
- **Padding mode:** a hard crop loses the sides; a blurred background keeps
  the whole frame but crops nothing. Should blurred padding be a second
  option? It costs one extra ffmpeg branch and a second render.
- **Where the option lives:** one checkbox on the download page, or a
  per-job setting on the queue card?
