# Implementation Plan: Dual-Check Discovery + Hardened Browser + Pro-Level Log

## Overview

Every creator in all three discovery modes gets two independent checks — an
**AI check** (Gemini with Google Search grounding, falling back to Groq with the
`browser_search` tool) and a **browser check** (a hardened, anti-detect browser
the app owns). Their answers are reconciled by one pure function, and every
operation is written to the Activity Log panel.

## Architecture Decisions

**A1 — The app owns ONE hardened browser session; browser-use attaches to it.**
`browser-use` already ships `--disable-blink-features=AutomationControlled` and
accepts `BrowserProfile.cdp_url`. So the app launches real Chrome with a
persistent profile (the profile dir already exists at
`app_storage_dir()/browser-profile`), exports its CDP URL, and hands that URL to
browser-use. The AI agent then browses inside the same hardened session, with
the same cookies and the same fingerprint — exactly the property the user wants
from ego-lite ("uses your browser logins → fewer CAPTCHAs"), but embedded in
our own app and observable in our own log.
*Rejected:* **ego-lite** (`citrolabs/ego-lite`). It is a native app + agent
skill, not an embeddable library; the `ego-browser` helper is a Node bundle the
ego runtime executes via heredoc; there is no documented API for a desktop app
to drive it, and it is visible-browser only. Shipping a second browser product
to gain what `cdp_url` already gives us is not worth it. *Kept as a note:* if
its embedding story changes, it is a drop-in replacement for the session.

**A2 — The AI check asks the web; it does not read the app's pages.**
Gemini's `google_search` tool and Groq's `browser_search` tool are both
server-side search. This is what makes the AI check independent of the browser
check — two different ways of learning the same fact — instead of the AI
re-reading what the browser already saw.

