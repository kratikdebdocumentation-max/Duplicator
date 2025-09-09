@echo off
echo Starting Unified Duplicator Trading Bot...
echo This will start both Telegram bot and Web server interfaces
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

REM Install/update requirements
echo Installing/updating requirements...
pip install -r web_requirements.txt

REM Start the unified application
echo Starting unified application...
echo.
echo ========================================
echo  Duplicator Trading Bot - Unified Mode
echo ========================================
echo.
echo 📱 Telegram Bot: Active
echo 🌐 Web Interface: http://localhost:8000
echo.
echo Press Ctrl+C to stop both services
echo.

py start_both.py

pause
