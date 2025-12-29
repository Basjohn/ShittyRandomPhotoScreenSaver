"""
Tests for ThrottledLogger rate-limiting functionality.

Verifies that high-frequency log messages are properly throttled
to reduce log spam in hot paths like animation frames and visualizer ticks.
"""
import time
import logging
import pytest
from unittest.mock import MagicMock, patch

from core.logging.logger import ThrottledLogger, get_throttled_logger


class TestThrottledLogger:
    """Tests for ThrottledLogger class."""

    def test_init_defaults(self):
        """Test default initialization."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger)
        
        assert throttled._max_per_second == 1.0
        assert throttled._sample_rate == 0
        assert throttled.suppressed_count == 0
        assert throttled.emitted_count == 0

    def test_init_custom_rate(self):
        """Test initialization with custom rate."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=5.0)
        
        assert throttled._max_per_second == 5.0

    def test_init_sample_mode(self):
        """Test initialization with sampling mode."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, sample_rate=10)
        
        assert throttled._sample_rate == 10

    def test_first_message_always_emitted(self):
        """Test that first message is always emitted."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=1.0)
        
        throttled.debug("Test message")
        
        mock_logger.debug.assert_called_once_with("Test message")
        assert throttled.emitted_count == 1
        assert throttled.suppressed_count == 0

    def test_rate_limiting_suppresses_rapid_messages(self):
        """Test that rapid messages are suppressed."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=1.0)
        
        # Send 10 messages rapidly
        for i in range(10):
            throttled.debug("Rapid message")
        
        # Only first should be emitted (rate is 1/second)
        assert mock_logger.debug.call_count == 1
        assert throttled.emitted_count == 1
        assert throttled.suppressed_count == 9

    def test_rate_limiting_allows_after_interval(self):
        """Test that messages are allowed after rate interval."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=10.0)  # 100ms interval
        
        throttled.debug("Message 1")
        time.sleep(0.15)  # Wait longer than interval
        throttled.debug("Message 2")
        
        assert mock_logger.debug.call_count == 2
        assert throttled.emitted_count == 2

    def test_sampling_mode_logs_every_nth(self):
        """Test sampling mode logs 1 in N messages."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, sample_rate=5)
        
        # Send 15 messages
        for i in range(15):
            throttled.debug("Sampled message")
        
        # Should log at 1, 6, 11 (1 in 5)
        assert mock_logger.debug.call_count == 3
        assert throttled.emitted_count == 3
        assert throttled.suppressed_count == 12

    def test_different_messages_tracked_separately(self):
        """Test that different message templates are tracked separately."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=1.0)
        
        throttled.debug("Message A")
        throttled.debug("Message B")
        throttled.debug("Message A")  # Should be suppressed
        throttled.debug("Message B")  # Should be suppressed
        
        assert mock_logger.debug.call_count == 2
        assert throttled.emitted_count == 2
        assert throttled.suppressed_count == 2

    def test_warning_never_throttled(self):
        """Test that warning messages are never throttled."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=1.0)
        
        for i in range(5):
            throttled.warning("Warning message")
        
        assert mock_logger.warning.call_count == 5
        assert throttled.emitted_count == 5
        assert throttled.suppressed_count == 0

    def test_error_never_throttled(self):
        """Test that error messages are never throttled."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=1.0)
        
        for i in range(5):
            throttled.error("Error message")
        
        assert mock_logger.error.call_count == 5
        assert throttled.emitted_count == 5

    def test_critical_never_throttled(self):
        """Test that critical messages are never throttled."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=1.0)
        
        for i in range(5):
            throttled.critical("Critical message")
        
        assert mock_logger.critical.call_count == 5
        assert throttled.emitted_count == 5

    def test_info_is_throttled(self):
        """Test that info messages are throttled."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=1.0)
        
        for i in range(5):
            throttled.info("Info message")
        
        assert mock_logger.info.call_count == 1
        assert throttled.suppressed_count == 4

    def test_reset_counts(self):
        """Test reset_counts clears counters."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=1.0)
        
        for i in range(10):
            throttled.debug("Message")
        
        assert throttled.emitted_count == 1
        assert throttled.suppressed_count == 9
        
        throttled.reset_counts()
        
        assert throttled.emitted_count == 0
        assert throttled.suppressed_count == 0

    def test_unlimited_rate(self):
        """Test unlimited rate (max_per_second=0) allows all messages."""
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=0)
        
        for i in range(10):
            throttled.debug("Unlimited message")
        
        assert mock_logger.debug.call_count == 10
        assert throttled.emitted_count == 10
        assert throttled.suppressed_count == 0

    def test_thread_safety(self):
        """Test that throttling is thread-safe."""
        import threading
        
        mock_logger = MagicMock(spec=logging.Logger)
        throttled = ThrottledLogger(mock_logger, max_per_second=100.0)
        
        def log_messages():
            for _ in range(100):
                throttled.debug("Thread message")
        
        threads = [threading.Thread(target=log_messages) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have some emitted and some suppressed
        total = throttled.emitted_count + throttled.suppressed_count
        assert total == 500  # 5 threads * 100 messages


class TestGetThrottledLogger:
    """Tests for get_throttled_logger factory function."""

    def test_returns_throttled_logger(self):
        """Test that factory returns ThrottledLogger instance."""
        throttled = get_throttled_logger("test.module")
        
        assert isinstance(throttled, ThrottledLogger)

    def test_custom_rate(self):
        """Test factory with custom rate."""
        throttled = get_throttled_logger("test.module", max_per_second=5.0)
        
        assert throttled._max_per_second == 5.0

    def test_sample_mode(self):
        """Test factory with sample mode."""
        throttled = get_throttled_logger("test.module", sample_rate=10)
        
        assert throttled._sample_rate == 10
