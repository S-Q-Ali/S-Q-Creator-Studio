"""Facebook page video listing.

No library lists a page's videos, and the official Graph API wants a Page
access token with ``pages_manage_posts`` — Meta App Review that an
open-source desktop app cannot get. So the page's Videos tab is read in the
app's own browser: it renders every video as a link, and yt-dlp downloads
them from there.

That tab shows a visitor who is not signed in the first screen only — 21
videos for ``nasa``, 9 for ``natgeo``. Behind the tab the page pages its
own video list, and that query answers a visitor without a sign-in, so the
listing asks it for the rest of the list and hands both halves on.

This leg is experimental: it reads a page Meta can change at any time.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Iterable
from typing import Any

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.core.listing import Listing

logger = logging.getLogger(__name__)

_PAGE_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w-]+\.)?facebook\.com/(?P<name>[A-Za-z0-9.\-]{1,60})(?P<rest>/[^?#]*)?",
    re.IGNORECASE,
)
_VIDEO_ID_RE = re.compile(r"/videos/(?:[^/\"]+/)?(\d{6,})")

#: The query that pages the list behind the Videos tab.
_QUERY_NAME = "PagesCometChannelTabAllVideosCardImplPaginationQuery"

#: Facebook renames this query with every deploy, so its id is read from the
#: page's own JavaScript instead of being written down here.
_OPERATION_RE = re.compile(re.escape(_QUERY_NAME) + r"_facebookRelayOperation")
_DOC_ID_RE = re.compile(r'a\.exports="(\d+)"')
_SCRIPT_RE = re.compile(r'<script[^>]+src="([^"]+\.js[^"]*)"')

#: The token the page hands to every visitor, and the page it belongs to.
_TOKEN_RE = re.compile(r'"lsd","value":"([^"]+)"')
_TOKEN_SHORT_RE = re.compile(r'"l":"([^"]+)"')
_PAGE_ID_RE = re.compile(r'"pageID":"(\d+)"')

#: Where the page's video list is, and where that first screen ended.
_LIST_MARKER = '"all_videos":{"edges"'
_CURSOR_RE = re.compile(r'"end_cursor":"([^"]+)"')

#: How many videos one answer of the query carries.
_PAGE_SIZE = 9

#: How many of the page's JavaScript bundles to read before giving up.
_MAX_BUNDLES = 25

#: How long one bundle may take to load.
_BUNDLE_TIMEOUT = 30

#: How many answers of the query one listing may ask for.
_MAX_REQUESTS = 1000

#: Pause between two paged answers.
_PAGE_GAP = 0.4

#: How long the paging may take.
MAX_PAGING_SECONDS = 120.0

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


class PagingUnavailable(Exception):
    """Facebook would not page past the first screen."""


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


# --------------------------------------------------------------------------- #
# The page's own paging
# --------------------------------------------------------------------------- #
def _checksum(token: str) -> str:
    """Facebook's own checksum of the token it hands to a visitor.

    The formula is the one Facebook's own clients use: a ``2`` followed by
    the sum of the token's character codes.
    """
    return "2" + str(sum(ord(char) for char in token))


def _http():
    """An HTTP session that looks like the browser to Facebook.

    Facebook answers a plain client with a 400 — it checks the browser's
    fingerprint — so the request carries curl_cffi's Chrome impersonation.
    """
    from curl_cffi import requests

    return requests.Session(impersonate="chrome")


def _query_id(html: str, session: Any, deadline: float | None = None) -> str | None:
    """The id of the paging query, read from the page's own JavaScript.

    Facebook renames the query with every deploy, so writing the id down
    would break this leg within days.

    ``deadline`` bounds the harvest. Every bundle is a request, and a page
    that names two dozen of them can take longer than the whole paging
    budget.
    """
    for url in [u.replace("\\/", "/") for u in _SCRIPT_RE.findall(html)][:_MAX_BUNDLES]:
        if deadline is not None and time.monotonic() > deadline:
            logger.info("the paging query id was not found before the budget ran out")
            return None
        if not url.startswith("http"):
            url = "https://www.facebook.com" + url
        timeout = float(_BUNDLE_TIMEOUT)
        if deadline is not None:
            timeout = max(1.0, min(timeout, deadline - time.monotonic()))
        try:
            body = session.get(url, timeout=timeout).text
        except Exception as exc:  # pragma: no cover - a bundle that will not load
            logger.debug("a page bundle did not load: %s", exc)
            continue
        found = _OPERATION_RE.search(body)
        if not found:
            continue
        query_id = _DOC_ID_RE.search(body[found.start() : found.start() + 400])
        if query_id:
            return query_id.group(1)
    return None


def _first_cursor(html: str) -> str | None:
    """Where the page's own first screen of the list ended."""
    start = html.find(_LIST_MARKER)
    if start == -1:
        return None
    info = html.find('"page_info"', start)
    if info == -1:
        return None
    cursor = _CURSOR_RE.search(html[info : info + 300])
    return cursor.group(1) if cursor else None


