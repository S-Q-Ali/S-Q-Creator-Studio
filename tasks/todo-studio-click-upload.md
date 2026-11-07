# Tasks: click the Vertical Studio well to choose files

Plan: `tasks/plan-studio-click-upload.md` · Test-first, one offline gate per
task, commit only when the gate is green. Not started — waiting on the owner's
answers to the plan's four open questions.

## Task 1: a button in the well opens the picker

- [ ] `QPushButton` inside the `#DropZone` well, connected to the existing
      `browse()`; the well keeps its labels, its objectName and its stretch.
- [ ] Same `getOpenFileNames` call: `DontUseNativeDialog`, same start folder,
      same `PICKER` filter.
- [ ] Keyboard-reachable by being a real button (`Tab`, `Space`/`Enter`), proven
      by a test rather than assumed.
- [ ] Chosen files go through `add_paths`, so folders and links are still named
      and skipped.
- [ ] `theme.py` carries the button's look; no inline stylesheet in the page.

**Verification:** `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_vertical_studio_page.py tests/test_ui_layout.py -m "not live" -q -p no:warnings -o addopts=""`

**Dependencies:** none · **Files:** `ui/vertical_studio_page.py`, `theme.py`,
`tests/test_vertical_studio_page.py` · **S**

## Task 2: the row loses Browse…, the page keeps one handler

- [ ] No `self.btn_browse` anywhere; `browse()` unchanged but for its new caller.
- [ ] Layout guards green at the smallest window; remaining buttons keep order.
- [ ] Tests that clicked `btn_browse` click the well's button instead, keeping
      the `DontUseNativeDialog` assertion.

**Verification:** Task 1's command plus
`./source/venv/Scripts/python.exe -m ruff check src tests --output-format concise`

**Dependencies:** Task 1 · **Files:** `ui/vertical_studio_page.py`,
`tests/test_vertical_studio_page.py`, `tests/test_ui_layout.py` · **S**

## Task 3: the well says what it now does

- [ ] The page hint names the click, not a `Browse` button that no longer exists.
- [ ] No user-visible string still says "press Browse" (grep in the same commit).
- [ ] README Studio bullet — **owner's go needed** for wording and version.
- [ ] Offline suite green, ruff clean, `graphify update .` in its own commit.
- [ ] Owner's live check on the built app: click the well, pick two files, drag
      one more, `Tab` to the button and press Enter.

**Dependencies:** Task 2 · **Files:** `ui/vertical_studio_page.py`, `README.md`,
`CHANGELOG.md` · **XS**
