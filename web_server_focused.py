"""
Focused Web Server for Duplicator Trading Bot
Web-only interface with enhanced features and performance
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys
from functools import lru_cache
import weakref

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
import uvicorn
from cachetools import TTLCache

from src.brokers.broker_manager import BrokerManager
from src.orders.order_manager import OrderManager, OrderStatus
from src.websocket.websocket_manager import WebSocketManager as TradingWebSocketManager
from src.utils.config_manager import config
from src.utils.logger import get_logger
from src.brokers.base_broker import OrderType, ProductType, PriceType


# Pydantic models for API
class OrderRequest(BaseModel):
    symbol: str
    order_type: str  # "BUY" or "SELL"
    quantity: int
    price: float
    exchange: str = "NFO"
    product_type: str = "INTRADAY"
    price_type: str = "LIMIT"
    remarks: Optional[str] = None


class OrderModifyRequest(BaseModel):
    order_id: str
    new_quantity: Optional[int] = None
    new_price: Optional[float] = None


class OrderCancelRequest(BaseModel):
    order_id: str


class WebSocketManager:
    """Enhanced WebSocket manager for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = get_logger('websocket_manager')
        self.message_queue = asyncio.Queue()
        self.batch_size = 5
        self.batch_timeout = 0.05  # 50ms
        self._batch_task = None
        self._start_batch_processor()
    
    async def _start_batch_processor(self):
        """Start background task to process batched messages"""
        self._batch_task = asyncio.create_task(self._process_message_batch())
    
    async def _process_message_batch(self):
        """Process batched messages for better performance"""
        batch = []
        last_send = time.time()
        
        while True:
            try:
                # Wait for messages with timeout
                try:
                    message = await asyncio.wait_for(self.message_queue.get(), timeout=self.batch_timeout)
                    batch.append(message)
                except asyncio.TimeoutError:
                    pass
                
                # Send batch if we have messages and either batch is full or timeout reached
                current_time = time.time()
                if batch and (len(batch) >= self.batch_size or 
                             current_time - last_send >= self.batch_timeout):
                    await self._send_batch(batch)
                    batch = []
                    last_send = current_time
                    
            except Exception as e:
                self.logger.error(f"Error in batch processor: {e}")
                await asyncio.sleep(0.1)
    
    async def _send_batch(self, messages: List[str]):
        """Send a batch of messages to all connections"""
        if not self.active_connections or not messages:
            return
        
        # Combine messages into a single batch
        batch_data = {
            "type": "batch",
            "messages": messages,
            "timestamp": datetime.now().isoformat()
        }
        batch_json = json.dumps(batch_data)
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(batch_json)
            except Exception as e:
                self.logger.error(f"Error sending batch to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            self.logger.error(f"Error sending personal message: {e}")
    
    async def broadcast(self, message: str):
        """Queue message for batch broadcasting"""
        await self.message_queue.put(message)


class FocusedTradingWebApp:
    """Focused trading web application with enhanced features"""
    
    def __init__(self):
        self.logger = get_logger('focused_trading_web_app')
        self.app = FastAPI(
            title="Duplicator Trading Bot - Web Interface",
            description="High-performance web trading interface",
            version="2.0.0"
        )
        
        # Initialize components
        self.broker_manager: Optional[BrokerManager] = None
        self.order_manager: Optional[OrderManager] = None
        self.trading_websocket_manager: Optional[TradingWebSocketManager] = None
        self.ws_manager = WebSocketManager()
        
        # Performance optimizations
        self.cache = TTLCache(maxsize=2000, ttl=15)  # 15 second cache
        self.last_health_check = 0
        self.health_cache_ttl = 3  # 3 seconds
        
        # Enhanced features
        self.market_data_cache = {}
        self.order_history = []
        self.performance_metrics = {
            "orders_placed": 0,
            "orders_completed": 0,
            "total_volume": 0,
            "start_time": datetime.now()
        }
        
        # Setup middleware
        self.app.add_middleware(GZipMiddleware, minimum_size=500)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        # Initialize trading components
        self._initialize_components()
    
    def _setup_routes(self):
        """Setup enhanced API routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def read_root():
            return FileResponse("web/index.html")
        
        @self.app.get("/api/health")
        async def health_check():
            """Enhanced health check with performance metrics"""
            current_time = time.time()
            if current_time - self.last_health_check < self.health_cache_ttl:
                return self.cache.get('health', {"status": "unknown"})
            
            try:
                broker_status = self.broker_manager.get_health_status() if self.broker_manager else {}
                health_data = {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "brokers": broker_status,
                    "active_orders": len(self.order_manager.get_active_orders()) if self.order_manager else 0,
                    "websocket_connections": len(self.ws_manager.active_connections),
                    "performance": self.performance_metrics,
                    "uptime": str(datetime.now() - self.performance_metrics["start_time"]).split('.')[0]
                }
                
                self.cache['health'] = health_data
                self.last_health_check = current_time
                return health_data
            except Exception as e:
                error_data = {"status": "unhealthy", "error": str(e)}
                self.cache['health'] = error_data
                return error_data
        
        @self.app.get("/api/orders")
        async def get_orders():
            """Get all orders with enhanced data"""
            cache_key = 'all_orders'
            cached_orders = self.cache.get(cache_key)
            if cached_orders:
                return cached_orders
            
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                orders = self.order_manager.get_all_orders()
                result = {
                    "orders": orders, 
                    "count": len(orders),
                    "performance": self.performance_metrics
                }
                self.cache[cache_key] = result
                return result
            except Exception as e:
                self.logger.error(f"Error getting orders: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/orders/active")
        async def get_active_orders():
            """Get active orders with real-time data"""
            cache_key = 'active_orders'
            cached_orders = self.cache.get(cache_key)
            if cached_orders:
                return cached_orders
            
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                orders = self.order_manager.get_active_orders()
                result = {
                    "orders": orders, 
                    "count": len(orders),
                    "timestamp": datetime.now().isoformat()
                }
                self.cache[cache_key] = result
                return result
            except Exception as e:
                self.logger.error(f"Error getting active orders: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/orders")
        async def place_order(order_request: OrderRequest, background_tasks: BackgroundTasks):
            """Place order with enhanced tracking"""
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                # Convert string order type to enum
                order_type = OrderType.BUY if order_request.order_type.upper() == "BUY" else OrderType.SELL
                product_type = ProductType.INTRADAY if order_request.product_type.upper() == "INTRADAY" else ProductType.DELIVERY
                price_type = PriceType.LIMIT if order_request.price_type.upper() == "LIMIT" else PriceType.MARKET
                
                success, message, order = self.order_manager.place_order(
                    symbol=order_request.symbol,
                    order_type=order_type,
                    quantity=order_request.quantity,
                    price=order_request.price,
                    exchange=order_request.exchange,
                    product_type=product_type,
                    price_type=price_type,
                    remarks=order_request.remarks
                )
                
                if success and order:
                    # Update performance metrics
                    self.performance_metrics["orders_placed"] += 1
                    self.performance_metrics["total_volume"] += order_request.quantity
                    
                    # Invalidate cache
                    self.cache.pop('all_orders', None)
                    self.cache.pop('active_orders', None)
                    
                    # Broadcast order update
                    await self.ws_manager.broadcast(json.dumps({
                        "type": "order_placed",
                        "data": {
                            "order_id": order.order_id,
                            "symbol": order.symbol,
                            "order_type": order.order_type.value,
                            "quantity": order.quantity,
                            "price": order.price,
                            "status": order.status.value,
                            "timestamp": order.created_at.isoformat(),
                            "performance": self.performance_metrics
                        }
                    }))
                    
                    return {
                        "success": True, 
                        "message": message, 
                        "order": {
                            "order_id": order.order_id,
                            "symbol": order.symbol,
                            "order_type": order.order_type.value,
                            "quantity": order.quantity,
                            "price": order.price,
                            "status": order.status.value,
                            "created_at": order.created_at.isoformat()
                        },
                        "performance": self.performance_metrics
                    }
                else:
                    return {"success": False, "message": message}
                    
            except Exception as e:
                self.logger.error(f"Error placing order: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/orders/{order_id}")
        async def modify_order(order_id: str, modify_request: OrderModifyRequest, background_tasks: BackgroundTasks):
            """Modify order with enhanced tracking"""
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                success, message = self.order_manager.modify_order(
                    order_id=order_id,
                    new_quantity=modify_request.new_quantity,
                    new_price=modify_request.new_price
                )
                
                if success:
                    # Invalidate cache
                    self.cache.pop('all_orders', None)
                    self.cache.pop('active_orders', None)
                    
                    # Broadcast order update
                    await self.ws_manager.broadcast(json.dumps({
                        "type": "order_modified",
                        "data": {
                            "order_id": order_id,
                            "new_quantity": modify_request.new_quantity,
                            "new_price": modify_request.new_price,
                            "timestamp": datetime.now().isoformat()
                        }
                    }))
                
                return {"success": success, "message": message}
                
            except Exception as e:
                self.logger.error(f"Error modifying order: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/orders/{order_id}")
        async def cancel_order(order_id: str, background_tasks: BackgroundTasks):
            """Cancel order with enhanced tracking"""
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                success, message = self.order_manager.cancel_order(order_id)
                
                if success:
                    # Invalidate cache
                    self.cache.pop('all_orders', None)
                    self.cache.pop('active_orders', None)
                    
                    # Broadcast order update
                    await self.ws_manager.broadcast(json.dumps({
                        "type": "order_cancelled",
                        "data": {
                            "order_id": order_id,
                            "timestamp": datetime.now().isoformat()
                        }
                    }))
                
                return {"success": success, "message": message}
                
            except Exception as e:
                self.logger.error(f"Error cancelling order: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/positions")
        async def get_positions():
            """Get positions with enhanced analytics"""
            cache_key = 'positions'
            cached_positions = self.cache.get(cache_key)
            if cached_positions:
                return cached_positions
            
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                positions = self.order_manager.get_positions_summary()
                positions['performance'] = self.performance_metrics
                self.cache[cache_key] = positions
                return positions
                
            except Exception as e:
                self.logger.error(f"Error getting positions: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/brokers")
        async def get_brokers():
            """Get broker status with enhanced monitoring"""
            cache_key = 'brokers'
            cached_brokers = self.cache.get(cache_key)
            if cached_brokers:
                return cached_brokers
            
            try:
                if not self.broker_manager:
                    return {"brokers": {}}
                
                broker_status = self.broker_manager.get_health_status()
                result = {
                    "brokers": broker_status,
                    "total_brokers": len(broker_status),
                    "connected_brokers": sum(1 for status in broker_status.values() if status),
                    "timestamp": datetime.now().isoformat()
                }
                self.cache[cache_key] = result
                return result
                
            except Exception as e:
                self.logger.error(f"Error getting broker status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/performance")
        async def get_performance():
            """Get performance metrics"""
            return {
                "metrics": self.performance_metrics,
                "uptime": str(datetime.now() - self.performance_metrics["start_time"]).split('.')[0],
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Enhanced WebSocket endpoint for real-time updates"""
            await self.ws_manager.connect(websocket)
            try:
                while True:
                    # Keep connection alive and handle incoming messages
                    data = await websocket.receive_text()
                    # Echo back for ping/pong
                    await websocket.send_text(f"Echo: {data}")
            except WebSocketDisconnect:
                self.ws_manager.disconnect(websocket)
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                self.ws_manager.disconnect(websocket)
    
    def _initialize_components(self):
        """Initialize trading components"""
        try:
            self.logger.info("Initializing Focused Trading Web App...")
            
            # Initialize broker manager
            self.broker_manager = BrokerManager()
            self.logger.info("Broker manager initialized")
            
            # Initialize order manager
            self.order_manager = OrderManager(self.broker_manager)
            self.logger.info("Order manager initialized")
            
            # Connect to brokers
            connection_results = self.broker_manager.connect_all()
            connected_brokers = [name for name, success in connection_results.items() if success]
            self.logger.info(f"Connected to brokers: {connected_brokers}")
            
            # Initialize trading websocket manager for real-time data
            if self.broker_manager:
                self.trading_websocket_manager = TradingWebSocketManager(self.broker_manager, self.order_manager)
                
                # Add callbacks for real-time updates
                self.trading_websocket_manager.add_order_callback(self._on_order_update)
                self.trading_websocket_manager.add_price_callback(self._on_price_update)
                
                self.trading_websocket_manager.start()
                self.logger.info("Trading WebSocket manager started")
            
            self.logger.info("Focused Trading Web App initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
    
    def _on_order_update(self, order_update) -> None:
        """Handle order update from trading websocket"""
        try:
            # Update performance metrics
            if order_update.status in ['COMPLETE', 'CANCELLED', 'REJECTED']:
                self.performance_metrics["orders_completed"] += 1
            
            # Invalidate relevant caches
            self.cache.pop('all_orders', None)
            self.cache.pop('active_orders', None)
            
            # Broadcast order update to web clients
            asyncio.create_task(self.ws_manager.broadcast(json.dumps({
                "type": "order_update",
                "data": {
                    "order_id": getattr(order_update, 'order_id', 'unknown'),
                    "symbol": getattr(order_update, 'symbol', 'unknown'),
                    "status": getattr(order_update, 'status', 'unknown'),
                    "broker": getattr(order_update, 'broker', 'unknown'),
                    "quantity": getattr(order_update, 'quantity', 0),
                    "price": getattr(order_update, 'price', 0.0),
                    "timestamp": getattr(order_update, 'timestamp', datetime.now()).isoformat(),
                    "performance": self.performance_metrics
                }
            })))
            
            self.logger.info(f"Order update broadcasted: {order_update.order_id} - {order_update.status}")
            
        except Exception as e:
            self.logger.error(f"Error handling order update: {e}")
    
    def _on_price_update(self, price_update) -> None:
        """Handle price update from trading websocket"""
        try:
            # Update market data cache
            symbol = getattr(price_update, 'symbol', 'unknown')
            self.market_data_cache[symbol] = {
                "last_price": getattr(price_update, 'last_price', 0.0),
                "timestamp": datetime.now().isoformat(),
                "broker": getattr(price_update, 'broker', 'unknown')
            }
            
            # Broadcast price update to web clients
            asyncio.create_task(self.ws_manager.broadcast(json.dumps({
                "type": "price_update",
                "data": {
                    "symbol": symbol,
                    "token": getattr(price_update, 'token', 'unknown'),
                    "last_price": getattr(price_update, 'last_price', 0.0),
                    "broker": getattr(price_update, 'broker', 'unknown'),
                    "timestamp": datetime.now().isoformat()
                }
            })))
            
        except Exception as e:
            self.logger.error(f"Error handling price update: {e}")
    
    def run(self, host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
        """Run the focused web server"""
        self.logger.info(f"Starting Focused Trading Web App on {host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            access_log=True,
            # Performance optimizations
            workers=1,
            loop="asyncio",
            http="httptools"
        )


def main():
    """Main entry point"""
    print("🚀 Starting Focused Duplicator Trading Bot (Web Only)")
    print("🌐 Web Interface: http://localhost:8000")
    print("📊 Enhanced Features: Performance metrics, real-time updates, advanced analytics")
    print("Press Ctrl+C to stop")
    print()
    
    app = FocusedTradingWebApp()
    app.run()


if __name__ == "__main__":
    main()
