"""Instagram profile listing.

yt-dlp cannot list an Instagram profile — its ``instagram:user`` extractor is
broken upstream (yt-dlp issue #4394, and ``InstagramUserIE._WORKING`` is
``False`` in the installed source). The listing is therefore done with
``instaloader``, a maintained MIT library that speaks Instagram's web API.

Only the *listing* lives here. The download leg stays with yt-dlp: this
module hands back **page permalinks** and never the CDN links instaloader
also exposes, because a CDN link carries an expiry token and stops working
minutes later.

The walk reads instaloader's timeline node rather than its ``Post`` object.
Building a ``Post`` fetches that post's full metadata — one request per
post, which is most of a walk's time — while the node already carries the
shortcode and the media type. Measured on a public profile: 2.9 s per post
through ``Post``, 0.85 s per post this way.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

from s_q_ali_media_downloader.agent.opslog import Ops
from s_q_ali_media_downloader.core.listing import Listing

logger = logging.getLogger(__name__)

#: Pause between two Instagram listings. Instagram answers 429 when it is
#: asked too quickly — measured: six listings in a row with this gap did not
#: trip it, two listings back to back did.
MIN_REQUEST_GAP = 3.0

#: How long one walk through a profile's timeline may take. A walk of a busy
#: profile runs for minutes, so it is bounded — and says where it stopped.
MAX_WALK_SECONDS = 180.0

#: The post types that carry a video of their own.
_VIDEO_TYPENAMES = frozenset({"GraphVideo", "XIGPolarisVideoMedia"})

#: The post types that hold a list of children, one of which may be a video.
_CAROUSEL_TYPENAMES = frozenset({"GraphSidecar", "XIGPolarisCarouselMedia"})

_PROFILE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/(?P<name>[A-Za-z0-9._]{1,30})/?(?:$|[?#])",
    re.IGNORECASE,
)
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")

#: Instagram paths that look like a handle but are not a profile.
_RESERVED = frozenset(
    {
        "about",
        "accounts",
        "challenge",
        "developer",
        "direct",
        "explore",
        "legal",
        "p",
        "reel",
        "reels",
        "stories",
        "tv",
    }
)

_last_call = 0.0


class InstagramError(Exception):
    """Base error for every Instagram listing failure."""


class InstagramRateLimited(InstagramError):
    """Instagram refused the request because it is rate-limiting this machine."""


class InstagramNotFound(InstagramError):
    """No such account."""


class InstagramPrivate(InstagramError):
    """The account is private; Instagram needs a signed-in session for it."""


def normalize_profile(text: str) -> tuple[str | None, str | None]:
    """Turn a handle or a profile link into ``(username, profile url)``.

    Returns ``(None, None)`` when the text is not a profile.
    """
    raw = (text or "").strip()
    if not raw:
        return (None, None)
    match = _PROFILE_URL_RE.search(raw)
    if match:
        name = match.group("name")
    else:
        name = raw.lstrip("@").strip("/ ")
    if not name or not _HANDLE_RE.match(name) or name.lower() in _RESERVED:
        return (None, None)
    return (name, f"https://www.instagram.com/{name}/")


def profile_permalink(shortcode: str) -> str:
    """The page URL of one post.

    Instagram serves a reel under this same path, so one form covers posts,
    reels and IGTV.
    """
    return f"https://www.instagram.com/p/{shortcode}/"


def carries_video(post: Any) -> bool:
    """True when the post holds a video.

    A plain photo post is not worth queueing. A carousel (sidecar) is worth
    queueing when any of its children is a video.
    """
    typename = getattr(post, "typename", "")
    if typename in _VIDEO_TYPENAMES:
        return True
    if typename in _CAROUSEL_TYPENAMES:
        try:
            return any(post.get_is_videos())
        except Exception:  # pragma: no cover - malformed node
            return False
    return False


class _RawPost:
    """One timeline node, read without the per-post metadata request.

    instaloader wraps every node of a timeline in a ``Post``, and building
    that ``Post`` fetches the post's full metadata — one HTTP request per
    post, which is most of what a walk spends. The timeline node already
    carries the shortcode and the media type, so the walk reads the node
    itself and only asks for the metadata of a carousel, which does not say
    what its children are.
    """

    #: The timeline node carries no timestamp. The iterator only compares
    #: dates to keep track of the newest item, so one fixed date is enough.
    _NO_DATE = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def __init__(self, node: dict[str, Any], context: Any) -> None:
        self.node = node
        self._context = context

    @property
    def shortcode(self) -> str:
        return self.node.get("code") or self.node.get("shortcode") or ""

    @property
    def typename(self) -> str:
        return self.node.get("__typename") or ""

    @property
    def date_local(self) -> datetime:
        return self._NO_DATE

    def get_is_videos(self) -> list[bool]:
        """Whether the post holds a video.

        A video is decided by the node alone. A carousel does not say what
        its children are, so its metadata is fetched — the one request per
        carousel that the fast path still pays.
        """
        if self.typename not in _CAROUSEL_TYPENAMES:
            return [self.node.get("media_type") == 2]
        from instaloader.structures import Post

        post = Post.from_shortcode(self._context, self.shortcode)
        return list(post.get_is_videos())


def _raw_timeline(posts: Any, context: Any) -> Any:
    """The profile's timeline, read as raw nodes.

    instaloader keeps the session, the query and the paging; only what each
    node is wrapped in changes here. If instaloader ever stops handing the
    node over, the walk falls back to instaloader's own posts — slower, but
    the same walk.
    """
    if not hasattr(posts, "_node_wrapper"):
        return posts
    posts._node_wrapper = lambda node: (
        _RawPost(node, context) if isinstance(node, dict) else node
    )
    return posts


def media_permalinks(
    posts: Iterable[Any],
    limit: int,
    progress: Callable[[int], None] | None = None,
    collected: list[str] | None = None,
    max_seconds: float | None = None,
) -> Listing:
    """Turn a timeline's posts into page permalinks, newest first.

    ``collected`` is filled in place. Instagram cuts a long walk off with a
    429, and the posts found before that are still worth queueing — so the
    caller hands in the list it wants the URLs in and keeps it either way.

    ``max_seconds`` bounds the walk. When the budget runs out the walk stops
    and the listing carries the reason.
    """
    urls = [] if collected is None else collected
    deadline = None if max_seconds is None else time.monotonic() + max_seconds
    reason = ""
    for post in posts:
        if deadline is not None and time.monotonic() > deadline:
            reason = f"stopped early at the {int(max_seconds)}-second limit"
            break
        if not carries_video(post):
            continue
        shortcode = getattr(post, "shortcode", "")
        if not shortcode:
            continue
        url = profile_permalink(shortcode)
        if url not in urls:
            urls.append(url)
        if progress is not None:
            progress(len(urls))
        if len(urls) >= limit:
            break
    return Listing(urls, reason)


def _build_loader():
    """An instaloader that lists and never downloads.

    The default rate controller is kept on purpose: it is the pacing that
    measured a clean run. A faster one is what earns a 429.
    """
    import instaloader

    return instaloader.Instaloader(
        download_videos=False,
        download_pictures=False,
        download_video_thumbnails=False,
        save_metadata=False,
        quiet=True,
        max_connection_attempts=1,
        request_timeout=30.0,
    )


def _wait_for_gap() -> None:
    """Keep at least ``MIN_REQUEST_GAP`` between two listings."""
    global _last_call
    elapsed = time.monotonic() - _last_call
    if _last_call and elapsed < MIN_REQUEST_GAP:
        time.sleep(MIN_REQUEST_GAP - elapsed)
    _last_call = time.monotonic()


def list_profile_media(
    username: str,
    limit: int = 20,
    *,
    ops: Ops | None = None,
    progress: Callable[[int], None] | None = None,
    max_seconds: float = MAX_WALK_SECONDS,
) -> Listing:
    """List a public profile's video posts as page permalinks.

    Raises :class:`InstagramError` (or one of its subclasses) with a message
    fit to show the user.
    """
    try:
        import instaloader
        from instaloader.exceptions import (
            LoginRequiredException,
            PrivateProfileNotFollowedException,
            ProfileNotExistsException,
            QueryReturnedForbiddenException,
            TooManyRequestsException,
        )
    except ImportError as exc:
        raise InstagramError(
            "Instaloader is not installed. Run: pip install -r requirements.txt"
        ) from exc

    limit = max(1, int(limit))
    started = time.monotonic()
    _wait_for_gap()
    ops = ops if ops is not None else Ops(None)
    target = f"@{username}"
    ops.start("instagram.list", "instaloader", target)

    loader = _build_loader()
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except ProfileNotExistsException as exc:
        ops.fail("instagram.list", "instaloader", target, "no such account")
        raise InstagramNotFound(f"There is no Instagram account called {target}.") from exc
    except (PrivateProfileNotFollowedException, LoginRequiredException) as exc:
        ops.fail("instagram.list", "instaloader", target, "private account")
        raise InstagramPrivate(
            f"{target} is private. Instagram only lists public accounts without a sign-in."
        ) from exc
    except TooManyRequestsException as exc:
        ops.fail("instagram.list", "instaloader", target, "rate limited")
        raise InstagramRateLimited(
            "Instagram is rate-limiting this machine. Wait a few minutes, then try again."
        ) from exc
    except QueryReturnedForbiddenException as exc:
        ops.fail("instagram.list", "instaloader", target, "refused")
        raise InstagramError("Instagram refused the request. Try again later.") from exc
    except Exception as exc:
        ops.fail("instagram.list", "instaloader", target, str(exc))
        raise InstagramError(f"Instagram could not be reached: {exc}") from exc

    urls: list[str] = []
    try:
        listing = media_permalinks(
            _raw_timeline(profile.get_posts(), loader.context),
            limit,
            progress,
            urls,
            max_seconds,
        )
    except TooManyRequestsException as exc:
        if urls:
            # Instagram cut the walk off halfway. The posts already found are
            # real, so they are kept and the reason goes to the log.
            logger.warning(
                "Instagram rate-limited the listing of %s after %d videos",
                target,
                len(urls),
            )
            ops.skip(
                "instagram.list",
                "instaloader",
                target,
                detail=f"rate limited after {len(urls)} videos",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            return Listing(urls, "Instagram rate-limited the listing")
        ops.fail("instagram.list", "instaloader", target, "rate limited")
        raise InstagramRateLimited(
            "Instagram is rate-limiting this machine. Wait a few minutes, then try again."
        ) from exc
    except Exception as exc:
        ops.fail("instagram.list", "instaloader", target, str(exc))
        raise InstagramError(f"Instagram could not be read: {exc}") from exc

    duration_ms = int((time.monotonic() - started) * 1000)
    if urls:
        detail = f"{len(urls)} videos"
        if listing.reason:
            detail = f"{detail}, {listing.reason}"
        ops.ok("instagram.list", "instaloader", target, detail=detail, duration_ms=duration_ms)
    else:
        ops.skip(
            "instagram.list",
            "instaloader",
            target,
            detail="no video posts",
            duration_ms=duration_ms,
        )
    return listing
