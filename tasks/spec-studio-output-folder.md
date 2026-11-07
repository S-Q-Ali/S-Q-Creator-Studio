# Spec: choosing where the Studio results are saved

## Objective

The Vertical Studio has no say about where its outputs go. Every `_9x16.mp4`
and every `_shortNN.mp4` lands beside the source file
(`core/reframe.py:221` `vertical_output_path`, `core/shorts.py:350`
`split_video` destinations), so a video dropped from the Desktop or an edits
folder leaves its results in the Desktop or the edits folder, mixed in with
the originals and the user's own work.

This adds one control to the Studio: a results folder the owner picks. With
it set, every file in the run writes its results into that folder; left
empty, the behaviour is today's — beside each source.

Success looks like: set the folder once, run three files, find three
verticals and their shorts in that folder and nothing new beside the sources;
clear the folder, run again, and the results are back beside each file.

## What is in scope

- The Studio run only: the two products of `engine.run_post_leg` when the
  caller is `LocalVideoThread` (`engine.py:1583`).
- The download tail (`engine.py:1380` `_post_leg`) is not touched. A download
  already lands in the folder the user chose on the Settings page, and its
  results beside it, so it already has an answer to "where".

## Decided with the owner (2026-11-07)

1. **Studio only.** The download tail keeps writing beside the download; its
   folder is already the one the user chose on the Settings page.
2. **Collision → a new name, never an overwrite.** Decided as
   `name (2).mp4` for the copy of the source, through `engine.unique_basename`.
   The outputs needed a rule of their own, and the first cut of this feature
   did not give them one — see findings 1 and 2 of
   [audit-vertical-studio.md](audit-vertical-studio.md). Both legs now name
   through [core/output_names.py](../src/s_q_ali_media_downloader/core/output_names.py):
   the vertical takes the next free `<stem>_9x16 Part N.mp4`, and the shorts
   number their pieces `<stem> Part N.mp4` from one past the highest on disk.
3. **Everything the folder, nothing beside the source.** When the folder is
   set, the run copies the source into it and works on the copy, so the
   folder holds the file, its `_9x16.mp4` and its shorts together. The
   original is read, never modified.
   - **The cost of this choice: the source occupies disk twice** — a 6 GB
     film means 6 GB of copy plus its results. It is the whole reason
     "beside each file" stays available as the default (empty field).
   - A source that already lives inside the chosen folder is not copied; the
     run works on it where it is.

## Tech Stack

PySide6 6.11 desktop app, Python 3.12/3.14. No new dependency: the pieces are
already in the repo — `engine.unique_basename` (`engine.py:775`) for names,
`QFileDialog.getExistingDirectory` for the picker, `make_settings()`
(`ui/settings_page.py:128`) for persistence.

## Commands

```
Test:   QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -m "not live" -q -p no:warnings
Focused: QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_vertical_studio_page.py tests/test_engine_post_leg.py -m "not live" -q -p no:warnings
Lint:   ./source/venv/Scripts/python.exe -m ruff check src tests release --output-format concise
Run:    ./source/venv/Scripts/python.exe -m s_q_ali_media_downloader
Build:  ./source/venv/Scripts/python.exe release/build.py
```

## Project Structure

```
src/s_q_ali_media_downloader/ui/vertical_studio_page.py  → the folder row + its save/load
src/s_q_ali_media_downloader/engine.py                   → the destination through the legs and LocalVideoThread
src/s_q_ali_media_downloader/core/reframe.py             → vertical_output_path gains a destination folder
src/s_q_ali_media_downloader/core/shorts.py              → split_video gains a destination folder
tests/test_vertical_studio_page.py                       → the control, its persistence, its validation
tests/test_engine_post_leg.py                            → results in the folder, sources untouched
tests/test_reframe.py / tests/test_shorts.py             → the destination naming and collision rule
```

## Code Style

The destination is one more keyword the legs already thread through — it does
not become a second path-building code path:

```python
def run_post_leg(path, *, vertical, split, clips, ffmpeg, duration, report,
                 out_dir=None, ...):
    """Where out_dir is set, every result of this file is written there
    instead of beside the source. None keeps today's behaviour."""
```

Hints stay in the page's voice: plain words, no filenames in the status line
until there is something to point at.

## Testing Strategy

- Offline pytest suite under `tests/`, `QT_QPA_PLATFORM=offscreen`, every test
  marked `not live` unless it needs real ffmpeg.
- The destination rule is proven per unit: the name a vertical/short gets in a
  chosen folder, a collision getting a suffix instead of an overwrite, and a
  run that writes nothing beside the source.
- The page is proven offscreen: the field holds what was picked, the value
  survives a reload, an unwritable folder is named before ffmpeg starts.
- One `@pytest.mark.live` test with real ffmpeg: one file, results in the
  chosen folder, none beside it.
- Gate per task: full offline suite + ruff before the commit lands.

## Boundaries

- Always: never overwrite or delete an existing file, whatever the folder;
  never touch the source; validate the folder is writable before the run.
- Ask first: changing the download flow's output location; adding a setting
  the Settings page shows; changing the existing beside-file default.
- Never: a path or credential in a log line; a silent fallback to another
  folder when the chosen one fails.

## Success Criteria

- [ ] The Studio shows a results-folder row; picking a folder is enough to
      route the next run's outputs there.
- [ ] Empty field = today's behaviour, byte for byte, including the existing
      tests' expectations.
- [ ] The choice is remembered after closing and reopening the app.
- [ ] Two sources with the same name in the same run produce two results, not
      one overwritten result.
- [ ] An unwritable or uncreatable folder is named in the status line and the
      run does not start.
- [x] No result is ever written over an existing file, and no source is
      modified. Proven by `test_a_file_already_in_the_folder_is_never_written_over`
      and `test_a_second_cut_continues_past_the_parts_on_disk`.

## Open Questions

1. Collision in the chosen folder: new suffix or refuse and say so? Decided: a
   new name — the folder accumulates from many sources, and refusing makes
   re-running one file impossible without manual cleanup. The legs disagreeing
   about it (one refusing, one overwriting) is what the audit caught.
2. Does the Settings page also get the field, or does it live only in the
   Studio? (Recommendation: Studio only — it is a Studio option, and the
   Settings page owns download options the Studio reads but never writes.)
3. Should the finished run offer to open the folder? (Recommendation: not in
   this change; the log line names the folder and the field already shows it.)
