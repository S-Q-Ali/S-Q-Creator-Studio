# Plan: UI & Style Audit Fixes (v2.19.0)

## Goal
Implement all 14 UI, style, and accessibility audit findings across `theme.py` and the 5 workspace pages (`MainWindow`, `MusicPage`, `SocialDiscoveryPage`, `VerticalStudioPage`, `AgentTabWidget`, `SettingsPage`), verify with automated Qt tests and Ruff, update `graphify`, bump to `2.19.0`, and push to `origin/master`.

## Non-Goals
- No changes to downloader, clipper, music provider, or agent backend scraping logic beyond cooperative cancellation hooks on `AgentWorkerThread`.
- No new third-party dependencies.
- No changes to the palette hex values in `C` (`theme.py`).

## Architecture & Constraints
- All styling lives in `src/s_q_ali_media_downloader/theme.py` (`build_stylesheet`); no hex color literals (`#...`) may appear in any other `.py` file under `src/`.
- Preserve exact selector headers tested in `tests/test_theme.py` (`"QLineEdit, QPlainTextEdit, QTextEdit, QComboBox"`, `"QPushButton"`, `'QLabel[role="section"]'`).
- Every `:focus` rule in `theme.py` must paint `C["accent_hi"]`, change only color (never geometry or font), and be declared after any competing pseudo-state on the same selector head.

## Tasks

### Task 1: Theme & Focus Ring Completeness (Findings 6, 7, 8-theme, 10-theme)
- **Files:** `src/s_q_ali_media_downloader/theme.py`, `src/s_q_ali_media_downloader/ui/main_window.py`, `src/s_q_ali_media_downloader/ui/music_page.py`, `tests/test_theme.py`, `tests/test_music_ui.py`
- **Changes:**
  - Add `QSpinBox`, `QSpinBox:focus`, and `QSpinBox:disabled` rules to `build_stylesheet()` in `theme.py` and register `"the spin box": "QSpinBox:focus"` in `FOCUS_RING` (`tests/test_theme.py`).
  - Move `GitHub` and `LinkedIn` button styles from inline `setStyleSheet()` in `main_window.py` to `QPushButton[kind="github"]` and `QPushButton[kind="linkedin"]` (with `:hover`, `:pressed`, `:focus`) in `theme.py` and register both in `FOCUS_RING`.
  - Replace inline `self.status.setStyleSheet(...)` in `MusicPage._say()` with `setProperty("role", "error" if error else "meta")` + `unpolish`/`polish`.
  - Give `QPushButton[kind="danger"]` a calm resting border (`border-color: {C['faint']};`) so it is visually distinct before hover.
  - Scale `QLabel[role="pageTitle"]` font-size from density (`{t['title'] - 3}px` -> `16px` comfortable, `14px` compact).
- **Verification:** `pytest tests/test_theme.py tests/test_qss_parses.py tests/test_glass_theme_qt.py tests/test_music_ui.py`

### Task 2: Packaged-Build Pickers & Running-State Guards (Findings 1, 2, 3)
- **Files:** `src/s_q_ali_media_downloader/ui/music_page.py`, `src/s_q_ali_media_downloader/ui/settings_page.py`, `src/s_q_ali_media_downloader/ui/agent_tab.py`, `src/s_q_ali_media_downloader/ui/social_discovery_page.py`, `src/s_q_ali_media_downloader/ui/main_window.py`, `tests/test_music_ui.py`, `tests/test_agent_tab.py`, `tests/test_settings_page.py`
- **Changes:**
  - Save `self.btn_browse` on `MusicPage` and disable it in `_set_running(running)`.
  - Pass `options=QFileDialog.Option.DontUseNativeDialog` to all 6 remaining `QFileDialog` calls (`music_page.py`, `settings_page.py`, `agent_tab.py`, `social_discovery_page.py`).
  - Add cooperative `cancel()` to `AgentWorkerThread` + `Stop` button (`self.btn_stop`) in `AgentTabWidget`, and include `self.agent_tab.worker` in `MainWindow._workers_running()` and `_begin_deferred_close()`.
- **Verification:** `pytest tests/test_music_ui.py tests/test_agent_tab.py tests/test_settings_page.py tests/test_social_discovery_ui.py`

