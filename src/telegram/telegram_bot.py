"""
Telegram Bot for Duplicator Trading Bot
Provides interactive commands for order placement and management
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re
import calendar
import requests
import os

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
    from telegram.constants import ParseMode
except ImportError:
    print("Warning: python-telegram-bot not found. Please install it.")
    Update = None
    Application = None

from ..brokers.base_broker import OrderType, ProductType, PriceType
from ..orders.order_manager import OrderManager
from ..brokers.broker_manager import BrokerManager
from ..utils.config_manager import config
from ..utils.logger import get_logger


class TelegramBot:
    """Telegram bot for Duplicator trading system"""
    
    def __init__(self, order_manager: OrderManager, broker_manager: BrokerManager, websocket_manager=None):
        self.order_manager = order_manager
        self.broker_manager = broker_manager
        self.websocket_manager = websocket_manager
        self.logger = get_logger('telegram_bot')
        
        # Get Telegram configuration
        telegram_config = config.get_telegram_config()
        self.bot_token = telegram_config.get('bot_token')
        self.chat_id = telegram_config.get('chat_id')
        self.sos_chat_id = telegram_config.get('sos_chat_id')
        
        if not self.bot_token:
            raise ValueError("Telegram bot token not configured")
        
        # Callback for initial LTP from websocket
        self.initial_ltp_callbacks = {}
        
        # Set up websocket callback if websocket manager is available
        if self.websocket_manager:
            self.websocket_manager.add_price_callback(self.handle_websocket_data)
        
        self.application = None
        self._setup_bot()
    
    def download_symbol_files(self) -> bool:
        """Download symbol files from exchange using zip files"""
        try:
            import zipfile
            
            root = 'https://api.shoonya.com/'
            masters = ['NSE_symbols.txt.zip', 'NFO_symbols.txt.zip', 'MCX_symbols.txt.zip', 'BFO_symbols.txt.zip']
            current_date = datetime.now().strftime("_%Y-%m-%d")
            
            downloaded_files = []
            
            for zip_file in masters:
                base_name = zip_file.replace('.zip', '')
                todays_file = f"data/{base_name}{current_date}.txt"
                
                if os.path.exists(todays_file):
                    self.logger.info(f"File for today already exists: {todays_file}. Skipping download.")
                    downloaded_files.append(todays_file)
                    continue
                
                self.logger.info(f'Downloading {zip_file}')
                url = root + zip_file
                try:
                    r = requests.get(url, allow_redirects=True, timeout=30)
                    r.raise_for_status()
                    
                    with open(zip_file, 'wb') as f:
                        f.write(r.content)
                    
                    with zipfile.ZipFile(zip_file, 'r') as z:
                        z.extractall('data/')
                        extracted_file = z.namelist()[0]
                        os.rename(f"data/{extracted_file}", todays_file)
                        downloaded_files.append(todays_file)
                        self.logger.info(f"Extracted and renamed to: {todays_file}")
                        
                except requests.exceptions.RequestException as e:
                    self.logger.warning(f"Error downloading {zip_file}: {e}")
                except zipfile.BadZipFile:
                    self.logger.warning(f"Error extracting {zip_file}: Invalid zip file")
                except Exception as e:
                    self.logger.warning(f"An unexpected error occurred with {zip_file}: {e}")
                finally:
                    if os.path.exists(zip_file):
                        os.remove(zip_file)
                        self.logger.info(f'Removed: {zip_file}')
            
            return len(downloaded_files) > 0
            
        except Exception as e:
            self.logger.error(f"Error downloading symbol files: {e}")
            return False
    
    def find_expiry_dates(self, instrument: str) -> Dict[str, str]:
        """Find current and next expiry dates for the given instrument using actual exchange data"""
        import glob
        
        # Find the latest files based on today's date
        date_str = datetime.today().strftime('%Y-%m-%d')
        
        nfo_files = glob.glob(f'data/NFO_symbols.txt_{date_str}.txt')
        mcx_files = glob.glob(f'data/MCX_symbols.txt_{date_str}.txt')
        bfo_files = glob.glob(f'data/BFO_symbols.txt_{date_str}.txt')
        
        # If no files found, try to download them
        if not nfo_files and not bfo_files and not mcx_files:
            self.logger.info("Symbol files not found, attempting to download...")
            if not self.download_symbol_files():
                self.logger.error("Failed to download symbol files from exchange")
                return {
                    "current": None,
                    "next": None,
                    "current_date": None,
                    "next_date": None,
                    "error": "Expiry dates cannot be extracted from internet. Please try again later or contact support."
                }
            
            # Try to find files again after download
            nfo_files = glob.glob(f'data/NFO_symbols.txt_{date_str}.txt')
            mcx_files = glob.glob(f'data/MCX_symbols.txt_{date_str}.txt')
            bfo_files = glob.glob(f'data/BFO_symbols.txt_{date_str}.txt')
        
        # Initialize sets to hold expiry dates
        finnifty_dates = set()
        nifty_dates = set()
        banknifty_dates = set()
        midcpnifty_dates = set()
        crude_dates = set()
        sensex_dates = set()
        bankex_dates = set()
        
        # Process NFO files
        for nfo_file in nfo_files:
            try:
                with open(nfo_file, 'r', encoding='utf-8') as file:
                    for line in file:
                        values = line.strip().split(',')
                        if len(values) > 5:
                            if values[3] == 'FINNIFTY':
                                finnifty_dates.add(values[5])
                            elif values[3] == 'NIFTY':
                                nifty_dates.add(values[5])
                            elif values[3] == 'BANKNIFTY':
                                banknifty_dates.add(values[5])
                            elif values[3] == 'MIDCPNIFTY':
                                midcpnifty_dates.add(values[5])
            except Exception as e:
                self.logger.warning(f"Error reading NFO file {nfo_file}: {e}")
        
        # Process MCX files
        for mcx_file in mcx_files:
            try:
                with open(mcx_file, 'r', encoding='utf-8') as file:
                    for line in file:
                        values = line.strip().split(',')
                        if len(values) > 6:
                            if values[4] == 'CRUDEOIL':
                                crude_dates.add(values[6])
            except Exception as e:
                self.logger.warning(f"Error reading MCX file {mcx_file}: {e}")
        
        # Process BFO files
        for bfo_file in bfo_files:
            try:
                with open(bfo_file, 'r', encoding='utf-8') as file:
                    for line in file:
                        values = line.strip().split(',')
                        if len(values) > 5:
                            if values[3] == 'BSXOPT':
                                sensex_dates.add(values[5])
                            elif values[3] == 'BKXOPT':
                                bankex_dates.add(values[5])
            except Exception as e:
                self.logger.warning(f"Error reading BFO file {bfo_file}: {e}")
        
        # Convert dates to datetime objects
        finnifty_dates = [datetime.strptime(date, '%d-%b-%Y') for date in finnifty_dates]
        nifty_dates = [datetime.strptime(date, '%d-%b-%Y') for date in nifty_dates]
        banknifty_dates = [datetime.strptime(date, '%d-%b-%Y') for date in banknifty_dates]
        midcpnifty_dates = [datetime.strptime(date, '%d-%b-%Y') for date in midcpnifty_dates]
        crude_dates = [datetime.strptime(date, '%d-%b-%Y') for date in crude_dates]
        sensex_dates = [datetime.strptime(date, '%d-%b-%Y') for date in sensex_dates]
        bankex_dates = [datetime.strptime(date, '%d-%b-%Y') for date in bankex_dates]
        
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        futdate = datetime.today() + timedelta(days=90)  # Increased window to capture next expiry
        
        def find_min_date(dates):
            min_date = None
            for date in dates:
                if date < futdate and date >= today:
                    if min_date is None or date < min_date:
                        min_date = date
            return min_date
        
        def find_next_min_date(dates, first_date):
            next_min_date = None
            for date in dates:
                if date > first_date and date < futdate:
                    if next_min_date is None or date < next_min_date:
                        next_min_date = date
            return next_min_date
        
        def find_next_two_expiries(dates):
            """Find the next two expiry dates"""
            valid_dates = [date for date in dates if today <= date < futdate]
            valid_dates.sort()
            
            if len(valid_dates) >= 2:
                return valid_dates[0], valid_dates[1]
            elif len(valid_dates) == 1:
                return valid_dates[0], None
            else:
                return None, None
        
        # Get the appropriate dates based on instrument
        if instrument == "nifty":
            current_expiry, next_expiry = find_next_two_expiries(nifty_dates)
        elif instrument == "banknifty":
            current_expiry, next_expiry = find_next_two_expiries(banknifty_dates)
        elif instrument == "sensex":
            current_expiry, next_expiry = find_next_two_expiries(sensex_dates)
        else:
            # Fallback to calculated dates
            return self._get_calculated_expiry_dates(instrument)
        
        # If no dates found in files, return error
        if not current_expiry:
            self.logger.error(f"No expiry dates found in symbol files for {instrument}")
            return {
                "current": None,
                "next": None,
                "current_date": None,
                "next_date": None,
                "error": f"Expiry dates cannot be extracted for {instrument.upper()}. Please try again later or contact support."
            }
        
        # Format dates for options symbols
        current_expiry_code = current_expiry.strftime("%d%b%y").upper()
        next_expiry_code = next_expiry.strftime("%d%b%y").upper() if next_expiry else None
        
        return {
            "current": current_expiry_code,
            "next": next_expiry_code,
            "current_date": current_expiry.strftime("%d %B %Y"),
            "next_date": next_expiry.strftime("%d %B %Y") if next_expiry else None
        }
    
    def get_current_price(self, instrument: str) -> float:
        """Get current price for the given instrument from broker"""
        self.logger.info(f"Getting current price for {instrument}")
        
        # Fallback prices for testing - use these first to avoid broker issues
        fallback_prices = {
            "nifty": 25000.0,
            "banknifty": 50000.0,
            "sensex": 80710.76
        }
        
        fallback_price = fallback_prices.get(instrument.lower())
        if fallback_price:
            self.logger.warning(f"Using fallback price for {instrument.upper()}: {fallback_price}")
            return fallback_price
        
        # If no fallback available, try broker
        try:
            # Get the current price from broker1 (assuming both brokers have same data)
            broker = self.broker_manager.get_broker('broker1')
            if broker and hasattr(broker, 'get_ltp'):
                # Map instrument names to broker symbols
                symbol_map = {
                    "nifty": "NIFTY",
                    "banknifty": "BANKNIFTY", 
                    "sensex": "SENSEX"
                }
                
                symbol = symbol_map.get(instrument.lower())
                if symbol:
                    current_price = broker.get_ltp(symbol)
                    if current_price:
                        self.logger.info(f"Current {instrument.upper()} price: {current_price}")
                        return float(current_price)
            
            # Throw error if no fallback available
            raise Exception(f"Could not fetch {instrument.upper()} price from broker API")
            
        except Exception as e:
            self.logger.error(f"Error getting {instrument.upper()} price: {e}")
            raise Exception(f"Failed to get {instrument.upper()} price: {str(e)}")

    def convert_sensex_format(self, input_str: str) -> str:
        """Convert SENSEX symbol format for BFO lookup"""
        import calendar
        from datetime import datetime, timedelta
        import re
        
        def is_last_thursday(date):
            """Check if given date is last Thursday of the month."""
            last_day = calendar.monthrange(date.year, date.month)[1]
            last_date = datetime(date.year, date.month, last_day).date()
            
            # Move backwards to find last Thursday
            while last_date.weekday() != 3:  # 3 = Thursday
                last_date -= timedelta(days=1)
            
            return date == last_date
        
        # Handle SENSEX format: SENSEX25JUL88300PE
        if input_str.startswith('SENSEX') and not input_str.startswith('SENSEX50'):
            # Extract the part after SENSEX
            details = input_str[6:]  # Remove 'SENSEX' prefix
            
            # Try to match monthly format first: YYMMM (e.g., 25JUL)
            monthly_match = re.match(r'(\d{2})([A-Z]{3})(\d+)([A-Z]{2})', details)
            if monthly_match:
                year, month_str, strike_price, ce_pe = monthly_match.groups()
                year = int(year)
                month = datetime.strptime(month_str, "%b").month
                # For monthly, we need to find the last Thursday of the month
                last_day = calendar.monthrange(2000 + year, month)[1]
                last_date = datetime(2000 + year, month, last_day).date()
                while last_date.weekday() != 3:  # 3 = Thursday
                    last_date -= timedelta(days=1)
                day = last_date.day
                output = f"SENSEX{year}{month_str}{strike_price}{ce_pe}"
                return output
            
            # Try to match weekly format: YYMMDD (e.g., 250708)
            weekly_match = re.match(r'(\d{2})(\d{2})(\d{2})(\d+)([A-Z]{2})', details)
            if weekly_match:
                year, month, day, strike_price, ce_pe = weekly_match.groups()
                year = int(year)
                month = int(month)
                day = int(day)
                output = f"SENSEX{year}{month}{day:02d}{strike_price}{ce_pe}"
                return output
        
        # If already in correct SENSEX format, return as is
        if input_str.startswith('SENSEX') and not input_str.startswith('SENSEX50'):
            return input_str
        # If it has SENSEX50 prefix, convert to SENSEX
        if input_str.startswith('SENSEX50'):
            return "SENSEX" + input_str[8:]
        
        raise ValueError(f"Invalid SENSEX symbol format: {input_str}")

    def generate_strike_options(self, current_price: float, option_type: str, expiry_code: str) -> List[str]:
        """Generate strike price options around current price"""
        # Round to nearest 100
        rounded_price = round(current_price / 100) * 100
        
        # Generate 7 strike prices around the rounded price
        strikes = []
        for i in range(-3, 4):  # -3, -2, -1, 0, 1, 2, 3
            strike = rounded_price + (i * 100)
            if strike > 0:  # Ensure positive strike price
                strikes.append(f"{strike:,.0f} {option_type}")
        
        return strikes

    def _get_calculated_expiry_dates(self, instrument: str) -> Dict[str, str]:
        """Fallback method to calculate expiry dates when symbol files are not available"""
        today = datetime.now()
        current_month = today.month
        current_year = today.year
        
        # For SENSEX, use Tuesday-based expiry dates (changed from 11th/18th to Tuesdays)
        if instrument == "sensex":
            # Find next Tuesday for weekly expiry
            def next_tuesday(date):
                days_ahead = 1 - date.weekday()  # 1 corresponds to Tuesday
                if days_ahead <= 0:
                    days_ahead += 7
                return date + timedelta(days=days_ahead)
            
            # Find last Tuesday of month for monthly expiry
            def last_tuesday_of_month(year, month):
                if month == 12:
                    next_month = datetime(year + 1, 1, 1)
                else:
                    next_month = datetime(year, month + 1, 1)
                last_day = next_month - timedelta(days=1)
                while last_day.weekday() != 1:  # 1 is Tuesday
                    last_day -= timedelta(days=1)
                return last_day
            
            # Get next Tuesday (weekly expiry)
            current_expiry = next_tuesday(today)
            
            # Get following Tuesday (next weekly expiry)
            next_expiry = current_expiry + timedelta(days=7)
            
            # If we're close to month end, also consider monthly expiry
            monthly_expiry = last_tuesday_of_month(current_year, current_month)
            if today > monthly_expiry:
                # If today is past this month's expiry, get next month's expiry
                next_month = current_month + 1 if current_month < 12 else 1
                next_year = current_year if current_month < 12 else current_year + 1
                monthly_expiry = last_tuesday_of_month(next_year, next_month)
            
            # Use the earlier of weekly or monthly expiry
            if monthly_expiry < current_expiry:
                current_expiry = monthly_expiry
                next_month = current_expiry.month + 1 if current_expiry.month < 12 else 1
                next_year = current_expiry.year if current_expiry.month < 12 else current_expiry.year + 1
                next_expiry = last_tuesday_of_month(next_year, next_month)
        else:
            # For NIFTY and BANKNIFTY, use last Thursday of the month
            last_day = calendar.monthrange(current_year, current_month)[1]
            last_thursday = None
            
            for day in range(last_day, 0, -1):
                date = datetime(current_year, current_month, day)
                if date.weekday() == 3:  # Thursday
                    last_thursday = date
                    break
            
            # If last Thursday has passed, get next month's last Thursday
            if last_thursday and last_thursday < today:
                next_month = current_month + 1 if current_month < 12 else 1
                next_year = current_year if current_month < 12 else current_year + 1
                
                last_day_next = calendar.monthrange(next_year, next_month)[1]
                for day in range(last_day_next, 0, -1):
                    date = datetime(next_year, next_month, day)
                    if date.weekday() == 3:  # Thursday
                        last_thursday = date
                        break
            
            # Get next month's last Thursday
            next_month = current_month + 1 if current_month < 12 else 1
            next_year = current_year if current_month < 12 else current_year + 1
            
            last_day_next = calendar.monthrange(next_year, next_month)[1]
            next_thursday = None
            
            for day in range(last_day_next, 0, -1):
                date = datetime(next_year, next_month, day)
                if date.weekday() == 3:  # Thursday
                    next_thursday = date
                    break
            
            current_expiry = last_thursday
            next_expiry = next_thursday
        
        # Format dates for options symbols
        current_expiry_code = current_expiry.strftime("%d%b%y").upper() if current_expiry else None
        next_expiry_code = next_expiry.strftime("%d%b%y").upper() if next_expiry else None
        
        return {
            "current": current_expiry_code,
            "next": next_expiry_code,
            "current_date": current_expiry.strftime("%d %B %Y") if current_expiry else None,
            "next_date": next_expiry.strftime("%d %B %Y") if next_expiry else None
        }
    
    def _setup_bot(self) -> None:
        """Setup Telegram bot handlers"""
        if not Application:
            self.logger.error("python-telegram-bot not available")
            return
        
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("orders", self.orders_command))
        self.application.add_handler(CommandHandler("positions", self.positions_command))
        self.application.add_handler(CommandHandler("trades", self.trades_command))
        self.application.add_handler(CommandHandler("m", self.modify_command))
        self.application.add_handler(CommandHandler("buy", self.buy_command))
        self.application.add_handler(CommandHandler("sell", self.sell_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel_command))
        self.application.add_handler(CommandHandler("modify", self.modify_command))
        self.application.add_handler(CommandHandler("brokers", self.brokers_command))
        
        # Add callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Add message handler for text messages
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        self.logger.info(f"Received /start command from user {update.effective_user.id}")
        
        welcome_message = """
