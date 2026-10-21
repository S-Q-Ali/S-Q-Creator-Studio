# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.4.2] — 2026-10-20

### Niche Research completed

The research suite had working engines but unreliable numbers, several crash
paths and only one of ~16 page-to-page handoffs. This release finishes it.

**Fixed (data was wrong by construction)**
- Keyword demand was overwritten with a constant `100` on every ranking run.
- Ranked-video lists repeated the same video once per run.
- A keyword scored in an earlier run was reset to "unscored" by an unrelated
  research run.
- Re-discovery wiped the "already analysed" marker of a channel.
- The keyword-placement half of the SEO score (34 of 100 points) could never
  fire — no caller ever passed a focus keyword. The Scorecard now has a
  **Focus keyword** field.
- The channel score treated subscribers as views, so engagement was always 0
  and a small channel scored 100 on "growth velocity". Channels are now scored
  on reach (views per subscriber) and output (average views per video).
- Tracked items showed a channel id instead of the channel title, and channel
  uploads always showed `0 views` (flat extraction drops the count).
- "Last discovered" showed an arbitrary niche, not the newest one.

**Fixed (crashes)**
- The Agent tab's **Queue** button called a method that did not exist — every
  click raised `AttributeError`.
- The Scorecard crashed on the *second* failed lookup (deleted empty-state
  widget re-added).
- Closing the AI Analysis modal mid-analysis aborted the process
  (`QDialog.reject()` bypassed `closeEvent`, so the workers were never joined).
- Closing the app left the research poller and its workers running.
- The Niche Discovery niche filter was empty until the format filter was
  touched.
- Two worker threads reaching the database at the same time both opened a
  connection and ran the migrations twice — "duplicate column name" and
  "database is locked". The connection is now opened under the lock.

**Security**
- **The YouTube cookie jar could be sent to any host the user pasted in.**
  The research client attached the configured `cookies.txt` to every yt-dlp
  request, and the channel lookup accepted any input *containing* the text
  `youtube.com` — so `https://attacker.tld/?youtube.com` produced an outbound
  request from the user's machine with their logged-in YouTube session
  attached. The host is now matched exactly, and a non-YouTube target is
  refused before any request is made.
- **The Data API key was written to the log file in cleartext.** It travelled
  as `?key=` in the query string, and httpx logs every request URL at INFO
  into the rotating `app.log` that sits next to the user's data. The key now
  travels in a header, the httpx logger is quietened, and a filter scrubs
  key/token patterns from every log record.
- **A key that could not be encrypted was stored in plain text** — and the
  fallback could never run anyway, because `ctypes.WinError` is a function on
  Python 3.14, so `except (OSError, ctypes.WinError)` raised `TypeError`
  instead of catching. Sealing now fails closed: if Windows refuses to
  protect the key, nothing is stored and the user is told.
- **A database copied to another Windows account could not start the app.**
  DPAPI is user-scoped, and the Settings page reads every key while the
  window is being built; the unseal call was unguarded, so that one case
  made the app fail to start with nothing but a traceback. The key is now
  reported as "needs re-entering" instead.
- **One click could buy several paid AI analyses.** The "Analyze this
  channel" button was a local variable, so it was never disabled: every
  click started another provider call while the first was still running.
  The button is now disabled while the analysis runs, a second click is
  ignored, and a **Cancel** button stops it — the analysis checks the flag
  between providers, so a cancelled analysis never falls through to the next
  paid call.

**Added**
- **Cross-page handoffs:** Niche Discovery → queue / Scorecard / Track / Open,
  Scorecard → AI Analysis, Competitors → Scorecard / keyword detail / AI
  Analysis, AI Analysis → Scorecard. One shared
  `send_to_queue_requested` bridge feeds the download queue.
- **A real Dashboard** — metric tiles, top channels, top keywords, a recent
  activity feed and working quick actions (it was a static intro card).
- **Export** on every data page: CSV (Excel-ready), JSON (full data) and
  Markdown (report) for Niche Discovery, Scorecard, Competitors, Keyword
  Research and AI Analysis. Every group of a page survives the export — the
  Competitors CSV and JSON used to keep one group of three. A cell whose
  value starts with `=`, `+`, `-` or `@` is neutralised, so a channel title
  cannot execute a formula when the export is opened in a spreadsheet.
