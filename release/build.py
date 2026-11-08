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
#: The detector models travel as a folder, and the app asks for them under
#: ``models`` at the root of the bundle (``reframe.model_path``).
MODELS = Path("src") / "s_q_ali_media_downloader" / "models"
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
IS_MACOS = sys.platform == "darwin"
FFMPEG_NAME = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"

#: The oldest macOS the app claims to run on. PySide6 6.11's wheel is
#: tagged macosx_13_0, but the Qt binaries inside it declare macOS 15 - and
#: the build measures what it actually got instead of trusting this.
MACOS_FLOOR = "15.0"

#: The Mach-O magics: 32-bit, 64-bit, and the fat header a universal2
#: wheel carries.
MACHO_MAGICS = (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe")


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
        "--add-data",
        f"{MODELS}{os.pathsep}models",
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
    if IS_MACOS:
        # On macOS PyInstaller writes two things: the COLLECT folder and the
        # bundle it assembles from it. Only the bundle is the app - it is
        # what carries Info.plist, and without it the app has no identifier
        # for the keychain and no home in the dock.
        bundle = DISTPATH / f"{APP_NAME}.app"
        if not bundle.is_dir():
            fail(f"PyInstaller left no app bundle in {DISTPATH}.")
        return bundle
    built = DISTPATH / APP_NAME
    if not built.is_dir():
        fail(f"PyInstaller left no build in {built}.")
    return built


def reframe_models() -> tuple[str, ...]:
    """The model files the app's own detector asks for, by name.

    The build and the app read one list: a bundle that stages a model the app
    never looks for ships weight and not the feature.
    """
    from s_q_ali_media_downloader.core.reframe import BODY_MODEL, FACE_MODEL

    return (FACE_MODEL, BODY_MODEL)


def check_reframe_bundle(root: Path) -> None:
    """Fail the build when the vertical reframe could not run inside it.

    OpenCV is imported lazily and the box is off by default, so a bundle that
    is missing it - or a model - starts perfectly well and fails only when a
    user asks for the 9:16 version. That is not a failure a release should
    carry.
    """
    wanted = set(reframe_models())
    found: set[str] = set()
    has_cv2 = False
    for path in root.rglob("*"):
        if path.name in wanted and path.parent.name == "models":
            found.add(path.name)
        elif path.is_dir() and path.name == "cv2":
            has_cv2 = True

    missing = [f"models/{name}" for name in sorted(wanted - found)]
    if not has_cv2:
        missing.append("cv2")
    if missing:
        fail(
            "The bundle cannot make a vertical video.",
            f"Missing from {root}: {', '.join(missing)}",
            "OpenCV is a runtime requirement and the models are staged with --add-data.",
        )
    print(f"The vertical reframe is bundled: {', '.join(sorted(found))} and cv2.")


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


def bundle_layout(portable: Path) -> tuple[Path, Path]:
    """The launcher to check and the folder its extras belong next to.

    Windows and Linux get the plain one-directory layout: the app, its
    ``_internal`` folder, and the ``bin`` and ``browsers`` this script stages.
    ``--windowed`` on macOS instead builds an ``.app`` bundle, where Apple
    allows only the executable in ``Contents/MacOS`` and keeps everything else
    in ``Contents/Resources`` - so the extras follow them there, and the app
    looks for them there too (``engine.bundle_extra_roots``).
    """
    plain = portable / (f"{APP_NAME}.exe" if IS_WINDOWS else APP_NAME)
    app_bundle = next(iter(sorted(portable.glob("*.app"))), None)
    if app_bundle is None:
        return plain, portable
    contents = app_bundle / "Contents"
    return contents / "MacOS" / APP_NAME, contents / "Resources"


def version_key(value: str) -> tuple[int, int]:
    """``"13.0"`` as a number a comparison can use."""
    parts = value.split(".")
    try:
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return 0, 0


def is_mach_o(path: Path) -> bool:
    """Whether the file is a Mach-O binary, or a fat one holding two."""
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACHO_MAGICS
    except OSError:
        return False


def macho_minos(output: str) -> list[str]:
    """The macOS versions an ``otool -l`` listing declares."""
    found = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("minos "):
            found.append(stripped.split()[1])
    return found


def macos_floor(build_folder: Path) -> tuple[str, Path]:
    """The oldest macOS the build can run on, and the file that decides it.

    A Mach-O binary carries the macOS it was built for in its load commands,
    and macOS refuses to load one that is newer than itself - so the floor is
    the highest of them. A universal2 file reports one version per slice, and
    both count. The whole build folder is scanned, not just the app bundle:
    the bundled Chromium is a binary too, and it is the one a user on an
    older Mac is most likely to fail on.
    """
    highest = "0.0"
    offender = build_folder
    for path in sorted(build_folder.rglob("*")):
        if path.is_symlink() or not path.is_file() or not is_mach_o(path):
            continue
        try:
            done = subprocess.run(
                ["otool", "-l", str(path)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        for found in macho_minos(done.stdout):
            if version_key(found) > version_key(highest):
                highest, offender = found, path
    return highest, offender


def check_macos_floor(build_folder: Path) -> None:
    """Fail the build when it needs a newer macOS than we claim."""
    floor, offender = macos_floor(build_folder)
    print(f"\n{'=' * 60}\n The build's macOS floor: {floor}\n{'=' * 60}")
    print(f"  decided by: {offender}")
    if version_key(floor) > version_key(MACOS_FLOOR):
        fail(
            f"The build needs macOS {floor}, not {MACOS_FLOOR}.",
            f"{offender} declares {floor}.",
            f"The README says macOS {MACOS_FLOOR} - either the claim or the build has to change.",
        )


def macos_arch() -> str:
    """The Mac architecture, in the name the release gives it."""
    import platform

    return "arm64" if platform.machine() == "arm64" else "x64"


def build_dmg(app_bundle: Path, out: Path) -> None:
    """A disk image with the app and an Applications shortcut to drag it into.

    ``ditto`` copies a ``.app`` without flattening the symlinks inside its
    frameworks, which ``Copy-Item`` would; ``hdiutil`` is macOS's own tool.
    """
    root = RELEASE / "dmg-root"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    try:
        # The Applications shortcut has to be in the folder before the image
        # is made - hdiutil reads the folder as it is when it runs.
        (root / "Applications").symlink_to("/Applications")
        ditto = ["ditto", str(app_bundle), str(root / app_bundle.name)]
        done = subprocess.run(ditto, capture_output=True, text=True, check=False)
        if done.returncode != 0:
            fail(
                "Could not build the disk image (ditto failed).",
                done.stderr.strip()[:400],
            )
        # Spotlight on macOS 15 briefly opens the new temporary volume while
        # hdiutil is closing it, which fails with "Resource busy". Retrying
        # after a short pause lets the indexer let go.
        hdiutil = [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(root),
            "-ov",
            "-format",
            "UDZO",
            str(out),
        ]
        for attempt in range(1, 6):
            if out.exists():
                out.unlink(missing_ok=True)
            done = subprocess.run(hdiutil, capture_output=True, text=True, check=False)
            if done.returncode == 0:
                break
            if attempt == 5:
                fail(
                    "Could not build the disk image (hdiutil failed).",
                    done.stderr.strip()[:400],
                )
            time.sleep(3)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def codesign_app(app_bundle: Path) -> None:
    """Sign the bundle again, because files were added to it.

    PyInstaller seals the bundle when it builds it. Adding ffmpeg and the
    browser to its resources breaks that seal, and macOS refuses a bundle
    whose signature no longer matches its contents. An ad-hoc signature is
    enough for now; issue #15 signs the app properly.
    """
    done = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_bundle)],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        fail(
            "Could not sign the app bundle.",
            done.stderr.strip()[:400],
        )
    print(f"Bundle signed: {app_bundle}")


def dmg_path(version: str) -> Path:
    """Where the disk image for this machine is written."""
    return RELEASE / f"S-Q-Creator-Studio-{version}-macos-{macos_arch()}.dmg"


def stage_contents(built: Path, portable: Path) -> None:
    print(f"\n{'=' * 60}\n Copying to {portable}\n{'=' * 60}\n")
    # An app bundle is copied as a bundle: its symlinks - the framework
    # cross-links inside Contents - have to stay symlinks, or the bundle is
    # no longer the app PyInstaller signed.
    target = portable / built.name if built.name.endswith(".app") else portable
    try:
        shutil.copytree(built, target, dirs_exist_ok=True, symlinks=True)
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


def stage_ffmpeg(extras: Path) -> str | None:
    """Copy ffmpeg into ``bin`` and say where it came from."""
    source = find_ffmpeg()
    if not source:
        print(
            f"[WARNING] {FFMPEG_NAME} not found.\n"
            f"          The portable build cannot merge video+audio until ffmpeg\n"
            f"          is copied to {extras / 'bin'} by hand."
        )
        return None
    (extras / "bin").mkdir(parents=True, exist_ok=True)
    target = extras / "bin" / FFMPEG_NAME
    shutil.copy2(source, target)
    target.chmod(target.stat().st_mode | 0o755)
    print(f"{FFMPEG_NAME} staged into {extras / 'bin'}\n  from {Path(source).resolve()}")
    return source


def browser_cache_dir() -> Path | None:
    """Where Playwright keeps the browsers it downloaded on this OS.

    The app's own resolver is the one definition of this; a build that looked
    in a different place would ship no browser.
    """
    from s_q_ali_media_downloader.agent.tools.browser import _playwright_cache_dir

    return _playwright_cache_dir()


def stage_browsers(extras: Path) -> None:
    """Copy the full Chromium build next to the app, where the app looks.

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
        shutil.copytree(found, extras / "browsers" / found.name, dirs_exist_ok=True)
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
    check_reframe_bundle(built)
    portable = portable_dir()
    stage_contents(built, portable)
    launcher, extras = bundle_layout(portable)
    ffmpeg_source = stage_ffmpeg(extras)
    stage_browsers(extras)

    if not launcher.is_file():
        fail(f"The build left no executable at {launcher}.")
    print(f"Done. {launcher.name} built in {portable}")

    disk_image = None
    if IS_MACOS:
        app_bundle = next(iter(sorted(portable.glob("*.app"))), None)
        if app_bundle is None:
            fail(f"The build left no app bundle in {portable}.")
        codesign_app(app_bundle)
        check_macos_floor(portable)
        disk_image = dmg_path(version)
        build_dmg(app_bundle, disk_image)
        print(f"Disk image: {disk_image}")

    build_installer(version, portable.name, ffmpeg_source)

    installer = RELEASE / f"S-Q-Creator-Studio-Setup-{version}.exe"
    print(
        f"\n{'=' * 60}\n BUILD COMPLETE\n{'=' * 60}\n"
        f" Version:   {version}\n"
        f" Portable:  {launcher}\n"
        f" Disk image: {disk_image}\n"
        f" Installer: {installer} (if built)\n"
        f"{'=' * 60}"
    )


if __name__ == "__main__":
    main()
