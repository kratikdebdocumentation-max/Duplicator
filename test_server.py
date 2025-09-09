#!/usr/bin/env python3
"""
Simple test server to verify the system is working
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

try:
    from src.brokers.broker_manager import BrokerManager
    from src.utils.logger import get_logger
    
    logger = get_logger('test_server')
    logger.info("Testing broker manager...")
    
    # Test broker manager
    broker_manager = BrokerManager()
    logger.info("Broker manager created successfully")
    
    # Test connection
    connection_results = broker_manager.connect_all()
    logger.info(f"Connection results: {connection_results}")
    
    # Test health status
    health_status = broker_manager.get_health_status()
    logger.info(f"Health status: {health_status}")
    
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
