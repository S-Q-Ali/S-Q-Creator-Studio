# Task List: Cross-Platform Support

Plan: `tasks/plan-cross-platform.md` · Spec: `tasks/spec-cross-platform.md`

Tasks are ordered by dependency. Sizes: XS = 1 file, S = 1–2, M = 3–5.

## Phase A — stop the false claim shipping (`docs-truth-interim`)

- [x] **A1. Honest platform + security wording** — README:7 badge, README:65,
      README:137, README:73, README:82 + :6, README:107-113 recipe,
      README:149 browser-use wording; SECURITY.md:49; CONTRIBUTING.md:49.
      Acceptance: no claim survives that CI does not currently prove; Windows
      stays the stated platform; "Linux/macOS: not yet tested, help wanted".
      Verify: `grep` for the removed strings; diff reviewed line by line.
      Files: `README.md`, `SECURITY.md`, `CONTRIBUTING.md` · **S**
- [x] **A2. CHANGELOG + commit** — docs-only entry under Unreleased/Fixed; no
      version bump of the package itself. Committed as `282622b`.
      Acceptance: dated heading, phrased as user impact, not internal mechanics.
      Verify: `git diff --stat` shows docs only. Files: `CHANGELOG.md` · **XS**

## Phase B — prove the dependencies resolve (`deps-proof`)