### Task 3: Keyboard Accessibility, Form Buddies & Table Link Interaction (Findings 4, 5, 11)
- **Files:** `src/s_q_ali_media_downloader/ui/main_window.py`, `src/s_q_ali_media_downloader/ui/social_discovery_page.py`, `src/s_q_ali_media_downloader/ui/agent_tab.py`, `src/s_q_ali_media_downloader/ui/widgets.py`, `src/s_q_ali_media_downloader/ui/settings_page.py`, `src/s_q_ali_media_downloader/ui/music_page.py`, `src/s_q_ali_media_downloader/ui/vertical_studio_page.py`, `src/s_q_ali_media_downloader/theme.py`, `tests/test_ui_layout.py`, `tests/test_social_discovery_ui.py`, `tests/test_agent_tab.py`
- **Changes:**
  - Convert `MainWindow.folder_label` from `QLabel` with `mousePressEvent` lambda to a `QPushButton` (`kind="ghost"`, `objectName="FolderPathLink"`) connected to `open_folder`.
  - Underline found link cells in `SocialDiscoveryPage`, populate the detail panel on `currentCellChanged` as well as click, and open links on `Return`/`Enter` in both `SocialDiscoveryPage` and `AgentTabWidget`.
  - Set `accessibleName` on `btn_toggle_rail`, `JobCard.check`, and `AgentTabWidget` row checkboxes; wire `setBuddy()` on labeled form controls across `SettingsPage`, `MusicPage`, `VerticalStudioPage`, `AgentTabWidget`, and `MainWindow`.
- **Verification:** `pytest tests/test_ui_layout.py tests/test_social_discovery_ui.py tests/test_agent_tab.py tests/test_gui.py`

### Task 4: Workspace Consistency, Empty States, Action Order, Logs & Inline Feedback (Findings 8-pages, 9, 10-studio, 12, 14)
- **Files:** `src/s_q_ali_media_downloader/ui/social_discovery_page.py`, `src/s_q_ali_media_downloader/ui/agent_tab.py`, `src/s_q_ali_media_downloader/ui/settings_page.py`, `src/s_q_ali_media_downloader/ui/music_page.py`, `src/s_q_ali_media_downloader/ui/vertical_studio_page.py`, `tests/test_music_ui.py`, `tests/test_vertical_studio_page.py`, `tests/test_agent_tab.py`, `tests/test_settings_page.py`
- **Changes:**
  - Remove duplicate `🔎 SOCIAL DISCOVERY` `pageTitle` from `SocialDiscoveryPage`, use Title Case in `AgentTabWidget` header (`🤖 AI Channel Finder & Social Inspector`), and add `#WorkHeader` (`⚙️ Settings` + hint) to `SettingsPage`.
  - Add `self.table_stack` with `#EmptyState` (`self.empty_state`), `setAlternatingRowColors(True)`, and `setShowGrid(False)` to `MusicPage`.
  - Reorder `VerticalStudioPage` action buttons so primary CTA (`self.btn_run`, `self.btn_stop`) comes before (`self.btn_remove`, `self.btn_clear`).
  - Cap `MusicPage.log` and `VerticalStudioPage.log` with `setMaximumBlockCount(500)`.
  - Standardize `"Browse…"` ellipsis across `settings_page.py` and `agent_tab.py`, and replace empty-input/empty-selection `QMessageBox.warning` dialogs in `AgentTabWidget` with inline `self.lbl_status.setText(...)`.
- **Verification:** `pytest tests/test_music_ui.py tests/test_vertical_studio_page.py tests/test_agent_tab.py tests/test_settings_page.py tests/test_social_discovery_ui.py`

### Task 5: Full-Workspace Layout Guards, Docs, Version & GitHub Push (Finding 13 + Release)
- **Files:** `tests/test_ui_layout.py`, `pyproject.toml`, `src/s_q_ali_media_downloader/__init__.py`, `CHANGELOG.md`, `graphify-out/`
- **Changes:**
  - Extend `test_the_nav_tabs_leave_room_for_their_text` to check all 5 nav buttons and add a `1280×720` clipping guard test across all 5 workspace tabs.
  - Bump version to `2.19.0` in `pyproject.toml` and `__init__.py`, update `CHANGELOG.md`, run `graphify update .`, tag `v2.19.0`, and push `master` + `v2.19.0` to `origin`.
- **Verification:** Full UI test suite + `ruff check src tests release` + `git status` / `git push`.
