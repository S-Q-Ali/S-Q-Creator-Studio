# Spec: Download at the best quality the source actually offers

**Status:** approved — the four decisions below are the user's answers.
**Date:** 2026-11-04

## Objective

A link should download at the highest resolution the source really offers, up to
4K, instead of at a fixed 1080p cap the user never chose. "etc" means the whole
ladder behaves that way: 4K when the video has 4K, 1080p when it does not, and
the app says which one it got.

Success for the user: paste a 4K YouTube link, get the 4K file. Paste a TikTok
link (never above 1080p), get the best TikTok offers, without asking for 4K
first.

## Assumptions I am making

1. **The quality setting stays one global dropdown.** yt-dlp's own height
   filters already do the per-platform right thing: a TikTok link has no 2160p
   stream, so `bestvideo[height<=2160]` falls back to its best. No per-platform
   dropdown is needed.
2. **"Best available" today means "no ceiling"** — `bestvideo+bestaudio/best`
   takes an 8K stream when one exists. The user asked for 4K, so the default
   will cap at 2160p and keep 8K as a deliberate choice.
3. **The user's own explicit choice is never overwritten.** Today a settings
   version bump resets Quality to `1080p` for everybody
   (`src/s_q_ali_media_downloader/ui/settings_page.py:446-451`). That has to go,
   or the new default silently replaces a chosen setting.
4. **A cookie-free YouTube run stays as it is.** Changing the player-client
   list is the one part that can reintroduce the bot check, so it is measured
   before it is changed (Task 1 of the plan).
5. **The Music workspace is untouched** — it has its own format list
   (`MUSIC_FORMATS`) and its own resolution story.

## What the code does today (evidence)

| Where | What it says |
|---|---|
| `engine.py:88-96` | `QUALITY_OPTIONS` already holds the whole ladder: `Best available`, `4K · 2160p`, `2K · 1440p`, `1080p`, `720p`, `480p`, `Audio only`. The "4K" entry is `bestvideo[height<=2160]+bestaudio/best[height<=2160]/best` — "the best up to 4K", exactly the target behaviour. |
| `settings_page.py:446-456` | The default is `1080p`, and a settings-version change resets it to `1080p` for every user. **This is the cap the user is hitting.** |
| `engine.py:1008` | The chosen label is looked up in `QUALITY_OPTIONS` and handed to yt-dlp as `format`. |
| `engine.py:1012` | `merge_output_format: "mp4"` — every download is merged into MP4. |
| `engine.py:117` | `YOUTUBE_PLAYER_CLIENTS = ("web_embedded", "mweb", "web")`. yt-dlp's own default list starts with `tv` (`yt_dlp/extractor/youtube/_base.py:429`), and the DASH protocol — which carries the premium streams — is marked PO-token-required there. **This is why "4K" may not even be on the table yet.** |
| `widgets.py:164-262` | The queue card shows title, status, size and speed. It never says which resolution came down. |

So the work is three things, not one: **the default**, **whether 4K is reachable
at all**, and **telling the user what they got**.

## Decisions taken (the user's answers)

| # | Question | Decision |
|---|---|---|
| Q1 | Default quality | **"Best up to 4K"** — the best the source offers, capped at 2160p. "Best available" stays in the list as the deliberate no-cap choice. |
| Q2 | Container for high-res | **MKV when the video is VP9/AV1, MP4 otherwise.** YouTube's 4K is VP9/AV1-only; remuxed into MP4 some players refuse to open it. |
| Q3 | What the card shows | **Resolution + codec + size** (`2160p · VP9 · 412 MB`), so "4K ho gaya" is visible. |
| Q4 | Size guard for big files | **No guard.** The card and the docs show the size; the dropdown still caps it. |


## Tech stack

PySide6 (Qt 6) UI, `yt-dlp` for extraction and download, `ffmpeg` (bundled)
for merging, pytest for the suite, ruff for lint. No new dependency.

## Commands

