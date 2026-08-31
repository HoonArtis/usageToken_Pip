@echo off
REM Claude Session PIP - run without installing (no console window)
cd /d "%~dp0"
start "" pythonw pip_widget.py
