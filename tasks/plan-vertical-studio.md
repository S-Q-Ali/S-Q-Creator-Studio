# Implementation Plan: the Vertical Studio section

Spec: `tasks/spec-vertical-studio.md`. Tasks: `tasks/todo-vertical-studio.md`.

## Dependency graph

```
run_post_leg (the two legs, lifted out of DownloadThread)
    ├── duration_seconds (the split needs a length; the download had one from yt-dlp)
    └── LocalVideoThread (a worker over local paths)
            └── VerticalStudioPage (drop zone, list, controls, Run/Stop)
                    └── MainWindow nav (the fifth button and page)
```

Bottom-up: the shared function first, because everything else calls it and
the download flow has to keep working while it moves.

## Architecture decisions

- **One implementation, two callers.** `_post_leg`, `_split_leg` and
  `_vertical_leg` (`engine.py:1193-1271`) become module-level functions that
  take the paths, the options, the ffmpeg binary and a `report` callback
  instead of reading `self.vertical` / emitting `self.log`. `DownloadThread`
  keeps three-line methods that call them. A duplicated copy of that logic
  in the new page would be the bug: two places to fix when the camera moves.
- **The file is the truth for its length.** The download leg got `duration`
  from the yt-dlp info dict. A local file has no info dict, so
  `reframe.duration_seconds(path)` reads frame count over frame rate out of
  the `cv2.VideoCapture` that `frame_size` already opens (`reframe.py:460`).
  No ffprobe path, no new dependency.
- **Serial by default.** The reframe costs about 4 s of work per second of
  film; two files at once only make both slower. One `LocalVideoThread`,
  files in drop order, one progress line at a time.
- **The page holds its own run options.** It seeds the vertical checkbox,
  the split dropdown and the clips spin box from the saved settings
  (`settings_page.py:555-559` reads the same keys) and writes nothing back —
  no new settings keys, and the download defaults stay where they are.
- **Stop finishes the file in hand.** The same rule the download worker
  already lives by: a job whose file is on disk is never cancelled mid-write.

## Order and checkpoints

Phase A (engine, Tasks 1-2) is the risky half and goes first: if the lift
breaks the download flow, everything after it is built on a broken base.
Checkpoint A: the post-leg tests green with the recorders, offline suite
green, and the Windows download flow still making a vertical file.

Phase B (Tasks 3-5) is the app-facing half. Checkpoint B: drop two files in
an offscreen test, fake the legs, assert the run reports and skips;
`MainWindow` still builds and the new section is reachable by keyboard.

Phase C (Task 6) is the docs and the version. Checkpoint C: README states
what the section does and what it costs, CHANGELOG has the 2.15.0 entry,
`ruff` clean, offline suite green, `graphify update .`.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Lifting `_post_leg` changes download behaviour unnoticed | A shipped feature regresses | `tests/test_engine_post_leg.py` already drives the real methods with recorders (line 28); it runs against the moved function with the same expectations, unchanged |
| A dropped path is a network share, a huge file, or a folder | The run hangs or the app looks dead | Only suffix-matching regular files get in; the work is in a QThread; the log names the file being worked on |
| The drop zone swallows a drop meant for the queue page | Confusion about what a drop does | Drops are accepted only while this section is the visible page |
| OpenCV cannot open the container (e.g. an .mkv codec it lacks) | Silent nothing | `frame_size` returning 0 is already the "no picture to reframe" sentence — reused, plus the run moves to the next file |

## Out of scope (named, not hidden)

- Right-clicking a finished job in the Download Queue to reframe it later
  (the same function would serve it; it is a second entry point, not a
  second feature).
- Choosing an output folder, a target height above the 1080×1920 cap, or
  per-file options.
- Batch parallelism.
