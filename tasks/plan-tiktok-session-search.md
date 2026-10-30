# Plan — Session search (spike first, feature gated)

Spec: `tasks/spec-tiktok-session-search.md` · Todo: `tasks/todo-tiktok-session-search.md`

## Shape

One capability, two phases separated by a measurement gate. Phase 0 is a
throwaway script; Phase 1 is the app wiring, written only if the gate passes.

## Phase 0 — the spike (`tasks/spike_session_search.py`, gitignored)

1. **Cookie loader.** Parse a Netscape `cookies.txt` into Playwright cookie
   dicts (`domain`, `path`, `secure`, `expires`, `name`, `value`). Never print
   a name/value pair. Reject a file with no cookies for the platform's domain.
2. **Session.** Reuse `BrowserSession`'s launch settings (`STEALTH_ARGS`,
   `harden`, bundled browsers) but a fresh context with `add_cookies`. Default
   visible.
3. **Per-platform search.**
   - TikTok: `tiktok.com/search?q=` → type in the search box → wait for
     `[data-e2e="search-user-item"], [data-e2e="search_top-item"]` → read
     `a[href*="/@"]`.
   - Instagram: `instagram.com/` → search dialog → type → read anchors whose
     href matches `^/([A-Za-z0-9._]+)/?$`; drop known paths
     (`explore`, `reels`, `accounts`, `p`, `direct`, `stories`).
   - Facebook: `facebook.com/search/top/?q=` → read anchors matching
     `facebook.com/(profile.php?id=\d+|[\w.]+)`; drop product paths.
4. **Wall detection.** Page text or title containing login / sign in /
   checkpoint / captcha / "rate limit" / "try again" → wall reason; no retry.
5. **Metrics.** Per platform × 3 queries: page loaded, raw result links,
   unique creator handles (session handle excluded via `--session-handle`),
   wall, seconds. Print one table; write JSON next to the script.
6. **Gate.** Exit 0 while any platform has ≥2 of 3 queries with ≥1 creator
   handle and no wall.

## Phase 1 — the feature (conditional on the gate)

1. `agent/tools/session_search.py`: `SearchOutcome` + `search_creators()`,
   one small function per platform, shared cookie loader and wall detector.
2. `agent/tools/tiktok_search.py`: session search becomes the last listing
   tier, per platform, only when that platform's cookies file is set; caps at
   `SESSION_QUERIES_PER_RUN` (3) and one platform failure never stops another.
3. Settings: three fields (`tiktok_cookies_file`, `instagram_cookies_file`,
   `facebook_cookies_file`) with the burner warning; the existing TikTok
   cookies field stays for yt-dlp.
4. Orchestrator/UI: pass the three paths through; the log shows one line per
   platform with count and wall reason, never a cookie.
5. Docs: README bullet + CHANGELOG; build and verify like 2.9.2.

## Risks and mitigation

| Risk | Mitigation |
|---|---|
| Burner account gets checkpointed or restricted | Visible browser, 3 queries, human pacing, stop on first wall, no retries, burner by default |
| Cookies expired | Login wall is reported as "cookies expired, export again" |
| A platform's DOM changes | Selectors isolated per platform; fixtures in tests; a miss returns 0 with a reason, never an exception |
| Slow run (3 × 3 page loads) | Per-platform time cap; session tier runs only after the cheap tiers return nothing |
| Cookie file is plaintext on disk | Same as today's TikTok/YouTube path; values only in memory, never logged; a sealed-store option is deferred |
| Playwright flagged as automation | Reuse the existing stealth args and fingerprint hardening; keep the window visible |

## Verification checkpoints

- After Phase 0: the ratio table is in front of the user and the gate is
  confirmed or rejected — no app code written before this.
- After Phase 1 searcher: focused tests green, ruff clean.
- After wiring: offline suite green; live run with burner cookies shows
  creators and the session account is absent.
- After release: bundle markers and smoke pass like 2.9.2.
