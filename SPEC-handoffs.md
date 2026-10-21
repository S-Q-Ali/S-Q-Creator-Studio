# Spec: `handoffs` — every page talks to every other page

**Objective:** a researcher should never have to leave a page, retype a URL and
guess what to do next. Today exactly one of ~16 plausible handoffs works.

## Handoff matrix to deliver

| From → To | Action |
|---|---|
| Niche Discovery → Download queue | "Queue videos" on the card: the channel's recent uploads become download-queue jobs |
| Niche Discovery → Scorecard | "Open in Scorecard" opens the channel in the Scorecard's channel mode |
| Niche Discovery → Competitors | "Track channel" writes the channel to `tracked_items` (kind='channel') |
| Niche Discovery → YouTube | "Open channel" opens the channel page in the default browser |
| Scorecard → AI Analysis | "Analyze channel" opens the AnalysisModal for the resolved channel |
| Scorecard → Competitors | "Track" already writes `tracked_items`; the button must reflect the tracked state |
| Scorecard → Download queue | "Queue video" adds the scored video to the download queue |
| Scorecard → YouTube | "Open video" opens the video in the browser |
| Keyword Research → Competitors | "Track this keyword" already writes `tracked_items`; it must be visible on the Competitors page |
| Keyword Research → Scorecard | "Analyze keyword" scores a keyword's top-ranked video on the Scorecard |
| Competitors → Scorecard | clicking a tracked video/channel opens it on the Scorecard |
| Competitors → Keyword detail | clicking a tracked keyword opens its keyword detail view |
| Competitors → AI Analysis | "Analyze" on a tracked channel opens the AnalysisModal |
| Competitors → Download queue | "Queue" on a tracked video adds it to the download queue |
| AI Analysis → Scorecard | "Open in Scorecard" for the analysed channel |
| AI Analysis → Download queue | "Queue videos" for the analysed channel's recent uploads |
| AI Analysis → Competitors | "Track channel" for the analysed channel |
| Research (any page) → Download queue | one shared, documented bridge from the research tab to the download queue |

## Acceptance criteria

1. `ResearchContainer` exposes one `send_to_queue_requested(list[str])` signal
   carrying ready-to-use video URLs; `MainWindow` connects it to the same
   code path the Agent tab uses, so both land in the download queue.
2. Every handoff above is reachable from the UI and does the thing it says.
3. Cross-page navigation preserves the item being looked at (the Scorecard
   opens with that URL prefilled and the correct mode selected).
4. A handoff that needs a channel id the page does not have must be disabled
   with a tooltip explaining why — never a dead button.
5. "Open in browser" uses `QDesktopServices.openUrl` with an `https` URL only.

## Verification

- Offscreen tests: each handoff emits the expected signal / populates the
  expected widget.
- A test that the research queue bridge adds jobs to the download queue.
- `pytest -q` green; `ruff check src tests` clean.

## Boundaries

- URLs handed to the download queue must pass the existing `is_tiktok_url` /
  `is_youtube_url` validation.
- No new network calls.
- The download queue keeps its existing behaviour (workers, retries, pacing).
