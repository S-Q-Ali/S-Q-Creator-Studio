# S-Q Creator Studio

Bulk-download **TikTok** and **YouTube** videos, discover cross-platform creators, and research niches — one queue-based desktop studio. Open source, free, and no activation keys — ever.

[![Release](https://img.shields.io/github/v/release/S-Q-Ali/S-Q-Creator-Studio)](https://github.com/S-Q-Ali/S-Q-Creator-Studio/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/S-Q-Ali/S-Q-Creator-Studio/actions/workflows/ci.yml/badge.svg)](https://github.com/S-Q-Ali/S-Q-Creator-Studio/actions)

---

## Features

- **TikTok & YouTube** in one queue — links are detected automatically and run through per-platform download settings.
- **YouTube playlists & channels** expand into individual videos in the background.
- **Queue management** — add, select, remove, retry, empty. Saved between sessions.
- **Worker pool** — 1–3 parallel downloads with per-worker pacing delays.
- **Automatic retries** — 4 tries per video on the spot, plus optional end passes over the stragglers.
- **Quality presets** — Best available → 2160p/1440p/1080p/720p/480p, plus **Audio only** (MP3 via bundled ffmpeg).
- **Account based** — paste a public TikTok profile and pull its newest video URLs for review.
- **Browser impersonation** — TikTok requests are signed with a real Chrome identity so rate-limit failures are far less likely.
- **AI Channel Finder** — cross-platform social discovery: YouTube → Facebook/Instagram/TikTok, and TikTok → YouTube. Uses a keyless yt-dlp search by default; an optional YouTube Data API key lifts quota walls.
- **Niche Research** — keyless keyword research, trending-channel discovery, SEO scorecards, and competitor tracking, all in the same dark theme.
- **Single dark theme** — ink-plum surfaces with a cyan accent across the whole app, built with PySide6; research UI shares it.

> Only download content you own or have permission to download.

## Install

### Installer (recommended)

Download `S-Q-Creator-Studio-Setup-2.4.2.exe` from the [latest release](https://github.com/S-Q-Ali/S-Q-Creator-Studio/releases).

- Per-user install — **no administrator rights needed**.
- Bundles `ffmpeg.exe`, so audio-only extraction and format merging work out of the box.
- Installs Start-menu and (optional) desktop shortcuts, plus an uninstaller.

### Portable

The release also ships a portable folder — just unzip and run `S-Q Creator Studio.exe`. It needs the `_internal` folder to stay next to it. System ffmpeg is used if present on `PATH`.

## Build from source

Requires Python 3.10+.

```powershell
git clone https://github.com/S-Q-Ali/S-Q-Creator-Studio.git
cd S-Q-Creator-Studio

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# run
python -m s_q_ali_media_downloader      # from the repo root (src/ is on the package path)
# or
pip install -e .
s-q-ali-media-downloader

# test + lint
pip install -r requirements-dev.txt
pytest
ruff check src tests

# build a standalone EXE (onedir, windowed)
pyinstaller --noconfirm --clean --onedir --windowed `
  --name "S-Q Creator Studio" `
  --icon "src\s_q_ali_media_downloader\resources\icon.ico" `
  --add-data "src\s_q_ali_media_downloader\resources\icon.ico;." `
  --paths "src" `
  "src\s_q_ali_media_downloader\__main__.py"
```

## How downloads work

Each link is tried 4 times on the spot (2–5 s apart). Stills-failing links are marked **Waiting**, and optional end passes sweep them again after a cooldown. Errors that can never succeed — deleted, private, region-blocked — fail immediately instead of wasting retries.

YouTube and TikTok links are handled separately: TikTok uses Chrome impersonation, YouTube skips it and uses native format selection. `Audio only` post-processes to MP3 with the bundled ffmpeg.

## Tech stack

- **PySide6** — Qt 6 desktop UI
- **yt-dlp** — extraction and download engine
- **curl_cffi** — TLS fingerprint impersonation for TikTok (`>=0.15,<0.18`)
- **httpx / pydantic / beautifulsoup4** — discovery HTTP, typed schemas, bio scraping
- **PyInstaller** — standalone EXE packaging
- **Inno Setup** — per-user installer
- **pytest / ruff / GitHub Actions (pip-audit gate)** — tests, lint, CI

## Links

- GitHub: https://github.com/S-Q-Ali
- LinkedIn: https://linkedin.com/in/s-qasim-ali
- Report a bug or request a feature: [Issues](https://github.com/S-Q-Ali/S-Q-Creator-Studio/issues)

## License

[MIT](LICENSE)
