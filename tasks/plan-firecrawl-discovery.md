# Plan — Firecrawl Primary Discovery + AI/Browser Fallback & Accuracy Fixes

Spec: `tasks/spec-firecrawl-discovery.md`

## Implementation Order (Vertical Slices)

### Slice 1: Firecrawl Client (`firecrawl_client.py`) & Settings UI (`settings_page.py`)
- Create `src/s_q_ali_media_downloader/agent/tools/firecrawl_client.py` using `httpx`:
  - `firecrawl_key()` (`FIRECRAWL_API_KEY` env first, then `settings_store.get_setting("firecrawl_api_key")`).
  - `test_firecrawl_key(api_key)` calling `GET https://api.firecrawl.dev/v1/team/credit-usage` and returning remaining credits summary.
  - `search(query, limit=5, api_key=None)` calling `POST https://api.firecrawl.dev/v1/search`.
  - `scrape_page(url, api_key=None) -> Page` calling `POST https://api.firecrawl.dev/v1/scrape` (`formats: ["markdown", "html", "links"]`) and returning a `browser.Page` (`url`, `title`, `text`, `links`, `meta`) compatible with `social_verify.read_profile` and `verify_page`.
- Add `FIRECRAWL_KEY = "firecrawl_api_key"`, `FirecrawlKeyTestWorker`, input row (`fc-...`), and `Test` button to `src/s_q_ali_media_downloader/ui/settings_page.py` at the top of the `AI KEYS` card.

### Slice 2: Firecrawl 1st Priority in Web Search, Page Verification & TikTok Discovery
- In `src/s_q_ali_media_downloader/agent/tools/social_judge.py`:
  - Update `any_key()` to return `True` when `firecrawl_key()`, `gemini_key()`, or `groq_key()` is set.
  - In `_ask_searched()`, try **Firecrawl `/v1/search`** first when `firecrawl_key()` is present, extracting platform URLs and snippets into `AiAnswer(provider="firecrawl")`, then fall back to Gemini (`google_search`) → Groq (`browser_search`).
  - Implement **P5**: in `parse_search_answer()`, accept `sources: list[str] | None = None` so when the model says `yes` (or omits the URL line) and `sources` contains a matching platform profile URL, populate `answer.url` from `sources`.
- In `src/s_q_ali_media_downloader/agent/tools/tiktok_search.py`:
  - When seeds, signed API, and `yt-dlp` return 0 handles for a keyword/hashtag query (`#7`), search for TikTok creator handles (`site:tiktok.com/@ {query}`) via **Firecrawl 1st → Gemini/Groq grounded search fallback**, extracting `@handle` tokens with `SEED_URL_PATTERN`.
- In `src/s_q_ali_media_downloader/agent/tools/social_verify.py` and `social_verifier.py`:
  - When a candidate page returns `Verdict.UNKNOWN` / `SocialStatus.INCONCLUSIVE` in the local browser, try `firecrawl_client.scrape_page(url)` (if `firecrawl_key()` is set) and run `verify_page` / `read_profile` on the scraped `Page` before falling back to `browser-use` (`agent_checker`).

### Slice 3: P1–P4 Discovery Accuracy Fixes Across All 3 Modes
- **P1 (`social_resolve.py` & `youtube_existence.py`):** Weight channel selection by subscriber count when name similarity is tied or close (`>= 0.75`), preventing 10-subscriber impersonator channels from beating 10M-subscriber official channels.
- **P2 (`social_resolve.py`):** In `resolve_channel()`, extract social URLs and `@handle` mentions from `record.description` via `LinkParserTool.extract_social_links(record.description, page_links)` and merge them into `record.bio_links`.
- **P3 (`orchestrator.py` & `social_verifier.py`):**
  - Keep secondary AI candidate URLs (`candidates[platform]`) so if the first candidate is `NOT_FOUND`, the next candidate is tried.
  - In `social_verifier.py:_identity_status()`, use `confidence_tier(evidence)` so model-proposed/handle-guessed accounts with 2+ positive signals (`name_match` + `handle_match` / `back_link`) and no conflict earn `SocialStatus.VERIFIED`.
- **P4 (`youtube_existence.py`):** URL-unquote HTML (`urllib.parse.unquote`) in `_channel_links_to_tiktok()` so `%40handle` matches `@handle`, and detect `YT: @handle` / `YouTube: @handle` in TikTok bios.

## Tasks

- [x] **Task 1:** Write failing tests in `tests/test_firecrawl_discovery.py` covering Firecrawl client, Settings UI, priority fallback order, and P1–P5 fixes.
- [x] **Task 2:** Implement Slice 1 (`firecrawl_client.py` + `settings_page.py`).
- [x] **Task 3:** Implement Slice 2 (Firecrawl 1st priority in `social_judge.py`, `tiktok_search.py`, `social_verify.py`, `social_verifier.py` + P5).
- [x] **Task 4:** Implement Slice 3 (P1–P4 fixes in `social_resolve.py`, `youtube_existence.py`, `social_verifier.py`).
- [x] **Task 5:** Run full test suite (`pytest -m "not live"`), `ruff check`, and `graphify update .`.
