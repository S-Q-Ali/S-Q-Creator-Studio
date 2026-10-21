# Plan: Desktop Shell (responsive, de-congested, research-free)

**Spec:** `SPEC-desktop-shell.md`
**Status:** approved — starting implementation.

## Why this order

`core-extract` must come first: the Social Discovery feature reads the Groq
key and the channel resolver out of the research package, so deleting the
package before extracting those three modules would break the feature that
shipped in 2.5.0.

`settings-panel` comes before `density`: the rail only becomes slim once the
download settings have somewhere else to live.

`ui-fixes` comes last: several of the fixes (the active tab, the empty
states, the contrast) are cheaper to make once the density scale exists, and
they need the rendering test that `density` introduces.

## Slices

### 1. `core-extract`
1. `core/settings_store.py` — the `settings` table, the DPAPI sealing,
   `db_path`, `configure`, `get_setting`, `set_setting`,
   `secret_is_unreadable`. Same database file, same table, same keys.
2. `core/youtube_client.py` — moved from the research tools, unchanged public
   names.
3. `core/exporter.py` — moved from the research tools, unchanged public names.
4. Point the four users at the new modules.
5. Rename the three test files; add a test that a value written by the old
   module still reads back.

**Verify:** `pytest -q` green, `ruff` clean.

### 2. `research-remove`
6. Delete `src/s_q_ali_media_downloader/niche_research/`.
7. Delete the 19 research test files.
8. `main_window.py`: drop the import, the third workspace, the nav button,
   the rail auto-hide branch and the close-time shutdown.

**Verify:** `pytest -q` green; no import of `niche_research` remains.

### 3. `settings-panel`
9. `ui/settings_page.py` — the app's own settings page, one column of
   grouped cards.
10. Move the download settings out of the rail into it; keep the existing
    `QSettings` keys.
11. Add the Groq key, the YouTube key and the cookies file.
12. Wire the third workspace tab and its nav segment.

**Verify:** `pytest -q` green; a test that saves a Groq key in the panel and
reads it back through `social_judge.groq_key()`.

### 4. `density`
13. `theme.py`: the token scale, the two density variants, the generated
    stylesheet.
14. `main_window.py`: the slim rail, the segmented switcher, the one 28px
    chrome bar.
15. `agent_tab.py`: the collapsible options, the wrapping rows.
16. `social_discovery_page.py`: the button width, the empty state.

**Verify:** the rendering test at 1280×720, 1366×768, 1440×900, 1680×1000.

### 5. `ui-fixes`
17. The active tab's contrast.
18. The secondary text's contrast.
19. The primary button's hover.
20. The empty states on both tables.
21. The social buttons into the rail.

**Verify:** the rendering test's contrast assertions; `pytest -q`; `ruff`.

## Risks

| Risk | Mitigation |
|---|---|
| The stored Groq key stops working | The database path and the table name stay the same; a test writes with the old module and reads with the new one |
| The extraction grows into a rewrite | The three modules move as files; only the research tables are dropped from the store |
| The density scale touches every widget | One stylesheet generator, then the layouts; the rendering test catches the regressions |
| The app looks different from before and something is missed | The rendering test asserts on the real widgets, not on a mock |
