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

WORKFLOW = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"
)

PLATFORM_KEYS = ("windows-x64", "linux-x64", "macos-arm64")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


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
    assert "windows-x64.zip" in text
    assert "linux-x64.tar.gz" in text
    assert "macos-arm64.tar.gz" in text
    assert "S-Q-Creator-Studio-Setup-$version.exe" in text


def test_publish_step_fails_when_a_platform_file_is_missing():
    assert "the release is missing" in _workflow()
