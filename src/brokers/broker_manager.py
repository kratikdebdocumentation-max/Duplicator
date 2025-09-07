"""
Broker Manager for Duplicator Trading Bot
Manages multiple broker instances and provides unified interface
"""

from typing import Dict, List, Optional, Any
from .base_broker import BaseBroker, OrderRequest, OrderResponse
from .shoonya_broker import ShoonyaBroker
from ..utils.config_manager import config
from ..utils.logger import get_logger


class BrokerManager:
    """Manages multiple broker instances"""
    
    def __init__(self):
        self.logger = get_logger('broker_manager')
        self.brokers: Dict[str, BaseBroker] = {}
        self._initialize_brokers()
    
    def _initialize_brokers(self) -> None:
        """Initialize all enabled brokers"""
        enabled_brokers = config.get_enabled_brokers()
        
        for broker_name, broker_config in enabled_brokers.items():
            try:
                broker = self._create_broker(broker_name, broker_config)
                if broker:
                    self.brokers[broker_name] = broker
                    self.logger.info(f"Initialized broker: {broker_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize broker {broker_name}: {e}")
    
    def _create_broker(self, name: str, broker_config: Dict[str, Any]) -> Optional[BaseBroker]:
        """Create broker instance based on configuration"""
        api_type = broker_config.get('api_type', '').lower()
        credentials_file = broker_config.get('credentials_file')
        
        if api_type == 'shoonya':
            if not credentials_file:
                self.logger.error(f"No credentials file specified for {name}")
                return None
            
            return ShoonyaBroker(name, credentials_file)
        else:
            self.logger.error(f"Unsupported broker type: {api_type}")
            return None
    
    def connect_all(self) -> Dict[str, bool]:
        """Connect to all brokers, exit program if any connection fails"""
        results = {}
        for name, broker in self.brokers.items():
            try:
                results[name] = broker.connect()
                if results[name]:
                    self.logger.info(f"Connected to {name}")
                else:
                    self.logger.error(f"Failed to connect to {name}")
                    raise RuntimeError(f"Failed to connect to broker {name}. Exiting program.")
            except Exception as e:
                self.logger.error(f"Error connecting to {name}: {e}")
                raise RuntimeError(f"Error connecting to broker {name}: {e}. Exiting program.")
        
        return results
    
    def disconnect_all(self) -> None:
        """Disconnect from all brokers"""
        for name, broker in self.brokers.items():
            try:
                broker.disconnect()
                self.logger.info(f"Disconnected from {name}")
            except Exception as e:
                self.logger.error(f"Error disconnecting from {name}: {e}")
    
    def get_broker(self, name: str) -> Optional[BaseBroker]:
        """Get specific broker instance"""
        return self.brokers.get(name)
    
    def get_connected_brokers(self) -> Dict[str, BaseBroker]:
        """Get all connected brokers"""
        return {name: broker for name, broker in self.brokers.items() 
                if broker.is_healthy()}
    
    def place_order_all(self, order_request: OrderRequest) -> Dict[str, OrderResponse]:
        """Place order on all connected brokers"""
        results = {}
        connected_brokers = self.get_connected_brokers()
        
        if not connected_brokers:
            self.logger.warning("No connected brokers available")
            return results
        
        for name, broker in connected_brokers.items():
            try:
                response = broker.place_order(order_request)
                results[name] = response
                
                if response.success:
                    self.logger.info(f"Order placed successfully on {name}: {response.order_id}")
                else:
                    self.logger.error(f"Order failed on {name}: {response.message}")
                    
            except Exception as e:
                self.logger.error(f"Error placing order on {name}: {e}")
                results[name] = OrderResponse(False, message=str(e))
        
        return results
    
    def modify_order_all(self, order_id: str, order_request: OrderRequest) -> Dict[str, OrderResponse]:
        """Modify order on all connected brokers"""
        results = {}
        connected_brokers = self.get_connected_brokers()
        
        for name, broker in connected_brokers.items():
            try:
                response = broker.modify_order(order_id, order_request)
                results[name] = response
                
                if response.success:
                    self.logger.info(f"Order modified successfully on {name}")
                else:
                    self.logger.error(f"Order modification failed on {name}: {response.message}")
                    
            except Exception as e:
                self.logger.error(f"Error modifying order on {name}: {e}")
                results[name] = OrderResponse(False, message=str(e))
        
        return results
    
    def cancel_order_all(self, order_id: str) -> Dict[str, OrderResponse]:
        """Cancel order on all connected brokers"""
        results = {}
        connected_brokers = self.get_connected_brokers()
        
        for name, broker in connected_brokers.items():
            try:
                response = broker.cancel_order(order_id)
                results[name] = response
                
                if response.success:
                    self.logger.info(f"Order cancelled successfully on {name}")
                else:
                    self.logger.error(f"Order cancellation failed on {name}: {response.message}")
                    
            except Exception as e:
                self.logger.error(f"Error cancelling order on {name}: {e}")
                results[name] = OrderResponse(False, message=str(e))
        
        return results
    
    def get_all_positions(self) -> Dict[str, List[Any]]:
        """Get positions from all connected brokers"""
        results = {}
        connected_brokers = self.get_connected_brokers()
        
        for name, broker in connected_brokers.items():
            try:
                positions = broker.get_positions()
                results[name] = positions
                self.logger.debug(f"Retrieved {len(positions)} positions from {name}")
            except Exception as e:
                self.logger.error(f"Error getting positions from {name}: {e}")
                results[name] = []
        
        return results
    
    def get_all_order_books(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get order books from all connected brokers"""
        results = {}
        connected_brokers = self.get_connected_brokers()
        
        for name, broker in connected_brokers.items():
            try:
                order_book = broker.get_order_book()
                results[name] = order_book
                self.logger.debug(f"Retrieved {len(order_book)} orders from {name}")
            except Exception as e:
                self.logger.error(f"Error getting order book from {name}: {e}")
                results[name] = []
        
        return results
    
    def start_websockets_all(self, 
                           order_callback: Optional[Any] = None,
                           quote_callback: Optional[Any] = None) -> None:
        """Start websockets for all connected brokers"""
        connected_brokers = self.get_connected_brokers()
        
        for name, broker in connected_brokers.items():
            try:
                broker.start_websocket(order_callback, quote_callback)
                self.logger.info(f"Started websocket for {name}")
            except Exception as e:
                self.logger.error(f"Error starting websocket for {name}: {e}")
    
    def stop_websockets_all(self) -> None:
        """Stop websockets for all brokers"""
        for name, broker in self.brokers.items():
            try:
                broker.stop_websocket()
                self.logger.info(f"Stopped websocket for {name}")
            except Exception as e:
                self.logger.error(f"Error stopping websocket for {name}: {e}")
    
    def get_health_status(self) -> Dict[str, bool]:
        """Get health status of all brokers"""
        return {name: broker.is_healthy() for name, broker in self.brokers.items()}
    
    def reconnect_broker(self, name: str) -> bool:
        """Reconnect specific broker"""
        broker = self.brokers.get(name)
        if not broker:
            self.logger.error(f"Broker {name} not found")
            return False
        
        try:
            broker.disconnect()
            return broker.connect()
        except Exception as e:
            self.logger.error(f"Error reconnecting {name}: {e}")
            return False
