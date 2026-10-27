# Spec: Groq key test + Social Discovery backend visibility

## Objective

The user could not tell whether the Groq API key works, or which backend steps
Social Discovery actually used for a run. Add a real "Test" button to Settings
and show the source counts for each discovery result.

## Scope

- Settings > AI Keys: a **Test** button next to the Groq key. It sends one small
  request to Groq and shows success (model name) or the exact failure inline.
- Social Discovery: each result says how many bio links were found, whether the
  Groq agent was used and how many candidates it proposed, and how many browser
  checks ran.
- Social Discovery: a short "how it works" line explains that the YouTube
  channel is resolved first, bio links are checked, Groq is optional, and only
  the browser confirms an account.
- No change to the verification rules: the AI still only proposes; the browser
  still decides.

## Non-goals

- No YouTube API key test button.
- No new key storage or encryption format.
- No automatic retry of a failed key test.

## Success criteria

- An empty key shows "Enter a Groq API key first." and sends no request.
- A working key shows "Groq key works · <model>" after a real request.
- A bad key shows the Groq error inline, without a modal dialog.
- The Settings page remains usable while the request runs (worker thread).
- A Social Discovery row shows `bio links N`, `AI N candidates` / `AI not used`,
  and `browser checks N`.
- Existing tests and `ruff check src tests` stay green.

## Plan / tasks

1. Add `test_key()` to `agent/tools/social_judge.py` with unit tests.
2. Add the Settings button, worker and inline status with UI tests.
3. Add source counts to `DiscoveryResult` and populate them in `discover()`.
4. Show the counts in the Social Discovery status line and tooltip.
5. Run focused tests, full suite, and `ruff`.

## Boundaries

- Always: keep the key out of logs and error text; never report a failed
  request as a working key.
- Ask first: changing the model, adding a new dependency.
- Never: let the AI turn a candidate into a finding.
