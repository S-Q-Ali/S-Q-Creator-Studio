# Spec: `export` — take the data with you

**Objective:** every page that shows data can export it as CSV, JSON or
Markdown. Today only the AI thumbnail can be saved.

## Acceptance criteria

1. **Export button on each data page:** Niche Discovery (grid), Scorecard
   (result), Competitors (dashboard), Keyword Research (results), AI Analysis
   (analysis).
2. **Three formats, one button:** a small menu offering CSV / JSON / Markdown.
   - CSV — flat table, one header row, UTF-8 with BOM so Excel opens it clean.
   - JSON — full-fidelity structure (lists of objects, nested fields kept).
   - Markdown — a human-readable report: a title, a generated-at line, tables
     and the AI analysis sections (strategy, ideas, scripts, blueprint).
3. **File chooser** with a sensible default name, e.g.
   `niche-discovery-2026-10-20.csv`, and an overwrite confirmation from the OS
   dialog.
4. **Empty state:** with nothing to export the button is disabled with a
   tooltip — never a silent no-op or an empty file.
5. **Errors are reported** (unwritable path, permission denied) in the page's
   status line; the app must not crash.
6. Export writes **only** the data already shown on that page — no hidden
   fields, no API keys.

## Verification

- Unit tests for the serialisers (CSV/JSON/Markdown) with fixed inputs.
- Offscreen tests that the export button is enabled/disabled correctly and that
   the chosen path is written.
- `pytest -q` green; `ruff check src tests` clean.

## Boundaries

- New module `niche_research/tools/exporter.py`; no changes to the engines.
- No new dependency (stdlib `csv`, `json` only).
- Ask first: any export that would include credentials or cookies.
