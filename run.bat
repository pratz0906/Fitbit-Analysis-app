@echo off
title Fitbit Dashboard
cd /d "%~dp0"

echo ============================================
echo   Fitbit Dashboard - Starting...
echo ============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    echo.
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Install / upgrade dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet
echo.

:: Open browser after a short delay (start launches async)
echo Opening browser...
start "" http://localhost:5000

:: Start the Flask app (this blocks until Ctrl+C)
echo.
echo ============================================
echo   Dashboard running at http://localhost:5000
echo   Press Ctrl+C to stop the server.
echo ============================================
echo.
python app.py

:: Deactivate when done
deactivate
pause
