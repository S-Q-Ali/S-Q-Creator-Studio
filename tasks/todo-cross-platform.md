# Task List: Cross-Platform Support

Plan: `tasks/plan-cross-platform.md` · Spec: `tasks/spec-cross-platform.md`

Tasks are ordered by dependency. Sizes: XS = 1 file, S = 1–2, M = 3–5.

## Phase A — stop the false claim shipping (`docs-truth-interim`)

- [ ] **A1. Honest platform + security wording** — README:7 badge, README:65,
      README:137, README:73, README:82 + :6, README:107-113 recipe,
      README:149 browser-use wording; SECURITY.md:49; CONTRIBUTING.md:49.
      Acceptance: no claim survives that CI does not currently prove; Windows
      stays the stated platform; "Linux/macOS: not yet tested, help wanted".
      Verify: `grep` for the removed strings; diff reviewed line by line.
      Files: `README.md`, `SECURITY.md`, `CONTRIBUTING.md` · **S**
- [ ] **A2. CHANGELOG 2.10.1 + commit** — docs-only entry under Fixed; no
      version bump of the package itself unless we ship it.
      Acceptance: dated heading, phrased as user impact, not internal mechanics.
      Verify: `git diff --stat` shows docs only. Files: `CHANGELOG.md` · **XS**

## Phase B — prove the dependencies resolve (`deps-proof`)

- [ ] **B1. Wheel + import proof spike** — one throwaway CI job (or a local
      `pip download` per target) resolving `requirements.txt` and
      `requirements-dev.txt` on manylinux x86_64, macOS arm64, macOS x86_64,
      Python 3.12 and 3.14, then importing every runtime module.
      Acceptance: a written result table in `tasks/` naming what resolves, what
      does not, and whether `browser-use==0.13.14`'s pins survive.
      Verify: the job runs green or produces the failure list. Files: a scratch
      workflow or `tasks/spike_platform_wheels.py` · **M**
- [ ] **B2. Decide `browser-use` placement** — runtime pin vs the `agent` extra,
      per B1's result; reconcile the pin drift already found
      (`requirements-dev.txt:15` exact vs `pyproject.toml:59-61` range) and the
      curl_cffi range contradicting `CONTRIBUTING.md:55-57`.
      Acceptance: one source of truth per dependency. Files: `requirements.txt`,
      `requirements-dev.txt`, `pyproject.toml`, `CONTRIBUTING.md` · **S**

## Phase C — secrets on every OS (`secrets-portable`)

- [ ] **C1. Failing tests for the three backends** — fake keyring injected;
      asserts no plaintext in the row when keyring works, `plain` marker +
      warning when the backend raises, `dpapi1:` round-trip on Windows, and
      `caplog` never contains the key. Acceptance: red before the code exists.
      Files: `tests/test_core_storage_secrets.py` (new) · **S**
- [ ] **C2. Backend table in `settings_store`** — `_secret_backend()`,
      `SEAL_DPAPI` / `SEAL_KEYRING` / `SEAL_PLAIN`, explicit
      `keyring.backends.macOS` / `SecretService` imports (frozen-safe), re-seal a
      `plain` row once a store appears. Acceptance: Windows branch byte-identical
      in behaviour. Files: `core/settings_store.py`, `requirements.txt`,
      `pyproject.toml` · **M**
- [ ] **C3. OS-aware Settings wording** — the unreadable-key message
      (`settings_page.py:480`) and a one-line note on how the key is stored here.
      Acceptance: no sentence says "Windows" on macOS; an unencrypted save is
      stated in the panel, not only the log. Files: `ui/settings_page.py` · **S**

## Phase D — runtime portability (`runtime-portable`)

- [ ] **D1. Storage dirs** — `app_storage_dir()` (`engine.py:208-218`) and
      `db_path()` (`settings_store.py:117`) onto `QStandardPaths`, Windows path
      byte-identical, `SQ_DB_PATH`/`LOCALAPPDATA` overrides still honoured,
      migrate a POSIX `~/S-Q Ali…` folder if it exists. Acceptance: the log dir
      and the data dir stop disagreeing (`app.py:49-50`).
      Files: `engine.py`, `core/settings_store.py`, `tests/test_engine_paths.py` · **M**
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
      assert alive, clean kill; artifacts uploaded per OS.
      Files: `.github/workflows/ci.yml` · **M**

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
      Python "3.12 and 3.14 tested", keyring/DPAPI statement, CONTRIBUTING setup
      blocks, SECURITY per-OS storage table, issue-template OS line.
      Acceptance: every claim maps to a CI job or an artifact that exists.
      Files: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `release/README.md`,
      `.github/ISSUE_TEMPLATE/bug_report.md` · **M**
- [ ] **H2. CHANGELOG + version bump** — the release that first claims three OSes.
      Verify: dated heading before any tag, per the standing rule.
      Files: `CHANGELOG.md`, `__init__.py`, `pyproject.toml` · **XS**

### Checkpoint: done
- [ ] Full matrix green twice, three archives published, no orphan processes,
      README claims only what CI proves, glass-UI work unblocked.
