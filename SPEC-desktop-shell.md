# Capability Map: Desktop Shell (responsive, de-congested, research-free)

**Status:** approved — the three shape decisions were made by the human
(delete the research code from the repo, a third Settings workspace tab, and
density that is automatic with a manual override).

**Problem.** Three things are wrong with the desktop app today.

1. **It only works on a big screen.** At 1366×768 the AI Finder clips its own
   controls ("50 chann", "Facebook Pag", "Only Creators") and the cookies row
   disappears below the panel. At 1280×720 the clipping is worse. Nothing in
   the app adapts to the window.
2. **The Niche Research module does not belong here.** It was ported from a
   web tool: it brings its own design system, its own navigation, its own
   brand lockup, and it sits in the desktop app as a third workspace next to
   two download workspaces. The human wants it in the web tool, not here.
3. **The left rail carries twelve controls** (folder, four combos, a cookie
   switch, an identity line, a source switch, an input, two buttons and a
   hint) and takes 25% of the width on a small screen.

**The constraint that shapes everything:** the Groq API key, the YouTube API
key and the cookies file live in the research module's SQLite database, and
the Social Discovery feature reads the Groq key from it. The research code
cannot simply be deleted — three of its modules are the core of the feature
that was shipped in 2.5.0.

## Module map

| Module id | Responsibility | Depends on |
|---|---|---|
| `core-extract` | Move the three shared modules out of the research package into `core/`: the secret store (DPAPI), the YouTube client, the exporter | — |
| `research-remove` | Delete the research-only code and its tests, unmount the third workspace, delete the second design system | `core-extract` |
| `settings-panel` | A third workspace tab that owns every setting: Groq key, YouTube key, cookies file, download folder, quality, pace, workers, passes, Chrome cookies, density override | `core-extract` |
| `density` | One spacing and type scale with a compact variant, applied everywhere; the rail slimmed to the input and one action; the options panel collapsible; the chrome rows merged | `research-remove`, `settings-panel` |
| `ui-fixes` | The visible defects: the invisible active tab, the contrast failures, the missing empty states, and the rule that no text may be clipped at any supported size | `density` |

Build order: `core-extract` → `research-remove` → `settings-panel` →
`density` → `ui-fixes`.

## What is reused, not rebuilt

| Existing piece | Used for |
|---|---|
| `niche_research/storage/db.py` | The settings table, the DPAPI sealing and `db_path()` — the stored Groq key must keep working, so the **database file path does not change** |
| `niche_research/tools/youtube_client.py` | Channel and video resolution for Social Discovery and the AI Finder |
| `niche_research/tools/exporter.py` | The Social Discovery CSV and JSON export |
| `theme.py` | The palette and the global stylesheet — one design system survives |
| `QSettings` in `main_window.py` | The download preferences — unchanged, they are not secrets |

---

# Spec: `core-extract`

## Objective

Move the three shared modules into `s_q_ali_media_downloader/core/` and point
every user at them, so that the research package can be deleted without
breaking Social Discovery.

Acceptance criteria:

- `core/settings_store.py` exposes `get_setting`, `set_setting`,
  `secret_is_unreadable`, `db_path`, `configure`, `close_store` and keeps the
  **same database file** as before, so a key stored today still reads back.
- The DPAPI sealing is unchanged: a secret is sealed at rest and fails closed
  when the machine cannot unseal it.
- `core/youtube_client.py` exposes the same public names as before
  (`fetch_channel`, `fetch_channels`, `fetch_video`, `fetch_videos`,
  `search_videos`, `search_channels`, `parse_video_id`, `parse_channel_id`,
  `is_youtube_url`, `VideoInfo`, `ChannelInfo`, `get_api_key`,
  `get_cookies_file`).
- `core/exporter.py` exposes the same public names as before.
- `agent/tools/social_judge.py`, `agent/tools/social_resolve.py`,
  `agent/tools/youtube_search.py` and `ui/social_discovery_page.py` import
  from `core`, not from `niche_research`.
- The research tables (keywords, channels, snapshots, rankings, trending,
  discovery log, scripts, blueprints) are **not** carried over; only the
  `settings` table is.

## Testing strategy

`tests/test_niche_db.py`, `tests/test_niche_youtube_client.py` and
`tests/test_niche_exporter.py` are renamed to `tests/test_core_*.py` and keep
asserting the same behaviour. A new test asserts that the store still reads
a value written by the previous module (same file, same table, same key).

---

# Spec: `research-remove`

## Objective

Remove the research feature from the desktop app and from the repository.

Acceptance criteria:

- `src/s_q_ali_media_downloader/niche_research/` does not exist.
- The research test files are deleted; the three renamed `test_core_*` files
  survive.
