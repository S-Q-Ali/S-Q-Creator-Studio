# Implementation Plan: click the Vertical Studio well to choose files

Request: "jahan drop down container hai wahan click and upload ka
feature/button b chahiyay Browse ki jagah" — the drop well becomes the way in,
and the separate `Browse…` button stops being the only door.

Prepared 2026-11-07 from `ui/vertical_studio_page.py`, `theme.py`,
`tests/test_vertical_studio_page.py`, `tests/test_ui_layout.py`. Nothing here is
implemented yet.

## Current state (measured, with lines)

- The well is a passive `QFrame` (`ui/vertical_studio_page.py:146-159`,
  `objectName("DropZone")` `:147`) holding two labels: "Drop video files here"
  `:151` and "Or press Browse. Files only — folders and links are named and
  skipped." `:153`. It has **no mouse handling, no focus policy, no cursor, no
  accessible name** — it cannot be operated by keyboard at all.
- Drag and drop is not on the well: the whole page accepts it
  (`self.setAcceptDrops(True)` `:115`, `dragEnterEvent` `:397`,
  `dragMoveEvent` `:405`, `dropEvent` `:411`). The well is decoration that
  happens to sit where the files land.
- `Browse…` is a `QPushButton("Browse…")` at `:228-230`, handler `browse()`
  `:353-368`, which calls `QFileDialog.getOpenFileNames(..., options=
  QFileDialog.Option.DontUseNativeDialog)` `:361-367` and feeds the result to
  `add_paths()` `:331-351` — the same function `dropEvent` calls `:416`.
- The clickable-area pattern the app already uses is `main_window.py:265-269`
  (a `QLabel` given `setToolTip`, `setCursor(Qt.PointingHandCursor)` and a
  `mousePressEvent` lambda). There is no `Clickable` widget and no
  `eventFilter` anywhere in `ui/`.
- `#DropZone` is styled in `theme.py:609-612` — well background, dashed border,
  10px radius, no hover/pressed/focus state.
- Guard tests that must stay green: `test_the_studio_buttons_stay_on_screen_at_the_smallest_window`
  (`tests/test_ui_layout.py:197`), `test_every_control_is_big_enough_to_click`
  (`:149`), `test_browse_adds_what_the_picker_returns`
  (`tests/test_vertical_studio_page.py:147`, asserts the `DontUseNativeDialog`
  kwarg at `:165`), `test_browse_starts_where_the_last_file_came_from` `:168`.

## Architecture decisions

- **A real `QPushButton` inside the well, not hand-rolled mouse handling.** The
  request is a button in the drop container; `QPushButton` gives click,
  `Space`/`Enter`, focus ring, and a screen-reader role for free. Assigning
  `mousePressEvent` on the `QFrame` (the `main_window.py` pattern) would need
  `focusPolicy` + `keyPressEvent` + `setAccessibleName` written by hand to reach
  the same bar, and the accessibility rule in `AGENTS.md` is not cuttable.
- **The well keeps its objectName and its drop look.** The new button lives
  inside it, so the dashed target the user aims at for dragging does not move;
  a widget-selector `#DropZone` rule in the sheet beats a type selector for the
  properties it declares, so the button can carry the well look with a small
  `theme.py` addition instead of an inline stylesheet — which is exactly what
  issue #17 complains about elsewhere.
- **`Browse…` disappears from the button row; `browse()` does not.** One
  handler, two doors removed. The picker call, its start folder and the
  non-native flag stay byte-for-byte as they are so the existing tests keep
  testing the real thing.
- **Drop stays page-level.** Moving `dragEnterEvent`/`dropEvent` onto the well
  would break dropping anywhere on the page, which is today's behaviour and is
  tested (`tests/test_vertical_studio_page.py:100`, `:111`, `:125`, `:402`).
- **Hint text has to stop lying.** "Or press Browse" names a button that will no
  longer exist.

## Task List

### Phase 1: the door

- [ ] Task 1: a button in the well opens the picker
- [ ] Task 2: the row loses `Browse…`, the page keeps one handler
- [ ] Checkpoint: offline Studio + layout tests green, ruff clean

### Phase 2: the wording and the proof