🤖 *Duplicator Trading Bot*

Welcome! I can help you place and manage orders across multiple brokers.

*Choose your trading instrument:*
        """
        
        # Create custom keyboard with instrument options
        keyboard = [
            [KeyboardButton("📈 NIFTY"), KeyboardButton("🏦 BANK NIFTY")],
            [KeyboardButton("📊 SENSEX"), KeyboardButton("❓ Help")],
            [KeyboardButton("📊 Status"), KeyboardButton("📋 Orders")],
            [KeyboardButton("💰 Positions"), KeyboardButton("🏦 Brokers")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        try:
            await update.message.reply_text(
                welcome_message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            self.logger.info("Successfully sent start command response")
        except Exception as e:
            self.logger.error(f"Error sending start command response: {e}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_message = """
📚 *Duplicator Bot Help*

*Order Commands:*
• `/buy SYMBOL QTY PRICE` - Place buy order
• `/sell SYMBOL QTY PRICE` - Place sell order
• `/cancel ORDER_ID` - Cancel specific order
• `/modify ORDER_ID QTY PRICE` - Modify order

*Status Commands:*
• `/status` - System and broker status
• `/orders` - List all active orders
• `/positions` - Current positions summary
• `/trades` - View active trades with current PnL
• `/m` - Modify active trades (SL, Target, Exit)
• `/brokers` - Individual broker status

*Order Format Examples:*
• NIFTY: `NIFTY25DEC24CE25000`
• BANKNIFTY: `BANKNIFTY25DEC24CE50000`
• SENSEX: `SENSEX25DEC24CE80000`

