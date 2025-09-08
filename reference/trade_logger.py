"""
Trade logging module for CSV operations and trade tracking.
Handles trade logging, CSV file management, and trade data persistence.
"""

import csv
import os
from datetime import datetime
from pathlib import Path


class TradeLogger:
    """Handles trade logging and CSV operations."""
    
    def __init__(self, log_file="trade_log.csv"):
        """Initialize trade logger with log file path."""
        self.log_file = log_file
        self._initialize_log_file()
    
    def _initialize_log_file(self):
        """Create log file with headers if it doesn't exist."""
        if not os.path.isfile(self.log_file):
            with open(self.log_file, mode="w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Symbol", "EntryPrice", "EntryTime", "ExitPrice", "ExitTime", "PnL"])
    
    def log_trade_entry(self, symbol, entry_price, entry_time):
        """Log a new trade entry and return the row index."""
        try:
            with open(self.log_file, mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([symbol, entry_price, entry_time, "", "", ""])
            
            # Get the row index (subtract 1 for 0-based indexing, subtract 1 more for header)
            row_index = sum(1 for _ in open(self.log_file)) - 2
            return row_index
        except Exception as e:
            print(f"❌ Error logging trade entry: {e}")
            return None
    
    def update_trade_exit(self, order_id, active_trades, exit_price, exit_time, pnl):
        """Update the CSV row of a trade once exited."""
        try:
            if order_id not in active_trades:
                print(f"⚠️ Order ID {order_id} not found in active trades")
                return False
            
            rows = []
            with open(self.log_file, mode="r") as f:
                rows = list(csv.reader(f))

            row_index = active_trades[order_id].get("log_row")
            if row_index and row_index < len(rows):
                rows[row_index][3] = exit_price
                rows[row_index][4] = exit_time
                rows[row_index][5] = pnl

                with open(self.log_file, mode="w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                return True
            else:
                print(f"⚠️ Invalid row index {row_index} for order {order_id}")
                return False
        except Exception as e:
            print(f"❌ Error updating trade exit: {e}")
            return False
    
    def get_trade_history(self, limit=None):
        """Get trade history from CSV file."""
        try:
            trades = []
            with open(self.log_file, mode="r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trades.append(row)
            
            if limit:
                return trades[-limit:]
            return trades
        except Exception as e:
            print(f"❌ Error reading trade history: {e}")
            return []
    
    def get_active_trades_count(self, active_trades):
        """Get count of currently active trades."""
        return len(active_trades)
    
    def get_total_pnl(self):
        """Calculate total PnL from completed trades."""
        try:
            total_pnl = 0.0
            with open(self.log_file, mode="r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["PnL"] and row["PnL"] != "":
                        try:
                            total_pnl += float(row["PnL"])
                        except ValueError:
                            continue
            return round(total_pnl, 2)
        except Exception as e:
            print(f"❌ Error calculating total PnL: {e}")
            return 0.0

