# Tasks: click the Vertical Studio well to choose files

Plan: `tasks/plan-studio-click-upload.md` · Test-first, one offline gate per
task, commit only when the gate is green. Owner answered 2026-11-08: `Browse…`
goes entirely, the button reads "Choose video files", this lands in **2.18.0**,
and the plan's README/CHANGELOG wording is approved.

## Task 1: a button in the well opens the picker

- [x] `QPushButton` inside the `#DropZone` well, connected to the existing
      `browse()`; the well keeps its labels, its objectName and its stretch.
- [x] Same `getOpenFileNames` call: `DontUseNativeDialog`, same start folder,
      same `PICKER` filter.
- [x] Keyboard-reachable by being a real button (`Tab`, `Space`/`Enter`), proven
      by a test rather than assumed. (The test caught it: outside a QDialog a
      QPushButton ignores Return — the button is `setDefault(True)`.)
- [x] Chosen files go through `add_paths`, so folders and links are still named
      and skipped.
- [x] `theme.py` carries the button's look; no inline stylesheet in the page.

**Verification:** `QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_vertical_studio_page.py tests/test_ui_layout.py -m "not live" -q -p no:warnings -o addopts=""`

**Dependencies:** none · **Files:** `ui/vertical_studio_page.py`, `theme.py`,
`tests/test_vertical_studio_page.py` · **S**

## Task 2: the row loses Browse…, the page keeps one handler

- [x] No `self.btn_browse` anywhere; `browse()` unchanged but for its new caller.
- [x] Layout guards green at the smallest window; remaining buttons keep order.
- [x] Tests that clicked `btn_browse` click the well's button instead, keeping
      the `DontUseNativeDialog` assertion.

**Verification:** Task 1's command plus
`./source/venv/Scripts/python.exe -m ruff check src tests --output-format concise`

**Dependencies:** Task 1 · **Files:** `ui/vertical_studio_page.py`,
`tests/test_vertical_studio_page.py`, `tests/test_ui_layout.py` · **S**

## Task 3: the well says what it now does

- [x] The page hint names the click, not a `Browse` button that no longer exists.
- [x] No user-visible string still says "press Browse" (grep in the same commit).
- [x] README Studio bullet — **owner's go needed** for wording and version.
      (Given 2026-11-08: "click the well or drop files on the page", 2.18.0.)
- [x] Offline suite green, ruff clean, `graphify update .` in its own commit.
- [ ] Owner's live check on the built app: click the well, pick two files, drag
      one more, `Tab` to the button and press Enter.

**Dependencies:** Task 2 · **Files:** `ui/vertical_studio_page.py`, `README.md`,
`CHANGELOG.md` · **XS**
