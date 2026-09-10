# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.1.0] — 2026-08-28

### Added
- **Cross-platform Social Matrix (AI Finder):** new *Discovery Mode* selector —
  "YouTube → Socials (FB/IG/TikTok)" and "TikTok → YouTube (Creators Without YT)".
- TikTok-first discovery: finds TikTok creator profiles by keyword/tag
  (yt-dlp flat extraction with HTML `uniqueId` harvest fallback), enriches
  follower counts/bio, then detects YouTube presence via bio links and
  bidirectional name-similarity + backlink confirmation.
- Creators **without a YouTube channel** are flagged `TARGET_NO_YOUTUBE`
  (with `NEEDS_REVIEW` for inconclusive probes) and can be exported to
  CSV/JSON, copied, or queued directly.
- TikTok presence probing for YouTube channels (`TARGET_NO_SOCIALS` matrix
  now covers Facebook, Instagram, and TikTok).
- **TikTok mode input flexibility:** paste `@handles` / `tiktok.com/@…` URLs
  directly (always works — no listing scraping needed), `#tag` queries now
  hit TikTok tag pages (yt-dlp does not support search URLs), and an optional
  **cookies.txt** file (TikTok mode "Browse…") unlocks tag/keyword listing
  data where TikTok allows it.
- New `INCONCLUSIVE` social status surfaced in the UI (yellow "? Unconfirmed")
  so network/rate-limit failures are never mistaken for "missing".

### Fixed
- Network errors and rate-limits no longer report socials as NOT_FOUND
  (they are INCONCLUSIVE) — target lists stop inflating with false positives.
- Facebook login-wall responses no longer mark real pages as missing
  (one mobile-UA retry; ambiguous bodies are inconclusive).
- Removed dead Instagram oEmbed fallback (endpoint deprecated by Meta).
- Explicit bio links found in a channel's own description can no longer be
  downgraded to NOT_FOUND by a failed probe (worst case: UNVERIFIED_HANDLE).
- `profile.php?id=` Facebook links keep their numeric id (no more
  query-string stripping); dead `FB_HANDLE_PATTERN` logic replaced with
  priority-ranked matching (vanity page > profile id > people > pages > groups).
- IG text-handle regex now word-boundary anchored with a mandatory separator
  ("config: name" and "instagram.com/explore/" no longer produce ghost handles).
- Zero-key yt-dlp search no longer fabricates YouTube handles from channel
  display names (which caused false FB/IG handle probes).
- `has_no_socials` now counts only platforms the user actually enabled.

### Changed
- Results table adapts per mode; opportunity flags, TikTok columns, and
  YouTube-existence columns added; CSV/JSON exports extended.
- Test suite expanded to 67 tests (100% passing); ruff clean.

### Known limitation (verified 2026-08-29)
- Anonymous TikTok **listing discovery** (keyword/`#tag` search) is blocked by
  TikTok for logged-out visitors (empty JS shells; yt-dlp search URLs
  unsupported, tag extractor broken upstream). Use seed profiles
  (`@handle` / profile URLs) or a cookies.txt file. YouTube-existence
  checking is unaffected.

### Engineering hardening (2026-09-09)
- **One theme.** The research suite now renders the app's single dark
  ink-plum/cyan system — the red accent, zinc cards, and OS light/dark
  switching are gone (`research_style()` always returns dark).
- **Secrets at rest.** API keys are sealed with Windows DPAPI in the settings
  store (plaintext rows migrate on first read); Gemini keys move out of the
  query string into the `x-goog-api-key` header.
- **WCAG-AA contrast.** Faint text lifted to `#8B83A0`; score/competition/SEO
  badge fills moved to the Tailwind-700 family; light secondary text now
  `#52525b`.
- **Version single-source.** Title bar, installer names, README, and packaging
  all derive from `__version__` (`2.1.0`).
- **Tests** grew to a QSS-parse regression for both stylesheets plus
  metadata-extractor and orchestrator control-flow coverage.
- **Git hygiene.** Session exports and personal `opencode.json` are ignored;
  a stray `W` token at the end of the research stylesheet removed.
- **CI.** Runs on Python 3.14, builds via `python -m PyInstaller`, and gates
  on `pip-audit`.
- **Dependencies.** `curl_cffi` pin relaxed to `>=0.15,<0.18`;
  `httpx`/`pydantic`/`beautifulsoup4` declared in `pyproject.toml`.

## [2.0.0] — 2026-08-06

### Added
- Open source release under the MIT license; activation keys removed entirely.
- Rebranded to **S-Q-Ali Media Downloader** with a new icon and dark cyan theme.
- YouTube support alongside TikTok — playlists and channels expand into
  individual videos automatically in the background.
- Per-platform download options (TikTok uses Chrome impersonation; YouTube
  uses native format selection).
- Audio-only preset (MP3) via bundled ffmpeg.
- Per-user Inno Setup installer (no admin required) that bundles ffmpeg.

### Changed
- Source reorganized into a proper `src/s_q_ali_media_downloader` package.
- Added pytest suite, ruff linting, and a GitHub Actions CI pipeline.

### Fixed
- Impersonation failure label now shows the underlying error instead of a
  literal `{exc}` placeholder.

### Removed
- Legacy activation gate and ANAS license keys (kept in git history only).
- Old `Anas Media Downloader` branding and orphaned artifacts.
