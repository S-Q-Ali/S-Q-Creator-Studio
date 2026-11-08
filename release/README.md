# The release

Everything about a local build lives in this folder.

| File | What it is |
|---|---|
| **`build.py`** | The build. It runs PyInstaller, stages the browser and ffmpeg next to the app, assembles `portable/`, and on Windows compiles the installer from `installer.iss`. One script, all three platforms. |
| **`build.bat`** | The Windows entry point: it finds the Python and starts `build.py`. Nothing else lives here, so the three platforms cannot drift into three different builds. |
| **`installer.iss`** | The installer's definition: what is installed where, the shortcuts, the uninstaller, the per-user install. The version is injected at build time. |
| `portable/` | The portable build — the folder you can unzip and run. |
| `staging/` | What the installer picks up: `staging\bin\ffmpeg.exe`. |
| `S-Q-Creator-Studio-Setup-<version>.exe` | The installers this machine has built. Windows only. |
| `S-Q-Creator-Studio-<version>-macos-<arch>.dmg` | The macOS disk image with an `Applications` drag-and-drop shortcut. macOS only. |

## Building it locally

```powershell
release\build.bat
```

```bash
python release/build.py
```

Either way: about twelve minutes on the first run. The app's version comes from
the package itself, so the installer's name and metadata cannot drift from the
app it carries.

Four things have to be on the machine:

| Needed | Where the script looks |
|---|---|
| **Python** | `source/venv/…/python` (or `python.exe`), otherwise the `python` on the PATH |
| **Inno Setup 6** | Windows only: `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`, then `%ProgramFiles%`, then `%ProgramFiles(x86)%`. Without it the portable build still completes and the installer is skipped, with a warning. |
| **ffmpeg** | `FFMPEG_EXE` if you set it, then the PATH, then the winget folder `Gyan.FFmpeg_*\bin` (Windows). It is copied to `portable/bin/` under the name this OS uses. |
| **The Playwright browser** | `%PLAYWRIGHT_BROWSERS_PATH%`, then the cache folder this OS uses (`%LOCALAPPDATA%\ms-playwright`, `~/.cache/ms-playwright`, `~/Library/Caches/ms-playwright`). The **full** `chromium-<build>` is shipped — the headless shell is not enough, Social Discovery asks Playwright for `channel="chromium"`. |

Off Windows, `keyring` is collected into the bundle when it is installed here;
Windows seals keys with DPAPI and does not have keyring at all.

### If the app is running

The old build in `release/portable` cannot be deleted while the app is
running, and Windows will not even rename it. The build does not stop for
that: it goes into `release/portable-new` instead and the installer is
told to read from there. Close the app when you can and the next build
goes back to `release/portable`.

### If Inno Setup fails with `EndUpdateResource failed (110)`

Inno Setup writes the Setup.exe first and then updates its icon and version
resources. Windows can refuse that open with error 110 when Explorer has the
output folder open, or when antivirus is still scanning the new 300 MB file.
The build writes the installer to `build/installer`, retries the compile
three times, and only then moves the finished file to `release/`.

If it still fails, close any Explorer window on `release/` and add the
project folder (or `build/installer`) to your antivirus exclusions. Do not
turn real-time protection off for the whole machine.

If something goes wrong, the window stays open with the reason in it, and
the build server gets the same message in its log. Either way the exit code
is non-zero — a release that failed never looks like one that succeeded.

## Building it on the server instead

Pushing a tag does the same thing, with nothing installed on your machine:

```powershell
git tag v<x.y.z>
git push origin v<x.y.z>
```

`.github/workflows/release.yml` runs `python release/build.py` across Windows,
Ubuntu 24.04, macOS 15 (Apple Silicon `arm64`), and macOS 15 (Intel `x64`),
checks the build, smoke tests the built app, and publishes the release with
checksums. On macOS it signs the bundle ad-hoc, verifies the Mach-O `minos`
floor (`15.0`), and builds the `.dmg` with `hdiutil` (retrying if Spotlight
briefly holds the temporary volume). The release notes are the matching section
of `CHANGELOG.md`.

## What the build produces

```
release/portable/S-Q Creator Studio[.exe|.app]       the app (bundle on macOS)
release/portable/_internal/                          its Python and its libraries
release/portable/browsers/chromium-<build>/          the browser the app drives
release/portable/bin/ffmpeg[.exe]                    merges video and audio
release/S-Q-Creator-Studio-Setup-<version>.exe       the installer, on Windows
release/S-Q-Creator-Studio-<version>-macos-<arch>.dmg the disk image, on macOS
```

The installer is unsigned: Windows will ask you to confirm it the first
time.
