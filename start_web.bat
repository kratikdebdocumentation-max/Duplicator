@echo off
echo Starting Duplicator Trading Bot Web Server...
echo.

REM Check if Python is installed
py --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    py -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/updating requirements
echo Installing/updating requirements...
pip install -r web_requirements.txt

REM Start the web server
echo Starting web server on http://localhost:8000
echo Press Ctrl+C to stop the server
echo.
py web_server.py

pause
