@echo off
setlocal
cd /d "%~dp0"
title SocialPilot AI - Windows Build
echo ==========================================
echo   SocialPilot AI - Build Windows EXE
echo ==========================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11+ is not installed or not in PATH.
  echo Install Python from https://www.python.org/downloads/windows/
  echo IMPORTANT: enable "Add Python to PATH".
  pause
  exit /b 1
)
py -m pip install --upgrade pip
if errorlevel 1 goto error
py -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto error
py -m PyInstaller --noconfirm --clean --windowed --name SocialPilotAI --collect-all PySide6 main.py
if errorlevel 1 goto error
echo.
echo BUILD SUCCESS!
echo EXE location: dist\SocialPilotAI\SocialPilotAI.exe
pause
exit /b 0
:error
echo.
echo BUILD FAILED. Scroll up to see the error.
pause
exit /b 1