*Note:* Orders are automatically placed on all connected brokers.
        """
        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command"""
        try:
            # Get broker health status
            broker_status = self.broker_manager.get_health_status()
            connected_brokers = [name for name, status in broker_status.items() if status]
            
            # Get positions summary
            positions_summary = self.order_manager.get_positions_summary()
            
            status_message = f"""
🔍 *System Status*

*Brokers:* {len(connected_brokers)}/{len(broker_status)} connected
• Connected: {', '.join(connected_brokers) if connected_brokers else 'None'}

*Positions:*
• Total P&L: ₹{positions_summary.get('total_pnl', 0):.2f}
• Total MTM: ₹{positions_summary.get('total_mtm', 0):.2f}

*Active Orders:* {len(self.order_manager.get_active_orders())}

*Status:* {'🟢 Online' if connected_brokers else '🔴 Offline'}
            """
            
            await update.message.reply_text(status_message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            await update.message.reply_text(f"❌ Error getting status: {str(e)}")
    
    async def orders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /orders command"""
        try:
            orders = self.order_manager.get_active_orders()
            
            if not orders:
                await update.message.reply_text("📋 No active orders found")
                return
            
            message = "📋 *Active Orders*\n\n"
            for order in orders:
                status_emoji = {
                    'PENDING': '⏳',
                    'OPEN': '🟡',
                    'COMPLETE': '✅',
                    'CANCELLED': '❌',
                    'REJECTED': '🚫'
                }.get(order['status'], '❓')
                
                message += f"""
{status_emoji} *{order['symbol']}*
• Type: {order['order_type']}
• Qty: {order['quantity']}
• Price: ₹{order['price']}
• Status: {order['status']}
• ID: `{order['order_id']}`
• Time: {order['created_at'][:19]}
---
                """
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            self.logger.error(f"Error in orders command: {e}")
            await update.message.reply_text(f"❌ Error getting orders: {str(e)}")
    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /positions command"""
        try:
            positions_summary = self.order_manager.get_positions_summary()
            
            message = f"""
💰 *Positions Summary*

*Overall:*
• Total P&L: ₹{positions_summary.get('total_pnl', 0):.2f}
• Total MTM: ₹{positions_summary.get('total_mtm', 0):.2f}

*By Broker:*
            """
            
            for broker_name, broker_data in positions_summary.get('broker_positions', {}).items():
                message += f"""
• *{broker_name}:*
  - Positions: {broker_data['positions_count']}
  - P&L: ₹{broker_data['pnl']:.2f}
  - MTM: ₹{broker_data['mtm']:.2f}
                """
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            self.logger.error(f"Error in positions command: {e}")
            await update.message.reply_text(f"❌ Error getting positions: {str(e)}")
    
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /buy command"""
        try:
            if not context.args or len(context.args) < 3:
                await update.message.reply_text(
                    "❌ Usage: `/buy SYMBOL QTY PRICE`\n"
                    "Example: `/buy NIFTY25DEC24CE25000 25 150.50`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            symbol = context.args[0].upper()
            quantity = int(context.args[1])
            price = float(context.args[2])
            
            # Place buy order
            success, message, order = self.order_manager.place_order(
                symbol=symbol,
                order_type=OrderType.BUY,
                quantity=quantity,
                price=price
            )
            
            if success:
                await update.message.reply_text(
                    f"✅ *Buy Order Placed*\n\n"
                    f"• Symbol: {symbol}\n"
                    f"• Quantity: {quantity}\n"
                    f"• Price: ₹{price}\n"
                    f"• Order ID: `{order.order_id}`\n\n"
                    f"*Status:* {message}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Send SOS notification
                await self._send_sos_notification(f"Buy order placed: {symbol} {quantity} @ ₹{price}")
            else:
                await update.message.reply_text(f"❌ *Order Failed*\n{message}", parse_mode=ParseMode.MARKDOWN)
                
        except ValueError as e:
            await update.message.reply_text(f"❌ Invalid input: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error in buy command: {e}")
            await update.message.reply_text(f"❌ Error placing buy order: {str(e)}")
    
    async def sell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /sell command"""
        try:
            if not context.args or len(context.args) < 3:
                await update.message.reply_text(
                    "❌ Usage: `/sell SYMBOL QTY PRICE`\n"
                    "Example: `/sell NIFTY25DEC24CE25000 25 150.50`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            symbol = context.args[0].upper()
            quantity = int(context.args[1])
            price = float(context.args[2])
            
            # Place sell order
            success, message, order = self.order_manager.place_order(
                symbol=symbol,
                order_type=OrderType.SELL,
                quantity=quantity,
                price=price
            )
            
            if success:
                await update.message.reply_text(
                    f"✅ *Sell Order Placed*\n\n"
                    f"• Symbol: {symbol}\n"
                    f"• Quantity: {quantity}\n"
                    f"• Price: ₹{price}\n"
                    f"• Order ID: `{order.order_id}`\n\n"
                    f"*Status:* {message}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Send SOS notification
                await self._send_sos_notification(f"Sell order placed: {symbol} {quantity} @ ₹{price}")
            else:
                await update.message.reply_text(f"❌ *Order Failed*\n{message}", parse_mode=ParseMode.MARKDOWN)
                
        except ValueError as e:
            await update.message.reply_text(f"❌ Invalid input: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error in sell command: {e}")
            await update.message.reply_text(f"❌ Error placing sell order: {str(e)}")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "❌ Usage: `/cancel ORDER_ID`\n"
                    "Example: `/cancel ORD_1234567890`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            order_id = context.args[0]
            success, message = self.order_manager.cancel_order(order_id)
            
            if success:
                await update.message.reply_text(f"✅ *Order Cancelled*\n{message}", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(f"❌ *Cancellation Failed*\n{message}", parse_mode=ParseMode.MARKDOWN)
                
        except Exception as e:
            self.logger.error(f"Error in cancel command: {e}")
            await update.message.reply_text(f"❌ Error cancelling order: {str(e)}")
    
    async def modify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /modify command"""
        try:
            if not context.args or len(context.args) < 3:
                await update.message.reply_text(
                    "❌ Usage: `/modify ORDER_ID QTY PRICE`\n"
                    "Example: `/modify ORD_1234567890 50 200.00`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            order_id = context.args[0]
            quantity = int(context.args[1])
            price = float(context.args[2])
            
            success, message = self.order_manager.modify_order(order_id, quantity, price)
            
            if success:
                await update.message.reply_text(f"✅ *Order Modified*\n{message}", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(f"❌ *Modification Failed*\n{message}", parse_mode=ParseMode.MARKDOWN)
                
        except ValueError as e:
            await update.message.reply_text(f"❌ Invalid input: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error in modify command: {e}")
            await update.message.reply_text(f"❌ Error modifying order: {str(e)}")
    
    async def brokers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /brokers command"""
        try:
            broker_status = self.broker_manager.get_health_status()
            
            message = "🏦 *Broker Status*\n\n"
            for broker_name, is_healthy in broker_status.items():
                status_emoji = "🟢" if is_healthy else "🔴"
                message += f"{status_emoji} {broker_name}: {'Connected' if is_healthy else 'Disconnected'}\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            self.logger.error(f"Error in brokers command: {e}")
            await update.message.reply_text(f"❌ Error getting broker status: {str(e)}")
    
    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /trades command to show active trades with current PnL"""
        try:
            # Get active orders from order manager
            active_orders = self.order_manager.get_active_orders()
            
            if not active_orders:
                await update.message.reply_text("📊 No active trades found.")
                return
            
            # Calculate total current PnL
            total_current_pnl = 0
            valid_trades = 0
            
            trades_msg = "📊 **Active Trades with Current PnL**\n\n"
            
            for order in active_orders:
                try:
                    # Get current price from broker
                    symbol = order['symbol']
                    broker = self.broker_manager.get_broker('broker1')
                    
                    if broker and hasattr(broker, 'get_ltp'):
                        # Try to get current price
                        current_price = broker.get_ltp(symbol)
                        if current_price:
                            current_price = float(current_price)
                        else:
                            current_price = order['price']  # Use order price as fallback
                    else:
                        current_price = order['price']  # Use order price as fallback
                    
                    # Calculate PnL
                    entry_price = float(order['price'])
                    qty = int(order['quantity'])
                    
                    # Simple PnL calculation (assuming all orders are buy orders for now)
                    current_pnl = (current_price - entry_price) * qty
                    current_pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    
                    total_current_pnl += current_pnl
                    valid_trades += 1
                    
                    # Format PnL with color emoji
                    pnl_emoji = "📈" if current_pnl >= 0 else "📉"
                    pnl_color = "🟢" if current_pnl >= 0 else "🔴"
                    
                    trades_msg += (
                        f"{pnl_color} **{symbol}**\n"
                        f"🆔 Order: `{order['order_id']}`\n"
                        f"💰 Entry: ₹{entry_price:.2f}\n"
                        f"📊 Current: ₹{current_price:.2f}\n"
                        f"📦 Qty: {qty}\n"
                        f"{pnl_emoji} PnL: ₹{current_pnl:.2f} ({current_pnl_pct:.2f}%)\n"
                        f"⏰ Time: {order['created_at'][:19]}\n"
                        f"📊 Status: {order['status']}\n\n"
                    )
                    
                except Exception as e:
                    self.logger.error(f"Error calculating PnL for {order['symbol']}: {e}")
                    # Add trade without PnL calculation
                    trades_msg += (
                        f"⚠️ **{order['symbol']}**\n"
                        f"🆔 Order: `{order['order_id']}`\n"
                        f"💰 Entry: ₹{order['price']}\n"
                        f"📦 Qty: {order['quantity']}\n"
                        f"❌ PnL: Unable to calculate\n"
                        f"⏰ Time: {order['created_at'][:19]}\n"
                        f"📊 Status: {order['status']}\n\n"
                    )
            
            # Add summary
            if valid_trades > 0:
                total_emoji = "📈" if total_current_pnl >= 0 else "📉"
                trades_msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                trades_msg += f"{total_emoji} **Total Current PnL: ₹{total_current_pnl:.2f}**\n"
                trades_msg += f"📊 **Active Trades: {len(active_orders)}**"
            else:
                trades_msg += f"⚠️ **Unable to calculate PnL for any trades**"
            
            await update.message.reply_text(trades_msg, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"Error in trades command: {e}")
            await update.message.reply_text(f"❌ Error getting trades: {str(e)}")
    
    async def modify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /m command for trade management and modification"""
        try:
            # Get active orders from order manager
            active_orders = self.order_manager.get_active_orders()
            
            if not active_orders:
                await update.message.reply_text("📊 No active trades found to modify.")
                return
            
            # Create trade selection keyboard
            trades_list = {}
            keyboard = []
            
            for order in active_orders:
                # Create display name for trade
                display_name = f"{order['symbol']} | Entry: ₹{order['price']} | Qty: {order['quantity']} | Status: {order['status']}"
                trades_list[display_name] = order['order_id']
                keyboard.append([display_name])
            
            # Add back button
            keyboard.append(["❌ Cancel"])
            
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            # Store trades list in user context for later reference
            user_id = update.effective_user.id
            if not hasattr(self, 'user_context'):
                self.user_context = {}
            if user_id not in self.user_context:
                self.user_context[user_id] = {}
            
            self.user_context[user_id]['trades_list'] = trades_list
            self.user_context[user_id]['in_modify_mode'] = True
            
            await update.message.reply_text(
                "📊 Select a trade to modify:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            self.logger.error(f"Error in modify command: {e}")
            await update.message.reply_text(f"❌ Error getting trades for modification: {str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button callbacks"""
        query = update.callback_query
        self.logger.info(f"Received button callback: {query.data} from user {update.effective_user.id}")
        await query.answer()
        
        try:
            # Handle different button callbacks
            if query.data.startswith("instrument_"):
                instrument = query.data.replace("instrument_", "")
                await self._handle_instrument_selection(query, instrument)
            elif query.data == "show_help":
                await self._show_help_menu(query)
            elif query.data == "back_to_instruments":
                await self._show_instrument_selection(query)
            elif query.data == "show_status":
                await self._show_status_menu(query)
            elif query.data == "show_orders":
                await self._show_orders_menu(query)
            elif query.data == "show_positions":
                await self._show_positions_menu(query)
            elif query.data == "show_brokers":
                await self._show_brokers_menu(query)
            elif query.data.startswith("cancel_"):
                order_id = query.data.replace("cancel_", "")
                success, message = self.order_manager.cancel_order(order_id)
                
                if success:
                    await query.edit_message_text(f"✅ Order {order_id} cancelled successfully")
                else:
                    await query.edit_message_text(f"❌ Failed to cancel order: {message}")
            else:
                self.logger.warning(f"Unknown button callback: {query.data}")
                await query.edit_message_text("❓ Unknown button action")
        except Exception as e:
            self.logger.error(f"Error handling button callback: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages"""
        message_text = update.message.text
        self.logger.info(f"Received message: '{message_text}' from user {update.effective_user.id}")
        
        # Handle custom keyboard button presses
        if message_text in ["📈 NIFTY", "🏦 BANK NIFTY", "📊 SENSEX"]:
            await self._handle_instrument_selection_text(update, message_text)
        elif message_text == "🔙 Back to Instruments":
            await self._show_main_menu(update)
        elif message_text.startswith("📅 Current") or message_text.startswith("📅 Next"):
            await self._handle_expiry_selection(update, message_text)
        elif "Call Options" in message_text or "Put Options" in message_text:
            await self._handle_option_type_selection(update, message_text)
        elif "CE" in message_text or "PE" in message_text:
            # Handle strike price selection (e.g., "80,700 CE")
            await self._handle_strike_selection(update, message_text)
        elif "Place Limit Order" in message_text or "Place Market Order" in message_text:
            # Handle order type selection
            await self._handle_order_type_selection(update, message_text)
        elif self._is_limit_price_input(update):
            # Handle limit price input
            await self._handle_limit_price_input(update, message_text)
        elif self._is_quantity_input(update):
            # Handle quantity input
            await self._handle_quantity_input(update, message_text)
        elif message_text == "❓ Help":
            await self._show_help_text(update)
        elif message_text == "📊 Status":
            await self._show_status_text(update)
        elif message_text == "📋 Orders":
            await self._show_orders_text(update)
        elif message_text == "💰 Positions":
            await self._show_positions_text(update)
        elif message_text == "🏦 Brokers":
            await self._show_brokers_text(update)
        elif self._is_trade_selection(update):
            # Handle trade selection for modification
            await self._handle_trade_selection(update, message_text)
        elif self._is_modify_option_selection(update):
            # Handle modify option selection
            await self._handle_modify_option_selection(update, message_text)
        elif message_text == "❌ Cancel":
            # Handle cancel in modify mode
            await self._handle_modify_cancel(update)
        # Check if it's a quick order format
        elif re.match(r'^[A-Z]+\d+[A-Z]+\d+[A-Z]+\d+\s+\d+\s+\d+\.?\d*$', message_text):
            parts = message_text.split()
            if len(parts) == 3:
                symbol, quantity, price = parts
                try:
                    quantity = int(quantity)
                    price = float(price)
                    
                    # Assume buy order for quick format
                    success, message, order = self.order_manager.place_order(
                        symbol=symbol,
                        order_type=OrderType.BUY,
                        quantity=quantity,
                        price=price
                    )
                    
                    if success:
                        await update.message.reply_text(f"✅ Quick buy order placed: {symbol} {quantity} @ ₹{price}")
                    else:
                        await update.message.reply_text(f"❌ Quick order failed: {message}")
                        
                except ValueError:
                    await update.message.reply_text("❌ Invalid quick order format")
        else:
            await update.message.reply_text("❓ Unknown command. Use /help for available commands.")
    
    async def _handle_instrument_selection(self, query, instrument: str) -> None:
        """Handle instrument selection from start menu"""
        instrument_info = {
            "nifty": {
                "name": "NIFTY",
                "emoji": "📈",
                "description": "Nifty 50 Index Options",
                "example_symbol": "NIFTY25DEC24CE25000"
            },
            "banknifty": {
                "name": "BANK NIFTY", 
                "emoji": "🏦",
                "description": "Bank Nifty Index Options",
                "example_symbol": "BANKNIFTY25DEC24CE50000"
            },
            "sensex": {
                "name": "SENSEX",
                "emoji": "📊", 
                "description": "Sensex Index Options",
                "example_symbol": "SENSEX25DEC24CE80000"
            }
        }
        
        if instrument not in instrument_info:
            await query.edit_message_text("❌ Invalid instrument selection")
            return
            
        info = instrument_info[instrument]
        
        message = f"""
{info['emoji']} *{info['name']} Selected*

{info['description']}

*Available Commands:*
• `/buy SYMBOL QTY PRICE` - Place buy order
• `/sell SYMBOL QTY PRICE` - Place sell order
• `/status` - Check system status
• `/orders` - View active orders
• `/positions` - View current positions

*Example Order:*
`/buy {info['example_symbol']} 25 150.50`

*Quick Order Format:*
Just send: `SYMBOL QTY PRICE`
Example: `{info['example_symbol']} 25 150.50`
        """
        
        # Create keyboard with common actions
        keyboard = [
            [InlineKeyboardButton("📊 Status", callback_data="show_status")],
            [InlineKeyboardButton("📋 Orders", callback_data="show_orders")],
            [InlineKeyboardButton("💰 Positions", callback_data="show_positions")],
            [InlineKeyboardButton("🏦 Brokers", callback_data="show_brokers")],
            [InlineKeyboardButton("🔄 Back to Instruments", callback_data="back_to_instruments")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _show_help_menu(self, query) -> None:
        """Show help menu"""
        help_message = """
📚 *Duplicator Bot Help*

*Order Commands:*
• `/buy SYMBOL QTY PRICE` - Place buy order
• `/sell SYMBOL QTY PRICE` - Place sell order
• `/cancel ORDER_ID` - Cancel specific order
• `/modify ORDER_ID QTY PRICE` - Modify order

*Status Commands:*
• `/status` - System and broker status
• `/orders` - List all active orders
• `/positions` - Current positions summary
• `/brokers` - Individual broker status

*Order Format Examples:*
• NIFTY: `NIFTY25DEC24CE25000`
• BANKNIFTY: `BANKNIFTY25DEC24CE50000`
• SENSEX: `SENSEX25DEC24CE80000`

*Note:* Orders are automatically placed on all connected brokers.
        """
        
        keyboard = [
            [InlineKeyboardButton("🔄 Back to Instruments", callback_data="back_to_instruments")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            help_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _show_instrument_selection(self, query) -> None:
        """Show instrument selection menu"""
        welcome_message = """
🤖 *Duplicator Trading Bot*

Welcome! I can help you place and manage orders across multiple brokers.

*Choose your trading instrument:*
        """
        
        # Create inline keyboard with instrument options
        keyboard = [
            [InlineKeyboardButton("📈 NIFTY", callback_data="instrument_nifty")],
            [InlineKeyboardButton("🏦 BANK NIFTY", callback_data="instrument_banknifty")],
            [InlineKeyboardButton("📊 SENSEX", callback_data="instrument_sensex")],
            [InlineKeyboardButton("❓ Help", callback_data="show_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _show_status_menu(self, query) -> None:
        """Show status information"""
        try:
            # Get broker health status
            broker_status = self.broker_manager.get_health_status()
            connected_brokers = [name for name, status in broker_status.items() if status]
            
            # Get positions summary
            positions_summary = self.order_manager.get_positions_summary()
            
            status_message = f"""
🔍 *System Status*

*Brokers:* {len(connected_brokers)}/{len(broker_status)} connected
• Connected: {', '.join(connected_brokers) if connected_brokers else 'None'}

*Positions:*
• Total P&L: ₹{positions_summary.get('total_pnl', 0):.2f}
• Total MTM: ₹{positions_summary.get('total_mtm', 0):.2f}

*Active Orders:* {len(self.order_manager.get_active_orders())}

*Status:* {'🟢 Online' if connected_brokers else '🔴 Offline'}
            """
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="show_status")],
                [InlineKeyboardButton("🔄 Back to Instruments", callback_data="back_to_instruments")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                status_message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            self.logger.error(f"Error in status menu: {e}")
            await query.edit_message_text(f"❌ Error getting status: {str(e)}")
    
    async def _show_orders_menu(self, query) -> None:
        """Show orders information"""
        try:
            orders = self.order_manager.get_active_orders()
            
            if not orders:
                message = "📋 No active orders found"
            else:
                message = "📋 *Active Orders*\n\n"
                for order in orders:
                    status_emoji = {
                        'PENDING': '⏳',
                        'OPEN': '🟡',
                        'COMPLETE': '✅',
                        'CANCELLED': '❌',
                        'REJECTED': '🚫'
                    }.get(order['status'], '❓')
                    
                    message += f"""
{status_emoji} *{order['symbol']}*
• Type: {order['order_type']}
• Qty: {order['quantity']}
• Price: ₹{order['price']}
• Status: {order['status']}
• ID: `{order['order_id']}`
• Time: {order['created_at'][:19]}
---
                    """
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="show_orders")],
                [InlineKeyboardButton("🔄 Back to Instruments", callback_data="back_to_instruments")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            self.logger.error(f"Error in orders menu: {e}")
            await query.edit_message_text(f"❌ Error getting orders: {str(e)}")
    
    async def _show_positions_menu(self, query) -> None:
        """Show positions information"""
        try:
            positions_summary = self.order_manager.get_positions_summary()
            
            message = f"""
💰 *Positions Summary*

*Overall:*
• Total P&L: ₹{positions_summary.get('total_pnl', 0):.2f}
• Total MTM: ₹{positions_summary.get('total_mtm', 0):.2f}

*By Broker:*
            """
            
            for broker_name, broker_data in positions_summary.get('broker_positions', {}).items():
                message += f"""
• *{broker_name}:*
  - Positions: {broker_data['positions_count']}
  - P&L: ₹{broker_data['pnl']:.2f}
  - MTM: ₹{broker_data['mtm']:.2f}
                """
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="show_positions")],
                [InlineKeyboardButton("🔄 Back to Instruments", callback_data="back_to_instruments")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            self.logger.error(f"Error in positions menu: {e}")
            await query.edit_message_text(f"❌ Error getting positions: {str(e)}")
    
    async def _show_brokers_menu(self, query) -> None:
        """Show brokers information"""
        try:
            broker_status = self.broker_manager.get_health_status()
            
            message = "🏦 *Broker Status*\n\n"
            for broker_name, is_healthy in broker_status.items():
                status_emoji = "🟢" if is_healthy else "🔴"
                message += f"{status_emoji} {broker_name}: {'Connected' if is_healthy else 'Disconnected'}\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="show_brokers")],
                [InlineKeyboardButton("🔄 Back to Instruments", callback_data="back_to_instruments")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            self.logger.error(f"Error in brokers menu: {e}")
            await query.edit_message_text(f"❌ Error getting broker status: {str(e)}")
    
    # Text-based handlers for custom keyboard
    async def _handle_instrument_selection_text(self, update: Update, instrument_text: str) -> None:
        """Handle instrument selection from custom keyboard"""
        instrument_map = {
            "📈 NIFTY": "nifty",
            "🏦 BANK NIFTY": "banknifty", 
            "📊 SENSEX": "sensex"
        }
        
        instrument = instrument_map.get(instrument_text)
        if not instrument:
            await update.message.reply_text("❌ Invalid instrument selection")
            return
            
        instrument_info = {
            "nifty": {
                "name": "NIFTY",
                "emoji": "📈",
                "description": "Nifty 50 Index Options"
            },
            "banknifty": {
                "name": "BANK NIFTY", 
                "emoji": "🏦",
                "description": "Bank Nifty Index Options"
            },
            "sensex": {
                "name": "SENSEX",
                "emoji": "📊", 
                "description": "Sensex Index Options"
            }
        }
        
        info = instrument_info[instrument]
        
        # Store instrument choice in user context
        user_id = update.effective_user.id
        if not hasattr(self, 'user_context'):
            self.user_context = {}
        if user_id not in self.user_context:
            self.user_context[user_id] = {}
        
        self.user_context[user_id]['instrument'] = instrument
        
        # Get expiry dates
        expiry_dates = self.find_expiry_dates(instrument)
        
        # Check if there's an error
        if "error" in expiry_dates:
            error_message = f"""
{info['emoji']} *{info['name']} Selected*

❌ **Error**: {expiry_dates['error']}

Please try again later or contact support if the issue persists.
            """
            
            # Create back button only
            error_keyboard = [[KeyboardButton("🔙 Back to Instruments")]]
            reply_markup = ReplyKeyboardMarkup(error_keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            await update.message.reply_text(
                error_message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        message = f"""
{info['emoji']} *{info['name']} Selected*

{info['description']}

*Choose {info['name']} Expiry:*
        """
        
        # Create expiry selection keyboard
        expiry_keyboard = []
        if expiry_dates["current"]:
            expiry_keyboard.append([KeyboardButton(f"📅 Current ({expiry_dates['current_date']})")])
        if expiry_dates["next"]:
            expiry_keyboard.append([KeyboardButton(f"📅 Next ({expiry_dates['next_date']})")])
        
        # Add back button
        expiry_keyboard.append([KeyboardButton("🔙 Back to Instruments")])
        
        reply_markup = ReplyKeyboardMarkup(expiry_keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _show_main_menu(self, update: Update) -> None:
        """Show main menu with instrument selection"""
        # Clean up any existing websocket subscriptions
        user_id = update.effective_user.id
        if hasattr(self, 'user_context') and user_id in self.user_context:
            user_data = self.user_context[user_id]
            if 'option_symbol' in user_data and 'option_token' in user_data:
                # Unsubscribe from previous websocket
                self.unsubscribe_from_websocket(user_data['option_symbol'], user_data['option_token'])
                # Clear user context
                self.user_context[user_id] = {}
        
        welcome_message = """
🤖 *Duplicator Trading Bot*

Welcome! I can help you place and manage orders across multiple brokers.

*Choose your trading instrument:*
        """
        
        # Create custom keyboard with instrument options
        keyboard = [
            [KeyboardButton("📈 NIFTY"), KeyboardButton("🏦 BANK NIFTY")],
            [KeyboardButton("📊 SENSEX"), KeyboardButton("❓ Help")],
            [KeyboardButton("📊 Status"), KeyboardButton("📋 Orders")],
            [KeyboardButton("💰 Positions"), KeyboardButton("🏦 Brokers")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _handle_expiry_selection(self, update: Update, message_text: str) -> None:
        """Handle expiry selection"""
        # Extract instrument from context (we'll need to store this in user data)
        # For now, let's determine from the message pattern
        if "Current" in message_text:
            expiry_type = "current"
        else:
            expiry_type = "next"
        
        # Get current expiry dates to show example symbols
        # We need to determine which instrument was selected
        # For now, we'll try to get the most recent instrument selection
        # In a real implementation, you'd store this in user context
        expiry_dates = self.find_expiry_dates("sensex")  # Default to sensex for now
        
        # Check if there's an error
        if "error" in expiry_dates:
            await update.message.reply_text(f"❌ {expiry_dates['error']}")
            return
        
        if expiry_type == "current" and expiry_dates["current"]:
            expiry_code = expiry_dates["current"]
            expiry_date = expiry_dates["current_date"]
        elif expiry_type == "next" and expiry_dates["next"]:
            expiry_code = expiry_dates["next"]
            expiry_date = expiry_dates["next_date"]
        else:
            await update.message.reply_text("❌ Expiry date not available")
            return
        
        # Store expiry info in user context for later use
        user_id = update.effective_user.id
        if not hasattr(self, 'user_context'):
            self.user_context = {}
        if user_id not in self.user_context:
            self.user_context[user_id] = {}
        
        self.user_context[user_id]['expiry_code'] = expiry_code
        self.user_context[user_id]['expiry_date'] = expiry_date
        # Get instrument from user context (set during instrument selection)
        self.user_context[user_id]['instrument'] = self.user_context[user_id].get('instrument', 'sensex')
        
        message = f"""
📅 *Expiry Selected: {expiry_date}*

*Expiry Code:* `{expiry_code}`

What would you like to trade?
        """
        
        # Create Call/Put selection keyboard
        option_keyboard = [
            [KeyboardButton("📈 Call Options"), KeyboardButton("📉 Put Options")],
            [KeyboardButton("🔙 Back to Instruments")]
        ]
        reply_markup = ReplyKeyboardMarkup(option_keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def _handle_option_type_selection(self, update: Update, message_text: str) -> None:
        """Handle Call/Put option type selection"""
        user_id = update.effective_user.id
        
        # Check if user has expiry info stored
        if not hasattr(self, 'user_context') or user_id not in self.user_context:
            await update.message.reply_text("❌ Please select an expiry first")
            return
        
        user_data = self.user_context[user_id]
        expiry_code = user_data.get('expiry_code')
        instrument = user_data.get('instrument', 'sensex')
        
        if not expiry_code:
            await update.message.reply_text("❌ Expiry information not found")
            return
        
        # Determine option type
        if "Call" in message_text:
            option_type = "CE"
            option_name = "Call Options"
        elif "Put" in message_text:
            option_type = "PE"
            option_name = "Put Options"
        else:
            await update.message.reply_text("❌ Invalid option type")
            return
        
        # Get current price for the selected instrument
        try:
            self.logger.info(f"Getting current price for {instrument}")
            current_price = self.get_current_price(instrument)
            self.logger.info(f"Current price for {instrument}: {current_price}")
        except Exception as e:
            self.logger.error(f"Error getting current price for {instrument}: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
            return
        
        # Generate strike options
        self.logger.info(f"Generating strike options for price: {current_price}, option_type: {option_type}")
        strike_options = self.generate_strike_options(current_price, option_type, expiry_code)
        self.logger.info(f"Generated strike options: {strike_options}")
        
        # Get instrument display name
        instrument_names = {
            "nifty": "NIFTY",
            "banknifty": "BANK NIFTY",
            "sensex": "SENSEX"
        }
        instrument_display = instrument_names.get(instrument, instrument.upper())
        
        message = f"""
📈 *{option_name} Selected*

*Current {instrument_display} Price:* {current_price:,.2f}
*Expiry:* {user_data.get('expiry_date', 'Unknown')}
*Expiry Code:* `{expiry_code}`

Select a strike price:
        """
        
        # Create strike price keyboard (3 per row)
        strike_keyboard = []
        for i in range(0, len(strike_options), 3):
            row = []
            for j in range(i, min(i + 3, len(strike_options))):
                row.append(KeyboardButton(strike_options[j]))
            strike_keyboard.append(row)
        
        # Add back button
        strike_keyboard.append([KeyboardButton("🔙 Back to Instruments")])
        
        reply_markup = ReplyKeyboardMarkup(strike_keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    def get_token_from_symbol(self, trading_symbol: str) -> str:
        """Get token from trading symbol using the symbol files"""
        try:
            # Load BFO symbols for SENSEX
            if "SENSEX" in trading_symbol:
                # Convert the trading symbol to BFO format for lookup
                bfo_trading_symbol = self.convert_sensex_format(trading_symbol)
                
                bfo_file = f"data/BFO_symbols.txt_{datetime.today().strftime('%Y-%m-%d')}.txt"
                if os.path.exists(bfo_file):
                    with open(bfo_file, 'r', encoding='utf-8') as file:
                        for line in file:
                            values = line.strip().split(',')
                            if len(values) > 4 and values[4] == bfo_trading_symbol:
                                return values[1]  # Token is in column 1
                return None
            else:
                # Load NFO symbols for NIFTY and BANK NIFTY
                nfo_file = f"data/NFO_symbols.txt_{datetime.today().strftime('%Y-%m-%d')}.txt"
                if os.path.exists(nfo_file):
                    with open(nfo_file, 'r', encoding='utf-8') as file:
                        for line in file:
                            values = line.strip().split(',')
                            if len(values) > 4 and values[4] == trading_symbol:
                                return values[1]  # Token is in column 1
                return None
        except Exception as e:
            self.logger.error(f"Error getting token for {trading_symbol}: {e}")
            return None

    def get_lot_size_from_symbol(self, trading_symbol: str) -> int:
        """Get lot size from trading symbol using the symbol files"""
        try:
            # Load BFO symbols for SENSEX
            if "SENSEX" in trading_symbol:
                # Convert the trading symbol to BFO format for lookup
                bfo_trading_symbol = self.convert_sensex_format(trading_symbol)
                
                bfo_file = f"data/BFO_symbols.txt_{datetime.today().strftime('%Y-%m-%d')}.txt"
                if os.path.exists(bfo_file):
                    with open(bfo_file, 'r', encoding='utf-8') as file:
                        for line in file:
                            values = line.strip().split(',')
                            if len(values) > 4 and values[4] == bfo_trading_symbol:
                                return int(values[2])  # Lot size is in column 2
                return 25  # Default lot size for SENSEX
            else:
                # Load NFO symbols for NIFTY and BANK NIFTY
                nfo_file = f"data/NFO_symbols.txt_{datetime.today().strftime('%Y-%m-%d')}.txt"
                if os.path.exists(nfo_file):
                    with open(nfo_file, 'r', encoding='utf-8') as file:
                        for line in file:
                            values = line.strip().split(',')
                            if len(values) > 4 and values[4] == trading_symbol:
                                return int(values[2])  # Lot size is in column 2
                return 25  # Default lot size for NIFTY/BANK NIFTY
        except Exception as e:
            self.logger.error(f"Error getting lot size for {trading_symbol}: {e}")
            return 25  # Default lot size

    def _generate_quantity_options(self, lot_size: int) -> list:
        """Generate quantity options as multiples of lot size"""
        # Fixed quantity options: [20, 40, 60, 80, 100, 200]
        quantities = [20, 40, 60, 80, 100, 200]
        
        self.logger.info(f"Generated quantity options: {quantities}")
        return quantities

    def subscribe_to_websocket(self, trading_symbol: str, token: str) -> bool:
        """Subscribe to websocket feed for the given symbol"""
        try:
            broker = self.broker_manager.get_broker('broker1')
            if broker and hasattr(broker, 'subscribe'):
                # Determine exchange
                if "SENSEX" in trading_symbol:
                    exchange = "BFO"
                else:
                    exchange = "NFO"
                
                # Create websocket token
                websocket_token = f"{exchange}|{token}"
                
                # Subscribe to websocket
                broker.subscribe(websocket_token)
                self.logger.info(f"Subscribed to websocket: {websocket_token}")
                return True
            else:
                self.logger.error("Broker does not support websocket subscription")
                return False
        except Exception as e:
            self.logger.error(f"Error subscribing to websocket for {trading_symbol}: {e}")
            return False

    def unsubscribe_from_websocket(self, trading_symbol: str, token: str) -> bool:
        """Unsubscribe from websocket feed for the given symbol"""
        try:
            broker = self.broker_manager.get_broker('broker1')
            if broker and hasattr(broker, 'unsubscribe'):
                # Determine exchange
                if "SENSEX" in trading_symbol:
                    exchange = "BFO"
                else:
                    exchange = "NFO"
                
                # Create websocket token
                websocket_token = f"{exchange}|{token}"
                
                # Unsubscribe from websocket
                broker.unsubscribe(websocket_token)
                self.logger.info(f"Unsubscribed from websocket: {websocket_token}")
                return True
            else:
                self.logger.error("Broker does not support websocket unsubscription")
                return False
        except Exception as e:
            self.logger.error(f"Error unsubscribing from websocket for {trading_symbol}: {e}")
            return False

    def handle_websocket_data(self, price_update) -> None:
        """Handle websocket data and trigger callback for initial LTP"""
        try:
            # Extract LTP from price update object
            ltp = price_update.last_price
            
            # Try to get token from different possible fields
            token = getattr(price_update, 'token', None) or getattr(price_update, 'tk', None)
            
            self.logger.info(f"Websocket data received - LTP: {ltp}, Token: {token}")
            
            if ltp:
                # If we have a token, try to match with pending callbacks
                if token and token in self.initial_ltp_callbacks:
                    self.logger.info(f"Found pending callback for token {token}, calling with LTP: {ltp}")
                    callback = self.initial_ltp_callbacks.pop(token)
                    callback(float(ltp))
                else:
                    # If no token match, try to use any pending callback (for cases where token doesn't match)
                    if self.initial_ltp_callbacks:
                        self.logger.info(f"No token match, using first available callback with LTP: {ltp}")
                        # Get the first available callback
                        token_key = list(self.initial_ltp_callbacks.keys())[0]
                        callback = self.initial_ltp_callbacks.pop(token_key)
                        callback(float(ltp))
                    else:
                        self.logger.debug(f"No pending callbacks available")
            else:
                self.logger.warning(f"Missing LTP: LTP={ltp}, Token={token}")
                    
        except Exception as e:
            self.logger.error(f"Error handling websocket data: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")


    def generate_option_symbol(self, instrument: str, strike: int, option_type: str, expiry_code: str) -> str:
        """Generate option symbol for broker API based on actual symbol files"""
        if instrument.lower() == "sensex":
            # Format: SENSEX<YY><MMM or MM><Strike><CE/PE>
            # The expiry_code is in format like "25SEP25", we need to convert to proper SENSEX format
            # Extract day, month, and year from expiry_code
            day = expiry_code[:2]
            month = expiry_code[2:5]
            year = expiry_code[5:]
            
            # Convert to proper date format for last Thursday check
            from datetime import datetime, timedelta
            import calendar
            
            def is_last_thursday(date):
                """Check if given date is last Thursday of the month."""
                last_day = calendar.monthrange(date.year, date.month)[1]
                last_date = datetime(date.year, date.month, last_day).date()
                
                # Move backwards to find last Thursday
                while last_date.weekday() != 3:  # 3 = Thursday
                    last_date -= timedelta(days=1)
                
                return date == last_date
            
            # Create date object
            date_obj = datetime(2000 + int(year), datetime.strptime(month, "%b").month, int(day)).date()
            
            # Generate symbol based on expiry type
            if is_last_thursday(date_obj):
                # Monthly expiry → Use month abbreviation
                symbol_year = str(date_obj.year)[-2:]
                month_abbr = date_obj.strftime("%b").upper()
                symbol = f"SENSEX{symbol_year}{month_abbr}{strike:05d}{option_type}"
            else:
                # Weekly expiry → Use numeric month/day
                symbol_year = str(date_obj.year)[-2:]
                month_num = f"{date_obj.month}"  # Remove leading zero
                day_num = f"{date_obj.day:02d}"
                symbol = f"SENSEX{symbol_year}{month_num}{day_num}{strike:05d}{option_type}"
            
            return symbol
        elif instrument.lower() == "nifty":
            # Format: NIFTY25SEP11C25000 (NIFTY + YYMMMDD + C/P + Strike)
            # Convert expiry_code from "11SEP25" to "25SEP11"
            day = expiry_code[:2]
            month = expiry_code[2:5]
            year = expiry_code[5:]
            option_char = "C" if option_type == "CE" else "P"
            return f"NIFTY{year}{month}{day}{option_char}{strike:05d}"
        elif instrument.lower() == "banknifty":
            # Format: BANKNIFTY25SEP30C73500 (BANKNIFTY + YYMMMDD + C/P + Strike)
            # Convert expiry_code from "30SEP25" to "25SEP30"
            day = expiry_code[:2]
            month = expiry_code[2:5]
            year = expiry_code[5:]
            option_char = "C" if option_type == "CE" else "P"
            return f"BANKNIFTY{year}{month}{day}{option_char}{strike:05d}"
        else:
            raise ValueError(f"Unsupported instrument: {instrument}")

    async def _handle_strike_selection(self, update: Update, message_text: str) -> None:
        """Handle strike price selection and show real-time LTP"""
        user_id = update.effective_user.id
        
        # Check if user has context stored
        if not hasattr(self, 'user_context') or user_id not in self.user_context:
            await update.message.reply_text("❌ Please start over with /start")
            return
        
        user_data = self.user_context[user_id]
        instrument = user_data.get('instrument', 'sensex')
        expiry_code = user_data.get('expiry_code')
        
        if not expiry_code:
            await update.message.reply_text("❌ Expiry information not found")
            return
        
        # Parse strike price and option type from message (e.g., "80,700 CE")
        try:
            # Remove commas and split
            parts = message_text.replace(',', '').split()
            if len(parts) != 2:
                await update.message.reply_text("❌ Invalid strike format")
                return
            
            strike_price = int(parts[0])
            option_type = parts[1]
            
            if option_type not in ['CE', 'PE']:
                await update.message.reply_text("❌ Invalid option type")
                return
                
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Invalid strike format")
            return
        
        # Generate option symbol
        option_symbol = self.generate_option_symbol(instrument, strike_price, option_type, expiry_code)
        
        # Store option details in user context
        user_data['selected_strike'] = strike_price
        user_data['selected_option_type'] = option_type
        user_data['option_symbol'] = option_symbol
        
        # Get token and lot size for websocket subscription
        token = self.get_token_from_symbol(option_symbol)
        lot_size = self.get_lot_size_from_symbol(option_symbol)
        
        if token:
            # Subscribe to websocket for real-time updates
            self.subscribe_to_websocket(option_symbol, token)
            user_data['option_token'] = token
            user_data['lot_size'] = lot_size
            self.logger.info(f"Lot size for {option_symbol}: {lot_size}")
            
            # Set up callback to get initial LTP from websocket
            initial_ltp = None
            def on_initial_ltp(ltp_value):
                nonlocal initial_ltp
                self.logger.info(f"Callback triggered with LTP: {ltp_value}")
                initial_ltp = ltp_value
            
            self.initial_ltp_callbacks[token] = on_initial_ltp
            self.logger.info(f"Set up callback for token {token}, waiting for websocket feed...")
            
            # Wait for first websocket feed (with timeout)
            import asyncio
            timeout = 10  # Increased to 10 seconds timeout
            start_time = asyncio.get_event_loop().time()
            
            while initial_ltp is None and (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(0.1)
            
            if initial_ltp is None:
                self.logger.error(f"Timeout waiting for websocket feed for token {token}")
                self.logger.error(f"Available callbacks: {list(self.initial_ltp_callbacks.keys())}")
                await update.message.reply_text("❌ Error: Could not get initial LTP from websocket feed")
                return
            else:
                self.logger.info(f"Successfully got initial LTP: {initial_ltp}")
        else:
            self.logger.warning(f"Could not find token for {option_symbol}")
            await update.message.reply_text("❌ Error: Could not find token for the selected option")
            return
        
        # Get instrument display name
        instrument_names = {
            "nifty": "NIFTY",
            "banknifty": "BANK NIFTY",
            "sensex": "SENSEX"
        }
        instrument_display = instrument_names.get(instrument, instrument.upper())
        
        message = f"""
🎯 *Option Selected*

*Symbol:* `{option_symbol}`
*Instrument:* {instrument_display}
*Strike:* {strike_price:,} {option_type}
*Expiry:* {user_data.get('expiry_date', 'Unknown')}

*Current LTP:* ₹{initial_ltp:,.2f}
        """
        
        # Create order type selection keyboard
        order_keyboard = [
            [KeyboardButton("📊 Place Limit Order"), KeyboardButton("⚡ Place Market Order")],
            [KeyboardButton("🔙 Back to Instruments")]
        ]
        reply_markup = ReplyKeyboardMarkup(order_keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        # Send initial message
        sent_message = await update.message.reply_text(
            message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        # Store message ID for real-time updates
        user_data['ltp_message_id'] = sent_message.message_id
        user_data['ltp_chat_id'] = update.effective_chat.id
        
        # Start real-time LTP updates
        await self.start_ltp_updates(user_id, option_symbol, instrument_display, strike_price, option_type, expiry_code)

    def get_option_ltp(self, option_symbol: str) -> float:
        """Get current LTP for option symbol from broker using get_quotes API"""
        try:
            broker = self.broker_manager.get_broker('broker1')
            if broker and hasattr(broker, 'api'):
                # Get token from symbol files
                token = self.get_token_from_symbol(option_symbol)
                if not token:
                    raise Exception(f"Could not find token for {option_symbol}")
                
                # Determine exchange based on symbol
                if "SENSEX" in option_symbol:
                    exchange = "BFO"
                else:
                    exchange = "NFO"
                
                # Use get_quotes API with exchange and token
                self.logger.info(f"Getting quotes for exchange={exchange}, token={token}")
                ret = broker.api.get_quotes(exchange=exchange, token=token)
                
                if ret and ret.get('stat') == 'Ok' and 'lp' in ret:
                    ltp = float(ret['lp'])
                    self.logger.info(f"Got LTP from get_quotes: {ltp}")
                    return ltp
                else:
                    self.logger.error(f"Invalid response from get_quotes: {ret}")
                    raise Exception(f"Invalid response from get_quotes API")
            
            # Throw error if broker not available
            raise Exception(f"Broker not available for LTP fetch")
            
        except Exception as e:
            self.logger.error(f"Error getting LTP for {option_symbol}: {e}")
            raise Exception(f"Failed to get LTP for {option_symbol}: {str(e)}")

    async def start_ltp_updates(self, user_id: int, option_symbol: str, instrument_display: str, 
                              strike_price: int, option_type: str, expiry_code: str) -> None:
        """Start real-time LTP updates every 2 seconds"""
        import asyncio
        
        try:
            while True:
                # Check if user still has this option selected
                if not hasattr(self, 'user_context') or user_id not in self.user_context:
                    break
                
                user_data = self.user_context[user_id]
                if user_data.get('option_symbol') != option_symbol:
                    break
                
                # Get current LTP from broker API
                try:
                    current_ltp = self.get_option_ltp(option_symbol)
                except Exception as e:
                    self.logger.error(f"Error getting LTP in updates: {e}")
                    break
                
                # Update message
                message = f"""
🎯 *Option Selected*

*Symbol:* `{option_symbol}`
*Instrument:* {instrument_display}
*Strike:* {strike_price:,} {option_type}
*Expiry:* {user_data.get('expiry_date', 'Unknown')}

*Current LTP:* ₹{current_ltp:,.2f}
                """
                
                try:
                    await self.application.bot.edit_message_text(
                        chat_id=user_data.get('ltp_chat_id'),
                        message_id=user_data.get('ltp_message_id'),
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    self.logger.error(f"Error updating LTP message: {e}")
                    break
                
                # Wait 2 seconds
                await asyncio.sleep(2)
                
        except Exception as e:
            self.logger.error(f"Error in LTP updates: {e}")

    def _is_limit_price_input(self, update: Update) -> bool:
        """Check if the message is a limit price input"""
        user_id = update.effective_user.id
        if not hasattr(self, 'user_context') or user_id not in self.user_context:
            return False
        
        user_data = self.user_context[user_id]
        order_type = user_data.get('order_type')
        limit_price = user_data.get('limit_price')
        
        # Check if user is in limit order flow, message is a number, and no limit price set yet
        if order_type == "LIMIT" and limit_price is None:
            try:
                float(update.message.text)
                return True
            except ValueError:
                return False
        
        return False

    def _is_quantity_input(self, update: Update) -> bool:
        """Check if the message is a quantity input"""
        user_id = update.effective_user.id
        if not hasattr(self, 'user_context') or user_id not in self.user_context:
            return False
        
        user_data = self.user_context[user_id]
        order_type = user_data.get('order_type')
        limit_price = user_data.get('limit_price')
        
        # Check if user is in order flow
        if order_type:
            # For limit orders: check if limit price has been set
            if order_type == "LIMIT" and limit_price is not None:
                try:
                    int(update.message.text)
                    return True
                except ValueError:
                    return False
            # For market orders: any number input after order type selection
            elif order_type == "MARKET":
                try:
                    int(update.message.text)
                    return True
                except ValueError:
                    return False
        
        return False

    async def _handle_limit_price_input(self, update: Update, message_text: str) -> None:
        """Handle limit price input"""
        user_id = update.effective_user.id
        user_data = self.user_context[user_id]
        
        try:
            limit_price = float(message_text)
            
            # Store limit price in context
            user_data['limit_price'] = limit_price
            
            # Get option symbol and other details
            option_symbol = user_data.get('option_symbol')
            
            # Get current LTP from broker API for confirmation
            try:
                current_ltp = self.get_option_ltp(option_symbol)
                self.logger.info(f"Got current LTP for confirmation: {current_ltp}")
            except Exception as e:
                self.logger.warning(f"Could not get LTP for confirmation: {e}")
                current_ltp = 0  # Use 0 as fallback to show "Not available"
            
            # Show confirmation message
            selected_strike = user_data.get('selected_strike')
            selected_option_type = user_data.get('selected_option_type')
            instrument = user_data.get('instrument', 'sensex')
            
            instrument_names = {
                "nifty": "NIFTY",
                "banknifty": "BANK NIFTY", 
                "sensex": "SENSEX"
            }
            instrument_display = instrument_names.get(instrument, instrument.upper())
            
            message = f"""
📊 *Limit Order Confirmation*

*Symbol:* `{option_symbol}`
*Instrument:* {instrument_display}
*Strike:* {selected_strike:,} {selected_option_type}
*Your Limit Price:* ₹{limit_price:,.2f}

Please select quantity:
            """
            
            # Get lot size and generate quantity options
            lot_size = user_data.get('lot_size', 25)
            quantity_options = self._generate_quantity_options(lot_size)
            
            # Create quantity selection keyboard
            quantity_keyboard = []
            for i in range(0, len(quantity_options), 3):
                row = [KeyboardButton(str(qty)) for qty in quantity_options[i:i+3]]
                quantity_keyboard.append(row)
            
            quantity_keyboard.append([KeyboardButton("🔙 Back to Instruments")])
            reply_markup = ReplyKeyboardMarkup(quantity_keyboard, resize_keyboard=True, one_time_keyboard=False)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid price number (e.g., 150.50 or 150)")

    async def _handle_quantity_input(self, update: Update, message_text: str) -> None:
        """Handle quantity input and place order"""
        user_id = update.effective_user.id
        user_data = self.user_context[user_id]
        
        try:
            quantity = int(message_text)
            
            # Get order details
            option_symbol = user_data.get('option_symbol')
            limit_price = user_data.get('limit_price')
            order_type = user_data.get('order_type')
            instrument = user_data.get('instrument', 'sensex')
            
            # Determine exchange
            if "SENSEX" in option_symbol:
                exchange = "BFO"
            else:
                exchange = "NFO"
            
            # Place order using Shoonya API
            broker = self.broker_manager.get_broker('broker1')
            if broker and hasattr(broker, 'api'):
                try:
                    # Determine price type and price based on order type
                    if order_type == "LIMIT":
                        price_type = 'LMT'  # Limit order
                        price = limit_price
                        order_type_display = "Limit Order"
                    else:  # MARKET order
                        price_type = 'MKT'  # Market order
                        price = 0  # Market orders don't have a specific price
                        order_type_display = "Market Order"
                    
                    # Place order
                    order_result = broker.api.place_order(
                        buy_or_sell='B',  # Buy order
                        product_type='C',  # CNC (Cash and Carry)
                        exchange=exchange,
                        tradingsymbol=option_symbol,
                        quantity=quantity,
                        discloseqty=0,
                        price_type=price_type,
                        price=price,
                        trigger_price=None,
                        retention='DAY',
                        remarks=f'telegram_order_{user_id}'
                    )
                    
                    if order_result and order_result.get('stat') == 'Ok':
                        order_no = order_result.get('norenordno', 'Unknown')
                        
                        # Create appropriate message based on order type
                        if order_type == "LIMIT":
                            price_info = f"*Price:* ₹{limit_price:,.2f}\n*Type:* {order_type_display}\n\nOrder has been placed and will be executed when market price reaches your limit price."
                        else:  # MARKET order
                            price_info = f"*Type:* {order_type_display}\n\nOrder has been placed and will be executed at the current market price."
                        
                        message = f"""
✅ *Order Placed Successfully!*

*Order Number:* {order_no}
*Symbol:* `{option_symbol}`
*Quantity:* {quantity}
{price_info}
*Exchange:* {exchange}
                        """
                        
                        await update.message.reply_text(
                            message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        
                        # Clear user context
                        if user_id in self.user_context:
                            del self.user_context[user_id]
                            
                    else:
                        error_msg = order_result.get('emsg', 'Unknown error') if order_result else 'No response from broker'
                        await update.message.reply_text(f"❌ Order failed: {error_msg}")
                        
                except Exception as e:
                    self.logger.error(f"Error placing order: {e}")
                    await update.message.reply_text(f"❌ Error placing order: {str(e)}")
            else:
                await update.message.reply_text("❌ Broker not available for order placement")
                
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid quantity number")

    async def _handle_order_type_selection(self, update: Update, message_text: str) -> None:
        """Handle order type selection (Limit Order or Market Order)"""
        user_id = update.effective_user.id
        
        # Check if user has context stored
        if not hasattr(self, 'user_context') or user_id not in self.user_context:
            await update.message.reply_text("❌ Please start over with /start")
            return
        
        user_data = self.user_context[user_id]
        option_symbol = user_data.get('option_symbol')
        selected_strike = user_data.get('selected_strike')
        selected_option_type = user_data.get('selected_option_type')
        instrument = user_data.get('instrument', 'sensex')
        
        if not option_symbol:
            await update.message.reply_text("❌ No option selected. Please start over.")
            return
        
        # Determine order type
        if "Limit Order" in message_text:
            order_type = "LIMIT"
            order_type_display = "Limit Order"
        elif "Market Order" in message_text:
            order_type = "MARKET"
            order_type_display = "Market Order"
        else:
            await update.message.reply_text("❌ Invalid order type")
            return
        
        # Store order type in context
        user_data['order_type'] = order_type
        
        # Get current LTP from broker API
        try:
            current_ltp = self.get_option_ltp(option_symbol)
            self.logger.info(f"Successfully got current LTP from broker API: {current_ltp}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
            return
        
        # Get instrument display name
        instrument_names = {
            "nifty": "NIFTY",
            "banknifty": "BANK NIFTY",
            "sensex": "SENSEX"
        }
        instrument_display = instrument_names.get(instrument, instrument.upper())
        
        if order_type == "LIMIT":
            message = f"""
📊 *Limit Order Selected*

*Symbol:* `{option_symbol}`
*Instrument:* {instrument_display}
*Strike:* {selected_strike:,} {selected_option_type}
*Current LTP:* ₹{current_ltp:,.2f}

Please enter your limit price:
(Example: 150.50 or 150)

Type your limit price as a number.
            """
            
            # Create price suggestion keyboard based on current LTP
            price_suggestions = []
            if current_ltp:
                # Suggest prices around current LTP
                base_price = round(current_ltp)
                suggestions = [
                    str(base_price - 5), str(base_price - 2), str(base_price),
                    str(base_price + 2), str(base_price + 5)
                ]
                price_suggestions = [[s] for s in suggestions]
            
            price_suggestions.append(["🔙 Back to Instruments"])
            reply_markup = ReplyKeyboardMarkup(price_suggestions, resize_keyboard=True, one_time_keyboard=False)
            
        else:  # MARKET ORDER
            message = f"""
⚡ *Market Order Selected*

*Symbol:* `{option_symbol}`
*Instrument:* {instrument_display}
*Strike:* {selected_strike:,} {selected_option_type}
*Current LTP:* ₹{current_ltp:,.2f}

Please select quantity:
            """
            
            # Get lot size and generate quantity options
            lot_size = user_data.get('lot_size', 25)
            quantity_options = self._generate_quantity_options(lot_size)
            
            # Create quantity input keyboard
            quantity_keyboard = []
            for i in range(0, len(quantity_options), 3):
                row = [KeyboardButton(str(qty)) for qty in quantity_options[i:i+3]]
                quantity_keyboard.append(row)
            
            quantity_keyboard.append([KeyboardButton("🔙 Back to Instruments")])
            reply_markup = ReplyKeyboardMarkup(quantity_keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _show_help_text(self, update: Update) -> None:
        """Show help information as text"""
        help_message = """
📚 *Duplicator Bot Help*

*Order Commands:*
• `/buy SYMBOL QTY PRICE` - Place buy order
• `/sell SYMBOL QTY PRICE` - Place sell order
• `/cancel ORDER_ID` - Cancel specific order
• `/modify ORDER_ID QTY PRICE` - Modify order

*Status Commands:*
• `/status` - System and broker status
• `/orders` - List all active orders
• `/positions` - Current positions summary
• `/brokers` - Individual broker status

*Order Format Examples:*
• NIFTY: `NIFTY25DEC24CE25000`
• BANKNIFTY: `BANKNIFTY25DEC24CE50000`
• SENSEX: `SENSEX25DEC24CE80000`

*Note:* Orders are automatically placed on all connected brokers.
        """
        
        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)
    
    async def _show_status_text(self, update: Update) -> None:
        """Show status information as text"""
        try:
            # Get broker health status
            broker_status = self.broker_manager.get_health_status()
            connected_brokers = [name for name, status in broker_status.items() if status]
            
            # Get positions summary
            positions_summary = self.order_manager.get_positions_summary()
            
            status_message = f"""
🔍 *System Status*

*Brokers:* {len(connected_brokers)}/{len(broker_status)} connected
• Connected: {', '.join(connected_brokers) if connected_brokers else 'None'}

*Positions:*
• Total P&L: ₹{positions_summary.get('total_pnl', 0):.2f}
• Total MTM: ₹{positions_summary.get('total_mtm', 0):.2f}

*Active Orders:* {len(self.order_manager.get_active_orders())}

*Status:* {'🟢 Online' if connected_brokers else '🔴 Offline'}
            """
            
            await update.message.reply_text(status_message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            self.logger.error(f"Error in status text: {e}")
            await update.message.reply_text(f"❌ Error getting status: {str(e)}")
    
    async def _show_orders_text(self, update: Update) -> None:
        """Show orders information as text"""
        try:
            orders = self.order_manager.get_active_orders()
            
            if not orders:
                message = "📋 No active orders found"
            else:
                message = "📋 *Active Orders*\n\n"
                for order in orders:
                    status_emoji = {
                        'PENDING': '⏳',
                        'OPEN': '🟡',
                        'COMPLETE': '✅',
                        'CANCELLED': '❌',
                        'REJECTED': '🚫'
                    }.get(order['status'], '❓')
                    
                    message += f"""
{status_emoji} *{order['symbol']}*
• Type: {order['order_type']}
• Qty: {order['quantity']}
• Price: ₹{order['price']}
• Status: {order['status']}
• ID: `{order['order_id']}`
• Time: {order['created_at'][:19]}
---
                    """
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            self.logger.error(f"Error in orders text: {e}")
            await update.message.reply_text(f"❌ Error getting orders: {str(e)}")
    
    async def _show_positions_text(self, update: Update) -> None:
        """Show positions information as text"""
        try:
            positions_summary = self.order_manager.get_positions_summary()
            
            message = f"""
💰 *Positions Summary*

*Overall:*
• Total P&L: ₹{positions_summary.get('total_pnl', 0):.2f}
• Total MTM: ₹{positions_summary.get('total_mtm', 0):.2f}

*By Broker:*
            """
            
            for broker_name, broker_data in positions_summary.get('broker_positions', {}).items():
                message += f"""
• *{broker_name}:*
  - Positions: {broker_data['positions_count']}
  - P&L: ₹{broker_data['pnl']:.2f}
  - MTM: ₹{broker_data['mtm']:.2f}
                """
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            self.logger.error(f"Error in positions text: {e}")
            await update.message.reply_text(f"❌ Error getting positions: {str(e)}")
    
    async def _show_brokers_text(self, update: Update) -> None:
        """Show brokers information as text"""
        try:
            broker_status = self.broker_manager.get_health_status()
            
            message = "🏦 *Broker Status*\n\n"
            for broker_name, is_healthy in broker_status.items():
                status_emoji = "🟢" if is_healthy else "🔴"
                message += f"{status_emoji} {broker_name}: {'Connected' if is_healthy else 'Disconnected'}\n"
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            self.logger.error(f"Error in brokers text: {e}")
            await update.message.reply_text(f"❌ Error getting broker status: {str(e)}")

    async def _send_sos_notification(self, message: str) -> None:
        """Send SOS notification to configured chat"""
        if self.sos_chat_id:
            try:
                await self.application.bot.send_message(
                    chat_id=self.sos_chat_id,
                    text=f"🚨 *SOS Alert*\n{message}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                self.logger.error(f"Error sending SOS notification: {e}")
    
    async def send_notification(self, message: str, chat_id: Optional[str] = None) -> None:
        """Send notification to specified chat or default chat"""
        target_chat = chat_id or self.chat_id
        if target_chat:
            try:
                await self.application.bot.send_message(
                    chat_id=target_chat,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                self.logger.error(f"Error sending notification: {e}")
    
    def run(self) -> None:
        """Run the Telegram bot (synchronous version)"""
        if not self.application:
            self.logger.error("Telegram bot not properly initialized")
            return
        
        self.logger.info("Starting Telegram bot...")
        self.application.run_polling()
    
    async def run_async(self) -> None:
        """Run the Telegram bot (asynchronous version)"""
        if not self.application:
            self.logger.error("Telegram bot not properly initialized")
            return
        
        self.logger.info("Starting Telegram bot...")
        try:
            # Start the bot with polling
            await self.application.run_polling()
        except asyncio.CancelledError:
            self.logger.info("Telegram bot task cancelled")
        except Exception as e:
            self.logger.error(f"Error in Telegram bot: {e}")
        finally:
            await self.application.stop()
            await self.application.shutdown()
    
    def _is_trade_selection(self, update: Update) -> bool:
        """Check if the message is a trade selection for modification"""
        user_id = update.effective_user.id
        if not hasattr(self, 'user_context') or user_id not in self.user_context:
            return False
        
        user_data = self.user_context[user_id]
        return user_data.get('in_modify_mode', False) and 'trades_list' in user_data
    
    def _is_modify_option_selection(self, update: Update) -> bool:
        """Check if the message is a modify option selection"""
        user_id = update.effective_user.id
        if not hasattr(self, 'user_context') or user_id not in self.user_context:
            return False
        
        user_data = self.user_context[user_id]
        return user_data.get('in_modify_mode', False) and 'selected_trade_id' in user_data
    
    async def _handle_trade_selection(self, update: Update, message_text: str) -> None:
        """Handle trade selection for modification"""
        user_id = update.effective_user.id
        user_data = self.user_context[user_id]
        
        if message_text == "❌ Cancel":
            await self._handle_modify_cancel(update)
            return
        
        trades_list = user_data.get('trades_list', {})
        if message_text not in trades_list:
            await update.message.reply_text("❌ Invalid trade selection. Please try again.")
            return
        
        # Store selected trade ID
        selected_trade_id = trades_list[message_text]
        user_data['selected_trade_id'] = selected_trade_id
        
        # Get order details
        active_orders = self.order_manager.get_active_orders()
        selected_order = None
        for order in active_orders:
            if order['order_id'] == selected_trade_id:
                selected_order = order
                break
        
        if not selected_order:
            await update.message.reply_text("❌ Selected trade not found.")
            return
        
        # Show modify options
        keyboard = [
            ["❌ Cancel Order"],
            ["📊 View Details"],
            ["❌ Back"]
        ]
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        
        await update.message.reply_text(
            f"🔧 What would you like to do with this trade?\n\n"
            f"**{selected_order['symbol']}**\n"
            f"• Entry: ₹{selected_order['price']}\n"
            f"• Qty: {selected_order['quantity']}\n"
            f"• Status: {selected_order['status']}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _handle_modify_option_selection(self, update: Update, message_text: str) -> None:
        """Handle modify option selection"""
        user_id = update.effective_user.id
        user_data = self.user_context[user_id]
        selected_trade_id = user_data.get('selected_trade_id')
        
        if message_text == "❌ Cancel Order":
            # Cancel the order
            success, message = self.order_manager.cancel_order(selected_trade_id)
            await update.message.reply_text(f"❌ {message}")
            await self._handle_modify_cancel(update)
            
        elif message_text == "📊 View Details":
            # Show detailed trade information
            active_orders = self.order_manager.get_active_orders()
            selected_order = None
            for order in active_orders:
                if order['order_id'] == selected_trade_id:
                    selected_order = order
                    break
            
            if selected_order:
                details_msg = f"""
📊 **Trade Details**

**Symbol:** {selected_order['symbol']}
**Order ID:** `{selected_order['order_id']}`
**Entry Price:** ₹{selected_order['price']}
**Quantity:** {selected_order['quantity']}
**Status:** {selected_order['status']}
**Created:** {selected_order['created_at'][:19]}
**Type:** {selected_order['order_type']}
                """
                await update.message.reply_text(details_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Trade details not found.")
                
        elif message_text == "❌ Back":
            await self._handle_modify_cancel(update)
        else:
            await update.message.reply_text("❌ Invalid option. Please try again.")
    
    async def _handle_modify_cancel(self, update: Update) -> None:
        """Handle cancel in modify mode"""
        user_id = update.effective_user.id
        if hasattr(self, 'user_context') and user_id in self.user_context:
            user_data = self.user_context[user_id]
            user_data.pop('in_modify_mode', None)
            user_data.pop('selected_trade_id', None)
            user_data.pop('trades_list', None)
        
        # Show main menu
        await self._show_main_menu(update)
    
    async def stop(self) -> None:
        """Stop the Telegram bot"""
        if self.application:
            await self.application.stop()
            self.logger.info("Telegram bot stopped")
