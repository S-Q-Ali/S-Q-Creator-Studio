@echo off
setlocal EnableDelayedExpansion
rem ============================================================
rem  S-Q-Ali Media Downloader — Canonical Release Build Script
rem  Produces a one-directory build in build\out\, then copies
rem  it to release\portable\ ready for the Inno Setup installer.
rem ============================================================

set "ROOT=%~dp0"
set "VENV=%ROOT%source\venv"
set "PYINSTALLER=%VENV%\Scripts\python.exe"
set "PYTHON=%VENV%\Scripts\python.exe"
set "ENTRY=src\s_q_ali_media_downloader\__main__.py"
set "ICON=src\s_q_ali_media_downloader\resources\icon.ico"
set "WORKPATH=build\pkg"
set "DISTPATH=build\out"
set "APP_NAME=S-Q-Ali Media Downloader"
set "PORTABLE=release\portable"

echo.
echo ============================================================
echo  Step 1 of 3 — Building with PyInstaller (one-directory)
echo ============================================================
echo.

"%PYINSTALLER%" -m PyInstaller ^
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
    --workpath "%WORKPATH%" ^
    --distpath "%DISTPATH%" ^
    "%ENTRY%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed with code %ERRORLEVEL%.
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo  Step 2 of 3 — Copying to release\portable\
echo ============================================================
echo.

if exist "%PORTABLE%" (
    echo Removing old portable build...
    rmdir /s /q "%PORTABLE%"
)
mkdir "%PORTABLE%"
xcopy /e /i /q "%DISTPATH%\%APP_NAME%\*" "%PORTABLE%\"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to copy build to %PORTABLE%.
    exit /b %ERRORLEVEL%
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

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
set "FFMPEG_SRC=C:\Users\MuslimQasim\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
set "STAGING=release\staging\bin"

if not exist "%ISCC%" (
    echo Inno Setup not found at: %ISCC%
    echo Skipping installer build. Portable build is complete.
    goto :done
)

echo Staging ffmpeg.exe for installer...
if not exist "%STAGING%" mkdir "%STAGING%"
if exist "%FFMPEG_SRC%" (
    copy /y "%FFMPEG_SRC%" "%STAGING%\ffmpeg.exe" >nul
    echo ffmpeg.exe staged.
) else (
    echo [WARNING] ffmpeg.exe not found at expected winget path.
    echo           Installer will build without ffmpeg — copy it manually to %STAGING%\ first.
)

echo Running Inno Setup compiler...
"%ISCC%" "release\installer.iss"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Inno Setup compilation failed.
    exit /b %ERRORLEVEL%
)

echo Installer built: release\S-Q-Ali-Media-Downloader-Setup-2.1.0.exe

:done
echo.
echo ============================================================
echo  BUILD COMPLETE
echo ============================================================
echo  Portable:  %PORTABLE%\%APP_NAME%.exe
echo  Installer: release\S-Q-Ali-Media-Downloader-Setup-2.1.0.exe (if built)
echo ============================================================
echo.
endlocal
