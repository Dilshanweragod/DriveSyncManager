@echo off
setlocal
title Install DriveSync Manager (Windows)
cd /d "%~dp0"

echo ============================================
echo   DriveSync Manager - Windows Installer
echo   Version 2.1.1
echo ============================================
echo.

REM Check for Python
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python Launcher ^(py^) not found.
  echo.
  echo Please install Python 3.11+ from:
  echo   https://www.python.org/downloads/windows/
  echo.
  echo During installation, make sure to check:
  echo   [x] Add python.exe to PATH
  echo   [x] Install Python Launcher for all users
  echo.
  pause
  exit /b 1
)

REM Show Python version
echo Detected Python:
py -3 --version
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 goto failed
  echo Virtual environment created.
) else (
  echo Virtual environment already exists.
)
echo.

REM Upgrade pip
echo Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
if errorlevel 1 goto failed

REM Install dependencies
echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 goto failed

echo.
echo ============================================
echo   Installation completed successfully!
echo ============================================
echo.
echo To start the app, double-click:
echo   Run_DriveSyncManager.bat
echo.
pause
exit /b 0

:failed
echo.
echo ============================================
echo   Installation FAILED
echo ============================================
echo.
echo Check the following:
echo   1. Python 3.11+ is installed
echo   2. Internet connection is available
echo   3. You have write access to this folder
echo.
echo Then run this installer again.
pause
exit /b 1
