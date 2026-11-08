# Todo: UI & Style Audit Fixes (v2.19.0)

- [x] Task 1: Theme & Focus Ring Completeness (Findings 6, 7, 8-theme, 10-theme) — test: `pytest tests/test_theme.py tests/test_qss_parses.py tests/test_glass_theme_qt.py tests/test_music_ui.py`
- [x] Task 2: Packaged-Build Pickers & Running-State Guards (Findings 1, 2, 3) — test: `pytest tests/test_music_ui.py tests/test_agent_tab.py tests/test_settings_page.py tests/test_social_discovery_ui.py`
- [x] Task 3: Keyboard Accessibility, Form Buddies & Table Link Interaction (Findings 4, 5, 11) — test: `pytest tests/test_ui_layout.py tests/test_social_discovery_ui.py tests/test_agent_tab.py tests/test_gui.py`
- [x] Task 4: Workspace Consistency, Empty States, Action Order, Logs & Inline Feedback (Findings 8-pages, 9, 10-studio, 12, 14) — test: `pytest tests/test_music_ui.py tests/test_vertical_studio_page.py tests/test_agent_tab.py tests/test_settings_page.py tests/test_social_discovery_ui.py`
- [x] Task 5: Full-Workspace Layout Guards, Docs, Version & GitHub Push (Finding 13 + v2.19.0) — test: `pytest tests/test_ui_layout.py && ruff check src tests release`
- [x] Task 6: Diagnose & Fix GitHub Actions CI & macOS Release Failures (Ubuntu/macOS layout clipping in `main_window.py` & `agent_tab.py`, plus `hdiutil` retry in `release/build.py`) — test: `pytest tests/test_ui_layout.py tests/test_release_build_script.py && ruff check src tests release`
