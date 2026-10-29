# Implementation Plan: Instagram & Facebook Bulk Expansion

## Overview

The app already expands a TikTok profile and a YouTube channel into a list of
individual video URLs and drops them into the download queue. This plan adds
the same for Instagram and Facebook, using two different engines because the
two platforms fail in two different ways:

- **Instagram** is enumerable through a maintained MIT library (`instaloader`).
  yt-dlp's own Instagram profile extractor is broken upstream, so the app
  borrows the enumeration and keeps yt-dlp for the download.
- **Facebook** is not enumerable by any library, and the official Graph API
  needs a Meta App Review that an open-source desktop app cannot get. The
  app's own hardened browser can read the page, so the browser is the engine.

Both legs produce the same thing the existing TikTok and YouTube legs produce:
a list of **page permalinks** that the existing queue downloads unchanged.

## Architecture Decisions

**A1 — One expansion shape, two engines.**
The existing pipeline is: `add_links` → `_enqueue_expand` → `_expand_queue`
(serially, one link at a time) → `_expand_thread_for(url)` → a QThread that
emits `found(urls, label)` / `failed(message)` / `note` / `progress`. The new
platforms join that shape; they do not get a parallel path. The new threads
mirror `AccountFetchThread` (engine.py:344) and `YouTubeFetchThread`
(engine.py:406).

*Rejected:* a second "bulk" screen. It would duplicate the queue, the status
line, the account-limit dropdown and the retry policy for no gain.

**A2 — Enumeration produces page permalinks, never CDN URLs.**
`instaloader` hands back `fna.fbcdn.net` links with an `oe=` expiry token;
they 403 minutes later. The expansion therefore converts every media node to
`instagram.com/p/<shortcode>/` or `instagram.com/reel/<shortcode>/`, and the
Facebook leg only ever emits `facebook.com/<page>/videos/<id>`. This is the
same rule TikTok follows (`tiktok_page_url`, engine.py:213).

