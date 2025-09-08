"""
Main entry point for the Order Executor trading bot.
This modular version uses separate modules for different functionalities.
"""

from config import Config
from api_client import APIClient
from trade_logger import TradeLogger
from trading_engine import TradingEngine
from websocket_handler import WebSocketHandler
from telegram_bot import TelegramBot


def main():
    """Main function to initialize and start the trading bot."""
    print("🚀 Starting Order Executor Trading Bot...")
    
    try:
        # Initialize configuration
        print("📋 Loading configuration...")
        config = Config()
        
        # Initialize API client
        print("🔌 Initializing API client...")
        api_client = APIClient(config)
        
        # Login to Shoonya
        print("🔐 Logging into Shoonya...")
        success, client_name = api_client.login()
        if not success:
            print("❌ Failed to login to Shoonya API")
            return
        
        # Initialize trade logger
        print("📊 Initializing trade logger...")
        trade_logger = TradeLogger(config.LOG_FILE)
        
        # Initialize trading engine
        print("⚙️ Initializing trading engine...")
        trading_engine = TradingEngine(config, api_client, trade_logger)
        
        # Initialize websocket handler
        print("🌐 Initializing websocket handler...")
        websocket_handler = WebSocketHandler(trading_engine)
        
        # Start websocket feed
        print("📡 Starting websocket feed...")
        if not websocket_handler.start_websocket(api_client):
            print("❌ Failed to start websocket feed")
            return
        
        # Initialize and start telegram bot
        print("🤖 Initializing Telegram bot...")
        telegram_bot = TelegramBot(config, api_client, trading_engine)
        
        print("✅ All systems initialized successfully!")
        print(f"👤 Logged in as: {client_name}")
        print("🎯 Bot is ready to accept trades!")
        print("=" * 50)
        
        # Start the telegram bot (this will block)
        telegram_bot.start_bot()
        
    except FileNotFoundError as e:
        print(f"❌ Configuration error: {e}")
        print("💡 Make sure 'credentials.json' exists with proper credentials")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("💡 Check your configuration and try again")


if __name__ == "__main__":
    main()