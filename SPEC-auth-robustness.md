# Spec: `auth-robustness` — cookies and API keys that actually work

**Objective:** YouTube bot-checks ("Sign in to confirm you're not a bot")
block the research pages exactly like they blocked the downloader. Every engine
already accepts a `cookiefile` parameter, but no UI can supply one — the
escape hatch does not exist for the user.

## Acceptance criteria

1. **Settings can point at a `cookies.txt`.**
   - A file picker on the Settings page (Netscape format, the same format the
     downloader's cookies option accepts) plus a "Clear" button.
   - The path is stored in the `settings` table (`youtube_cookies_file`) and
     shown on load.
2. **The cookie file reaches every engine.**
   - Niche Discovery, Keyword Research, Scorecard (video + channel),
     Competitors refresh, AI Analysis, and the research-side YouTube client
     all read the configured path and pass it down.
   - The path must be validated at pick time (file exists, is readable) and the
     UI must show a clear warning if it disappears later.
3. **A missing/invalid cookie file must not break anything** — the affected
   action fails with a message naming the cookie file, and the app continues.
4. **The YouTube Data API key path is completed.**
   - With a key configured, `youtube_client.fetch_channel` must also return the
     channel's uploads (today the API path returns `uploads=[]`, so the
     Scorecard shows "No uploads fetched" and the AI prompt's "Top videos"
     section is empty).
   - The API path must surface errors instead of silently dropping a 50-id
     chunk.
5. **Cookie values are never logged.** Only the file path may appear in logs.
6. **The downloader and the research tab can share one cookie file** — the
   downloader already offers a Chrome-cookies option; the research tab uses the
   Netscape file. Both must be described clearly in the UI.

## Verification

- Unit tests that the configured path is threaded into every engine call
  (monkeypatched clients).
- A test that a missing cookie file produces a clear error, not a traceback.
- A test that the Data API path returns uploads.
- `pytest -q` green; `ruff check src tests` clean.

## Boundaries

- The cookie file is read at request time; it is never copied into the
  database and never uploaded anywhere.
- Ask first: any change to how the YouTube Data API key is stored.
