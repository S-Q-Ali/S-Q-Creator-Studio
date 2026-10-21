# Implementation Plan: Social Discovery (AI Finder)

**Spec:** `SPEC-social-discovery.md` (capability map) + one spec per module:
`SPEC-social-resolve.md`, `SPEC-social-verify.md`, `SPEC-social-judge.md`,
`SPEC-social-report.md`.

**Status:** approved scope (2026-10-21). The user narrowed it to: find the
YouTube channel's own bio first, then check a Facebook-page-style candidate,
and let the AI agent (Groq) handle the cases that need judgement.

## What the live spikes proved (2026-10-21)

| Question | Answer |
|---|---|
| Does the Groq key work? | Yes (`gsk_`, 56 chars). Models: `openai/gpt-oss-20b`, `openai/gpt-oss-120b` |
| Does Groq find the handles of a creator with an empty bio? | Yes — MrBeast → `mrbeast` ×3, MKBHD → `MKBHD`, confidence "high" |
| Does Groq invent handles for a creator it does not know? | No — empty lists, confidence "none" |
| Can plain HTTP tell a real profile from a fake one? | **No** — IG/TikTok/FB answer both identically |
| Can a real browser tell them apart? | **Yes** — IG: "Profile isn't available"; FB: the login page; TikTok: "Couldn't find this account" |
| Does a browser read the channel's own bio links? | Yes — after the consent wall, `event=channel_header` links are the creator's own |
| Does Playwright need a 118 MB download? | **No** — `channel="msedge"` drives the browser Windows already has |

## Architecture decisions

- **One browser per run, in a worker thread.** Playwright's sync API runs in
  the worker; the UI never blocks. The browser is closed in a `finally`.
- **Chromium ships with the app** (decided 2026-10-21). The installer
  carries the Playwright *headless shell* (~277 MB) — the headless shell
  and not the full Chromium (~436 MB), because the feature only ever runs
  headless. The app points `PLAYWRIGHT_BROWSERS_PATH` at the shipped copy
  before Playwright starts, so the feature works on a machine that has
  neither Edge nor Chrome. The browsers Windows already has stay the
  fallback for a source checkout.
- **Playwright stays an optional dependency.** The app starts without it
  and the feature explains what to install instead of crashing.
- **The channel's own links are the only "self-claim" evidence.** On the
  About page, `event=channel_header` links belong to the creator;
  `event=video_description` links belong to other creators whose videos are
  listed there. Mixing them is a false-positive machine.
- **The model never decides a fact.** Groq proposes handles and explains
  matches; only the browser may turn a candidate into a finding.
- **The channel description is untrusted input** — truncated, delimited, and
  the model is told to ignore instructions inside it.
- **Engines stay Qt-free.** The browser code lives in its own module with no
  PySide6 import; the UI only renders and wires signals.

## Module ids and dependency direction

| Module id | Responsibility | Depends on |
|---|---|---|
| `social-resolve` | URL / handle / name → channel record + the channel's own bio links | — |
| `social-verify` | open each candidate in the browser → exists? matches? blocked? | `social-resolve` |
| `social-judge` | Groq proposes handles (empty bio) and explains ambiguous matches | `social-resolve` |
| `social-report` | the AI Finder mode: input, batch run, results table, export | `social-verify`, `social-judge` |

Build order: `social-resolve` → `social-verify` → `social-judge` →
`social-report`.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Edge/Chromium missing on the user's machine | The feature cannot run | Edge is on every Windows install; Chromium is the fallback; a clear message otherwise |
| The platform blocks the browser too | "Unknown" instead of a result | Never report "not found" for a blocked page |
| The consent wall changes | The About page cannot be read | Click "Accept all", then re-read; the cookie is set for the session |
| The About page mixes in other creators' links | False positives | Only `event=channel_header` links count as the creator's own |
| Playwright adds a dependency | Bigger install, CI change | Optional extra; the rest of the app does not import it; CI's Edge needs no download |
| A batch of 20 channels takes minutes | The UI looks stuck | One worker, a progress line, cancel, and the results appear row by row |

## Verification checkpoints

- After `social-resolve`: a live check on `@mkbhd` returns the title, the
  handle and the creator's own links.
- After `social-verify`: a live check on a real and a made-up account on
  each platform returns different outcomes.
- After `social-judge`: a live check on a known creator, an unknown creator
  and a malformed response.
- After `social-report`: an offscreen test of the table, plus a live run of
  two channels.

Full suite (`pytest -q`) and `ruff check src tests` must stay green at every
checkpoint.
