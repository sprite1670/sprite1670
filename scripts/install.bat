@echo off
setlocal
title WorkBuddy Check-in Skill - Setup Check

rem ============================================================
rem  WorkBuddy Check-in Skill - setup check
rem  Locates Python, then hands over to setup_check.py which does
rem  the environment check, cloud-config check and a live
rem  check-in self-test.
rem ============================================================

set "SCRIPT_DIR=%~dp0"

set "PYEXE="
where python >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE where python3 >nul 2>&1 && set "PYEXE=python3"

if not defined PYEXE (
  echo [X] Python not found in PATH.
  echo     Install Python 3 from https://www.python.org/downloads/
  echo     IMPORTANT: tick "Add Python to PATH" during setup.
  echo.
  pause
  exit /b 1
)

pushd "%SCRIPT_DIR%" >nul 2>&1
"%PYEXE%" "setup_check.py"
set "RC=%ERRORLEVEL%"
popd >nul 2>&1

echo.
pause
exit /b %RC%
