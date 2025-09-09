#!/bin/bash

echo "Starting Unified Duplicator Trading Bot..."
echo "This will start both Telegram bot and Web server interfaces"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed or not in PATH"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update requirements
echo "Installing/updating requirements..."
pip install -r web_requirements.txt

# Start the unified application
echo "Starting unified application..."
echo
echo "========================================"
echo " Duplicator Trading Bot - Unified Mode"
echo "========================================"
echo
echo "📱 Telegram Bot: Active"
echo "🌐 Web Interface: http://localhost:8000"
echo
echo "Press Ctrl+C to stop both services"
echo

python3 start_both.py
