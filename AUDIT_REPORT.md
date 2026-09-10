# S-Q-Ali Media Downloader — Production Readiness Audit

**Date:** 2026-09-09 · **Scope:** `src/s_q_ali_media_downloader/` (46 py files, ~13.5k LOC) + packaging, CI, tests, git, skills tooling.
**Method:** every installed skill used as an audit lens (`frontend-design`, `theme-factory`, `brand-guidelines`, `canvas-design`, `code-review-and-quality`, `security-and-hardening`, `performance-optimization`, `test-driven-development`, `ci-cd-and-automation`, `git-workflow-and-versioning`, `deprecation-and-migration`, `observability-and-instrumentation`, `documentation-and-adrs`, `code-simplification`, `doubt-driven-development`, `webapp-testing`→Qt-offscreen analog, graphify architecture). Evidence gathered via full theme reads, targeted grep, WCAG contrast computation, live Qt offscreen QSS parse (PySide6 6.11.1), and three exploration agents.
**No code was changed in this pass** — this is the audit + a Phase C roadmap, not an implementation.

**Severity legend:** Critical → High → Medium → Low → Nit. "AA" = WCAG 2.1 AA contrast (normal text ≥ 4.5:1, large ≥ 3:1).

---

## 1. Executive summary

The app is functionally in good shape: 259 tests passing, QSS in both themes parses clean, no dead modules, no subprocess/eval/exec anywhere, filenames are carefully sanitized, and the downloader's visual identity is genuinely distinctive (ink-plum + cyan, status spine — one of the better desktop themes seen in a Python app).

The production blockers are concentrated in four areas:

1. **Two competing design systems** — the Niche Research suite ships a second brand (Tailwind zinc + red-600, auto light/dark, 14px base) inside a dark-cyan 13px app. Three workspace pages read as three different products.
2. **Packaging / dependency drift** — `httpx`, `pydantic`, `beautifulsoup4` are imported at runtime but missing from `pyproject.toml [project.dependencies]`; only the spec's hiddenimports keep PyInstaller builds working. `pip install .` ships a broken app.
3. **Secret handling** — API keys stored plaintext in SQLite; an old product-key secret is still recoverable from git history; a session JSON with set-cookie/token data sits untracked in the workspace.
4. **Version drift** — window title says `2.0.0`, package says `2.1.0`, installer names and README disagree, and there is no `v2.1.0` tag.

A few WCAG contrast fails and a persistent-`curl_cffi`-pin quirk round out the list. Full findings in §3, unified-token proposal in §4, roadmap in §5.

---

## 2. Asset inventory (context for the audit)

| Asset | State |
|---|---|
| `ui/theme.py` | Single plain-string `STYLESHEET` (~7.3 KB of QSS) + `C` palette dict + `STATUS_COLORS`; palette dict is **not** interpolated into the QSS (token duplication). |
| `niche_research/ui/theme.py` | 575-line f-string QSS, two palettes (`LIGHT`/`DARK`), auto dark via `QStyleHints`; ends with a stray bare `W` token (line 574, harmless — QSS parser ignores it). |
| `ui/main_window.py` | 1,200 lines; nav rail, queue cards, QSettings, `VERSION = "2.0.0"` (line 59). |
| `engine.py` | 770 lines; yt-dlp thread pool, retry/pass, filename sanitization. |
| `niche_research/` | ~28 files, ~5.6k LOC, ported wholesale from the Niche-Scope web app (`github.com/S-Q-Ali/YouTube-Creator-Tool`). |
| Tests | 25 files, ~256 test functions (259 collected on 3.14.6). Offscreen GUI smoke tests exist (conftest.py sets `QT_QPA_PLATFORM=offscreen`, `test_gui.py` constructs the real MainWindow). |
| CI | Windows + Python 3.12, ruff, pytest offscreen, PyInstaller onedir artifact. |
| Git | Mostly conventional commits; last 3 commits are large skill/graph imports. `origin/master` 4 commits behind local. |
| Skills tooling | `.opencode/skills/` = 35 skill dirs; `.opencode/references/` = 7 checklists; graphify graph = 1,165 nodes / 2,525 edges / 62 communities. |

