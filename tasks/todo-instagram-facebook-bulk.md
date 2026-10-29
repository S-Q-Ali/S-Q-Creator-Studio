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
- [x] Manual run: Instagram profile → queue → a video file on disk.
      **Done:** the expansion listed `nasa`, the queue took the first
      permalink and the download thread wrote an 8 MB mp4 (the Artemis II
      post). The Facebook leg listed 21 videos for `nasa` in the real
      window, with the first-screen caveat in the status line.
