@echo off
REM Claude/Codex Session PIP - run without installing (no console window)
cd /d "%~dp0"
start "" pythonw src\pip_widget.py
