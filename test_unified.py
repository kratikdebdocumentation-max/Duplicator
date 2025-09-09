#!/usr/bin/env python3
"""
Test script for Unified Duplicator Trading Bot
Verifies that both Telegram and Web interfaces work together
"""

import requests
import time
import json
import sys
from pathlib import Path

def test_unified_setup(base_url="http://localhost:8000", timeout=10):
    """Test unified setup functionality"""
    
    print("🧪 Testing Unified Duplicator Trading Bot...")
    print(f"📍 Testing Web URL: {base_url}")
    print("📱 Telegram Bot: (Manual test required)")
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
    
    # Test 1: Web Server Health
    def test_web_health():
        response = requests.get(f"{base_url}/api/health", timeout=timeout)
        data = response.json()
        return response.status_code == 200 and "status" in data
    
    # Test 2: Web Server Orders API
    def test_web_orders():
        response = requests.get(f"{base_url}/api/orders", timeout=timeout)
        return response.status_code == 200 and "orders" in response.json()
    
    # Test 3: Web Server Brokers API
    def test_web_brokers():
        response = requests.get(f"{base_url}/api/brokers", timeout=timeout)
        return response.status_code == 200 and "brokers" in response.json()
    
    # Test 4: Web Server Main Page
    def test_web_main_page():
        response = requests.get(f"{base_url}/", timeout=timeout)
        return response.status_code == 200 and "Duplicator Trading Bot" in response.text
    
    # Test 5: Web Server WebSocket (basic check)
    def test_web_websocket():
        try:
            import websocket
            ws = websocket.create_connection(f"ws://localhost:8000/ws", timeout=5)
            ws.close()
            return True
        except:
            return False
    
    # Test 6: Configuration Files
    def test_config_files():
        config_file = Path("config/config.yaml")
        credentials1 = Path("credentials1.json")
        credentials2 = Path("credentials2.json")
        return config_file.exists() and credentials1.exists() and credentials2.exists()
    
    # Test 7: Source Files
    def test_source_files():
        main_py = Path("main.py")
        start_both_py = Path("start_both.py")
        web_server_py = Path("web_server_optimized.py")
        return main_py.exists() and start_both_py.exists() and web_server_py.exists()
    
    # Run all tests
    run_test("Web Server Health", test_web_health)
    run_test("Web Server Orders API", test_web_orders)
    run_test("Web Server Brokers API", test_web_brokers)
    run_test("Web Server Main Page", test_web_main_page)
    run_test("Web Server WebSocket", test_web_websocket)
    run_test("Configuration Files", test_config_files)
    run_test("Source Files", test_source_files)
    
    print()
    print("=" * 60)
    print(f"📊 Test Results: {tests_passed}/{tests_total} tests passed")
    
    if tests_passed == tests_total:
        print("🎉 All tests passed! Unified setup is working correctly.")
        print()
        print("📱 Telegram Bot Test:")
        print("   1. Send /start to your bot")
        print("   2. Send /status to check bot health")
        print("   3. Send /orders to see active orders")
        print()
        print("🌐 Web Interface Test:")
        print(f"   1. Open {base_url} in your browser")
        print("   2. Check the dashboard loads")
        print("   3. Try placing a test order")
        return True
    else:
        print("⚠️  Some tests failed. Check the server logs for details.")
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Unified Duplicator Trading Bot')
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL to test')
    parser.add_argument('--timeout', type=int, default=10, help='Request timeout in seconds')
    
    args = parser.parse_args()
    
    try:
        success = test_unified_setup(args.url, args.timeout)
        sys.exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to web server")
        print("Make sure the unified application is running:")
        print("python start_both.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
