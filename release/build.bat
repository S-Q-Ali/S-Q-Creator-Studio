@echo off
setlocal EnableDelayedExpansion
rem ============================================================
rem  S-Q Creator Studio — Canonical Release Build Script
rem  Produces a one-directory build in build\out\, then copies
rem  it to release\portable\ ready for the Inno Setup installer.
rem
rem  Everything about the release lives in this folder: this script,
rem  installer.iss, and the portable\ staging\ and the installers
rem  themselves. Run it from anywhere - it moves to the repository
rem  root first, because every path below is relative to it.
rem ============================================================

cd /d "%~dp0.."
set "ROOT=%~dp0..\"
set "VENV=%ROOT%source\venv"
rem The build uses the project's virtualenv when there is one. A build
rem machine (CI) has no source\venv - it installs the dependencies into
rem its own Python - so fall back to the Python on the PATH.
set "PYTHON_EXE=%VENV%\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "ENTRY=src\s_q_ali_media_downloader\__main__.py"
set "ICON=src\s_q_ali_media_downloader\resources\icon.ico"
set "WORKPATH=build\pkg"
set "DISTPATH=build\out"
set "APP_NAME=S-Q Creator Studio"
rem The folder the build is copied into. It is "portable", or
rem "portable-new" when the old one is in use.
set "PORTABLE=release\portable"
set "APPSOURCE=portable"

rem Read the app version from src/__init__.py so the setup name and
rem installer metadata never drift from the packaged app (single source).
set "VERFILE=%TEMP%\sq_creator_ver.tmp"
if exist "%VERFILE%" del /q "%VERFILE%"
"%PYTHON_EXE%" -c "import io,sys; sys.path.insert(0, r'%ROOT%src'); import s_q_ali_media_downloader; print(s_q_ali_media_downloader.__version__)" > "%VERFILE%"
set /p APP_VERSION=<"%VERFILE%"
del /q "%VERFILE%" 2>nul
if not defined APP_VERSION set "APP_VERSION=2.6.0"

echo.
echo ============================================================
echo  Building release %APP_VERSION% with PyInstaller (one-directory)
echo ============================================================
echo.

"%PYTHON_EXE%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name "%APP_NAME%" ^
    --icon "%ICON%" ^
    --add-data "%ICON%;." ^
    --paths src ^
    --hidden-import=pydantic ^
    --hidden-import=pydantic_core ^
    --hidden-import=annotated_types ^
    --hidden-import=typing_extensions ^
    --hidden-import=typing_inspection ^
    --hidden-import=httpx ^
    --collect-all pydantic ^
    --collect-all pydantic_core ^
    --collect-all annotated_types ^
    --collect-all typing_extensions ^
    --collect-all typing_inspection ^
    --collect-all httpx ^
    --collect-all yt_dlp ^
    --collect-all curl_cffi ^
    --collect-all playwright ^
    --workpath "%WORKPATH%" ^
    --distpath "%DISTPATH%" ^
    "%ENTRY%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed with code %ERRORLEVEL%.
    call :failed || exit /b 1
)

echo.
echo ============================================================
echo  Step 2 of 3 — Copying to release\portable\
echo ============================================================
echo.

