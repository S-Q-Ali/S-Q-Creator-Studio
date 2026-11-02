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
