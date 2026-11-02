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
- [ ] **D2. ffmpeg discovery** — `find_ffmpeg()` (`engine.py:694-714`) checks a
      bundled `ffmpeg` as well as `ffmpeg.exe`, then PATH. Acceptance: a POSIX
      bundle with `bin/ffmpeg` is found with an empty PATH. Files: `engine.py`,
      `tests/test_engine_ffmpeg.py` · **S**
- [ ] **D3. Browser resolution** — POSIX playwright cache roots
      (`browser.py:160-162`), `msedge` channel gated to Windows (`:41`),
      Chromium sandbox handling for root/CI (`:288-301`). Acceptance: the
      darwin/linux branches each have a test that fails without the change.
      Files: `agent/tools/browser.py`, `tests/test_social_browser.py` · **M**
- [ ] **D4. OS-neutral strings** — `browser.py:12`/`:269`,
      `settings_page.py:109`, `engine.py:815-820`. Files: as listed · **XS**

## Phase E — make the suite portable before CI sees it (`test-portable`)

- [ ] **E1. Per-OS font sourcing** — replace `%WINDIR%\Fonts` seeding
      (`conftest.py:143`) with a per-OS source, keep the documented intent
      ("tests see the same clipping the user does"), no-op cleanly when absent.
      Files: `tests/conftest.py` · **M**
- [ ] **E2. POSIX-safe teardown** — remove the `QThread.terminate()` reliance
      (`conftest.py:77`, `:192-197`): interruption + bounded wait, then a loud
      failure instead of a silent kill. Acceptance: no orphaned process on any
      OS. Files: `tests/conftest.py` · **S**
- [ ] **E3. Storage isolation** — make the temp-appdata fixture autouse for
      anything touching `app_storage_dir()`/`db_path()`. Acceptance: a test run
      creates nothing in the real home. Files: `tests/conftest.py` · **S**

### Checkpoint: before any CI change
- [ ] Offline suite green on Windows, `ruff` clean, `graphify update .` run, the
      pre-baked `dpapi1:` row still reads, no plaintext key when a store exists.

## Phase F — the matrix (`ci-matrix`)

- [ ] **F1. Matrix job** — `ci.yml` → ubuntu/macos/windows × 3.12/3.14, PRs
      trimmed to windows+ubuntu at one Python, full matrix on `master` and tags,
      `QT_QPA_PLATFORM=offscreen`, per-OS ffmpeg + `playwright install chromium`
      only where needed, pip-audit kept. Acceptance: the same tests that pass
      locally pass on all three runners. Files: `.github/workflows/ci.yml` · **M**
- [ ] **F2. Per-OS build + smoke** — portable build on each OS, launch for 15 s,
      assert alive, clean kill; artifacts uploaded per OS. The runner floors
      come from B1: `ubuntu-24.04` or newer (glibc ≥ 2.34 x86_64, 2.39 arm64)
      and a macOS 13+ runner, or PySide6 6.11 has no wheel to install.
      Files: `.github/workflows/ci.yml`, `.github/workflows/release.yml` · **M**

## Phase G — one build script (`packaging`, portable-first scope)

- [ ] **G1. `release/build.py`** — the `build.bat:47-189` logic ported: PyInstaller
      with the same `--hidden-import`/`--collect-all` set plus `keyring`
      (submodules + metadata), OS-correct `--add-data` separator, ffmpeg and
      Chromium staging from the right cache per OS, portable folder assembly
      without `robocopy`/`xcopy`/`attrib`. Inno Setup stays Windows-only.
      Acceptance: `build.bat` becomes a thin wrapper and the Windows artifact is
      unchanged file-for-file. Files: `release/build.py` (new), `release/build.bat`,
      `release/README.md` · **L**
- [ ] **G2. Verify the Windows artifact did not move** — rebuild and compare
      against published 2.10.0 (251,752,029 bytes) + bundle contents + a 40 s
      offscreen frozen run. Acceptance: no unexplained delta. Files: none · **S**
- [ ] **G3. `release.yml` three archives** — tag builds and uploads a portable
      archive per OS, notes state the platform support honestly.
      Files: `.github/workflows/release.yml` · **M**
- [ ] **G4. File the deferred scope as issues** — native `.AppImage`/`.deb`/`.dmg`,
      signing + notarisation, each with the reason it was cut. Cross-linked to
      this plan. Files: GitHub issues · **XS**

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

### Checkpoint: done
- [ ] Full matrix green twice, three archives published, no orphan processes,
      README claims only what CI proves, glass-UI work unblocked.
