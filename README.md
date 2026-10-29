# S-Q Creator Studio

[![Release](https://img.shields.io/github/v/release/S-Q-Ali/S-Q-Creator-Studio)](https://github.com/S-Q-Ali/S-Q-Creator-Studio/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/S-Q-Ali/S-Q-Creator-Studio/actions/workflows/ci.yml/badge.svg)](https://github.com/S-Q-Ali/S-Q-Creator-Studio/actions)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-green.svg)](https://github.com/S-Q-Ali/S-Q-Creator-Studio)

Bulk-download **TikTok**, **YouTube**, **Instagram** and **Facebook** videos and find a creator's Facebook, Instagram and TikTok accounts — one queue-based desktop studio. Every account is confirmed in a real browser, not just guessed by an AI. Open source, free, and no activation keys — ever.

**[Quick Start](#quick-start)** | **[Features](#features)** | **[Install](#install)** | **[Build from Source](#build-from-source)** | **[FAQ](#faq)** | **[Roadmap](#roadmap)**

---

## 🚀 Quick Start

Download the latest release and start downloading videos in seconds:

1. Download the newest `S-Q-Creator-Studio-Setup-*.exe` from [Releases](https://github.com/S-Q-Ali/S-Q-Creator-Studio/releases)
2. Install (no admin rights needed)
3. Paste TikTok, YouTube, Facebook or Instagram links
4. Click Start

**Or build from source** - See [Build from source](#build-from-source) section.

---

## 📸 Screenshots

| Main Interface | Settings |
|----------------|----------|
| ![Main Interface](https://github.com/S-Q-Ali/S-Q-Creator-Studio/raw/master/screenshots/interface.png) | ![Settings](https://github.com/S-Q-Ali/S-Q-Creator-Studio/raw/master/screenshots/settings.png) |

| Social Discovery | Compact Mode |
|------------------|--------------|
| ![Social Discovery](https://github.com/S-Q-Ali/S-Q-Creator-Studio/raw/master/screenshots/social-discovery.png) | ![Compact Mode](https://github.com/S-Q-Ali/S-Q-Creator-Studio/raw/master/screenshots/compact.png) |

---

## Features

- **TikTok & YouTube** in one queue — links are detected automatically and run through per-platform download settings. Instagram and Facebook post links are queued too, without the per-platform tuning TikTok gets.
- **YouTube playlists & channels** expand into individual videos in the background.
- **Instagram profiles** expand into their video posts and reels. Only public profiles — no sign-in, and no account is ever stored. Instagram slows the walk down on purpose, so a listing stops after three minutes and tells you how far it got.
- **Facebook pages** expand into their videos — *experimental*: the page's Videos tab is read in the app's own browser, and the page's own query pages the rest of the list behind it. Only public pages — no sign-in, and no Facebook session is ever stored.
- **Queue management** — add, select, remove, retry, empty. Saved between sessions.
- **Worker pool** — 1–3 parallel downloads with per-worker pacing delays.
- **Automatic retries** — 4 tries per video on the spot, plus optional end passes over the stragglers.
- **Quality presets** — Best available → 2160p/1440p/1080p/720p/480p, plus **Audio only** (MP3 via bundled ffmpeg).
- **Account based** — paste a public TikTok profile and pull its newest video URLs for review. The same button takes an Instagram profile or a Facebook page.
- **Browser impersonation** — TikTok requests are signed with a real Chrome identity so rate-limit failures are far less likely.
- **AI Channel Finder & Social Inspector** — one tab with three modes: **YouTube → Socials**, **TikTok → YouTube**, and **Social Discovery**, which takes a channel URL, a handle or a name and finds the creator's other accounts. Uses a keyless yt-dlp search by default; an optional YouTube Data API key lifts quota walls.
- **Every account is checked twice** — the AI proposes a link and a real browser opens it, then the two answers are reconciled. Neither one is trusted on its own; found, not found and unknown are told apart.
- **Search-grounded answers** — Gemini is asked with Google Search turned on, so the proposal comes from a real search result instead of the model's memory. Groq answers when Gemini has no key or fails.
- **A browser that does not look like a bot** — `navigator.webdriver` and the one-language `navigator.languages` are the two tells a platform can read without guessing; the app hides both.
- **Operation log** — every step writes one line: the stage, the engine that did it, the link it touched and how long it took. The search budget is in there too.
- **Neon theme** — electric cyan on a near-black surface across the whole app, built with PySide6.
- **Fits a small laptop** — the layout has a compact density that switches on below 1500×850, so nothing is clipped on a 1280×720 screen.

> Only download content you own or have permission to download.

## Install

The installer is Windows-only. The source itself runs on Linux and macOS too.

### Installer (recommended)

Download the newest `S-Q-Creator-Studio-Setup-*.exe` from the [latest release](https://github.com/S-Q-Ali/S-Q-Creator-Studio/releases).

- Per-user install — **no administrator rights needed**.
- Bundles `ffmpeg.exe`, so audio-only extraction and format merging work out of the box.
- Bundles a headless Chromium, so Social Discovery works even where no browser is installed.
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

# Social Discovery drives a real browser. Chrome or Edge is used when the
# machine has one; otherwise install the fallback:
playwright install chromium

# run
python -m s_q_ali_media_downloader      # from the repo root (src/ is on the package path)
# or
pip install -e .
s-q-ali-media-downloader

# test + lint
pip install -r requirements-dev.txt
pytest -m "not live"        # the live tests hit the network; run them with `pytest -m live`
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

YouTube and TikTok links are handled separately: TikTok uses Chrome impersonation, YouTube skips it and uses native format selection. Instagram and Facebook post links go through yt-dlp's own extractors, without the per-platform tuning TikTok gets. `Audio only` post-processes to MP3 with the bundled ffmpeg.

## Settings

Everything is in the **Settings** tab of the app.

| Setting | What it does |
|---|---|
| **Gemini API key** | Tried first by Social Discovery, with Google Search turned on so the answer comes from a real search result. |
| **Groq API key** | The second opinion. Used when Gemini has no key or fails; the model only *proposes* accounts, a real browser confirms them. Leave both AI keys empty to search by bio links only. |
| **YouTube API key** | Optional. Without it the search runs keyless through yt-dlp; with it the results carry exact view and subscriber counts. |
| **Cookies file** | Optional. A Netscape `cookies.txt` exported from a signed-in browser — the way around YouTube's "confirm you are not a bot". |
| **Save to / Quality / Pace / Workers / End passes** | Where the videos land and how hard the app works. |
| **Compact layout** | Follows the window by default: below 1500×850 the interface tightens itself so nothing is clipped on a small laptop. Tick the box to choose it yourself. |

The API keys are sealed at rest with Windows DPAPI — on Windows they are stored encrypted and tied to your Windows account, and no key is ever written to a URL or to the log.

## Tech stack

- **PySide6** — Qt 6 desktop UI
- **yt-dlp** — extraction and download engine
- **curl_cffi** — TLS fingerprint impersonation for TikTok (`>=0.15,<0.16`)
- **instaloader** — lists an Instagram profile's posts (yt-dlp's own Instagram extractor is broken upstream)
- **httpx / pydantic / beautifulsoup4** — discovery HTTP, typed schemas, bio scraping
- **Playwright** — the real browser that confirms every account
- **browser-use** *(optional)* — the AI-agent browser, attached over CDP to the session the app already hardened
- **PyInstaller** — standalone EXE packaging
- **Inno Setup** — per-user installer
- **pytest / ruff / GitHub Actions (pip-audit gate)** — tests, lint, CI

## ❓ FAQ

### Common Issues

**Q: "Bot check" error on YouTube?**
A: Export cookies from your signed-in browser:
1. Open Chrome/Edge → Developer Tools (F12) → Application → Cookies
2. Find `youtube.com` cookies
3. Export as `cookies.txt` format
4. Set path in Settings → Cookies file

**Q: Social Discovery fails to verify accounts?**
A: Check these:
- A Gemini API key set in Settings (Groq answers when Gemini has none or fails)
- Browser installed (Chrome or Edge recommended)
- Internet connection stable
- Account actually exists (try visiting the URL directly)

The operation log says which of the two checks answered, and which one did not.

**Q: Downloads fail with "Deleted or Private"?**
A: These videos cannot be downloaded. They're marked as **Waiting** but won't retry to save bandwidth.

**Q: App won't start or crashes?**
A: Try these:
- Reinstall the app
- Check Python 3.10+ installed (if running from source)
- Ensure ffmpeg.exe is accessible (check PATH)
- Verify output directory is writable

**Q: Which quality options are available?**
A: Best available → 2160p → 1440p → 1080p → 720p → 480p, plus **Audio only** (MP3).

---

## 🛣️ Roadmap

### Q4 2026
- [ ] Twitch video downloader
- [x] Instagram & Facebook bulk downloading — expand a profile into its posts, and tune the requests the way TikTok's are
- [ ] Mobile companion app (Android)

### Q1 2027
- [ ] Download history & statistics dashboard
- [ ] Cloud sync (optional, encrypted)
- [ ] Batch download optimization

### Future
- [ ] AI-powered video recommendations
- [ ] Multi-language UI (i18n)
- [ ] Browser extension for quick add

---

## 🙏 Acknowledgments

This project wouldn't be possible without these amazing libraries and tools:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - Powerful video extraction engine
- **[PySide6](https://pypi.org/project/PySide6/)** - Qt 6 Python bindings for desktop UI
- **[curl_cffi](https://pypi.org/project/curl-cffi/)** - TLS fingerprint impersonation for TikTok
- **[httpx](https://www.python-httpx.org/)** - Modern HTTP client for async requests
- **[Pydantic](https://docs.pydantic.dev/)** - Data validation and settings management
- **[BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)** - HTML/XML parsing
- **[Playwright](https://playwright.dev/python/)** - The real browser that confirms every account
- **[instaloader](https://instaloader.github.io/)** - Lists an Instagram profile's public posts
- **[Gemini](https://ai.google.dev/)** - Google Search grounding for the first opinion
- **[Groq LLM](https://groq.com/)** - The second opinion, and the model that browses the web
- **[Inno Setup](https://jrsoftware.org/isinfo.php)** - Windows installer creation
- **[PyInstaller](https://www.pyinstaller.org/)** - Standalone EXE packaging
- **[pytest](https://docs.pytest.org/)** - Testing framework
- **[Ruff](https://docs.astral.sh/ruff/)** - Fast Python linter

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting pull requests.

For bugs or feature requests, please use our [issue templates](.github/ISSUE_TEMPLATE/).

---

## 🔒 Security

We take security seriously. Please see our [Security Policy](SECURITY.md) for vulnerability reporting guidelines.

---

## Links

- **GitHub:** https://github.com/S-Q-Ali/S-Q-Creator-Studio
- **LinkedIn:** https://linkedin.com/in/s-qasim-ali
- **Report Bug:** [Issues](https://github.com/S-Q-Ali/S-Q-Creator-Studio/issues)
- **Request Feature:** [Issues](https://github.com/S-Q-Ali/S-Q-Creator-Studio/issues)

---

## License

[MIT](LICENSE) - Free to use, modify, and distribute.

---

> **⚠️ Disclaimer:** Only download content you own or have permission to download. The developer is not responsible for misuse of this tool. Please respect copyright laws and terms of service of the platforms you use.
