@echo off
REM Claude/Codex Session PIP - double-click uninstaller
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\uninstall.ps1"
echo.
pause
