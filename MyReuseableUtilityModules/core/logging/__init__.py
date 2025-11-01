"""
Simplified logging module for the framework.

This is a minimal logging wrapper that works standalone.
In your application, you can replace this with your own logging system.
"""

import logging
import sys
from typing import Optional

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (usually __name__ of the module)
        level: Optional logging level (e.g., logging.DEBUG)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger

__all__ = ['get_logger']
