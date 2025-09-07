"""
Base broker interface for Duplicator Trading Bot
Defines the abstract interface that all broker implementations must follow
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class OrderType(Enum):
    """Order type enumeration"""
    BUY = "B"
    SELL = "S"


class ProductType(Enum):
    """Product type enumeration"""
    INTRADAY = "I"
    DELIVERY = "D"
    MARGIN = "M"


class PriceType(Enum):
    """Price type enumeration"""
    LIMIT = "LMT"
    MARKET = "MKT"
    STOP_LOSS = "SL"
    STOP_LOSS_MARKET = "SL-M"


@dataclass
class OrderRequest:
    """Order request data structure"""
    buy_or_sell: OrderType
    product_type: ProductType
    exchange: str
    tradingsymbol: str
    quantity: int
    price_type: PriceType
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    discloseqty: int = 0
    retention: str = "DAY"
    remarks: Optional[str] = None


@dataclass
class OrderResponse:
    """Order response data structure"""
    success: bool
    order_id: Optional[str] = None
    message: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class Position:
    """Position data structure"""
    symbol: str
    quantity: int
    average_price: float
    current_price: float
    pnl: float
    mtm: float


class BaseBroker(ABC):
    """Abstract base class for broker implementations"""
    
    def __init__(self, name: str, credentials: Dict[str, Any]):
        self.name = name
        self.credentials = credentials
        self.is_connected = False
        self._order_callbacks: List[Callable] = []
        self._quote_callbacks: List[Callable] = []
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker API"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker API"""
        pass
    
    @abstractmethod
    def place_order(self, order_request: OrderRequest) -> OrderResponse:
        """Place an order"""
        pass
    
    @abstractmethod
    def modify_order(self, order_id: str, order_request: OrderRequest) -> OrderResponse:
        """Modify an existing order"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status"""
        pass
    
    @abstractmethod
    def get_order_book(self) -> List[Dict[str, Any]]:
        """Get order book"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get current positions"""
        pass
    
    @abstractmethod
    def get_quotes(self, exchange: str, token: str) -> Dict[str, Any]:
        """Get quotes for a symbol"""
        pass
    
    @abstractmethod
    def start_websocket(self, 
                       order_callback: Optional[Callable] = None,
                       quote_callback: Optional[Callable] = None) -> None:
        """Start websocket connection for real-time updates"""
        pass
    
    @abstractmethod
    def stop_websocket(self) -> None:
        """Stop websocket connection"""
        pass
    
    @abstractmethod
    def subscribe(self, symbol: str) -> bool:
        """Subscribe to symbol for real-time updates"""
        pass
    
    @abstractmethod
    def unsubscribe(self, symbol: str) -> bool:
        """Unsubscribe from symbol"""
        pass
    
    def add_order_callback(self, callback: Callable) -> None:
        """Add order update callback"""
        self._order_callbacks.append(callback)
    
    def add_quote_callback(self, callback: Callable) -> None:
        """Add quote update callback"""
        self._quote_callbacks.append(callback)
    
    def _notify_order_update(self, order_data: Dict[str, Any]) -> None:
        """Notify all order callbacks"""
        for callback in self._order_callbacks:
            try:
                callback(order_data)
            except Exception as e:
                print(f"Error in order callback: {e}")
    
    def _notify_quote_update(self, quote_data: Dict[str, Any]) -> None:
        """Notify all quote callbacks"""
        for callback in self._quote_callbacks:
            try:
                callback(quote_data)
            except Exception as e:
                print(f"Error in quote callback: {e}")
    
    def is_healthy(self) -> bool:
        """Check if broker connection is healthy"""
        return self.is_connected
