# Spec — TikTok discovery when TikTok refuses to list

## Objective

The TikTok-first mode ("TikTok - YouTube, creators without YT") returns 0
profiles for every `#tag` and keyword query, so the mode only works when the
user already knows the creators. This spec makes a hashtag/keyword query
useful again by asking the search-grounded AI for public TikTok profiles and
feeding them into the existing YouTube-presence check.

**User story.** As a creator-researcher, I type `#ishowspeed` (or `cats`), and
the app lists TikTok creators for that niche with their YouTube status,
instead of an empty table.

**Success looks like:** with an AI key configured, a tag query that TikTok
refuses to list still shows candidates, and the log says the handles were
proposed by the AI rather than read from TikTok.

### Measured evidence (2026-10-29)

| Route | Result |
|---|---|
| `tiktok.com/tag/<tag>` over HTTP (httpx and curl_cffi Chrome) | 200, ~390 KB shell, 0 `uniqueId` |
| Rendered tag page in the app's Chromium | 224 chars, 9 links, 0 handles |
| Signed `/api/challenge/item_list/` (X-Bogus) | 200, 0 bytes |
| `m.tiktok.com/tag` | 404 |
| yt-dlp tag extract | 1 `None` entry |
| yt-dlp profile, real and fake handle | both fail: "Unable to extract secondary user ID" |
| Public mirror (tikwm) | Cloudflare / empty list |

### Measured provider constraints (2026-10-30)

| Provider | Result |
|---|---|
| Gemini grounded (`google_search`), 3 models | HTTP 200 without the tool, 429 "quota exceeded" with it: the free grounded quota is spent |
| Groq `gpt-oss-120b` + `browser_search` | Cloudflare 524 after ~125 s on every request |
| Groq `gpt-oss-20b` + `browser_search`, short prompt | 200 in 4-6 s, real `tiktok.com/@handle` with 10 cited results |
| Groq `gpt-oss-20b` free tier | 8 000 tokens/minute and 200 000 tokens/day |

So the Groq search leg now names `gpt-oss-20b`; the 120b model stays for
plain asks. A keyless or quota-spent run still ends in the honest note.

## Assumptions

1. This mode already needs an AI key for the YouTube check, so a grounded
   search call is not a new prerequisite.
2. `#tag` text (without `#`) and the remaining words are the niche to search.
3. TikTok exposes no local way to confirm a proposed profile, so the result is
   labelled "proposed", never "verified".
4. One search-grounded call per run is an acceptable cost.
5. The tab layout stays; only the hint text changes.

→ Correct these now or I proceed with them.

## Tech stack

Python 3.10+ source, PySide6, httpx, yt-dlp, Gemini/Groq REST (no SDK). Tests
with pytest. Build venv: `source/venv`.

## Commands

```
Test:  QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -q -m "not live"
Lint:  ./source/venv/Scripts/python.exe -m ruff check src tests
Graph: graphify update .
Build: MSYS_NO_PATHCONV=1 GITHUB_ACTIONS=1 cmd.exe /c "release\build.bat"
```

## Project structure

```
src/s_q_ali_media_downloader/agent/tools/social_judge.py   AI search grounding
src/s_q_ali_media_downloader/agent/tools/tiktok_search.py  TikTok discovery tiers
src/s_q_ali_media_downloader/agent/orchestrator.py         run wiring, budget, ops
src/s_q_ali_media_downloader/ui/agent_tab.py               user-facing hint
tests/test_tiktok_pipeline.py                              discovery tests
tests/test_social_judge.py                                 AI parse tests
```

## Code style

Match the surrounding modules: one-line docstrings that say why, `logger` over
prints, no comments restating code.

```python
def propose_tiktok_creators(niche: str, limit: int, *, ops: Ops | None = None) -> list[str]:
    """Ask the web which public TikTok profiles match a niche."""
    answer = _ask_searched(
        TIKTOK_DISCOVERY_PROMPT.format(niche=niche[:DESCRIPTION_LIMIT], limit=limit),
        ("tiktok",),
        ops=ops,
        parse=_parse_creator_handles,
    )
    return list(answer.answers)[:limit]
```

## Testing strategy

pytest, offline only (`-m "not live"`). Tests inject fake proposers and fake
provider answers; no test touches TikTok, Gemini or the user's key store. New
logic gets tests first (red), then the implementation (green).

## Boundaries

- **Always:** run the offline suite and ruff before committing; keep cookie
  values, keys and `Authorization` headers out of every log line and message.
- **Ask first:** adding a dependency, changing CI, rebuilding the EXE.
- **Never:** add a TikTok login or session requirement; claim an AI handle was
  verified; print cookie material.

## Success criteria

1. `search_profiles("#x", proposer=fake)` returns the proposer's handles when
   the listing tiers are empty; `proposer=None` keeps today's result.
2. A seed query (`@handle`) never calls the proposer.
3. Parsing accepts a JSON list and fenced JSON of `tiktok.com/@handle` URLs,
   rejects everything else, strips `@`, dedupes and caps.
4. `run_tiktok_discovery` spends at most one search-budget call on discovery
   and logs where the handles came from.
5. Offline suite and ruff stay green.

## Open questions

None. Route chosen by the user: AI search grounding.
