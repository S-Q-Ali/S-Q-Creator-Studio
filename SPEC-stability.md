# Spec: `stability` — no crash, no abort

**Objective:** every reachable action in Niche Research (and the Agent tab's
queue button) either works or shows an error. No path may abort the process.

## Acceptance criteria

1. **Agent tab "Queue" works.**
   - `main_window._handle_agent_urls` calls `self.add_links_to_queue()`, which
     does not exist. The method must resolve and the URLs must land in the
     download queue.
2. **Scorecard survives repeated failures.**
   - Today the shared empty-state widget is deleted by `_clear_content` and then
     re-added by `_render_placeholder`; the *second* failure raises
     `RuntimeError: Internal C++ object already deleted`.
   - After the fix, failing the same lookup ten times in a row is safe, and
     switching modes repeatedly is safe.
3. **Closing the AnalysisModal mid-analysis never aborts.**
   - `QDialog.reject()` bypasses `closeEvent`, so the worker threads are never
     joined and PySide6 aborts with "QThread: Destroyed while thread is still
     running".
   - After the fix, closing the modal during analysis, thumbnail generation and
     channel loading all exit cleanly.
4. **Closing the app never aborts.**
   - `MainWindow.closeEvent` must stop the research poller and wait for the
     research workers.
5. **The Niche Discovery niche filter is populated at startup.**
   - The combo box is currently empty until the format combo is touched.
6. **No research worker outlives its page.**
   - Scorecard / competitors / trending workers must be joined or cancelled
     when the owning widget goes away.
7. **A failed analysis does not lose the strategy.**
   - When a provider returns 0 scripts, the modal must still show the stored
     analysis instead of falling back to "Ready to Analyze".

## Verification

- Offscreen regression tests in `tests/test_niche_scorecard_ui.py`,
  `tests/test_niche_analysis_ui.py`, `tests/test_niche_research_container.py`,
  `tests/test_gui.py`.
- The Agent-tab queue path gets a test that asserts the job list grows.
- `pytest -q` green; `ruff check src tests` clean.

## Boundaries

- Allowed to touch `ui/main_window.py` for exactly two integration points: the
  queue bridge and the close handler.
- No behaviour change beyond "stop crashing".
- Never swallow an exception that was previously visible to the user.
