"""
Order Manager for Duplicator Trading Bot
Handles order placement, modification, cancellation, and tracking across multiple brokers
"""

import pandas as pd
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from ..brokers.base_broker import OrderRequest, OrderResponse, OrderType, ProductType, PriceType
from ..brokers.broker_manager import BrokerManager
from ..utils.config_manager import config
from ..utils.logger import get_logger


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class DuplicatedOrder:
    """Represents an order duplicated across multiple brokers"""
    order_id: str
    symbol: str
    order_type: OrderType
    quantity: int
    price: float
    broker_orders: Dict[str, str]  # broker_name -> broker_order_id
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    remarks: Optional[str] = None


class OrderManager:
    """Manages orders across multiple brokers"""
    
    def __init__(self, broker_manager: BrokerManager):
        self.broker_manager = broker_manager
        self.logger = get_logger('order_manager')
        self.orders: Dict[str, DuplicatedOrder] = {}
        self.orders_file = Path("data/orders.json")
        self._load_orders()
    
    def _load_orders(self) -> None:
        """Load orders from file"""
        try:
            if self.orders_file.exists():
                with open(self.orders_file, 'r') as f:
                    data = json.load(f)
                    for order_id, order_data in data.items():
                        # Convert string dates back to datetime objects
                        order_data['created_at'] = datetime.fromisoformat(order_data['created_at'])
                        order_data['updated_at'] = datetime.fromisoformat(order_data['updated_at'])
                        order_data['order_type'] = OrderType(order_data['order_type'])
                        order_data['status'] = OrderStatus(order_data['status'])
                        self.orders[order_id] = DuplicatedOrder(**order_data)
                self.logger.info(f"Loaded {len(self.orders)} orders from file")
        except Exception as e:
            self.logger.error(f"Error loading orders: {e}")
    
    def _save_orders(self) -> None:
        """Save orders to file"""
        try:
            self.orders_file.parent.mkdir(exist_ok=True)
            data = {}
            for order_id, order in self.orders.items():
                order_dict = asdict(order)
                # Convert datetime objects to strings
                order_dict['created_at'] = order.created_at.isoformat()
                order_dict['updated_at'] = order.updated_at.isoformat()
                order_dict['order_type'] = order.order_type.value
                order_dict['status'] = order.status.value
                data[order_id] = order_dict
            
            with open(self.orders_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving orders: {e}")
    
    def place_order(self, 
                   symbol: str,
                   order_type: OrderType,
                   quantity: int,
                   price: float,
                   exchange: str = "NFO",
                   product_type: ProductType = ProductType.INTRADAY,
                   price_type: PriceType = PriceType.LIMIT,
                   remarks: Optional[str] = None) -> Tuple[bool, str, Optional[DuplicatedOrder]]:
        """Place order across all connected brokers - ULTRA-FAST PARALLEL EXECUTION"""
        start_time = time.time()
        
        try:
            # Create order request (optimized for speed)
            order_request = OrderRequest(
                buy_or_sell=order_type,
                product_type=product_type,
                exchange=exchange,
                tradingsymbol=symbol,
                quantity=quantity,
                price_type=price_type,
                price=price,
                remarks=remarks
            )
            
            # Place order on all brokers in parallel
            broker_responses = self.broker_manager.place_order_all(order_request)
            
            # Check if any orders were successful
            successful_orders = {broker: resp for broker, resp in broker_responses.items() 
                               if resp.success}
            
            if not successful_orders:
                self.logger.error("❌ No orders were placed successfully")
                return False, "No orders placed successfully", None
            
            # Create duplicated order record (optimized)
            order_id = f"ORD_{int(time.time() * 1000)}"  # Use milliseconds for uniqueness
            duplicated_order = DuplicatedOrder(
                order_id=order_id,
                symbol=symbol,
                order_type=order_type,
                quantity=quantity,
                price=price,
                broker_orders={broker: resp.order_id for broker, resp in successful_orders.items()},
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                remarks=remarks
            )
            
            # Store order in memory immediately (file save in background)
            self.orders[order_id] = duplicated_order
            
            # Save to file asynchronously to avoid blocking
            import threading
            threading.Thread(target=self._save_orders, daemon=True).start()
            
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            self.logger.info(f"🚀 Order {order_id} placed on {len(successful_orders)} brokers in {execution_time:.2f}ms")
            
            return True, f"Order placed on {len(successful_orders)} brokers in {execution_time:.1f}ms", duplicated_order
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return False, str(e), None
    
    def modify_order(self, order_id: str, new_quantity: Optional[int] = None, 
                    new_price: Optional[float] = None) -> Tuple[bool, str]:
        """Modify order across all brokers"""
        try:
            if order_id not in self.orders:
                return False, "Order not found"
            
            order = self.orders[order_id]
            
            # Create modified order request
            order_request = OrderRequest(
                buy_or_sell=order.order_type,
                product_type=ProductType.INTRADAY,
                exchange="NFO",
                tradingsymbol=order.symbol,
                quantity=new_quantity or order.quantity,
                price_type=PriceType.LIMIT,
                price=new_price or order.price,
                remarks=order.remarks
            )
            
            # Modify order on all brokers
            broker_responses = self.broker_manager.modify_order_all(order_id, order_request)
            
            successful_modifications = sum(1 for resp in broker_responses.values() if resp.success)
            
            if successful_modifications > 0:
                # Update order record
                if new_quantity:
                    order.quantity = new_quantity
                if new_price:
                    order.price = new_price
                order.updated_at = datetime.now()
                self._save_orders()
                
                self.logger.info(f"Order {order_id} modified successfully on {successful_modifications} brokers")
                return True, f"Order modified on {successful_modifications} brokers"
            else:
                return False, "No modifications were successful"
                
        except Exception as e:
            self.logger.error(f"Error modifying order: {e}")
            return False, str(e)
    
    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """Cancel order across all brokers"""
        try:
            if order_id not in self.orders:
                return False, "Order not found"
            
            order = self.orders[order_id]
            
            # Cancel order on all brokers
            broker_responses = {}
            for broker_name, broker_order_id in order.broker_orders.items():
                broker = self.broker_manager.get_broker(broker_name)
                if broker:
                    response = broker.cancel_order(broker_order_id)
                    broker_responses[broker_name] = response
            
            successful_cancellations = sum(1 for resp in broker_responses.values() if resp.success)
            
            if successful_cancellations > 0:
                # Update order status
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now()
                self._save_orders()
                
                self.logger.info(f"Order {order_id} cancelled successfully on {successful_cancellations} brokers")
                return True, f"Order cancelled on {successful_cancellations} brokers"
            else:
                return False, "No cancellations were successful"
                
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return False, str(e)
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status from all brokers"""
        try:
            if order_id not in self.orders:
                return None
            
            order = self.orders[order_id]
            status_info = {
                'order_id': order_id,
                'symbol': order.symbol,
                'order_type': order.order_type.value,
                'quantity': order.quantity,
                'price': order.price,
                'status': order.status.value,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat(),
                'broker_statuses': {}
            }
            
            # Get status from each broker
            for broker_name, broker_order_id in order.broker_orders.items():
                broker = self.broker_manager.get_broker(broker_name)
                if broker:
                    broker_status = broker.get_order_status(broker_order_id)
                    status_info['broker_statuses'][broker_name] = broker_status
            
            return status_info
            
        except Exception as e:
            self.logger.error(f"Error getting order status: {e}")
            return None
    
    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Get all orders"""
        return [self.get_order_status(order_id) for order_id in self.orders.keys()]
    
    def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get all active orders (not completed or cancelled)"""
        active_statuses = [OrderStatus.PENDING, OrderStatus.OPEN]
        active_orders = [order for order in self.orders.values() 
                        if order.status in active_statuses]
        return [self.get_order_status(order.order_id) for order in active_orders]
    
    def update_order_status(self, order_id: str, status: OrderStatus) -> None:
        """Update order status"""
        if order_id in self.orders:
            self.orders[order_id].status = status
            self.orders[order_id].updated_at = datetime.now()
            self._save_orders()
    
    def handle_order_update(self, broker_name: str, order_data: Dict[str, Any]) -> None:
        """Handle order update from websocket"""
        try:
            broker_order_id = order_data.get('norenordno')
            if not broker_order_id:
                return
            
            # Find the duplicated order that contains this broker order
            for order_id, order in self.orders.items():
                if broker_order_id in order.broker_orders.values():
                    # Update order status based on broker response
                    status = order_data.get('status', '').upper()
                    if status == 'COMPLETE':
                        self.update_order_status(order_id, OrderStatus.COMPLETE)
                    elif status == 'CANCELLED':
                        self.update_order_status(order_id, OrderStatus.CANCELLED)
                    elif status == 'REJECTED':
                        self.update_order_status(order_id, OrderStatus.REJECTED)
                    elif status == 'OPEN':
                        self.update_order_status(order_id, OrderStatus.OPEN)
                    
                    self.logger.info(f"Updated order {order_id} status to {status} from {broker_name}")
                    break
                    
        except Exception as e:
            self.logger.error(f"Error handling order update: {e}")
    
    def get_positions_summary(self) -> Dict[str, Any]:
        """Get positions summary from all brokers"""
        try:
            all_positions = self.broker_manager.get_all_positions()
            summary = {
                'total_brokers': len(all_positions),
                'broker_positions': {},
                'total_pnl': 0,
                'total_mtm': 0
            }
            
            for broker_name, positions in all_positions.items():
                broker_pnl = sum(pos.pnl for pos in positions)
                broker_mtm = sum(pos.mtm for pos in positions)
                
                summary['broker_positions'][broker_name] = {
                    'positions_count': len(positions),
                    'pnl': broker_pnl,
                    'mtm': broker_mtm
                }
                
                summary['total_pnl'] += broker_pnl
                summary['total_mtm'] += broker_mtm
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting positions summary: {e}")
            return {}
    
    def cleanup_old_orders(self, days: int = 7) -> None:
        """Clean up orders older than specified days"""
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            orders_to_remove = []
            
            for order_id, order in self.orders.items():
                if order.created_at.timestamp() < cutoff_date:
                    orders_to_remove.append(order_id)
            
            for order_id in orders_to_remove:
                del self.orders[order_id]
            
            if orders_to_remove:
                self._save_orders()
                self.logger.info(f"Cleaned up {len(orders_to_remove)} old orders")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old orders: {e}")
