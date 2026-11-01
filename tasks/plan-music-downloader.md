# Plan: Music Downloader (free tier)

Build order follows the capability map in `SPEC-music-downloader.md`.

## Slices

1. **music-source** — URL classification, playlist detection, Spotify
   resolve through spotdl (lazy import), YouTube/SoundCloud resolve through
   yt-dlp. Pure URL helpers tested first.
2. **music-engine** — format map, yt-dlp audio option builder, output path
   builder, `MusicResolveThread`, `MusicDownloadThread`.
3. **music-tagging** — cover fetch, mutagen tag/artwork embed, quality
   report. Round-trip tests with ffmpeg-generated files.
4. **music-ui** — `MusicPage` with URL box, format, folder, queue table,
   progress and start/stop; wire into `MainWindow` workspace tabs.
5. **deps + verification** — pyproject/requirements, full test suite, ruff,
   offscreen GUI smoke.

## Risks

- spotdl needs Spotify API credentials on some releases → env pass-through
  and a clear error message; no account is ever stored.
- spotdl may match the wrong YouTube video → the queue shows the resolved
  title/artist and the source, so the user can spot it before/after.
- YouTube bot checks → reuse the existing player-client fallback and the
  optional Chrome cookies flag.
