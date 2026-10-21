# Task List: Social Discovery (AI Finder)

Plan: `tasks/plan-social-discovery.md` · Specs: `SPEC-social-discovery.md` +
one per module (`SPEC-social-resolve.md`, `SPEC-social-verify.md`,
`SPEC-social-judge.md`, `SPEC-social-report.md`).

Run before every checkpoint:
`source\venv\Scripts\python.exe -m pytest -q` and
`source\venv\Scripts\python.exe -m ruff check src tests`

**Rule for every task:** the test comes first and must fail before the fix.
A test that passes before the change proves nothing.

> **Status (2026-10-21): all six tasks are done.** Two designs changed
> because of what the live checks showed: the channel page cannot say whose
> links they are, and a plain HTTP request cannot tell a real profile from
> a made-up one.

---

## Task 1: Playwright browser session (the enabler)

**Description:** one browser session that opens a page, reads its rendered
text, the title and its links, and closes cleanly. Edge first, bundled
Chromium as the fallback, and a clear error when neither exists.

- Acceptance:
  - `open_page(url)` returns the rendered text, the title and the page's
    `href` list.
  - A page that cannot be opened raises one error type the caller can turn
    into "unknown".
  - The browser is closed even when the page raised.
  - The module imports no PySide6 and no project code.
- Verify: `pytest tests/test_social_browser.py -q` with a saved HTML
  fixture; a live check against `https://example.com`.
- Files: `src/s_q_ali_media_downloader/agent/tools/browser.py`,
  `tests/test_social_browser.py`
- **Done.** The session also reads the page's Open Graph metadata — that is
  what the profile pages describe themselves with, and it is far more
  reliable than scraping the text. The shipped Chromium (the headless
  shell) is tried first, the browsers Windows has are the fallback, and
  `PLAYWRIGHT_BROWSERS_PATH` points at the shipped copy.

## Task 2: `social-resolve` — the channel record and its own bio links

- **Done, with one correction.** The channel page cannot say whose links
  they are: on MrBeast's About page his own accounts and his sponsors' sit
  in the same description element, and the URL parameter cannot tell them
  apart either. So every social link the page shows is a **candidate**, and
  the verifier decides. The record carries the name, the handle, the
  subscriber count and the candidates.

## Task 3: `social-verify` — does the account exist, and is it this creator?

**Description:** open each candidate in the browser and classify it.

- Acceptance:
  - A real account → `FOUND`, with at least one evidence item.
  - A made-up account → `NOT_FOUND`, and it is dropped from the results.
  - An account that exists but belongs to somebody else → `NO_MATCH`.
  - A login wall, a CAPTCHA or a timeout → `UNKNOWN`, never `NOT_FOUND`.
  - A candidate from the creator's own bio is `FOUND` with the evidence
    `bio_link` even when the page could not be read.
- Verify: `pytest tests/test_social_verify.py -q`; live: `facebook.com/MrBeast`
  (found) vs a made-up page (not found) vs `facebook.com/MrBeastFanPage99x`.
- Depends on: Task 1
- **Done.** The fixtures are real rendered pages, captured on 2026-10-21. The
  outcomes are honest about what could not be read: Instagram and TikTok say
  plainly when an account does not exist, and Facebook shows the same wall
  for a page that does not exist and for one that is gated — so a missing
  Facebook page is "unknown", never "not found".

## Task 4: `social-judge` — the Groq agent proposes and explains

**Description:** one Groq call per channel: propose handles when the bio lists
nothing, explain a match the browser could not settle.

- Acceptance:
  - A known creator with an empty bio yields candidates plus a reason.
  - An unknown creator yields no candidate and says so.
  - A response that is not valid JSON is a clean failure, never a candidate.
  - The model never sets a status; the result carries `source="model"`.
  - The key is read from the sealed setting and never written to a log.
- Verify: `pytest tests/test_social_judge.py -q`; live: MrBeast, MKBHD and a
  made-up channel.
- Depends on: Task 2
- **Done.** The key comes from the Settings page (sealed at rest) or from
  `GROQ_API_KEY` in the environment, which is a deliberate local override.
  The description is cut to 600 characters and passed as data.

## Task 5: `social-report` — the AI Finder mode

**Description:** a mode in the AI Finder tab: paste one channel or a list,
get a table of results. No modals, no cramped layout.

- Acceptance:
  - One row per channel, in the order the user gave them.
  - "Found" and "Suggested" are visually distinct; a suggested account never
    looks like a found one.
  - The evidence is shown under the row it belongs to.
  - A channel that cannot be resolved shows a reason and does not stop the
    other rows.
  - The run can be cancelled and the browser is closed.
  - The export contains every row with its status and evidence.
- Verify: `pytest tests/test_social_report.py -q`; live: two channels, one
  with a bio link and one without.
- Depends on: Tasks 2, 3, 4
- **Done.** The page is `ui/social_discovery_page.py` and the mode is wired
  into the AI Finder tab. The pipeline behind it is Qt-free
  (`agent/social_discovery.py`) so it can be tested without a display.

## Task 6: Packaging and documentation

- Acceptance:
  - `playwright` is an optional dependency; the app starts without it and
    the feature explains how to install it.
  - The CI job installs what it needs and stays green.
  - The changelog, the README and the security note describe what the
    feature sends to Groq and what it does not.
- Verify: `pytest -q`, `ruff check src tests`, the CI job.
- Depends on: Task 5
- **Done.** Chromium (the headless shell) is staged into the portable build
  and the installer carries it; the app points Playwright at the shipped
  copy. Playwright is an optional dependency, so the app starts without it.

### Checkpoint: complete

- [x] Full suite green, ruff clean
- [x] Live check: one channel with a bio link, one without
- [ ] `graphify update .` run
- [x] CHANGELOG updated