- [x] **B1. Wheel + import proof spike** — the wheel half ran locally
      (`tasks/spike_platform_wheels.py`, results in
      `tasks/spike_platform_wheels.json` — both under the gitignored
      `tasks/spike_*` path, so the command is recorded here); the import half
      cannot run here and moves to the CI matrix (F1/F2), which is where
      importing on Linux/macOS is actually proven.

      Reproduce one target with:
      `uv pip compile --only-binary :all: --python-version 3.14
      --python-platform x86_64-manylinux_2_35 requirements.txt
      requirements-dev.txt` (stdout, no install).

      | Target | 3.12 | 3.14 |
      |---|---|---|
      | linux x86_64, glibc ≥ 2.34 | ok · 149 pkgs | ok · 149 pkgs |
      | linux x86_64, glibc 2.28 | **no PySide6 6.11 wheel** | same |
      | linux x86_64, manylinux2014 (2.17) | PySide6 **and** pillow 12.3.0 have no wheel | same |
      | linux arm64, glibc ≥ 2.39 | ok · 149 pkgs | ok · 149 pkgs |
      | linux arm64, glibc 2.35 | **no PySide6 6.11 wheel** (aarch64 ships 2.39) | same |
      | macos arm64 | ok · 153 pkgs | ok · 153 pkgs |
      | macos x86_64 | ok · 153 pkgs | ok · 153 pkgs |
      | windows x86_64 (today's CI) | ok · 152 pkgs | ok · 152 pkgs |

      Verdicts that change the plan:
      1. **Scope does not change.** Every pin — `PySide6 6.11.3`,
         `curl_cffi 0.15.0`, `yt-dlp 2026.10.26`, `playwright 1.64.1`,
         `instaloader 4.16`, `mutagen 1.48.1`, `SpotipyFree 1.9.14`,
         `browser-use 0.13.14`, `pyinstaller 6.22.3` — resolves identically on
         all four platforms. Nothing has to be loosened or replaced.
      2. **`pywin32` was a false alarm.** `pip install --platform` filters wheel
         tags but still evaluates environment markers against the *host*, so on
         Windows it demands `pywin32; sys_platform=="win32"` for a Linux target
         and reports a failure that does not exist. `uv pip compile
         --python-platform` rewrites markers for the target; with it,
         `pywin32`/`pywin32-ctypes` appear only in the Windows lock. Cross-
         resolution in this repo is a uv job, and the spike now shells out to it.
      3. **The floors are real and must be documented:** Linux x86_64 needs
         glibc ≥ 2.34 (Ubuntu 22.04, Debian 12, Fedora 36+), Linux arm64 needs
         glibc ≥ 2.39, macOS needs 13 Ventura+ (PySide6 ships
         `macosx_13_0_universal2` only). Python 3.12 and 3.14 both work; 3.10 and
         3.11 are untested and are not claimed.
      4. **Still open:** the Linux Qt runtime libraries (`libxkbcommon`,
         `libEGL`, `libGL`) and whether the headless runner has them — only a CI
         run shows that.

      Files: `tasks/spike_platform_wheels.py`, `tasks/spike_platform_wheels.json` · **M**
- [x] **B2. Reconcile the dependency sources** — B1 removed the portability
      argument for moving `browser-use`, so it stays out of the runtime
      requirements. The spike instead surfaced a worse drift: **`playwright` was
      in `requirements.txt` and only in a `.[social]` pyproject extra**, so
      `pip install .` built an app without the browser Social Discovery needs.
      `tests/test_requirements_agree.py` now compares both requirements files
      against `pyproject.toml` and names every mismatch; it was red on exactly
      three findings (playwright's home, `browser-use` exact-vs-range,
      `pip-audit` undeclared) and is green now that they are fixed.
      Acceptance: one source of truth per dependency, guarded by a test.
      Files: `pyproject.toml`, `tests/test_requirements_agree.py` · **S**

## Phase C — secrets on every OS (`secrets-portable`)

- [x] **C1. Failing tests for the three backends** — written first and red
      (13 failures on 14 tests), then green: fake keyring injected; no plaintext
      in the row when keyring works; `plain:` marker + warning when there is no
      store or the keychain refuses the write; a `plain:` row upgraded to the
      keychain when a store appears; `dpapi1:` round-trip on Windows; `caplog`
      never contains the key.
      Files: `tests/test_core_storage_secrets.py` (new) · **S**
- [x] **C2. Backend table in `settings_store`** — `_secret_backend()` /
      `_detect_secret_backend()` / `secret_backend_name()`, `SEAL_DPAPI` /
      `SEAL_KEYRING` / `SEAL_PLAIN`, the keyring backends imported by name for
      frozen builds, and the re-seal of a `plain` row. The Windows-only
      `ctypes.wintypes` import now sits behind `if sys.platform == "win32"`,
      which is what had made the module (and Settings) unimportable off Windows.
      `keyring>=25.0; sys_platform != "win32"` is in `requirements.txt` and
      `pyproject.toml`, so the Windows dependency set is unchanged.
      Acceptance held: the Windows branch is behaviourally byte-identical, and
      `tests/test_core_settings_store.py` still passes untouched. · **M**
- [x] **C3. OS-aware Settings wording** — `settings_page.py:480` no longer says
      "this Windows account" off Windows, and the keys card now carries
      `key_storage_note` stating where the keys live for the backend in use,
      including the unencrypted case. README and SECURITY.md describe all three
      backends and mark the keychain path as unit-tested but not yet run on real
      Linux/macOS hardware.
      Files: `ui/settings_page.py`, `tests/test_settings_page.py`, `README.md`,
      `SECURITY.md`, `CHANGELOG.md` · **S**

## Phase D — runtime portability (`runtime-portable`)

- [x] **D1. Storage dirs** — `app_storage_dir()` (`engine.py:208-218`) and
      `db_path()` (`settings_store.py:117`) onto `QStandardPaths`, Windows path
      byte-identical, `SQ_DB_PATH`/`LOCALAPPDATA` overrides still honoured,
      migrate a POSIX `~/S-Q Ali…` folder if it exists. Acceptance: the log dir
      and the data dir stop disagreeing (`app.py:49-50`).
      Files: `engine.py`, `core/settings_store.py`, `tests/test_engine_paths.py` · **M**
      Done: the base is `LOCALAPPDATA` → `QStandardPaths.GenericDataLocation` →
      home, so Windows keeps `%LOCALAPPDATA%\S-Q-Ali Media Downloader\storage`,
      Linux gets `~/.local/share/…` and macOS `~/Library/Application Support/…`.
      `db_path()` and `setup_logging()` now read that one decision (the log left
      `AppData\Local\S-Q-Ali\S-Q-Ali Media Downloader` for the storage folder),
      and `migrate_legacy_storage_dir()` moves a home-directory folder into place
      once at startup — only when the legacy folder exists and the new one does
      not, so a current install is never touched. 7 tests in
      `tests/test_engine_paths.py`; the full offline suite is green on Windows.
- [x] **D2. ffmpeg discovery** — `find_ffmpeg()` (`engine.py:694-714`) checks a
      bundled `ffmpeg` as well as `ffmpeg.exe`, then PATH. Acceptance: a POSIX
      bundle with `bin/ffmpeg` is found with an empty PATH. Files: `engine.py`,
      `tests/test_engine_ffmpeg.py` · **S**
      Done: the bundled name follows `sys.platform` (win32 → `ffmpeg.exe`,
      anything else → `ffmpeg`), probed beside the app and in `bin/` before
      PATH. 5 tests in `tests/test_engine_ffmpeg.py` cover win32/linux/darwin
      with an empty PATH; the Windows bundle and the PATH fallback keep their
      own cases so the shipped behaviour is guarded, not just the new branch.
- [x] **D3. Browser resolution** — POSIX playwright cache roots
      (`browser.py:160-162`), `msedge` channel gated to Windows (`:41`),
      Chromium sandbox handling for root/CI (`:288-301`). Acceptance: the
      darwin/linux branches each have a test that fails without the change.
      Files: `agent/tools/browser.py`, `tests/test_social_browser.py` · **M**
      Done: `browser_channels()` and `_playwright_cache_dir()` replace the
      Windows constants, `launch_args()` adds `--no-sandbox` only when the uid
      is 0, and 14 tests cover the three OSes. Reading the installed Playwright
      package turned up a fourth gap the plan did not name: the cached Chromium
      layouts. 1.64 installs `chrome-linux64/chrome`, `chrome-linux-arm64/chrome`
      and `chrome-mac-{x64,arm64}/Google Chrome for Testing.app/…`, none of which
      the old list (`chrome-linux`, `Chromium.app`) would find — so even with the
      cache root fixed, the browser stayed invisible. Verified against
      `playwright/driver/package/lib/coreBundle.js`, not guessed.
- [x] **D4. OS-neutral strings** — `browser.py:12`/`:269`,
      `settings_page.py:109`, `engine.py:815-820`. Files: as listed · **XS**
      Done: the module header and the "no Playwright" message now say "this
      machine", and the preferences comment names the registry, the plist and the
      ini file. `engine.py:815-820` needed nothing — those strings name Chrome,
      not Windows. Left alone on purpose: the four hardcoded
      `Mozilla/5.0 (Windows NT 10.0…)` user-agent strings in
      `metadata_extractor.py`, `social_verifier.py`, `tiktok_api.py` and
      `youtube_existence.py`. They are a fingerprint the scraping was tuned
      against, not a sentence anyone reads, and making them "honest" would
      change what TikTok and YouTube see from a Linux session.

## Phase E — make the suite portable before CI sees it (`test-portable`)

- [x] **E1. Per-OS font sourcing** — replace `%WINDIR%\Fonts` seeding
      (`conftest.py:143`) with a per-OS source, keep the documented intent
      ("tests see the same clipping the user does"), no-op cleanly when absent.
      Files: `tests/conftest.py` · **M**
      Done: `FONT_SOURCES` names the folders and the faces per OS (Windows
      Segoe/Consolas from `%WINDIR%\Fonts`, macOS Helvetica/Menlo, Linux
      DejaVu/Liberation/Noto/Ubuntu under `/usr/share/fonts` and the user's own
      font dirs) and `system_font_files()` resolves them, skipping a folder that
      is not there and a font nobody has. The intent sentence is unchanged and
      the fixture says out loud, rather than failing quietly, when a machine has
      none of them: the widths then are Qt's fallback metrics.
- [x] **E2. POSIX-safe teardown** — remove the `QThread.terminate()` reliance
      (`conftest.py:77`, `:192-197`): interruption + bounded wait, then a loud
      failure instead of a silent kill. Acceptance: no orphaned process on any
      OS. Files: `tests/conftest.py` · **S**
      Done: `terminate()` is gone from both teardowns. `_stop_running_qthreads()`
      now calls the worker's own `stop()` (the app's threads check that flag
      between jobs and inside every wait, so they end in under 0.2 s), asks Qt
      for an interruption as well, waits, and *returns* the threads that would
      not stop. The per-test fixture fails naming them; the session fixture does
      the same after its 10 s grace. Nothing in the current suite was relying on
      the silent kill — 761 offline tests pass with the loud version, and no
      `python.exe` survives the run.