- **A cookies.txt setting** (Settings → YouTube cookies.txt). YouTube's bot
  check blocked the research pages; this is the escape hatch, and it now
  reaches every engine.
- **An app-wide hourly poller** — snapshots are recorded even when the
  Competitors page is not open (VPH and 7-day growth need two snapshots), with
  a configurable interval (30/60/180 min) and failure counts in the summary.
- **Thumbnail generator without an AI analysis** — it was gated behind a
  full chat analysis.
- **A real "Create Similar Channel"** — a nearest-neighbour search over the
  discovered channels with a 0-100 similarity score. It used to compare the
  channel with itself and report 100.
- **An "AI only" filter** in Niche Discovery (the engine supported it, nothing
  could switch it on) and the niche **competition / difficulty** badges. The
  filter now applies to the count as well, so the header does not claim more
  channels than the grid shows.
- The **niche filter** is usable at startup: with "All Formats" selected it
  offers every niche instead of only "All Niches".
- **Analysis progress** — the modal shows which provider is being tried, and
  a **Cancel** button stops the run before the next provider is called.
- **The full analysis is stored, not just the strategy** — `analysis_json`
  now holds the strategy, the ideas, the scripts and the blueprint (rows
  written by the previous release still read back correctly), and each script
  is linked to the content idea it came from.
- **The Data API path carries the same data as the yt-dlp path** — a tracked
  video shows the channel title instead of the channel id, and a channel
  lookup includes the newest uploads with their real view counts.

**Polish**
- The Competitors sparklines were flat lines for every series above 100
  (view and subscriber counts) — they now scale to their own range.
- The untrack button said "Tracking" while it deleted the item.
- Dead code removed: `trending_engine.get_format_niche_counts`,
  `keyword_engine.decode_term`, `keyword_engine.get_cached_keywords`,
  `scorecard_engine.score_label`, `autocomplete.expand_seed`, `db.vacuum`,
  plus six dead QSS rules.

### Download engine (same release)

### Fixed
- **YouTube downloads failing everywhere** — every YouTube download died with
  "Sign in to confirm you're not a bot". Root cause: yt-dlp 2026.x asks
  YouTube's default `web` player client for a PO token, and only a real browser
  can mint one, so the request is bot-checked. Every yt-dlp options builder
  (downloads, TikTok account fetch, YouTube playlist/channel expansion,
  research client, agent search) now passes `js_runtimes` for
  deno/node/bun/quickjs so the EJS challenges have a runtime, **and** YouTube
  downloads now request the PO-token-free `web_embedded` / `mweb` clients
  first, with `web` kept as the cookie-friendly fallback. Guarded by
  regression tests.
- **TikTok profile fetch produced undownloadable links** — expanding a
  TikTok profile queued the signed CDN media URL that TikTok puts in each
  listing entry. Those links answer `HTTP 403 Forbidden`, so every video
  failed. The queue now gets the stable page URL
  (`tiktok.com/@user/video/<id>`), and CDN media links are no longer
  accepted as queueable TikTok links.
- **Download failures showed a useless message** — the extractor error was
  discarded and every failure surfaced as "Download finished but the file is
  missing". The real reason (bot check, 403, missing ffmpeg) now reaches the
  queue row and is written to the app log.
