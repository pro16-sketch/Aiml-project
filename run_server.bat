@echo off
echo ================================
echo Vehicle Detection System - Server
echo ================================
echo.
echo Checking Python installation...
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)
echo Python found!
echo.
echo Installing dependencies...
pip install -r requirements.txt > nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed!
echo.
echo ================================
echo Starting Vehicle Detection Server
echo ================================
echo.
echo Server is running at: http://localhost:5001
echo Press Ctrl+C to stop the server
echo.
python app.py
pause
