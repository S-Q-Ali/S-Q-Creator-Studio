# Tasks: Instagram & Facebook Bulk Expansion

Plan: `tasks/plan-instagram-facebook-bulk.md`
Spec: `tasks/spec-instagram-facebook-bulk.md`

## Phase 0: Spikes

- [x] Task 1: Facebook paging spike — find what loads more than the first
      screen of a page's Videos tab (inner scroll container, a "See more
      videos" control, the page's own paginated XHR, or a session-only route).
      **Outcome:** the Videos tab renders the first screen only — **21** ids
      for `nasa`, **9** for `natgeo`. Scrolling `#scrollview` bottoms out and
      stops; every Comet pagination response comes back `"payload": null`, so
      **Facebook refuses to page a logged-out visitor**; replaying the
      request returns an empty body; `m.facebook.com` shows the same set.
      **Decision:** anonymous expansion = first screen. The client loads **no**
      cookies file — the app stores no Facebook session (public content only)
      — and says in the status line that it stopped at the first screen.
- [x] Task 2: Instagram pacing spike — how many profile requests before
      Instagram answers 429, and whether the app's cookies file changes that.
      **Outcome:** six profiles in a row (3 s apart, instaloader's default
      pacing) → **no 429**. The earlier 429 came from two listings back to
      back with no gap. One profile ≈ 1–5 s; a 20-post listing ≈ 100 s
      (instaloader sleeps before each request). **`post.url` is the CDN link,
      not the permalink** — the permalink comes from `post.shortcode`. Video
      posts are `GraphVideo`; a sidecar can carry a video in a child.
      **Decision:** keep instaloader's default pacing, report progress while
      listing, and never use `post.url`.

## Checkpoint: Spikes
- [x] The Facebook leg has a go/no-go decision.
- [x] The Instagram pacing numbers are written down.

## Phase 1: The clients

- [x] Task 3: `core/instagram_client.py` — instaloader wrapper returning
      permalinks, with pacing, the exception translation and one ops line.
      **Verify:** a live script lists a public profile; a 429 gives one
      sentence; the ops line carries no credential.
      **Done:** 22 offline tests; verified live — 3 permalinks from `nasa`.
      **Measured afterwards:** the walk costs **2.90 s per timeline item**, so
      the 200-video limit would have run for ~35 minutes. The walk is now
      bounded at **180 s** and says how far it got; a listing that Instagram
      cuts off with a 429 keeps the videos it already found.
- [x] Task 4: `core/facebook_client.py` — browser page lister using the app's
      own `BrowserSession`, one helper for the DOM selector.
      **Verify:** a live script lists a public page; a bogus page gives one
      sentence; no browser process is left behind.
      **Done:** 14 offline tests; verified live — 21 videos from `nasa`.
      **Extended in Task 12:** the client is now two legs — the browser's
      first screen and the page's own query for the rest — and returns a
      `PageListing` (the URLs plus the reason it stopped short).

## Checkpoint: Clients
- [x] Both clients work live from a script.
- [x] No credential reaches a message, a log line or an exception.

## Phase 2: The expansion

- [x] Task 5: `InstagramFetchThread` and `FacebookFetchThread` in
      `engine.py`, mirroring the existing TikTok and YouTube threads.
      **Verify:** `found(urls, label)` carries page permalinks only.
- [x] Task 6: `is_instagram_profile_url` / `is_facebook_page_url`, the
      `add_links` routing and the `_expand_thread_for` branches. The account
      field takes the same three kinds of profile.
      **Verify:** a profile expands; a single post still queues one download.

## Checkpoint: Expansion
- [x] A pasted profile/page expands and queues in the real app.

## Phase 3: Packaging

- [x] Task 7: `instaloader` into `requirements.txt`, the PyInstaller build and
      the installer; the resolver keeps `requests==2.33.0`; the version bump.
      **Verify:** a clean install resolves, `pip-audit` is clean, the built EXE
      expands an Instagram profile.
      **Done:** `requests==2.33.0` already satisfies instaloader's `>=2.25`;
      `pip-audit -r requirements.txt` reports no known vulnerabilities; the
      version is 2.9.0. The Inno Setup script copies the whole `_internal`
      folder, so it needs no per-package line — only the PyInstaller build
      needed `--collect-all instaloader`.

## Phase 4: Tests and text

- [x] Task 8: offline unit tests for both clients, the threads and the
      routing; live tests marked `live`.
      **Verify:** `pytest -m "not live"` green.
      **Done:** 65 new tests — 19 IG client, 14 FB client, 24 threads and
      detectors, 7 routing, 2 live.
- [x] Task 9: the link-box placeholder, the status sentences, the Facebook
      "experimental" note, the README and the CHANGELOG.
      **Verify:** every UI sentence matches the code; the README carries no
      stale version or maintainer note.

