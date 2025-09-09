#!/usr/bin/env python3
"""
Start only the Web server
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

def main():
    print("🚀 Starting Duplicator Trading Bot (Web Only)...")
    print("🌐 Web Interface: http://localhost:8000")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        from web_server_optimized import TradingWebApp
        app = TradingWebApp()
        app.run()
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("Please install web dependencies:")
        print("py -m pip install fastapi uvicorn websockets")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting web server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
