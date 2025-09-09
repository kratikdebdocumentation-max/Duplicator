#!/usr/bin/env python3
"""
Start only the Telegram bot (original functionality)
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from main import main

if __name__ == "__main__":
    print("🚀 Starting Duplicator Trading Bot (Telegram Only)...")
    print("📱 Telegram Bot: Active")
    print("Press Ctrl+C to stop")
    print()
    
    main()
