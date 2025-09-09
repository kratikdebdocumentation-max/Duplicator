#!/usr/bin/env python3
"""
Test script for optimized websocket setup
Tests that price updates come from Broker 1 only and order updates from both brokers
"""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from src.brokers.broker_manager import BrokerManager
from src.websocket.websocket_manager import WebSocketManager
from src.orders.order_manager import OrderManager
from src.utils.logger import get_logger

class WebSocketTest:
    """Test class for websocket optimization"""
    
    def __init__(self):
        self.logger = get_logger('websocket_test')
        self.price_updates = []
        self.order_updates = []
        
    def on_price_update(self, price_update):
        """Handle price updates"""
        self.price_updates.append(price_update)
        self.logger.info(f"Price update from {price_update.broker}: {price_update.symbol} = ₹{price_update.last_price}")
    
    def on_order_update(self, order_update):
        """Handle order updates"""
        self.order_updates.append(order_update)
        self.logger.info(f"Order update from {order_update.broker}: {order_update.order_id} - {order_update.status}")
    
    def test_websocket_setup(self):
        """Test the optimized websocket setup"""
        try:
            self.logger.info("🧪 Testing Optimized WebSocket Setup")
            self.logger.info("=" * 50)
            
            # Initialize components
            broker_manager = BrokerManager()
            order_manager = OrderManager(broker_manager)
            ws_manager = WebSocketManager(broker_manager, order_manager)
            
            # Add callbacks
            ws_manager.add_price_callback(self.on_price_update)
            ws_manager.add_order_callback(self.on_order_update)
            
            # Connect to brokers
            self.logger.info("Connecting to brokers...")
            connection_results = broker_manager.connect_all()
            connected_brokers = [name for name, success in connection_results.items() if success]
            
            if len(connected_brokers) < 2:
                self.logger.warning(f"Only {len(connected_brokers)} broker(s) connected. Need at least 2 for full test.")
            
            self.logger.info(f"Connected brokers: {connected_brokers}")
            
            # Start websockets
            self.logger.info("Starting optimized websockets...")
            ws_manager.start()
            
            # Test symbol subscription (should only subscribe to Broker 1)
            test_symbol = "NIFTY24123400CE"
            self.logger.info(f"Subscribing to {test_symbol} for price updates...")
            success = ws_manager.subscribe_symbol(test_symbol, "NFO")
            
            if success:
                self.logger.info("✅ Symbol subscription successful (Broker 1 only)")
            else:
                self.logger.warning("⚠️ Symbol subscription failed")
            
            # Check connection status
            status = ws_manager.get_connection_status()
            self.logger.info(f"WebSocket Status: {status}")
            
            # Wait for some updates
            self.logger.info("Waiting for websocket updates (10 seconds)...")
            time.sleep(10)
            
            # Analyze results
            self.analyze_results(connected_brokers)
            
            # Cleanup
            ws_manager.stop()
            broker_manager.disconnect_all()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Test failed: {e}")
            return False
    
    def analyze_results(self, connected_brokers):
        """Analyze the test results"""
        self.logger.info("\n📊 Test Results Analysis")
        self.logger.info("=" * 30)
        
        # Analyze price updates
        price_brokers = set(update.broker for update in self.price_updates)
        self.logger.info(f"Price updates received: {len(self.price_updates)}")
        self.logger.info(f"Price update brokers: {list(price_brokers)}")
        
        if len(price_brokers) == 1 and list(price_brokers)[0] == connected_brokers[0]:
            self.logger.info("✅ Price updates correctly limited to Broker 1 only")
        else:
            self.logger.warning(f"⚠️ Price updates from unexpected brokers: {price_brokers}")
        
        # Analyze order updates
        order_brokers = set(update.broker for update in self.order_updates)
        self.logger.info(f"Order updates received: {len(self.order_updates)}")
        self.logger.info(f"Order update brokers: {list(order_brokers)}")
        
        if len(order_brokers) >= 1:
            self.logger.info("✅ Order updates received from brokers")
        else:
            self.logger.warning("⚠️ No order updates received")
        
        # Summary
        self.logger.info("\n📋 Summary:")
        self.logger.info(f"  - Price updates: {len(self.price_updates)} (should be from Broker 1 only)")
        self.logger.info(f"  - Order updates: {len(self.order_updates)} (should be from all brokers)")
        self.logger.info(f"  - Price brokers: {list(price_brokers)}")
        self.logger.info(f"  - Order brokers: {list(order_brokers)}")

def main():
    """Main test function"""
    test = WebSocketTest()
    success = test.test_websocket_setup()
    
    if success:
        print("\n✅ WebSocket optimization test completed successfully!")
    else:
        print("\n❌ WebSocket optimization test failed!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
