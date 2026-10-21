# Capability Map: Social Discovery (YouTube → Facebook / Instagram / TikTok)

**Status:** proposed — awaiting human review of the module boundaries and the
accuracy contract before any module spec is written.

**Problem:** today the AI Finder starts with a YouTube *search* and only finds
social accounts that the creator linked in their own channel description. Paste
a channel URL, a name or a handle and there is no way to ask "where is this
person on Facebook, Instagram and TikTok?" — and when the bio is empty, the
answer is "no socials", which is usually wrong.

**The design rule that makes the accuracy work:** *the model proposes, the
network disposes.* Groq is a lead generator, never the source of truth. A
platform is reported as found only when a real page answered.

## Module map

| Module id | Responsibility | Depends on |
|---|---|---|
| `social-resolve` | Turn a channel URL, name or handle into exactly one channel record: title, handle, description, outbound links, subscriber count | — |
| `social-propose` | Groq (structured output) turns the channel record into ranked candidate handles per platform, each with its reason and a source label (`bio` / `model`) | `social-resolve` |
| `social-verify` | Probe every candidate on Facebook, Instagram and TikTok; attach the evidence; drop the ones that do not exist; keep the unknown ones as unknown | `social-propose` |
| `social-report` | The AI Finder gets a "Social Discovery" mode: a table per platform with status, confidence, evidence and the link, plus export | `social-verify` |

Build order: `social-resolve` → `social-propose` → `social-verify` →
`social-report`.

## What is reused, not rebuilt

| Existing piece | Used for |
|---|---|
| `niche_research/tools/youtube_client.py` | `fetch_channel` — resolves a URL or handle into a full channel record |
| `agent/tools/youtube_search.py` | `search_channels` — only when the input is a *name* rather than a URL or handle |
| `agent/tools/link_parser.py` | `extract_social_links` — the links in the creator's own bio. These are the **highest-confidence** candidates and they cost nothing |
| `agent/tools/social_verifier.py` | The Facebook / Instagram / TikTok probes, including the `VERIFIED` / `UNVERIFIED_HANDLE` / `NOT_FOUND` / `INCONCLUSIVE` rules |
| `agent/schema.py` | `SocialPresence`, `SocialStatus`, `SocialPlatform` — the result vocabulary |
| `agent/orchestrator.py` | The pipeline shape (search → enrich → verify → report) |
| `ui/agent_tab.py` | The AI Finder tab the new mode lives in |

## The accuracy contract (needs a human decision — see Open Questions)

| Outcome | Meaning | Shown as |
|---|---|---|
| **FOUND** | The page answered *and* the link is in the creator's own bio | Found — high confidence |
| **FOUND (weak)** | The page answered, but the candidate came from the model | Found — no bio link, with the model's reason |
| **NOT FOUND** | The page answered with a not-found signature | Not found |
| **UNKNOWN** | Network error, rate limit or a login wall | Unknown — *never* "missing" |
| **SUGGESTED** | The model proposed it and the probe could not decide | Suggested — unverified |

Rules that make this honest:

1. The model never sets a status. It only proposes candidates.
2. A candidate that is probed and does not exist is dropped, not shown as a lead.
3. A probe that could not decide is `UNKNOWN`, never `NOT_FOUND`.
4. Every found row carries its evidence: the bio link it came from, or the
   model reason, and the probe result.
5. The channel description is untrusted input: it is truncated, marked as data
   in the prompt, and never treated as an instruction.

## Cost and latency

- One Groq call per channel, structured output, ~600 prompt + ~200 completion
  tokens → roughly $0.0001 per channel on `openai/gpt-oss-20b`
  ($0.075 / $0.30 per 1M tokens, 1K RPM on the developer plan).
  Source: https://console.groq.com/docs/models
- 3–9 HTTP probes with the verifier's existing 2 s politeness delay.
- The whole run is one channel: a couple of seconds plus the probes.
- The installer carries the Playwright headless shell (~277 MB) so the
  feature works without Edge or Chrome; the full Chromium is not shipped
  because the feature only runs headless.

## Privacy

- What leaves the machine: the channel title, handle, and the first 600
  characters of the description, to Groq. Nothing else.
- The API key is stored DPAPI-sealed in the research database (already the
  case for the other providers) and never written to a log.
- The description is attacker-controlled text. It is passed as data inside a
  delimited block, and the model is told to ignore instructions inside it.

## Open Questions (blocking for the module specs)

1. **The Groq key in the database is invalid** — it returns
   `401 {"code":"invalid_api_key"}`. A working `gsk_...` key is needed for the
   live accuracy test. The code can be built and tested against a fake
   provider without it.
2. **The accuracy contract** — is "found only when verified, unverified model
   guesses shown separately as *suggested*" the behaviour you want, or should
   the model's best guess be shown as a lead even when it could not be
   verified?
3. **Input shape** — one channel per run (URL / name / handle), or a list?
   And when the input is only a *name*, should the model also propose which
   YouTube channel it is, or should that stay a YouTube search?
4. **Model choice** — `openai/gpt-oss-20b` (fastest, cheapest, already the
   project's Groq model) or `openai/gpt-oss-120b` (better at "I know this
   creator" recall, 4× the price)?

## Sources

- Groq chat completions (OpenAI-compatible):
  https://console.groq.com/docs/api-reference#chat-create
- Groq models, pricing and rate limits: https://console.groq.com/docs/models
- Structured outputs (`response_format: json_schema`):
  https://console.groq.com/docs/structured-outputs
