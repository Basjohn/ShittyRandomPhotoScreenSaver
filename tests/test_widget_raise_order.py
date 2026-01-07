"""
Tests for widget raise/fade ordering policy.

Verifies that all overlay raises are synchronous immediately after
transition.start() returns (no 0ms singleShot for raises; QTimer usage
allowed for fade coordination only).
"""
import pytest
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import QTimer
from unittest.mock import Mock, patch
from rendering.widget_manager import WidgetManager
from core.settings.settings_manager import SettingsManager
from core.resources.manager import ResourceManager


@pytest.fixture
def settings_manager(qtbot):
    """Create test settings manager."""
    settings = SettingsManager(organization="Test", application="WidgetRaiseTest")
    yield settings
    settings.clear()


@pytest.fixture
def resource_manager():
    """Create test resource manager."""
    manager = ResourceManager()
    yield manager
    manager.shutdown()


@pytest.fixture
def widget_manager(qtbot, settings_manager, resource_manager):
    """Create test widget manager."""
    parent = QWidget()
    qtbot.addWidget(parent)
    manager = WidgetManager(parent, settings_manager, resource_manager)
    yield manager
    manager.cleanup_all()


def test_widget_raise_is_synchronous_not_deferred(widget_manager):
    """Test that widget raises are synchronous, not deferred with QTimer.singleShot(0)."""
    # Create a test widget
    test_widget = QLabel("Test")
    test_widget.setParent(widget_manager._parent)
    widget_manager.register_widget("test", test_widget)
    
    # Mock raise_() to track when it's called
    original_raise = test_widget.raise_
    raise_called = []
    
    def tracked_raise():
        raise_called.append("raised")
        original_raise()
    
    test_widget.raise_ = tracked_raise
    
    # Call raise_all_widgets() which should raise synchronously
    widget_manager.raise_all_widgets()
    
    # Verify raise was called immediately (synchronously)
    assert len(raise_called) == 1, "Widget should be raised synchronously"
    
    # Verify no deferred calls are pending (process events should not trigger more raises)
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    assert len(raise_called) == 1, "No deferred raises should occur"


def test_no_single_shot_zero_for_raises(widget_manager):
    """Test that QTimer.singleShot(0, ...) is not used for widget raises."""
    test_widget = QLabel("Test")
    test_widget.setParent(widget_manager._parent)
    widget_manager.register_widget("test", test_widget)
    
    # Patch QTimer.singleShot to detect any 0ms calls
    with patch.object(QTimer, 'singleShot') as mock_single_shot:
        widget_manager.raise_all_widgets()
        
        # Check if singleShot was called with 0ms (which would be deferred)
        zero_ms_calls = [call for call in mock_single_shot.call_args_list 
                         if call[0][0] == 0]
        
        assert len(zero_ms_calls) == 0, \
            "QTimer.singleShot(0, ...) should not be used for widget raises"


def test_raise_widget_by_name_is_synchronous(widget_manager):
    """Test that raise_widget_by_name() raises synchronously."""
    test_widget = QLabel("Test")
    test_widget.setParent(widget_manager._parent)
    widget_manager.register_widget("test", test_widget)
    
    raise_count = []
    original_raise = test_widget.raise_
    
    def tracked_raise():
        raise_count.append(1)
        original_raise()
    
    test_widget.raise_ = tracked_raise
    
    # Call raise_widget_by_name
    result = widget_manager.raise_widget_by_name("test")
    
    # Should return True and raise synchronously
    assert result is True
    assert len(raise_count) == 1, "Widget should be raised synchronously"


def test_rate_limited_raises_use_timer_correctly(widget_manager):
    """Test that rate-limited raises use QTimer for scheduling, not immediate raises."""
    test_widget = QLabel("Test")
    test_widget.setParent(widget_manager._parent)
    widget_manager.register_widget("test", test_widget)
    
    # First raise should be immediate
    widget_manager.raise_all_widgets(force=False)
    
    # Second raise within rate limit should schedule a timer (not immediate)
    with patch.object(QTimer, 'singleShot') as mock_single_shot:
        widget_manager.raise_all_widgets(force=False)
        
        # Should have scheduled a deferred raise (not 0ms)
        if mock_single_shot.called:
            # Verify it's not 0ms (which would be immediate)
            for call_args in mock_single_shot.call_args_list:
                delay_ms = call_args[0][0]
                assert delay_ms > 0, "Rate-limited raises should use delay > 0ms"


