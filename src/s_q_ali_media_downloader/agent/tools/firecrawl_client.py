"""Firecrawl v1 REST client for web search and rendered page scraping.

Firecrawl is the 1st-priority web search and page-scrape engine when a key is
configured in Settings -> AI Keys (or ``FIRECRAWL_API_KEY`` in the
environment). Every answer it returns is still fed through the deterministic
ownership rules in ``social_verify.py``.

Security rule: ``api_key`` and ``Authorization`` headers never appear in a URL,
log line, exception message, or ``Ops`` entry.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from s_q_ali_media_downloader.agent.tools.browser import Page
from s_q_ali_media_downloader.core import settings_store

FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"
FIRECRAWL_KEY_SETTING = "firecrawl_api_key"

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


class FirecrawlUnavailable(RuntimeError):
    """Firecrawl is not configured or did not answer usefully."""


@dataclass(frozen=True)
class SearchHit:
    """One search result from Firecrawl /v1/search."""

    url: str
    title: str = ""
    description: str = ""
    markdown: str = ""


def firecrawl_key() -> str | None:
    """The Firecrawl key: environment override first, then the sealed store."""
    from_env = (os.environ.get("FIRECRAWL_API_KEY") or "").strip()
    if from_env:
        return from_env
    stored = (settings_store.get_setting(FIRECRAWL_KEY_SETTING) or "").strip()
    return stored or None


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _error_detail(response: httpx.Response) -> str:
    if response.status_code == 401:
        return "Invalid Firecrawl API key (401 Unauthorized)."
    if response.status_code == 402:
        return "Firecrawl credit quota exhausted (402 Payment Required)."
    if response.status_code == 429:
        return "Firecrawl rate limit reached (429 Too Many Requests)."
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return (response.text or "")[:160]
    if isinstance(body, dict):
        msg = body.get("error") or body.get("message")
        if msg:
            return str(msg)[:160]
    return f"HTTP {response.status_code}"


def test_firecrawl_key(api_key: str | None = None) -> str:
    """Verify a Firecrawl key via the zero-cost credit-usage endpoint."""
    key = (api_key or firecrawl_key() or "").strip()
    if not key:
        raise FirecrawlUnavailable(
            "No Firecrawl API key configured. Add one in Settings > AI Keys."
        )
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{FIRECRAWL_BASE}/team/credit-usage",
                headers=_headers(key),
            )
    except httpx.HTTPError as exc:
        raise FirecrawlUnavailable(f"Could not reach Firecrawl: {exc}") from exc

    if response.status_code != 200:
        raise FirecrawlUnavailable(_error_detail(response))

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise FirecrawlUnavailable("Firecrawl answered with invalid JSON.") from exc

    data = (payload.get("data") if isinstance(payload, dict) else None) or {}
    remaining = (
        data.get("remainingCredits")
        if "remainingCredits" in data
        else data.get("remaining_credits")
    )
    if remaining is not None:
        return f"{remaining} credits left"
    return "active"


def search(
    query: str,
    *,
    limit: int = 5,
    api_key: str | None = None,
    timeout: float = 30.0,
) -> list[SearchHit]:
    """Run a web search through Firecrawl /v1/search."""
    key = (api_key or firecrawl_key() or "").strip()
    if not key:
        raise FirecrawlUnavailable("No Firecrawl API key configured.")
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{FIRECRAWL_BASE}/search",
                headers=_headers(key),
                json={"query": query, "limit": max(1, min(limit, 10))},
            )
    except httpx.HTTPError as exc:
        raise FirecrawlUnavailable(f"Could not reach Firecrawl search: {exc}") from exc

    if response.status_code != 200:
        raise FirecrawlUnavailable(_error_detail(response))

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise FirecrawlUnavailable("Firecrawl search returned invalid JSON.") from exc

    rows = (payload.get("data") if isinstance(payload, dict) else None) or []
    hits: list[SearchHit] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        hits.append(
            SearchHit(
                url=url,
                title=str(row.get("title") or "").strip(),
                description=str(row.get("description") or "").strip(),
                markdown=str(row.get("markdown") or "").strip(),
            )
        )
    return hits


def scrape_page(
    url: str,
    *,
    api_key: str | None = None,
    timeout: float = 30.0,
) -> Page:
    """Scrape one URL via Firecrawl /v1/scrape into a browser.Page."""
    key = (api_key or firecrawl_key() or "").strip()
    if not key:
        raise FirecrawlUnavailable("No Firecrawl API key configured.")
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{FIRECRAWL_BASE}/scrape",
                headers=_headers(key),
                json={"url": url, "formats": ["markdown", "links"]},
            )
    except httpx.HTTPError as exc:
        raise FirecrawlUnavailable(f"Could not reach Firecrawl scrape: {exc}") from exc

    if response.status_code != 200:
        raise FirecrawlUnavailable(_error_detail(response))

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise FirecrawlUnavailable("Firecrawl scrape returned invalid JSON.") from exc

    data = (payload.get("data") if isinstance(payload, dict) else None) or {}
    meta_raw = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    markdown = str(data.get("markdown") or "").strip()
    title = str(meta_raw.get("title") or meta_raw.get("ogTitle") or "").strip()
    og_title = str(meta_raw.get("ogTitle") or meta_raw.get("og:title") or title).strip()
    og_desc = str(
        meta_raw.get("ogDescription")
        or meta_raw.get("og:description")
        or meta_raw.get("description")
        or ""
    ).strip()
    og_url = str(
        meta_raw.get("ogUrl")
        or meta_raw.get("og:url")
        or meta_raw.get("sourceURL")
        or url
    ).strip()

    raw_links = data.get("links") if isinstance(data.get("links"), list) else []
    links = [str(link).strip() for link in raw_links if str(link).strip()]
    for match in _URL_RE.findall(markdown):
        clean = match.rstrip(".,;:)]}\"'")
        if clean not in links:
            links.append(clean)

    return Page(
        url=og_url or url,
        title=title,
        text=markdown,
        links=links,
        meta={
            "ogTitle": og_title,
            "ogDescription": og_desc,
            "ogUrl": og_url,
            "description": str(meta_raw.get("description") or og_desc),
        },
    )
