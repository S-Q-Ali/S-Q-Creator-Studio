"""The ffmpeg the app can use, wherever this OS keeps it.

The portable bundle ships ffmpeg beside the app — `bin\\ffmpeg.exe` on
Windows, `bin/ffmpeg` on Linux and macOS — and PATH is the fallback for
anyone who installed it themselves.
"""

import os
import stat
import sys

import pytest

from s_q_ali_media_downloader import engine

WINDOWS_BINARY = "ffmpeg.exe"
POSIX_BINARY = "ffmpeg"
NATIVE_BINARY = WINDOWS_BINARY if os.name == "nt" else POSIX_BINARY


@pytest.fixture
def no_ffmpeg_on_path(monkeypatch, tmp_path):
    """An empty PATH, so only a bundled binary can be found."""
    nowhere = tmp_path / "empty-path"
    nowhere.mkdir()
    monkeypatch.setenv("PATH", str(nowhere))


@pytest.fixture
def running_from_source(monkeypatch, tmp_path):
    """Nothing beside the executable: the folder is only a fixture."""
    monkeypatch.setattr(
        sys, "argv", [str(tmp_path / "checkout" / "app.exe")], raising=False
    )


def _stage(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _bundle(tmp_path, monkeypatch, binary):
    """A bundle laid out like the portable release, with ffmpeg in bin/."""
    root = tmp_path / "S-Q-Creator-Studio"
    monkeypatch.setattr(sys, "argv", [str(root / "app.exe")], raising=False)
    return root, _stage(root / "bin" / binary)


@pytest.mark.parametrize(
    ("platform", "binary"),
    [("win32", WINDOWS_BINARY), ("linux", POSIX_BINARY), ("darwin", POSIX_BINARY)],
)
def test_the_bundled_ffmpeg_is_found(monkeypatch, no_ffmpeg_on_path, tmp_path, platform, binary):
    monkeypatch.setattr(sys, "platform", platform)
    root, staged = _bundle(tmp_path, monkeypatch, binary)

    assert engine.find_ffmpeg() == str(staged.parent)
    assert staged.parent == root / "bin"


def test_a_bundled_ffmpeg_beside_the_app_is_found(monkeypatch, no_ffmpeg_on_path, tmp_path):
    """The installer stages ffmpeg next to the app rather than in a bin folder."""
    monkeypatch.setattr(sys, "platform", "darwin")
    root = tmp_path / "S-Q-Creator-Studio"
    monkeypatch.setattr(sys, "argv", [str(root / "app.exe")], raising=False)
    staged = _stage(root / POSIX_BINARY)

    assert engine.find_ffmpeg() == str(staged.parent)


def test_an_ffmpeg_on_the_path_is_used(monkeypatch, running_from_source, tmp_path):
    tools = _stage(tmp_path / "tools" / NATIVE_BINARY).parent
    monkeypatch.setenv("PATH", str(tools))

    assert engine.find_ffmpeg() == str(tools)


def test_no_ffmpeg_anywhere_returns_none(monkeypatch, no_ffmpeg_on_path, running_from_source):
    monkeypatch.setattr(sys, "platform", "linux")
    assert engine.find_ffmpeg() is None


@pytest.fixture
def running_from_an_app_bundle(monkeypatch, tmp_path):
    """A frozen macOS run: Contents/MacOS holds the app, Contents/Resources the rest.

    PyInstaller builds an .app for --windowed on macOS and only the executable
    may sit in Contents/MacOS, so the extras the release stages there are not
    beside the launcher the way they are on the other two platforms.
    """
    contents = tmp_path / "S-Q Creator Studio.app" / "Contents"
    launcher = contents / "MacOS" / "S-Q Creator Studio"
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(launcher), raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    return contents


def test_a_macos_app_finds_its_ffmpeg_in_the_resources_folder(
    monkeypatch, no_ffmpeg_on_path, running_from_an_app_bundle
):
    contents = running_from_an_app_bundle
    staged = _stage(contents / "Resources" / "bin" / POSIX_BINARY)

    assert engine.find_ffmpeg() == str(staged.parent)


def test_the_app_bundle_roots_are_the_launcher_and_the_resources(
    running_from_an_app_bundle,
):
    contents = running_from_an_app_bundle

    assert engine.bundle_extra_roots() == [str(contents / "MacOS"), str(contents / "Resources")]


def test_a_folder_laid_out_like_windows_gets_one_root(monkeypatch, tmp_path):
    """The split is the bundle's, not the OS's - a plain folder gets plain treatment."""
    root = tmp_path / "portable"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(root / "S-Q Creator Studio.exe"), raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert engine.bundle_extra_roots() == [str(root)]

