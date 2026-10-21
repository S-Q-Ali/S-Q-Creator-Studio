# Spec: `social-resolve` — find the channel's real name, handle and bio

**Objective:** turn whatever the user pasted — a channel URL, an `@handle`, or a
channel name — into one channel record, and read the channel's **own** bio
(the rendered "About" page and its links), because that is the only evidence
that is a self-claim: the creator pointing at their own accounts.

**Why Playwright:** the About page and its links are rendered by JavaScript.
The plain HTTP response is a shell — yt-dlp's description misses the links
section for most channels. A real browser sees what a visitor sees.

## Input forms

| Input | Example | How it is resolved |
|---|---|---|
| Channel URL | `https://www.youtube.com/@mkbhd` | open the page, read the name + handle |
| Bare handle | `@mkbhd` | `https://www.youtube.com/@mkbhd` |
| Channel name | `Marques Brownlee` | YouTube search (yt-dlp) → the top match; the user picks if there is more than one |

## Output

```python
@dataclass
class ResolvedChannel:
    channel_id: str          # UC… when known
    title: str               # the channel's display name
    handle: str              # without the @, e.g. "mkbhd"
    url: str
    description: str         # the channel's own description, trimmed
    bio_links: list[str]     # the social links the page shows — candidates
    subscribers: int
    source: str              # "url" | "handle" | "search"
```

**The page cannot say whose links they are.** On MrBeast's About page his own
accounts (`facebook.com/MrBeast`, `instagram.com/mrbeast`) sit in the same
description element as the sponsors he mentions (`johnpeelfitness`, a car
dealership) — verified 2026-10-21. So every social link the page shows is a
**candidate**; whether it belongs to the creator is the verifier's question,
and it is answered by opening the account.

## Acceptance criteria

1. A URL or handle resolves to a record with a non-empty `title` and `handle`.
2. `bio_links` holds the social links the About page shows, unwrapped from
   YouTube's redirect and normalised to https.
3. A name that matches several channels does not silently pick one: the user
   is shown the candidates and picks.
4. A channel that cannot be opened produces a clear error, not an empty record.
5. The rendered page is used, not the HTML shell: the test asserts the
   channel's name and handle are read from the rendered page.

## Boundaries

- **Always:** run the browser off the UI thread; close the browser on exit;
  give every navigation a timeout; never log a cookie or a session token.
- **Ask first:** any change to the app's dependency list (the browser binary
  is ~150 MB — the installer must either bundle it or fetch it on first run).
- **Never:** execute JavaScript that the page did not already run; type into
  a login form; bypass a CAPTCHA.

## Verification

- Offscreen test: a fake page (saved HTML) → the record is parsed out of it.
- Live check: `@mkbhd` → title "Marques Brownlee", handle "mkbhd", and the
  About links are read.
