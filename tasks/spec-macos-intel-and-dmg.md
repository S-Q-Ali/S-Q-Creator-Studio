# Spec: macOS Intel builds and disk images

Status: **awaiting approval**

## Objective

An Intel Mac user should be able to download the app and run it, and a Mac
user of either chip should get a `.dmg` they can drag into Applications —
the way software arrives on that platform.

Today the release ships `S-Q-Creator-Studio-2.12.0-macos-arm64.tar.gz`: an
Apple Silicon build in a portable archive. It does not run on an Intel Mac,
because Rosetta 2 translates x86 to arm and not the other way round, so the
Intel user has nothing to download at all.

Success looks like:

- A `macos-x64` build, published, built and smoke-tested on an Intel runner.
- A `.dmg` for each Mac architecture, alongside the portable archive.
- The README and the release notes naming exactly those files.

## Commands

```
Build:  python release/build.py
Test:   QT_QPA_PLATFORM=offscreen python -m pytest tests -m "not live" -q
Lint:   python -m ruff check src tests --output-format concise
Graph:  graphify update .
Release: git tag -a v2.13.0 -m "2.13.0" && git push origin v2.13.0
```

## Project Structure

```
.github/workflows/release.yml   the build matrix, the archive step, the publish guard
.github/workflows/ci.yml        the test matrix — the suite runs here, not in the release
release/build.py                one build script for all platforms (unchanged)
tests/test_release_workflow.py  the workflow's own regression tests
README.md                       the platform table and the "what CI proves" paragraph
```

## The two facts this rests on

**The dependencies already resolve on Intel.** The B1 wheel spike
(`tasks/spike_platform_wheels.json`) resolved the full requirement set on
**macOS x86_64 at Python 3.12 and 3.14** — 153 packages, PySide6 6.11.3,
Playwright 1.64.1, browser-use 0.13.14 and yt-dlp 2026.10.26 among them.
Nothing about the dependency set blocks an Intel build.

**GitHub's Intel images are running out.** `macos-15-intel` is the last x86_64
image GitHub offers, and it retires in **Fall 2027**. After that, an Intel
build needs a self-hosted runner. This work is worth doing now; it is not
worth building a self-hosted runner for now.

## Tech Stack

GitHub Actions, PowerShell (`shell: pwsh`) on every runner, `hdiutil` for the
disk image, `ditto` to stage the bundle.

## Code Style

The workflow already reads its platform from the matrix and never hardcodes a
path per OS. The new work follows that:

```yaml
# .github/workflows/release.yml
- os: macos-15-intel
  key: macos-x64
  archive: tar.gz
```

```powershell
# The disk image is macOS's own tool - hdiutil - and ditto is what copies a
# .app without breaking the symlinks inside its frameworks.
ditto "$app" "$root/S-Q Creator Studio.app"
New-Item -ItemType SymbolicLink -Path "$root/Applications" -Target "/Applications"
hdiutil create -volname "S-Q Creator Studio" -srcfolder $root -ov -format UDZO "dist/$name.dmg"
```

## Testing Strategy

- **The workflow's own tests** — `tests/test_release_workflow.py` reads the
  YAML and asserts the matrix keys, the expected asset names and the guard.
  Every new asset name and every new matrix key gets an assertion.
- **The suite on the new runner** — `ci.yml` gains the Intel cell, so
  `pytest -m "not live"` runs on macOS x86_64 rather than the claim resting
  on a build that nobody ran the tests on.
- **The built app** — the release workflow's smoke test launches the frozen
  app on each runner and fails if it exits early. It runs on the Intel cell
  too.
- **The deployment target** — the app claims macOS 13+. A binary built on
  macOS 15 without `MACOSX_DEPLOYMENT_TARGET` declares `minos 15` and refuses
  to start on macOS 13 or 14. The build step must set the target to `13.0`,
  and the workflow must read the built bundle back and fail when
  `LSMinimumSystemVersion` is not `13.0`.

## Boundaries

- **Always:** run the suite before committing; keep the README's platform
  table equal to the files the release actually publishes; never claim a
  platform CI has not run on.
- **Ask first:** publishing a release; writing to the public tracker;
  changing the CI matrix size.
- **Never:** remove the `tar.gz` archives — a published download link must
  keep working; sign or notarise anything here (issue #15 owns that).

## Success Criteria

- [ ] `ci.yml` runs the offline suite on `macos-15-intel` at 3.12 and 3.14.
- [ ] The release workflow builds, smoke-tests and publishes
      `S-Q-Creator-Studio-2.13.0-macos-x64.tar.gz`.
- [ ] It publishes `S-Q-Creator-Studio-2.13.0-macos-arm64.dmg` and
      `S-Q-Creator-Studio-2.13.0-macos-x64.dmg`.
- [ ] The publish step refuses to release when any of the seven files is
      missing.
- [ ] The built `.app` reports `LSMinimumSystemVersion` 13.0 on both Mac
      runners, so "macOS 13+" is true.
- [ ] The README lists every published file, and the sentence about Intel
      Macs being untested is gone.

## Open Questions

- **Size.** The macOS archives are ~750 MB each because the bundle carries
  its own Chromium. Adding a `.dmg` beside the `.tar.gz` publishes about
  1.5 GB per architecture. A DMG that is compressed-but-barely-compressible
  is close to the size of the tar it duplicates. Accepted: the user asked for
  both, and GitHub's per-asset limit is 2 GB.
- **Signing.** Both files stay unsigned until issue #15 lands, so Gatekeeper
  still asks the user to approve the app once. Recorded in the README.
