# Spec: Music Downloader (free tier)

## Objective

A new **Music** workspace in S-Q Creator Studio that downloads audio from
YouTube, YouTube Music, SoundCloud and Spotify links without any paid
account. Spotify links carry metadata rather than audio: `spotipyFree` reads
that metadata anonymously and `yt-dlp`'s own search matches each title to the
YouTube audio. `yt-dlp` performs every download. Default output is FLAC with
embedded cover art and tags. Playlists and albums enter the queue in one
click.

Success: paste a Spotify playlist URL, press Start, and get a folder of
tagged FLAC files with no account, key or subscription.

## Tech Stack

- PySide6 6.11 (existing) — UI.
- yt-dlp (existing) — audio download and conversion.
- spotipyFree (new) — anonymous Spotify metadata; no login and no client ID.
- mutagen (new) — tag writing and quality report.
- ffmpeg (system, located by `find_ffmpeg()`) — format conversion.

## Commands

- Test: `python -m pytest`
- Focused: `python -m pytest tests/test_music_*.py -q`
- Lint: `python -m ruff check src tests`
- Run: `python -m s_q_ali_media_downloader`

## Project Structure

```
src/s_q_ali_media_downloader/
  core/music_source.py     URL classify, Spotify resolve via spotipyFree,
                           YouTube/SoundCloud resolve via yt-dlp
  core/music_tagging.py    cover fetch, tag embed, quality report
  engine.py                MUSIC_FORMATS, build_music_opts,
                           music_output_path, MusicResolveThread,
                           MusicDownloadThread
  ui/music_page.py         MusicPage widget
  ui/main_window.py        Music workspace tab
tests/
  test_music_source.py
  test_music_engine.py
  test_music_tagging.py
```

## Code Style

Follow the existing engine: type hints, snake_case, 100-column ruff,
docstrings that explain why, user-facing errors through `tidy_error`.
Pure helpers take plain arguments so they can be tested without network.

## Testing Strategy

- Unit tests (no network) for URL classification, playlist detection,
  format mapping, output path, yt-dlp option builder and tag round-trips.
- Tag tests generate a short tone with ffmpeg and are skipped when ffmpeg
  is absent.
- Live tests for a real YouTube and Spotify URL are opt-in (`-m live`).

## Boundaries

- Always: validate URLs at the trust boundary; embed artwork and metadata;
  funnel worker errors to signals; keep the neon theme tokens.
- Ask first: any dependency beyond spotipyFree/mutagen; edits to existing
  downloader pages; version bumps.
- Never: commit credentials; bypass DRM; delete or skip failing tests.

## Success Criteria

1. YouTube video URL → FLAC file with embedded cover and tags.
2. YouTube playlist URL → every entry queued; per-track progress; cancel
   works; one failure does not stop the rest.
3. Spotify track URL → correct title/artist/cover → audio downloaded and
   tagged, with no Spotify account.
4. Spotify playlist URL → full queue in one click.
5. All five formats (FLAC, MP3, M4A, Opus, WAV) produce the right file.
6. Failed track retries inline three times, then the queue continues.
7. `pytest` and `ruff check` pass; no network calls in unit tests.

## Out of Scope (later phases)

True lossless via Tidal/Qobuz (SpotiFLAC), Dolby Atmos, lyrics embedding,
clipboard monitor, tray, download history, trim, batch tag editor.

## Open Questions

- Spotify credentials: resolved. spotdl pinned rich, websockets and uvicorn to
  versions that broke the Social Discovery browser stack, so Spotify metadata
  now comes from spotipyFree, which needs no client ID and no login at all.
- Music downloads run sequentially to stay clear of YouTube bot checks.
