# Spec: `social-verify` — check a candidate account in a real browser

**Objective:** decide whether a candidate Facebook / Instagram / TikTok account
exists **and belongs to the creator**. This is the module that makes the
result trustworthy, so it must be able to say "no" — and to say "I could not
tell" instead of guessing.

**Why Playwright:** a plain HTTP request cannot tell a real profile from a
made-up one. Verified on 2026-10-21: Instagram answers every handle with the
same 590 KB shell, TikTok with the same 1.4 KB script shell, Facebook with
`HTTP 400 <title>Error</title>`. A rendered page shows the difference — the
"page isn't available" state, or the real profile.

**Status:** approved 2026-10-27 for the stricter ownership slice. The user
asked for the back-link cross-check and the fan-page rejection; thumbnails are
deliberately out of scope.

## The three checks per candidate

| Check | What it reads | Meaning |
|---|---|---|
| **Exists** | the rendered page's own not-found / error state | the account does not exist |
| **Matches** | the page's display name, handle, follower count, and the links it lists (a Facebook page lists its website — often the YouTube channel) | the account belongs to this creator |
| **Blocked** | a login wall, a CAPTCHA, a rate limit | we could not tell |

The account's own page is the only reliable ownership signal. The channel
page cannot help: on MrBeast's About page his own accounts and his sponsors'
accounts sit in the same description element (verified 2026-10-21). Rendered,
they are unmistakable — Facebook shows the page name and its follower count,
Instagram puts the handle in the title, and a profile that does not exist says
so.

## Ownership signals

| Signal | What it means | Counts as |
|---|---|---|
| `bio_link` | the candidate URL came from the creator's own YouTube page | positive |
| `back_link` | the candidate page links to the **same** YouTube channel | positive |
| `name_match` | the display name is the creator's name (exact, ignoring punctuation/spacing), or adds only neutral words such as `official`, `the`, `channel`, `tv`, `show`, `yt`, `youtube` | positive |
| `handle_match` | the page's handle equals the creator's handle, case-insensitive | positive |
| `name_partial` | the name contains the creator's name plus other words, but no fan/clip words | informational, not positive |
| `name_conflict` | the name says `fan`, `fans`, `fanpage`, `clips`, `clip`, `edits`, `edit`, `updates`, `news`, `parody`, `fake`, `unofficial`, `community`, `backup`, `reupload`, `archive`, `highlights`, or `compilation` — including when the words are run together, such as `MrBeastFan` | negative |
| `conflicting_back_link` | the page links only to a **different** YouTube channel | negative |

A `back_link` is counted only when the link target names the creator's channel
ID or `@handle`. Redirect links (Facebook `l.php`, YouTube `redirect`, TikTok
`link/v2`, Instagram `l.php`) are unwrapped before the target is read. A link
to a different channel is `conflicting_back_link`, never `back_link`.

Video and short links that do not name a channel are not used as back-link
evidence. The common bio link is a channel link, and that is the case this
spec covers.

## Decision rules

- Positive signals are `bio_link`, `back_link`, `name_match`, `handle_match`.
- `FOUND` needs **two positive signals**.
- One positive signal is `NO_MATCH`.
- `name_conflict` without `bio_link` is `NO_MATCH`, even when two other
  signals match. A page that calls itself a fan/clip page is not the main
  account.
- `conflicting_back_link` without `bio_link` is `NO_MATCH`. A page that links
  only to a different YouTube channel does not become the creator's account on
  the strength of its name alone.
- A candidate from the creator's own bio is `FOUND` with `bio_link` when the
  page cannot be read, or when the page supplies at least one positive signal.
  A readable page with no positive signal stays `NO_MATCH` (the channel page
  also lists sponsors).
- A blocked, rate-limited, or timed-out page is `UNKNOWN`, never `NOT_FOUND`.
- A page that renders nothing is read once more after a short wait; if it is
  still empty, it is `UNKNOWN`. TikTok paints its profile in late.
- An explicit not-found page is `NOT_FOUND` and is dropped from the results.

## Confidence tiers

The verdict says whether to show the account; the tier says how strong the
evidence is.

| Tier | When |
|---|---|
| `confirmed` | `bio_link` + one positive signal, or `name_match` + `handle_match` + `back_link` |
| `likely` | two positive signals without the above, or `bio_link` alone on an unreadable page, or a `name_conflict` that is allowed by `bio_link` |
| `unclear` | not found, no match, or unknown — the verdict already says it, so no tier is shown |

A tier is shown next to the result, in the tooltip and in the detail line, so
the user never sees "Found" without knowing whether it was confirmed.

## Acceptance criteria

1. A real account with two matching signals → `FOUND`.
2. A made-up account → `NOT_FOUND` (and it is dropped from the results).
3. An account that exists but belongs to somebody else → `NO_MATCH`.
4. A blocked platform → `UNKNOWN`, never `NOT_FOUND`.
5. A candidate from the creator's own bio is `FOUND` even when the page
   cannot be read — but its tier is `likely` and it carries `bio_link`.
6. A page whose name contains `fan`, `clips`, `edits`, or a similar word is
   `NO_MATCH` unless the creator's own bio linked it.
7. A page that links only to a different YouTube channel is `NO_MATCH` unless
   the creator's own bio linked it.
8. A Facebook redirect to the creator's YouTube channel counts as
   `back_link`.
9. A real page with name + handle + matching back-link is `confirmed`.
10. A real page with name + handle but no readable back-link is `likely`.
11. The browser is closed after every run, including on failure.

## Boundaries

- **Always:** one browser context per run; a navigation timeout on every
  page; a per-platform cooldown; never send the user's own cookies to a
  platform unless the user configured that platform's cookies.
- **Ask first:** anything that needs a login.
- **Never:** solve a CAPTCHA, or send a request that bypasses a rate limit.
- **Never:** treat a thumbnail or avatar as ownership proof. Fan pages reuse
  both; the link graph is the stronger signal.

## Verification

- Offscreen test with a saved page fixture: real / fake / blocked / unrelated
  / fan page / wrong back-link.
- Live check: `facebook.com/MrBeast` vs a made-up page → different outcomes.
- Focused tests: `pytest tests/test_social_verify.py tests/test_social_discovery.py tests/test_social_discovery_ui.py -q`.
- Lint: `ruff check src tests`.
