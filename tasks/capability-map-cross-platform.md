# Capability Map: Cross-Platform Support (option b)

**Status:** awaiting map approval — no module spec is written until this table
and the four open decisions are approved.

**Problem.** v2.10.0 advertises `Windows | Linux | macOS` (README:7, README:65)
and "keys sealed with DPAPI" (README:137, SECURITY.md:49), and none of it is
delivered: CI runs only `windows-latest` (ci.yml:10, release.yml:15), releases
ship only `.exe`, and off-Windows the secret store writes keys in plain text
(`core/settings_store.py:92`) and refuses to read a Windows-sealed one
(:97-98). Choosing (b) means making the claim true, then documenting it.

## Module map

| Module id | Responsibility | Depends on |
|---|---|---|
| `docs-truth-interim` | A docs-only patch release that stops the README/SECURITY claims being false while (b) is built | — |
| `secrets-portable` | Seal API keys per OS: DPAPI on Windows (unchanged), OS-native store on macOS/Linux, honest behaviour when no secret store exists | — |
| `runtime-portable` | Per-OS storage dirs (XDG / Application Support), ffmpeg discovery incl. a bundled POSIX binary, Playwright cache roots, browser channel + Chromium sandbox handling, OS-neutral UI and error strings | — |
| `test-portable` | The offline suite green on three OSes: font sourcing per OS, no reliance on `QThread.terminate()` (a no-op on POSIX), autouse storage isolation, tests for the darwin/linux branches that nothing covers today | `secrets-portable`, `runtime-portable` |
| `ci-matrix` | `ci.yml` becomes an OS × Python matrix that runs lint, offline tests, pip-audit and a wheel/import resolution check on ubuntu + macos + windows | `test-portable` |
| `packaging` | A per-OS build (PyInstaller onedir, ffmpeg + Chromium staging, code-signing story or an explicit "unsigned" note) and `release.yml` uploading an artifact per OS | `ci-matrix` |
| `docs-truth` | README, CONTRIBUTING, SECURITY, `release/README.md`, bug-report template state per OS what actually works, with the correct build recipe (`--add-data` separator, the `--collect-all` set `release/build.bat:56-77` proves is needed) | `packaging` |

Build order: `docs-truth-interim` → (`secrets-portable` ∥ `runtime-portable`) →
`test-portable` → `ci-matrix` → `packaging` → `docs-truth`.

## Assumptions I'm making

1. Windows stays the primary product: the `.exe` + Inno installer path must not
   regress at any step, and the Windows release stays green throughout.
2. The current DB file and the `dpapi1:` rows in it are never invalidated — a
   key stored on Windows today must keep working on Windows tomorrow.
3. "Supported" = the app starts, downloads, discovers and stores a key on that
   OS, proven by CI — not a polished installer on every OS.
4. No new runtime dependency without approval (that is why decision 1 below
   exists).
5. The user's machine is Windows; macOS/Linux behaviour is proven only by CI
   runners and offscreen renders, never by local eyeballing.

## Evidence the map is built on

- `core/settings_store.py:27` imports `ctypes.wintypes` unconditionally (harmless
  — it imports fine on POSIX), `:80` gates sealing on `win32`, `:92` returns the
  secret unchanged, `:97` raises for `dpapi1:` rows elsewhere.
- `engine.py:706-711` only ever looks for `ffmpeg.exe` inside the bundle, then
  `shutil.which("ffmpeg")` — a bundled POSIX binary would be missed.
- `engine.py:213` and `settings_store.py:117` use `LOCALAPPDATA` → `~` fallback,
  while `app.py:49-50` uses `QStandardPaths` — two different storage conventions.
- `agent/tools/browser.py:160-162` only appends `%LOCALAPPDATA%\ms-playwright`;
  the Linux (`~/.cache/ms-playwright`) and macOS (`~/Library/Caches/…`) roots are
  missing. `:41` always tries the `msedge` channel. No launch sets
  `chromium_sandbox=False`, which breaks under root in CI containers.
- `requirements.txt` / `pyproject.toml` have **zero** platform markers and no
  Windows-only deps — so the wheel question is empirical, not visible in files.
- `tests/conftest.py:143` seeds the offscreen font DB from `%WINDIR%\Fonts`, and
  `:77`/:192-197 lean on `QThread.terminate()`; layout tests measure real font
  metrics, so both behave differently on other OSes.
- `release/build.bat` is cmd.exe throughout (`robocopy`, `xcopy`, `winget`,
  `ISCC`) — the logic is reusable, the syntax is not.

## Boundaries

- **Always:** offline suite + `ruff` before every commit; the Windows pipeline
  stays green; no secret ever reaches a log, URL or exception message.
- **Ask first:** any new dependency; any CI config change; any change to the
  stored key format; any release-affecting push or tag.
- **Never:** invalidate an existing Windows key; delete a test to make a run
  pass; claim an OS in the README that CI does not test.

## Success criteria (draft, to be finalised per module)

- `pytest -m "not live"` is green on ubuntu-latest, macos-latest and
  windows-latest in one CI run.
- On macOS/Linux a key entered in Settings is not written in plain text, or the
  app says so out loud and refuses silently-degrading.
- A release download exists for each supported OS, and the README build recipe
  actually produces a working bundle on that OS.

## Open decisions (blocking)

1. **POSIX secret backend** — `keyring` dependency vs 0600 file + loud warning
   vs refuse to store off Windows.
2. **Packaging scope now** — native `.AppImage`/`.dmg`, or per-OS portable
   onedir folders only (native installers filed as an issue).
3. **Python floor claim** — CI proves which versions; README then claims only
   those. Matrix over 3.10–3.14, or a raised floor?
4. **Build order against the glass-UI initiative** (`tasks/design-brief-glass-ui.md`).