- [ ] Task 3: the well says what it now does
- [ ] Checkpoint: owner's live click on the built app

## Task 1: a button in the well opens the picker

**Description:** the drop well gains a `QPushButton` that opens the same
non-native picker `Browse…` opens, and is reachable by keyboard.

**Acceptance criteria:**

- [ ] The well still has `objectName("DropZone")`, its two labels, and its
      stretch factor — a drag onto the page lands files exactly as today.
- [ ] A `QPushButton` inside the well, named for what it does ("Choose video
      files" or the owner's wording), connected to the existing `browse()`.
- [ ] Clicking it produces the same `QFileDialog.getOpenFileNames` call with
      `DontUseNativeDialog`, the same start folder and the same `PICKER` filter.
- [ ] It takes focus with `Tab` and fires on `Space`/`Enter` (free from
      `QPushButton`, asserted in a test rather than assumed).
- [ ] Files chosen by the click go through `add_paths`, so the junk-rejection
      sentence still names folders and links it skipped.

**Verification:** `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_vertical_studio_page.py tests/test_ui_layout.py -m "not live" -q -p no:warnings -o addopts=""`

**Dependencies:** none · **Files:** `ui/vertical_studio_page.py`,
`theme.py`, `tests/test_vertical_studio_page.py` · **S**

## Task 2: the row loses Browse…, the page keeps one handler

**Description:** delete the `Browse…` button from the button row
(`ui/vertical_studio_page.py:228-230`) so the well is the only way in, keeping
`browse()` untouched.

**Acceptance criteria:**

- [ ] No `Browse…` button is constructed; no code path references
      `self.btn_browse`.
- [ ] `browse()` is unchanged apart from being called from the new button.
- [ ] The two layout guards still pass at the smallest window, and the row's
      remaining buttons keep their order.
- [ ] Any test that clicked `btn_browse` now clicks the well's button, and the
      `DontUseNativeDialog` assertion (`:165`) survives.

**Verification:** the Task 1 command, plus
`./source/venv/Scripts/python.exe -m ruff check src tests --output-format concise`

**Dependencies:** Task 1 · **Files:** `ui/vertical_studio_page.py`,
`tests/test_vertical_studio_page.py`, `tests/test_ui_layout.py` · **S**

## Task 3: the well says what it now does

**Description:** the hint at `:153` and the README/hint wording name a button
that will not exist; they have to name the click.

**Acceptance criteria:**

- [ ] The hint reads as one sentence about clicking the well or dragging onto
      it, and still states that folders and links are named and skipped.
- [ ] `ui/vertical_studio_page.py:132` (the cost line) and the page's other hint
      roles stay untouched — this is a wording change, not a restyle.
- [ ] README's Studio bullet says "click the well or drop files on the page"
      where it currently says Browse. **Needs the owner's go for the wording and
      for the version it lands in.**

**Verification:** the Task 1 command; a `grep` proving no user-visible string
still says "press Browse".

**Dependencies:** Task 2 · **Files:** `ui/vertical_studio_page.py`, `README.md`,
`CHANGELOG.md` · **XS**

## Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| A button inside a dashed well reads as a second drop target | Low | The well keeps its labels; the button is the only thing with a border of its own (`theme.py` rule scoped to the objectName) |
| Removing `Browse…` breaks a test that looks it up by name | Med | Task 2 re-points those tests rather than deleting assertions |
| `#DropZone` id rule plus a new `QPushButton` rule fights the app-wide `QPushButton` type rule | Med | One screenshot-free assertion: the button's computed `styleSheet()` is empty and its text colour comes from the sheet, the same trick used for the status role in `tasks/plan-studio-audit-fixes.md` |
| Touch/no-mouse machines lose the drag path | Low | The button is the pointer-independent door; drop stays as the fast path |

## Open questions (need the owner)

1. Does the old `Browse…` button disappear entirely (this plan assumes yes), or
   stay as a second, smaller door?
2. Label wording for the new button.
3. Which version this lands in — 2.17.0 is tagged and building now, so this is
   **2.18.0** unless the owner wants it folded into a still-unpublished release.
4. README/CHANGELOG wording needs its own go (standing rule).
