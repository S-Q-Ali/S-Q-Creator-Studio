# Task list: Glass UI

Plan: `tasks/plan-glass-ui.md` · Brief: `tasks/design-brief-glass-ui.md`
Commands are the repository's own (see the plan). One commit per task.

## Phase 1 — tokens-unify

### Task 1: The glass token set and a sheet rendered from it

**Description:** `theme.py` gains the six base tokens (`void`, `graphite`,
`chalk`, `smoke`, `signal`, plus `signal_hi`/`signal_deep`), a separate `GLASS`
alpha set, and a `render(density)` sheet builder that produces the glass QSS.
Nothing is applied yet — the old live sheet still wins. Written test-first: the
sheet exists and parses before it is judged by eye.

**Acceptance criteria:**
- [x] `theme.py` exposes `GLASS` (fills at 0.04/0.07/0.10, hairline 0.14, glow 0.28) as its own dict, so `test_theme.py:38-40`'s "every `C` value is a 7-char hex" rule keeps holding.
- [x] The rendered sheet contains no `box-shadow`, `opacity`, `transition` or `backdrop-filter`, and parses with zero Qt warnings.
- [x] Every text token is paired with its flattened composite colour in one table both the sheet and the tests read.

**Verification:**
- [x] `pytest tests/test_theme.py tests/test_qss_parses.py -q` passes, and each new test failed before the change.
- [x] `ruff check src tests` clean.

**Built as:** the builder kept its existing name `stylesheet(density)` (not
`render`) and the tokens kept the `C` keys the ~40 call sites already read, so
this task changed no consumer. Two of the brief's hand-written numbers did not
survive the arithmetic: the panel composite is `#17191D`, not `#12161D`, and
`signal_deep` at 2.28:1 cannot be a spine, so it became the action fill
`accent_deep #3A6BB0` (4.73:1 with chalk) and the pressed/selected blues moved
onto it.

**Dependencies:** none · **Scope:** S (2 files: `theme.py`, `tests/test_theme.py`)

### Task 2: One theme module — the app stops rendering two stylesheets

**Description:** `app.py` applies the sheet from Task 1; `core/theme_neon.py`
and `ui/themes.py` are deleted along with the `s_q_theme` property check, and
the assertions still worth keeping from `tests/test_neon_theme.py` and
`tests/test_neon_theme_qt.py` are re-pointed at the rendered sheet instead of
deleted. `tests/quick_neon_test.py` — a print script pytest collects but which
asserts nothing (`no tests collected`) — goes with them.

**Acceptance criteria:**
- [x] One stylesheet reaches `QApplication`; no module under `src/` mentions `neon`.
- [x] `tests/test_agent_tab.py:25-27`'s literal import line still exists in `agent_tab.py`.
- [x] Every old neon assertion is either rewritten against the new sheet or removed with a one-line reason in the commit message — none silently dropped.

**Verification:**
- [x] Full offline suite green; `pytest -q` output shows the suite count and no skips added.
- [x] Offscreen render of the main window produces a PNG on the glass sheet.

**Built as:** 800 offline tests green, no skips. `test_neon_theme_qt.py` became
`test_glass_theme_qt.py` with its density assertion flipped (density now *must*
re-render the same tokens); its other two assertions are already made against
the rendered sheet by `test_theme.py` and `test_qss_parses.py`. `test_neon_theme.py`
and `quick_neon_test.py` asserted nothing at all — both were print scripts, and
`quick_neon_test.py` matched pytest's default `*_test.py` glob, so it applied
the neon sheet inside the test session. `render_neon_screenshots.py` was renamed
with them, and `_neon_glow` became `_glow` on `C["accent"]` because its default
was the old electric blue literal. README's theme bullet moved with the build,
since from this commit the two would disagree.

**Still true here:** the render shows the restyle is only half-applied — the
usage notice and the GitHub chip are still warm, and the queue area is a flat
void. Those are Tasks 4, 5 and 6, not regressions from this one.

**Dependencies:** Task 1 · **Scope:** M (6 files: `app.py`, `theme.py`, delete `core/theme_neon.py` + `ui/themes.py`, `tests/test_theme.py`, delete/merge 3 test files)

### Task 3: Density finally means something

**Description:** `apply_density()` stops skipping the stylesheet swap, so
compact actually restyles. `comfortable` must reproduce today's literals
(13/19/10 px, 8/14 and 8/10 padding) so the switch is visually flat; `compact`
uses the existing `DENSITY` numbers.

**Acceptance criteria:**
- [x] A test pins that the comfortable render emits today's font sizes and paddings.
- [x] Toggling density re-renders the same tokens and leaves the sheet parse-clean.
- [x] `test_ui_layout.py`'s clipping and click-target tests pass at all four sizes in both densities.

