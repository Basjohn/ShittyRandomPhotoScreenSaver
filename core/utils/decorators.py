"""
Centralized error handling decorators.

Provides reusable decorators for common error handling patterns:
- Exception suppression with logging
- Retry logic with exponential backoff
- Error logging with context
"""
from typing import Callable, TypeVar, ParamSpec, Any, Optional
from functools import wraps
import time
from core.logging.logger import get_logger

P = ParamSpec('P')
T = TypeVar('T')

logger = get_logger(__name__)


def suppress_exceptions(
    logger_instance: Optional[Any] = None,
    message: str = "Operation failed",
    return_value: Any = None,
    log_level: str = "error"
) -> Callable[[Callable[P, T]], Callable[P, Optional[T]]]:
    """
    Decorator to suppress exceptions and log them.
    
    Args:
        logger_instance: Logger to use (defaults to module logger)
        message: Error message prefix
        return_value: Value to return on exception
        log_level: Logging level ('debug', 'info', 'warning', 'error')
    
    Returns:
        Decorated function that suppresses exceptions
    
    Example:
        @suppress_exceptions(logger, "Failed to load image")
        def load_image(path: str) -> QImage:
            return QImage(path)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, Optional[T]]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log = logger_instance or logger
                log_method = getattr(log, log_level, log.error)
                log_method(f"{message}: {e}", exc_info=True)
                return return_value
        return wrapper
    return decorator


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    logger_instance: Optional[Any] = None
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to retry a function on failure with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
        logger_instance: Logger to use (defaults to module logger)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry(max_attempts=3, delay=1.0, backoff=2.0)
        def fetch_data(url: str) -> dict:
            return requests.get(url).json()
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            log = logger_instance or logger
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        log.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    
                    log.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise RuntimeError(f"{func.__name__} failed after {max_attempts} attempts")
        return wrapper
    return decorator


def log_errors(
    logger_instance: Optional[Any] = None,
    message: str = "Error in {func_name}",
    log_level: str = "error",
    reraise: bool = True
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to log errors with context before optionally re-raising.
    
    Args:
        logger_instance: Logger to use (defaults to module logger)
        message: Error message template (can use {func_name} placeholder)
        log_level: Logging level ('debug', 'info', 'warning', 'error')
        reraise: Whether to re-raise the exception after logging
    
    Returns:
        Decorated function that logs errors
    
    Example:
        @log_errors(logger, "Failed to process {func_name}")
        def process_data(data: dict) -> None:
            validate(data)
            transform(data)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log = logger_instance or logger
                log_method = getattr(log, log_level, log.error)
                error_msg = message.format(func_name=func.__name__)
                log_method(f"{error_msg}: {e}", exc_info=True)
                
                if reraise:
                    raise
                return None  # type: ignore
        return wrapper
    return decorator


def log_call(
    logger_instance: Optional[Any] = None,
    log_level: str = "debug",
    log_args: bool = False,
    log_result: bool = False
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to log function calls with optional args and return values.
    
    Args:
        logger_instance: Logger to use (defaults to module logger)
        log_level: Logging level ('debug', 'info', 'warning', 'error')
        log_args: Whether to log function arguments
        log_result: Whether to log return value
    
    Returns:
        Decorated function that logs calls
    
    Example:
        @log_call(logger, log_args=True, log_result=True)
        def calculate(x: int, y: int) -> int:
            return x + y
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            log = logger_instance or logger
            log_method = getattr(log, log_level, log.debug)
            
            if log_args:
                log_method(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            else:
                log_method(f"Calling {func.__name__}")
            
            result = func(*args, **kwargs)
            
            if log_result:
                log_method(f"{func.__name__} returned: {result}")
            
            return result
        return wrapper
    return decorator


def deprecated(
    message: str = "This function is deprecated",
    logger_instance: Optional[Any] = None
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to mark functions as deprecated and log warnings.
    
    Args:
        message: Deprecation message
        logger_instance: Logger to use (defaults to module logger)
    
    Returns:
        Decorated function that logs deprecation warnings
    
    Example:
        @deprecated("Use new_function() instead")
        def old_function() -> None:
            pass
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            log = logger_instance or logger
            log.warning(f"{func.__name__} is deprecated: {message}")
            return func(*args, **kwargs)
        return wrapper
    return decorator
