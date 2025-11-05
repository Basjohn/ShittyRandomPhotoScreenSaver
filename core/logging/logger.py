"""
Centralized logging configuration for screensaver application.

Uses rotating file handler with logs stored in logs/ directory.
Includes colored console output for debug mode.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    FALLBACK_COLOR = '\033[38;5;208m'  # Orange for fallback warnings
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def format(self, record):
        # Save original levelname
        original_levelname = record.levelname
        original_msg = record.msg
        
        # Check if this is a fallback message
        is_fallback = '[FALLBACK]' in str(record.msg)
        
        # Color the entire line
        if record.levelname in self.COLORS:
            # Use orange for fallback warnings instead of regular yellow
            if is_fallback and record.levelname == 'WARNING':
                color = self.FALLBACK_COLOR
            else:
                color = self.COLORS[record.levelname]
            
            # Color the level name in bold
            record.levelname = f"{self.BOLD}{color}{record.levelname}{self.RESET}"
            # Format the message
            message = super().format(record)
            # Color the entire formatted message
            colored_message = f"{color}{message}{self.RESET}"
            # Restore original values
            record.levelname = original_levelname
            record.msg = original_msg
            return colored_message
        
        # Restore original values for non-colored output
        record.levelname = original_levelname
        record.msg = original_msg
        return super().format(record)


def setup_logging(debug: bool = False) -> None:
    """
    Configure application logging with file rotation.
    
    Args:
        debug: If True, set log level to DEBUG, otherwise INFO
    """
    # Create logs directory
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "screensaver.log"
    
    # Configure root logger
    level = logging.DEBUG if debug else logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Console handler (for development) - with colors in debug mode
    console_handler = logging.StreamHandler(sys.stdout)
    if debug and sys.stdout.isatty():
        # Use colored formatter for terminal output
        colored_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(colored_formatter)
    else:
        console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    
    if debug:
        root_logger.addHandler(console_handler)
    
    # Log startup
    root_logger.info("=" * 60)
    root_logger.info("Screensaver logging initialized (debug=%s)", debug)
    root_logger.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (usually __name__ of the module)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)
