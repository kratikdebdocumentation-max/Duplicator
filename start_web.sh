#!/bin/bash

echo "Starting Duplicator Trading Bot Web Server..."
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

# Start the web server
echo "Starting web server on http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo
python web_server.py
