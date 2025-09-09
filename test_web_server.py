#!/usr/bin/env python3
"""
Test script for Duplicator Trading Bot Web Server
Verifies that the web server starts correctly and basic functionality works
"""

import requests
import time
import json
import sys
from pathlib import Path

def test_web_server(base_url="http://localhost:8000", timeout=10):
    """Test basic web server functionality"""
    
    print("🧪 Testing Duplicator Trading Bot Web Server...")
    print(f"📍 Testing URL: {base_url}")
    print()
    
    tests_passed = 0
    tests_total = 0
    
    def run_test(test_name, test_func):
        nonlocal tests_passed, tests_total
        tests_total += 1
        try:
            print(f"🔍 {test_name}...", end=" ")
            result = test_func()
            if result:
                print("✅ PASSED")
                tests_passed += 1
            else:
                print("❌ FAILED")
        except Exception as e:
            print(f"❌ FAILED - {e}")
    
    # Test 1: Health Check
    def test_health():
        response = requests.get(f"{base_url}/api/health", timeout=timeout)
        return response.status_code == 200 and "status" in response.json()
    
    # Test 2: Orders API
    def test_orders():
        response = requests.get(f"{base_url}/api/orders", timeout=timeout)
        return response.status_code == 200 and "orders" in response.json()
    
    # Test 3: Active Orders API
    def test_active_orders():
        response = requests.get(f"{base_url}/api/orders/active", timeout=timeout)
        return response.status_code == 200 and "orders" in response.json()
    
    # Test 4: Brokers API
    def test_brokers():
        response = requests.get(f"{base_url}/api/brokers", timeout=timeout)
        return response.status_code == 200 and "brokers" in response.json()
    
    # Test 5: Positions API
    def test_positions():
        response = requests.get(f"{base_url}/api/positions", timeout=timeout)
        return response.status_code == 200
    
    # Test 6: Main Page
    def test_main_page():
        response = requests.get(f"{base_url}/", timeout=timeout)
        return response.status_code == 200 and "Duplicator Trading Bot" in response.text
    
    # Test 7: Order Placement (should fail gracefully without proper data)
    def test_order_placement():
        order_data = {
            "symbol": "TEST",
            "order_type": "BUY",
            "quantity": 1,
            "price": 100.0
        }
        response = requests.post(f"{base_url}/api/orders", 
                               json=order_data, 
                               timeout=timeout)
        # Should return 500 or 200 depending on broker connection
        return response.status_code in [200, 500]
    
    # Run all tests
    run_test("Health Check", test_health)
    run_test("Orders API", test_orders)
    run_test("Active Orders API", test_active_orders)
    run_test("Brokers API", test_brokers)
    run_test("Positions API", test_positions)
    run_test("Main Page", test_main_page)
    run_test("Order Placement", test_order_placement)
    
    print()
    print("=" * 50)
    print(f"📊 Test Results: {tests_passed}/{tests_total} tests passed")
    
    if tests_passed == tests_total:
        print("🎉 All tests passed! Web server is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the server logs for details.")
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Duplicator Trading Bot Web Server')
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL to test')
    parser.add_argument('--timeout', type=int, default=10, help='Request timeout in seconds')
    
    args = parser.parse_args()
    
    try:
        success = test_web_server(args.url, args.timeout)
        sys.exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to web server")
        print("Make sure the web server is running on the specified URL")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
