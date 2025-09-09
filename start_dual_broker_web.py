#!/usr/bin/env python3
"""
Start script for dual broker trading bot with web interface
Runs both the main trading bot and web server
"""

import asyncio
import threading
import time
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from main import DuplicatorApp
from web_server import TradingWebApp
from src.utils.logger import get_logger

def run_web_server():
    """Run the web server in a separate thread"""
    logger = get_logger('web_server_thread')
    try:
        logger.info("Starting web server...")
        app = TradingWebApp()
        app.run(host="127.0.0.1", port=8000, reload=False)
    except Exception as e:
        logger.error(f"Web server error: {e}")

def run_main_app():
    """Run the main trading application"""
    logger = get_logger('main_app_thread')
    try:
        logger.info("Starting main trading application...")
        app = DuplicatorApp()
        asyncio.run(app.run())
    except Exception as e:
        logger.error(f"Main app error: {e}")

def main():
    """Main entry point"""
    logger = get_logger('dual_broker_startup')
    
    try:
        logger.info("🚀 Starting Dual Broker Trading Bot with Web Interface")
        logger.info("=" * 60)
        
        # Start web server in a separate thread
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        
        # Give web server time to start
        time.sleep(3)
        
        # Start main application
        logger.info("Starting main trading application...")
        run_main_app()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        logger.info("Dual broker application stopped")

if __name__ == "__main__":
    main()