if exist "%PORTABLE%" (
    echo Removing old portable build...
    rem Read-only attributes make rmdir fail with "Access is denied", and a
    rem running copy of the app - or a virus scanner - can hold a lock on the
    rem old DLLs. The browser folder alone is ~1500 files, so the removal is
    retried for a while and the copy never prompts: a build that waits for
    rem an answer is a hung build.
    set "EMPTY_DIR=%TEMP%\sq_empty_%RANDOM%"
    mkdir "%EMPTY_DIR%" >nul 2>nul
    for /l %%i in (1,1,20) do (
        if exist "%PORTABLE%" (
            attrib -R "%PORTABLE%\*" /S /D >nul 2>nul
            rem Mirroring an empty folder over it removes the contents; it is
            rem far quicker than rmdir on a few thousand files.
            robocopy "%EMPTY_DIR%" "%PORTABLE%" /MIR /NFL /NDL /NJH /NJS /NC /NS /R:1 /W:1 >nul 2>nul
            rmdir /s /q "%PORTABLE%" >nul 2>nul
            if exist "%PORTABLE%" ping -n 4 127.0.0.1 >nul
        )
    )
    rmdir /s /q "%EMPTY_DIR%" >nul 2>nul
    if exist "%PORTABLE%" (
        rem The files are locked - a running copy of the app, most likely.
        rem Windows will not delete them and will not even rename the
        rem folder, so the build goes into a fresh one and the installer
        ; is told to read from there. The running app keeps its files.
        echo           The old build is in use - the app is probably running.
        echo           Building into release\portable-new instead.
        set "PORTABLE=release\portable-new"
        set "APPSOURCE=portable-new"
        if exist "%PORTABLE%" (
            rem A leftover from an earlier build; nobody is running it.
            rmdir /s /q "%PORTABLE%" >nul 2>nul
            if exist "%PORTABLE%" (
                echo [ERROR] Could not remove "%PORTABLE%" either.
                echo           Close the app and run this script again.
                call :failed || exit /b 1
            )
        )
    )
)
mkdir "%PORTABLE%"
xcopy /e /i /q /y "%DISTPATH%\%APP_NAME%\*" "%PORTABLE%\"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to copy build to %PORTABLE%.
    call :failed || exit /b 1
)

rem Locate ffmpeg once: PATH first, then the winget install folder.
rem FFMPEG_EXE can be set by the caller to point at a specific build.
set "FFMPEG_EXE=%FFMPEG_EXE%"
for /f "delims=" %%F in ('where ffmpeg 2^>nul') do if not defined FFMPEG_EXE set "FFMPEG_EXE=%%F"
if not defined FFMPEG_EXE (
    for /f "delims=" %%F in ('dir /b /s "%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\bin\ffmpeg.exe" 2^>nul') do if not defined FFMPEG_EXE set "FFMPEG_EXE=%%F"
)

rem The Social Discovery feature drives a real browser. The Playwright
rem headless shell ships with the app so the feature works on a machine
rem that has no Edge and no Chrome. It is the headless shell and not the
rem full Chromium because the feature only ever runs headless.
set "BROWSERS_SRC=%PLAYWRIGHT_BROWSERS_PATH%"
if not defined BROWSERS_SRC set "BROWSERS_SRC=%LOCALAPPDATA%\ms-playwright"
if exist "%BROWSERS_SRC%" (
    for /d %%D in ("%BROWSERS_SRC%\chromium_headless_shell-*") do (
        echo Shipping browser: %%~nxD
        xcopy /e /i /q /y "%%D" "%PORTABLE%\browsers\%%~nxD" >nul
    )
) else (
    echo [WARNING] No Playwright browser found in "%BROWSERS_SRC%".
    echo           The Social Discovery feature will use the browser Windows
    echo           has, or report that it needs 'playwright install chromium'.
)

rem ffmpeg ships next to the app: "Best available" downloads video and audio
rem as separate streams and yt-dlp needs ffmpeg to merge them. Without it the
rem portable build fails on every YouTube download.
if defined FFMPEG_EXE (
    if not exist "%PORTABLE%\bin" mkdir "%PORTABLE%\bin"
    copy /y "%FFMPEG_EXE%" "%PORTABLE%\bin\ffmpeg.exe" >nul
    echo ffmpeg.exe staged into %PORTABLE%\bin
    for %%F in ("%FFMPEG_EXE%") do echo   from %%~fF
) else (
    echo [WARNING] ffmpeg.exe not found.
    echo           The portable build cannot merge video+audio until ffmpeg.exe
    echo           is copied to %PORTABLE%\bin\ by hand.
)

for %%F in ("%PORTABLE%\%APP_NAME%.exe") do (
    set /a "SIZE_MB=%%~zF / 1048576"
)

echo Done. EXE size: !SIZE_MB! MB
echo Portable location: %PORTABLE%\%APP_NAME%.exe

echo.
echo ============================================================
echo  Step 3 of 3 — Optional: Build Inno Setup Installer
echo ============================================================
echo.