## Checkpoint: Ship
- [x] `pytest -m "not live"` green and `ruff check src tests` clean.
- [x] The EXE smoke test passes with the new dependency bundled.
      **Done:** PyInstaller 6.22.0 built **2.9.0** — the portable EXE and
      `release\S-Q-Creator-Studio-Setup-2.9.0.exe`. `_internal` carries
      `instaloader` and `instaloader-4.16.dist-info`, the bundled package
      imports and lists a live profile, and the built app starts and stays
      up.
      **Rebuilt after Task 12** (Task 13): the first build predated the
      Instagram speedup and the Facebook paging.
- [x] Manual run: Instagram profile → queue → a video file on disk.
      **Done:** the expansion listed `nasa`, the queue took the first
      permalink and the download thread wrote an 8 MB mp4 (the Artemis II
      post). The Facebook leg listed 21 videos for `nasa` in the real
      window, with the first-screen caveat in the status line — **now 61**,
      with the caveat replaced by "Facebook's own list, paged as far as it
      goes" (Task 12).

## Phase 5: The GitHub scraper sweep

The user asked whether the GitHub scrapers solve what the expansion does
not. They do not — but reading them pointed at the real problem.

- [x] Task 10: survey the GitHub scrapers for Facebook and Instagram.
      **Done:** `shaikhsajid1111/social-media-profile-scraper` reads a
      profile's *about* data, not its videos; `lucasgrow/ads-library-scraper`
      reads Meta **Ad Library** ads, which are ads and not organic page
      posts; `omkarcloud/facebook-scraper` and the `facebook-scraper` package
      need a session or the Graph API. None of them lists a page's organic
      videos for a logged-out visitor.
      **What the sweep did find:** the shape of the way to do it. The
      scrapers that work anonymously all end at the same door — Facebook's
      **Relay** persisted-query route, `POST /api/graphql/` with a `doc_id`
      read from the page's own JavaScript. Our own spike had only tried the
      Comet route, which is a different one and is closed to a visitor.
- [x] Task 11: read the installed instaloader and find where the walk's time
      went.
      **Done:** `structures.py` — `Post.from_shortcode` fetches the post's
      full metadata, one request per post. That was the 2.90 s per timeline
      item. The timeline node already carries the shortcode and the media
      type, so the walk now reads the node and asks for the metadata only of
      a carousel, which does not describe its children.
      **Measured:** same profile, same 20-video limit — **164.7 s → 55.1 s
      (3.0x)**. A 30-video listing finishes in 96 s instead of being cut off
      by the 180 s budget.
- [x] Task 12: the Facebook leg pages the list behind the first screen.
      **Done:** `paged_video_ids()` in `core/facebook_client.py` — it reads
      the page's own token, the page id and the first cursor out of the
      rendered HTML, finds the query's `doc_id` in the page's own JavaScript
      bundle, and follows `page_info.end_cursor` until the list ends. The
      browser's first screen is kept as well: the two lists are disjoint
      (`nasa`'s 21 and 40 share no id).
      **Measured live:** `nasa` **61** distinct videos, `natgeo` 60+ at a
      limit of 60 (13 s), `nasa` 40 through the query alone (10.8 s). A
      Relay-found permalink extracts in yt-dlp (`3319544694917358` — "12M
      views · 334K reactions").
      **No credential:** no `fb_dtsg`, no cookie file, no sign-in. The only
      token is the per-load one the page hands every visitor, and it travels
      in the request body — never in a URL, a log line or an error message.
      **Verify:** 31 offline tests (the paging loop, the query-id harvest,
      the token's absence from every ops line, the fallback to the first
      screen); `pytest -m "not live"` green; `ruff check src tests` clean.
- [x] Task 13: rebuild the release so the shipped app carries the two new
      changes.
      **Why:** the first 2.9.0 build finished at 08:06, before the Instagram
      speedup (11:11) and the Facebook paging (11:11) landed. The EXE the
      user had on disk did neither.
      **Done:** `release\build.bat` rebuilt 2.9.0 in place — the portable EXE
      (17:05) and `release\S-Q-Creator-Studio-Setup-2.9.0.exe` (17:20,
      331 MB). Inno Setup's compile took 803 s. No version bump: 2.9.0 is
      still untagged and the CHANGELOG already describes the paging.
      **Verified in the shipped artifact, not just in the source:**
      the PYZ archive inside the EXE carries `facebook_client` (the Relay
      query name and `PagingUnavailable`), `instagram_client` (`_raw_timeline`,
      `GraphSidecar`) and `engine` (the new Facebook label); the bundled
      `curl_cffi` answers Facebook's videos tab with HTTP 200 and the page's
      token; the bundled `instaloader` walks NASA's timeline; the built app
      starts, stays up, writes its settings and opens its storage, and
      leaves no browser behind.
      **Files:** `release/build.bat` (unchanged), `release\portable\`,
      `release\S-Q-Creator-Studio-Setup-2.9.0.exe` (build output, not
      tracked).
