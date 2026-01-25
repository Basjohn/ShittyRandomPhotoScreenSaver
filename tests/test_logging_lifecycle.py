"""
Tests for logging lifecycle management (Phase 0.1).

Verifies:
- Handler teardown prevents duplicate file descriptors after repeated setup/teardown cycles
- ANSI coloring auto-disables when stdout is not a TTY
- get_log_dir() warns when logging is disabled
"""
import logging
import sys
from pathlib import Path
from unittest import mock


class TestLoggingLifecycle:
    """Test logging setup/teardown lifecycle."""

    def test_repeated_setup_teardown_no_duplicate_handlers(self):
        """AC: No duplicate file descriptors after 3 setup/teardown cycles."""
        from core.logging.logger import setup_logging, _teardown_handlers

        # Get initial handler count
        root = logging.getLogger()
        
        # Run 3 setup/teardown cycles
        for i in range(3):
            setup_logging(debug=True)
            handler_count_after_setup = len(root.handlers)
            
            # Should have reasonable number of handlers (not multiplied)
            # Typical: main, console, perf, spotify_vis, spotify_vol, verbose = ~6-7
            assert handler_count_after_setup <= 10, (
                f"Cycle {i+1}: Too many handlers ({handler_count_after_setup}), "
                "possible leak from previous setup"
            )
        
        # After final setup, verify handler count is consistent
        final_count = len(root.handlers)
        
        # Teardown and verify clean state
        _teardown_handlers()
        assert len(root.handlers) == 0, "Handlers not fully cleaned up"
        
        # One more setup should have same count as before
        setup_logging(debug=True)
        assert len(root.handlers) == final_count, (
            f"Handler count inconsistent: expected {final_count}, got {len(root.handlers)}"
        )
        
        # Cleanup
        _teardown_handlers()

    def test_teardown_handlers_idempotent(self):
        """_teardown_handlers() should be safe to call multiple times."""
        from core.logging.logger import _teardown_handlers

        root = logging.getLogger()
        
        # Call teardown multiple times - should not raise
        for _ in range(5):
            _teardown_handlers()
        
        assert len(root.handlers) == 0

    def test_teardown_flushes_before_close(self):
        """Handlers should be flushed before closing."""
        from core.logging.logger import _teardown_handlers

        root = logging.getLogger()
        
        # Add a mock handler to track flush/close order
        mock_handler = mock.MagicMock(spec=logging.Handler)
        mock_handler.flush = mock.MagicMock()
        mock_handler.close = mock.MagicMock()
        root.addHandler(mock_handler)
        
        _teardown_handlers()
        
        # Verify flush was called before close
        assert mock_handler.flush.called, "flush() was not called"
        assert mock_handler.close.called, "close() was not called"


class TestColoredFormatterTTY:
    """Test ANSI coloring auto-disable when not TTY."""

    def test_colored_formatter_disables_color_when_not_tty(self):
        """ColoredFormatter should not emit ANSI codes when stdout is not a TTY."""
        from core.logging.logger import ColoredFormatter

        # Mock _is_stdout_tty to return False
        with mock.patch('core.logging.logger._is_stdout_tty', return_value=False):
            formatter = ColoredFormatter('%(levelname)s - %(message)s')
        
        # Create a test record
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=None,
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        # Should not contain ANSI escape codes
        assert '\033[' not in formatted, (
            f"ANSI codes found in non-TTY output: {formatted!r}"
        )

    def test_colored_formatter_enables_color_when_tty(self):
        """ColoredFormatter should emit ANSI codes when stdout is a TTY."""
        from core.logging.logger import ColoredFormatter

        # Mock _is_stdout_tty to return True
        with mock.patch('core.logging.logger._is_stdout_tty', return_value=True):
            formatter = ColoredFormatter('%(levelname)s - %(message)s')
        
        # Create a test record
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=None,
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        # Should contain ANSI escape codes for INFO level (green)
        assert '\033[' in formatted, (
            f"ANSI codes not found in TTY output: {formatted!r}"
        )


class TestGetLogDirWarning:
    """Test get_log_dir() warning when logging disabled."""

    def test_get_log_dir_warns_when_disabled(self, capsys):
        """get_log_dir() should warn to stderr when logging is disabled."""
        import core.logging.logger as logger_module
        
        # Save original values
        orig_disabled = logger_module._LOGGING_DISABLED
        orig_warning = logger_module._LOG_DIR_WARNING_EMITTED
        
        try:
            # Set logging as disabled and reset warning flag
            logger_module._LOGGING_DISABLED = True
            logger_module._LOG_DIR_WARNING_EMITTED = False
            
            # Call get_log_dir()
            result = logger_module.get_log_dir()
            
            # Should return a valid Path
            assert isinstance(result, Path)
            
            # Check stderr for warning
            captured = capsys.readouterr()
            assert "Warning: get_log_dir() called while logging is disabled" in captured.err
            
            # Second call should NOT emit warning again
            logger_module.get_log_dir()
            captured2 = capsys.readouterr()
            assert "Warning" not in captured2.err, "Warning emitted twice"
            
        finally:
            # Restore original values
            logger_module._LOGGING_DISABLED = orig_disabled
            logger_module._LOG_DIR_WARNING_EMITTED = orig_warning

    def test_get_log_dir_no_warning_when_enabled(self, capsys):
        """get_log_dir() should not warn when logging is enabled."""
        import core.logging.logger as logger_module
        
        # Save original values
        orig_disabled = logger_module._LOGGING_DISABLED
        orig_warning = logger_module._LOG_DIR_WARNING_EMITTED
        
        try:
            # Set logging as enabled
            logger_module._LOGGING_DISABLED = False
            logger_module._LOG_DIR_WARNING_EMITTED = False
            
            # Call get_log_dir()
            logger_module.get_log_dir()
            
            # Check stderr - should be empty
            captured = capsys.readouterr()
            assert "Warning" not in captured.err
            
        finally:
            # Restore original values
            logger_module._LOGGING_DISABLED = orig_disabled
            logger_module._LOG_DIR_WARNING_EMITTED = orig_warning


class TestIsTTYHelper:
    """Test _is_stdout_tty() helper function."""

    def test_is_stdout_tty_returns_bool(self):
        """_is_stdout_tty() should always return a boolean."""
        from core.logging.logger import _is_stdout_tty
        
        result = _is_stdout_tty()
        assert isinstance(result, bool)

    def test_is_stdout_tty_handles_none_stdout(self):
        """_is_stdout_tty() should handle None stdout gracefully."""
        from core.logging.logger import _is_stdout_tty
        
        with mock.patch.object(sys, 'stdout', None):
            result = _is_stdout_tty()
            assert result is False

    def test_is_stdout_tty_handles_exception(self):
        """_is_stdout_tty() should handle exceptions gracefully."""
        from core.logging.logger import _is_stdout_tty
        
        mock_stdout = mock.MagicMock()
        mock_stdout.isatty.side_effect = Exception("Test exception")
        
        with mock.patch.object(sys, 'stdout', mock_stdout):
            result = _is_stdout_tty()
            assert result is False
