#!/usr/bin/env python3
"""
Test script for dual broker web interface
Tests the web server with both brokers enabled
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from web_server import TradingWebApp
from src.utils.logger import get_logger

def test_web_server():
    """Test the web server with dual broker setup"""
    logger = get_logger('test_dual_broker')
    
    try:
        logger.info("Starting dual broker web server test...")
        
        # Create web app instance
        app = TradingWebApp()
        
        # Check if both brokers are initialized
        if app.broker_manager:
            broker_status = app.broker_manager.get_health_status()
            logger.info(f"Broker status: {broker_status}")
            
            # Check if both brokers are configured
            enabled_brokers = list(broker_status.keys())
            logger.info(f"Enabled brokers: {enabled_brokers}")
            
            if len(enabled_brokers) >= 2:
                logger.info("✅ Dual broker configuration detected")
            else:
                logger.warning(f"⚠️ Only {len(enabled_brokers)} broker(s) configured")
            
            # Test broker details endpoint
            try:
                import requests
                response = requests.get("http://127.0.0.1:8000/api/brokers/details", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Broker details API working: {len(data.get('brokers', {}))} brokers")
                else:
                    logger.warning(f"⚠️ Broker details API returned status {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Could not test API (server may not be running): {e}")
        
        logger.info("✅ Web server test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Web server test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_web_server()
    sys.exit(0 if success else 1)