**Verification:**
- [x] `pytest tests/test_ui_layout.py tests/test_theme.py -q`.

**Built as:** the swap itself stopped being skipped in Task 2, when the
`s_q_theme` check went with the modules it guarded. What was left is proof.
`test_ui_layout.py`'s two size tests are now parametrised over both densities —
8 extra tests, all green, and they had never run in compact before because the
density pass never reached the stylesheet. The parse guard covers both renders
and one test pins that `STYLESHEET` *is* the comfortable render, so the sheet
the tests read and the sheet `app.py` applies cannot diverge again.

**Dependencies:** Task 2 · **Scope:** S (2-3 files: `theme.py`, `tests/test_theme.py`, `tests/test_ui_layout.py`)

### Checkpoint: tokens-unify
- [x] Suite green, PNG reviewed, one module owns the look, no test asserts on CSS the app does not render.

The reviewed PNG is the 1568×1097 queue render from Task 2: the void, the panel
and the action blue all land where the tokens say they do, and the two warm
spots still visible (the usage notice, the GitHub chip) are the Tasks 4-5
backlog, not breakage. `graphify update .` has not been re-run since Task 2
deleted two modules — do it with the next commit.

## Phase 2 — state-language

### Task 4: Seven statuses in four colours

**Description:** `STATUS_COLORS` becomes the strict palette: `Queued` smoke and
`Paused` slate (neutral, dimmer); `Downloading` `signal`, `Retrying`
`signal_hi`, `Waiting` `signal_deep` (one blue family, three luminances);
`Completed` chalk; `Failed` chalk on an inverted chip, and label weight carries
the actionable states. No new glyph anywhere.

**Acceptance criteria:**
- [x] All seven tokens are distinct and every spine is ≥3:1 against `graphite`; the status label text is ≥4.5:1.
- [x] `Failed` and `Completed` are identifiable in a greyscale screenshot of the queue.
- [x] No hue outside black/white/grey/blue remains in `theme.py`.

**Verification:**
- [x] A new contrast test using `tests/test_ui_layout.py:40-53`'s `contrast()` fails before the tokens change and passes after.
- [x] `pytest tests/test_theme.py tests/test_ui_layout.py -q`, full suite green.

**Built as:** RED confirmed — `Waiting as a label fails AA (3.28:1)`, which is
why the brief's `signal_deep` for that state became the new `accent_mid
#6FB2F9`; `#3A6BB0` stays fill-only, where its 3.28:1 still clears the 3:1
non-text bar. Four tests added: spines ≥3:1 on a panel, labels ≥4.5:1 on a
panel, the Failed chip is chalk with void text, and the three groups read
(apart) — grey does not move, the three moving states are blue, chalk has
finished, and `Queued` is dimmer than `Paused`.

`JobCard.refresh()` now sets the label weight from `STATUS_WEIGHTS` and paints
the one inverted chip. The greyscale criterion is tested as it sounds: a real
window on the glass sheet, two cards driven through `on_result`, and each
status label grabbed and averaged — **215.5 vs 41.4** grey, asserted as a gap
over 60. The no-warm-hue criterion is read off the *rendered* sheets, both
densities, not just the token dictionary: a literal left in the CSS would
otherwise reach the screen unmeasured. Full offline suite: 818 passed,
19 deselected.

**Dependencies:** Task 2 · **Scope:** M (4 files: `theme.py`, `ui/widgets.py`, `ui/main_window.py`, `tests/test_theme.py`)

### Task 5: The hardcoded colours move onto the tokens

Three commits, grouped by file so each is reviewable:

- [x] **5a** — `ui/settings_page.py`: 6 `setStyleSheet` sites and the ~19 hex
  literals at `:538-641` read from tokens; the per-OS storage wording untouched.
  **Built as:** the four warm literals map onto the queue's vocabulary —
  `faint` waits on you, `waiting` is the app working, `done` and `failed` are
  over. Two of the six sites were constant colours in a call site, so they are
  sheet rules now: the grid's row labels take a new `role="fieldLabel"`, and
  `key_warning` takes the `error` role it always meant. The identity line's
  pinned `font-size: 10px` is gone — `role="hint"` renders the caption size
  anyway, so it now scales with density instead of fighting it. Suite green
  (818), no hex literal left in the file.
- [x] **5b** — `ui/widgets.py`, `ui/activity_log.py`, `ui/music_page.py`: 7 sites,
  `music_page.py:364` and `widgets.py:27` included; the `shield_pixmap` idiom
  stays, it is what Task 8 reuses.
  **Built as:** the shield's amber default is the amber token (lit blue now),
  the music page's pink is `failed`, and the activity log's inline
  `font-weight: bold` is gone — `role="section"` is the hint role plus 700, so
  the sheet already had the rule.
