# Spec: `social-report` — the AI Finder mode: input, results, export

**Objective:** a mode in the AI Finder tab where the user pastes one channel
or a list of them, and gets a readable answer: which Facebook / Instagram /
TikTok accounts belong to that creator, how sure we are, and why.

**No modals, no cramped layout.** The results live in the page, in one table
with room to breathe.

## The screen

```
┌ Social Discovery ────────────────────────────────────────────────┐
│ [ https://youtube.com/@mkbhd                    ]  [ Find ]        │
│ ⌄ paste several, one per line                                    │
├───────────────────────────────────────────────────────────────────┤
│  Channel            Facebook        Instagram        TikTok        │
│  ─────────────────────────────────────────────────────────────    │
│  Marques Brownlee   ✓ Found         ✓ Found          ? Unknown    │
│  @mkbhd             fb.com/MKBHD    ig.com/mkbhd     blocked      │
│                     ↳ linked from your channel bio                │
│  ─────────────────────────────────────────────────────────────    │
│  MrBeast            ~ Suggested     ~ Suggested      ~ Suggested   │
│  @MrBeast           fb.com/mrbeast  ig.com/mrbeast   tt.com/...   │
│                     ↳ model: same handle on all platforms         │
└───────────────────────────────────────────────────────────────────┘
```

- **Input**: one URL/handle/name, or several (one per line) for a batch run.
- **Progress**: a line under the input ("checking 3 of 7 channels…"), never
  a modal.
- **Rows**: one per channel, the platforms as columns, the evidence under
  the row it belongs to.
- **A row expands** to show the links, the evidence and the reason.
- **Export**: CSV and JSON of the table (the research module already has an
  exporter — reuse it).

## Vocabulary (the same words everywhere)

| Badge | Meaning |
|---|---|
| **Found** | the account exists and belongs to this creator |
| **Suggested** | the model proposed it; not confirmed |
| **Not this creator** | the account exists but belongs to somebody else |
| **Unknown** | we could not check (blocked / rate limited) |
| — | nothing proposed and nothing found |

## Acceptance criteria

1. One channel → one row, filled in.
2. A list of channels → a row per channel, in the order the user gave them.
3. A channel that cannot be resolved shows a clear reason in its row; the
   other rows are unaffected.
4. "Found" and "Suggested" are visually distinct — a suggested account must
   never look like a found one.
5. The export contains every row, with the status and the evidence.
6. Nothing is shown in a modal; the whole flow stays in the page.
7. The run can be cancelled and the browser is closed.

## Boundaries

- **Always:** the worker runs off the UI thread; the table updates as rows
  finish; the run can be cancelled.
- **Ask first:** a new export format.
- **Never:** freeze the window while a run is in progress; open a dialog for
  a result.

## Verification

- Offscreen test: a fake resolver + a fake verifier → the table shows the
  right badges, the right order, and the evidence.
- Live check: two channels, one with a bio link and one without.