def _ask(
    session: Any,
    page: str,
    token: str,
    page_id: str,
    query_id: str,
    cursor: str,
    request_number: int,
) -> tuple[list[str], str | None, bool]:
    """One answer of the paging query: the video ids, and where it ended.

    The token travels in the request body and a header — never in the URL,
    a log line or an error message.
    """
    variables = {
        "alwaysIncludeAudioRooms": False,
        "count": _PAGE_SIZE,
        "cursor": cursor,
        "pageID": page_id,
        "scale": 2,
        "showReactions": True,
        "useDefaultActor": False,
        "id": page_id,
    }
    try:
        answer = session.post(
            "https://www.facebook.com/api/graphql/",
            data={
                "av": "0",
                "__user": "0",
                "__a": "1",
                "__req": str(request_number),
                "__hs": "1920.1080",
                "dpr": "1",
                "__ccg": "GOOD",
                "__comet_req": "0",
                "lsd": token,
                "jazoest": _checksum(token),
                "fb_api_caller_class": "RelayModern",
                "fb_api_req_friendly_name": _QUERY_NAME,
                "server_timestamps": "true",
                "doc_id": query_id,
                "variables": json.dumps(variables),
            },
            headers={
                "x-fb-lsd": token,
                "content-type": "application/x-www-form-urlencoded",
                "referer": f"https://www.facebook.com/{page}/videos/",
                "origin": "https://www.facebook.com",
            },
            timeout=45,
        ).text
    except Exception as exc:
        # A transport error here is not a bug in the app, it is Facebook
        # refusing to answer. It has to arrive as a refusal, because an
        # arbitrary exception would escape the thread that asked for it.
        raise PagingUnavailable("Facebook would not answer the paging query.") from exc
    try:
        parsed = json.loads(answer)
    except json.JSONDecodeError:
        return ([], None, False)
    connection = ((parsed.get("data") or {}).get("node") or {}).get("all_videos") or {}
    ids = [
        ((edge or {}).get("node") or {}).get("id") for edge in connection.get("edges") or []
    ]
    info = connection.get("page_info") or {}
    return (
        [video_id for video_id in ids if video_id],
        info.get("end_cursor"),
        bool(info.get("has_next_page")),
    )


def paged_video_ids(
    page: str,
    limit: int,
    *,
    ops: Ops | None = None,
    progress: Callable[[int], None] | None = None,
    max_seconds: float = MAX_PAGING_SECONDS,
    known: Iterable[str] = (),
) -> tuple[list[str], str]:
    """The video ids the page's list holds behind its first screen.

    Returns the ids and the reason the walk stopped, if it stopped early.
    Raises :class:`PagingUnavailable` when Facebook will not answer.

    ``known`` is the videos the caller already has. They are not returned
    and not counted, so the caller's count is the whole list and not this
    leg's share of it.
    """
    ops = ops if ops is not None else Ops(None)
    target = f"facebook.com/{page}"
    started = time.monotonic()
    deadline = started + max_seconds
    ops.start("facebook.page", "relay", target)

    try:
        session = _http()
        html = session.get(
            f"https://www.facebook.com/{page}/videos/", timeout=45
        ).text
    except Exception as exc:
        ops.fail("facebook.page", "relay", target, str(exc))
        raise PagingUnavailable("Facebook would not serve the page.") from exc

    token = _TOKEN_RE.search(html) or _TOKEN_SHORT_RE.search(html)
    page_id = _PAGE_ID_RE.search(html)
    cursor = _first_cursor(html)
    query_id = _query_id(html, session, deadline)
    if not (token and page_id and cursor and query_id):
        ops.fail("facebook.page", "relay", target, "the page carried no paging query")
        raise PagingUnavailable("Facebook's page carried no paging query.")

    token_value = token.group(1)
    page_id_value = page_id.group(1)
    found: list[str] = []
    seen: set[str] = set(known)
    reason = ""
    for request_number in range(1, _MAX_REQUESTS):
        if len(found) >= limit:
            break
        if time.monotonic() > deadline:
            reason = "stopped early"
            break
        try:
            ids, next_cursor, has_next = _ask(
                session,
                page,
                token_value,
                page_id_value,
                query_id,
                cursor,
                request_number,
            )
        except PagingUnavailable:
            if not found:
                ops.fail("facebook.page", "relay", target, "the paging query was refused")
                raise
            # The videos already found are real, so they are kept and the
            # reason goes to the log.
            logger.info("Facebook stopped answering the paging of %s", page)
            reason = "Facebook stopped answering"
            break
        for video_id in ids:
            if video_id not in seen:
                seen.add(video_id)
                found.append(video_id)
        if progress is not None:
            progress(len(found))
        if not has_next or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(_PAGE_GAP)

    duration_ms = int((time.monotonic() - started) * 1000)
    detail = f"{len(found)} videos"
    if reason:
        detail = f"{detail}, {reason}"
    ops.ok("facebook.page", "relay", target, detail=detail, duration_ms=duration_ms)
    return (found, reason)


