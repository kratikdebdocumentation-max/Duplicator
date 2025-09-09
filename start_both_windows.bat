@echo off
echo Starting Duplicator Trading Bot - Both Interfaces
echo.

REM Check if Python is installed
py --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

echo Installing web dependencies...
py -m pip install fastapi uvicorn websockets python-telegram-bot requests pandas pyyaml

echo.
echo ========================================
echo  Duplicator Trading Bot - Both Interfaces
echo ========================================
echo.
echo Starting both interfaces in separate windows...
echo.

REM Start Telegram bot in new window
start "Telegram Bot" py start_telegram_only.py

REM Wait a moment
timeout /t 3 /nobreak >nul

REM Start Web server in new window
start "Web Server" py start_web_only.py

echo.
echo Both interfaces are starting...
echo.
echo 📱 Telegram Bot: Check the "Telegram Bot" window
echo 🌐 Web Interface: http://localhost:8000
echo.
echo Press any key to close this launcher...
pause >nul