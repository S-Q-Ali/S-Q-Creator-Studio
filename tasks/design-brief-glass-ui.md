# Design Brief: Glass UI (black · white · grey · blue)

**Status:** approved 2026-11-03 — the token system, the strict-palette state
language, and the single-module decision were each confirmed by the user. The
task list is `tasks/todo-glass-ui.md`, the plan is `tasks/plan-glass-ui.md`. No
stylesheet is edited until that plan is executed in order.

**Brief.** Restyle the whole PySide6 app from "neon cyan on near-black" to
glassmorphic, using only black, white, grey and blue. Today's look is
documented in README:58 and pinned by tests.

## The one technical constraint that shapes everything

Qt QSS has no `backdrop-filter` and no blur-behind. `QGraphicsBlurEffect` blurs
a widget's own contents, not what is behind it, and putting any
`QGraphicsEffect` on a container makes it one composited layer and breaks child
hover repaints. There is no `paintEvent` anywhere in the app today, and
`test_qss_parses.py` / `test_neon_theme_qt.py` fail on any Qt-invalid property
(`box-shadow`, `opacity`, `transition`).

So this is **faux glass**, done honestly:

1. one app-level **backdrop** widget paints the depth once — a vertical
   blue-black gradient plus two soft radial light pools, no per-frame work;
2. panels are translucent fills over that known backdrop, with a 1px light
   hairline on the top edge and a radius, and a drop shadow only on leaf panels;
3. every text token is defined together with its **flattened composite** colour
   (what the translucent fill actually resolves to over the backdrop), and the
   existing WCAG calculator in `tests/test_ui_layout.py:40-53` asserts contrast
   against that composite — so "it looks fine" is never the argument.

Tables, combo popups, tooltips and message boxes stay **opaque**. Translucent
rows over `setAlternatingRowColors(True)` (`agent_tab.py:328`,
`social_discovery_page.py:212`) produce moiré, and native popups sit over an
arbitrary desktop.

## Colour tokens

| Token | Value | Job |
|---|---|---|
| `void` | `#06080C` | backdrop base — blue-black, never a flat `#000` panel |
| `graphite` | `#12161D` | the flattened fill a card resolves to; the contrast reference |
| `chalk` | `#EDF1F5` | primary text, lit chips, the active-segment fill |
| `smoke` | `#7C8794` | secondary text and muted structure — 4.9:1 on `graphite` |
| `signal` | `#2F81F7` | the single blue: focus, progress, primary action |
| `signal_hi` / `signal_deep` | `#8FC1FF` / `#1B4F9C` | hover and pressed, same hue |

Glass alphas live in a **separate** token set, not in `C`, because
`test_theme.py:38-40` requires every `C` value to be a 7-char hex: fills at
`rgba(255,255,255,0.04 / 0.07 / 0.10)`, hairline at `rgba(255,255,255,0.14)`,
`signal` glow at `rgba(47,129,247,0.28)`. Three elevation levels only — glass
as depth, not as decoration.

## Type

Fonts are the platform fault line as much as the design one: `core/theme_neon.py:79`
hardcodes `"Segoe UI"`, which does not exist on macOS or Linux. The tests are
already safe — `tests/conftest.py:13-44` loads the font folder of whichever OS
runs them, from Phase E — so it is the app that names a Windows face, not the
harness. The stack becomes an ordered fallback (system UI on each OS),
the scale keeps the existing `DENSITY` numbers in `theme.py:49-76`
(13/19/10 comfortable, 12/17/9 compact), and personality comes from **weight
and the wordmark**, not a new face: `#Wordmark` is drawn once with `QPainter`
into a pixmap — the same idiom `widgets.py:27` `shield_pixmap` already uses — so
the logotype is part of the glass, and no font file is added.

QSS has no `letter-spacing`, so the ALL-CAPS eyebrow treatment the current sheet
leans on is done with real strings, not fake tracking.

## Layout

Structure is untouched — left rail + segmented nav + `QStackedWidget`
(`main_window.py:197`, `:393`, `:434`), because `test_ui_layout.py:226-236`
asserts the stack. The change is material, not geometry:

```
┌ backdrop: void → graphite, one blue light pool behind the rail ────────┐
│ ┌ glass rail ─────────┐   ┌ lit glass slab = active workspace ──────┐  │
│ │ wordmark (drawn)    │   │  opaque cards, hairline tops, blue fill │  │
│ │ nav: 3 glass segs   │   │  progress = signal, no hue shift        │  │
│ └─────────────────────┘   └─────────────────────────────────────────┘  │
└ one 28px status bar ───────────────────────────────────────────────────┘
```

`theme_neon.py:76-81` sets `background-color` on the bare `QWidget` selector, so
it cascades onto every widget; selective glass means replacing that with an
explicit container background and letting panels override it. The
`#MusicPage` objectName currently has no rule at all in either sheet — it gets
one.

## Principles

1. Three elevations, one light source (top-left), no gradient washes used as
   decoration.
2. Boldness is spent once: the drawn wordmark and the lit active segment.
   Everything else stays quiet.
3. State is legible without colour (see decision below) — the 7 statuses in
   `theme.py:33-41` are today teal/pink/purple/amber, none of which exist in
   this palette.
4. Keyboard focus gets a real visible ring — `QPushButton` has **no** `:focus`
   rule in either current sheet, and grey glass would swallow it.
