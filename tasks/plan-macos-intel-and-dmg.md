# Implementation Plan: macOS Intel builds and disk images

## Overview

Two things are missing from the macOS side of the release: an Intel build
(nobody on an Intel Mac can run what is published today) and a `.dmg` (the
format a Mac user expects). The plan adds an Intel runner to both the test
matrix and the release matrix, builds a disk image on each Mac runner, and
makes the publish step demand all seven files.

## Architecture decisions

- **`macos-15-intel` for the Intel cell.** GitHub's last x86_64 image, and it
  retires in Fall 2027 — so this buys time rather than solving the platform
  forever. Recorded here so the end is not a surprise.
- **`MACOSX_DEPLOYMENT_TARGET=13.0` on both Mac runners.** The README claims
  macOS 13+, but nothing sets a deployment target today, so a build on macOS
  14 or 15 declares its own macOS version as the floor and would refuse to
  start on an older Mac. The target is set explicitly and the build reads
  `LSMinimumSystemVersion` back, so the claim is checked rather than hoped
  for.
- **The suite runs on the Intel runner, not only the build.** The release
  workflow builds and smoke-tests; it does not run pytest — `ci.yml` does.
  So the Intel cell goes into `ci.yml` as well, or "the suite passes on
  macOS x86_64" would be a claim nobody checked.
- **Both formats ship.** The `.tar.gz` stays and the `.dmg` is added. The
  portable archive is what CI already proves, and a published download link
  must keep working.
- **`hdiutil` and `ditto`, nothing else.** Both are macOS's own tools.
  `ditto` copies a `.app` without flattening the symlinks inside its
  frameworks, which `Copy-Item` would.
- **The publish guard grows from four names to seven.** The same guard that
  caught the v2.11.0 defect — three archives, one name, the Linux build
  overwritten — now covers the two new files.

## Task list

### Phase 1 — the tests that say what must be true

- [ ] Task 1: the workflow's own tests cover the Intel cell, the two disk
      images and the deployment target.
- [ ] Task 2: `ci.yml` runs the suite on `macos-15-intel`.

### Checkpoint: red

- [ ] The new tests fail against the current workflows, and the failure
      names the missing Intel cell and the missing `.dmg` files.

### Phase 3 — the release workflow

- [ ] Task 3: the `macos-x64` cell, the deployment target and the disk
      image step.

### Checkpoint: green

- [ ] The new tests pass; `ruff` clean; the offline suite green.

### Phase 4 — the docs and the version

- [ ] Task 4: the README's platform table and "what CI proves" paragraph, the
      release notes table, the version bump to 2.13.0.

### Phase 5 — the release

- [ ] Task 5: tag `v2.13.0`, watch the run, confirm seven assets with the
      right names, and close the macOS half of issue #14.

### Checkpoint: done

- [ ] Seven assets on the release, the Intel one built on an Intel runner,
      the suite green on macOS x86_64, the README claiming only that.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `macos-15-intel` retires Fall 2027 | The Intel build stops building | Recorded in the spec and the issue; a self-hosted runner is the later answer, and the portable `.tar.gz` keeps working for anyone who already has it |
| The app's floor is really macOS 14 or 15, not 13 | A user on macOS 13 cannot start it | `MACOSX_DEPLOYMENT_TARGET=13.0` plus a read-back of `LSMinimumSystemVersion`; if the build cannot honour it, the floor moves to what the build proves and the README says so |
| The `.dmg` is unsigned, so Gatekeeper refuses it | The user has to approve the app | Same as today's `.app`; issue #15 owns signing, and the README already says the app is unsigned |
| The `.dmg` is ~750 MB beside a ~750 MB `.tar.gz` | ~1.5 GB per architecture published | GitHub's per-asset limit is 2 GB, so it fits; recorded in the spec |
| The Intel runner is slower and the queue grows | CI takes longer | The Intel cell runs only on pushes to `master`, like the rest of the matrix |
| `ditto` is macOS-only | The disk image step cannot run on other runners | The step is guarded by `if: runner.os == 'macOS'` |

## Open questions

None open — the two decisions the user had to make (both formats per
architecture, and Intel and `.dmg` in one change) are recorded in the spec.
