"""The release workflow, checked without running a release.

The workflow builds one archive per platform and publishes them as one
GitHub Release. Nothing in CI runs that publish step on a pull request, so a
naming mistake in it stays invisible until a tag is cut - and a bad name
does not fail the job, it ships two platforms under one file name and
publishes a release that looks complete.

These tests read the workflow and check the two things that decide what the
release actually contains: the name each archive is given, and the list of
files the publish step insists on finding.
"""

from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "release.yml"
CI_WORKFLOW = WORKFLOWS / "ci.yml"

PLATFORM_KEYS = ("windows-x64", "linux-x64", "macos-arm64", "macos-x64")

#: Every file a release has to carry. The publish step refuses to release
#: when one of them is missing, so this list is the release's contract.
PUBLISHED_FILES = (
    "S-Q-Creator-Studio-Setup-$version.exe",
    "S-Q-Creator-Studio-$version-windows-x64.zip",
    "S-Q-Creator-Studio-$version-linux-x64.tar.gz",
    "S-Q-Creator-Studio-$version-macos-arm64.tar.gz",
    "S-Q-Creator-Studio-$version-macos-arm64.dmg",
    "S-Q-Creator-Studio-$version-macos-x64.tar.gz",
    "S-Q-Creator-Studio-$version-macos-x64.dmg",
)


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _matrix_cells(text: str) -> list[str]:
    """The build matrix's ``include:`` entries, as text blocks."""
    start = text.index("include:")
    end = text.index("runs-on:", start)
    return text[start:end].split("- os:")[1:]


def test_workflow_defines_one_key_per_platform():
    text = _workflow()
    for key in PLATFORM_KEYS:
        assert f"key: {key}" in text, f"{key} is not in the build matrix"


def test_archive_name_reads_the_platform_key_from_the_environment():
    # PowerShell only reads an environment variable as $env:NAME. A bare
    # $NAME is a different variable that is always empty, which named every
    # archive "S-Q-Creator-Studio-<version>-.tar.gz".
    text = _workflow()
    assert "$env:BUILD_KEY" in text
    assert "$BUILD_KEY" not in text.replace("$env:BUILD_KEY", "")


def test_archive_name_is_guarded_against_an_empty_key():
    assert "the archive would be unnamed" in _workflow()


def test_publish_step_expects_every_platform_file():
    text = _workflow()
    for name in PUBLISHED_FILES:
        assert name in text, f"the publish step does not expect {name}"


def test_publish_step_fails_when_a_platform_file_is_missing():
    assert "the release is missing" in _workflow()


def test_each_mac_architecture_is_built_on_a_matching_runner():
    # An Apple Silicon build does not run on an Intel Mac, and Rosetta 2
    # translates x86 to arm and not the other way round. So the two
    # architectures need two runners: an arm one and an Intel one.
    cells = _matrix_cells(_workflow())
    arm = [cell for cell in cells if "key: macos-arm64" in cell]
    intel = [cell for cell in cells if "key: macos-x64" in cell]
    assert arm, "no macos-arm64 cell in the build matrix"
    assert intel, "no macos-x64 cell in the build matrix"
    assert arm[0].strip().startswith("macos-14")
    assert intel[0].strip().startswith("macos-15-intel")


def test_the_macos_build_sets_a_deployment_target():
    # The floor a macOS build promises is the build script's business, not
    # the workflow's - see test_release_build_script.py. The workflow only
    # has to say which runner builds which architecture.
    assert "MACOSX_DEPLOYMENT_TARGET" not in _workflow()


def test_the_disk_image_is_published_next_to_the_archive():
    # The build script writes the disk image; the workflow picks it up and
    # publishes it under the same name the publish step insists on.
    text = _workflow()
    assert "the build left no disk image" in text
    assert 'dist/$name.dmg' in text


def test_the_browser_and_ffmpeg_are_looked_for_inside_the_macos_bundle():
    """On macOS the app is a bundle: Apple allows only the executable in
    Contents/MacOS, so the shipped browser and ffmpeg live in Resources.
    A check that looks beside the launcher would pass on a build that
    shipped neither."""
    text = _workflow()

    assert "Contents/Resources" in text
    assert '"$extras/browsers"' in text
    assert '"$extras/bin/ffmpeg"' in text


def test_the_suite_runs_on_the_intel_mac():
    # The release workflow builds and smoke-tests; it does not run pytest.
    # CI does, so an Intel claim that nobody ran the tests on would be an
    # assumption.
    assert "macos-15-intel" in CI_WORKFLOW.read_text(encoding="utf-8")
