"""
Tests for centralized error handling decorators.
"""
import pytest
import time
from unittest.mock import MagicMock
from core.utils.decorators import (
    suppress_exceptions,
    retry,
    log_errors,
    log_call,
    deprecated
)


class TestSuppressExceptions:
    """Test suppress_exceptions decorator."""
    
    def test_suppress_exception_returns_none(self):
        """Test that exceptions are suppressed and None is returned by default."""
        mock_logger = MagicMock()
        
        @suppress_exceptions(mock_logger, "Test failed")
        def failing_func():
            raise ValueError("Test error")
        
        result = failing_func()
        assert result is None
        mock_logger.error.assert_called_once()
    
    def test_suppress_exception_returns_custom_value(self):
        """Test that custom return value is used on exception."""
        mock_logger = MagicMock()
        
        @suppress_exceptions(mock_logger, "Test failed", return_value=42)
        def failing_func():
            raise ValueError("Test error")
        
        result = failing_func()
        assert result == 42
    
    def test_suppress_exception_logs_with_custom_level(self):
        """Test that custom log level is used."""
        mock_logger = MagicMock()
        
        @suppress_exceptions(mock_logger, "Test failed", log_level="warning")
        def failing_func():
            raise ValueError("Test error")
        
        failing_func()
        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_not_called()
    
    def test_no_exception_returns_normal_value(self):
        """Test that normal return value is preserved when no exception."""
        mock_logger = MagicMock()
        
        @suppress_exceptions(mock_logger, "Test failed")
        def working_func():
            return "success"
        
        result = working_func()
        assert result == "success"
        mock_logger.error.assert_not_called()


class TestRetry:
    """Test retry decorator."""
    
    def test_retry_succeeds_on_first_attempt(self):
        """Test that function succeeds on first attempt without retry."""
        mock_logger = MagicMock()
        call_count = [0]
        
        @retry(max_attempts=3, delay=0.1, logger_instance=mock_logger)
        def working_func():
            call_count[0] += 1
            return "success"
        
        result = working_func()
        assert result == "success"
        assert call_count[0] == 1
        mock_logger.warning.assert_not_called()
    
    def test_retry_succeeds_on_second_attempt(self):
        """Test that function retries and succeeds on second attempt."""
        mock_logger = MagicMock()
        call_count = [0]
        
        @retry(max_attempts=3, delay=0.01, logger_instance=mock_logger)
        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count[0] == 2
        mock_logger.warning.assert_called_once()
    
    def test_retry_fails_after_max_attempts(self):
        """Test that function raises after max attempts."""
        mock_logger = MagicMock()
        call_count = [0]
        
        @retry(max_attempts=3, delay=0.01, logger_instance=mock_logger)
        def always_failing_func():
            call_count[0] += 1
            raise ValueError("Permanent error")
        
        with pytest.raises(ValueError):
            always_failing_func()
        
        assert call_count[0] == 3
        assert mock_logger.warning.call_count == 2
        mock_logger.error.assert_called_once()
    
    def test_retry_with_exponential_backoff(self):
        """Test that delay increases with backoff multiplier."""
        mock_logger = MagicMock()
        call_times = []
        
        @retry(max_attempts=3, delay=0.05, backoff=2.0, logger_instance=mock_logger)
        def timing_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Retry")
            return "success"
        
        timing_func()
        
        # Check that delays increase (approximately)
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        # Second delay should be roughly 2x first delay
        assert delay2 > delay1 * 1.5


class TestLogErrors:
    """Test log_errors decorator."""
    
    def test_log_errors_logs_and_reraises(self):
        """Test that errors are logged and re-raised by default."""
        mock_logger = MagicMock()
        
        @log_errors(mock_logger, "Error in {func_name}")
        def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_func()
        
        mock_logger.error.assert_called_once()
        assert "Error in failing_func" in str(mock_logger.error.call_args)
    
    def test_log_errors_suppresses_when_reraise_false(self):
        """Test that errors are logged but not re-raised when reraise=False."""
        mock_logger = MagicMock()
        
        @log_errors(mock_logger, "Error in {func_name}", reraise=False)
        def failing_func():
            raise ValueError("Test error")
        
        result = failing_func()
        assert result is None
        mock_logger.error.assert_called_once()
    
    def test_log_errors_with_custom_level(self):
        """Test that custom log level is used."""
        mock_logger = MagicMock()
        
        @log_errors(mock_logger, "Warning in {func_name}", log_level="warning", reraise=False)
        def failing_func():
            raise ValueError("Test error")
        
        failing_func()
        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_not_called()


class TestLogCall:
    """Test log_call decorator."""
    
    def test_log_call_basic(self):
        """Test basic function call logging."""
        mock_logger = MagicMock()
        
        @log_call(mock_logger)
        def test_func():
            return "result"
        
        result = test_func()
        assert result == "result"
        mock_logger.debug.assert_called_once()
        assert "Calling test_func" in str(mock_logger.debug.call_args)
    
    def test_log_call_with_args(self):
        """Test logging with arguments."""
        mock_logger = MagicMock()
        
        @log_call(mock_logger, log_args=True)
        def test_func(x, y):
            return x + y
        
        result = test_func(1, 2)
        assert result == 3
        mock_logger.debug.assert_called_once()
        call_str = str(mock_logger.debug.call_args)
        assert "args=" in call_str
    
    def test_log_call_with_result(self):
        """Test logging with return value."""
        mock_logger = MagicMock()
        
        @log_call(mock_logger, log_result=True)
        def test_func():
            return 42
        
        result = test_func()
        assert result == 42
        assert mock_logger.debug.call_count == 2
        # Second call should log the result
        second_call = mock_logger.debug.call_args_list[1]
        assert "returned" in str(second_call)


class TestDeprecated:
    """Test deprecated decorator."""
    
    def test_deprecated_logs_warning(self):
        """Test that deprecated decorator logs warning."""
        mock_logger = MagicMock()
        
        @deprecated("Use new_func instead", mock_logger)
        def old_func():
            return "result"
        
        result = old_func()
        assert result == "result"
        mock_logger.warning.assert_called_once()
        assert "deprecated" in str(mock_logger.warning.call_args).lower()
        assert "Use new_func instead" in str(mock_logger.warning.call_args)
    
    def test_deprecated_still_executes(self):
        """Test that deprecated function still executes normally."""
        mock_logger = MagicMock()
        
        @deprecated("Old function", mock_logger)
        def old_func(x, y):
            return x * y
        
        result = old_func(3, 4)
        assert result == 12


class TestDecoratorCombinations:
    """Test combining multiple decorators."""
    
    def test_suppress_and_retry(self):
        """Test combining suppress_exceptions with retry."""
        mock_logger = MagicMock()
        call_count = [0]
        
        @suppress_exceptions(mock_logger, "Suppressed", return_value="fallback")
        @retry(max_attempts=2, delay=0.01, logger_instance=mock_logger)
        def flaky_func():
            call_count[0] += 1
            raise ValueError("Always fails")
        
        result = flaky_func()
        # Retry will exhaust attempts, then suppress will catch the final exception
        assert result == "fallback"
        assert call_count[0] == 2
    
    def test_log_errors_and_retry(self):
        """Test combining log_errors with retry."""
        mock_logger = MagicMock()
        call_count = [0]
        
        @log_errors(mock_logger, "Error in {func_name}", reraise=True)
        @retry(max_attempts=2, delay=0.01, logger_instance=mock_logger)
        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Retry this")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count[0] == 2
