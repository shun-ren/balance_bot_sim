@echo off
cd /d "%~dp0"
if exist ".runtime\python.exe" (
  ".runtime\python.exe" main.py %*
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py %*
) else (
  python main.py %*
)
if errorlevel 1 pause
