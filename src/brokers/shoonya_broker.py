"""
Shoonya broker implementation for Duplicator Trading Bot
Implements the BaseBroker interface for Shoonya API
"""

import json
import pyotp
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from retrying import retry

# Import the Shoonya API (assuming it's available)
try:
    from NorenRestApiPy.NorenApi import NorenApi
except ImportError:
    print("Warning: NorenRestApiPy not found. Please install it.")
    NorenApi = None

from .base_broker import (
    BaseBroker, OrderRequest, OrderResponse, Position, 
    OrderType, ProductType, PriceType
)
from ..utils.logger import get_logger


class ShoonyaBroker(BaseBroker):
    """Shoonya broker implementation"""
    
    def __init__(self, name: str, credentials_file: str):
        self.credentials_file = Path(credentials_file)
        credentials = self._load_credentials()
        super().__init__(name, credentials)
        
        self.logger = get_logger(f'shoonya_{name}')
        self.api = None
        self._websocket_thread = None
        self._stop_websocket = False
    
    def _load_credentials(self) -> Dict[str, Any]:
        """Load credentials from JSON file"""
        try:
            with open(self.credentials_file, 'r') as file:
                return json.load(file)
        except Exception as e:
            raise RuntimeError(f"Failed to load credentials from {self.credentials_file}: {e}")
    
    def connect(self) -> bool:
        """Connect to Shoonya API"""
        try:
            if NorenApi is None:
                raise RuntimeError("NorenRestApiPy not available")
            
            self.api = NorenApi(
                host='https://api.shoonya.com/NorenWClientTP/',
                websocket='wss://api.shoonya.com/NorenWSTP/'
            )
            
            # Generate TOTP
            totp = pyotp.TOTP(self.credentials['factor2']).now()
            
            # Login
            login_response = self.api.login(
                userid=self.credentials['username'],
                password=self.credentials['pwd'],
                twoFA=totp,
                vendor_code=self.credentials['vc'],
                api_secret=self.credentials['app_key'],
                imei=self.credentials['imei']
            )
            
            if login_response and 'uname' in login_response:
                self.is_connected = True
                self._last_login_time = time.strftime('%Y-%m-%d %H:%M:%S')
                self.logger.info(f"Successfully connected to Shoonya as {login_response['uname']}")
                return True
            else:
                self.logger.error("Failed to connect to Shoonya API")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Shoonya API"""
        try:
            if self.api:
                self.stop_websocket()
                self.api = None
            self.is_connected = False
            self.logger.info("Disconnected from Shoonya API")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def place_order(self, order_request: OrderRequest) -> OrderResponse:
        """Place an order"""
        try:
            if not self.is_connected:
                return OrderResponse(False, message="Not connected to broker")
            
            response = self.api.place_order(
                buy_or_sell=order_request.buy_or_sell.value,
                product_type=order_request.product_type.value,
                exchange=order_request.exchange,
                tradingsymbol=order_request.tradingsymbol,
                quantity=order_request.quantity,
                discloseqty=order_request.discloseqty,
                price_type=order_request.price_type.value,
                price=order_request.price,
                trigger_price=order_request.trigger_price,
                retention=order_request.retention,
                remarks=order_request.remarks
            )
            
            if response and 'norenordno' in response:
                self.logger.info(f"Order placed successfully: {response['norenordno']}")
                return OrderResponse(True, order_id=response['norenordno'])
            else:
                error_msg = response.get('emsg', 'Unknown error') if response else 'No response'
                self.logger.error(f"Order placement failed: {error_msg}")
                return OrderResponse(False, message=error_msg)
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return OrderResponse(False, message=str(e))
    
    def modify_order(self, order_id: str, order_request: OrderRequest) -> OrderResponse:
        """Modify an existing order"""
        try:
            if not self.is_connected:
                return OrderResponse(False, message="Not connected to broker")
            
            response = self.api.modify_order(
                exchange=order_request.exchange,
                tradingsymbol=order_request.tradingsymbol,
                orderno=order_id,
                newquantity=order_request.quantity,
                newprice_type=order_request.price_type.value,
                newprice=order_request.price
            )
            
            if response and 'norenordno' in response:
                self.logger.info(f"Order modified successfully: {order_id}")
                return OrderResponse(True, order_id=order_id)
            else:
                error_msg = response.get('emsg', 'Unknown error') if response else 'No response'
                self.logger.error(f"Order modification failed: {error_msg}")
                return OrderResponse(False, message=error_msg)
                
        except Exception as e:
            self.logger.error(f"Error modifying order: {e}")
            return OrderResponse(False, message=str(e))
    
    def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel an order"""
        try:
            if not self.is_connected:
                return OrderResponse(False, message="Not connected to broker")
            
            response = self.api.cancel_order(orderno=order_id)
            
            if response and 'norenordno' in response:
                self.logger.info(f"Order cancelled successfully: {order_id}")
                return OrderResponse(True, order_id=order_id)
            else:
                error_msg = response.get('emsg', 'Unknown error') if response else 'No response'
                self.logger.error(f"Order cancellation failed: {error_msg}")
                return OrderResponse(False, message=error_msg)
                
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return OrderResponse(False, message=str(e))
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status"""
        try:
            if not self.is_connected:
                return {"error": "Not connected to broker"}
            
            order_book = self.api.get_order_book()
            for order in order_book:
                if order.get('norenordno') == order_id:
                    return order
            return {"error": "Order not found"}
            
        except Exception as e:
            self.logger.error(f"Error getting order status: {e}")
            return {"error": str(e)}
    
    def get_order_book(self) -> List[Dict[str, Any]]:
        """Get order book"""
        try:
            if not self.is_connected:
                return []
            
            return self.api.get_order_book()
            
        except Exception as e:
            self.logger.error(f"Error getting order book: {e}")
            return []
    
    def get_positions(self) -> List[Position]:
        """Get current positions"""
        try:
            if not self.is_connected:
                return []
            
            positions_data = self.api.get_positions()
            positions = []
            
            for pos in positions_data:
                position = Position(
                    symbol=pos.get('tsym', ''),
                    quantity=int(pos.get('netqty', 0)),
                    average_price=float(pos.get('netprice', 0)),
                    current_price=float(pos.get('lp', 0)),
                    pnl=float(pos.get('rpnl', 0)),
                    mtm=float(pos.get('urmtom', 0))
                )
                positions.append(position)
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    def get_quotes(self, exchange: str, token: str) -> Dict[str, Any]:
        """Get quotes for a symbol"""
        try:
            if not self.is_connected:
                return {"error": "Not connected to broker"}
            
            return self.api.get_quotes(exchange=exchange, token=token)
            
        except Exception as e:
            self.logger.error(f"Error getting quotes: {e}")
            return {"error": str(e)}
    
    def start_websocket(self, 
                       order_callback: Optional[Callable] = None,
                       quote_callback: Optional[Callable] = None) -> None:
        """Start websocket connection for real-time updates"""
        try:
            if not self.is_connected:
                self.logger.error("Cannot start websocket: Not connected to broker")
                return
            
            if order_callback:
                self.add_order_callback(order_callback)
            if quote_callback:
                self.add_quote_callback(quote_callback)
            
            self._stop_websocket = False
            self._websocket_thread = threading.Thread(
                target=self._websocket_worker,
                daemon=True
            )
            self._websocket_thread.start()
            self.logger.info("Websocket started")
            
        except Exception as e:
            self.logger.error(f"Error starting websocket: {e}")
    
    def stop_websocket(self) -> None:
        """Stop websocket connection"""
        try:
            self._stop_websocket = True
            if self._websocket_thread:
                self._websocket_thread.join(timeout=5)
            self.logger.info("Websocket stopped")
        except Exception as e:
            self.logger.error(f"Error stopping websocket: {e}")
    
    def _websocket_worker(self) -> None:
        """Websocket worker thread"""
        try:
            self.api.start_websocket(
                order_update_callback=self._on_order_update,
                subscribe_callback=self._on_quote_update,
                socket_open_callback=self._on_socket_open
            )
        except Exception as e:
            self.logger.error(f"Websocket worker error: {e}")
    
    def _on_order_update(self, order_data: Dict[str, Any]) -> None:
        """Handle order update from websocket"""
        # Add broker name to order data for identification
        order_data['broker_name'] = self.name
        self.logger.debug(f"Order update from {self.name}: {order_data}")
        self._notify_order_update(order_data)
    
    def _on_quote_update(self, quote_data: Dict[str, Any]) -> None:
        """Handle quote update from websocket"""
        # Add broker name to quote data for identification
        quote_data['broker_name'] = self.name
        self.logger.debug(f"Quote update from {self.name}: {quote_data}")
        self._notify_quote_update(quote_data)
    
    def _on_socket_open(self) -> None:
        """Handle websocket open event"""
        self.logger.info("Websocket connection opened")
    
    def subscribe(self, symbol: str) -> bool:
        """Subscribe to symbol for real-time updates"""
        try:
            if not self.is_connected:
                return False
            
            self.api.subscribe(symbol)
            self.logger.info(f"Subscribed to {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to {symbol}: {e}")
            return False
    
    def unsubscribe(self, symbol: str) -> bool:
        """Unsubscribe from symbol"""
        try:
            if not self.is_connected:
                return False
            
            self.api.unsubscribe(symbol)
            self.logger.info(f"Unsubscribed from {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unsubscribing from {symbol}: {e}")
            return False
    
    def is_healthy(self) -> bool:
        """Check if broker is healthy and connected"""
        return self.is_connected and self.api is not None
    
    def get_orders_today(self) -> int:
        """Get count of orders placed today"""
        try:
            if not self.is_connected or not self.api:
                return 0
            
            # Get today's date
            from datetime import datetime
            today = datetime.now().strftime('%d-%m-%Y')
            
            # Get order book for today
            order_book = self.api.get_order_book()
            if order_book and isinstance(order_book, list):
                # Count orders from today
                today_orders = [order for order in order_book 
                              if order.get('d', '').startswith(today)]
                return len(today_orders)
            return 0
        except Exception as e:
            self.logger.error(f"Error getting orders today: {e}")
            return 0
    
    def get_success_rate(self) -> float:
        """Get success rate of orders"""
        try:
            if not self.is_connected or not self.api:
                return 0.0
            
            order_book = self.api.get_order_book()
            if not order_book or not isinstance(order_book, list):
                return 0.0
            
            total_orders = len(order_book)
            if total_orders == 0:
                return 0.0
            
            # Count completed orders
            completed_orders = len([order for order in order_book 
                                  if order.get('status') == 'COMPLETE'])
            
            return (completed_orders / total_orders) * 100
        except Exception as e:
            self.logger.error(f"Error getting success rate: {e}")
            return 0.0
    
    def get_pnl_today(self) -> float:
        """Get P&L for today"""
        try:
            if not self.is_connected or not self.api:
                return 0.0
            
            positions = self.api.get_positions()
            if not positions or not isinstance(positions, list):
                return 0.0
            
            total_pnl = sum(float(pos.get('pnl', 0)) for pos in positions)
            return total_pnl
        except Exception as e:
            self.logger.error(f"Error getting P&L today: {e}")
            return 0.0
    
    def get_active_orders_count(self) -> int:
        """Get count of active orders"""
        try:
            if not self.is_connected or not self.api:
                return 0
            
            order_book = self.api.get_order_book()
            if not order_book or not isinstance(order_book, list):
                return 0
            
            # Count active orders (PENDING, OPEN)
            active_statuses = ['PENDING', 'OPEN', 'TRIGGER_PENDING']
            active_orders = len([order for order in order_book 
                               if order.get('status') in active_statuses])
            return active_orders
        except Exception as e:
            self.logger.error(f"Error getting active orders count: {e}")
            return 0
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        try:
            if not self.is_connected or not self.api:
                return {}
            
            return {
                "session_id": getattr(self.api, 'session_id', 'N/A'),
                "last_heartbeat": getattr(self.api, 'last_heartbeat', None),
                "user_id": self.credentials.get('username', 'N/A'),
                "api_type": "shoonya"
            }
        except Exception as e:
            self.logger.error(f"Error getting connection info: {e}")
            return {}
    
    @property
    def last_login_time(self) -> Optional[str]:
        """Get last login time"""
        if hasattr(self, '_last_login_time'):
            return self._last_login_time
        return None
    
    @property
    def api_type(self) -> str:
        """Get API type"""
        return "shoonya"