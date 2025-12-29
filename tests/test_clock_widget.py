"""Tests for clock widget."""
import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QColor
from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def parent_widget(qapp):
    """Create parent widget."""
    widget = QWidget()
    widget.resize(800, 600)
    yield widget
    widget.deleteLater()


def test_time_format_enum():
    """Test TimeFormat enum."""
    assert TimeFormat.TWELVE_HOUR.value == "12h"
    assert TimeFormat.TWENTY_FOUR_HOUR.value == "24h"


def test_clock_position_enum():
    """Test ClockPosition enum."""
    assert ClockPosition.TOP_LEFT.value == "top_left"
    assert ClockPosition.TOP_RIGHT.value == "top_right"
    assert ClockPosition.BOTTOM_LEFT.value == "bottom_left"
    assert ClockPosition.BOTTOM_RIGHT.value == "bottom_right"
    assert ClockPosition.TOP_CENTER.value == "top_center"
    assert ClockPosition.BOTTOM_CENTER.value == "bottom_center"


def test_clock_creation(qapp, parent_widget):
    """Test clock widget creation."""
    clock = ClockWidget(
        parent=parent_widget,
        time_format=TimeFormat.TWELVE_HOUR,
        position=ClockPosition.TOP_RIGHT,
        show_seconds=True
    )
    
    assert clock is not None
    assert clock._time_format == TimeFormat.TWELVE_HOUR
    assert clock._clock_position == ClockPosition.TOP_RIGHT
    assert clock.get_position().value == ClockPosition.TOP_RIGHT.value
    assert clock._show_seconds is True
    assert clock.is_running() is False


def test_clock_start_stop(qapp, parent_widget, thread_manager):
    """Test starting and stopping clock."""
    clock = ClockWidget(parent=parent_widget)
    clock._thread_manager = thread_manager  # Inject thread manager
    parent_widget.show()  # Show parent so child visibility works
    
    assert clock.is_running() is False
    
    clock.start()
    assert clock.is_running() is True
    assert clock.isVisible() is True
    
    clock.stop()
    assert clock.is_running() is False
    assert clock.isVisible() is False


def test_clock_signals(qapp, parent_widget, qtbot, thread_manager):
    """Test clock signals."""
    clock = ClockWidget(parent=parent_widget)
    clock._thread_manager = thread_manager  # Inject thread manager
    
    time_updates = []
    clock.time_updated.connect(lambda t: time_updates.append(t))
    
    clock.start()
    
    # Wait for at least one update
    qtbot.wait(1500)
    
    assert len(time_updates) >= 1
    
    clock.stop()


def test_clock_12h_format(qapp, parent_widget, thread_manager):
    """Test 12-hour format."""
    clock = ClockWidget(
        parent=parent_widget,
        time_format=TimeFormat.TWELVE_HOUR,
        show_seconds=True
    )
    clock._thread_manager = thread_manager  # Inject thread manager
    
    clock.start()
    text = clock.text()
    
    # Should contain AM or PM
    assert 'AM' in text or 'PM' in text
    # Should contain colons
    assert ':' in text
    
    clock.stop()


def test_clock_24h_format(qapp, parent_widget, thread_manager):
    """Test 24-hour format."""
    clock = ClockWidget(
        parent=parent_widget,
        time_format=TimeFormat.TWENTY_FOUR_HOUR,
        show_seconds=True
    )
    clock._thread_manager = thread_manager  # Inject thread manager
    
    clock.start()
    text = clock.text()
    
    # Should NOT contain AM or PM
    assert 'AM' not in text
    assert 'PM' not in text
    # Should contain colons
    assert ':' in text
    
    clock.stop()


def test_clock_without_seconds(qapp, parent_widget, thread_manager):
    """Test clock without seconds."""
    clock = ClockWidget(
        parent=parent_widget,
        show_seconds=False
    )
    clock._thread_manager = thread_manager  # Inject thread manager
    
    clock.start()
    text = clock.text()
    
    # Should have only one colon (HH:MM)
    assert text.count(':') == 1
    
    clock.stop()


def test_clock_with_seconds(qapp, parent_widget, thread_manager):
    """Test clock with seconds."""
    clock = ClockWidget(
        parent=parent_widget,
        show_seconds=True
    )
    clock._thread_manager = thread_manager  # Inject thread manager
    
    clock.start()
    text = clock.text()
    
    # Should have two colons (HH:MM:SS)
    assert text.count(':') == 2
    
    clock.stop()


