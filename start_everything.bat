@echo off
echo ========================================
echo  Duplicator Trading Bot - Complete Setup
echo ========================================
echo.

REM Check if Python is installed
py --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

echo Installing all dependencies...
py -m pip install fastapi uvicorn websockets python-telegram-bot requests pandas pyyaml cachetools httptools

echo.
echo ========================================
echo  Starting Both Interfaces
echo ========================================
echo.

echo Starting Telegram Bot in new window...
start "Telegram Bot" py main.py

echo Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo Starting Web Server in new window...
start "Web Server" py -c "
import sys
sys.path.append('src')
from web_server_optimized import TradingWebApp
app = TradingWebApp()
app.run()
"

echo.
echo ========================================
echo  Both Interfaces Started!
echo ========================================
echo.
echo 📱 Telegram Bot: Check the "Telegram Bot" window
echo 🌐 Web Interface: http://localhost:8000
echo.
echo Press any key to close this launcher...
pause >nul
