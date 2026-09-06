"""Keyless YouTube autocomplete (ported from Niche-Scope's lib/autocomplete.ts).

Suggestions come straight from YouTube's search logs via the undocumented
``suggestqueries.google.com`` endpoint — no API key, no quota cost.
"""

from __future__ import annotations

import time

import httpx

AUTOCOMPLETE_BASE_URL = "https://suggestqueries.google.com/complete/search"
AUTOCOMPLETE_TIMEOUT_MS = 10_000

ALPHABET: list[str] = [chr(97 + i) for i in range(26)]
DIGITS: list[str] = [str(i) for i in range(10)]
QUESTION_WORDS: list[str] = ["what", "how", "why", "who", "when", "where", "vs"]


class AutocompleteError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def fetch_suggestions(
    query: str,
    *,
    hl: str = "en",
    gl: str = "us",
    retries: int = 3,
    timeout_ms: int = AUTOCOMPLETE_TIMEOUT_MS,
) -> list[str]:
    """Fetch YouTube autocomplete suggestions for a query. Best-effort + retry."""
    params = {"client": "firefox", "ds": "yt", "hl": hl, "gl": gl, "q": query}
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = httpx.get(
                AUTOCOMPLETE_BASE_URL,
                params=params,
                headers=headers,
                timeout=timeout_ms / 1000,
            )
            if resp.status_code == 502 and attempt < retries:
                time.sleep(0.4 * 2**attempt)
                continue
            if resp.status_code != 200:
                raise AutocompleteError(
                    f"Autocomplete request failed with status {resp.status_code}",
                    resp.status_code,
                )
            parsed = resp.json()
            raw = parsed[1] if isinstance(parsed, list) and len(parsed) > 1 else []
            return [s for s in raw if isinstance(s, str)]
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.4 * 2**attempt)

    if isinstance(last_error, AutocompleteError):
        raise last_error
    raise AutocompleteError("Autocomplete endpoint unreachable")


def _add_dedup(results: dict[str, str], value: str) -> None:
    key = " ".join(value.lower().split())
    if key:
        results.setdefault(key, value)


def expand_seed(
    seed: str,
    *,
    hl: str = "en",
    gl: str = "us",
    retries: int = 3,
) -> list[str]:
    """Expand a seed by appending a-z / 0-9 prefixes and question words."""
    results: dict[str, str] = {}

    for suggestion in fetch_suggestions(seed, hl=hl, gl=gl, retries=retries):
        _add_dedup(results, suggestion)
    for prefix in [*ALPHABET, *DIGITS]:
        for suggestion in fetch_suggestions(f"{seed} {prefix}", hl=hl, gl=gl, retries=retries):
            _add_dedup(results, suggestion)
    for qw in QUESTION_WORDS:
        for suggestion in fetch_suggestions(f"{qw} {seed}", hl=hl, gl=gl, retries=retries):
            _add_dedup(results, suggestion)
    return list(results.values())
