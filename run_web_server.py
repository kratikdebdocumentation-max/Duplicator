#!/usr/bin/env python3
"""
Duplicator Trading Bot - Web Server Launcher
High-performance web interface launcher with configuration options
"""

import argparse
import sys
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Duplicator Trading Bot Web Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to (default: 8000)')
    parser.add_argument('--optimized', action='store_true', help='Use optimized server (recommended)')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--network', action='store_true', help='Allow network access (bind to 0.0.0.0)')
    parser.add_argument('--log-level', default='info', choices=['debug', 'info', 'warning', 'error'], 
                       help='Log level (default: info)')
    
    args = parser.parse_args()
    
    # Adjust host for network access
    if args.network:
        args.host = '0.0.0.0'
    
    print("🚀 Starting Duplicator Trading Bot Web Server...")
    print(f"📍 Host: {args.host}")
    print(f"🔌 Port: {args.port}")
    print(f"⚡ Optimized: {'Yes' if args.optimized else 'No'}")
    print(f"🔄 Auto-reload: {'Yes' if args.reload else 'No'}")
    print(f"🌐 Network Access: {'Yes' if args.network else 'No'}")
    print()
    
    # Check if web directory exists
    if not Path("web").exists():
        print("❌ Error: web directory not found!")
        print("Please ensure you're running this from the project root directory.")
        sys.exit(1)
    
    # Check if index.html exists
    if not Path("web/index.html").exists():
        print("❌ Error: web/index.html not found!")
        print("Please ensure the web interface files are present.")
        sys.exit(1)
    
    try:
        if args.optimized:
            print("🚀 Starting optimized web server...")
            from web_server_optimized import TradingWebApp
            app = TradingWebApp()
            app.run(host=args.host, port=args.port, reload=args.reload)
        else:
            print("🚀 Starting standard web server...")
            from web_server import TradingWebApp
            app = TradingWebApp()
            app.run(host=args.host, port=args.port, reload=args.reload)
            
    except ImportError as e:
        print(f"❌ Error importing web server: {e}")
        print("Please install the required dependencies:")
        print("pip install -r web_requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Web server stopped by user")
    except Exception as e:
        print(f"❌ Error starting web server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
