# Tasks: macOS Intel builds and disk images

Plan: `tasks/plan-macos-intel-and-dmg.md` · Spec: `tasks/spec-macos-intel-and-dmg.md`

## Task 1: the workflow's own tests

**Description:** `tests/test_release_workflow.py` reads the workflow YAML and
asserts what it must contain. It is the only test that runs before a release,
and it is what caught the v2.11.0 archive-naming defect. It grows to cover
the Intel cell, the two disk images and the deployment target.

**Acceptance criteria:**
- [ ] A test asserts the release matrix has a `macos-x64` cell and a
      `macos-15-intel` runner.
- [ ] A test asserts the publish step expects all seven file names.
- [ ] A test asserts `MACOSX_DEPLOYMENT_TARGET` is set to `13.0`.
- [ ] A test asserts the disk image step exists and is guarded to macOS.
- [ ] A test asserts `ci.yml` runs the suite on `macos-15-intel`.

**Verification:** `python -m pytest tests/test_release_workflow.py -q` — each
new test fails first, with a message naming what is missing.

**Dependencies:** none

**Files:** `tests/test_release_workflow.py` · **S**

## Task 2: the CI matrix runs the suite on Intel

**Description:** The release workflow builds and smoke-tests; it does not run
pytest. `ci.yml` is where the suite runs, so the Intel cell has to go there
for "the suite passes on macOS x86_64" to be a checked claim rather than an
assumption.

**Acceptance criteria:**
- [ ] A push to `master` runs `pytest -m "not live"` on `macos-15-intel` at
      Python 3.12 and 3.14.
- [ ] The build and smoke-test steps run there too, as they do on the other
      platforms.

**Verification:** the six-cell matrix becomes eight, and the two new cells
are green on the push.

**Dependencies:** Task 1

**Files:** `.github/workflows/ci.yml` · **XS**

## Task 3: the release workflow builds Intel and the disk images

**Description:** The build matrix gains the Intel cell; the macOS runners get
an explicit deployment target; a new step builds a `.dmg` from the staged
`.app`; the publish guard expects all seven files.

**Acceptance criteria:**
- [ ] The matrix has `macos-14 → macos-arm64` and `macos-15-intel →
      macos-x64`, both archiving as `tar.gz`.
- [ ] `MACOSX_DEPLOYMENT_TARGET` is `13.0` on the macOS build step, and the
      step reads `LSMinimumSystemVersion` back from the built bundle and
      fails when it is not 13.0.
- [ ] The disk image step creates `dist/S-Q-Creator-Studio-$version-macos-*.dmg`
      from the staged `.app`, with an `Applications` symlink inside, and it
      runs only on macOS.
- [ ] The publish step fails when any of the seven expected files is missing.
- [ ] The release notes table names the four Mac files.

**Verification:** `python -m pytest tests/test_release_workflow.py -q` green;
the tagged run publishes all seven assets.

**Dependencies:** Task 1

**Files:** `.github/workflows/release.yml` · **M**

## Task 4: the docs and the version

**Description:** The README's platform table gains the three new files, and
the sentence that says Intel Macs are untested goes away. The version moves
to 2.13.0 with a dated changelog heading, because a release is what ships
this.

**Acceptance criteria:**
- [ ] The README's table lists the Windows installer, the Windows zip, the
      Linux tar.gz and the four Mac files — seven rows that exist on the
      release.
- [ ] The "what CI proves" paragraph names the Intel runner and drops the
      claim that Intel Macs are untested.
- [ ] The macOS section says the `.dmg` drags into Applications, and that
      both files are unsigned until issue #15.
- [ ] `pyproject.toml`, `src/s_q_ali_media_downloader/__init__.py` and
      `CHANGELOG.md` say 2.13.0, with the heading dated.

**Verification:** every file name in the README appears in the release's
asset list.

**Dependencies:** Task 3

**Files:** `README.md`, `CHANGELOG.md`, `pyproject.toml`,
`src/s_q_ali_media_downloader/__init__.py` · **S**

## Task 5: publish, then close the macOS half of issue #14

**Description:** Tag `v2.13.0`, watch the run, and confirm the seven assets
with their names. Then update issue #14, whose macOS half this closes: the
Linux native packages (`.AppImage`, `.deb`) stay open.

**Acceptance criteria:**
- [ ] `v2.13.0` is published with all seven assets, correctly named.
- [ ] The macOS runner that built the Intel archive is an Intel runner.
- [ ] Issue #14 says the macOS `.dmg` is done and only the Linux packages
      remain.

**Verification:** `gh release view v2.13.0 --json assets`.

**Dependencies:** Task 4

**Files:** none in the repo · **XS**

## Checkpoint: after task 4

- [ ] `ruff check src tests` clean.
- [ ] The offline suite green.
- [ ] `graphify update .` refreshed and committed.

## Checkpoint: after task 5

- [ ] Seven assets, correct names, on the release.
- [ ] The suite green on macOS x86_64 in CI.
- [ ] The README claims nothing that is not on the release.
