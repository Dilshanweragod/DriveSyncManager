@echo off
setlocal
title DriveSync Manager
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ============================================
  echo   DriveSync Manager - Not Installed
  echo ============================================
  echo.
  echo Please run Install_DriveSyncManager.bat first.
  echo.
  pause
  exit /b 1
)

".venv\Scripts\pythonw.exe" DriveSyncManager.py
if errorlevel 1 (
  echo.
  echo ============================================
  echo   DriveSync Manager exited with an error
  echo ============================================
  echo.
  echo Possible causes:
  echo   - Tkinter not installed with Python
  echo   - Corrupt virtual environment
  echo.
  echo Try running Install_DriveSyncManager.bat again.
  pause
)