---

## 3. Findings by lens

### L1 · Design language & tokens — `frontend-design`, `theme-factory`

**H1 — Two design systems in one product.** `ui/theme.py` (ink-plum `#100E14` + cyan `#22D3EE` accent, 13px, radii 8/9/10px, one dark mode) vs `niche_research/ui/theme.py:1-15` (zinc + `#dc2626` red-600, 14px base, auto light AND dark). The research tab auto-hides the nav rail (`main_window.py:559-564`) so it renders as a separate app. This is the classic "forked-in from another project" pattern; the distinct SQLite-backed research suite currently has no visual relationship to the downloader it lives inside.

**H2 — Primary button accent switches hue on hover.** `theme.py` STYLESHEET: `QPushButton[kind="primary"]` is cyan (`#22D3EE`), but `:hover` flips to coral `#FF8354`. Cyan button → orange hover is a palette violation (cyan↔coral have no family relationship), reads as two different buttons, and breaks the accent-consistency rule. Hover should deepen *within* the accent family (see §4).

**M4 — Token duplication.** The `C` palette dict in `theme.py` (accent `#22D3EE` etc.) is never referenced by the QSS — changing `C["accent"]` silently does nothing. The QSS and the dict can drift. *Niche* theme defines constant names (`RED_600`…) but then hard-sprinkles bare literals `#22c55e`, `#f97316`, `#eab308` across ~12 rules (theme.py:227-259, 304-335) instead of named tokens, and `#dc2626` appears inline (line 231, 245, 259) alongside the `RED_600` constant.

**M8 — Inverted tooltips in dark mode.** Niche tooltip uses `solution["text_primary"]` as background — in dark mode that is `#ffffff`, so tooltips flash white on a dark UI (`theme.py:543-549`). Readable, but a jarring inversion; the *download* theme does the correct dark tooltip (`theme.py` QSS: bg `#241F30`).

**M3 — Stray token.** `niche_research/ui/theme.py:574` ends the stylesheet with a bare `W` before the closing `"""` — a paste artifact. Harmless (QSS parser drops it silently) but embarrassing.

**Craft critique (frontend-design calibration):** the main downloader theme is *not* an AI-generic design — the vertical status spine on cards, teal→cyan rail stripe, and tracking-set wordmark give it a defensible point of view. The niche theme *is* the "SaaS-card kit" tell: uniform 12px rounded cards, one soft shadow, default red CTA, `text-transform: uppercase` labels in three places. When unifying (§4), preserve the spine and wordmark; drop the default-red + all-caps habit. `letter-spacing: 3-4px` on wordmark/follow labels is fine as a deliberate display treatment; it is *not* applied consistently (main `role="section"` also uses 2px) — settle on one tracking scale.

### L2 · Brand consistency — `brand-guidelines` (pattern only)

