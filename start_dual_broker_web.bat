@echo off
echo Starting Dual Broker Trading Bot with Web Interface...
echo =====================================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Start the dual broker web application
python start_dual_broker_web.py

pause
