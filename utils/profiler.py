"""
Simple profiler for diagnosing performance issues.

Usage:
    with Profiler("operation_name"):
        # code to profile
"""
import time
from typing import Optional
from contextlib import contextmanager
from core.logging.logger import get_logger

logger = get_logger(__name__)


class Profiler:
    """Context manager for profiling code blocks."""
    
    def __init__(self, name: str, threshold_ms: float = 0.0, log_level: str = "DEBUG"):
        """
        Initialize profiler.
        
        Args:
            name: Name of the operation being profiled
            threshold_ms: Only log if duration exceeds this threshold (in milliseconds)
            log_level: Log level to use ("DEBUG", "INFO", "WARNING")
        """
        self.name = name
        self.threshold_ms = threshold_ms
        self.log_level = log_level.upper()
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        duration_ms = (self.end_time - self.start_time) * 1000.0
        
        if duration_ms >= self.threshold_ms:
            msg = f"[PROFILE] {self.name}: {duration_ms:.2f}ms"
            
            if self.log_level == "INFO":
                logger.info(msg)
            elif self.log_level == "WARNING":
                logger.warning(msg)
            else:
                logger.debug(msg)
        
        return False  # Don't suppress exceptions
    
    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000.0


@contextmanager
def profile(name: str, threshold_ms: float = 0.0, log_level: str = "DEBUG"):
    """
    Context manager for profiling code blocks.
    
    Args:
        name: Name of the operation
        threshold_ms: Only log if duration exceeds threshold
        log_level: Log level ("DEBUG", "INFO", "WARNING")
    
    Example:
        with profile("expensive_operation", threshold_ms=10.0):
            do_expensive_work()
    """
    profiler = Profiler(name, threshold_ms, log_level)
    with profiler:
        yield profiler
