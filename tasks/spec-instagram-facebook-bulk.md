# Spec: Instagram & Facebook Bulk Expansion

## Objective

Today the app can expand a **TikTok profile** and a **YouTube channel or
playlist** into a list of individual video URLs that land in the download
queue. Instagram and Facebook have no such path: an Instagram profile link or
a Facebook page link is rejected by the link box ("use single video, reel or
post links"), even though the app can already download a single Instagram post,
reel or Facebook video.

This spec adds the same expansion for those two platforms: paste an Instagram
profile or a Facebook page, get its posts / reels / videos queued, exactly
like TikTok and YouTube behave today.

**User stories**

1. As a creator-archivist, when I paste an Instagram profile link, I want its
   newest posts and reels queued for download, so I can archive a creator the
   same way I archive a TikTok profile.
2. As a creator-archivist, when I paste a Facebook page link, I want that
   page's videos queued, so I do not have to open the Videos tab and copy
   links by hand.
3. As a creator-archivist, when a platform rate-limits or blocks me, I want a
   plain message that says which platform did it and what to try, so I know
   whether to wait, sign in, or give up.

**Success criteria**

- `instagram.com/<handle>` expands to a list of individual post / reel / IGTV
  permalinks, bounded by the app's existing account limit, and those links
  land in the queue.
- `facebook.com/<page>` expands to a list of individual video permalinks and
  those links land in the queue.
- Every expanded link is a **page URL**, never a CDN URL. A CDN URL carries an
  expiry token and 403s minutes later.
- The download leg is unchanged: the queue still downloads with yt-dlp, the
  same quality presets, the same retry policy.
- A blocked or rate-limited platform produces one clear sentence, not a stack
  trace, and it names the platform.
- Nothing about an API key, a cookie value or an `Authorization` header ever
  reaches the operation log.

## Non-goals

- No bulk download that bypasses the queue, the retry policy or the worker
  pool. Expansion only *fills* the queue.
- No Instagram Stories, no saved posts, no followers, no hashtag feeds.
- No Facebook groups, events, watchparties or personal profiles — pages only.
- No private profiles and no logged-in sessions in v1. **Decided 2026-10-29:**
  public content only — the app stores no Instagram or Facebook credential.
- No new download engine. yt-dlp stays the downloader.

## Assumptions

These are the assumptions the plan is built on. Correct me before I code.

1. **"Bulk" means "expand a profile/page into the existing queue"** — the
   same meaning it has for TikTok and YouTube today — not "download 200 files
   in one go without the queue".
2. **Public content only in v1.** Instagram's public profiles and Facebook's
   public pages are readable without a session; private content needs one.
3. **The existing account-limit dropdown (20–200) governs both platforms** —
   no new limit control.
4. **Instagram contributes posts and reels that carry a video.** Photo-only
   posts are skipped — the app downloads video, and a still has nothing to
   save. Stories are excluded because they expire. The reels tab is not
   queried separately: `instaloader` spends one extra API request per reel
   there, and the profile timeline already carries reels as `GraphVideo`.
5. **Facebook contributes the page's videos**, not its photo posts. A photo
   post has no video file to download.
6. **The download leg is untouched.** Expansion only produces URLs; yt-dlp
   still downloads them with the current quality settings.

## Tech Stack

- Python 3.10+, PySide6 (desktop).
- **instaloader 4.16** (MIT) for Instagram enumeration — a new runtime
  dependency.
- **yt-dlp** (already a dependency) for the download leg, unchanged.
- **Playwright + the app's own hardened browser session**
  (`agent/tools/browser.py`) for Facebook page enumeration — no new dependency.
- `agent/opslog.py` for one operation line per expansion.

## Verified facts (measured, not assumed — 2026-10-29)

Everything below was run against the live platforms from this machine.

| Question | Measured answer | How |
|---|---|---|
| Does yt-dlp list an Instagram profile? | **No.** `ERROR: [instagram:user] porsche: Unable to extract data` | `yt-dlp --flat-playlist https://www.instagram.com/porsche/` with yt-dlp 2026.08.19 |
| Is that a known upstream break? | **Yes** — `InstagramUserIE._WORKING = False` in the installed source; issue [yt-dlp#4394](https://github.com/yt-dlp/yt-dlp/issues/4394) is open, and a rework PR ([#17081](https://github.com/yt-dlp/yt-dlp/pull/17081)) is still open | source + GitHub API |
| Does yt-dlp list a Facebook page's videos? | **No.** Falls through to the generic extractor: `ERROR: Unsupported URL` | `yt-dlp --flat-playlist https://www.facebook.com/sqaddledots/videos/` |
| Can the Meta Graph API list a page's videos? | **Yes, but not shippable.** `GET /{page-id}/videos` needs a **Page access token** with `pages_manage_posts` + `pages_show_list`, which requires Meta App Review | [Page Videos reference](https://developers.facebook.com/docs/graph-api/reference/page/videos/) |
| Does instaloader list an Instagram profile? | **Yes, live, no login.** `porsche` → posts with shortcodes and CDN URLs; `instagram` → profile resolved, full name, privacy flag | instaloader 4.16, `Profile.get_posts()` |
| How hard does Instagram rate-limit? | **Hard.** Three profile requests in a row produced `429 Too Many Requests` with an 11-minute retry hint | instaloader 429 on the second run |
| Does instaloader support reels and IGTV? | **Yes** — `Profile.get_posts()`, `Profile.get_reels()`, `Profile.get_igtv_posts()` | instaloader source |
| Is instaloader safe to depend on? | **Yes** — MIT licence, 1,038 commits, 152 releases | [instaloader/instaloader](https://github.com/instaloader/instaloader) |
| Can the app's browser list a Facebook page's videos? | **Yes, live, anonymous.** `facebook.com/nasa/videos/` in the app's own hardened Playwright session returned **21 video ids** from the rendered DOM | app `BrowserSession`, headless, no cookies |
| Do those Facebook URLs download? | **Yes.** yt-dlp extracted 3 of 3 with real titles and durations ("Artemis Acceleration", 59.9 s) | `extract_info(download=False)` on the collected URLs |
| Does scrolling load more Facebook videos? | **No — yet.** Six scroll passes kept the count at 21 | same run; paging is an open task |
| Does yt-dlp download a single Instagram post/reel? | **Yes.** `DfC0AF6z68E → "Video by porsche"` | `yt-dlp https://www.instagram.com/reel/DfC0AF6z68E/` |
| Does yt-dlp download a single Facebook video? | **Yes** — the `facebook` extractor matches `/videos/<id>`, `/reel/<id>`, `fb.watch` | installed extractor source |

## Boundaries

**Always**

- Enumerate, then queue — never download from inside the expansion.
- Emit page permalinks, never CDN URLs (CDN links carry expiry tokens).
- One `Ops` line per expansion: platform, target, count, duration, error.
- Keep every credential out of the log, the status line and any exception text.
- Pace Instagram requests; treat a 429 as a normal outcome, not a crash.

**Ask first**

- Adding `instaloader` to `requirements.txt` (a new runtime dependency) and
  anything it pulls in.
- Changing the PyInstaller build or the Inno Setup installer.
- Shipping a Facebook leg at all, given how brittle page scraping is.

**Never**

- Print, log or embed an API key, a cookie value or an `Authorization` header.
- Store an Instagram/Facebook password anywhere in the app.
- Bypass the queue, the retry policy or the worker pool.

## Success criteria (testable)

- [ ] `instagram.com/<handle>` in the link box queues N posts/reels, and each
      queued link is `instagram.com/p/...` or `instagram.com/reel/...`.
- [ ] `facebook.com/<page>` in the link box queues N video links, each
      `facebook.com/<page>/videos/<id>`.
- [ ] Both honour the account-limit dropdown.
- [ ] An Instagram 429 shows one sentence naming Instagram and suggesting a
      wait; the app stays responsive.
- [ ] A Facebook page that does not exist shows one sentence, no traceback.
- [ ] The operation log shows one line per expansion and contains no cookie
      values or key material.
- [ ] `pytest -m "not live"` and `ruff check src tests` stay green.
- [ ] The built EXE still passes the smoke test with `instaloader` bundled.

## Decisions (2026-10-29)

1. **Both platforms ship in v1; the Facebook leg is labelled experimental.**
   It is proven to work, but it scrapes a page Meta can change, so it is
   marked as such in the UI and the README and it fails loudly.
2. **Public content only.** No sign-in, no session file, no stored
   credential. A private profile or a login-walled page gets a clear message.
3. **How far the Facebook leg pages** is decided by the paging spike
   (Task 1 of the plan), not here.

## Remaining unknown

Whether a Facebook page's Videos tab can be paged past the first screen
without a session. 21 videos were measured from one tab; the paging mechanism
has to be found first.