**A3 — Groq's browser search cannot be combined with `response_format:
json_schema`** (confirmed in the vendor docs), so the search path parses the
model's plain text plus `executed_tools[].search_results` instead of a schema.
The existing schema-based `propose()` stays untouched for the no-search path.

**A4 — The AI check runs only when it is needed.** Free tier = 20 requests/day
per model. The AI is asked when the bio has no link for a platform, or when the
browser could not read the page. Never per creator unconditionally.

**A5 — Reconciliation is one pure function in `social_verify.py`,** the module
that already owns the evidence rules. It is table-driven, so every combination
of the two verdicts is a unit test, not a live site.

**A6 — The log is panel-only** (user's choice). One `OpLog` record per
operation, formatted into one line and pushed through the existing
`log_callback` → `ActivityLog.append_line` path. No file is written.

## Spike Outcomes (2026-10-29)

All three spikes ran against the user's real stored keys and a real Chrome
156. The decisions below are measured, not assumed.

| Spike | Measured | Decision |
|---|---|---|
| Groq `browser_search` | **Works.** `openai/gpt-oss-120b` answered with a per-platform breakdown (Facebook: no, Instagram: yes + URL + quote, TikTok: yes + URL + quote) and 39 source URLs in 14 s. | Groq is the proven AI-search leg. `groq/compound-mini` is decommissioned and is not used. |
| Gemini `google_search` | Endpoint and key authenticate correctly, but **all three chain models answer 429** (`retry-after: 30`) — the free-tier quota is spent for the day. The request never reaches the tool, so the tool itself is still unverified on this key. | Build the Gemini leg exactly as documented; treat a 429 as "no answer" and fall through to Groq, which works. Surface `retry-after` in the log. |
| Fingerprint, app today | `navigator.webdriver === true` — the one readable tell. `cdpLeak: false` (Playwright's own launch does **not** leak the CDP debugger). | Fix `webdriver` with an init script + `--disable-blink-features=AutomationControlled`. |
| Fingerprint, hardened | `webdriver: undefined`, `plugins: 5`, `languages: en-US,en`, real Intel WebGL renderer, `cdpLeak: false`. | **Patchright is not needed — no new dependency.** The init script is enough. |
| browser-use's own launch | `webdriver: false`, `plugins: 5`, `chrome: true`, `cdpLeak: false` — already clean. | browser-use needs no hardening of its own; it only needs our profile dir so it shares the logins. |
| browser-use over CDP to our Chrome | `webdriver: false`, `cdpLeak: false`, same profile. Works, but a manual CDP launcher is ~60 lines of new risk. | **Rejected.** The deterministic browser already closes before the AI browser starts, so the two share one profile *sequentially*. No launcher rewrite. |

**Consequence for the design:** the AI check is functional today through Groq
alone, the browser check gets a clean fingerprint with a ~30-line change, and
the app gains no new dependency.

## The Reconciliation Rule

| AI says | Browser says | Final status | Source |
|---|---|---|---|
| yes (url) | FOUND, name/handle match | `VERIFIED` 0.95 | both |
| yes (url) | FOUND, page names someone else | `UNVERIFIED_HANDLE` 0.55 | browser |
| yes (url) | UNKNOWN (login wall / block) | `UNVERIFIED_HANDLE` 0.60 | model |
| yes (url) | NOT_FOUND | `UNVERIFIED_HANDLE` 0.60 | model |
| no | FOUND, name/handle match | `VERIFIED` 0.95 | browser |
| no | NOT_FOUND | `NOT_FOUND` 0.0 | both |
| no | UNKNOWN | `INCONCLUSIVE` 0.0 | browser |
| unknown | any | browser's answer | browser |

A `bio_link` (the creator's own link) that the page matches stays `VERIFIED`
0.95 regardless of what the AI said — the creator's own word beats both.

## Task List

### Phase 0: Spikes (fail fast, cheap, decisive)

- [ ] **Task 1: Search-grounding API spike.**
  - Probe `/v1beta/interactions` with `"tools":[{"type":"google_search"}]` on
    each model of `GEMINI_MODELS`, and Groq `/chat/completions` with
    `"tools":[{"type":"browser_search"}]` on `openai/gpt-oss-120b`, using the
    user's stored keys (read-only; never printed).
  - Acceptance: a script prints, per model, whether the tool was accepted, the
    answer text, and the number of source URLs. No key material in the output.
  - Verify: run it; record the outcome in the task list.
  - Files: scratch script under `%TEMP%` only.
  - Depends on: —

- [ ] **Task 2: Fingerprint spike.**
  - Measure `navigator.webdriver`, `navigator.plugins.length`,
    `window.chrome.runtime`, `navigator.languages`, WebGL vendor/renderer and
    the CDP-debugger side channel under (a) plain Playwright, (b) Playwright +
    stealth init script, (c) Patchright (if installed).
  - Acceptance: a table of results; a decision on whether Patchright is worth
    a dependency.
  - Verify: run the probe against a local page and against facebook.com.
  - Depends on: —

### Checkpoint: Spikes
- [ ] Both spikes produce a decision, not a maybe.

### Phase 1: Foundations

- [ ] **Task 3: Operation log.**
  - `agent/opslog.py`: an `Op` record (ts, stage, engine, target, outcome,
    detail, duration_ms, error) and `log_op()` that formats one line and calls
    the existing log callback.
  - Acceptance: every engine (judge, verifier, agent browser, tiktok search)
    emits through it; the panel shows engine + target + outcome + duration.
  - Verify: unit test for the line format; the existing Activity Log tests
    still pass.
  - Files: `agent/opslog.py`, `agent/tools/*.py`, `ui/activity_log.py`.
  - Depends on: —

- [ ] **Task 4: Hardened browser session.**
  - `agent/tools/stealth.py`: launch args (`--disable-blink-features=
    AutomationControlled`, ...), a realistic UA + `Accept-Language`, and an
    init script that patches `navigator.webdriver`, `navigator.plugins`,
    `window.chrome`, `permissions.query`, `screen`, and WebGL vendor/renderer.
    `browser.py` uses it and exposes the session's CDP URL.
  - Acceptance: a page opened by the app reports `navigator.webdriver ===
    false` and a clean CDP leak check; the browser still opens and reads pages.
  - Verify: fingerprint probe test (marked `live`) + unit test on the payload.
  - Files: `agent/tools/stealth.py`, `agent/tools/browser.py`.
  - Depends on: Task 2.

### Checkpoint: Foundations
- [ ] Fingerprint probe clean; ops log visible in the panel.

### Phase 2: The two checks

- [ ] **Task 5: Search-grounded AI check.**
  - `social_judge.propose_searched()`: asks Gemini with `google_search`
    (chain order preserved), then Groq with `browser_search`; returns an
    `AiAnswer` per platform with the answer, url, quote and source urls.
    Gemini "no answer" → Groq; Groq "no answer" → `JudgeUnavailable`.
  - Acceptance: with the real key, one call returns a per-platform answer with
    at least one source URL; the fallback order is proven by a test that fails
    the Gemini call.
  - Verify: unit tests on the payload builders + a live test.
  - Files: `agent/tools/social_judge.py`, `tests/test_search_grounding.py`.
  - Depends on: Task 1, Task 3.

- [ ] **Task 6: browser-use attaches to our session.**
  - `agent_browser.py` builds its `BrowserProfile` with `cdp_url` from the app's
    hardened session instead of launching its own browser; falls back to its
    own launch when no session is running.
  - Acceptance: the log shows the AI browser running inside the app session
    (same profile dir); behaviour is unchanged when no session exists.
  - Verify: unit test on the profile construction + live run.
  - Files: `agent/tools/agent_browser.py`.
  - Depends on: Task 4, Task 3.

- [ ] **Task 7: Reconciliation.**
  - `social_verify.reconcile(ai_answer, browser_result, is_bio_link)` returns
    the final `SocialStatus` + confidence + source, per the table above.
  - Acceptance: every row of the table is a unit test.
  - Verify: `tests/test_reconcile.py`, all rows green.
  - Files: `agent/tools/social_verify.py`, `tests/test_reconcile.py`.
  - Depends on: Task 5, Task 7's inputs.

### Checkpoint: Core
- [ ] A creator's status is the product of two independent checks.

### Phase 3: Wire the three modes

- [ ] **Task 8: Wire the dual check into modes 1, 2 and 3.**
  - Mode 1 (`run_discovery`): when a platform has no bio link, or the browser
    verdict is UNKNOWN → ask the AI, then reconcile.
  - Mode 2 (`run_tiktok_discovery`): when no YouTube channel was found → ask
    the AI for the handle/channel, then browser-check the candidate.
  - Mode 3 (`social_discovery.discover`): same as mode 1.
  - A per-run budget caps the number of search-grounded calls, and the log
    shows the budget spent and remaining.
  - Acceptance: a live run of each mode shows both engines in the log for the
    same creator, and a `reconcile` line giving the final status.
  - Verify: live runs of all three modes + existing mode tests green.
  - Files: `agent/orchestrator.py`, `agent/social_discovery.py`.
  - Depends on: Task 5, Task 6, Task 7.

### Checkpoint: Modes
- [ ] All three modes run both checks.

### Phase 4: Ship

- [ ] **Task 9: Verify and ship.**
  - Full suite (`-m "not live"` + `-m live`), ruff, `pip-audit`,
    `graphify update .`, then rebuild the portable app.
  - Acceptance: suite green, ruff clean, audit clean, portable build produced.
  - Depends on: Task 8.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| No model in `GEMINI_MODELS` accepts `google_search` | The primary AI check has no grounding | Task 1 settles it; if none work, add a grounding-capable model to the chain — an "ask first" decision |
| Gemini's free tier counts a search call per query, not per request | The quota runs out in minutes | The budget + the log's remaining count make it visible; the budget is per run |
| Groq search breaks the existing JSON-schema parsing | The Groq fallback returns nothing usable | A2/A3: the search path parses text + `executed_tools`, separate from the schema path |
| Patchright adds a dependency for no gain | A liability for no benefit | Task 2 measures first; the dependency is only added if it measurably wins |
| browser-use over CDP behaves differently from its own launch | The AI browser regresses | Task 6 keeps the old launch as the fallback and logs which path was used |
| TikTok blocks regardless of fingerprint | Mode 2 yields no profiles | The signed API + cookie + yt-dlp impersonation path already exists and is kept; the browser is the fallback, not the only route |
| Anti-detection work drifts into evasion of access controls | Platform-policy and legal risk | Scope stays at "look like a normal browser session for the pages the user already visits"; no CAPTCHA solving, no credential harvesting, no proxy rotation |

## Parallelization Opportunities

- Tasks 1 and 2 are independent spikes → run them together.
- Task 3 (ops log) is independent of 1, 2 and 4 → start it while the spikes run.
- Tasks 5 and 6 are independent of each other once 3 and 4 are done.
- Task 7 and Task 8 are strictly sequential after 5 and 6.

## Open Questions

- Which Gemini model in the chain takes `google_search`? (Task 1)
- Should the AI check also run for creators whose bio *does* list every
  platform, as a sanity check on the bio? Default: **no** — it would spend the
  quota for no new information.
