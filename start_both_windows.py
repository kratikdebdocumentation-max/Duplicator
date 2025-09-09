#!/usr/bin/env python3
"""
Windows-specific launcher for Unified Duplicator Trading Bot
Handles Python path issues on Windows
"""

import subprocess
import sys
import os
from pathlib import Path

def find_python_executable():
    """Find the correct Python executable on Windows"""
    # Try different Python commands
    python_commands = ['py', 'python', 'python3', 'python.exe']
    
    for cmd in python_commands:
        try:
            result = subprocess.run([cmd, '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                print(f"✅ Found Python: {cmd}")
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    
    return None

def main():
    print("🚀 Starting Unified Duplicator Trading Bot...")
    print("🔍 Detecting Python installation...")
    
    # Find Python executable
    python_cmd = find_python_executable()
    
    if not python_cmd:
        print("❌ Error: Python not found!")
        print("Please install Python 3.8+ and try again")
        print("Download from: https://www.python.org/downloads/")
        input("Press Enter to exit...")
        return
    
    print(f"🐍 Using Python: {python_cmd}")
    print()
    
    # Check if start_both.py exists
    if not Path("start_both.py").exists():
        print("❌ Error: start_both.py not found!")
        print("Please ensure you're in the correct directory")
        input("Press Enter to exit...")
        return
    
    # Check if web_requirements.txt exists
    if not Path("web_requirements.txt").exists():
        print("❌ Error: web_requirements.txt not found!")
        print("Please ensure all files are present")
        input("Press Enter to exit...")
        return
    
    print("📦 Installing/updating requirements...")
    try:
        # Install requirements
        subprocess.run([python_cmd, '-m', 'pip', 'install', '-r', 'web_requirements.txt'], 
                      check=True)
        print("✅ Requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing requirements: {e}")
        input("Press Enter to exit...")
        return
    
    print()
    print("🚀 Starting unified application...")
    print("=" * 50)
    print("  Duplicator Trading Bot - Unified Mode")
    print("=" * 50)
    print()
    print("📱 Telegram Bot: Active")
    print("🌐 Web Interface: http://localhost:8000")
    print()
    print("Press Ctrl+C to stop both services")
    print()
    
    try:
        # Start the unified application
        subprocess.run([python_cmd, 'start_both.py'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting application: {e}")
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
