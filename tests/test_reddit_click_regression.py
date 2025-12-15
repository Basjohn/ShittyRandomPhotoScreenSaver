#!/usr/bin/env python3
"""
Test script to verify Reddit widget click handling behavior in different scenarios.

This test verifies the fix for the regression where Reddit URLs were always deferred
in hard-exit mode, even when the application was running on the primary display.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
import pytest

from rendering.display_widget import DisplayWidget
from widgets.reddit_widget import RedditWidget


@pytest.fixture
def qt_app():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't quit the app, let it clean up naturally


@pytest.fixture
def mock_display_widget(qt_app):
    """Create a mock DisplayWidget for testing."""
    widget = Mock(spec=DisplayWidget)
    widget._screen = QApplication.primaryScreen()
    widget._is_hard_exit_enabled = Mock(return_value=False)
    widget._pending_reddit_url = None
    widget._reddit_exit_on_click = True
    widget._exiting = False
    widget.exit_requested = Mock()
    widget.reddit_widget = None
    widget.reddit2_widget = None
    widget.hide = Mock()
    return widget


@pytest.fixture
def mock_reddit_widget():
    """Create a mock RedditWidget for testing."""
    widget = Mock(spec=RedditWidget)
    widget.handle_click = Mock()
    widget.isVisible = Mock(return_value=True)
    
    # Create a proper geometry mock
    geometry_mock = Mock()
    geometry_mock.contains.return_value = True
    geometry_mock.x.return_value = 50
    geometry_mock.y.return_value = 50
    widget.geometry.return_value = geometry_mock
    
    return widget


def get_mock_qpoint(x, y):
    """Helper to create QPoint mocks."""
    point = Mock(spec=QPoint)
    point.x.return_value = x
    point.y.return_value = y
    return point


class TestRedditClickHandling:
    """Test Reddit widget click handling in different display configurations."""


    def test_primary_display_hard_exit_deferred(self, mock_display_widget, mock_reddit_widget):
        """Test that URLs are deferred on primary display in hard-exit mode."""
        # Setup: Primary display with hard-exit enabled
        mock_display_widget._screen = QApplication.primaryScreen()
        mock_display_widget._is_hard_exit_enabled = Mock(return_value=True)
        
        # Mock Reddit widget to return a URL when deferred=True
        test_url = "https://reddit.com/r/test"
        mock_reddit_widget.handle_click.return_value = test_url
        
        # Simulate mouse click at position within widget geometry
        event = Mock()
        event.pos.return_value = QPoint(100, 100)  # Position within widget
        event.button.return_value = 1  # Left click
        
        # Patch the widget lookup
        with patch.object(mock_display_widget, 'reddit_widget', mock_reddit_widget):
            with patch.object(mock_display_widget, 'reddit2_widget', None):
                mock_display_widget.mousePressEvent(event)
        
        # Verify URL was deferred
        assert mock_display_widget._pending_reddit_url == test_url
        assert mock_reddit_widget.handle_click.call_count == 1
        # Should be called with deferred=True for deferring
        mock_reddit_widget.handle_click.assert_called_with(QPoint(50, 50), deferred=True)
    
    def test_secondary_display_hard_exit_immediate_open(self, mock_display_widget, mock_reddit_widget):
        """Test that URLs open immediately on secondary display in hard-exit mode when only one screen."""
        # Setup: Secondary display with hard-exit enabled
        secondary_screen = Mock()
        secondary_screen.__hash__ = Mock(return_value=2)
        mock_display_widget._screen = secondary_screen
        mock_display_widget._is_hard_exit_enabled = Mock(return_value=True)
        
        # Mock Reddit widget to return True when called with deferred=False
        mock_reddit_widget.handle_click.return_value = True
        
        # Mock that only one screen is available (so not all displays taken)
        with patch('PySide6.QtGui.QGuiApplication.screens', return_value=[Mock()]):  # 1 screen total
            with patch('PySide6.QtGui.QGuiApplication.primaryScreen', return_value=Mock()):
                # Simulate mouse click at position within widget geometry
                event = Mock()
                event.pos.return_value = QPoint(100, 100)  # Position within widget
                event.button.return_value = 1  # Left click
                
                # Patch the widget lookup
                with patch.object(mock_display_widget, 'reddit_widget', mock_reddit_widget):
                    with patch.object(mock_display_widget, 'reddit2_widget', None):
                        mock_display_widget.mousePressEvent(event)
            
            # Verify URL was opened immediately (not deferred)
            assert mock_display_widget._pending_reddit_url is None
            assert mock_reddit_widget.handle_click.call_count == 1
            # Should be called with deferred=False for immediate opening
            mock_reddit_widget.handle_click.assert_called_with(QPoint(50, 50), deferred=False)
    
    def test_secondary_display_hard_exit_all_displays_taken_deferred(self, mock_display_widget, mock_reddit_widget):
        """Test that URLs are deferred on secondary display in hard-exit mode when multiple screens."""
        # Setup: Secondary display with hard-exit enabled
        secondary_screen = Mock()
        secondary_screen.__hash__ = Mock(return_value=2)
        mock_display_widget._screen = secondary_screen
        mock_display_widget._is_hard_exit_enabled = Mock(return_value=True)
        
        # Mock Reddit widget to return a URL when deferred=True
        test_url = "https://reddit.com/r/test"
        mock_reddit_widget.handle_click.return_value = test_url
        
        # Mock that multiple screens are available (so all displays might be taken)
        with patch('PySide6.QtGui.QGuiApplication.screens', return_value=[Mock(), Mock()]):  # 2 screens total
            with patch('PySide6.QtGui.QGuiApplication.primaryScreen', return_value=Mock()):
                # Simulate mouse click at position within widget geometry
                event = Mock()
                event.pos.return_value = QPoint(100, 100)  # Position within widget
                event.button.return_value = 1  # Left click
                
                # Patch the widget lookup
                with patch.object(mock_display_widget, 'reddit_widget', mock_reddit_widget):
                    with patch.object(mock_display_widget, 'reddit2_widget', None):
                        mock_display_widget.mousePressEvent(event)
            
            # Verify URL was deferred (all displays taken)
            assert mock_display_widget._pending_reddit_url == test_url
            assert mock_reddit_widget.handle_click.call_count == 1
            # Should be called with deferred=True for deferring
            mock_reddit_widget.handle_click.assert_called_with(QPoint(50, 50), deferred=True)
    
    def test_normal_mode_exits_instead_of_handling_click(self, mock_display_widget, mock_reddit_widget):
        """Test that in normal mode, Reddit clicks trigger exit instead of being handled."""
        # Setup: Normal mode (hard-exit disabled)
        mock_display_widget._screen = QApplication.primaryScreen()
        mock_display_widget._is_hard_exit_enabled = Mock(return_value=False)
        
        # Mock the exit_requested signal
        mock_display_widget.exit_requested = Mock()
        
        # Simulate mouse click
        event = Mock()
        event.pos.return_value = QPoint(100, 100)  # Position within widget
        event.button.return_value = 1  # Left click
        event.accept = Mock()
        
        # Patch the widget lookup
        with patch.object(mock_display_widget, 'reddit_widget', mock_reddit_widget):
            with patch.object(mock_display_widget, 'reddit2_widget', None):
                mock_display_widget.mousePressEvent(event)
        
        # Verify that Reddit widget was NOT called (no interaction routing in normal mode)
        assert mock_reddit_widget.handle_click.call_count == 0
        # Verify that exit was requested instead
        mock_display_widget.exit_requested.emit.assert_called_once()
        assert mock_display_widget._exiting is True


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
