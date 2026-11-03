"""The release build script, tested without running a build.

A PyInstaller run takes minutes and writes 250 MB, so these tests cover the
decisions the script makes - the flags it passes, the ffmpeg and browser it
stages, the folder it builds into - and leave the build itself to the release
workflow, which runs it on all three OSes.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

RELEASE_DIR = Path(__file__).resolve().parent.parent / "release"


def _load_build_script():
    """``release/build.py`` as a module. It is not an importable package."""
    spec = importlib.util.spec_from_file_location("release_build", RELEASE_DIR / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _load_build_script()

#: The packages the Windows build has collected since before this script
#: existed. Each is reached through a string, an optional extra or a plugin
#: hook, so PyInstaller's import graph does not see it and an app missing one
#: fails at run time rather than at build time.
EXPECTED_COLLECT_ALL = {
    "pydantic",
    "pydantic_core",
    "annotated_types",
    "typing_extensions",
    "typing_inspection",
    "httpx",
    "yt_dlp",
    "curl_cffi",
    "playwright",
    "instaloader",
    "browser_use",
    "browser_harness",
    "cdp_use",
    "mutagen",
    "SpotipyFree",
    "spotapi",
}


# --------------------------------------------------------------------------- #
# The PyInstaller command line
# --------------------------------------------------------------------------- #
def test_every_package_the_build_has_always_collected_is_still_collected():
    flags = {a.split("=", 1)[1] for a in build.pyinstaller_args() if a.startswith("--collect-all=")}

    assert flags == EXPECTED_COLLECT_ALL


def test_the_entry_point_icon_and_names_the_installer_expect_are_passed():
    args = build.pyinstaller_args()

    assert args[args.index("--name") + 1] == build.APP_NAME
    assert args[args.index("--icon") + 1] == str(build.ICON)
    assert args[-1] == str(build.ENTRY)
    assert "--windowed" in args and "--onedir" in args
    assert "--clean" in args and "--noconfirm" in args


def test_add_data_uses_the_separator_of_the_os_building():
    """Windows separates with ';' and everything else with ':'."""
    value = build.pyinstaller_args()[build.pyinstaller_args().index("--add-data") + 1]

    assert value.endswith(f"{os.pathsep}.")
    assert value.count(os.pathsep) == 1


def test_keyring_travels_only_where_it_is_installed(monkeypatch):
    """The keychain backends are chosen by name at run time.

    Without them the app builds fine and then finds no secret store on the
    user's machine. Windows is the case the other way round: keyring is not
    installed there at all, and asking PyInstaller to collect what is not
    there is how a build fails for a reason nothing explains.
    """
    real = importlib.util.find_spec

    monkeypatch.setattr(build.importlib.util, "find_spec", lambda name: real(name))
    with_keyring = "--collect-submodules=keyring" in build.pyinstaller_args()

    monkeypatch.setattr(build.importlib.util, "find_spec", lambda name: None)
    without_keyring = build.pyinstaller_args()

    assert with_keyring == (real("keyring") is not None)
    assert "--collect-submodules=keyring" not in without_keyring
    assert "--copy-metadata=keyring" not in without_keyring


def test_the_version_the_installer_is_named_for_is_the_one_the_app_reports():
    import s_q_ali_media_downloader

    assert build.app_version() == s_q_ali_media_downloader.__version__


# --------------------------------------------------------------------------- #
# ffmpeg
# --------------------------------------------------------------------------- #
@pytest.fixture
def no_ffmpeg_anywhere(monkeypatch, tmp_path):
    monkeypatch.delenv("FFMPEG_EXE", raising=False)
    monkeypatch.setattr(build.shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "no-appdata"))


def test_the_callers_ffmpeg_wins(no_ffmpeg_anywhere, monkeypatch, tmp_path):
    chosen = tmp_path / "my-ffmpeg"
    chosen.write_text("ffmpeg")
    monkeypatch.setenv("FFMPEG_EXE", str(chosen))

    assert build.find_ffmpeg() == str(chosen)


def test_the_ffmpeg_on_the_path_is_found_by_its_native_name(no_ffmpeg_anywhere, monkeypatch):
    # The name the search asks for is the one this OS's file finder expects:
    # on Windows shutil.which honours PATHEXT, and asking it for "ffmpeg.exe"
    # there is what finds the file that is actually called ffmpeg.exe.
    asked = []

    def fake_which(name):
        asked.append(name)
        return f"/somewhere/bin/{name}"

    monkeypatch.setattr(build.shutil, "which", fake_which)

    assert build.find_ffmpeg() == f"/somewhere/bin/{build.FFMPEG_NAME}"
    assert asked == [build.FFMPEG_NAME]


def test_a_winget_ffmpeg_is_used_when_path_has_none(no_ffmpeg_anywhere, monkeypatch, tmp_path):
    monkeypatch.setattr(build, "IS_WINDOWS", True)
    staged = tmp_path / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_8.0"
    (staged / "bin").mkdir(parents=True)
    winget = staged / "bin" / "ffmpeg.exe"
    winget.write_text("ffmpeg")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert build.find_ffmpeg() == str(winget)


def test_no_ffmpeg_anywhere_is_reported_as_none(no_ffmpeg_anywhere):
    assert build.find_ffmpeg() is None


def test_staged_ffmpeg_keeps_the_name_and_the_bit_this_os_needs(monkeypatch, tmp_path):
    source = tmp_path / "ffmpeg-src"
    source.write_bytes(b"#!/bin/sh\n")
    portable = tmp_path / "portable"
    portable.mkdir()
    monkeypatch.setenv("FFMPEG_EXE", str(source))

    build.stage_ffmpeg(portable)

    staged = portable / "bin" / build.FFMPEG_NAME
    assert staged.is_file()
    if os.name != "nt":
        assert staged.stat().st_mode & 0o111, "a staged ffmpeg nobody can execute"


# --------------------------------------------------------------------------- #
# The browser that ships with the app
# --------------------------------------------------------------------------- #
@pytest.fixture
def browser_cache(tmp_path, monkeypatch):
    cache = tmp_path / "ms-playwright"
    full = cache / "chromium-1181"
    (full / "chrome-linux64").mkdir(parents=True)
    (full / "chrome-linux64" / "chrome").write_text("browser")
    shell = cache / "chromium_headless_shell-1181"
    shell.mkdir(parents=True)
    (shell / "headless_shell").write_text("not enough")
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr(build, "browser_cache_dir", lambda: cache)
    return cache


def test_only_the_full_chromium_is_shipped(browser_cache, tmp_path, capsys):
    portable = tmp_path / "portable"
    portable.mkdir()

    build.stage_browsers(portable)

    shipped = [p.name for p in (portable / "browsers").iterdir()]
    assert shipped == ["chromium-1181"]
    assert (portable / "browsers" / "chromium-1181" / "chrome-linux64" / "chrome").is_file()
    assert "Shipping browser: chromium-1181" in capsys.readouterr().out


def test_a_machine_with_no_browser_says_what_to_do_about_it(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr(build, "browser_cache_dir", lambda: tmp_path / "nowhere")
    portable = tmp_path / "portable"
    portable.mkdir()

    build.stage_browsers(portable)

    out = capsys.readouterr().out
    assert "No Playwright browser found" in out
    assert "playwright install chromium" in out
    assert not (portable / "browsers").exists()


def test_the_builders_browser_cache_is_the_apps_own_answer(tmp_path, monkeypatch):
    """One definition of where the browsers live, shared with the app.

    A build that looked in a different folder from the finished app would ship
    nothing and the app would not find it either.
    """
    from s_q_ali_media_downloader.agent.tools import browser as app_browser

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "linux", raising=False)

    assert build.browser_cache_dir() == tmp_path / ".cache" / "ms-playwright"
    assert build.browser_cache_dir() == app_browser._playwright_cache_dir()


# --------------------------------------------------------------------------- #
# Where the build lands
# --------------------------------------------------------------------------- #
def test_a_free_portable_folder_is_the_one_used(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "RELEASE", tmp_path)

    assert build.portable_dir() == tmp_path / "portable"


def test_a_locked_portable_folder_sends_the_build_to_a_fresh_one(tmp_path, monkeypatch, capsys):
    """The app is probably running: Windows will not delete its files."""
    monkeypatch.setattr(build, "RELEASE", tmp_path)
    monkeypatch.setattr(
        build, "is_clearable", lambda path: path.name != "portable"
    )  # "portable" is locked, "portable-new" is not

    assert build.portable_dir() == tmp_path / "portable-new"
    assert "portable-new" in capsys.readouterr().out


def test_a_build_with_nowhere_to_go_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "RELEASE", tmp_path)
    monkeypatch.setattr(build, "is_clearable", lambda path: False)

    with pytest.raises(SystemExit):
        build.portable_dir()


# --------------------------------------------------------------------------- #
# The installer stays Windows-only, and the batch file stays thin
# --------------------------------------------------------------------------- #
def test_inno_setup_is_only_looked_for_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "IS_WINDOWS", False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert build.inno_compiler() is None


def test_the_installer_build_is_skipped_out_loud_on_other_systems(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(build, "IS_WINDOWS", False)

    build.build_installer("9.9.9", "portable", None)

    assert "Skipping the installer" in capsys.readouterr().out


def test_the_windows_wrapper_starts_the_script_and_carries_its_exit_code():
    """One build script: a second copy of these steps in batch is how the
    three platforms end up building three different apps."""
    text = (RELEASE_DIR / "build.bat").read_text(encoding="utf-8").lower()

    assert "pyinstaller" not in text
    assert "robocopy" not in text and "xcopy" not in text and "attrib" not in text
    assert "build.py" in text
    assert "exit /b %rc%" in text