```powershell
# offline suite (what CI runs)
QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -m "not live" -q

# lint
./source/venv/Scripts/python.exe -m ruff check src tests --output-format concise

# the one live measurement this feature needs (Task 1)
./source/venv/Scripts/python.exe tasks/spike_video_quality.py
```

## Project structure

```
src/s_q_ali_media_downloader/
  engine.py              # QUALITY_OPTIONS, the yt-dlp format string, the client list
  ui/settings_page.py    # the Quality dropdown, its default, the settings migration
  ui/widgets.py          # JobCard — where the resolution would be shown
  ui/main_window.py      # the job_meta signal: title + platform reach the card
tests/
  test_engine.py         # the format strings are pinned here
  test_ui_layout.py      # the window's layout is measured here
tasks/spike_video_quality.py   # the one-off measurement (new)
```

## Code style

One entry per behaviour, no new abstraction. The ladder stays a plain dict, the
default a module constant, the card a label. Follows the house style in
`AGENTS.md` (Ponytail): the smallest change that fully solves the task.

```python
# engine.py
QUALITY_OPTIONS = {
    "Best up to 4K": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "Best available": "bestvideo+bestaudio/best",
    ...
}
DEFAULT_QUALITY = "Best up to 4K"


def merge_container_for(vcodec):
    """MKV for VP9/AV1, MP4 for everything else."""
    codec = (vcodec or "").split(".")[0].lower()
    return "mkv" if codec.startswith(("vp8", "vp9", "av01")) else "mp4"
```

The container cannot come from the format string: yt-dlp reads
`merge_output_format` as a fixed preference list and picks the first
compatible container, and `mkv` is compatible with everything - so
`mkv/mp4` would make every download an MKV. The format selector is
therefore a callable: it selects once to learn the video codec, sets the
container that codec needs, and selects again so yt-dlp's own merge code
builds the file with it.

```python
def codec_aware_format_selector(spec, get_ydl):
    """A yt-dlp format callable that picks the container from the codec."""

    def selector(ctx):
        ydl = get_ydl()
        chosen = list(ydl.build_format_selector(spec)(ctx))
        if not chosen:
            return []
        ydl.params["merge_output_format"] = merge_container_for(chosen[0].get("vcodec"))
        return list(ydl.build_format_selector(spec)(ctx))

    return selector
```

## Testing strategy

- **Unit (offline, in CI):** the format strings still parse, the ladder still
  contains every option, the default is the new one, a settings migration does
  **not** overwrite a quality the user chose, and the card renders a resolution
  chip without clipping.
- **Measurement (live, manual, once):** `tasks/spike_video_quality.py` asks
  yt-dlp for the formats a 4K video exposes, per player client, with and
  without the user's cookies file. It prints heights and codecs — no download.
  This is the evidence for the client-list decision.
- **End-to-end (manual, once):** one 4K link downloaded to disk, the file
  reported as 2160p by ffprobe.

## Boundaries

- Always: keep the offline suite green, keep ruff clean, no key or cookie in a
  log line, keep the "live" tests out of CI.
- Ask first: changing the player-client list (it can bring the bot check back),
  adding a dependency, changing the CI matrix.
- Never: ship a claim about 4K that the measurement does not support.

## Success criteria

- [x] A fresh install downloads a 4K YouTube video at 2160p, and a 1080p-only
      video at 1080p, with no setting to touch.
- [x] A user who had chosen a quality keeps it; only a never-set quality gets
      the new default.
- [x] The queue card names the resolution and codec of what came down.
- [x] The measurement script's output is the evidence quoted in the changelog.
- [x] The offline suite and ruff are green; the CI matrix is green on the three
      OSes at 3.12 and 3.14.

## Open questions

- Q1-Q4 are answered (see the decisions table). The size guard is settled:
  no guard, the card shows the size.
- Still open, and answered by the measurement (Task 1 of the plan): which
  YouTube player client exposes 2160p from this machine. The app pins
  `web_embedded, mweb, web`; YouTube's premium 4K streams live behind the
  `tv` client and a PO token. If no client reaches 2160p here, the honest
  outcome is that the ladder is right and the source does not offer 4K -
  not a claim that the app downloads 4K.
