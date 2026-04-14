@echo off
REM Launch the Fitbit Dashboard as a standalone desktop application
cd /d "%~dp0"
call .venv\Scripts\activate 2>nul
python fitbit_desktop.py
