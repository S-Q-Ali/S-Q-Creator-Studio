# Implementation Plan: TikTok discovery via AI search grounding

Spec: `tasks/spec-tiktok-ai-discovery.md` · Tasks: `tasks/todo-tiktok-ai-discovery.md`

## Overview

When TikTok returns nothing for a `#tag`/keyword query, ask the existing
search-grounded AI for public TikTok profile URLs and run them through the
current YouTube-presence check. Seeds (`@handle`) keep today's path.

## Architecture decisions

- **Reuse the provider fallback.** `_ask_searched` already tries Gemini then
  Groq and writes the ops lines. It gains a `parse` hook instead of a second
  copy of that loop.
- **The tool stays AI-agnostic.** `TikTokSearchTool` takes a `proposer`
  callable, the same way `facebook_client.list_page_videos` takes `pager`;
  tests inject a fake and no test needs the network or a key.
- **One budgeted call.** The proposer runs through `ask_the_web`, so the
  per-run `SearchBudget` and its ops lines apply unchanged.
- **No false confidence.** TikTok walls profile reads, so nothing claims the
  proposed handles exist; the log and the tool note say "proposed".
- **The search leg names its own Groq model.** Measured 2026-10-30: 120b's
  `browser_search` dies at Cloudflare (524) while 20b answers in seconds, so
  `GROQ_SEARCH_MODEL` is 20b and every search-grounded ask defaults to it;
  the plain asks keep `DEFAULT_MODEL`.

## Task list

### Phase 1 — The ask (`social_judge.py`)

- Task 1: prompt, parser, `propose_tiktok_creators`, `parse` hook.
- Task 2: tests for the parser and the proposer.

**Checkpoint:** new tests pass; existing judge tests untouched.

### Phase 2 — The fallback (`tiktok_search.py`)

- Task 3: `proposer` keyword, `discovered_by` (`"seed"` | `"listing"` |
  `"ai"` | `""`), note wording.
- Task 4: tests (proposer used, seed skips it, `None` unchanged).

**Checkpoint:** full offline suite green.

### Phase 3 — The wiring (`orchestrator.py`)

- Task 5: propose through `ask_the_web`, log the count and source.
- Task 6: orchestrator tests (one budget call, spent budget still runs).

**Checkpoint:** full offline suite green.

### Phase 4 — Text and docs

- Task 7: `ui/agent_tab.py` hint and the `CHANGELOG.md` bullet.

### Checkpoint: Complete

- Offline suite and ruff clean.
- `graphify update .` committed.
- User asked before the EXE rebuild.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AI names a handle that does not exist | Med | Only `tiktok.com/@handle` URLs accepted; worded as "proposed"; user sees the log line |
| AI key missing or budget spent | Low | Proposer returns `[]`; today's honest note stands |
| Grounded call slows the run | Low | One call per run, budget-capped, existing timeouts |
| Prompt injection from the niche text | Med | Niche is passed as untrusted data, same pattern as `SEARCH_PROMPT` |

## Open questions

None.