- [x] **E3. Storage isolation** — make the temp-appdata fixture autouse for
      anything touching `app_storage_dir()`/`db_path()`. Acceptance: a test run
      creates nothing in the real home. Files: `tests/conftest.py` · **S**
      Done: a session-scoped autouse fixture points `LOCALAPPDATA` at one
      `sqali_appdata_*` temp folder, which is the base `app_storage_dir()` reads
      on every OS, so the queue, downloads, database, browser profile and log of
      a test run all land there. The per-test `isolated_appdata` stays for the
      tests that want a clean folder and now restores to the session's, not the
      developer's. Verified by marker: the 70 GUI/queue/settings tests that open
      a window leave the real `%LOCALAPPDATA%\S-Q-Ali Media Downloader` untouched.
- [x] **E4. The suite guards itself** — `tests/test_suite_portability.py` (new,
      6 tests): the font lookup finds a named face in a subfolder and ignores
      what it is not told to read, every OS the suite can run on has a source,
      the run's app folder is inside the temporary appdata, and the teardown
      helper stops a cooperating worker but *reports* one that ignores the stop
      request. Writing it found the shape of the crash the old `terminate()` was
      hiding: a test that starts a QThread and drops the reference has it deleted
      while running, which kills the process mid-run with no summary at all
      (exit 127, empty log). The tests now hold the thread and wait for it.

