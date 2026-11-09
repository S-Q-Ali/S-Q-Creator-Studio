# Spec — Firecrawl Primary Discovery + AI/Browser Fallback & Accuracy Fixes

## Objective

Make **Firecrawl** (`https://api.firecrawl.dev/v1`) the **1st-priority web search and page-scrape engine** across all 3 Discovery modes (`YouTube → Socials`, `TikTok → YouTube/FB/IG`, and `Social Discovery`), with a sealed API key field and zero-cost `Test` button in **Settings → AI Keys**, and use the existing **Gemini / Groq grounded search + `browser-use` agent browser + P1–P5 accuracy fixes** as the automatic fallback.

## Assumptions

1. Firecrawl is called directly over HTTPS via the already-installed `httpx` client (Ponytail Rule #4: zero new dependencies).
2. `firecrawl_api_key` ends with `_api_key`, so `core/settings_store.py` automatically seals it with DPAPI (Windows) or OS Keyring (Linux/macOS). `FIRECRAWL_API_KEY` in the environment overrides the stored value, matching `GEMINI_API_KEY` and `GROQ_API_KEY`.
3. Standing security rule: **API keys, cookies, and Authorization headers must never appear in a URL, log line, exception text, or `Ops` entry.**
4. Firecrawl is still a witness/scraper: scraped page content and search results go through the deterministic ownership rules (`social_verify.py`) before an account is marked `VERIFIED` / `FOUND`.

## Tech Stack

- Python 3.12+, PySide6, `httpx`, `pytest`

## Commands

```
Test: QT_QPA_PLATFORM=offscreen python -m pytest tests -q -m "not live"
Lint: python -m ruff check src tests
```

## Project Structure

```
src/s_q_ali_media_downloader/agent/tools/firecrawl_client.py   Firecrawl v1 REST client (key check, /v1/search, /v1/scrape -> Page)
src/s_q_ali_media_downloader/ui/settings_page.py               Firecrawl API key input + Test button + worker in AI KEYS card
src/s_q_ali_media_downloader/agent/tools/social_judge.py       Firecrawl 1st priority in _ask_searched + cited sources URL fallback (P5)
src/s_q_ali_media_downloader/agent/tools/tiktok_search.py      Firecrawl 1st -> Gemini/Groq fallback for TikTok keyword/tag discovery (#7)
src/s_q_ali_media_downloader/agent/tools/social_verify.py      Firecrawl scrape fallback before browser-use on UNKNOWN pages
src/s_q_ali_media_downloader/agent/tools/social_verifier.py    Firecrawl scrape fallback + multi-signal _identity_status (P3)
src/s_q_ali_media_downloader/agent/tools/social_resolve.py     Subscriber-weighted _best_match (P1) + description bio links (P2)
src/s_q_ali_media_downloader/agent/tools/youtube_existence.py  Subscriber tie-breaker (P1) + URL-unquoted backlinks & YT text handle (P4)
src/s_q_ali_media_downloader/agent/orchestrator.py             Keep all AI candidate URLs in Mode 1 & Mode 2 (P3)
tests/test_firecrawl_discovery.py                              Unit & regression tests for Firecrawl + P1–P5 accuracy fixes
```

## Code Style

```python
def search_web(query: str, *, limit: int = 5, api_key: str | None = None) -> list[SearchHit]:
    """Search the web via Firecrawl /v1/search. Raises FirecrawlUnavailable on failure."""
```

## Testing Strategy

Offline unit tests in `tests/test_firecrawl_discovery.py` using mocked `httpx` responses and Qt offscreen mode (`QT_QPA_PLATFORM=offscreen`):
- `firecrawl_key()` env override and `settings_store` DPAPI/keyring sealing
- `test_firecrawl_key()` against `/v1/team/credit-usage` (200 OK with remaining credits, 401 invalid key, 402 exhausted credits)
- `SettingsPage` Firecrawl key field, save/load, and `Test` button state
- Priority order in `_ask_searched`: Firecrawl first → Gemini second → Groq third
- TikTok keyword discovery fallback: Firecrawl `/v1/search` first → Gemini/Groq fallback when TikTok API & yt-dlp return 0 handles
- P1–P5 accuracy regressions (subscriber tie-breaker, description bio links, multi-candidate preservation, `%40` URL-unquoted backlinks, cited `sources` URL extraction)

## Boundaries

- **Always:** seal `firecrawl_api_key` at rest; never log keys or Authorization headers; run `pytest` and `ruff` after each slice.
- **Ask first:** adding any new PyPI dependency (none needed).
- **Never:** let an unverified scrape bypass `match_evidence` ownership checks.

## Success Criteria

1. Settings → `AI KEYS` shows `Firecrawl API key` (`fc-...`) with a working `Test` button and saves it encrypted via `settings_store`.
2. When `firecrawl_api_key` is configured, web-grounded checks (`propose_searched`, `propose_youtube_searched`), unreadable-page scrapes, and TikTok keyword searches use Firecrawl first and automatically fall back to Gemini → Groq → `browser-use` if Firecrawl is unconfigured or fails.
3. All P1–P5 accuracy fixes pass unit tests and the full offline test suite (`pytest -m "not live"`) + `ruff check` pass with 0 errors.
