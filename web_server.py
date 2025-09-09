"""
FastAPI Web Server for Duplicator Trading Bot
High-performance local web interface for trading operations
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

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
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = get_logger('websocket_manager')
    
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
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                self.logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)


class TradingWebApp:
    """Main trading web application"""
    
    def __init__(self):
        self.logger = get_logger('trading_web_app')
        self.app = FastAPI(
            title="Duplicator Trading Bot",
            description="High-performance trading interface",
            version="1.0.0"
        )
        
        # Initialize components
        self.broker_manager: Optional[BrokerManager] = None
        self.order_manager: Optional[OrderManager] = None
        self.trading_websocket_manager: Optional[TradingWebSocketManager] = None
        self.ws_manager = WebSocketManager()
        
        # Setup CORS
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
        """Setup API routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def read_root():
            return FileResponse("web/index.html")
        
        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint"""
            try:
                broker_status = self.broker_manager.get_health_status() if self.broker_manager else {}
                return {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "brokers": broker_status,
                    "active_orders": len(self.order_manager.get_active_orders()) if self.order_manager else 0
                }
            except Exception as e:
                return {"status": "unhealthy", "error": str(e)}
        
        @self.app.get("/api/orders")
        async def get_orders():
            """Get all orders"""
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                orders = self.order_manager.get_all_orders()
                return {"orders": orders, "count": len(orders)}
            except Exception as e:
                self.logger.error(f"Error getting orders: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/orders/active")
        async def get_active_orders():
            """Get active orders only"""
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                orders = self.order_manager.get_active_orders()
                return {"orders": orders, "count": len(orders)}
            except Exception as e:
                self.logger.error(f"Error getting active orders: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/orders")
        async def place_order(order_request: OrderRequest, background_tasks: BackgroundTasks):
            """Place a new order"""
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
                    # Broadcast order update to all connected clients
                    await self.ws_manager.broadcast(json.dumps({
                        "type": "order_placed",
                        "data": {
                            "order_id": order.order_id,
                            "symbol": order.symbol,
                            "order_type": order.order_type.value,
                            "quantity": order.quantity,
                            "price": order.price,
                            "status": order.status.value,
                            "timestamp": order.created_at.isoformat()
                        }
                    }))
                    
                    return {"success": True, "message": message, "order": {
                        "order_id": order.order_id,
                        "symbol": order.symbol,
                        "order_type": order.order_type.value,
                        "quantity": order.quantity,
                        "price": order.price,
                        "status": order.status.value,
                        "created_at": order.created_at.isoformat()
                    }}
                else:
                    return {"success": False, "message": message}
                    
            except Exception as e:
                self.logger.error(f"Error placing order: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/orders/{order_id}")
        async def modify_order(order_id: str, modify_request: OrderModifyRequest, background_tasks: BackgroundTasks):
            """Modify an existing order"""
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                success, message = self.order_manager.modify_order(
                    order_id=order_id,
                    new_quantity=modify_request.new_quantity,
                    new_price=modify_request.new_price
                )
                
                if success:
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
            """Cancel an order"""
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                success, message = self.order_manager.cancel_order(order_id)
                
                if success:
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
            """Get positions from all brokers"""
            try:
                if not self.order_manager:
                    raise HTTPException(status_code=500, detail="Order manager not initialized")
                
                positions = self.order_manager.get_positions_summary()
                return positions
                
            except Exception as e:
                self.logger.error(f"Error getting positions: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/brokers")
        async def get_brokers():
            """Get broker status"""
            try:
                if not self.broker_manager:
                    return {"brokers": {}}
                
                broker_status = self.broker_manager.get_health_status()
                return {"brokers": broker_status}
                
            except Exception as e:
                self.logger.error(f"Error getting broker status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
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
            self.logger.info("Initializing trading components...")
            
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
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
    
    def _on_order_update(self, order_update) -> None:
        """Handle order update from trading websocket"""
        try:
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
                    "timestamp": getattr(order_update, 'timestamp', datetime.now()).isoformat()
                }
            })))
            
            self.logger.info(f"Order update broadcasted: {order_update.order_id} - {order_update.status}")
            
        except Exception as e:
            self.logger.error(f"Error handling order update: {e}")
    
    def _on_price_update(self, price_update) -> None:
        """Handle price update from trading websocket"""
        try:
            # Broadcast price update to web clients
            asyncio.create_task(self.ws_manager.broadcast(json.dumps({
                "type": "price_update",
                "data": {
                    "symbol": getattr(price_update, 'symbol', 'unknown'),
                    "token": getattr(price_update, 'token', 'unknown'),
                    "last_price": getattr(price_update, 'last_price', 0.0),
                    "broker": getattr(price_update, 'broker', 'unknown'),
                    "timestamp": datetime.now().isoformat()
                }
            })))
            
        except Exception as e:
            self.logger.error(f"Error handling price update: {e}")
    
    def run(self, host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
        """Run the web server"""
        self.logger.info(f"Starting web server on {host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            access_log=True
        )


def main():
    """Main entry point"""
    app = TradingWebApp()
    app.run()


if __name__ == "__main__":
    main()
