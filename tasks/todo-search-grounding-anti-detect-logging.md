# Tasks: Dual-Check Discovery + Hardened Browser + Pro-Level Log

Plan: `tasks/plan-search-grounding-anti-detect-logging.md`
Spec: `tasks/spec-search-grounding-anti-detect-logging.md`

## Phase 0: Spikes

- [x] Task 1: Search-grounding API spike (Gemini `google_search` + Groq
      `browser_search` against the stored keys).
      **Outcome:** Groq `browser_search` on `openai/gpt-oss-120b` works — a
      per-platform answer with quotes and 39 source URLs. Gemini's three chain
      models all answer 429 (quota spent today), so the Gemini leg is built as
      documented and treated as "no answer" when it fails.
- [x] Task 2: Fingerprint spike — plain Playwright vs stealth init script vs
      Patchright.
      **Outcome:** the init script + `--disable-blink-features=
      AutomationControlled` removes the only readable tell
      (`navigator.webdriver`). Playwright does not leak CDP. browser-use's own
      launch is already clean. **No Patchright — no new dependency.**

## Checkpoint: Spikes
- [x] Both spikes produced a decision.

## Phase 1: Foundations

- [x] Task 3: `agent/opslog.py` — one operation record, one Activity Log line
      per operation (engine, target, outcome, duration, error). Wire every
      engine to it.
- [x] Task 4: `agent/tools/stealth.py` — launch args, UA/headers, init-script
      fingerprint patches; `browser.py` exposes the session's CDP URL.

## Checkpoint: Foundations
- [x] Fingerprint probe clean; ops log visible in the panel.

## Phase 2: The two checks

- [x] Task 5: `social_judge.propose_searched()` — Gemini with `google_search`,
      then Groq with `browser_search`; per-platform answer with sources.
- [x] Task 6: `agent_browser.py` attaches browser-use to the app's hardened
      session over CDP (`BrowserProfile.cdp_url`), with its old launch as the
      fallback.
- [x] Task 7: `social_verify.reconcile()` — the AI/browser truth table, every
      row a unit test.

## Checkpoint: Core
- [x] A creator's status is the product of two independent checks.

## Phase 3: The three modes

- [x] Task 8: Wire the dual check into mode 1 (YouTube→Socials), mode 2
      (TikTok→YouTube) and mode 3 (Social Discovery), with a per-run budget for
      search-grounded calls.
      **Outcome:** `agent/tools/dual_check.py` holds the shared trigger, the
      budget and the ask; `social_discovery`, `orchestrator._second_check` and
      `orchestrator._second_check_youtube` each call it. The log shows the
      budget spent and remaining, and a `reconcile` line per platform.

## Checkpoint: Modes
- [x] All three modes run both checks.

## Phase 4: Ship

- [x] Task 9: Full suite (offline + live), ruff, `pip-audit`, `graphify
      update .`, rebuild the portable app.
      **Outcome:** offline suite 522/522, live suite 13/13, ruff clean, and the
      project's own CI audit gate (`pip_audit -r requirements.txt`) reports
      "No known vulnerabilities found". `graphify update .` rebuilt the graph
      (4968 nodes, 7427 edges). The build produced
      `release/S-Q-Creator-Studio-Setup-2.8.0.exe` — the version was bumped
      from 2.7.0 so the released 2.7.0 installer is not overwritten — and the
      built app stayed alive under `QT_QPA_PLATFORM=offscreen` for 20 s.

## Checkpoint: Complete
- [x] Suite green, ruff clean, audit clean, portable build produced.

## Known, not fixed

- **The full venv reports 64 advisories** (anyio, mcp, pillow, pypdf). They
  are the exact transitive pins of `browser-use==0.13.14`, which is the latest
  published version — the pillow fix needs a major bump (13.0.0). The
  project's own CI gate is clean, so nothing was downgraded.

