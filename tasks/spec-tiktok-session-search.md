# Spec — Session search: the signed-in search bar on TikTok, Instagram and Facebook

## Objective

Today the TikTok mode discovers creators only from pasted `@handles`; TikTok
lists nothing to this client, signed in or not. The user wants the app to sign
in with their own cookies and search each platform's **search bar** the way a
person would, then reuse the existing per-creator YouTube / Instagram /
Facebook checks on the accounts that posted about the query.

The feature ships **only if a measurement says it works**. Phase 0 is a
throwaway spike, run with the user's burner cookies, that prints a per-platform
success ratio. No app code changes before that number is known.

**User story.** As a creator-researcher I paste `ishowspeed` (or a hashtag),
the app searches TikTok, Instagram and Facebook with my burner session, lists
the creators posting about it, and shows each creator's YouTube, Instagram and
Facebook status. My own account never appears in the table.

**Success looks like:** the spike reports attempts, loaded pages, creator
handles and walls per platform in one table; if the gate passes, a TikTok run
with cookies configured fills the table from search when the pasted-handle
path finds nothing, and a wall or captcha degrades to today's behaviour with a
visible reason instead of an exception.

## Decisions (user, 2026-10-30)

1. **Spike first** — measure the ratio before building the feature.
2. **Three separate cookies files** — one Netscape `cookies.txt` per platform.
3. **Automatic on every run** — when a platform's cookies file is configured,
   session search runs; no extra button. An empty field disables it.
4. **Burner / side accounts** — main account is not the default and the app
   must say so.

## Prior evidence

| Route (user's cookies) | Result |
|---|---|
| TikTok tag/search HTML | ~392 KB shell, 1 `uniqueId` = session user |
| TikTok signed listing API | 200, 0 bytes |
| Playwright render of tag/search URL | 0 profile links |
| Facebook page read via AI browser | login wall → `unknown` |
| Instagram public profile read (no login) | works (12 timeline nodes) |

The search-bar path is different from the URL-render path measured above: the
signed-in client app fetches its own results after the user types. That is the
open question the spike answers.

## Decisions taken as assumptions

1. Cookie files are user-supplied, read-only and never logged, printed, put in
   a URL or written to the operation log.
2. No password or login flow, no captcha solving, no checkpoint bypass. A wall
   is reported, never retried through.
3. Search only reads public result lists; no follow, like, comment or message.
4. Visible browser (`headless=False`) is the default for session search,
   because a hidden Chrome is the first thing these sites flag.
5. Ratio gate is per platform: a platform ships only if its own spike passes.
6. The existing per-creator checks stay the only source of "verified".

## Gate (agreed after the spike)

Proposed, to confirm when the numbers are in: a platform passes when **≥2 of 3
queries return ≥1 real creator handle** (never the session account) and no
checkpoint / 2FA prompt appears during the run. Failing platforms keep today's
behaviour and the app says why.

## Commands

```
Test:  QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -q -m "not live"
Lint:  ./source/venv/Scripts/python.exe -m ruff check src tests
Spike: ./source/venv/Scripts/python.exe tasks/spike_session_search.py \
         --tiktok <path> --instagram <path> --facebook <path> [--headless]
```

## Project structure

```
tasks/spike_session_search.py                  Phase 0, throwaway (gitignored)
src/.../agent/tools/session_search.py          Phase 1, the real searcher
src/.../agent/tools/tiktok_search.py           last tier when seeds find nothing
src/.../ui/settings_page.py                    three cookie-file fields
tests/test_session_search.py                   parsing, extraction, walls
tests/test_tiktok_pipeline.py                  tier order
```

## Code style

```python
@dataclass(frozen=True)
class SearchOutcome:
    platform: str
    query: str
    creators: tuple[str, ...]
    wall: str = ""  # "login", "captcha", "rate limit" — empty when clean


def search_creators(platform: str, query: str, cookie_file: str) -> SearchOutcome:
    """Type the query into the platform's search bar and read the result list."""
```

Every outcome carries its own reason; callers never infer one.

## Testing strategy

Offline unit tests only, against saved HTML fixtures: cookie-file parsing,
handle extraction per platform, wall detection, session-handle exclusion, tier
order (seeds → API → yt-dlp → session) and "no cookies, no session search".
The live ratio is measured by the spike, not by pytest.

## Boundaries

- **Always:** never log cookie values or `sessionid`; keep tests off the real
  store; report a wall instead of retrying; use burner accounts.
- **Ask first:** adding the three settings keys, changing the search tier
  order, shipping the feature in a build.
- **Never:** store a password, solve a captcha, retry through a checkpoint,
  write cookie contents into the DB, logs, URLs or exception text.

## Success criteria

Spike:

- one table: platform × query → page loaded, result count, unique creator
  handles (session account excluded), wall/captcha, seconds;
- zero cookie values in stdout, stderr or any file;
- exit code 0 only when the gate passes on at least one platform.

Feature (only after the gate):

- with a platform's cookies file set, a run whose seeds and listings are empty
  falls back to session search and shows the creators it found;
- a wall or captcha prints one line and leaves the run's other platforms
  working;
- the session account never appears, even if the site shows it in results;
- the three cookie paths live in Settings and are never printed.

## Open questions

1. Confirm the gate numbers above.
2. Are burner cookies exported for all three platforms yet? The spike needs
   them before it can run.
3. Is a visible browser window acceptable during a run? It is the recommended
   default, but it costs a window and some speed.
