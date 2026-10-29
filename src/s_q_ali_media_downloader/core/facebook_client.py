"""Facebook page video listing.

No library lists a page's videos, and the official Graph API wants a Page
access token with ``pages_manage_posts`` — Meta App Review that an
open-source desktop app cannot get. So the page's Videos tab is read in the
app's own browser: it renders every video as a link, and yt-dlp downloads
them from there.

Measured ceiling (2026-10-29): a visitor without a session sees the **first
screen only** — 21 videos for ``nasa``, 9 for ``natgeo``. Facebook's own
pagination route answers ``"payload": null`` to such a visitor, so there is
no anonymous way past it. The client says that out loud instead of handing
back a short list quietly.

This leg is experimental: it reads a page Meta can change at any time.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Iterable
from typing import Any

from s_q_ali_media_downloader.agent.opslog import Ops

logger = logging.getLogger(__name__)

_PAGE_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w-]+\.)?facebook\.com/(?P<name>[A-Za-z0-9.\-]{1,60})(?P<rest>/[^?#]*)?",
    re.IGNORECASE,
)
_VIDEO_ID_RE = re.compile(r"/videos/(?:[^/\"]+/)?(\d{6,})")

#: Facebook paths that are not a page.
_RESERVED = frozenset(
    {
        "groups",
        "events",
        "watch",
        "watchparty",
        "share",
        "reel",
        "profile.php",
        "help",
        "login",
        "settings",
        "privacy",
        "policies",
        "legal",
    }
)

#: A path under the page name that points at one item rather than the page.
_ITEM_SEGMENTS = frozenset(
    {"videos", "reel", "posts", "photos", "permalink.php", "share", "groups"}
)


class FacebookError(Exception):
    """Base error for every Facebook listing failure."""


class FacebookNotFound(FacebookError):
    """No such page."""


class FacebookUnavailable(FacebookError):
    """The page could not be read — no browser, or Facebook refused."""


def normalize_page(text: str) -> tuple[str | None, str | None]:
    """Turn a page name or a page link into ``(page name, videos url)``.

    A link to one video, one post or one photo is not a page.
    """
    raw = (text or "").strip()
    if not raw:
        return (None, None)
    match = _PAGE_URL_RE.search(raw)
    if match:
        name = match.group("name")
        rest = (match.group("rest") or "").strip("/")
    else:
        name = raw.lstrip("@").strip("/ ")
        rest = ""
    if not name or name.lower() in _RESERVED:
        return (None, None)
    if not re.fullmatch(r"[A-Za-z0-9.\-]{1,60}", name):
        return (None, None)
    first, _, more = rest.partition("/")
    if first.lower() in _ITEM_SEGMENTS and more:
        return (None, None)
    return (name, f"https://www.facebook.com/{name}/videos/")


def video_permalink(page: str, video_id: str) -> str:
    """The page URL of one video.

    Facebook resolves a video by its id, so the page it was seen on is enough
    to build a link that yt-dlp can download.
    """
    return f"https://www.facebook.com/{page}/videos/{video_id}"


def video_ids_from_links(links: Iterable[str]) -> list[str]:
    """The video ids behind the links of a Videos tab, in the order shown."""
    ids: list[str] = []
    for href in links:
        for video_id in _VIDEO_ID_RE.findall(href or ""):
            if video_id not in ids:
                ids.append(video_id)
    return ids


def list_page_videos(
    page: str,
    limit: int = 20,
    *,
    ops: Ops | None = None,
    progress: Callable[[int], None] | None = None,
    session: Any | None = None,
) -> list[str]:
    """List a public page's videos as page permalinks.

    ``session`` is a :class:`BrowserSession`; the caller may pass one to
    reuse a browser. The tests pass a stand-in.

    Raises :class:`FacebookError` with a message fit to show the user.
    """
    limit = max(1, int(limit))
    ops = ops if ops is not None else Ops(None)
    target = f"facebook.com/{page}"
    ops.start("facebook.list", "browser", target)
    started = time.monotonic()

    name, videos_url = normalize_page(page)
    if not name:
        ops.fail("facebook.list", "browser", target, "not a page")
        raise FacebookNotFound(f"{page} does not look like a Facebook page.")

    own_session = session is None
    if own_session:
        from s_q_ali_media_downloader.agent.tools.browser import BrowserSession

        session = BrowserSession(headless=True, timeout_ms=45000)

    try:
        try:
            rendered = session.open(videos_url, wait_ms=6000)
        except Exception as exc:
            ops.fail("facebook.list", "browser", target, str(exc))
            raise FacebookUnavailable(
                "Facebook could not be reached. Check the page name and try again."
            ) from exc

        links = list(getattr(rendered, "links", []) or [])
        video_ids = video_ids_from_links(links)[:limit]
        urls = [video_permalink(name, video_id) for video_id in video_ids]
    finally:
        if own_session:
            try:
                session.close()
            except Exception as exc:  # pragma: no cover - closing is best effort
                logger.debug("closing the browser failed: %s", exc)

    duration_ms = int((time.monotonic() - started) * 1000)
    if urls:
        ops.ok(
            "facebook.list",
            "browser",
            target,
            detail=f"{len(urls)} videos",
            duration_ms=duration_ms,
        )
    else:
        ops.skip(
            "facebook.list",
            "browser",
            target,
            detail="no videos on the page",
            duration_ms=duration_ms,
        )
    if progress is not None:
        progress(len(urls))
    return urls
