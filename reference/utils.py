"""
Utility functions for the Order Executor trading bot.
Contains helper functions for common operations.
"""

import re


def parse_percentage(value_str):
    """
    Parse percentage value from string, handling both formats:
    - "0.2" -> 0.2
    - "0.2%" -> 0.2
    - "0.2 %" -> 0.2
    """
    if not value_str:
        raise ValueError("Empty value provided")
    
    # Remove any whitespace
    value_str = value_str.strip()
    
    # Remove % symbol if present
    if value_str.endswith('%'):
        value_str = value_str[:-1].strip()
    
    try:
        # Convert to float
        value = float(value_str)
        
        # Validate range (0-100% is reasonable for trading)
        if value < 0:
            raise ValueError("Percentage cannot be negative")
        if value > 100:
            raise ValueError("Percentage cannot exceed 100%")
            
        return value
    except ValueError as e:
        if "could not convert" in str(e):
            raise ValueError(f"Invalid percentage format: '{value_str}'. Use format like '0.2' or '0.2%'")
        else:
            raise e


def calculate_pnl(entry_price, exit_price, quantity):
    """
    Calculate Profit/Loss for a trade.
    
    Args:
        entry_price: Entry price of the trade
        exit_price: Exit price of the trade
        quantity: Quantity of shares
    
    Returns:
        tuple: (pnl_amount, pnl_percentage)
    """
    pnl_amount = round((exit_price - entry_price) * quantity, 2)
    pnl_percentage = round(((exit_price - entry_price) / entry_price) * 100, 2)
    
    return pnl_amount, pnl_percentage


def format_pnl_message(entry_price, sl_price, target_price, quantity):
    """
    Format PnL information for order confirmation message.
    
    Args:
        entry_price: Entry price
        sl_price: Stoploss price
        target_price: Target price
        quantity: Quantity
    
    Returns:
        str: Formatted PnL message
    """
    # Calculate loss on SL hit
    sl_loss, sl_loss_pct = calculate_pnl(entry_price, sl_price, quantity)
    
    # Calculate profit on target hit
    target_profit, target_profit_pct = calculate_pnl(entry_price, target_price, quantity)
    
    return (
        f"📉 Loss on SL: ₹{sl_loss} ({sl_loss_pct}%)\n"
        f"📈 Profit on Target: ₹{target_profit} ({target_profit_pct}%)"
    )


def is_market_open():
    """
    Check if the Indian stock market is currently open.
    
    Returns:
        bool: True if market is open, False otherwise
    """
    from datetime import datetime
    import pytz
    
    # Get current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # Market hours: 9:15 AM to 3:30 PM IST (Monday to Friday)
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    # Check if it's a weekday and within market hours
    is_weekday = now.weekday() < 5  # Monday = 0, Sunday = 6
    is_market_hours = market_open <= now <= market_close
    
    return is_weekday and is_market_hours