def test_clock_set_time_format(qapp, parent_widget, thread_manager):
    """Test setting time format."""
    clock = ClockWidget(parent=parent_widget, time_format=TimeFormat.TWELVE_HOUR)
    clock._thread_manager = thread_manager
    
    clock.start()
    
    # Change to 24-hour
    clock.set_time_format(TimeFormat.TWENTY_FOUR_HOUR)
    text = clock.text()
    assert 'AM' not in text and 'PM' not in text
    
    # Change back to 12-hour
    clock.set_time_format(TimeFormat.TWELVE_HOUR)
    text = clock.text()
    assert 'AM' in text or 'PM' in text
    
    clock.stop()


def test_clock_set_show_seconds(qapp, parent_widget, thread_manager):
    """Test setting show seconds."""
    clock = ClockWidget(parent=parent_widget, show_seconds=True)
    clock._thread_manager = thread_manager
    
    clock.start()
    assert clock.text().count(':') == 2
    
    clock.set_show_seconds(False)
    assert clock.text().count(':') == 1
    
    clock.set_show_seconds(True)
    assert clock.text().count(':') == 2
    
    clock.stop()


def test_clock_all_positions(qapp, parent_widget, thread_manager):
    """Test all clock positions."""
    parent_widget.show()  # Show parent so child visibility works
    
    positions = [
        ClockPosition.TOP_LEFT,
        ClockPosition.TOP_RIGHT,
        ClockPosition.BOTTOM_LEFT,
        ClockPosition.BOTTOM_RIGHT,
        ClockPosition.TOP_CENTER,
        ClockPosition.BOTTOM_CENTER
    ]
    
    for position in positions:
        clock = ClockWidget(parent=parent_widget, position=position)
        clock._thread_manager = thread_manager
        clock.start()
        
        # Check position is set
        assert clock._clock_position == position
        assert clock.get_position().value == position.value
        
        # Check widget is visible
        assert clock.isVisible() is True
        
        clock.stop()


def test_clock_set_position(qapp, parent_widget, thread_manager):
    """Test changing clock position."""
    clock = ClockWidget(parent=parent_widget, position=ClockPosition.TOP_LEFT)
    clock._thread_manager = thread_manager
    
    clock.start()
    old_x, old_y = clock.x(), clock.y()
    
    clock.set_position(ClockPosition.BOTTOM_RIGHT)
    new_x, new_y = clock.x(), clock.y()
    
    # Position should have changed
    assert (new_x, new_y) != (old_x, old_y)
    
    clock.stop()


def test_clock_set_font_size(qapp, parent_widget):
    """Test setting font size."""
    clock = ClockWidget(parent=parent_widget)
    
    clock.set_font_size(72)
    assert clock._font_size == 72
    
    # Invalid size should fall back to widget default
    clock.set_font_size(-10)
    assert clock._font_size == ClockWidget.DEFAULT_FONT_SIZE


def test_clock_set_text_color(qapp, parent_widget):
    """Test setting text color."""
    clock = ClockWidget(parent=parent_widget)
    
    color = QColor(255, 0, 0, 255)  # Red
    clock.set_text_color(color)
    
    assert clock._text_color == color


def test_clock_set_margin(qapp, parent_widget):
    """Test setting margin."""
    clock = ClockWidget(parent=parent_widget)
    
    clock.set_margin(50)
    assert clock._margin == 50
    
    # Negative margin reuses default edge offset
    clock.set_margin(-10)
    assert clock._margin == ClockWidget.DEFAULT_MARGIN


def test_clock_cleanup(qapp, parent_widget, thread_manager):
    """Test clock cleanup."""
    clock = ClockWidget(parent=parent_widget)
    clock._thread_manager = thread_manager
    
    clock.start()
    assert clock.is_running() is True
    
    clock.cleanup()
    assert clock.is_running() is False
    assert clock._timer is None


def test_clock_concurrent_start_prevention(qapp, parent_widget, thread_manager):
    """Test that starting when already running is handled."""
    clock = ClockWidget(parent=parent_widget)
    clock._thread_manager = thread_manager
    
    clock.start()
    assert clock.is_running() is True
    
    # Try to start again
    clock.start()
    assert clock.is_running() is True  # Still running
    
    clock.stop()


def test_clock_updates_over_time(qapp, parent_widget, qtbot, thread_manager):
    """Test that clock updates multiple times."""
    clock = ClockWidget(parent=parent_widget, show_seconds=True)
    clock._thread_manager = thread_manager
    
    time_updates = []
    clock.time_updated.connect(lambda t: time_updates.append(t))
    
    clock.start()
    
    # Wait for multiple updates
    qtbot.wait(2500)
    
    # Should have at least 2 updates
    assert len(time_updates) >= 2
    
    clock.stop()
