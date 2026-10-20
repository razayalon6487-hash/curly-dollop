@echo off
cd /d "%~dp0"
title Verification Bot
if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found. Restore or recreate .venv first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" bot.py
echo.
echo Bot process stopped. Close this window to end the session.
pause