"""The release build, on the machine that runs it.

One directory build in ``build\\out``, copied into ``release\\portable`` ready for
the installer, with the browser and ffmpeg staged next to the app. The Windows
installer is compiled here too, because Inno Setup is a Windows program;
everywhere else the portable folder is the deliverable.

Run it from anywhere - every path below is worked out from this file, not from
the working directory.

    python release/build.py

The Python that runs it is the Python that builds: the project's virtualenv
when the build is started with it, CI's own interpreter otherwise.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "release"
APP_NAME = "S-Q Creator Studio"
ENTRY = Path("src") / "s_q_ali_media_downloader" / "__main__.py"
ICON = Path("src") / "s_q_ali_media_downloader" / "resources" / "icon.ico"
WORKPATH = ROOT / "build" / "pkg"
DISTPATH = ROOT / "build" / "out"

#: Modules PyInstaller cannot see from the import graph: they are reached
#: through a string, an optional extra or a plugin hook.
COLLECT_ALL = (
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
)
HIDDEN_IMPORTS = (
    "pydantic",
    "pydantic_core",
    "annotated_types",
    "typing_extensions",
    "typing_inspection",
    "httpx",
)

IS_WINDOWS = sys.platform == "win32"
FFMPEG_NAME = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"


def fail(message: str, *hints: str) -> None:
    """Stop the build, and make sure the reason is readable.

    A build started by double-clicking closes its window the moment it ends,
    so the window is held open - unless this is CI, where that would hang the
    job. The exit code is always non-zero: a release that failed must never
    look like one that succeeded.
    """
    print(f"\n[ERROR] {message}")
    for hint in hints:
        print(f"        {hint}")
    if not os.environ.get("GITHUB_ACTIONS") and IS_WINDOWS and sys.stdin.isatty():
        input("Press Enter to close... ")
    sys.exit(1)


def app_version() -> str:
    """The version the packaged app will report, read from the package itself.

    The installer's name and metadata come from the same place, so they cannot
    drift from the app.
    """
    sys.path.insert(0, str(ROOT / "src"))
    import s_q_ali_media_downloader

    return s_q_ali_media_downloader.__version__


def pyinstaller_args() -> list[str]:
    """The PyInstaller command line for this OS."""
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(ICON),
        # The separator between the two halves of --add-data is a semicolon on
        # Windows and a colon everywhere else. Getting it wrong builds an app
        # that quietly ships nothing.
        "--add-data",
        f"{ICON}{os.pathsep}.",
        "--paths",
        "src",
    ]
    args += [f"--hidden-import={name}" for name in HIDDEN_IMPORTS]
    for name in COLLECT_ALL:
        args.append(f"--collect-all={name}")
    # The API keys are sealed through keyring on Linux and macOS. Its backends
    # are chosen by name at run time, so the bundle needs every one of them and
    # the metadata that lets importlib find them. Windows seals with DPAPI and
    # does not install keyring at all, so this only appears where it is there.
    if importlib.util.find_spec("keyring") is not None:
        args += ["--collect-submodules=keyring", "--copy-metadata=keyring"]
    args += ["--workpath", str(WORKPATH), "--distpath", str(DISTPATH), str(ENTRY)]
    return args


def build_with_pyinstaller() -> Path:
    print(f"\n{'=' * 60}\n Building with PyInstaller (one directory)\n{'=' * 60}\n")
    result = subprocess.run(pyinstaller_args(), cwd=ROOT, check=False)
    if result.returncode != 0:
        fail(f"PyInstaller build failed with code {result.returncode}.")
    built = DISTPATH / APP_NAME
    if not built.is_dir():
        fail(f"PyInstaller left no build in {built}.")
    return built


def is_clearable(path: Path) -> bool:
    """Whether this folder can be emptied - or is already gone.

    Read-only files refuse to go on Windows, and a virus scanner can hold a
    lock for a moment, so the attributes are cleared and the removal retried.
    The browser folder alone is around 1500 files.
    """
    for _ in range(20):
        if not path.exists():
            return True
        for found in path.rglob("*"):
            try:
                found.chmod(0o700)
            except OSError:
                pass
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return True
        time.sleep(0.3)
    return not path.exists()


def portable_dir() -> Path:
    """The staging folder: ``portable``, or ``portable-new`` when it is locked.

    Windows will not delete or even rename the files of a running copy of the
    app, so the build goes into a fresh folder and the installer is told to
    read from there. The app that is running keeps its own files.
    """
    target = RELEASE / "portable"
    if is_clearable(target):
        target.mkdir(parents=True, exist_ok=True)
        return target
    print("          The old build is in use - the app is probably running.")
    fresh = RELEASE / "portable-new"
    print(f"          Building into {fresh} instead.")
    if not is_clearable(fresh):
        fail(
            f'Could not remove "{fresh}" either.',
            "Close the app and run this script again.",
        )
    fresh.mkdir(parents=True, exist_ok=True)
    return fresh


def stage_contents(built: Path, portable: Path) -> None:
    print(f"\n{'=' * 60}\n Copying to {portable}\n{'=' * 60}\n")
    try:
        shutil.copytree(built, portable, dirs_exist_ok=True)
    except OSError as exc:
        fail(f"Failed to copy the build to {portable}: {exc}")


def find_ffmpeg() -> str | None:
    """The ffmpeg to ship: the caller's, then the one on the PATH, then winget's.

    It goes next to the app because "Best available" downloads video and audio
    as separate streams, and yt-dlp needs ffmpeg to merge them; without it the
    portable build fails on every YouTube download.

    This is the *build machine's* ffmpeg, so it is looked for where a machine
    keeps one - not with the app's own search, which starts from the bundle the
    finished app is standing in.
    """
    if os.environ.get("FFMPEG_EXE"):
        return os.environ["FFMPEG_EXE"]
    found = shutil.which(FFMPEG_NAME)
    if found:
        return found
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            # The winget install of Gyan.FFmpeg, which is what a developer
            # machine that never touched PATH usually has.
            packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
            for candidate in sorted(packages.glob("Gyan.FFmpeg_*/bin/ffmpeg.exe")):
                return str(candidate)
    return None


def stage_ffmpeg(portable: Path) -> str | None:
    """Copy ffmpeg into ``bin`` and say where it came from."""
    source = find_ffmpeg()
    if not source:
        print(
            f"[WARNING] {FFMPEG_NAME} not found.\n"
            f"          The portable build cannot merge video+audio until ffmpeg\n"
            f"          is copied to {portable / 'bin'} by hand."
        )
        return None
    (portable / "bin").mkdir(parents=True, exist_ok=True)
    target = portable / "bin" / FFMPEG_NAME
    shutil.copy2(source, target)
    target.chmod(target.stat().st_mode | 0o755)
    print(f"{FFMPEG_NAME} staged into {portable / 'bin'}\n  from {Path(source).resolve()}")
    return source


def browser_cache_dir() -> Path | None:
    """Where Playwright keeps the browsers it downloaded on this OS.

    The app's own resolver is the one definition of this; a build that looked
    in a different place would ship no browser.
    """
    from s_q_ali_media_downloader.agent.tools.browser import _playwright_cache_dir

    return _playwright_cache_dir()


def stage_browsers(portable: Path) -> None:
    """Copy the full Chromium build into the portable folder.

    The Social Discovery feature drives a real browser and the app ships one,
    so the feature works on a machine with no Chrome and no Edge. The headless
    shell is not enough: Playwright needs the full build for channel="chromium".
    """
    cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or browser_cache_dir() or ".")
    if not cache.is_dir():
        print(
            f"[WARNING] No Playwright browser found in {cache}.\n"
            "          The Social Discovery feature will use the browser this\n"
            "          machine has, or report that it needs\n"
            "          'playwright install chromium'."
        )
        return
    shipped = 0
    for found in sorted(cache.glob("chromium-*")):
        # chromium-1181 and friends; chromium_headless_shell-* is the shell.
        version = found.name.removeprefix("chromium-")
        if not version[:1].isdigit():
            continue
        print(f"Shipping browser: {found.name}")
        shutil.copytree(found, portable / "browsers" / found.name, dirs_exist_ok=True)
        shipped += 1
    if not shipped:
        print(
            f"[WARNING] {cache} has no Chromium build to ship.\n"
            "          Run 'python -m playwright install chromium' and build again."
        )


def inno_compiler() -> Path | None:
    """The Inno Setup compiler on this machine, if it has one."""
    if not IS_WINDOWS:
        return None
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(key)
        if base:
            candidates.append(Path(base) / "Inno Setup 6" / "ISCC.exe")
    return next((c for c in candidates if c.is_file()), None)


def build_installer(version: str, app_source: str, ffmpeg_source: str | None) -> None:
    """Compile the Windows installer, when this machine can."""
    iscc = inno_compiler()
    if iscc is None:
        print(
            "[WARNING] Inno Setup was not found on this machine.\n"
            "          Skipping the installer. The portable build is complete."
        )
        return

    print(f"\n{'=' * 60}\n Building the installer\n{'=' * 60}\n")
    staging = RELEASE / "staging" / "bin"
    staging.mkdir(parents=True, exist_ok=True)
    if ffmpeg_source:
        shutil.copy2(ffmpeg_source, staging / "ffmpeg.exe")
        print("ffmpeg.exe staged for installer.")
    else:
        print(
            "[WARNING] ffmpeg.exe not found.\n"
            f"          Installer will build without ffmpeg - copy it manually to {staging} first."
        )

    # Compile into a clean folder instead of release\. An Explorer window left
    # open on release\ - or antivirus scanning the new 200 MB Setup.exe - can
    # hold the file open while Inno updates its icon and version resources,
    # which fails with "EndUpdateResource failed (110)". The finished file is
    # moved into release\ after the compile.
    out_dir = ROOT / "build" / "installer"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_name = f"S-Q-Creator-Studio-Setup-{version}.exe"
    final = RELEASE / setup_name

    print("Running Inno Setup compiler...")
    for attempt in range(1, 4):
        result = subprocess.run(
            [
                str(iscc),
                f"/O{out_dir}",
                f"/DMyAppVersion={version}",
                f"/DMyAppSource={app_source}",
                str(RELEASE / "installer.iss"),
            ],
            cwd=ROOT,
            check=False,
        )
        if result.returncode == 0:
            break
        if attempt == 3:
            fail(
                "Inno Setup compilation failed after 3 attempts.",
                'If the error is "EndUpdateResource failed (110)", close any',
                "Explorer window on release\\ and add this project folder to",
                "your antivirus exclusions, then run the build again.",
            )
        print(f"          Inno Setup failed; retrying in 10 seconds (attempt {attempt + 1} of 3)...")
        time.sleep(10)

    # The move can hit the same brief lock. Retry it rather than fail a build
    # that has already spent minutes compressing.
    for _ in range(10):
        try:
            shutil.move(str(out_dir / setup_name), str(final))
            break
        except (OSError, shutil.Error):
            time.sleep(3)
    else:
        if not final.is_file():
            fail(f'Could not move the installer to "{final}".')
    print(f"Installer built: {final}")


def main() -> None:
    os.chdir(ROOT)
    version = app_version()
    print(
        f"\n{'=' * 60}\n Building release {version} with PyInstaller (one-directory)\n{'=' * 60}"
    )

    built = build_with_pyinstaller()
    portable = portable_dir()
    stage_contents(built, portable)
    ffmpeg_source = stage_ffmpeg(portable)
    stage_browsers(portable)

    # Off Windows the launcher carries no extension: PyInstaller names it after
    # the app, exactly as it does here with one.
    launcher = portable / (f"{APP_NAME}.exe" if IS_WINDOWS else APP_NAME)
    if not launcher.is_file():
        fail(f"The build left no executable at {launcher}.")
    print(f"Done. {launcher.name} built in {portable}")

    build_installer(version, portable.name, ffmpeg_source)

    installer = RELEASE / f"S-Q-Creator-Studio-Setup-{version}.exe"
    print(
        f"\n{'=' * 60}\n BUILD COMPLETE\n{'=' * 60}\n"
        f" Version:   {version}\n"
        f" Portable:  {launcher}\n"
        f" Installer: {installer} (if built)\n"
        f"{'=' * 60}"
    )


if __name__ == "__main__":
    main()
