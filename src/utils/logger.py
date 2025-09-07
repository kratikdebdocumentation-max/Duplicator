"""
Logging utilities for Duplicator Trading Bot
Provides structured logging with file rotation and console output
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
from .config_manager import config


class DuplicatorLogger:
    """Custom logger for Duplicator application"""
    
    def __init__(self, name: str, level: Optional[str] = None):
        self.name = name
        self.level = level or config.get('logging.level', 'INFO')
        self.log_dir = Path(config.get('logging.log_dir', 'logs'))
        self.max_file_size = config.get('logging.max_file_size', '10MB')
        self.backup_count = config.get('logging.backup_count', 5)
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger with file and console handlers"""
        logger = logging.getLogger(self.name)
        logger.setLevel(getattr(logging, self.level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # File handler with rotation
        log_file = self.log_dir / f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self._parse_file_size(self.max_file_size),
            backupCount=self.backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _parse_file_size(self, size_str: str) -> int:
        """Parse file size string to bytes"""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def info(self, message: str) -> None:
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """Log error message"""
        self.logger.error(message)
    
    def debug(self, message: str) -> None:
        """Log debug message"""
        self.logger.debug(message)
    
    def critical(self, message: str) -> None:
        """Log critical message"""
        self.logger.critical(message)


# Create specific loggers for different components
def get_logger(name: str) -> DuplicatorLogger:
    """Get logger instance for specific component"""
    return DuplicatorLogger(name)


# Pre-configured loggers for different components
telegram_logger = get_logger('telegram_bot')
broker_logger = get_logger('broker_api')
order_logger = get_logger('order_manager')
websocket_logger = get_logger('websocket')
main_logger = get_logger('duplicator_main')