5. Motion only answers an action (tab change, progress, result). No ambient
   animation; the existing three `_neon_glow` effects (`main_window.py:236`,
   `:342`, `:476`) become a single restrained `signal` glow or go away.

## What a restyle must re-point (not silently break)

- `tests/test_theme.py:48-49` pins `C["accent"] == "#22D3EE"` and `:56-57` pins
  the sheet starting at `QWidget`; `test_neon_theme_qt.py:15-21` pins `#0a0a0a`,
  `#00d4ff` and `qlineargradient` in the rendered QSS; `:24-29` pins that density
  keeps neon. These are assertions about the *old* look — they are rewritten to
  the new tokens, never deleted.
- `tests/test_ui_layout.py:207-223` requires the checked tab's `color` and
  `background` to be **6-digit hex** and reach 4.5:1 — a translucent glass tab
  fails the regex by construction, so this test moves to the flattened composite.
- `test_agent_tab.py:25-27` asserts the literal source line
  `from s_q_ali_media_downloader.theme import C` exists — that import stays.
- 19 `setStyleSheet()` call sites live outside the theme modules (6 in
  `settings_page.py`, 5 in `widgets.py`, 4 in `agent_tab.py`, 2 in
  `main_window.py`, 1 each in `music_page.py`, `activity_log.py`) and about 20
  hardcoded semantic hex literals sit in `settings_page.py:538-641`,
  `music_page.py:364`, `main_window.py:85/96/97/604`, `widgets.py:27`.
- `social_discovery_page.py:320-326` uses raw `Qt.gray` / `Qt.green` — off
  palette by construction.
- `screenshots/*.png` (4, all Oct 26) and README:58 ("electric cyan") go stale.

## The three-module decision it forces

`theme.py`'s stylesheet (445 lines) is **never rendered** — `theme.py:432-433`
skips the swap when the `s_q_theme` property is `neon` — yet three tests assert
against it, while `core/theme_neon.py` is what users actually see, and the two
palettes already disagree. Recommended: converge on one token module
(`theme.py`), delete the duplicate QSS, and let the tests finally describe the
rendered app. The alternative is restyling `theme_neon.py` and leaving dead CSS
plus a lying test suite in place.

Re-checked against the code today, and it is worse than "a lying test suite":
`tests/test_ui_layout.py:207-223` regexes `stylesheet("comfortable")` for the
checked tab's colours and demands 4.5:1, and `tests/test_qss_parses.py:12,28`
hands `STYLESHEET` to Qt's parser — both read the sheet `app.py:87-88` replaced.
So the app's readability and its QSS validity are asserted against CSS nobody
renders, while the rendered sheet is checked by `test_neon_theme_qt.py` only for
three literals and a warning-free parse. Converging is not a tidiness call: it
is what makes the contrast gate mean something again.

`ui/stylesheets/` is an empty folder and `themes/*.html` are the two design
concept mockups from Oct 25 — no Python reads either. They are cleanup candidates
in the same pass, not part of the styling.

## Module map (this initiative)

| Module id | Responsibility | Depends on |
|---|---|---|
| `tokens-unify` | One palette/density module; dead QSS deleted; tests re-pointed at the rendered sheet | — |
| `state-language` | Statuses re-expressed in black/white/grey/blue; the ~20 hardcoded literals and raw `Qt.gray/green` call sites moved onto tokens | `tokens-unify` |
| `glass-treatment` | Backdrop paint + panel alphas/hairlines/radius + focus ring + opaque tables/popups | `tokens-unify` |
| `verify-and-docs` | Offscreen renders at all four supported sizes, contrast assertions on composites, new screenshots, README:58 + CHANGELOG | `state-language`, `glass-treatment` |

Build order: `tokens-unify` → `state-language` ∥ `glass-treatment` →
`verify-and-docs`.

## Honest limit

I can render the app offscreen and inspect PNGs (`tests/render_neon_screenshots.py`
already does this), but alpha compositing over a real desktop, and how the glass
reads on a physical panel, can only be judged by you running the app. I will not
report the look as "verified" — only the geometry, contrast and parse-clean
stylesheet will be.

## State language (decided: strict palette)

The seven statuses in `theme.py:33-41` — today teal, pink, purple and amber —
are re-expressed as luminance tiers of one blue family plus neutrals, with
label weight and the word already printed on the card carrying the rest:

| State | Spine | Label |
|---|---|---|
| Queued | `smoke` (neutral) | normal |
| Paused | `slate` (neutral, dimmer) | normal |
| Waiting | `signal_deep` | normal |
| Downloading | `signal` | 600 |
| Retrying | `signal_hi` | 700 |
| Completed | `chalk` | 700 |
| Failed | `chalk`, inverted chip | 800 on the chip |

No glyph is added: `theme_neon.py:256-259` records that emoji fall back to a
wider face than `QFontMetrics` measures and clip the 285px rail, and the layout
tests fail on clipped text. Each spine must clear 3:1 against `graphite`
(WCAG 1.4.11) and each label 4.5:1, checked on the flattened composite.

The rejected alternative — keeping a red for failures — would have read faster
but broke the four-colour brief, so it stays out. If a greyscale screenshot of
the queue cannot tell `Failed` from `Completed`, this decision is wrong and the
chip gets stronger rather than the palette getting wider.