def _default_pager(
    ops: Ops, progress: Callable[[int], None] | None, known: list[str]
) -> Callable[[str, int], tuple[list[str], str]]:
    """The pager used when the caller names none.

    ``known`` is what the browser leg already found. The count the caller
    sees is the whole list and not this leg's share of it, and a video both
    engines name is counted once.
    """

    def pager(name: str, remaining: int) -> tuple[list[str], str]:
        report = (
            None if progress is None else (lambda found: progress(len(known) + found))
        )
        return paged_video_ids(
            name, remaining, ops=ops, progress=report, known=known
        )

    return pager


class _Progress:
    """The count the user sees, so it never goes backwards.

    The listing counts two engines' work — the browser's first screen and
    the page's own query — and the two can name the same video. A counter
    that reported the larger number and then the smaller one would read as
    a list that shrank.
    """

    def __init__(self, report: Callable[[int], None] | None, limit: int) -> None:
        self._report = report
        self._limit = limit
        self._count = 0

    def __call__(self, found: int) -> None:
        count = max(self._count, min(found, self._limit))
        if count == self._count:
            return
        self._count = count
        if self._report is not None:
            self._report(count)


def list_page_videos(
    page: str,
    limit: int = 20,
    *,
    ops: Ops | None = None,
    progress: Callable[[int], None] | None = None,
    session: Any | None = None,
    pager: Callable[[str, int], tuple[list[str], str]] | None = None,
) -> Listing:
    """List a public page's videos as page permalinks.

    ``session`` is a :class:`BrowserSession`; the caller may pass one to
    reuse a browser. The tests pass a stand-in.

    ``pager`` asks the page for the videos behind its first screen. The
    tests pass a stand-in, so no test needs the network.

    Raises :class:`FacebookError` with a message fit to show the user.
    """
    limit = max(1, int(limit))
    ops = ops if ops is not None else Ops(None)
    target = f"facebook.com/{page}"
    ops.start("facebook.list", "browser", target)
    started = time.monotonic()
    counter = _Progress(progress, limit)

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
    finally:
        if own_session:
            try:
                session.close()
            except Exception as exc:  # pragma: no cover - closing is best effort
                logger.debug("closing the browser failed: %s", exc)

    video_ids = video_ids_from_links(links)[:limit]
    browser_count = len(video_ids)
    counter(browser_count)

    # The tab stops at its first screen. The page's own query pages the list
    # behind it, and that one answers a visitor without a sign-in.
    reason = ""
    paged_count = 0
    if len(video_ids) < limit:
        if pager is None:
            pager = _default_pager(ops, counter, video_ids)
        try:
            paged, reason = pager(name, limit - len(video_ids))
        except PagingUnavailable as exc:
            logger.info("Facebook would not page %s: %s", name, exc)
            reason = "first screen only"
        else:
            for video_id in paged:
                if video_id not in video_ids:
                    video_ids.append(video_id)
            paged_count = len(video_ids) - browser_count

    urls = [video_permalink(name, video_id) for video_id in video_ids]

    duration_ms = int((time.monotonic() - started) * 1000)
    if urls:
        if paged_count:
            engine = "browser+relay"
            detail = (
                f"{len(urls)} videos "
                f"({browser_count} from the browser, {paged_count} from the page's own list)"
            )
        else:
            engine = "browser"
            detail = f"{len(urls)} videos"
        ops.ok(
            "facebook.list",
            engine,
            target,
            detail=detail,
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
    counter(len(urls))
    return Listing(urls, reason)
