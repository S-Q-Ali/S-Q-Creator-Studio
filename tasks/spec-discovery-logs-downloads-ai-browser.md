# Spec — Discovery logs, FB/IG downloads, Gemini fallback, browser accuracy

## Capability map

| # | Capability | Independently testable? |
|---|---|---|
| 1 | Visible activity log for all three discovery modes, including every AI hand-off | Yes — orchestrator/log widget tests |
| 2 | Facebook and Instagram single-post downloads alongside TikTok/YouTube | Yes — URL classification + queue tests |
| 3 | Gemini fallback after Groq, with its own key and Test button | Yes — provider-chain tests |
| 4 | Real-browser accuracy: persistent Chrome/Edge profile + browser fallback for mode 1 | Yes — session/config tests; live checks manual |

## Problem

- Discovery progress is a status string only. The file log has almost no
  discovery entries, so a stalled mode cannot be diagnosed.
- `platform_of()` only knows TikTok and YouTube; the queue rejects every
  Facebook/Instagram link.
- `social_judge` is hard-wired to Groq. A Groq outage or missing key leaves
  Social Discovery without the AI step.
- Social Discovery launches a fresh bundled Chromium each run. That browser
  has no login cookies, so Instagram/TikTok/Facebook show walls and the
  verifier reports `unknown`. Mode 1 verifies with plain HTTP probes and has
  no rendered-page fallback.

## Requirements

### 1. Logs

- Every discovery mode writes timestamped, visible lines to an in-app
  activity log while it runs.
- The log says which backend is active: yt-dlp/API search, TikTok search,
  bio links, Groq, Gemini, browser check, completion/error.
- The AI hand-off is explicit: which provider is tried, whether it fell
  back, how many candidates it proposed, and why it was skipped.
- Lines also go to the rotating file log at INFO.
- The panel is read-only, capped (no unbounded memory), and has Clear.

### 2. Facebook / Instagram downloads

- Accept single Facebook video/reel/watch links and Instagram post/reel/tv
  links in Paste Links.
- `platform_of()` returns `Facebook` / `Instagram`; queue persistence and
  retry logic work unchanged.
- Reject profile/timeline/login URLs (they are not a single video).
- Use the existing yt-dlp options, cookies and ffmpeg. No new dependency.
- Explain login-gated failures in `tidy_error()` and point at Chrome cookies.

### 3. Gemini fallback

- Groq is tried first. Gemini is tried when Groq has no key or fails.
- Gemini uses the REST Interactions API (`POST /v1beta/interactions`,
  `x-goog-api-key`, `response_format` JSON schema, `steps[].content[].text`).
- Keys come from `GEMINI_API_KEY` / `GOOGLE_API_KEY`, then the sealed
  `gemini_api_key` setting. Never logged, never in the repo.
- Settings gets a Gemini key field and its own Test button. Both keys are
  listed in the unreadable-secret warning.
- `Proposal` records the provider and model that answered.

### 4. Browser accuracy

- Social Discovery uses a persistent browser profile under the app storage,
  with the real installed Chrome first, then Edge, then the shipped
  Chromium. Cookies/login survive between runs.
- A browser window is shown by default during discovery so the user can
  sign in once; a setting can keep it hidden.
- Mode 1 uses the rendered-page verifier as a fallback when the HTTP probe
  is inconclusive, instead of marking the account unknown.
- `browser-use` is **not** adopted: it needs Python >= 3.11, an LLM driver
  and is non-deterministic; it does not bypass a login wall. The real
  Chrome/Edge profile is the smaller, reliable fix.

## Non-goals

- Facebook/Instagram profile expansion into a video list (yt-dlp's
  `instagram:user` extractor is currently broken).
- Logging in on the user's behalf, or storing passwords.
- A new AI SDK dependency.
- Version bump or changelog (user request).

## Acceptance criteria

- `pytest -m "not live"` passes, `ruff check src tests` is clean.
- New tests cover: provider fallback order, Gemini response parsing, FB/IG
  URL acceptance/rejection, queue admission, log lines for every mode and
  AI hand-off, persistent-profile configuration.
- The CI `portable-build` artifact is the complete `release\portable`
  folder (browser + `bin\ffmpeg.exe`), not the bare PyInstaller output.
- No secret value appears in source, tests, logs or git history.
