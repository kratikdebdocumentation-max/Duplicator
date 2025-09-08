"""
Configuration module for the Order Executor trading bot.
Handles loading and managing configuration settings.
"""

import json
import os
from typing import Dict, Any


class Config:
    """Configuration class for the trading bot."""
    
    def __init__(self):
        """Initialize configuration by loading from credentials.json."""
        self.credentials_file = "config.json"
        self.load_credentials()
        
        # Trading configuration
        self.DEFAULT_PRODUCT_TYPE = "I"  # Default to Intraday (I) to match working code
        self.LOG_FILE = "trade_log.csv"
        
        # Conversation state constants (must be strings for ConversationHandler)
        self.ASK_CAPITAL = "ASK_CAPITAL"
        self.ASK_SL = "ASK_SL"
        self.ASK_TARGET = "ASK_TARGET"
        self.READY = "READY"
        self.ORDER_TYPE_SELECTION = "ORDER_TYPE_SELECTION"
        self.LIMIT_PRICE_INPUT = "LIMIT_PRICE_INPUT"
        self.TRADE_SELECTION = "TRADE_SELECTION"
        self.MODIFY_OPTIONS = "MODIFY_OPTIONS"
        self.MODIFY_SL = "MODIFY_SL"
        self.MODIFY_TARGET = "MODIFY_TARGET"
        self.MODIFY_ENTRY_PRICE = "MODIFY_ENTRY_PRICE"
        
        # Order status constants
        self.ORDER_PENDING = "PENDING"
        self.ORDER_CANCELED = "CANCELED"
        self.ORDER_OPEN = "OPEN"
        self.ORDER_REJECTED = "REJECTED"
        self.ORDER_COMPLETE = "COMPLETE"
        self.ORDER_TRIGGER_PENDING = "TRIGGER_PENDING"
        self.ORDER_INVALID_STATUS = "INVALID_STATUS_TYPE"
        
        # Order report type constants
        self.REPORT_NEW_ACK = "NewAck"
        self.REPORT_MOD_ACK = "ModAck"
        self.REPORT_CAN_ACK = "CanAck"
        self.REPORT_PENDING_NEW = "PendingNew"
        self.REPORT_PENDING_REPLACE = "PendingReplace"
        self.REPORT_PENDING_CANCEL = "PendingCancel"
        self.REPORT_NEW = "New"
        self.REPORT_REPLACED = "Replaced"
        self.REPORT_CANCELED = "Canceled"
        self.REPORT_FILL = "Fill"
        self.REPORT_REJECTED = "Rejected"
        self.REPORT_REPLACE_REJECTED = "ReplaceRejected"
        self.REPORT_CANCEL_REJECTED = "CancelRejected"
        self.REPORT_INVALID_TYPE = "INVALID_REPORT_TYPE"
        
        # Feature flags (boolean)
        self.DEBUG = False  # Debug mode
        self.VERBOSE = False  # Verbose logging
        self.SYMBOL_SEARCH = True  # Symbol search enabled
        self.MANUAL_EXIT = True  # Manual exit enabled
        self.SL_INPUT = True  # Stop loss input enabled
        self.TARGET_INPUT = True  # Target input enabled
        self.QUANTITY_INPUT = True  # Quantity input enabled
        self.EXCHANGE_INPUT = True  # Exchange input enabled
        self.SYMBOL_INPUT = True  # Symbol input enabled
        self.STATISTICS_VIEW = True  # Statistics view enabled
        self.ACTIVE_TRADES_VIEW = True  # Active trades view enabled
        self.SL_MODIFY = True  # Stop loss modification enabled
        self.TARGET_MODIFY = True  # Target modification enabled
        self.CANCEL_ORDER = True  # Cancel order enabled
        self.ORDER_HISTORY = True  # Order history enabled
        
        # Active trades and LTP tracking
        self.active_trades = {}
        self.last_ltp = {}
    
    def load_credentials(self):
        """Load credentials from credentials.json file."""
        try:
            # Check if file exists
            if not os.path.exists(self.credentials_file):
                print(f"❌ Credentials file '{self.credentials_file}' not found in current directory: {os.getcwd()}")
                print("💡 Please create a 'config.json' file with the following structure:")
                print("""
{
    "username": "YOUR_USERNAME",
    "pwd": "YOUR_PASSWORD", 
    "factor2": "YOUR_2FA_CODE",
    "vc": "YOUR_VENDOR_CODE",
    "app_key": "YOUR_API_SECRET",
    "imei": "YOUR_IMEI",
    "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "default_product_type": "MIS"
}
                """)
                raise FileNotFoundError(f"Credentials file '{self.credentials_file}' not found")
            
            with open(self.credentials_file, 'r') as f:
                creds = json.load(f)
            
            # Load API credentials
            self.USER_ID = creds.get("username")
            self.PASSWORD = creds.get("pwd")
            self.twoFA = creds.get("factor2")
            self.VENDOR_CODE = creds.get("vc")
            self.API_SECRET = creds.get("app_key")
            self.IMEI = creds.get("imei")
            
            
            # Load Telegram bot credentials
            self.TELEGRAM_BOT_TOKEN = creds.get("telegram_bot_token")
            self.TELEGRAM_CHAT_ID = creds.get("telegram_chat_id")
            
            # Load trading configuration
            self.DEFAULT_PRODUCT_TYPE = creds.get("default_product_type", "I")
            
            # Validate required fields
            required_fields = ["username", "pwd", "factor2", "vc", "app_key", "imei"]
            field_mapping = {
                "username": "USER_ID",
                "pwd": "PASSWORD", 
                "factor2": "twoFA",
                "vc": "VENDOR_CODE",
                "app_key": "API_SECRET",
                "imei": "IMEI"
            }
            missing_fields = [field for field in required_fields if not getattr(self, field_mapping[field], None)]
            
            if missing_fields:
                print(f"❌ Missing required credentials in {self.credentials_file}: {', '.join(missing_fields)}")
                print("💡 Please check your config.json file and ensure all required fields are present.")
                raise ValueError(f"Missing required credentials: {', '.join(missing_fields)}")
                
        except FileNotFoundError as e:
            raise e
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in credentials file: {e}")
            print("💡 Please check the JSON format of your config.json file.")
            raise ValueError(f"Invalid JSON in credentials file: {e}")
        except Exception as e:
            print(f"❌ Error loading credentials: {e}")
            raise ValueError(f"Error loading credentials: {e}")
    
    def get_telegram_config(self):
        """Get Telegram bot configuration."""
        return {
            "bot_token": self.TELEGRAM_BOT_TOKEN,
            "chat_id": self.TELEGRAM_CHAT_ID
        }
    
    @property
    def BOT_TOKEN(self):
        """Get Telegram bot token."""
        return self.TELEGRAM_BOT_TOKEN
    
    @property
    def CHAT_ID(self):
        """Get Telegram chat ID."""
        return self.TELEGRAM_CHAT_ID
    
    def update_product_type(self, product_type: str):
        """Update the default product type (MIS or CNC)."""
        if product_type.upper() in ["MIS", "CNC"]:
            self.DEFAULT_PRODUCT_TYPE = product_type.upper()
        else:
            raise ValueError("Product type must be 'MIS' or 'CNC'")