rem Inno Setup: a per-user install, or the machine-wide one. The paths are
rem checked with GOTO rather than a chain of IFs, because "%ProgramFiles(x86)%"
rem expands to a path with a bracket in it - and a bracket inside a
rem parenthesised block ends the block early, which broke the build.
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :have_iscc
set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :have_iscc
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :have_iscc
echo [WARNING] Inno Setup was not found on this machine.
echo           Skipping the installer. The portable build is complete.
goto :done
:have_iscc
set "STAGING=release\staging\bin"

echo Staging ffmpeg.exe for installer...
if not exist "%STAGING%" mkdir "%STAGING%"
if defined FFMPEG_EXE (
    copy /y "%FFMPEG_EXE%" "%STAGING%\ffmpeg.exe" >nul
    echo ffmpeg.exe staged.
) else (
    echo [WARNING] ffmpeg.exe not found.
    echo           Installer will build without ffmpeg — copy it manually to %STAGING%\ first.
)

rem Compile into a clean folder instead of release\. An Explorer window left
rem open on release\ - or antivirus scanning the new 200 MB Setup.exe - can
rem hold the file open while Inno updates its icon and version resources,
rem which fails with "EndUpdateResource failed (110)". The finished file is
rem moved into release\ after the compile.
set "INSTALLER_OUT=%ROOT%build\installer"
if exist "%INSTALLER_OUT%" rmdir /s /q "%INSTALLER_OUT%" >nul 2>nul
mkdir "%INSTALLER_OUT%" >nul 2>nul
set "INSTALLER_EXE=%ROOT%release\S-Q-Creator-Studio-Setup-%APP_VERSION%.exe"

echo Running Inno Setup compiler...
rem MyAppSource tells the installer which folder the build landed in.
set "ISCC_TRY=1"
:run_iscc
"%ISCC%" /O"%INSTALLER_OUT%" /DMyAppVersion=%APP_VERSION% /DMyAppSource=%APPSOURCE% "release\installer.iss"

if %ERRORLEVEL% equ 0 goto :iscc_ok
if %ISCC_TRY% geq 3 (
    echo [ERROR] Inno Setup compilation failed after 3 attempts.
    echo         If the error is "EndUpdateResource failed (110)", close any
    echo         Explorer window on release\ and add this project folder to
    echo         your antivirus exclusions, then run the build again.
    call :failed || exit /b 1
)
set /a ISCC_TRY+=1
echo           The output file was busy; retrying in 10 seconds ^(attempt %ISCC_TRY% of 3^)...
ping -n 11 127.0.0.1 >nul
goto :run_iscc

:iscc_ok
rem The move can hit the same brief lock. Retry it instead of failing a build
rem that has already spent minutes compressing.
for /l %%i in (1,1,10) do (
    move /y "%INSTALLER_OUT%\S-Q-Creator-Studio-Setup-%APP_VERSION%.exe" "%INSTALLER_EXE%" >nul 2>nul
    if not errorlevel 1 goto :installer_done
    ping -n 4 127.0.0.1 >nul
)
echo [ERROR] Could not move the installer to "%INSTALLER_EXE%".
call :failed || exit /b 1

:installer_done
echo Installer built: %INSTALLER_EXE%

rem Step past the failure subroutine: the build is done.
goto :done

:failed
rem A build that was started by double-clicking closes its window the
rem moment it ends, and the message goes with it. The window is kept
rem open here so the reason can be read. The build server does not need
rem it.
if not defined GITHUB_ACTIONS pause
rem 'exit /b 1' returns to the caller, which turns it into the end of
rem the script with 'call :failed || exit /b 1'. The two-step is the
rem safe one: it does not depend on how 'exit' behaves inside a
rem parenthesised block, and a release build that fails must never
rem look like one that succeeded.
exit /b 1

:done
echo.
echo ============================================================
echo  BUILD COMPLETE
echo ============================================================
echo  Version:   %APP_VERSION%
echo  Portable:  %PORTABLE%\%APP_NAME%.exe
echo  Installer: release\S-Q-Creator-Studio-Setup-%APP_VERSION%.exe (if built)
echo ============================================================
echo.
endlocal