### Checkpoint: before any CI change
- [x] Offline suite green on Windows, `ruff` clean, `graphify update .` run, the
      pre-baked `dpapi1:` row still reads, no plaintext key when a store exists.
      Results: 761 passed / 19 deselected in 3 min 38 s, exit 0, no summary lost.
      `ruff check src tests` clean. All six stored keys in the real
      `%LOCALAPPDATA%\S-Q-Ali Media Downloader\storage\niche_research.db` are
      `dpapi1:` sealed and unseal (lengths checked, never the values), and none
      is plaintext or `plain:`. No `python.exe` left running after the suite.

## Phase F — the matrix (`ci-matrix`)

- [x] **F1. Matrix job** — `ci.yml` → ubuntu/macos/windows × 3.12/3.14, PRs
      trimmed to windows+ubuntu at one Python, full matrix on `master` and tags,
      `QT_QPA_PLATFORM=offscreen`, per-OS ffmpeg + `playwright install chromium`
      only where needed, pip-audit kept. Acceptance: the same tests that pass
      locally pass on all three runners. Files: `.github/workflows/ci.yml` · **M**
      Done: a `pick` job emits the matrix as JSON — a pull request gets
      ubuntu-24.04 + windows-latest at 3.14, a push to master gets all three
      OSes at 3.12 and 3.14 (`fail-fast: false`, so one OS failing shows up
      rather than cancelling the others). Both payloads and the whole file parse
      (checked with a throwaway PyYAML run; no actionlint or Docker here). Linux
      installs `libxkbcommon-x11-0 libegl1 libgl1 libglib2.0-0 libdbus-1-3`,
      which the offscreen platform needs before the first `QApplication`; the
      audit runs once per OS at 3.14 because `keyring` only enters the set off
      Windows; ffmpeg, the Chromium download, the build, the smoke test and the
      artifact are gated to Windows at 3.14, so master still publishes exactly
      one portable build.
      **Still open — the acceptance itself.** Whether the 761 tests pass on the
      other two runners is what the matrix exists to find out, and that needs a
      push. Nothing here is claimed in the README until a green run is seen.
- [ ] **F2. Per-OS build + smoke** — portable build on each OS, launch for 15 s,
      assert alive, clean kill; artifacts uploaded per OS. The runner floors
      come from B1: `ubuntu-24.04` or newer (glibc ≥ 2.34 x86_64, 2.39 arm64)
      and a macOS 13+ runner, or PySide6 6.11 has no wheel to install.
      Files: `.github/workflows/ci.yml`, `.github/workflows/release.yml` · **M**
      **Was blocked by G1, not by F1 — now unblocked.** A POSIX build needs
      `release/build.py`: the only build script was `release/build.bat`, and its
      ffmpeg staging probed `bin\ffmpeg.exe` — a name that does not exist on
      Linux or macOS, so the build failed out on the spot (B2's "the build fails"
      finding). G1 landed and is verified on Windows (G2), so F2 is now the job
      that runs that script on three OSes — which needs a push to be seen.

## Phase G — one build script (`packaging`, portable-first scope)

