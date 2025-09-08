"""
WebSocket handler module for real-time data processing.
Handles websocket callbacks and real-time market data updates.
"""

from trading_engine import TradingEngine


class WebSocketHandler:
    """Handles WebSocket callbacks and real-time data processing."""
    
    def __init__(self, trading_engine: TradingEngine):
        """Initialize websocket handler with trading engine."""
        self.trading_engine = trading_engine
        self.config = trading_engine.config
    
    def order_update_callback(self, tick_data):
        """Handles order updates from websocket."""
        print(f"📡 Order Update: {tick_data}")
        # You can add additional order processing logic here
        # For example, updating order status, handling partial fills, etc.
    
    def quote_update_callback(self, tick_data):
        """Handles live quote updates from websocket."""
        try:
            print("🟢 WebSocket tick received:", tick_data)

            symbol = tick_data.get("ts")
            token = tick_data.get("tk")
            price = tick_data.get("lp")

            if token:
                # Keep last seen LTP for this token
                if price:
                    self.config.last_ltp[token] = float(price)
                elif token in self.config.last_ltp:
                    price = self.config.last_ltp[token]
                else:
                    price = 0.0

            print(f"📈 Symbol: {symbol}, Token: {token}, LTP: {price}")

            # Check if any active trades should be exited
            if token and price and price > 0:
                self.trading_engine.check_trade_conditions(symbol, token, price)
            elif token and price == 0:
                print(f"⚠️ Zero price received for {symbol} (Token: {token})")
        except Exception as e:
            print(f"❌ Error in quote_update_callback: {e}")
            # Continue processing other trades even if one fails
    
    def socket_open_callback(self):
        """Called when websocket connection is established."""
        print("🔗 WebSocket connected for Master account")
    
    def start_websocket(self, api_client):
        """Start the websocket feed."""
        try:
            api_client.api.start_websocket(
                order_update_callback=self.order_update_callback,
                subscribe_callback=self.quote_update_callback,
                socket_open_callback=self.socket_open_callback,
            )
            print("✅ WebSocket feed started successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to start websocket: {e}")
            return False