**M1 — Two brand voices in source.** 20 module docstrings across `niche_research/` still say "Niche-Scope" and point at `github.com/S-Q-Ali/YouTube-Creator-Tool` (`niche_research/__init__.py:1-3`, `ui/theme.py:1`, every engine's docstring). The UI renders `researchBrand`/`researchSub` labels (`theme.py:556-561`) — check the rendered strings: the *download* brand is "S-Q-Ali Media Downloader", the research brand is Niche-Scope's. A production product ships one brand. Decide the product name (user said the research brand name is retired) and sweep the docstrings + visible labels. Other products' names should live only in provenance comments, not in the product's voice.

### L3 · Accessibility — contrast (computed, not guessed)

**H4 — WCAG AA fails.** Computed ratios (see Appendix A for the full table):

- **Niche score/status badges, white text on bright fills — FAIL:** `#22c55e` 2.28:1, `#84cc16` 1.98:1, `#eab308` 1.92:1, `#f97316` 2.80:1 (theme.py:227-231). `#16a34a` 3.30:1 passes only AA-large. Only `#dc2626` 4.83:1 passes normal text. Also `competitionBadge16a34a` (white on `#16a34a`) = 3.30:1.
- **Main theme `faint` #6E667E on `bg` #100E14 = 3.53:1, on `panel` = 3.25:1 — FAIL for small text.** Used for 10-11px labels (`role="section"`, `role="hint"`), which are small. These pass AA only as *large* text.
- **Niche light-mode secondary #71717a (zinc-500) on `panel_bg` #f4f4f5 = 4.40:1 — FAIL** (passes on pure white 4.83:1). 10-11px `statKey`/`smallLabel` sit on zero-500/zero-100 panels.
- Everything else in both themes passes: main text 16.2:1, muted 6.0-6.6:1, primary button text 10.4:1, white-on-red 4.83:1, green/blue/purple tinted badges all ≥ 5.4:1.

Fixes are small: darken the badge fills one Tailwind step for the score badges, lighten `faint` one step in the main palette (e.g. `#7C7490`), and use zinc-600 for light-mode secondary on panels — no broad redesign needed.

`QScrollBar::handle` (2E2840 on 100E14) is decorative, not text — fine.

### L4 · Code health — `code-review-and-quality`, `code-simplification`

**M2 — Oversized modules.** `main_window.py` 1,200 lines, `analysis_modal.py` 794, `engine.py` 770, `agent_tab.py` 677, `youtube_client.py` 616. The top three each already contain two or three cohesive subsystems (queue+rail+settings+folders; modal+rendering; engine+classification+ffmpeg). No refactor risk score is elevated today (tests cover them), but any single-window change is expensive to review and merge. Decompose opportunistically (Phase C: split main_window's settings dialog and notice/social bars; carve `engine`'s URL classification into `agent/tools/link_parser`-style unit).

**M7 — Untested modules.** Zero test imports for `agent/orchestrator.py`, `agent/tools/tiktok_api.py`, `agent/tools/metadata_extractor.py` (verify: `rg "import" tests | grep -E "tiktok_api|orchestrator|metadata"`). `agent/tools/agent/__init__.py` and `agent/tools/__init__.py` re-exports are never imported through the package (`agent/__init__.py:3-9`) — dead API surface.

**M6 — QSS never regression-tested.** `test_theme.py` only greps strings; the `setStyleSheet()` parse (verified live for this audit: clean) isn't a test. Add a cheap offscreen test that applies both stylesheets to a widget and asserts no QSS warnings — this would have caught the stray `W`.

**N2 — Lazy-logging style.** `orchestrator.py:45`, `tiktok_api.py:160-163`, `tiktok_search.py:91,146,210,241` use eager f-string args in `logger.info(f"...")`. No secrets implicated; switch to `%s` lazy args for hygiene.

### L5 · Security — `security-and-hardening`

**C1/Critical — API keys in plaintext SQLite.** `niche_research/storage/db.py:284-294` `set_setting`/`get_setting` store `aihubmix_api_key`, `groq_api_key`, `openrouter_api_key`, `google_ai_api_key` as plain `TEXT` in `%LOCALAPPDATA%\S-Q-Ali Media Downloader\storage\niche_research.db`. Same-user processes can read them. Fix: Windows DPAPI (win32crypt / `ctypes.CryptProtectData`) or `keyring`, fall back to plaintext off-Windows, migrate existing rows on first read. `QSettings` for app settings (`main_window.py:89-90,688-689`) is fine (no secrets there).

**C2/Critical — Secret in git history.** `legacy/licensing.py` (old product-key tool) *was committed* (`SECURITY.md:32` confirms it hardcoded a secret) then removed in `487795f` and gitignored. Secrets in history are compromised forever: rotate any key the tool could derive, and consider history-rewrite only if the repo is not yet public-exposed — otherwise accept-and-rotate.

**C3/Critical — Cookies/token data untracked but present.** `new-session---2026-09-04t18-23-05-955z.json` (workspace root, untracked) captures HTTP set-cookie/token data. Delete it; add a `.gitignore` rule for `new-session---*.json` / `opencode.json` (personal config) before any push. Related gaps: `NICHE_DB_PATH` (`db.py:220`) can redirect a DB containing real keys into the repo tree, and nothing ignores it — add `*.db` ignores or document the env var as dev-only.

**H5 — Key in URL.** Gemini key rides in the query string `?key=...` (`ai_analysis_engine.py:187-190`); use `x-goog-api-key` header. httpx error snippets (`res.text[:500]`, lines 222-229) can echo request context; keep 4F response truncation, don't log request headers.

**M5 — Fetch URLs from metadata not validated.** Thumbnail/avatar/bio-link candidates fetched by raw `httpx.get` (`niche_research/ui/widgets.py:357,419`, `agent/tools/social_verifier.py:124-127,189-192,243-246`, `metadata_extractor.py:61-62`) follow redirects to arbitrary hosts. Desktop context limits severity, but https-scheme + basic SSRF/file checks are cheap. The *download* path is properly gated (`engine.py:157-224`, `main_window.py:866` scheme+host checks) — the research fetchers should match that bar. Full URLs rendered in the status bar (`engine.py:703`) — acceptable today (TikTok/YT only, no query secrets), revisit if query-bearing URLs ever land there.

**Positives:** no `.env` loading, no hardcoded creds (only fake `AIzaSy...` test fixtures), cookie file is per-run & never persisted, no key ever logged, yt-dlp used as a library (no subprocess), no eval/exec/pickle/yaml.load anywhere, downloads get sanitized filenames + atomic `os.replace`.

### L6 · CI/CD & git — `ci-cd-and-automation`, `git-workflow-and-versioning`

**H6 — CI/local drift.** CI runs Python 3.12 (`ci.yml:18`) and invokes bare `pyinstaller` (`ci.yml:34`); the local venv is 3.14.6 where the `pyinstaller.exe` launcher fails silently and only `python -m PyInstaller` works. Pin CI to py3.14 (or matrix 3.12+3.14) and use `python -m PyInstaller`.

**H3 — No release pipeline (docs lie).** `CONTRIBUTING.md:51-53` promises "the tag triggers the CI release pipeline" — no job builds the Inno installer or creates a GitHub Release. Either implement a tag-triggered release job (`release\installer.iss` exists) or correct the docs.

**M9 — CI blind spots.** No dependency audit (add `pip-audit`/`osv-scanner`); no markdown lint (5 *.md maintained unscanned); build only uploads a portable artifact — the installer the README tells users to download isn't built in CI nor attached.

**L3 — Git hygiene.** 6 orphaned Cline "checkpoint" merge blobs in history (created off the first-parent line; mainline narrative is clean). `origin/master` 4 commits behind. Conven-commits style is otherwise consistent (`rebrand`, `Add @handle` are the sole non-conforming subjects).

### L7 · Testing — `test-driven-development`, `webapp-testing`→Qt analog

**Strength:** offscreen GUI smoke suite exists (real MainWindow, rail collapse/toggle, queue add/remove), niche engines have strong per-file coverage (youtube_client 19, ai_engine 17, trending 17, scorecard 16, keyword 15), and `conftest.py` isolates APPDATA. That is a better-than-average desktop-python posture.

**Gaps:** orchestrator / tiktok_api / metadata_extractor untested (M7), QSS parse not tested (M6), and `test_engine.py:79` skips the curl_cffi/ImpersonateTarget path — which is exactly the path that's silently degrading in production (L2 below). Fix both: a trait-faked impersonate target, and a venv that actually has curl_cffi in CI.

### L8 · Performance — `performance-optimization`

No showstoppers. Startup is a single window + DB open; heavy work already lives in QThreads (`agent_tab.py` workers, `engine.py` pool). Watchlist (not findings):
- `youtube_client.py` and `engine.py` each probe thumbnails/avatars per card; if a dataset in-flight ever shows jank, cache `id → avatar` and reuse `QIcon` across cards (currently re-fetched per row — `widgets.py:357,419`).
- Graphify-out (5.4 MB committed) and 54 canvas-design TTFs (~5 MB) grow the repo clone; unrelated to runtime perf.
- Both themes redeclare `QScrollArea`/`QScrollBar` — cosmetic only.

### L9 · Deprecation / migration — `deprecation-and-migration`

**L1 — Stale `curl_cffi==0.15.0` exact pin.** The venv **does not have curl_cffi installed**, so `impersonate_target()` degrades to "missing" silently (`engine.py:125`) — TikTok downloads fail intermittently without an obvious cause, and CI runs without it too since requirements-dev inherits requirements.txt... (verify: `pip install -r requirements.txt` would install it; but the dev venv predates it). Pin to the current 0.16/0.17 line (cookie/proxy fixes), install it in the build venv, and stop silently degrading.

**L2 — Niche-Scope wholesale port.** `niche_research/` is a straight TS→Py port (docstrings say so). Debt: `data/niches.py` static catalog, sqlite DB, keyword/scorecard/trending engines — all currently proven by tests, so no action now. Revisit only if the research suite's product direction changes.

### L10 · Observability — `observability-and-instrumentation`

**M10 — No root logging config anywhere.** No `basicConfig`, no file handler, no rotation; PyInstaller ships `console=False` (spec line 50), so runtime diagnostics evaporate. Add a rotating file handler under the app-data dir (respecting an env var for verbosity), and keep the UI's status bar emitting to it. Quote secrets-never: this is where the AI-key-in-URL bug (H5) would have surfaced first.

### L11 · Docs — `documentation-and-adrs`

**M11 — Stale/incorrect docs.**
- `README.md` documents only the downloader — no mention of the AI Agent tab or Niche Research tab (the app's biggest features); references `S-Q-Ali-Media-Downloader-Setup-2.0.0.exe` (stale).
- `CONTRIBUTING.md:18` says "25+ tests" (actual ~256); `:26-29` code-layout omits `agent/` and `niche_research/`; `:51` links a deleted `REPO_IMPROVEMENT_PLAN.md`; `:51-53` promises a pipeline that doesn't exist.
- `CHANGELOG.md:48` "67 tests" (stale). CHANGELOG otherwise matches 2.1.0.
- No `docs/` dir, no ADRs. Given graphify now maps the architecture, a short `docs/ARCHITECTURE.md` (or arch ADR) is the highest-value addition.

### L12 · Risk — `doubt-driven-development`

Top risky assumptions worth consciously owning (each is fine if deliberate):
- **VERSION wall of drift (own finding H7):** `main_window.py:59` `VERSION="2.0.0"`, `SETTINGS_VERSION="2.0"`; pyproject 2.1.0; installer filenames in `build_release.bat:118,126` say `2.0.0` while `release\` contains `Setup-2.1.0.exe`; `test_gui.py:15` asserts `"2.0.0"` in the title; git has `v2.0.0` but no `v2.1.0`. One source of truth (read version from package metadata) and sweep.
- **"Keyless by default" research path relies on yt-dlp's public-HTML scraping** (`youtube_client.py`) — behavior flips silently when YouTube changes markup. The keyword/takedown handling is there; just be aware it's an implicit dependency on scrapers.
- **`cookiesfrombrowser=("chrome",)`** (`engine.py:269,546`) reaches into the user's Chrome profile by design — keep it opt-in (it is; the toggle is saved, the path isn't).

### L13 · Architecture — graphify

Graph (1,165 nodes / 2,525 edges / 62 communities) confirms: `agent/` (orchestrator+tools), `niche_research/` (engines+ui+storage), and `ui/` (window+rail+queue) are cleanly separated; the only cross-cutting surface is `engine.py` (download) + `main_window.py` (queue). No accidental cycles beyond the expected ui→engine/agent→schema direction. `niche_research/storage/db.py` is the one module with its own io boundary (sqlite) — treat it as the seam for future DPAPI sealing (C1).

### L14 · Skill applicability matrix (Claude/Anthropic skills that don't directly apply)

| Skill | Verdict for this repo |
|---|---|
| `webapp-testing` (Playwright) | N/A for Qt — mapped to offscreen GUI smoke tests (which exist). |
| `web-artifacts-builder` | N/A — desktop app, no React/TS web artifacts. |
| `claude-api` | N/A today — the app calls third-party AI APIs (Groq/OpenRouter/AIHubMix/Gemini), not the Anthropic API. Useful reference if Anthropic joins the provider list. |
| `mcp-builder` | N/A — no MCP server; the research tools are in-process. Could *become* relevant if a multi-session research service is ever made external. |
| `skill-creator` | Applicable — next agent-quality task (self-audit `.opencode/skills/`, add a design-review skill) should follow its grader/eval loop. |

---

## 4. Proposed unified token spec (design system target)

Derived from `theme-factory`'s pair/token structure, **preserving the downloader's identity** (ink-plum + cyan + teal spine) as the app-wide single system. The niche research pages adopt this system (dark-only; no light mode) rather than carrying a second brand.

| Token | Value | Notes |
|---|---|---|
| bg / surface base | `#100E14` | keep ink-plum |
| panel | `#1A1722` | keep |
| raised tiers | `#241F30` / `#2E2840` | keep |
| border | `#332C42` / hover `#6E667E` | keep |
| text / primary | `#EFEAF5` | keep |
| text / secondary | `#9C93AE` | keep |
| text / tertiary (faint) | `#7C7490` | **raise from #6E667E** to pass AA on bg (3.53→4.5+) |
| accent / primary | `#22D3EE` → hover `#67E8F9` | **fix H2**: hover lightens within the cyan family, not coral |
| accent / done | `#2DD4BF` | keep teal family |
| accent / waiting | `#A78BFA` | keep |
| warning | `#FFB020` | keep |
| error / failed | `#F2547D` | **replace red `#dc2626`** in research UI |
| success fills (badges) | green-600 `#15803D` on `#DCFCE7` | **fix H4**: use darker fills for white/colored text |
| radius scale | 6 / 8 / 10 (was 5/6/8/9/10/12/999) | unify: badges 6, inputs 8, cards 10; pill `999` only where literally pill |
| type scale | 10/11/12/13/14/17/19 | research's 14px base → 13px app base; display stays 19px wordmark |
| tracking | 2px labels, 3-4px display only | settle on one scale |
| dark mode | single app dark (no auto light) | research auto-light/dark removed |

Brand: **one** name in UI strings + docstrings (sweep Niche-Scope). Migration keeps the SQLite schema and all engine APIs untouched — a pure token/stylesheet swap (Phase C) — so the 163 niche tests stay green unchanged.

---

## 5. Phase C roadmap (deferred — implement only after this report is approved)

Ordered by (cost ÷ impact). Each is a separately verifiable slice; run `pytest` + `ruff` after each.

1. **Secrets & hygiene (quick, high impact):** delete `new-session---*.json` + gitignore rules; DPAPI-seal API keys in `db.py` (or `keyring`); switch Gemini `?key=`→header; add `*.db` note.
2. **Version wall:** single version source (package `__version__`), update `main_window.py` + `test_gui.py` + installer names + README; tag `v2.1.0`.
3. **Dependencies:** add httpx/pydantic/beautifulsoup4 to `pyproject [project.dependencies]`; relax curl_cffi to `~=0.16`; install into build venv; stop silent impersonation degrade.
4. **Contrast fixes:** faint→`#7C7490`; badge fills darkened; light-mode secondary on panels.
5. **Design unification (biggest slice):** research pages → unified dark-cyan token system (§4); primary-hover fix; tooltip fix; remove stray `W`; renumber radii. Keep engine/schema/DB untouched.
6. **Brand sweep:** Niche-Scope docstrings + visible labels → app brand; provenance comments only.
7. **CI:** `python -m PyInstaller`, py 3.14 (or matrix), `pip-audit`, tag-triggered release job (or correct CONTRIBUTING).
8. **Tests:** QSS-parse regression test; orchestrator/tiktok_api/metadata_extractor coverage; un-skip the curl_cffi path.
9. **Docs:** README features + v2.1.0 installer; CONTRIBUTING test counts/layout/deleted-file; CHANGELOG "tests" number; optional `docs/ARCHITECTURE.md` from graphify.
10. **Observability:** rotating file logger under app-data.
11. **Cleanup (opportunistic, low priority):** `main_window`/`engine`/`analysis_modal` decomposition; dead `agent/__init__` re-exports; final `W`/lazy-log nits.

**Verification plan for Phase C:** every slice ends with `pytest` (259+ ≥ 250), `ruff check src tests`, and — for the design slices — the new offscreen QSS-parse test + contrast re-computation. End of phase: rebuild portable + installer via `python -m PyInstaller` path, screenshot the three workspace pages for a visual review.

---

## Appendix A — WCAG contrast table (computed)

Legend: ✓ AA (≥4.5), ◐ AA-large only (≥3), ✗ fail (<3, or <4.5 for small text).

| Pair | Ratio | Status | Note |
|---|---|---|---|
| `#EFEAF5` on `#100E14` | 16.22 | ✓ | main text |
| `#9C93AE` on `#1A1722` | 6.05 | ✓ | main muted |
| `#6E667E` on `#100E14` | 3.53 | ◐ | **small 10-11px labels FAIL** |
| `#6E667E` on `#1A1722` | 3.25 | ◐ | same |
| `#17100C` on `#22D3EE` | 10.41 | ✓ | primary btn text |
| `#17100C` on `#FF8354` | 7.73 | ✓ | hover — contrast fine, **hue wrong** |
| `#FFB020` on `#241C14` | 9.18 | ✓ | notice bar |
| `#22D3EE` on `#100E14` | 10.61 | ✓ | accent |
| `#F2547D` on `#100E14` | 5.79 | ✓ | failed |
| `#ffffff` on `#dc2626` | 4.83 | ✓ | white-on-red (research) |
| `#71717a` on `#ffffff` | 4.83 | ✓ | light secondary on white |
| `#71717a` on `#f4f4f5` | 4.40 | ◐ | **small labels FAIL** on z-100 |
| `#a1a1aa` on `#27272a` | 5.81 | ✓ | dark secondary on card |
| `#ffffff` on `#22c55e` | 2.28 | ✗ | score badge green-500 |
| `#ffffff` on `#84cc16` | 1.98 | ✗ | lime |
| `#ffffff` on `#eab308` | 1.92 | ✗ | yellow (black variant `competitionBadgeEab308` = 10.95 ✓) |
| `#ffffff` on `#f97316` | 2.80 | ✗ | orange |
| `#ffffff` on `#16a34a` | 3.30 | ◐ | green-600 AA-large only |
| `#166534` on `#dcfce7` | 6.49 | ✓ | green-700 on green-100 |
| `#1d4ed8` on `#dbeafe` | 5.49 | ✓ | blue badge |
| `#7e22ce` on `#f3e8ff` | 5.92 | ✓ | purple badge |

## Appendix B — Method / verification breadcrumbs

- QSS parse: both stylesheets applied offscreen on PySide6 6.11.1 → zero QSS warnings; `text-transform: uppercase` IS supported by Qt QSS (non-issue, verified live).
- Contrast: relative-luminance WCAG 2.1 formulas, computed from the exact hex in both theme files.
- Dead/untested module checks: `rg` over test imports; graphify `query`/`path` used for the architecture lens.
- Line refs are to the current working tree (`70b4f54` + AUDIT_REPORT.md).