- The workspace stack has exactly three pages: Download Queue, AI Finder,
  Settings.
- No file in `src/` imports `niche_research`.
- The research database file is left on disk (the user's stored keys live
  there) but the research rows are ignored.

---

# Spec: `settings-panel`

## Objective

One place where every setting of the app is edited, in the app's own design
language.

Layout — a single column of grouped cards, one card per concern:

```
┌─ SETTINGS ──────────────────────────────────────────────┐
│ AI KEYS                                                │
│   Groq API key       [••••••••]        (Social Discovery)│
│   YouTube API key    [••••••••]        (optional)        │
│   Cookies file       [D:\...\cookies.txt]  [Browse][Clear]│
│                                                          │
│ DOWNLOADS                                               │
│   Save to            [E:\Videos\...]      [Browse][Open]  │
│   Quality            [Best available ▾]                   │
│   Pace               [Normal · 4-9s ▾]                    │
│   Workers            [2 · parallel ▾]                     │
│   End passes         [2 passes ▾]                        │
│   ☐ Sign in with Chrome cookies                          │
│   Browser identity · chrome-146:macos-26                  │
│                                                          │
│ LAYOUT                                                  │
│   ☐ Compact layout  (auto: on because the window is small)│
└──────────────────────────────────────────────────────────┘
```

Acceptance criteria:

- The Groq key is saved to the same store and read by
  `agent/tools/social_judge.py` — the key stored today works without being
  entered again.
- The YouTube key is read by `core/youtube_client.get_api_key()`.
- The download preferences keep their existing `QSettings` keys, so an
  existing user's settings are not reset.
- Secrets are shown masked and never logged.
- The panel is a workspace page, not a modal.

---

# Spec: `density`

## Objective

One spacing and type scale that has a compact variant, so the app is usable
on a 1280×720 laptop without clipping a single control.

## The token scale

```
space-1  4px     space-4  16px
space-2  8px     space-5  20px
space-3  12px    space-6  24px

type-body   13px → 12px      control-height  34px → 30px
type-title  19px → 17px      rail-width      280px → 248px
type-caption 10px → 9px      page-margin     24px → 16px
```

Comfortable is the default. Compact is applied when the window is narrower
than 1500px or shorter than 850px, and the human can force either state from
Settings. The choice is remembered.

## Layout rules

- The left rail carries **the input and one action** only. The folder, the
  four combos, the cookie switch and the identity line move to Settings.
- The AI Finder's options live behind a collapsed **Options** disclosure.
  The default view is: mode, query, search, results.
- The notice bar, the status line and the footer become **one 28px bar**.
- The workspace switcher becomes three segmented segments.
- No row may hold more than four controls; anything longer wraps to a new
  line.

## Acceptance criteria

- At 1280×720, 1366×768, 1440×900 and 1680×1000: **no widget's text is
  clipped** (checked by comparing `sizeHint()` with `size()`), and no
  interactive control is shorter than 28px.
- The rail is 248px in compact and 280px in comfortable.
- Switching density re-lays out the whole app without a restart.

---

# Spec: `ui-fixes`

## Objective

The visible defects, fixed and locked by a test.

| Defect | Rule |
|---|---|
| The active workspace tab is invisible (dark text `#17100C` on `#100E14`, 1.02:1) | The checked tab must reach 4.5:1 against its own background |
| The AI Finder's option row is clipped | The options disclosure wraps, never clips |
| The two result tables have no empty state | Each shows an icon, one line and the action that fills it |
| `#5A5370` on `#1A1722` is 2.44:1 | Secondary text must reach 4.5:1 |
| The primary button hovers to a coral `#FF8354` | The hover stays in the cyan family |
| The GitHub and LinkedIn buttons sit in the footer | They move into the rail, as two small buttons |

## Testing strategy

- A rendering test asserts, at each of the four sizes, that no visible label
  is clipped and that the active tab's contrast is at least 4.5:1.
- The test renders the real widgets offscreen and samples the pixels, the
  same way the audit did.

## Boundaries

- Always: run the full suite and `ruff` before every commit; keep the
  database path stable; never log a secret.
- Ask first: changing the stored key format; adding a dependency; changing
  the CI config.
- Never: commit a key; delete a test to make a build pass; widen a control
  to hide a clipping problem.

## Success criteria

- The app is fully usable at 1280×720 with no clipped text.
- `niche_research` is gone from the repository; the Social Discovery feature
  still passes its tests end to end.
- The Groq key stored today still works.
- One design system, one brand lockup, one navigation.
- The full suite is green and `ruff` is clean.

## Open Questions

None. The three decisions that shaped this spec were answered by the human.
