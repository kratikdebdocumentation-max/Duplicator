#!/usr/bin/env python3
"""
Performance test for ultra-fast order execution
Tests parallel order placement speed and measures execution times
"""

import asyncio
import time
import requests
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import statistics

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from src.brokers.broker_manager import BrokerManager
from src.orders.order_manager import OrderManager
from src.brokers.base_broker import OrderRequest, OrderType, ProductType, PriceType
from src.utils.logger import get_logger

class OrderSpeedTest:
    """Test class for measuring order execution speed"""
    
    def __init__(self):
        self.logger = get_logger('speed_test')
        self.execution_times = []
        
    def test_parallel_order_speed(self):
        """Test parallel order execution speed"""
        try:
            self.logger.info("🚀 Testing Ultra-Fast Parallel Order Execution")
            self.logger.info("=" * 60)
            
            # Initialize components
            broker_manager = BrokerManager()
            order_manager = OrderManager(broker_manager)
            
            # Connect to brokers
            self.logger.info("Connecting to brokers...")
            connection_results = broker_manager.connect_all()
            connected_brokers = [name for name, success in connection_results.items() if success]
            
            if len(connected_brokers) < 2:
                self.logger.warning(f"Only {len(connected_brokers)} broker(s) connected. Need at least 2 for full test.")
                return False
            
            self.logger.info(f"Connected brokers: {connected_brokers}")
            
            # Test multiple orders
            test_orders = [
                {
                    "symbol": "NIFTY24123400CE",
                    "order_type": OrderType.BUY,
                    "quantity": 25,
                    "price": 100.0
                },
                {
                    "symbol": "BANKNIFTY24123400PE", 
                    "order_type": OrderType.SELL,
                    "quantity": 15,
                    "price": 150.0
                },
                {
                    "symbol": "NIFTY24123400PE",
                    "order_type": OrderType.BUY,
                    "quantity": 50,
                    "price": 80.0
                }
            ]
            
            # Test sequential vs parallel execution
            self.logger.info("\n📊 Testing Sequential vs Parallel Execution")
            self.logger.info("-" * 50)
            
            # Sequential execution test
            sequential_times = self._test_sequential_execution(broker_manager, test_orders)
            
            # Parallel execution test
            parallel_times = self._test_parallel_execution(broker_manager, test_orders)
            
            # Analyze results
            self._analyze_results(sequential_times, parallel_times)
            
            # Test web API speed
            self._test_web_api_speed()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Test failed: {e}")
            return False
    
    def _test_sequential_execution(self, broker_manager, test_orders):
        """Test sequential order execution"""
        self.logger.info("Testing Sequential Execution...")
        times = []
        
        for i, order_data in enumerate(test_orders):
            start_time = time.time()
            
            order_request = OrderRequest(
                buy_or_sell=order_data["order_type"],
                product_type=ProductType.INTRADAY,
                exchange="NFO",
                tradingsymbol=order_data["symbol"],
                quantity=order_data["quantity"],
                price_type=PriceType.LIMIT,
                price=order_data["price"]
            )
            
            # Sequential execution (old method)
            results = {}
            connected_brokers = broker_manager.get_connected_brokers()
            for name, broker in connected_brokers.items():
                try:
                    response = broker.place_order(order_request)
                    results[name] = response
                except Exception as e:
                    results[name] = None
            
            execution_time = (time.time() - start_time) * 1000
            times.append(execution_time)
            self.logger.info(f"  Order {i+1}: {execution_time:.2f}ms")
        
        return times
    
    def _test_parallel_execution(self, broker_manager, test_orders):
        """Test parallel order execution"""
        self.logger.info("Testing Parallel Execution...")
        times = []
        
        for i, order_data in enumerate(test_orders):
            start_time = time.time()
            
            order_request = OrderRequest(
                buy_or_sell=order_data["order_type"],
                product_type=ProductType.INTRADAY,
                exchange="NFO",
                tradingsymbol=order_data["symbol"],
                quantity=order_data["quantity"],
                price_type=PriceType.LIMIT,
                price=order_data["price"]
            )
            
            # Parallel execution (new method)
            results = broker_manager.place_order_all(order_request)
            
            execution_time = (time.time() - start_time) * 1000
            times.append(execution_time)
            self.logger.info(f"  Order {i+1}: {execution_time:.2f}ms")
        
        return times
    
    def _test_web_api_speed(self):
        """Test web API order placement speed"""
        self.logger.info("\n🌐 Testing Web API Speed...")
        self.logger.info("-" * 30)
        
        # Test order data
        test_order = {
            "symbol": "NIFTY24123400CE",
            "order_type": "BUY",
            "quantity": 25,
            "price": 100.0,
            "exchange": "NFO",
            "product_type": "INTRADAY",
            "price_type": "LIMIT"
        }
        
        api_times = []
        
        for i in range(3):  # Test 3 API calls
            try:
                start_time = time.time()
                
                response = requests.post(
                    "http://127.0.0.1:8000/api/orders",
                    json=test_order,
                    timeout=10
                )
                
                execution_time = (time.time() - start_time) * 1000
                api_times.append(execution_time)
                
                if response.status_code == 200:
                    result = response.json()
                    self.logger.info(f"  API Call {i+1}: {execution_time:.2f}ms (Success: {result.get('success', False)})")
                else:
                    self.logger.warning(f"  API Call {i+1}: {execution_time:.2f}ms (Failed: {response.status_code})")
                    
            except Exception as e:
                self.logger.error(f"  API Call {i+1}: Error - {e}")
        
        if api_times:
            avg_api_time = statistics.mean(api_times)
            self.logger.info(f"  Average API Time: {avg_api_time:.2f}ms")
    
    def _analyze_results(self, sequential_times, parallel_times):
        """Analyze and display test results"""
        self.logger.info("\n📈 Performance Analysis")
        self.logger.info("=" * 30)
        
        if not sequential_times or not parallel_times:
            self.logger.warning("Insufficient data for analysis")
            return
        
        # Calculate statistics
        seq_avg = statistics.mean(sequential_times)
        par_avg = statistics.mean(parallel_times)
        speedup = seq_avg / par_avg if par_avg > 0 else 0
        
        # Display results
        self.logger.info(f"Sequential Average: {seq_avg:.2f}ms")
        self.logger.info(f"Parallel Average:   {par_avg:.2f}ms")
        self.logger.info(f"Speed Improvement: {speedup:.2f}x faster")
        
        # Performance rating
        if par_avg < 100:
            rating = "🚀 ULTRA-FAST"
        elif par_avg < 500:
            rating = "⚡ FAST"
        elif par_avg < 1000:
            rating = "✅ GOOD"
        else:
            rating = "⚠️ SLOW"
        
        self.logger.info(f"Performance Rating: {rating}")
        
        # Recommendations
        self.logger.info("\n💡 Recommendations:")
        if speedup > 2:
            self.logger.info("  ✅ Parallel execution provides significant speedup")
        if par_avg < 200:
            self.logger.info("  ✅ Execution speed is excellent for options trading")
        if par_avg > 1000:
            self.logger.info("  ⚠️ Consider optimizing broker connections")
        
        self.logger.info(f"\n🎯 Target for Options Trading: <200ms")
        self.logger.info(f"📊 Your Performance: {par_avg:.1f}ms")

def main():
    """Main test function"""
    test = OrderSpeedTest()
    success = test.test_parallel_order_speed()
    
    if success:
        print("\n✅ Order speed test completed successfully!")
    else:
        print("\n❌ Order speed test failed!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
