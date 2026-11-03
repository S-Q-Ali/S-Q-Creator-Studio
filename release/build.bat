@echo off
setlocal EnableDelayedExpansion
rem ============================================================
rem  S-Q Creator Studio — Windows build entry point
rem
rem  The build is release\build.py, and this wrapper only starts it.
rem  One script builds all three platforms: keeping the Windows logic
rem  here as batch as well would mean three versions of the same steps,
rem  and only one of them would ever be run.
rem
rem  The Python that runs it is the one the build belongs to — the
rem  project's virtualenv when there is one, the Python on the PATH
rem  otherwise, because a build machine (CI) has no source\venv.
rem ============================================================

set "PYTHON_EXE=%~dp0..\source\venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

"%PYTHON_EXE%" "%~dp0build.py" %*
set "RC=%ERRORLEVEL%"

rem build.py holds the window open itself when a failure has something to
rem say; this only makes sure the exit code reaches the caller, because a
rem release that failed must never look like one that succeeded.
exit /b %RC%
