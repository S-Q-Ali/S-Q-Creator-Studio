# The release

Everything about a local build lives in this folder.

| File | What it is |
|---|---|
| **`build.bat`** | The build. Run it — it moves to the repository root, builds the app with PyInstaller, stages the browser and ffmpeg, and runs Inno Setup over `installer.iss`. |
| **`installer.iss`** | The installer's definition: what is installed where, the shortcuts, the uninstaller, the per-user install. The version is injected at build time. |
| `portable/` | The portable build — the folder you can unzip and run. |
| `staging/` | What the installer picks up: `staging\bin\ffmpeg.exe`. |
| `S-Q-Creator-Studio-Setup-<version>.exe` | The installers this machine has built. |

## Building it locally

```powershell
release\build.bat
```

It takes about twelve minutes. Three things have to be on the machine:

| Needed | Where the script looks |
|---|---|
| **Inno Setup 6** | `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`, then `%ProgramFiles%`, then `%ProgramFiles(x86)%` |
| **ffmpeg** | `where ffmpeg`, then the winget folder `Gyan.FFmpeg_*\bin`; or set `FFMPEG_EXE` yourself |
| **The Playwright browser** | `%PLAYWRIGHT_BROWSERS_PATH%`, then `%LOCALAPPDATA%\ms-playwright`. Only `chromium_headless_shell-*` is shipped. |
| **Python** | `source\venv\Scripts\python.exe`, otherwise the `python` on the PATH |

### If the app is running

The old build in `release\portable` cannot be deleted while the app is
running, and Windows will not even rename it. The build does not stop for
that: it goes into `release\portable-new` instead and the installer is
told to read from there. Close the app when you can and the next build
goes back to `release\portable`.

### If Inno Setup fails with `EndUpdateResource failed (110)`

Inno Setup writes the Setup.exe first and then updates its icon and version
resources. Windows can refuse that open with error 110 when Explorer has the
output folder open, or when antivirus is still scanning the new 200 MB file.
The build writes the installer to `build\installer`, retries the compile
three times, and only then moves the finished file to `release\`.

If it still fails, close any Explorer window on `release\` and add the
project folder (or `build\installer`) to your antivirus exclusions. Do not
turn real-time protection off for the whole machine.

If something goes wrong, the window stays open with the reason in it, and
the build server gets the same message in its log.

## Building it on the server instead

Pushing a tag does the same thing, with nothing installed on your machine:

```powershell
git tag v2.6.1
git push origin v2.6.1
```

`.github/workflows/release.yml` builds it, checks the build, smoke tests the
built app, and publishes the release with the checksum. The release notes
are the matching section of `CHANGELOG.md`.

## What the build produces

```
release\portable\S-Q Creator Studio.exe     the app
release\portable\_internal\                  its Python and its libraries
release\portable\browsers\                   the browser the app drives
release\portable\bin\ffmpeg.exe             merges video and audio
release\S-Q-Creator-Studio-Setup-2.6.0.exe  the installer
```

The installer is unsigned: Windows will ask you to confirm it the first
time.