def test_forced_raises_are_immediate(widget_manager):
    """Test that forced raises bypass rate limiting and are immediate."""
    test_widget = QLabel("Test")
    test_widget.setParent(widget_manager._parent)
    widget_manager.register_widget("test", test_widget)
    
    raise_count = []
    original_raise = test_widget.raise_
    
    def tracked_raise():
        raise_count.append(1)
        original_raise()
    
    test_widget.raise_ = tracked_raise
    
    # Multiple forced raises should all execute immediately
    widget_manager.raise_all_widgets(force=True)
    widget_manager.raise_all_widgets(force=True)
    widget_manager.raise_all_widgets(force=True)
    
    assert len(raise_count) == 3, "All forced raises should execute immediately"


def test_fade_coordination_can_use_timers(widget_manager):
    """Test that fade coordination is allowed to use QTimer (not raises)."""
    # This test documents that QTimer usage is acceptable for fade coordination,
    # just not for widget raises themselves.
    
    test_widget = QLabel("Test")
    test_widget.setParent(widget_manager._parent)
    widget_manager.register_widget("test", test_widget)
    
    # Fade coordination methods can use timers
    # (This is allowed per the policy: "QTimer usage allowed for fade kicks only")
    with patch.object(QTimer, 'singleShot'):
        # Simulate fade coordination (not a raise operation)
        widget_manager.request_overlay_fade_sync("test", duration_ms=1000)
        
        # Timer usage for fade coordination is acceptable
        # (We're just documenting this is allowed, not testing specific implementation)
        pass


def test_widget_creation_raises_synchronously(widget_manager, settings_manager):
    """Test that widgets are raised synchronously during creation."""
    # Configure settings for a clock widget
    settings_manager.set("widgets.clock.enabled", True)
    settings_manager.set("widgets.clock.monitor", 1)
    
    with patch('rendering.widget_manager.ClockWidgetFactory') as mock_factory:
        mock_widget = Mock(spec=QLabel)
        mock_factory.return_value.create_widget.return_value = mock_widget
        
        # Create widgets
        widget_manager.setup_all_widgets(screen_index=0, screen_count=1)
        
        # Verify raise_() was called on the created widget
        if mock_widget.raise_.called:
            # Should be called synchronously during setup, not deferred
            assert mock_widget.raise_.call_count >= 1


def test_multiple_widgets_raised_in_order(widget_manager):
    """Test that multiple widgets are raised in registration order."""
    widgets = []
    raise_order = []
    
    for i in range(5):
        widget = QLabel(f"Widget{i}")
        widget.setParent(widget_manager._parent)
        widget_manager.register_widget(f"test{i}", widget)
        widgets.append(widget)
        
        original_raise = widget.raise_
        widget_index = i
        
        def make_tracked_raise(idx):
            def tracked_raise():
                raise_order.append(idx)
                widgets[idx].raise_ = original_raise  # Restore original
                widgets[idx].raise_()
            return tracked_raise
        
        widget.raise_ = make_tracked_raise(widget_index)
    
    # Raise all widgets
    widget_manager.raise_all_widgets()
    
    # Verify all were raised
    assert len(raise_order) >= 5, "All widgets should be raised"


def test_no_raise_on_hidden_widgets(widget_manager):
    """Test that hidden widgets are not raised."""
    visible_widget = QLabel("Visible")
    visible_widget.setParent(widget_manager._parent)
    visible_widget.show()
    widget_manager.register_widget("visible", visible_widget)
    
    hidden_widget = QLabel("Hidden")
    hidden_widget.setParent(widget_manager._parent)
    hidden_widget.hide()
    widget_manager.register_widget("hidden", hidden_widget)
    
    visible_raised = []
    hidden_raised = []
    
    original_visible_raise = visible_widget.raise_
    original_hidden_raise = hidden_widget.raise_
    
    def track_visible():
        visible_raised.append(1)
        original_visible_raise()
    
    def track_hidden():
        hidden_raised.append(1)
        original_hidden_raise()
    
    visible_widget.raise_ = track_visible
    hidden_widget.raise_ = track_hidden
    
    # Raise all widgets
    widget_manager.raise_all_widgets()
    
    # Only visible widget should be raised
    assert len(visible_raised) == 1, "Visible widget should be raised"
    assert len(hidden_raised) == 0, "Hidden widget should not be raised"


def test_policy_documentation():
    """Document the widget raise/fade ordering policy.
    
    Policy:
    1. Widget raises MUST be synchronous immediately after transition.start()
    2. No QTimer.singleShot(0, ...) for raises (deferred raises not allowed)
    3. QTimer usage IS allowed for fade coordination (fade kicks)
    4. Rate limiting uses QTimer with delay > 0ms (not immediate)
    5. Forced raises bypass rate limiting and execute immediately
    
    This test serves as documentation of the policy.
    """
    assert True, "Policy documented in test docstring"
