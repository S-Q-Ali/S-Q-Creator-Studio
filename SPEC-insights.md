# Spec: `insights` — finish the features that promise more than they deliver

**Objective:** the AI analysis surface and the discovery surface promise
capabilities they do not deliver.

## Acceptance criteria

1. **The Thumbnail generator is reachable without an AI analysis.**
   - Today the Thumbnail tab lives inside the "already analysed" branch, so a
     fresh channel cannot generate a thumbnail without first paying for (and
     waiting on) a full chat analysis.
   - After the fix, the Thumbnail tab is available immediately; generating a
     thumbnail does not require a prior analysis.
2. **"Create Similar Channel" finds a genuinely similar channel.**
   - A nearest-neighbour search over the discovered `trending_channels` table
     (same niche first, then subscriber/view scale and viral score) must
     return a *different* channel with a real similarity score in 0-100.
   - The modal shows the match: name, subs, views, similarity score, and a
     link to open it on the Scorecard.
   - No match → an explicit "no similar channel found yet" message, never a
     self-comparison.
3. **"AI only" filter in Niche Discovery.**
   - The engine already supports `ai_only`; the toolbar must expose it and the
     grid must honour it.
4. **Niche competition and difficulty are visible.**
   - `Niche.competition` and `Niche.difficulty` are in the catalog but never
     rendered — show them on the trending card.
5. **The AI analysis shows progress.**
   - `analyze_channel` accepts a `progress` callback that the modal ignores;
     the modal must show which provider is being tried and how long it has been
     running, and must offer a cancel.
6. **Analysis output is complete.**
   - A channel with 0 scripts still shows its strategy, ideas and blueprint
     (see `core-fixes` / `stability`).
   - The analysis JSON stored in the DB must contain the full analysis, not
     only the strategy.
7. **Scripts are linked to the ideas they came from** (`channel_scripts.idea_id`
   is never written).
8. **The stale hint text is fixed** — the modal still says the thumbnail
   generator "requires the aiHubMix API key" while it also falls back to Google
   AI and OpenRouter.

## Verification

- Offscreen tests: the Thumbnail tab is reachable on a fresh channel; the
  similar-channel finder returns a different channel with a score; the AI-only
  filter changes the grid; the analysis progress label updates.
- Engine tests: nearest-neighbour scoring, `analysis_json` completeness.
- `pytest -q` green; `ruff check src tests` clean.

## Boundaries

- The similar-channel search reads only locally discovered channels — no new
  network calls.
- Ask first: any change to the AI prompt contract (the JSON shape).