- [x] **5c** — `ui/agent_tab.py`, `ui/main_window.py`, `ui/social_discovery_page.py`:
  the remaining sites, the raw `Qt.gray`/`Qt.green` at
  `social_discovery_page.py:320-326`, and the three `_neon_glow` calls
  (`main_window.py:236`, `:342`, `:476`) reduced to one restrained `signal`
  glow on the primary action — or removed if the glass reads fine without it.
  **Built as:** the discovery table's `Qt.GlobalColor.green/gray` became the
  channel table's verdict language (`done` / `amber` for unknown / `failed`),
  so the two tables that describe the same finding colour it the same way. The
  four `font-weight` sheets in `agent_tab.py` are one `role="hintStrong"` now;
  the shield badge's `background: transparent` moved to `#ShieldBadge`; the
  social buttons' GitHub and LinkedIn fills are tokens, because both are
  already inside the brief — one near-black, one blue — and a button that says
  GitHub in an invented hue is a button nobody recognises (both pairs are in
  `TEXT_SURFACES`, so their chalk labels are measured, not assumed). One glow
  survives, on Start. `chip_left` stopped borrowing the Retrying blue: a count
  is not a state.

**Acceptance criteria:**
- [x] `grep -rn "setStyleSheet" src/` returns only the theme module and the widgets that genuinely need a per-instance colour, each of which uses a token.
- [x] No 6-digit hex literal outside `theme.py`'s token dicts.
- [x] Behaviour unchanged: no settings, no queue logic, no download path edited.

**Verification:**
- [x] Full offline suite green after each of 5a/5b/5c; `ruff check src tests` clean.
- [x] A guard test reads every `.py` under `src/` and fails on a quoted hex outside `theme.py`.

**Built as:** 5a/5b/5c. Thirteen `setStyleSheet` calls are left in `src/`; two of
them are the theme applying itself (`app.py`, `apply_density`). The other
eleven are the queue card — spine, status chip, placeholder title, error line,
chip value — the two key-test statuses, the identity line, the music status and
the two brand buttons: every one a colour that changes per instance, and every
one a token. The hex rule is now machine-enforced:
`test_no_colour_literal_outside_the_token_table` walks the package, so the next
literal added in a page fails rather than going unnoticed.

Suite after 5c: **819 passed, 19 deselected**. One run at the end of the task,
not one per commit — the per-slice runs were the four files each slice touches.

**Dependencies:** Task 4 · **Scope:** M each (1-3 files per commit)

### Checkpoint: state-language
- [x] Suite green, no hex literal left outside `theme.py`, no colour named by a
      hue the brief does not allow.
- [x] The queue, Music, discovery and Settings pages rendered offscreen and
      read as pixels, not as arithmetic.

Phase 2 leaves the app readable: seven statuses told apart by luminance and
weight, verdict tables saying the same thing in the same words, and a guard
test that fails the next time a page reaches for `#` instead of a token.

The render review found two things the suite could not see:

- The active nav tab bolded itself out of its own width. `sizeHint()` is
  measured with the calm font, so `:checked { font-weight: 700 }` painted
  wider text into a narrower box and ate the last letter of "Inspector" —
  while `test_ui_layout.py` stayed green, because it measures the calm font
  too. Weight now belongs to the base rule only, and a sheet-wide guard test
  refuses any pseudo-state that changes the font.
- A completed job had a full *blue* bar. Blue is the moving colour; the widest
  element in the row was contradicting the word COMPLETED above it. A finished
  bar is now chalk.

## Phase 3 — glass-treatment

### Task 6: One backdrop, painted once

**Description:** a `Backdrop` widget with a `paintEvent` that draws the
`void`→`graphite` vertical gradient and two soft `QRadialGradient` light pools
behind the rail. It is the app's first and only `paintEvent`, and the depth
source every translucent panel composites against.

**Acceptance criteria:**
- [ ] The backdrop paints in `resizeEvent`-free code: one gradient object per paint, no effect on a container, no timer.
- [ ] An offscreen PNG shows the panels reading as surfaces above the backdrop, not as flat rectangles.
- [ ] `test_ui_layout.py`'s structure assertions (`:226-236` stack, rail) still pass.

**Verification:**
- [ ] `pytest tests/test_gui.py tests/test_ui_layout.py -q` green, and a reviewed PNG.

**Dependencies:** Task 2 · **Scope:** M (3 files: `ui/widgets.py` or `theme.py`, `ui/main_window.py`, one test file)

### Task 7: Panels, hairlines, focus

