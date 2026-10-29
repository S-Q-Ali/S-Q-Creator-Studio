# Implementation Plan: TikTok seeds checked on YouTube + Instagram + Facebook

Spec: `tasks/spec-tiktok-seed-socials.md` · Tasks: `tasks/todo-tiktok-seed-socials.md`

## Overview

Delete the HTML harvest that turned the session user into a creator, make
pasted `@handles` the supported path, and give every pasted creator one AI ask
plus live checks on YouTube, Instagram and Facebook. Hashtag tiers stay as a
best-effort with an honest "paste handles" note.

## Architecture decisions

- **Delete the harvest, do not filter it.** The page shell's only `uniqueId`
  is the viewer. A filter would need to know the session user, which the app
  cannot learn safely. Removing the HTML tier removes the false positive at
  the root; the signed API (whose items carry `author.uniqueId`) stays.
- **No AI creator discovery.** Per decision 2 the `proposer` plumbing,
  `propose_tiktok_creators`, its prompt and parser go. The hashtag tiers stay
  because decision 3 still parses tags, but they only produce an honest note
  when TikTok walls them.
- **One AI ask per creator, for all three platforms.** A new
  `propose_tiktok_socials` asks for FB / IG / YT in one JSON, replacing
  `propose_youtube` (which asked only YouTube) so a seeded run does not spend
  two calls per creator. It goes through `_ask_providers` and the existing
  `MAX_AI_PROPOSALS` budget.
- **One verifier entry point for FB + IG.** `verify_creator_socials` gathers
  the two HTTP probes and reuses the existing rendered / agent fallbacks, but
  never probes TikTok: the profile is the input, not something to verify.
- **Same-handle guess is free.** When the ask names nobody, the verifier's
  existing `channel_handle` path builds `facebook.com/<handle>` and
  `instagram.com/<handle>/`; YouTube uses `check_youtube_presence`.
- **No false confidence.** Model / guessed URLs are `model` / `handle_guess`
  and verify as `UNVERIFIED_HANDLE` unless the page's identity evidence says
  otherwise. TikTok profile reads stay impossible; nothing claims a bio read.
- **One dedupe/enrichment path.** The seed and listing paths share
  `_finalize_profiles`; when enrichment is silent the nickname becomes the
  handle, so a walled profile read does not leave every row named
  "TikTok Creator".
- **The existing grounded YouTube second check stays** (`_second_check_youtube`,
  5-search budget): it is the only live-web leg for YouTube after the plain
  ask, and it already reconciles AI + browser.

## Task list

### Phase 1 — Listing truth (`tiktok_api.py`, `tiktok_search.py`)

- Task 1: delete `_html_handles`, `HANDLE_PATTERN`, `UNIQUE_ID_PATTERN` and the
  HTML tiers; allow dotted handles in `_clean_handles`.
- Task 2: delete `_discover_via_html`; parse comma/newline segments into seeds,
  tags (`#word` or a bare single word) and keywords; update the note;
  `_finalize_profiles`.
- Task 3: remove the `proposer` keyword and all AI discovery plumbing from the
  tool, the orchestrator and `social_judge`.
- Task 4: tests — session-shell regression, seed/tag parsing, note wording,
  no proposer.

**Checkpoint:** tool-level suite green; a hashtag run makes no HTML request.

### Phase 2 — Per-creator socials (`schema.py`, `social_judge.py`, `social_verifier.py`, `orchestrator.py`)

- Task 5: add `facebook` / `instagram` presences to `TikTokProfileMetadata`.
- Task 6: `propose_tiktok_socials` prompt, schema and parser; remove
  `propose_youtube`, `YOUTUBE_SCHEMA`, `build_youtube_prompt`.
- Task 7: `verify_creator_socials` (FB + IG, rendered/agent fallbacks, no
  TikTok probe).
- Task 8: orchestrator — one proposal per profile, YouTube handle into
  `check_youtube_presence`, FB/IG verification, per-platform logs, budgets.
- Task 9: tests — one ask per profile, no key → guesses, budget caps, source
  labels, no session handle.

**Checkpoint:** full offline suite green.

### Phase 3 — UI and docs

- Task 10: TikTok table columns (FB / IG / YT), populate, CSV export, copy
  FB / IG buttons, mode label and hint.
- Task 11: README and CHANGELOG.

### Phase 4 — Verification and release

- Task 12: ruff + full offline suite.
- Task 13: live seed run with the user's cookies (`@ishowspeed` and one more),
  checking the log for the session handle and all three statuses.
- Task 14: bump the version, rebuild EXE + installer, bundle markers, smoke.
- Task 15: `graphify update .`, atomic commits.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AI names somebody else's account | Med | Live probe + identity evidence; `UNVERIFIED_HANDLE`, never `VERIFIED` on a model URL alone |
| IG/FB login wall | Med | Existing rendered/agent fallback; an honest `inconclusive` when both fail |
| Many seeds make the browser slow | Med | HTTP probes first; 15-ask cap; 0.5 s pacing; browser only on unclear rows |
| Removing the 2.9.1 proposer surprises the user | Low | Explicit CHANGELOG/README line; recoverable from git history |
| TikTok unblocks listing later | Low | Signed API and yt-dlp tiers stay wired; only the shell harvest is gone |
| Cookie/key material leaks | High | Values never printed; new logs carry handles/status only |

## Open questions

None — the four design questions were answered 2026-10-30.