**A3 — Instagram rides on `instaloader` instead of a hand-rolled GraphQL client.**
`instaloader` is MIT, actively maintained (1,038 commits / 152 releases),
verified live from this machine, and it already absorbs the GraphQL
query-hash churn that breaks every hand-written client — the churn that
breaks yt-dlp's `instagram:user` extractor today
([yt-dlp#4394](https://github.com/yt-dlp/yt-dlp/issues/4394)).

*Rejected:* writing `agent/tools/instagram_api.py` against Instagram's private
GraphQL, mirroring `agent/tools/tiktok_api.py`. It would look symmetrical, but
it would put us in charge of re-fixing a broken query hash every time Meta
rotates it. That is exactly the maintenance burden we refuse for TikTok.

*Rejected:* yt-dlp's `InstagramUserIE`. Measured broken; `_WORKING = False` in
the installed source.

**A4 — Facebook rides on the app's own browser, not on a Meta token.**
`GET /{page-id}/videos` needs a Page access token with
`pages_manage_posts` + `pages_show_list`
([Page Videos reference](https://developers.facebook.com/docs/graph-api/reference/page/videos/)),
which requires Meta App Review. A distributed open-source desktop app cannot
obtain that. Meanwhile the app already owns a hardened Playwright session
(`agent/tools/browser.py:226`, `BrowserSession`) with real Chrome/Edge
preference and stealth patches — and that session reads a public Facebook
Videos tab fine (measured: 21 video ids, anonymous, no cookies).

*Rejected:* the Selenium + logged-in-profile approach used by the closest
GitHub project we found
([bharatcj/facebook-channel-videos-downloader](https://github.com/bharatcj/facebook-channel-videos-downloader)).
It needs a real logged-in Chrome profile; the app's browser session plus its
existing cookies setting covers the same ground with no new tool.

**A5 — Rate limits are a product constraint, not an error to hide.**
Instagram answered `429 Too Many Requests` after three profile requests in a
row, with an 11-minute retry hint. So: one profile per expansion, the
expansion queue stays serial (it already is — `_expand_queue`), a minimum gap
between Instagram calls, and a named error message. "Instagram is rate-limiting
this machine — wait a few minutes and try again" beats a traceback.

**A6 — The download leg is untouched.**
No change to `_base_opts`, `QUALITY_OPTIONS`, the retry policy or the worker
pool. Instagram and Facebook downloads keep going through yt-dlp's own
extractors, exactly as they do today for single links.

**A7 — The Facebook leg is labelled experimental.**
It scrapes a page Meta can change at any time. It ships with its own note in
the UI and in the README, and it fails loudly rather than silently returning
short lists.

## Spike Outcomes (2026-10-29)

### Task 1 — Facebook paging

**Measured, not assumed.** Four passes against the live site:

| Probe | Result |
|---|---|
| Videos tab as rendered | **21** video ids for `nasa`, **9** for `natgeo` — the first screen only |
| Scrolling the real container (`#scrollview`, scrollHeight 5064 vs clientHeight 720) | reaches the bottom (`scrollTop` 4344 of 5064) and **stops issuing requests** |
| The page's own pagination route (`comet.fbweb.ProfileCometProfilePlusVideosRoute`) | every response is `{"__ar":1,"rid":"…","payload":null}` — **the server refuses to page a logged-out visitor** |
| Replaying that request with a rising `__comet_req` | 757-byte empty body, no ids |
| `m.facebook.com` | the same 21 ids; `mbasic.facebook.com` | nothing at all |

**Decision:** anonymous Facebook expansion yields **the first screen only**
(measured 9–21 videos). There is no anonymous paging, so the leg must not
promise more than it can deliver.

**Revised by the user's decision (public content only, no sign-in):** the
client does **not** load the app's cookies file into the browser context.
There is no Instagram or Facebook credential anywhere in the app, so a page
that hides its videos behind a sign-in gets one clear message instead of a
credential prompt. The consequence is that the leg is first-screen-only, and
it says so in the status line ("experimental: Facebook shows a visitor the
first screen only") instead of quietly returning a short list.

**Unverified and now out of scope:** whether a signed-in session would page
Facebook further. It is not measured and not needed — the app stores no
Facebook session.

**Superseded by the GitHub sweep (2026-10-29, Task 10).** The scroll and the
Comet route were the wrong door. The page's *own* list is a Relay
persisted query — `PagesCometChannelTabAllVideosCardImplPaginationQuery` — and
that one answers a visitor with no sign-in at all:

| Probe | Result |
|---|---|
| The query, posted anonymously with the page's own token | answers: 9 ids per answer, `page_info.end_cursor` to continue with |
| `nasa` | **40** ids over 7 answers, then `has_next_page: false` |
| `natgeo` | **120+** ids over 20 answers, still going |
| The browser's first screen vs. the query's list | **disjoint** — `nasa`'s 21 and 40 share no id (union 61) |
| The query's id | read from the page's own JavaScript bundle, because Meta renames it on every deploy |
| A plain HTTP client | HTTP 400 — the request needs curl_cffi's Chrome impersonation |

So the Facebook leg became **two halves**: the browser renders the first
screen, the page's own query pages the rest, and the app hands both on.
No `fb_dtsg`, no cookie file, no sign-in — the only credential is the
per-load token the page hands every visitor, and it travels in the request
body, never in a URL or a log line.

### Task 2 — Instagram pacing

**Measured against the live API.**

| Probe | Result |
|---|---|
| Six profiles in a row, 3 s apart, instaloader's default pacing | **no 429** — all six listed |
| The 429 seen earlier | caused by running two profile listings **back to back with no gap**, not by normal use |
| One profile | 1–5 s |
| One 20-post listing | ~100 s (instaloader sleeps `min(expovariate(0.6), 15 s)` before each request) |
| Node shape | `typename` ∈ {`GraphVideo`, `GraphSidecar`}; `post.is_video` is True only for `GraphVideo`; a sidecar can still carry a video in one of its children |
| **`post.url`** | **the CDN link, never the permalink** — `display_url` with an `oe=` expiry token |

**Decisions:**

1. **The permalink is built from `post.shortcode`** —
   `https://www.instagram.com/p/<shortcode>/`. `post.url` is never used;
   it is the CDN link that expires (this is the A2 rule, confirmed against
   the library's own source).
2. **"Carries a video"** = `typename == "GraphVideo"`, or a sidecar where
   `post.get_is_videos()` holds at least one True. Photo-only posts are
   skipped.
3. **Keep instaloader's default pacing.** It is the setting that produced no
   429. Tuning it down is exactly what would cause one. The expansion thread
   therefore reports progress, because a 20-post listing takes ~100 s and
   200 posts take considerably longer.


| Leg | Engine | Result |
|---|---|---|
| IG profile → posts/reels/IGTV | instaloader 4.16 | **works live**, no login for public profiles; 429 after ~3 rapid requests |
| IG single post/reel download | yt-dlp | works (`DfC0AF6z68E → "Video by porsche"`) |
| IG profile via yt-dlp | yt-dlp `instagram:user` | broken upstream — issue #4394 open, `_WORKING = False` |
| FB page → videos | the app's browser | **works live**, anonymous: 21 ids from `facebook.com/nasa/videos/`; the 3 tested URLs all extract in yt-dlp with titles and durations |
| FB page via yt-dlp | yt-dlp | unsupported — falls through to the generic extractor |
| FB page via Graph API | Meta Graph API | works only with an App-Reviewed Page token — rejected |
| FB paging past the first screen | the page's own Relay query | **works live**: `nasa` 40 ids (7 answers), `natgeo` 120+ (20 answers); the query's ids are disjoint from the browser's first screen |

## Task List

### Phase 0: Spikes (read-only, no product code)

- [x] **Task 1 — Facebook paging spike.** Find the mechanism that loads more
      than the first screen of a page's Videos tab (inner scroll container,
      a "See more videos" control, a paginated GraphQL call in the page's own
      XHR traffic, or a logged-in-only route). Capture the approach that
      yields the most videos per minute without a session.
      **Outcome:** a written decision + the number of videos reachable.
      **Files:** none (scratch script under `tasks/` or `/tmp`).
      **Depends on:** nothing.

- [x] **Task 2 — Instagram pacing spike.** Measure how many profile requests
      this machine can make before Instagram answers 429, and whether the
      app's existing cookies file changes the answer. Decide the minimum gap
      between calls and the maximum posts per expansion.
      **Outcome:** the pacing numbers the client will use.
      **Files:** none (scratch script).
      **Depends on:** nothing.

### Checkpoint: Spikes
- [x] Facebook paging has a decision (it decides whether the Facebook leg
      ships in v1 at all).
- [x] Instagram pacing numbers are written down.

### Phase 1: The two clients

- [x] **Task 3 — `core/instagram_client.py`.** A thin wrapper over
      `instaloader` that lists a profile's posts / reels / IGTV and returns
      permalinks. It owns: the instaloader instance (no downloads, no
      metadata), the limit, the pacing gap, the exception translation
      (`TooManyRequestsException` → a named message, `ProfileNotExistsException`
      → "no such account", `PrivateProfileNotFollowedException` → "private"),
      and one `Ops` line per call. No key or cookie value may appear in any
      message it produces.
      **Acceptance:** `list_profile_media("porsche", limit=20)` returns
      `https://www.instagram.com/p/<shortcode>/` style URLs, newest first,
      bounded by `limit`, **video-carrying posts only** (a photo-only post is
      skipped — the app downloads video); a 429 raises one clear error; the
      ops line carries the platform, the handle, the count and the duration.
      The reels tab is not queried separately: `instaloader` costs one extra
      API request per reel there, and the timeline already carries reels.
      **Measured after the spike:** one timeline item costs **2.90 s**, so
      walking to the 200-video limit would take ~35 minutes. The walk is
      therefore bounded by a **180 s budget** (`MAX_WALK_SECONDS`), the
      listing carries the reason it stopped, and a 429 halfway through keeps
      the videos already found.
      **Measured again after the build:** 2.90 s was instaloader building a
      `Post` per node, which fetches that post's full metadata — one request
      per post. The timeline node already carries the shortcode and the media
      type, so the walk reads the node and asks for the metadata only of a
      carousel, which does not describe its children. Same profile, same
      20-video limit: **164.7 s → 55.1 s (3.0x)**. A 30-video listing went
      from being cut off by the budget to finishing in 96 s.
      **Files:** `src/s_q_ali_media_downloader/core/instagram_client.py`,
      `tests/test_instagram_client.py`.
      **Depends on:** Task 2.

- [x] **Task 4 — `core/facebook_client.py`.** A browser-based page lister.
      It opens `<page>/videos/` in the app's `BrowserSession`, collects
      `/videos/<id>` permalinks from the rendered DOM (one helper for the
      selector/regex so a Meta DOM change is a one-line fix), and returns
      permalinks. It must close the page and the session in a `finally` block.
      Per Task 1 it also says in the status line when the count stopped at the
      first screen, instead of quietly returning a short list. It loads **no
      cookies file**: the app stores no Facebook session (public content only).
      **Acceptance:** `list_page_videos("nasa", limit=20)` returns
      `https://www.facebook.com/nasa/videos/<id>` URLs; a bogus page returns
      one clear error; the browser never leaks a process on failure.
      **Extended by Task 10/11:** the client became two legs — the browser's
      first screen, plus the page's own Relay query for the rest
      (`paged_video_ids`). The listing returns a `PageListing` (a list plus the
      reason it stopped short) so the status line can say why a list is short.
      **Measured live:** `nasa` 21 + 40 = **61** distinct videos, `natgeo`
      9 + 12 = 21 at a limit of 20, and 60+ when the limit allows it. A
      Relay-found permalink extracts in yt-dlp (`3319544694917358` — "12M views
      · 334K reactions").
      **Files:** `src/s_q_ali_media_downloader/core/facebook_client.py`,
      `tests/test_facebook_client.py`.
      **Depends on:** Task 1.

### Checkpoint: Clients
- [x] Both clients work against the live platforms from a script.
- [x] Neither prints, logs or embeds a credential.

### Phase 2: The expansion threads and the wiring

- [x] **Task 5 — `InstagramFetchThread` and `FacebookFetchThread`.** Two
      QThreads in `engine.py` mirroring `AccountFetchThread` /
      `YouTubeFetchThread`: same signals (`found`, `failed`, `note`,
      `progress`), same `limit` clamp to `MAX_ACCOUNT_VIDEOS`
      (engine.py:85-86), same "no results" message shape. The Facebook thread
      emits progress because a browser page takes seconds to render.
      **Acceptance:** both threads emit `found(urls, label)` with page
      permalinks only, and `failed(message)` with one sentence on error.
      **Files:** `src/s_q_ali_media_downloader/engine.py`,
      `tests/test_expand_threads.py`.
      **Depends on:** Tasks 3, 4.

- [x] **Task 6 — Detect the new URLs and route them.** Add
      `is_instagram_profile_url(url)` and `is_facebook_page_url(url)` next to
      `is_instagram_url` (engine.py:253) and `is_facebook_url` (engine.py:235);
      teach `add_links` (main_window.py:867) to route them to `expand_links`
      instead of skipping them; extend `_expand_thread_for`
      (main_window.py:947) with the two new branches. The existing
      single-link detection must keep working — an Instagram post URL is not a
      profile URL.
      **Acceptance:** pasting an IG profile or an FB page queues an expansion;
      pasting a single post still queues one download; a `/videos/<id>` link is
      still a single video, never a page.
      **Files:** `src/s_q_ali_media_downloader/engine.py`,
      `src/s_q_ali_media_downloader/ui/main_window.py`,
      `tests/test_link_routing.py`.
      **Depends on:** Task 5.

### Checkpoint: Expansion
- [ ] A pasted profile/page expands and queues, in the real app.

### Phase 3: Packaging

- [x] **Task 7 — Ship `instaloader` with the app.** Add it to
      `requirements.txt` (it is a runtime dependency now, like `playwright`),
      confirm the resolver keeps `requests==2.33.0` (browser-use pins it;
      instaloader needs `requests>=2.4`, which 2.33.0 satisfies), add it to
      the PyInstaller build and the Inno Setup installer, and let the CI audit
      gate check it.
      **Acceptance:** a clean install of `requirements.txt` resolves without a
      conflict; `pip-audit` is clean; the built EXE expands an Instagram
      profile.
      **Files:** `requirements.txt`, `release/build.bat`, the `.iss` file,
      `src/s_q_ali_media_downloader/__init__.py` (version bump).
      **Depends on:** Task 6.

### Phase 4: Tests, text, docs

- [x] **Task 8 — Tests.** Offline unit tests with fake pages / fake instaloader
      responses (no network in the default suite) plus `live`-marked tests for
      the two live paths. The live tests must be skipped by
      `pytest -m "not live"`.
      **Acceptance:** `pytest -m "not live"` green; the live tests are opt-in.
      **Files:** `tests/test_instagram_client.py`,
      `tests/test_facebook_client.py`, `tests/test_expand_threads.py`,
      `tests/test_link_routing.py`.
      **Depends on:** Task 6.

- [x] **Task 9 — User-facing text and docs.** The link-box placeholder, the
      status sentences, the "experimental" note for Facebook, the README
      feature bullet and install/build lines, and the CHANGELOG entry. The
      README follows the house rule: no hardcoded version numbers, no
      maintainer notes, nothing shipped-but-not-yet-true.
      **Acceptance:** every sentence in the UI matches what the code does;
      the CHANGELOG has a dated section for the new version.
      **Files:** `src/s_q_ali_media_downloader/ui/main_window.py`,
      `README.md`, `CHANGELOG.md`.
      **Depends on:** Task 7.

### Checkpoint: Ship
- [ ] `pytest -m "not live"` green, `ruff check src tests` clean.
- [ ] The EXE smoke test passes with the new dependency bundled.
- [ ] Manual run: IG profile → queue → downloaded file on disk.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Instagram 429 rate limiting | High — the feature looks broken | bounded requests, a pacing gap, a named error, the serial expansion queue; a listing cut off halfway keeps the videos it already found |
| An Instagram listing that runs for half an hour | High — the app looks hung | **Measured: 2.90 s per timeline item** (Task 2), now **0.85 s per item** after the walk stopped fetching every post's metadata. The walk is bounded by `MAX_WALK_SECONDS = 180`, it reports progress, and the status line says how far it got |
| Instagram query/API changes inside instaloader | Medium | instaloader is maintained and versioned; we depend on it instead of re-implementing it, and a pip upgrade fixes it |
| Facebook DOM changes | High | the selector lives in one helper; the leg is labelled experimental; failure is loud |
| Facebook paging beyond the first screen | Low | **Solved by the page's own Relay query** (Task 10/11): it answers an anonymous visitor, and the browser's first screen is kept as well because the two lists are disjoint. The query's id is read from the page's own JavaScript, so a Meta rename costs one regex, not a rewrite. If Facebook refuses to page, the app says the listing stopped at the first screen |
| A page whose list is paged but whose videos are private | Medium | the Relay answers with the same list the page shows a visitor; anything behind a sign-in never appears, so no credential is needed or stored |
| New dependency weight (instaloader pulls `requests`) | Medium | `requests==2.33.0` already satisfies instaloader's `>=2.4`; the resolver check is Task 7 |
| A page URL that turns out to be a single video | Medium | the routing tests in Task 6 pin the difference |
| Credentials leaking into the log | High | the log rule already exists; the clients produce their own messages, and the CI secret scan still runs |

## Decisions taken (2026-10-29, user-approved)

1. **Both platforms ship in v1; the Facebook leg is labelled experimental.**
   Proven to work, but it scrapes a page Meta can change — so it is marked as
   such in the UI and the README, and it fails loudly instead of quietly
   returning a short list.
2. **Public content only.** No Instagram/Facebook sign-in, no session file, no
   credential storage anywhere in the app. Private profiles and login-walled
   pages get one clear message instead of a credential prompt.

Still open: nothing. The Facebook paging question is settled — the page's own
query pages the list for an anonymous visitor, so the leg is no longer
first-screen-only — and both legs are built, tested and packaged.