- **Portable builds shipped without ffmpeg** — "Best available" downloads
  video and audio as separate streams and yt-dlp needs ffmpeg to merge them.
  `build_release.bat` now stages `ffmpeg.exe` into `release\portable\bin\`
  (the engine already looks there), so the portable build works on machines
  that have no ffmpeg installed.
- Friendlier, actionable messages for the two flaky upstream failures:
  YouTube's bot check (wait / Chrome cookies) and TikTok's intermittent
  "Unable to extract secondary user ID" profile fetch (retry in a few
  minutes — TikTok-side flakiness that persists on latest yt-dlp 2026.8.19).


## [2.4.1] — 2026-09-11

### Fixed
- **TikTok account (profile) fetch regression** — "Couldn't fetch that account"
  in the Account tab. Root cause: bundled yt-dlp was too old to parse TikTok's
  current profile pages ("Unable to extract secondary user ID"). Bundled
  yt-dlp is now **2026.8.19+**; `yt-dlp>=2026.8.19` is pinned in
  `requirements.txt` / `pyproject.toml`, and the floor is guarded by a
  regression test so it can't silently drop again.

## [2.4.0] — 2026-09-10

### Added
- **AI thumbnail generation in Niche Research** — channel analyses can now
  generate a thumbnail from any AI provider with an auto fallback chain
  (aihubmix → Google AI → OpenRouter). A clear "No AI image provider
  configured" error guides you to Settings instead of silently failing.
  The **Google AI key** now actually reaches channel analysis (Settings key
  `google_ai_api_key` was being read under the wrong name).
- **Paste a TikTok profile URL and it auto-expands** into its videos in the
  downloader — profile links are routed into the expand queue via the
  account-based fetch thread.
- **Clickable verified badges & channel links** in the AI Channel Finder
  results (channel titles, verified FB/IG/TikTok badges, TikTok YouTube
  channel + URL cells) — one click opens the link.
- **Selectable text everywhere in Niche Research** — channel names, stats,
  strategy rows, ideas, scripts, and trending card values can be copied,
  and long trend-card titles now word-wrap instead of getting clipped.
- A single analysis modal per session (no stacking when clicking
  "Create Similar Channel" repeatedly).

### Fixed
- **Trending card crash on re-render** — the Analyze → reload path crashed
  when `_clear_layout` hit the trailing stretch spacer; the rebuild no longer
  dies on non-widget layout items.
- **Empty / blocked profile pictures** no longer break avatar thumbnails —
  they fall back to the clean initials treatment.
- **Stacked confirm dialogs** in the AI Channel Finder replaced with inline
  status messages (send-to-queue, copy FB/IG/TikTok links, CSV/JSON export);
  only genuine errors still pop a dialog.

### Changed
- **UI tightness pass**: trending cards are a uniform 300px with wrapped
  titles; the agent results table is read-only with no grid lines, hidden
  row numbers, and extended row selection; the research dashboard spacing
  is tightened (no more floating gap between the intro card and the
  quick-start hints).

## [2.3.0] — 2026-09-10

### Fixed
- **Channel video counts were always "0"** in Niche Discovery / Scorecard /
  AI Analysis: `channel_video_count` does not exist in yt-dlp; the pipeline now
  falls back to `playlist_count`, so totals like "1.2K videos" match the web tool.
- **Channel stat downloads blocked the UI** — avatars and video thumbs now load
  asynchronously off the GUI thread with a disk cache, a `maxres→hq→mq` fallback
  chain, and a smooth crop instead of a stretch.
- **Avatar placeholders were broken**: a channel with no real profile picture
  showed a red "error" gradient instead of a clean initials avatar; it now falls
  back to the "S-Q" cyan→teal initials treatment.
- Scorecard/AI Analysis no longer show a fabricated `0` for stats that keyless
  research couldn't measure — unknown counts display a neutral `—`; the DB stores
  NULL instead of zero for unknown totals.

### Added
- **YouTube Data API key field in Settings** (optional): unlocks exact channel
  stats — total uploads, total views, join date — matching the web tool. Search &
  discovery stay keyless (yt-dlp). The "Default AI provider" dropdown is now
  visible (it was silently hidden on small windows).
- Research UI now renders with the app's font family (`Segoe UI Variable
  Display` → `Segoe UI` → `Inter`) so the whole suite reads as one brand.

### Changed
- Keyword detail metrics and analysis-modal stat tiles start at `—` instead of `0`
  until real data arrives.

## [2.2.0] — 2026-09-10

### Changed
- **Rebranded to S-Q Creator Studio** — the downloader, AI Channel Finder, and Niche Research suites now ship under one creator-brand. Window title, installer (per-user), portable build, and release artifacts are named `S-Q Creator Studio`.
- On-disk identity (`%LOCALAPPDATA%\S-Q-Ali Media Downloader`) is intentionally unchanged so settings, the saved queue, and the sealed research DB survive the update untouched.

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
