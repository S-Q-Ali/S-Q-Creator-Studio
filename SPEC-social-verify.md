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

## The three checks per candidate

| Check | What it reads | Meaning |
|---|---|---|
| **Exists** | the rendered page's own not-found / error state | the account does not exist |
| **Matches** | the page's display name, handle, follower count, and the links it lists (a Facebook page lists its website — often the YouTube channel) | the account belongs to this creator |
| **Blocked** | a login wall, a CAPTCHA, a rate limit | we could not tell |

The account's own page is the only reliable ownership signal. The channel
page cannot help: on MrBeast's About page his own accounts and his
sponsors' accounts sit in the same description element (verified
2026-10-21). Rendered, they are unmistakable — Facebook shows the page
name and its follower count, Instagram puts the handle in the title, and a
profile that does not exist says so.

## Outcomes

| Outcome | When | Shown as |
|---|---|---|
| `FOUND` | the account exists **and** matches the creator (or the creator's own bio linked it) | Found — with the evidence |
| `NOT_FOUND` | the account does not exist | dropped (never shown) |
| `NO_MATCH` | the account exists but nothing ties it to this creator | Not this creator |
| `UNKNOWN` | blocked, rate limited, or a timeout | Unknown — never "missing" |

## Evidence

Every `FOUND` carries why it is believed:

- `bio_link` — the link came from the creator's own channel bio (strongest)
- `back_link` — the account's page links back to the YouTube channel (strong)
- `name_match` — the page's display name equals the channel title (medium)
- `handle_match` — the page's handle equals the channel handle (medium)

Two of the four are enough for `FOUND`. One is `NO_MATCH`.

## Acceptance criteria

1. A real account → `FOUND` with at least one evidence item.
2. A made-up account → `NOT_FOUND` (and it is dropped from the results).
3. An account that exists but belongs to somebody else → `NO_MATCH`.
4. A blocked platform → `UNKNOWN`, never `NOT_FOUND`.
5. A candidate from the creator's own bio is `FOUND` even when the page
   cannot be read (the self-claim is the evidence) — but it is marked
   `bio_link` so the user knows the page itself was not read.
6. The browser is closed after every run, including on failure.

## Boundaries

- **Always:** one browser context per run; a navigation timeout on every
  page; a per-platform cooldown; never send the user's own cookies to a
  platform unless the user configured that platform's cookies.
- **Ask first:** anything that needs a login.
- **Never:** solve a CAPTCHA, or send a request that bypasses a rate limit.

## Verification

- Offscreen test with a saved page fixture: real / fake / blocked / unrelated.
- Live check: `facebook.com/MrBeast` vs a made-up page → different outcomes.
