"""
WebSocket management for Duplicator Trading Bot
"""

from .websocket_manager import WebSocketManager, PriceUpdate, OrderUpdate

__all__ = [
    'WebSocketManager',
    'PriceUpdate',
    'OrderUpdate'
]
