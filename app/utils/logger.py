import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from app.config import settings
from app.constants import (
    DEFAULT_LOGGER_NAME,
    LOG_BACKUP_COUNT,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    LOG_MAX_BYTES,
)
from pathlib import Path

def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """
    Setup a comprehensive logger with console and file handlers.
    Includes rotation to prevent log files from growing too large.
    
    Args:
        name: Logger name
        log_file: Optional log file path. If None, uses settings.LOG_FILE
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File handler with rotation (if enabled)
    if settings.ENABLE_FILE_LOGGING:
        try:
            log_path = log_file or settings.LOG_FILE
            log_dir = os.path.dirname(log_path)
            
            # Create log directory if it doesn't exist
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not setup file logging: {e}")

    return logger

# Create a default logger for the application
logger = setup_logger(DEFAULT_LOGGER_NAME)

