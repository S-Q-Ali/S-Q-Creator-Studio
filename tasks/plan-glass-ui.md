# Implementation Plan: Glass UI (black · white · grey · blue)

**Brief:** `tasks/design-brief-glass-ui.md` — approved 2026-11-03, together with
the three decisions below. Tasks and acceptance criteria live in
`tasks/todo-glass-ui.md`.

## The three approved decisions

1. **Strict palette.** No red, no amber, no violet. The 7 queue statuses are
   told apart by luminance tier + label weight + the word already printed on the
   card; `Failed` additionally gets the inverted chip. Nothing else in the app
   gets an off-brief hue.
2. **One theme module.** `theme.py` owns the tokens, the density and the single
   rendered stylesheet. `core/theme_neon.py` and `ui/themes.py` are deleted;
   `app.py` stops importing them. After this, the contrast gate and the QSS
   parse guard are asserting against what users actually see.
3. **Now, on top of the 30 unpushed commits.** The restyle touches no file the
   cross-platform work still needs, and it is verifiable offscreen, so it does
   not wait on a CI result.

## Dependency graph

```
tokens-unify ──┬── state-language ──┐
               └── glass-treatment ─┴── verify-and-docs
```

`tokens-unify` is first and highest-risk: it deletes a module, so everything
that imports it has to move in the same breath. `state-language` and
`glass-treatment` then touch different lines of the same sheet and can be done
in either order (or by two agents), but not in one commit each — each leaves
the app looking complete on its own.

## Commands (the repository's own)

```
Test (focused):  QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_theme.py -q
Test (full):     QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -m "not live"
Lint:            ./source/venv/Scripts/python.exe -m ruff check src tests
Render PNGs:     QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe tests/render_glass_screenshots.py
Graph:           graphify update .
```

## Architecture notes that constrain every task

- **Faux glass, on purpose.** QSS has no `backdrop-filter`; `QGraphicsBlurEffect`
  blurs a widget's own contents, and any `QGraphicsEffect` on a container makes
  it one composited layer and breaks child hover repaints. Depth comes from one
  static `Backdrop` `paintEvent` (a vertical gradient plus two radial pools)
  with translucent panels over it — no per-frame work, no window-level alpha.
- **Comfortable density is the current look.** `theme.py:50-62` (13/19/10 px,
  8/14 and 8/10 padding) matches the literals in the live neon sheet, so
  rendering the sheet from tokens should be visually near-identical at
  comfortable and finally honour compact. A test pins that.
- **Opacity where function needs it.** Tables (`setAlternatingRowColors` at
  `agent_tab.py:328`, `social_discovery_page.py:212`), combo popups, tooltips,
  message boxes and the activity log read surface stay solid; moiré over a
  translucent row is a real defect, and native popups sit on an arbitrary desktop.
- **Contrast is asserted on the flattened composite**, not on the alpha. Each
  text token is stored with the opaque colour it resolves to over the backdrop,
  and the existing `contrast()` helper in `tests/test_ui_layout.py:40-53` checks
  that composite at ≥4.5:1 for text, ≥3:1 for the status spine (WCAG 1.4.11).
- **No new glyphs in narrow places.** `theme_neon.py:256-259` records that emoji
  fall back to a wider face than `QFontMetrics` measures and clip the 285px rail;
  the status language therefore uses luminance and weight, not symbols.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Translucent `background` not compositing over the parent's paint | High — the whole look | Prove it in the first sheet commit with an offscreen PNG before any panel is styled |
| Qt warning on a QSS property (`border-top`, `rgba`, focus rules) silently drops every rule after it | High | `test_qss_parses.py` extended to the rendered sheet, run on every task |
| Deleting `theme_neon.py` breaks an importer | Medium | Grep says only `app.py:87-88`, `ui/themes.py`, and four test files |
| Clipping and click-target tests fail at 1280x720 in compact | Medium | Run `tests/test_ui_layout.py` after each surface change, not only at the end |
| A blue token fails the 3:1 spine gate | Low | The token moves within its hue family; the family is not renegotiated |
| Screenshots and README:58 go stale | Low | `verify-and-docs` replaces them in the same pass |

## Honest limit

Offscreen renders show geometry, contrast and parse-cleanliness. How alpha
reads on a physical panel, and how the glass behaves over a real desktop, can
only be judged by the user running the app. The plan never reports the look as
"verified" — only those three properties.

## Checkpoints

- **After `tokens-unify`:** one sheet, one module, full suite green, PNGs of the
  app unchanged at comfortable density.
- **After `state-language` + `glass-treatment`:** every screen on the glass sheet,
  7 statuses distinguishable in a greyscale screenshot, no test asserting on a
  stylesheet the app does not render.
- **After `verify-and-docs`:** PNGs at 4 sizes × 2 densities reviewed, README and
  CHANGELOG describing the build that exists, graph refreshed.