**Description:** the sheet gets the three elevations (`GLASS` fills at
0.04/0.07/0.10), a 1px `rgba(255,255,255,0.14)` top hairline on leaf panels,
radii, and a real `:focus` ring on buttons and inputs — the current sheets have
no focus rule at all, and grey glass swallows one. Tables, combo popups,
tooltips, message boxes and the log's read surface stay opaque. `#MusicPage`,
which has no rule in either current sheet, gets one.

**Acceptance criteria:**
- [ ] `theme_neon.py:76-81`'s `background-color` on the bare `QWidget` selector is replaced by an explicit container background, so the sheet no longer cascades onto every widget.
- [ ] Keyboard focus is visible on every interactive control in a screenshot, and `test_ui_layout.py:197` ("no stylesheet cascades onto the workspace tabs") still holds.
- [ ] The checked tab's readability test moves to the flattened composite and still demands 4.5:1.

**Verification:**
- [ ] `pytest tests/test_qss_parses.py tests/test_ui_layout.py tests/test_gui.py -q`; full suite green; PNGs at all four sizes reviewed.

**Dependencies:** Task 6 · **Scope:** M (3 files: `theme.py`, `tests/test_ui_layout.py`, `tests/test_qss_parses.py`)

### Task 8: The wordmark, drawn

**Description:** `#Wordmark` is painted once with `QPainter` into a pixmap —
the idiom `widgets.py:27` `shield_pixmap` already uses — so the logotype is
glass rather than text in a font nobody guarantees. Personality is spent here
and nowhere else.

**Acceptance criteria:**
- [ ] The pixmap is generated once and reused; a resize does not repaint it per frame.
- [ ] It is legible at both densities and in both the 280px and 248px rail.

**Verification:**
- [ ] A test asserts the rail's wordmark has non-empty geometry at both densities; `test_ui_layout.py` clipping green.

**Dependencies:** Task 7 · **Scope:** S (3 files: `ui/widgets.py`, `ui/main_window.py`, `tests/test_gui.py`)

### Task 9: A font stack that exists on each OS

**Description:** `"Segoe UI"` (hardcoded at `theme_neon.py:79`, now in the sheet)
becomes an ordered per-OS fallback. No font file is added, and the tests already
load the right font folder per OS (`conftest.py:13-44`), so this is what makes
the type honest on the Linux and macOS builds.

**Acceptance criteria:**
- [ ] The stack names the system UI face on Windows, macOS and Linux, in that order, with a generic fallback.
- [ ] No clipping appears at any supported size on this machine.

**Verification:**
- [ ] `pytest tests/test_ui_layout.py tests/test_suite_portability.py -q`.

**Dependencies:** Task 7 · **Scope:** XS (1-2 files: `theme.py`, one test)

### Checkpoint: glass treatment
- [ ] Every screen on the glass sheet; opaque where function demands it; contrast asserted on composites; PNGs reviewed.

## Phase 4 — verify-and-docs

### Task 10: Renders, screenshots, and the honest report

**Description:** `tests/render_glass_screenshots.py` becomes
`tests/render_glass_screenshots.py` and renders every page at 4 sizes × 2
densities; the four stale `screenshots/*.png` (all Oct 26) are replaced.

**Acceptance criteria:**
- [ ] Fresh PNGs for Download, Music, Social Discovery, Agent and Settings.
- [ ] The report states geometry, contrast and parse-cleanliness only — never "looks right".

**Verification:**
- [ ] `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe tests/render_glass_screenshots.py` writes the files, and the user is asked to run the app for the judgement that cannot be automated.

**Dependencies:** Tasks 4-9 · **Scope:** S (2 files + 4 PNGs)

### Task 11: Docs that match the build

**Description:** README:58's "**Neon theme** — electric cyan on a near-black
surface" becomes the glass wording, CHANGELOG gets the entry, `graphify update .`
runs, and the ask-first cleanups are raised rather than done: `themes/*.html`
(the two Oct 25 concept mockups no code reads) and the empty
`ui/stylesheets/` folder.

**Acceptance criteria:**
- [ ] No mention of neon/cyan/electric remains anywhere a user would read it.
- [ ] The README claims no platform beyond what CI has proven.
- [ ] Deletions are proposed, not performed, unless the user says otherwise.

**Verification:**
- [ ] `grep -rin "neon\|electric cyan" README.md CHANGELOG.md src` returns nothing user-facing; full suite green after the graph refresh.

**Dependencies:** Task 10 · **Scope:** XS (3-4 files)

## Open question left for the user

Whether `themes/design-concepts.html` and `themes/neon-concepts.html` should be
kept as design history or deleted with the empty `ui/stylesheets/` folder
(Task 11 raises it; nothing is deleted without a go).
