"""
Configuration Manager for Duplicator Trading Bot
Handles loading and managing configuration from YAML files
"""

import yaml
import os
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self._config: Optional[Dict[str, Any]] = None
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self._config = yaml.safe_load(file)
                
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        if self._config is None:
            return default
        
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_telegram_config(self) -> Dict[str, str]:
        """Get Telegram configuration"""
        return self.get('telegram', {})
    
    def get_trading_config(self) -> Dict[str, Any]:
        """Get trading configuration"""
        return self.get('trading', {})
    
    def get_broker_config(self, broker_name: str) -> Dict[str, Any]:
        """Get configuration for specific broker"""
        brokers = self.get('brokers', {})
        return brokers.get(broker_name, {})
    
    def get_enabled_brokers(self) -> Dict[str, Dict[str, Any]]:
        """Get all enabled brokers"""
        brokers = self.get('brokers', {})
        return {name: config for name, config in brokers.items() 
                if config.get('enabled', False)}
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.get('logging', {})
    
    def get_websocket_config(self) -> Dict[str, Any]:
        """Get websocket configuration"""
        return self.get('websocket', {})
    
    def get_orders_config(self) -> Dict[str, Any]:
        """Get order management configuration"""
        return self.get('orders', {})
    
    def reload_config(self) -> None:
        """Reload configuration from file"""
        self.load_config()
    
    def is_broker_enabled(self, broker_name: str) -> bool:
        """Check if broker is enabled"""
        broker_config = self.get_broker_config(broker_name)
        return broker_config.get('enabled', False)
    
    def get_lot_multiplier(self, index: str) -> int:
        """Get lot multiplier for specific index"""
        multipliers = self.get('trading.lot_multipliers', {})
        return multipliers.get(index, 1)
    
    def get_default_order_type(self) -> str:
        """Get default order type (MIS or CNC)"""
        return self.get('trading.default_order_type', 'MIS')


# Global configuration instance
config = ConfigManager()
