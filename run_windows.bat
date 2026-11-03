@echo off
setlocal
cd /d "%~dp0"
title SocialPilot AI
if exist "dist\SocialPilotAI\SocialPilotAI.exe" (
  start "" "dist\SocialPilotAI\SocialPilotAI.exe"
  exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
  echo Python environment not found. Run build_windows.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
  echo SocialPilot AI closed with an error.
  pause
)
