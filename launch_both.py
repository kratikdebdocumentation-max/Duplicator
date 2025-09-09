#!/usr/bin/env python3
"""
Complete launcher for both Telegram and Web interfaces
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    
    dependencies = [
        "fastapi",
        "uvicorn", 
        "websockets",
        "python-telegram-bot",
        "requests",
        "pandas",
        "pyyaml",
        "cachetools",
        "httptools"
    ]
    
    for dep in dependencies:
        try:
            print(f"Installing {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                         check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to install {dep}: {e}")

def start_telegram_bot():
    """Start Telegram bot in background"""
    print("📱 Starting Telegram Bot...")
    try:
        # Start in background
        subprocess.Popen([sys.executable, "main.py"], 
                        creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True
    except Exception as e:
        print(f"Error starting Telegram bot: {e}")
        return False

def start_web_server():
    """Start web server in background"""
    print("🌐 Starting Web Server...")
    try:
        # Add src to path
        sys.path.append(str(Path(__file__).parent / "src"))
        
        # Import and start web server
        from web_server_optimized import TradingWebApp
        app = TradingWebApp()
        
        # Start in background
        subprocess.Popen([sys.executable, "-c", 
                         "import sys; sys.path.append('src'); "
                         "from web_server_optimized import TradingWebApp; "
                         "app = TradingWebApp(); app.run()"],
                        creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True
    except Exception as e:
        print(f"Error starting web server: {e}")
        return False

def main():
    print("🚀 Duplicator Trading Bot - Complete Launcher")
    print("=" * 50)
    
    # Install dependencies
    install_dependencies()
    
    print("\n🚀 Starting both interfaces...")
    
    # Start Telegram bot
    if start_telegram_bot():
        print("✅ Telegram Bot started")
    else:
        print("❌ Failed to start Telegram Bot")
    
    # Wait a moment
    time.sleep(3)
    
    # Start Web server
    if start_web_server():
        print("✅ Web Server started")
    else:
        print("❌ Failed to start Web Server")
    
    print("\n" + "=" * 50)
    print("🎉 Both interfaces are starting!")
    print("=" * 50)
    print()
    print("📱 Telegram Bot: Check the 'Telegram Bot' window")
    print("🌐 Web Interface: http://localhost:8000")
    print()
    print("Press Enter to close this launcher...")
    input()

if __name__ == "__main__":
    main()
