@echo off
REM Claude/Codex Session PIP - update from GitHub, then (re)start the widget
cd /d "%~dp0"

REM 1) pull latest code if git is available (skipped on conflict: --ff-only)
where git >nul 2>nul
if %errorlevel%==0 (
    git pull --ff-only
)

REM 2) stop any running widget instance (restart with fresh code)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*pip_widget.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul

REM 3) launch without a console window
start "" pythonw src\pip_widget.py
