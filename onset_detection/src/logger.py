"""Logging configuration for onset detection system."""

import logging
import sys
from pathlib import Path
from typing import Optional

from .config_loader import Config, load_config
from .utils.paths import PathManager


class Logger:
    """
    Centralized logging configuration for the onset detection system.
    
    Provides both console and file logging with configurable levels and formats.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize logger configuration.
        
        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()
        self.path_manager = PathManager(self.config)
        
        # Ensure logs directory exists
        self.logs_dir = self.path_manager.get_logs_path()
        
        # Logger instances cache
        self._loggers = {}
        
        # Configure root logger if not already configured
        if not logging.getLogger().handlers:
            self._configure_root_logger()
    
    def _configure_root_logger(self) -> None:
        """Configure the root logger with console and file handlers."""
        root_logger = logging.getLogger()
        
        # Set root level based on config
        log_level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        root_logger.setLevel(log_level)
        
        # Create formatter
        formatter = logging.Formatter(self.config.logging.format)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler
        log_file = self.logs_dir / "app.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        
        # Add rotation if enabled
        if self.config.logging.file_rotation:
            # Use RotatingFileHandler for large files
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
        
        root_logger.addHandler(file_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get or create a logger with the specified name.
        
        Args:
            name: Logger name (typically module name).
            
        Returns:
            logging.Logger: Configured logger instance.
        """
        if name in self._loggers:
            return self._loggers[name]
        
        logger = logging.getLogger(name)
        
        # Prevent duplicate handlers if logger already exists
        if not logger.handlers:
            # Child loggers inherit from root logger configuration
            pass
        
        self._loggers[name] = logger
        return logger
    
    def set_level(self, level: str) -> None:
        """
        Change the logging level for all loggers.
        
        Args:
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
        """
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        # Update root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Update all handlers
        for handler in root_logger.handlers:
            handler.setLevel(log_level)
        
        # Update config
        self.config.logging.level = level.upper()
    
    def add_file_handler(self, filename: str, level: Optional[str] = None) -> None:
        """
        Add an additional file handler.
        
        Args:
            filename: Log filename.
            level: Log level for this handler. If None, uses default.
        """
        log_file = self.logs_dir / filename
        
        if level is None:
            log_level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        else:
            log_level = getattr(logging, level.upper(), logging.INFO)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        
        # Create formatter
        formatter = logging.Formatter(self.config.logging.format)
        file_handler.setFormatter(formatter)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    
    def get_log_files(self) -> list:
        """
        Get list of log files in the logs directory.
        
        Returns:
            list: List of log file paths.
        """
        if not self.logs_dir.exists():
            return []
        
        log_files = []
        for log_file in self.logs_dir.glob("*.log"):
            log_files.append(log_file)
        
        return sorted(log_files)
    
    def clear_logs(self) -> bool:
        """
        Clear all log files.
        
        Returns:
            bool: True if successful.
        """
        try:
            for log_file in self.get_log_files():
                log_file.unlink()
            return True
        except Exception as e:
            print(f"Error clearing logs: {e}")
            return False


# Global logger instance
_logger_instance = None


def setup_logging(config: Optional[Config] = None) -> Logger:
    """
    Setup global logging configuration.
    
    Args:
        config: Configuration object.
        
    Returns:
        Logger: Configured logger instance.
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger(config)
    return _logger_instance


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__).
        
    Returns:
        logging.Logger: Configured logger instance.
    """
    if _logger_instance is None:
        setup_logging()
    return _logger_instance.get_logger(name)


# Convenience functions for common logging operations
def log_replay_tick(logger: logging.Logger, tick_data: dict, row_num: int = None) -> None:
    """
    Log replay tick information.
    
    Args:
        logger: Logger instance.
        tick_data: Tick data dictionary.
        row_num: Optional row number.
    """
    if row_num is not None:
        logger.info(f"replay row={row_num} stock={tick_data.get('stock_code')} "
                   f"price={tick_data.get('price')} volume={tick_data.get('volume')}")
    else:
        logger.info(f"replay stock={tick_data.get('stock_code')} "
                   f"price={tick_data.get('price')} volume={tick_data.get('volume')}")


def log_event(logger: logging.Logger, event_type: str, details: dict) -> None:
    """
    Log event information.
    
    Args:
        logger: Logger instance.
        event_type: Type of event.
        details: Event details.
    """
    logger.info(f"event type={event_type} details={details}")


def log_onset_detection(
    logger: logging.Logger, 
    stock_code: str, 
    detection_type: str, 
    score: float, 
    timestamp: float
) -> None:
    """
    Log onset detection information.
    
    Args:
        logger: Logger instance.
        stock_code: Stock code.
        detection_type: Type of detection ('candidate', 'confirmed', etc.).
        score: Detection score.
        timestamp: Event timestamp.
    """
    logger.info(f"onset stock={stock_code} type={detection_type} "
               f"score={score:.3f} ts={timestamp}")


if __name__ == "__main__":
    # Demo/test the logging system
    print("Logger Demo")
    print("=" * 40)
    
    # Setup logging
    logger_system = setup_logging()
    
    # Get loggers for different modules
    main_logger = get_logger("main")
    replay_logger = get_logger("replay")
    onset_logger = get_logger("onset_detection")
    
    # Test different log levels
    main_logger.debug("This is a debug message")
    main_logger.info("This is an info message")
    main_logger.warning("This is a warning message")
    main_logger.error("This is an error message")
    
    # Test convenience functions
    sample_tick = {
        'stock_code': '005930',
        'price': 74000,
        'volume': 1000,
        'ts': 1704067200.0
    }
    
    log_replay_tick(replay_logger, sample_tick, row_num=1)
    
    log_event(main_logger, "test_event", {"key": "value", "number": 42})
    
    log_onset_detection(onset_logger, "005930", "candidate", 2.35, 1704067200.0)
    
    # Show log files
    print(f"\nLog files created: {[f.name for f in logger_system.get_log_files()]}")
    
    # Test level change
    print("\nChanging log level to DEBUG...")
    logger_system.set_level("DEBUG")
    main_logger.debug("This debug message should now appear")
    
    print("Logging demo completed. Check logs/app.log for output.")