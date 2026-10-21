# Spec: `polish` — remove what does not earn its place

**Objective:** the module carries dead code, a lying label and a chart that
cannot show anything. Clean it up last, once the behaviour has settled.

## Acceptance criteria

1. **Dead code removed** (or made live where that is clearly better):
   - `trending_engine.get_format_niche_counts`
   - `trending_engine.update_last_analyzed` (duplicated SQL in
     `ai_analysis_engine.save_analysis`)
   - `keyword_engine.decode_term`, `keyword_engine.get_cached_keywords`
   - `scorecard_engine.score_label` (duplicated in `ui/widgets.py`)
   - `autocomplete.expand_seed` (duplicated inline in `keyword_engine`) —
     either use it or delete it
   - `data.niches.format_name`, `data.niches.VIDEO_FORMATS`
   - `ai_analysis_engine.THUMB_STYLES` (the modal hardcodes the same list)
   - `db.vacuum` — wire it into a periodic maintenance path or delete it
   - `ResearchOutput.related_count` (written, never read)
2. **The Competitors sparklines show data.**
   - `Sparkline` normalises by 100 and clamps, so raw view/subscriber series
     render as a flat line. It must auto-scale to the series range, with the
     0-100 case unchanged.
3. **The untrack button says what it does.**
   - It currently reads "Tracking" with a "Remove from tracking" tooltip.
4. **Dead QSS rules removed** and the missing container rule added:
   - `QLabel#modalSubHeader`, `QFrame#thumbPreview`, `QLabel#settingsTitle`,
     `QLabel#settingsHint`, `QLabel#formLabel`, `QLabel#badge` /
     `QPushButton#badge`, plus `QWidget#researchContainer`.
5. **Layout inconsistency normalised** — the trending page installs a
   `FlowLayout` with both a parent and `setLayout`; the other pages use one
   mechanism.
6. **The `VideoThumb` cursor** promises a click that does not exist — either
   wire it or remove the cursor.
7. **The thumbnail save path handles I/O errors** instead of raising inside a
   Qt slot.
8. **The discovery status bar no longer claims a search budget** that the
   engine does not enforce ("Search: unlimited (yt-dlp)" — the engine has a
   `SEARCH_BUDGET` constant).

## Verification

- `pytest -q` green; `ruff check src tests` clean.
- A test asserting the sparkline auto-scales (two points 10x apart produce a
  non-flat curve).
- Offscreen screenshot-free checks that the removed QSS rules have no users
  left (`rg` over `src/`).

## Boundaries

- Deletions only for symbols with no callers in `src/` and `tests/`; if a
  symbol is used by a test, the test is updated in the same change.
- No visual redesign.
