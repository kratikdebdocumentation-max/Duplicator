"""
WebSocket Manager for Duplicator Trading Bot
Handles real-time order updates and price feeds from multiple brokers
"""

import asyncio
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass

from ..brokers.broker_manager import BrokerManager
from ..orders.order_manager import OrderManager
from ..utils.config_manager import config
from ..utils.logger import get_logger


@dataclass
class PriceUpdate:
    """Price update data structure"""
    symbol: str
    exchange: str
    token: str
    last_price: float
    volume: int
    timestamp: datetime
    broker: str


@dataclass
class OrderUpdate:
    """Order update data structure"""
    order_id: str
    broker: str
    status: str
    symbol: str
    quantity: int
    price: float
    filled_quantity: int
    average_price: float
    timestamp: datetime
    remarks: Optional[str] = None


class WebSocketManager:
    """Manages websocket connections for all brokers"""
    
    def __init__(self, broker_manager: BrokerManager, order_manager: OrderManager):
        self.broker_manager = broker_manager
        self.order_manager = order_manager
        self.logger = get_logger('websocket_manager')
        
        # WebSocket configuration
        self.ws_config = config.get_websocket_config()
        self.reconnect_attempts = self.ws_config.get('reconnect_attempts', 5)
        self.reconnect_delay = self.ws_config.get('reconnect_delay', 5)
        self.heartbeat_interval = self.ws_config.get('heartbeat_interval', 30)
        
        # Callbacks
        self._order_callbacks: List[Callable] = []
        self._price_callbacks: List[Callable] = []
        
        # State
        self.is_running = False
        self._monitor_thread = None
        self._heartbeat_thread = None
        self._subscribed_symbols: Dict[str, List[str]] = {}  # broker -> symbols
        
    def add_order_callback(self, callback: Callable) -> None:
        """Add order update callback"""
        self._order_callbacks.append(callback)
    
    def add_price_callback(self, callback: Callable) -> None:
        """Add price update callback"""
        self._price_callbacks.append(callback)
    
    def start(self) -> None:
        """Start websocket connections with optimized strategy"""
        try:
            self.logger.info("Starting websocket connections...")
            self.is_running = True
            
            # Get connected brokers
            connected_brokers = self.broker_manager.get_connected_brokers()
            if not connected_brokers:
                self.logger.error("No connected brokers available")
                self.is_running = False
                return
            
            # Start websockets with different strategies
            self._start_optimized_websockets(connected_brokers)
            
            # Start monitoring thread
            self._monitor_thread = threading.Thread(target=self._monitor_connections, daemon=True)
            self._monitor_thread.start()
            
            # Start heartbeat thread
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
            self._heartbeat_thread.start()
            
            self.logger.info("Websocket connections started successfully")
            
        except Exception as e:
            self.logger.error(f"Error starting websockets: {e}")
            self.is_running = False
    
    def _start_optimized_websockets(self, connected_brokers: Dict[str, Any]) -> None:
        """Start websockets with optimized strategy:
        - Price/Quote updates: Only Broker 1
        - Order updates: Both brokers individually
        """
        try:
            broker_names = list(connected_brokers.keys())
            
            if not broker_names:
                self.logger.error("No brokers available for websocket setup")
                return
            
            # Get the first broker (Broker 1) for price/quote updates
            primary_broker_name = broker_names[0]
            primary_broker = connected_brokers[primary_broker_name]
            
            self.logger.info(f"Setting up websockets:")
            self.logger.info(f"  - Price/Quote updates: {primary_broker_name} only")
            self.logger.info(f"  - Order updates: All brokers ({', '.join(broker_names)})")
            
            # Start websocket for primary broker (Broker 1) with both callbacks
            try:
                primary_broker.start_websocket(
                    order_callback=self._handle_order_update,
                    quote_callback=self._handle_quote_update
                )
                self.logger.info(f"Started websocket for {primary_broker_name} (price + order updates)")
            except Exception as e:
                self.logger.error(f"Failed to start websocket for {primary_broker_name}: {e}")
            
            # Start websockets for other brokers with only order callbacks
            for broker_name in broker_names[1:]:
                try:
                    broker = connected_brokers[broker_name]
                    broker.start_websocket(
                        order_callback=self._handle_order_update,
                        quote_callback=None  # No price updates for secondary brokers
                    )
                    self.logger.info(f"Started websocket for {broker_name} (order updates only)")
                except Exception as e:
                    self.logger.error(f"Failed to start websocket for {broker_name}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error in optimized websocket setup: {e}")
    
    def stop(self) -> None:
        """Stop websocket connections"""
        try:
            self.logger.info("Stopping websocket connections...")
            self.is_running = False
            
            # Stop websockets for all brokers
            self.broker_manager.stop_websockets_all()
            
            # Wait for threads to finish
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)
            if self._heartbeat_thread:
                self._heartbeat_thread.join(timeout=5)
            
            self.logger.info("Websocket connections stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping websockets: {e}")
    
    def subscribe_symbol(self, symbol: str, exchange: str = "NFO") -> bool:
        """Subscribe to symbol for price updates (Broker 1 only)"""
        try:
            connected_brokers = self.broker_manager.get_connected_brokers()
            if not connected_brokers:
                self.logger.warning("No connected brokers available for subscription")
                return False
            
            # Get the first broker (Broker 1) for price subscriptions
            broker_names = list(connected_brokers.keys())
            primary_broker_name = broker_names[0]
            primary_broker = connected_brokers[primary_broker_name]
            
            try:
                # Format symbol for websocket subscription
                ws_symbol = f"{exchange}|{symbol}"
                if primary_broker.subscribe(ws_symbol):
                    if primary_broker_name not in self._subscribed_symbols:
                        self._subscribed_symbols[primary_broker_name] = []
                    self._subscribed_symbols[primary_broker_name].append(ws_symbol)
                    self.logger.info(f"Subscribed to {symbol} for price updates on {primary_broker_name}")
                    return True
                else:
                    self.logger.error(f"Failed to subscribe to {symbol} on {primary_broker_name}")
                    return False
            except Exception as e:
                self.logger.error(f"Error subscribing to {symbol} on {primary_broker_name}: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error subscribing to symbol {symbol}: {e}")
            return False
    
    def unsubscribe_symbol(self, symbol: str, exchange: str = "NFO") -> bool:
        """Unsubscribe from symbol for price updates (Broker 1 only)"""
        try:
            connected_brokers = self.broker_manager.get_connected_brokers()
            if not connected_brokers:
                self.logger.warning("No connected brokers available for unsubscription")
                return False
            
            # Get the first broker (Broker 1) for price unsubscriptions
            broker_names = list(connected_brokers.keys())
            primary_broker_name = broker_names[0]
            primary_broker = connected_brokers[primary_broker_name]
            
            ws_symbol = f"{exchange}|{symbol}"
            
            try:
                if primary_broker.unsubscribe(ws_symbol):
                    if primary_broker_name in self._subscribed_symbols:
                        self._subscribed_symbols[primary_broker_name] = [
                            s for s in self._subscribed_symbols[primary_broker_name] if s != ws_symbol
                        ]
                    self.logger.info(f"Unsubscribed from {symbol} for price updates on {primary_broker_name}")
                    return True
                else:
                    self.logger.error(f"Failed to unsubscribe from {symbol} on {primary_broker_name}")
                    return False
            except Exception as e:
                self.logger.error(f"Error unsubscribing from {symbol} on {primary_broker_name}: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error unsubscribing from symbol {symbol}: {e}")
            return False
    
    def _handle_order_update(self, order_data: Dict[str, Any]) -> None:
        """Handle order update from broker websocket"""
        try:
            # Determine which broker this update came from
            # We need to identify the broker based on the order data or context
            broker_name = self._identify_broker_from_order_data(order_data)
            
            # Extract order information
            order_update = OrderUpdate(
                order_id=order_data.get('norenordno', ''),
                broker=broker_name,
                status=order_data.get('status', ''),
                symbol=order_data.get('tsym', ''),
                quantity=int(order_data.get('qty', 0)),
                price=float(order_data.get('prc', 0)),
                filled_quantity=int(order_data.get('fillshares', 0)),
                average_price=float(order_data.get('avgprc', 0)),
                timestamp=datetime.now(),
                remarks=order_data.get('remarks', '')
            )
            
            # Update order manager
            self.order_manager.handle_order_update(broker_name, order_data)
            
            # Notify callbacks
            for callback in self._order_callbacks:
                try:
                    callback(order_update)
                except Exception as e:
                    self.logger.error(f"Error in order callback: {e}")
            
            # Log significant order updates
            if order_update.status in ['COMPLETE', 'CANCELLED', 'REJECTED']:
                self.logger.info(
                    f"Order {order_update.order_id} status: {order_update.status} "
                    f"on {order_update.broker} for {order_update.symbol}"
                )
                
        except Exception as e:
            self.logger.error(f"Error handling order update: {e}")
    
    def _identify_broker_from_order_data(self, order_data: Dict[str, Any]) -> str:
        """Identify which broker an order update came from"""
        try:
            # Check if broker name is provided in the order data
            broker_name = order_data.get('broker_name')
            if broker_name:
                return broker_name
            
            # Fallback: try to identify from other fields
            # This might need to be enhanced based on how Shoonya API provides broker identification
            connected_brokers = self.broker_manager.get_connected_brokers()
            
            if not connected_brokers:
                return "unknown"
            
            # For now, return the first available broker as fallback
            return list(connected_brokers.keys())[0]
            
        except Exception as e:
            self.logger.error(f"Error identifying broker from order data: {e}")
            return "unknown"
    
    def _handle_quote_update(self, quote_data: Dict[str, Any]) -> None:
        """Handle quote update from broker websocket (Broker 1 only)"""
        try:
            # Identify broker (should be Broker 1 for price updates)
            broker_name = quote_data.get('broker_name', 'broker1')
            
            # Extract quote information
            price_update = PriceUpdate(
                symbol=quote_data.get('tsym', ''),
                exchange=quote_data.get('exch', ''),
                token=quote_data.get('token', ''),
                last_price=float(quote_data.get('lp', 0)),
                volume=int(quote_data.get('vol', 0)),
                timestamp=datetime.now(),
                broker=broker_name
            )
            
            # Notify callbacks
            for callback in self._price_callbacks:
                try:
                    callback(price_update)
                except Exception as e:
                    self.logger.error(f"Error in price callback: {e}")
            
            # Log price updates (debug level to avoid spam)
            self.logger.debug(
                f"Price update from {broker_name}: {price_update.symbol} = ₹{price_update.last_price}"
            )
                
        except Exception as e:
            self.logger.error(f"Error handling quote update: {e}")
    
    def _monitor_connections(self) -> None:
        """Monitor websocket connections and reconnect if needed"""
        while self.is_running:
            try:
                # Check broker health
                broker_status = self.broker_manager.get_health_status()
                disconnected_brokers = [
                    name for name, status in broker_status.items() if not status
                ]
                
                if disconnected_brokers:
                    self.logger.warning(f"Disconnected brokers detected: {disconnected_brokers}")
                    
                    # Attempt to reconnect
                    for broker_name in disconnected_brokers:
                        self.logger.info(f"Attempting to reconnect {broker_name}...")
                        if self.broker_manager.reconnect_broker(broker_name):
                            self.logger.info(f"Successfully reconnected {broker_name}")
                        else:
                            self.logger.error(f"Failed to reconnect {broker_name}")
                
                # Sleep before next check
                time.sleep(self.reconnect_delay)
                
            except Exception as e:
                self.logger.error(f"Error in connection monitor: {e}")
                time.sleep(self.reconnect_delay)
    
    def _heartbeat_worker(self) -> None:
        """Send periodic heartbeat to keep connections alive"""
        while self.is_running:
            try:
                # Log connection status
                broker_status = self.broker_manager.get_health_status()
                connected_count = sum(1 for status in broker_status.values() if status)
                total_count = len(broker_status)
                
                self.logger.debug(f"Heartbeat: {connected_count}/{total_count} brokers connected")
                
                # Sleep for heartbeat interval
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Error in heartbeat worker: {e}")
                time.sleep(self.heartbeat_interval)
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get websocket connection status"""
        broker_status = self.broker_manager.get_health_status()
        connected_brokers = [name for name, status in broker_status.items() if status]
        
        return {
            'is_running': self.is_running,
            'total_brokers': len(broker_status),
            'connected_brokers': len(connected_brokers),
            'broker_status': broker_status,
            'subscribed_symbols': self._subscribed_symbols
        }
    
    def get_subscribed_symbols(self) -> List[str]:
        """Get list of all subscribed symbols"""
        all_symbols = []
        for symbols in self._subscribed_symbols.values():
            all_symbols.extend(symbols)
        return list(set(all_symbols))
    
    def cleanup_subscriptions(self) -> None:
        """Clean up all subscriptions"""
        try:
            for broker_name, symbols in self._subscribed_symbols.items():
                broker = self.broker_manager.get_broker(broker_name)
                if broker:
                    for symbol in symbols:
                        try:
                            broker.unsubscribe(symbol)
                        except Exception as e:
                            self.logger.error(f"Error unsubscribing {symbol} from {broker_name}: {e}")
            
            self._subscribed_symbols.clear()
            self.logger.info("Cleaned up all subscriptions")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up subscriptions: {e}")
