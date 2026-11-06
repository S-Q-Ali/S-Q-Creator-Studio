# Spec: the Vertical Studio section (a local file, reframed)

## Objective

The 9:16 reframe and the shorts split today only run as the tail of a
download (`engine.py:1193` `_post_leg`). A file the app did not download —
one from a phone, one from the edits folder, one downloaded last week —
cannot be reframed without re-downloading it.

This adds a fifth section to the window: drop videos onto it (or browse to
them), choose vertical and/or a shorts mode, press Run, and the app does the
two passes it already knows how to do on each file in turn. Outputs land
beside the source, exactly as in the download flow, and the source is never
touched.

Success looks like: three files dropped in, one already vertical, one not a
video — the run says so, makes a `_9x16.mp4` beside each of the two it can,
and the app stays responsive the whole time.

## Tech Stack

PySide6 6.11 desktop app, Python 3.12/3.14. The reframe maths is
`core/reframe.py` (OpenCV + ffmpeg), the splitting is `core/shorts.py`. No
new dependency: `cv2` is already bundled and already reads any local file
(`reframe.frame_size`, `reframe.py:460`).

## Commands

```
Test:   QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -m "not live" -q -p no:warnings
Lint:   ./source/venv/Scripts/python.exe -m ruff check src tests release --output-format concise
Run:    ./source/venv/Scripts/python.exe -m s_q_ali_media_downloader
Build:  ./source/venv/Scripts/python.exe release/build.py
```

## Project Structure

```
src/s_q_ali_media_downloader/ui/vertical_studio_page.py  → the new page (drop zone, list, controls)
src/s_q_ali_media_downloader/ui/main_window.py           → one nav button, one addWidget
src/s_q_ali_media_downloader/engine.py                   → the legs as one shared function + a worker over local files
src/s_q_ali_media_downloader/core/reframe.py             → duration of a local file (the split needs it)
tests/test_vertical_studio_page.py                       → drop, browse, run, skip
tests/test_engine_post_leg.py                            → the shared function, both callers
```

## Code Style

The legs move, they do not get rewritten — one implementation, two callers:

```python
def run_post_leg(path, *, vertical, split, clips, ffmpeg, duration, report):
    """The shorts and the vertical versions of one file that is already on
    disk. Nothing here raises: a step that fails says why and moves on."""
```

`report` is a callback the caller supplies (`log.emit` in the download
thread, the page's log line in the new one) so the function needs no signals
of its own. Page widgets follow `music_page.py`: a `QWidget` subclass, a
`_build` that lays out, properties on the controls, hints in tooltips.

## Testing Strategy

pytest, offline only (`-m "not live"`), `tests/conftest.py` already forces
`QT_QPA_PLATFORM=offscreen` and a session `qapp`.

- The shared leg function: monkeypatched `reframe`/`shorts` recorders, the
  pattern in `tests/test_engine_post_leg.py:28` — proves the download flow
  behaves identically after the move and that a failing step reports instead
  of raising.
- The page: a synthesized `QMimeData` drop and a monkeypatched
  `QFileDialog.getOpenFileNames` prove files get in; the worker is faked, so
  no ffmpeg and no OpenCV run.
- One offscreen smoke test builds `MainWindow` and switches to the new
  section — the `test_gui.py:22` pattern.

## Boundaries

- Always: the source file is opened read-only and never rewritten; every
  step logs what it did; a bad file skips, it does not stop the run; the
  offline suite and `ruff` are green before the commit.
- Ask first: a new dependency, a new settings key, changing what the download
  flow does.
- Never: a password or cookie anywhere near this path; no network call from
  this page; no half-written output claimed as done.

## Success Criteria

- A video file from anywhere on disk — not downloaded by the app — comes out
  as `<name>_9x16.mp4` beside it, tracked by the same camera that shipped in
  2.14.0.
- Dropping three files and pressing Run processes them one after another with
  a progress line for the current one, and Stop ends the run after the file
  in hand.
- The Shorts dropdown and clips spin box on this page do what the same two
  controls do after a download.
- A non-video, an unreadable file and an already-vertical video each get one
  plain sentence and are skipped.
- The download flow is unchanged in behaviour: the same function runs its
  post-download legs.

## Open Questions

1. Section label — "Vertical Studio"? ("Video Tools", "Shorts & Vertical"
   also fit the existing nav vocabulary.)
2. Does one file at a time (the current plan) hurt, or is a real queue with
   per-file rows wanted now rather than later?
3. Ship as 2.15.0 after the `v2.14.0` tag move, or hold 2.14.0 and fold this
   into it?
