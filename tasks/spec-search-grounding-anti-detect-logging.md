# Spec: Dual-Check Discovery (AI + Browser), Hardened Browser, Pro-Level Operation Log

## Objective

The three discovery modes currently decide a creator's social presence with one
kind of evidence: a browser render. The user wants two independent checks on
every creator — a direct question to an AI that can search the web, and a real
browser visit — with a hardened (anti-detect) browser in the middle so TikTok
and the other platforms do not block the app, and a pro-level log that shows
exactly what happened at every step.

**User stories**

1. As a lead-finder, when a YouTube channel's bio lists no Instagram, I want
   the app to ask Gemini "does this creator have an Instagram?" and, if Gemini
   does not answer, ask Groq — and only then fall back to the browser — so I
   do not lose a creator because their account was not in the bio.
2. As a lead-finder, I want the app's browsing to look like a normal person so
   TikTok does not block it and I do not need to keep re-entering captchas.
3. As a lead-finder, I want to see, per operation, which link was opened, which
   engine ran (AI or browser), which provider and model answered, and what
   error occurred, so I can trust the result and debug it.

**Success criteria**

- Every platform verdict in all three modes is produced by **both** an AI check
  and a browser check (or explicitly recorded as "AI unavailable" / "browser
  unavailable" in the log).
- A search-grounded AI answer is only reached when it is needed (bio empty, or
  the browser could not read the page) — the Gemini free tier allows 20
  requests/day/model and must not be spent per creator.
- `navigator.webdriver` and the CDP-debugger leak are measurably absent on
  every page the app opens, and the browser-use AI agent runs **inside** that
  same hardened session.
- The Activity Log panel shows one line per operation, with engine, target,
  outcome, duration and error.

## Non-goals

- No new UI screen. The log goes in the existing Activity Log panel.
- No scraping of follower lists, no mass messaging, no new platform beyond
  Facebook / Instagram / TikTok / YouTube.
- No new browser engine unless the fingerprint spike proves it is needed.

## Tech Stack

- Python 3.14, PySide6 (desktop), `httpx` for the AI calls.
- Gemini **Interactions API** (`POST https://generativelanguage.googleapis.com/v1beta/interactions`)
  with the `google_search` tool — the same endpoint the app already uses.
- Groq **chat/completions** with the `browser_search` built-in tool on
  `openai/gpt-oss-120b` — the model the app already falls back to.
- `browser-use` 0.13.14 for the AI browser, attached to the app's own browser
  over CDP via `BrowserProfile.cdp_url`.
- Playwright (already a dependency) for the app's own rendered checks.

## Verified API facts (checked against the vendor docs)

| Fact | Source |
|---|---|
| Gemini search grounding: `"tools": [{"type": "google_search"}]` on `/v1beta/interactions`; results arrive as `google_search_call` steps and `url_citation` annotations on text blocks | ai.google.dev/gemini-api/docs/grounding |
| Groq browser search: `"tools": [{"type": "browser_search"}]`, `tool_choice: "required"`; sources arrive in `message.executed_tools[].search_results.results[]` (`content`, `score`, `title`, `url`) | console.groq.com/docs/tool-use/built-in-tools/browser-search |
| Groq browser search is **not compatible** with `response_format: json_schema` | console.groq.com/docs/tool-use/built-in-tools/browser-search |
| Groq browser search is supported on `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `openai/gpt-oss-safeguard-20b` | console.groq.com/docs/tool-use/built-in-tools/browser-search |
| `groq/compound` and `groq/compound-mini` were **decommissioned 2026-09-21** — they must not be used | console.groq.com/docs/compound/systems/compound-mini |
| `browser-use` already passes `--disable-blink-features=AutomationControlled` and accepts `cdp_url`, `user_data_dir`, `executable_path`, `args`, `headers`, `user_agent` | installed `browser_use/browser/profile.py` |

**Open risk:** the docs name `gemini-3.8-flash` / `gemini-4-argon` as
grounding-capable. The app's chain is `gemini-3.6-flash`, `gemini-3.5-flash`,
`gemini-3.5-flash-lite`. Which of them accept `google_search` is **unverified**
and is the first thing the spike (Task 1) settles.

## Commands

```
Build:  release\build.bat
Test:   "C:\Users\MuslimQasim\AppData\Local\Programs\Python\Python314\python.exe" -m pytest -q
Live:   "C:\Users\MuslimQasim\AppData\Local\Programs\Python\Python314\python.exe" -m pytest -q -m live
Lint:   "C:\Users\MuslimQasim\AppData\Local\Programs\Python\Python314\python.exe" -m ruff check src tests
Audit:  "C:\Users\MuslimQasim\AppData\Local\Programs\Python\Python314\python.exe" -m pip_audit -r requirements.txt
Graph:  graphify update .
```

## Project Structure

```
src/s_q_ali_media_downloader/agent/
    tools/
        browser.py          # app's browser session  -> gains hardened launch + CDP export
        stealth.py          # NEW: launch args, init script, fingerprint patches
        social_judge.py     # AI propose()           -> gains propose_searched()
        social_verify.py    # canonical evidence     -> gains reconcile()
        agent_browser.py    # browser-use agent      -> attaches to our CDP endpoint
    orchestrator.py         # mode 1 + mode 2
    social_discovery.py     # mode 3
tests/
    test_stealth.py         # NEW
    test_search_grounding.py# NEW
    test_reconcile.py       # NEW
```

## Code Style

Match the existing style: module docstring stating the rule the module
enforces, `from __future__ import annotations`-style typing, dataclasses for
records, and a docstring on the public function that says *what the caller
learns*, not what the code does.

```python
@dataclass(frozen=True)
class AiAnswer:
    """What one AI provider said about a creator on one platform."""

    provider: str
    model: str
    platform: str
    found: bool | None
    url: str | None
    quote: str | None
    source_urls: tuple[str, ...] = ()
```

## Testing Strategy

- pytest + pytest-qt, `QT_QPA_PLATFORM=offscreen`.
- Unit tests for the pure functions: `reconcile()` (every branch of the truth
  table), the stealth init script (asserts the patched values), the search
  payload builders (asserts the exact JSON sent).
- Live tests stay behind the `live` marker (they hit real sites).
- A fingerprint probe test asserts `navigator.webdriver is False` and the
  CDP-debugger side channel is absent on a page the app opened.

## Boundaries

- **Always:** keep the rule "the model is a witness, not a judge" — the AI
  never sets a verified status by itself. Run the suite and ruff before
  committing. Never log an API key, a cookie value, or a `dpapi1:` blob.
- **Ask first:** adding a new dependency (Patchright, Camoufox); changing the
  `GEMINI_MODELS` chain; anything that ships a new binary in the portable
  build.
- **Never:** commit secrets; write a raw `cookie`/`Authorization` header into
  the Activity Log; disable the existing block/captcha detection.

## Success Criteria

- [ ] Mode 1, 2 and 3 each run an AI check and a browser check per creator,
      and the log shows both.
- [ ] When the bio is empty, the app asks Gemini with `google_search`; when
      Gemini does not answer, it asks Groq with `browser_search`; when neither
      answers, it falls back to the browser and says so in the log.
- [ ] The browser-use AI agent runs inside the app's hardened session (same
      profile, same fingerprint), verified by the log and by a fingerprint probe.
- [ ] `navigator.webdriver` is `false` and the CDP leak check is clean on every
      page the app opens.
- [ ] One Activity Log line per operation with engine, target, outcome,
      duration and error.
- [ ] Full suite green, ruff clean, `pip-audit` clean, `graphify update .` run,
      portable build rebuilt.

## Open Questions

- Which Gemini model in the chain accepts `google_search`? (Task 1 resolves it
  with the user's real key; if none do, a grounding-capable model is added to
  the chain — that is an "ask first" decision.)
- Does the free tier count a search-grounded call as one request or one per
  search query? (Task 1 measures it and the log will show the remaining budget.)