- [x] **G1. `release/build.py`** — the `build.bat:47-189` logic ported: PyInstaller
      with the same `--hidden-import`/`--collect-all` set plus `keyring`
      (submodules + metadata), OS-correct `--add-data` separator, ffmpeg and
      Chromium staging from the right cache per OS, portable folder assembly
      without `robocopy`/`xcopy`/`attrib`. Inno Setup stays Windows-only.
      Acceptance: `build.bat` becomes a thin wrapper and the Windows artifact is
      unchanged file-for-file. Files: `release/build.py` (new), `release/build.bat`,
      `release/README.md` · **L**
      Done: the script builds, stages and installs exactly as the batch file did,
      with every OS-dependent decision in a named function. 19 tests in
      `tests/test_release_build_script.py` cover the flag set, the `--add-data`
      separator, the ffmpeg search order and staged name, the browser cache the
      app itself reports (one definition, shared with `agent/tools/browser.py`),
      the locked-`portable` fallback, and that `build.bat` no longer mentions
      PyInstaller, `robocopy`, `xcopy` or `attrib` at all.
      `.gitignore` gained `!release/build.py` / `!release/build.bat` — both are
      source now, not output.
- [x] **G2. Verify the Windows artifact did not move** — rebuilt
      `release\build.py` end to end on Windows (exit 0, 14 min):
      3,610 files vs the recorded 3,608 — the two additions are
      `_internal/libcrypto-3-x64.dll` and `_internal/libssl-3-x64.dll`, resolved
      from `C:\Program Files\Git\mingw64\bin` because PyInstaller searches the
      build machine's PATH for a loose DLL name. Nothing else differs; the file
      lists match line for line (`/tmp/pre_files.txt` vs `/tmp/post_files.txt`).
      Launcher 41,071,419 B (was 41,066,924 — the bootloader embeds its own
      build stamp); installer 336,254,560 B (was 334,776,797 — the same 6.8 MB of
      DLLs compressed). `bin\ffmpeg.exe` from the winget folder,
      `browsers\chromium-1248` (the full build, headless shell skipped), Inno
      compile first attempt, and the frozen EXE alive 40 s offscreen with no
      orphan left behind. Command-line proof that the script did not change what
      is collected: the old `build.bat`'s 16 `--collect-all` and 6
      `--hidden-import` values are the same sets, and the keyring flags appear
      only where keyring is importable (not on this machine).
      Verdict: no unexplained delta. The PATH-resolved DLLs are a property of
      the machine, not of the script — recorded here because it is how a future
      artifact diff gets explained. Files: none · **S**
- [ ] **G3. `release.yml` three archives** — tag builds and uploads a portable
      archive per OS, notes state the platform support honestly.
      Files: `.github/workflows/release.yml` · **M**
- [ ] **G4. File the deferred scope as issues** — native `.AppImage`/`.deb`/`.dmg`,
      signing + notarisation, each with the reason it was cut. Cross-linked to
      this plan. Files: GitHub issues · **XS** — not filed: writing to the public
      tracker needs a fresh go from the user.

## Phase H — docs that match the build (`docs-truth`)

- [ ] **H1. Per-OS install/run/build docs** — README install + Quick Start +
      build-from-source recipe (now `python release/build.py`), FAQ per OS,
      Python "3.12 and 3.14 tested", the OS floors from B1 (glibc ≥ 2.34
      x86_64 / ≥ 2.39 arm64, macOS 13+), keyring/DPAPI statement, CONTRIBUTING
      setup blocks, SECURITY per-OS storage table, issue-template OS line.
      Acceptance: every claim maps to a CI job or an artifact that exists.
      Files: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `release/README.md`,
      `.github/ISSUE_TEMPLATE/bug_report.md` · **M**
- [ ] **H2. CHANGELOG + version bump** — the release that first claims three OSes.
      Verify: dated heading before any tag, per the standing rule.
      Files: `CHANGELOG.md`, `__init__.py`, `pyproject.toml` · **XS**
- [ ] **H3. The declared Python floor** — `pyproject.toml:10` says
      `requires-python = ">=3.10"`, which is a promise nothing runs on: F1 tests
      3.12 and 3.14 only, and B1's spike found that the `[agent]` extra cannot
      even resolve on 3.10 (`browser-use==0.13.14` needs >=3.11). Raise the floor
      to what CI proves — a metadata change consumers can see, so it belongs with
      the version bump, not beside a workflow edit.
      Acceptance: `uv pip compile` resolves the package for every Python the
      metadata allows. Files: `pyproject.toml` · **XS**

### Checkpoint: done
- [ ] Full matrix green twice, three archives published, no orphan processes,
      README claims only what CI proves, glass-UI work unblocked.
