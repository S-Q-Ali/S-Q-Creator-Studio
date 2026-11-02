# Implementation Plan: Cross-Platform Support

Spec: `tasks/spec-cross-platform.md` · Map: `tasks/capability-map-cross-platform.md`

## The dependency graph

```
docs-truth-interim (stop the false claim shipping)
        │
        ├── deps-proof (spike: do the wheels even resolve?)  ← highest risk, first
        │
        ├── secrets-portable ──┐
        ├── runtime-portable ──┼──→ test-portable ──→ ci-matrix ──→ packaging ──→ docs-truth
        └── (neutral strings) ─┘
```

Everything before `test-portable` can be built and verified on this Windows
machine; nothing after it can be claimed without a CI run. That is the honest
boundary of this plan: **the phase that proves the feature is the phase that
runs on someone else's hardware.**

## Phase order and why

| # | Phase | Scope | Why here |
|---|---|---|---|
| A | `docs-truth-interim` | README/SECURITY/CONTRIBUTING honesty patch, CHANGELOG 2.10.1, file the deferred-issue set | The published release is lying today; fix that before adding anything |
| B | `deps-proof` | A throwaway CI job (or local `pip download`) proving `requirements.txt` + `requirements-dev.txt` resolve **and import** on manylinux_2_28 x86_64, macOS arm64 + x86_64 at 3.12/3.14 | If `curl_cffi<0.16`, `PySide6<6.12` or `browser-use==0.13.14`'s pins do not resolve on one of those, the whole scope changes. Fail in day one, not in week two |
| C | `secrets-portable` | `settings_store` backend table: `dpapi1:` (untouched) · `keyring1:` · warned plaintext | Independent of everything else; security-critical, so early |
| D | `runtime-portable` | storage dirs via `QStandardPaths` (+ migration), `find_ffmpeg` POSIX binary, playwright cache roots, `msedge` gating, Chromium sandbox flag, OS-neutral strings | Same shape of work, no shared state with C |
| E | `test-portable` | per-OS font sourcing, POSIX-safe thread teardown (no `QThread.terminate()` reliance), autouse storage isolation, tests for the darwin/linux branches | Must precede CI, otherwise the matrix is red on arrival |
| F | `ci-matrix` | `ci.yml` OS × Python matrix, per-OS ffmpeg + chromium install, per-OS smoke launch, pip-audit | Now it can actually go green |
| G | `packaging` | `release/build.py` (one script, three OSes), per-OS portable archive, `release.yml` uploads three artifacts | Portable-first is the approved scope; `.AppImage`/`.dmg` filed as an issue |
| H | `docs-truth` | Per-OS install/run/build docs, corrected build recipe, keyring wording | Last, because it states what CI now proves |

Sequential: C→E→F→G→H share `settings_store.py`, `engine.py`, `ci.yml` and the
suite. Parallelisable: C and D are independent files and can be built in either
order or by two sessions.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **keyring finds no backend in a frozen build.** Its backends are discovered through entry points, which PyInstaller does not carry (jaraco/keyring#324: importing `keyring.backends.X` explicitly is the fix) | High — the feature works from source and fails in the shipped archive | Import the specific backend module at the top of the keyring branch, add `--collect-submodules keyring` + `--copy-metadata keyring` to the build, and assert the round-trip in the per-OS artifact smoke test — not only in a source-run unit test |
| A change to sealing invalidates a stored Windows key | High — every existing user silently loses their key | The win32 branch, the `dpapi1:` prefix and `_SEAL_ENTROPY` are untouched; a test reads a pre-baked `dpapi1:` row written before the change |
| The OS×Python matrix triples CI minutes and macOS runners are the expensive ones | Med | PRs run `windows + ubuntu` at one Python; `master` pushes and tags run the full matrix; concurrency cancels stale runs |
| Layout/QSS tests fail on POSIX because the font DB differs (`conftest.py:143` loads `%WINDIR%\Fonts`) | Med — the tempting wrong fix is to loosen the assertion | Phase E lands *before* Phase F; the failure is fixed by sourcing real per-OS fonts, never by weakening `test_ui_layout.py` |
| `QThread.terminate()` is a documented no-op on POSIX (`conftest.py:77`, `:192-197`) → hangs or leaks on the runners | Med | Replace with interruption + bounded wait; if a thread survives, fail the test loudly instead of killing it |
| `release/build.py` regressing the Windows artifact | High — the shipped product is Windows | `build.bat` stays as a thin wrapper; the new artifact is compared file-by-file and by size against the published 2.10.0 (251,752,029 bytes), per the standing "verify the shipped artifact" rule |
| Headless Linux has no Secret Service, so the keyring path is never exercised in CI | Low/med | That is the *fallback* branch, and it gets its own test; the keyring branch is covered by the macOS runner and by a fake backend unit test |
| A bundled Chromium on Linux needs system libs the runner lacks | Med | Phase B proves it; Phase F installs `qt6-base-dev`/`libxcb` only where a browser is actually launched — offline tests do not launch one |

## Verification checkpoints

**After A** — the published README no longer claims anything CI cannot show;
`2.10.1` docs commit sits clean on `master` (push/tag only on approval).

**After B–D** — offline suite green on Windows, `ruff` clean, `graphify update .`
run, a pre-baked `dpapi1:` row still decrypts, no plaintext key anywhere in the
DB when a store exists.

**After E–F** — the full matrix green on three OSes, twice (re-run to prove it
is not flaky), pip-audit gate still passing, no orphan processes left on the
runner.

**After G–H** — three per-OS archives in a draft release, each smoke-launched by
CI; the README's build recipe run verbatim on at least Linux by CI; docs claim
exactly what is in the release.

## What this plan deliberately does not do

- No `.AppImage`, `.deb` or `.dmg`, no code signing or notarisation — filed as a
  GitHub issue with the reason recorded.
- No macOS/Linux feature parity beyond what already works (e.g. reading Chrome's
  cookies from a browser profile behaves differently per OS — noted, not
  re-architected).
- No theme or layout work — that is `tasks/design-brief-glass-ui.md`, next.
- No change to the research-era database file name, which would orphan stored
  keys for no benefit.
