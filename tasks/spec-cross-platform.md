# Spec: Cross-Platform Support (Linux + macOS)

**Approved decisions (2026-11-03):** keyring for POSIX secret storage · portable
folders first, native installers filed as an issue · CI proves 3.12 + 3.14 and
only that is claimed · this initiative runs **before** the glass-UI restyle
(`tasks/design-brief-glass-ui.md`).

Capability map: `tasks/capability-map-cross-platform.md` (approved).

## Objective

Make the claim in README:7 and README:65 true — or remove it. A user on Ubuntu
or macOS can install the app's dependencies, start it, download video and audio,
run Social Discovery, and store an API key without that key landing on disk in
plain text. Windows behaviour, the shipped installer and the existing stored
keys must not regress by one byte.

User stories:

- As a Linux user I download a portable archive, run it, and the app works.
- As a macOS user I paste my Groq key once and it is in my Keychain, not in a
  SQLite row.
- As a maintainer I see CI run the whole suite on three OSes, so "supported" is
  a fact and not a hope.

## Tech Stack

Python 3.12 + 3.14 · PySide6 6.11 · yt-dlp · curl_cffi 0.15 · Playwright ·
instaloader · mutagen · SpotipyFree · **keyring (new, runtime, macOS/Linux
secrets only)** · PyInstaller onedir · GitHub Actions matrix.

## Commands

```powershell
# offline suite (the repo's own command, Windows)
QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests -q -m "not live"
./source/venv/Scripts/python.exe -m ruff check src tests
# the live network tests, only when deliberately run
QT_QPA_PLATFORM=offscreen ./source/venv/Scripts/python.exe -m pytest tests/test_music_live.py -q -m live
# Linux/mac equivalents for CI
pip install -r requirements.txt -r requirements-dev.txt
sudo apt-get install -y ffmpeg qt6-base-dev libx11-xcb1 libgl1   # linux runtime libs for Qt
brew install ffmpeg                                              # macos
python -m pip_audit -r requirements.txt
```

## Project Structure

```
src/s_q_ali_media_downloader/
  core/settings_store.py   → the seal/unseal backends (DPAPI · keyring · warned plaintext)
  engine.py                → find_ffmpeg(), app_storage_dir()
  agent/tools/browser.py   → playwright cache roots, channel list, sandbox flag
  ui/settings_page.py      → OS-aware wording for the key store
release/build.py           → new: one cross-platform build script (build.bat keeps calling it,
                             so the Windows path is unchanged in behaviour)
.github/workflows/ci.yml   → OS × Python matrix
tests/                     → per-OS branch coverage, POSIX-safe teardown
```

## Code Style

Backends are chosen by one small table, not by scattered `sys.platform` checks,
so the next OS is a row and not a hunt:

```python
def _seal(value: str) -> str:
    backend = _secret_backend()          # one decision, cached, testable
    if backend == "dpapi":
        return SEAL_DPAPI + b64(_dpapi_protect(value.encode(), protect=True))
    if backend == "keyring":
        _keyring_store(backend_service(), value)   # the DB keeps a label, never the secret
        return SEAL_KEYRING + backend_service()
    # No secret store on this machine: store it, mark it, and say so.
    logger.warning("no secret store on this platform — the key is saved unencrypted")
    return SEAL_PLAIN + value
```

Naming keeps the existing `SEAL_*` prefix style; every prefix is one constant at
the top of the module; no secret is ever interpolated into a log line, an
exception message or a URL (standing project invariant).

## Testing strategy

`pytest`, markers `live` / default offline, `QT_QPA_PLATFORM=offscreen`.

- **Unit** — `tests/test_core_storage_secrets.py`: a fake keyring backend is
  injected; assert (a) nothing plaintext reaches the SQLite row when keyring
  works, (b) `SEAL_PLAIN` + a surfaced warning when the backend raises
  `InitError`, (c) a `dpapi1:` row still round-trips on Windows, (d) `caplog`
  never contains the secret.
- **Unit** — the darwin/linux branches of `browser_executable()` and
  `_playwright_browser_roots()`, which no test covers today; monkeypatched
  `sys.platform`, no real browser.
- **Integration** — the whole offline suite on ubuntu + macos + windows in CI,
  at 3.12 and 3.14.
- **Artifact** — the existing per-OS portable build + a smoke launch on each OS
  (alive after 15 s, clean kill, no orphan process).

## Boundaries

- **Always** — offline suite and `ruff` before every commit; `graphify update .`
  after code changes; the Windows build and installer stay green at every step;
  never log a secret.
- **Ask first** — any further dependency; any change to the stored key format;
  any push, tag or release; changing `dpapi1:` or the existing entropy constant
  (that would silently orphan every user's keys).
- **Never** — delete or weaken a test to make another OS pass; store a key when
  the user was not told it was unencrypted; claim an OS in the README that CI
  does not run.

## Success criteria

1. `pytest -m "not live"` green on ubuntu-latest, macos-latest and
   windows-latest at 3.12 and 3.14 in a single CI run.
2. On macOS, a key written by Settings is retrievable from the Keychain and the
   SQLite row holds no secret; on a headless Linux runner with no secret
   service, the user is told the key is stored unencrypted — never silently.
3. A per-OS portable archive exists in the release, built by one script.
4. README/SECURITY/CONTRIBUTING describe exactly the above, with the false
   claims gone (the interim honesty patch ships first, before any of this).

## Open questions

1. Linux CI needs Qt runtime libs — if the offscreen plugin still fails on the
   runner, do we install `libxcb*`/`qt6-base-dev` (plan A) or keep Linux tests
   non-blocking for one release (plan B)? Decided by the first CI run.
2. macOS Keychain access from a GitHub runner: the default login keychain is
   unlocked there, but if a prompt blocks the job, the keyring test degrades to
   a fake-backend unit test and the real round-trip becomes a manual step.
3. ~~Do we keep `browser-use==0.13.14` exact-pinned on all three OSes, or move it
   to the `agent` extra only?~~ **Answered by the B1 spike:** the exact pin and
   all of its transitives resolve on manylinux, macOS arm64 and macOS x86_64, and
   `pywin32` is marker-gated to Windows. So it stays exact-pinned, in the `agent`
   extra and `requirements-dev.txt` only — never a runtime requirement.
   `pyproject.toml` now states the same pin as the requirements file, and
   `tests/test_requirements_agree.py` keeps them that way.
