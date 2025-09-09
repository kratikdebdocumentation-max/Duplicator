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
        """Place order on all connected brokers - PARALLEL EXECUTION for speed"""
        import asyncio
        import concurrent.futures
        import time
        
        start_time = time.time()
        results = {}
        connected_brokers = self.get_connected_brokers()
        
        if not connected_brokers:
            self.logger.warning("No connected brokers available")
            return results
        
        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(connected_brokers)) as executor:
            # Submit all orders simultaneously
            future_to_broker = {
                executor.submit(self._place_order_single, name, broker, order_request): name
                for name, broker in connected_brokers.items()
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_broker):
                broker_name = future_to_broker[future]
                try:
                    response = future.result()
                    results[broker_name] = response
                    
                    if response.success:
                        self.logger.info(f"✅ Order placed on {broker_name}: {response.order_id}")
                    else:
                        self.logger.error(f"❌ Order failed on {broker_name}: {response.message}")
                        
                except Exception as e:
                    self.logger.error(f"💥 Error placing order on {broker_name}: {e}")
                    results[broker_name] = OrderResponse(False, message=str(e))
        
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        self.logger.info(f"🚀 Parallel order execution completed in {execution_time:.2f}ms")
        
        return results
    
    def _place_order_single(self, broker_name: str, broker: Any, order_request: OrderRequest) -> OrderResponse:
        """Place order on a single broker (used for parallel execution)"""
        try:
            return broker.place_order(order_request)
        except Exception as e:
            return OrderResponse(False, message=str(e))
    
    def modify_order_all(self, order_id: str, order_request: OrderRequest) -> Dict[str, OrderResponse]:
        """Modify order on all connected brokers - PARALLEL EXECUTION"""
        import concurrent.futures
        import time
        
        start_time = time.time()
        results = {}
        connected_brokers = self.get_connected_brokers()
        
        if not connected_brokers:
            self.logger.warning("No connected brokers available")
            return results
        
        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(connected_brokers)) as executor:
            future_to_broker = {
                executor.submit(self._modify_order_single, name, broker, order_id, order_request): name
                for name, broker in connected_brokers.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_broker):
                broker_name = future_to_broker[future]
                try:
                    response = future.result()
                    results[broker_name] = response
                    
                    if response.success:
                        self.logger.info(f"✅ Order modified on {broker_name}")
                    else:
                        self.logger.error(f"❌ Order modification failed on {broker_name}: {response.message}")
                        
                except Exception as e:
                    self.logger.error(f"💥 Error modifying order on {broker_name}: {e}")
                    results[broker_name] = OrderResponse(False, message=str(e))
        
        execution_time = (time.time() - start_time) * 1000
        self.logger.info(f"🚀 Parallel order modification completed in {execution_time:.2f}ms")
        
        return results
    
    def _modify_order_single(self, broker_name: str, broker: Any, order_id: str, order_request: OrderRequest) -> OrderResponse:
        """Modify order on a single broker (used for parallel execution)"""
        try:
            return broker.modify_order(order_id, order_request)
        except Exception as e:
            return OrderResponse(False, message=str(e))
    
    def cancel_order_all(self, order_id: str) -> Dict[str, OrderResponse]:
        """Cancel order on all connected brokers - PARALLEL EXECUTION"""
        import concurrent.futures
        import time
        
        start_time = time.time()
        results = {}
        connected_brokers = self.get_connected_brokers()
        
        if not connected_brokers:
            self.logger.warning("No connected brokers available")
            return results
        
        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(connected_brokers)) as executor:
            future_to_broker = {
                executor.submit(self._cancel_order_single, name, broker, order_id): name
                for name, broker in connected_brokers.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_broker):
                broker_name = future_to_broker[future]
                try:
                    response = future.result()
                    results[broker_name] = response
                    
                    if response.success:
                        self.logger.info(f"✅ Order cancelled on {broker_name}")
                    else:
                        self.logger.error(f"❌ Order cancellation failed on {broker_name}: {response.message}")
                        
                except Exception as e:
                    self.logger.error(f"💥 Error cancelling order on {broker_name}: {e}")
                    results[broker_name] = OrderResponse(False, message=str(e))
        
        execution_time = (time.time() - start_time) * 1000
        self.logger.info(f"🚀 Parallel order cancellation completed in {execution_time:.2f}ms")
        
        return results
    
    def _cancel_order_single(self, broker_name: str, broker: Any, order_id: str) -> OrderResponse:
        """Cancel order on a single broker (used for parallel execution)"""
        try:
            return broker.cancel_order(order_id)
        except Exception as e:
            return OrderResponse(False, message=str(e))
    
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
