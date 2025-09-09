#!/usr/bin/env python3
"""
Simple Unified Launcher for Duplicator Trading Bot
Runs both Telegram bot and Web server interfaces
"""

import asyncio
import threading
import time
import signal
import sys
from pathlib import Path
from typing import Optional
import subprocess

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from src.brokers.broker_manager import BrokerManager
from src.orders.order_manager import OrderManager
from src.telegram.telegram_bot import TelegramBot
from src.websocket.websocket_manager import WebSocketManager
from src.utils.config_manager import config
from src.utils.logger import get_logger


class SimpleUnifiedApp:
    """Simple unified application that runs both interfaces"""
    
    def __init__(self):
        self.logger = get_logger('simple_unified_app')
        self.is_running = False
        self._loop = None
        
        # Initialize components
        self.broker_manager: Optional[BrokerManager] = None
        self.order_manager: Optional[OrderManager] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.websocket_manager: Optional[WebSocketManager] = None
        
        # Threads
        self.telegram_thread = None
        self.web_thread = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False
        self.stop()
    
    def initialize(self) -> bool:
        """Initialize all components"""
        try:
            self.logger.info("Initializing Simple Unified Duplicator Trading Bot...")
            
            # Initialize broker manager
            self.broker_manager = BrokerManager()
            self.logger.info("Broker manager initialized")
            
            # Initialize order manager
            self.order_manager = OrderManager(self.broker_manager)
            self.logger.info("Order manager initialized")
            
            # Initialize websocket manager
            self.websocket_manager = WebSocketManager(self.broker_manager, self.order_manager)
            self.logger.info("Websocket manager initialized")
            
            # Initialize telegram bot
            self.telegram_bot = TelegramBot(self.order_manager, self.broker_manager, self.websocket_manager)
            self.logger.info("Telegram bot initialized")
            
            # Setup callbacks
            self._setup_callbacks()
            
            self.logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}")
            return False
    
    def _setup_callbacks(self) -> None:
        """Setup callbacks between components"""
        try:
            # Add order update callback to websocket manager
            self.websocket_manager.add_order_callback(self._on_order_update)
            
            # Add price update callback to websocket manager
            self.websocket_manager.add_price_callback(self._on_price_update)
            
            self.logger.info("Callbacks setup completed")
            
        except Exception as e:
            self.logger.error(f"Error setting up callbacks: {e}")
    
    def _on_order_update(self, order_update) -> None:
        """Handle order update from websocket"""
        try:
            # Log order update
            self.logger.info(
                f"Order update: {order_update.order_id} - {order_update.status} "
                f"on {order_update.broker} for {order_update.symbol}"
            )
            
            # Send notification to Telegram if significant update
            if order_update.status in ['COMPLETE', 'CANCELLED', 'REJECTED']:
                # Schedule the async task in the event loop
                if hasattr(self, '_loop') and self._loop and not self._loop.is_closed():
                    self._loop.create_task(self._send_order_notification(order_update))
                else:
                    self.logger.warning("Event loop not available for sending order notification")
                
        except Exception as e:
            self.logger.error(f"Error handling order update: {e}")
    
    def _on_price_update(self, price_update) -> None:
        """Handle price update from websocket"""
        try:
            # Log price update (debug level to avoid spam)
            self.logger.debug(
                f"Price update: {price_update.symbol} = ₹{price_update.last_price} "
                f"on {price_update.broker}"
            )
            
            # Update LTP cache in telegram bot
            if self.telegram_bot and hasattr(self.telegram_bot, 'update_ltp_cache'):
                self.telegram_bot.update_ltp_cache(price_update.token, price_update.last_price)
            
        except Exception as e:
            self.logger.error(f"Error handling price update: {e}")
    
    async def _send_order_notification(self, order_update) -> None:
        """Send order notification to Telegram"""
        try:
            if self.telegram_bot:
                # Check if testing mode is enabled
                testing_mode = config.get('orders', {}).get('testing_mode', False)
                
                # Skip REJECTED status notifications during testing (but still log them)
                if order_update.status == 'REJECTED' and testing_mode:
                    self.logger.info(
                        f"Order {order_update.order_id} REJECTED (testing mode - notification skipped): "
                        f"Symbol: {order_update.symbol}, Broker: {order_update.broker}, "
                        f"Qty: {order_update.quantity}, Price: ₹{order_update.price}"
                    )
                    return
                
                # Send notifications for other statuses
                status_emoji = {
                    'COMPLETE': '✅',
                    'CANCELLED': '❌',
                    'REJECTED': '🚫'
                }.get(order_update.status, '❓')
                
                message = (
                    f"{status_emoji} *Order Update*\n\n"
                    f"• Order ID: `{order_update.order_id}`\n"
                    f"• Symbol: {order_update.symbol}\n"
                    f"• Status: {order_update.status}\n"
                    f"• Broker: {order_update.broker}\n"
                    f"• Quantity: {order_update.quantity}\n"
                    f"• Price: ₹{order_update.price}\n"
                    f"• Time: {order_update.timestamp.strftime('%H:%M:%S')}"
                )
                
                await self.telegram_bot.send_notification(message)
                
        except Exception as e:
            self.logger.error(f"Error sending order notification: {e}")
    
    def connect_brokers(self) -> bool:
        """Connect to all configured brokers"""
        try:
            self.logger.info("Connecting to brokers...")
            
            if not self.broker_manager:
                self.logger.error("Broker manager not initialized")
                return False
            
            # Connect to all brokers
            connection_results = self.broker_manager.connect_all()
            
            # Check results
            connected_brokers = [name for name, success in connection_results.items() if success]
            failed_brokers = [name for name, success in connection_results.items() if not success]
            
            if connected_brokers:
                self.logger.info(f"Successfully connected to brokers: {connected_brokers}")
            else:
                self.logger.error("No brokers connected successfully")
                return False
            
            if failed_brokers:
                self.logger.warning(f"Failed to connect to brokers: {failed_brokers}")
            
            return len(connected_brokers) > 0
            
        except Exception as e:
            self.logger.error(f"Error connecting to brokers: {e}")
            return False
    
    def start_websockets(self) -> bool:
        """Start websocket connections"""
        try:
            self.logger.info("Starting websocket connections...")
            
            if not self.websocket_manager:
                self.logger.error("Websocket manager not initialized")
                return False
            
            self.websocket_manager.start()
            self.logger.info("Websocket connections started")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting websockets: {e}")
            return False
    
    def start_telegram_bot_thread(self) -> bool:
        """Start Telegram bot in a separate thread"""
        try:
            self.logger.info("Starting Telegram bot...")
            
            if not self.telegram_bot:
                self.logger.error("Telegram bot not initialized")
                return False
            
            def run_telegram_bot():
                try:
                    # Create new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Run the bot
                    self.telegram_bot.run()
                    
                except Exception as e:
                    self.logger.error(f"Error in Telegram bot thread: {e}")
            
            # Start bot in a separate thread
            self.telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
            self.telegram_thread.start()
            
            self.logger.info("Telegram bot started")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting Telegram bot: {e}")
            return False
    
    def start_web_server_thread(self, host: str = "127.0.0.1", port: int = 8000) -> bool:
        """Start web server in a separate thread"""
        try:
            self.logger.info("Starting web server...")
            
            def run_web_server():
                try:
                    # Import web server here to avoid circular imports
                    from web_server_optimized import TradingWebApp
                    
                    # Create web app with existing components
                    web_app = TradingWebApp()
                    # Replace components with existing ones
                    web_app.broker_manager = self.broker_manager
                    web_app.order_manager = self.order_manager
                    web_app.trading_websocket_manager = self.websocket_manager
                    
                    # Start web server
                    web_app.run(host=host, port=port, reload=False)
                    
                except Exception as e:
                    self.logger.error(f"Error in web server thread: {e}")
            
            # Start web server in a separate thread
            self.web_thread = threading.Thread(target=run_web_server, daemon=True)
            self.web_thread.start()
            
            self.logger.info(f"Web server started on {host}:{port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting web server: {e}")
            return False
    
    def run(self, web_host: str = "127.0.0.1", web_port: int = 8000) -> None:
        """Run the unified application"""
        try:
            self.logger.info("Starting Simple Unified Duplicator Trading Bot...")
            
            # Initialize components
            if not self.initialize():
                self.logger.error("Failed to initialize application")
                return
            
            # Connect to brokers
            if not self.connect_brokers():
                self.logger.error("Failed to connect to brokers")
                return
            
            # Start websockets
            if not self.start_websockets():
                self.logger.error("Failed to start websockets")
                return
            
            # Start Telegram bot in thread
            if not self.start_telegram_bot_thread():
                self.logger.error("Failed to start Telegram bot")
                return
            
            # Start web server in thread
            if not self.start_web_server_thread(web_host, web_port):
                self.logger.error("Failed to start web server")
                return
            
            self.is_running = True
            self.logger.info("Simple Unified Duplicator Trading Bot started successfully!")
            self.logger.info(f"🌐 Web Interface: http://{web_host}:{web_port}")
            self.logger.info("📱 Telegram Bot: Active and ready for commands")
            
            # Send startup notification
            asyncio.run(self._send_startup_notification())
            
            # Main loop
            self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Error in main application: {e}")
        finally:
            self.stop()
    
    def _main_loop(self) -> None:
        """Main application loop"""
        try:
            while self.is_running:
                # Check system health
                self._check_system_health()
                
                # Cleanup old orders periodically
                if self.order_manager:
                    self.order_manager.cleanup_old_orders(days=7)
                
                # Sleep for a short interval
                time.sleep(10)
                
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
    
    def _check_system_health(self) -> None:
        """Check system health and log status"""
        try:
            # Check broker connections
            broker_status = self.broker_manager.get_health_status() if self.broker_manager else {}
            connected_brokers = sum(1 for status in broker_status.values() if status)
            total_brokers = len(broker_status)
            
            # Check websocket status
            ws_status = self.websocket_manager.get_connection_status() if self.websocket_manager else {}
            
            # Log health status periodically
            if hasattr(self, '_last_health_log'):
                if time.time() - self._last_health_log > 300:  # Every 5 minutes
                    self.logger.info(
                        f"Health check: {connected_brokers}/{total_brokers} brokers connected, "
                        f"WebSocket running: {ws_status.get('is_running', False)}, "
                        f"Telegram: Active, Web: Active"
                    )
                    self._last_health_log = time.time()
            else:
                self._last_health_log = time.time()
            
            # Check for critical issues
            if connected_brokers == 0:
                self.logger.critical("No brokers connected! Attempting reconnection...")
                self.connect_brokers()
                
        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
    
    async def _send_startup_notification(self) -> None:
        """Send startup notification to Telegram"""
        try:
            if self.telegram_bot:
                broker_status = self.broker_manager.get_health_status() if self.broker_manager else {}
                connected_brokers = [name for name, status in broker_status.items() if status]
                
                message = (
                    f"🚀 *Simple Unified Duplicator Bot Started*\n\n"
                    f"• Connected Brokers: {len(connected_brokers)}\n"
                    f"• Brokers: {', '.join(connected_brokers)}\n"
                    f"• Telegram Bot: ✅ Active\n"
                    f"• Web Interface: ✅ Active\n"
                    f"• Status: Online\n"
                    f"• Time: {time.strftime('%H:%M:%S')}"
                )
                
                await self.telegram_bot.send_notification(message)
                
        except Exception as e:
            self.logger.error(f"Error sending startup notification: {e}")
    
    def stop(self) -> None:
        """Stop the application"""
        try:
            self.logger.info("Stopping Simple Unified Duplicator Trading Bot...")
            self.is_running = False
            
            # Stop websockets
            if self.websocket_manager:
                self.websocket_manager.stop()
                self.logger.info("Websockets stopped")
            
            # Disconnect brokers
            if self.broker_manager:
                self.broker_manager.disconnect_all()
                self.logger.info("Brokers disconnected")
            
            self.logger.info("Simple Unified Duplicator Trading Bot stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping application: {e}")


def main():
    """Main entry point"""
    print("🚀 Starting Simple Unified Duplicator Trading Bot...")
    print("📱 Telegram Bot: Active")
    print("🌐 Web Interface: http://localhost:8000")
    print("Press Ctrl+C to stop both services")
    print()
    
    app = SimpleUnifiedApp()
    app.run()


if __name__ == "__main__":
    main()
