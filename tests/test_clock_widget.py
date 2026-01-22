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


def test_analog_clock_visual_offset_calculation(qapp, parent_widget):
    """Test that analogue clock without background calculates visual offset correctly."""
    clock = ClockWidget(
        parent=parent_widget,
        position=ClockPosition.TOP_RIGHT,
    )
    clock.set_display_mode("analog")
    clock.set_show_background(False)
    clock.resize(200, 200)
    parent_widget.show()
    clock.show()
    
    # Visual offset should be non-zero for analogue mode without background
    offset_x, offset_y = clock._compute_analog_visual_offset()
    
    # The offset should be positive (visual content is inset from widget bounds)
    assert offset_x >= 0, "Visual X offset should be non-negative"
    assert offset_y >= 0, "Visual Y offset should be non-negative"
    
    # For a 200x200 widget, the offset should be reasonable (not larger than half the widget)
    assert offset_x < 100, f"Visual X offset {offset_x} too large for 200px widget"
    assert offset_y < 100, f"Visual Y offset {offset_y} too large for 200px widget"
    
    clock.cleanup()


def test_analog_clock_visual_offset_zero_with_background(qapp, parent_widget):
    """Test that analogue clock with background has zero visual offset."""
    clock = ClockWidget(
        parent=parent_widget,
        position=ClockPosition.TOP_RIGHT,
    )
    clock.set_display_mode("analog")
    clock.set_show_background(True)
    clock.resize(200, 200)
    parent_widget.show()
    clock.show()
    
    # Visual offset should be zero when background is shown
    offset_x, offset_y = clock._compute_analog_visual_offset()
    assert offset_x == 0, "Visual X offset should be 0 with background"
    assert offset_y == 0, "Visual Y offset should be 0 with background"
    
    clock.cleanup()


def test_digital_clock_visual_offset_zero(qapp, parent_widget):
    """Test that digital clock has zero visual offset."""
    clock = ClockWidget(
        parent=parent_widget,
        position=ClockPosition.TOP_RIGHT,
    )
    clock.set_display_mode("digital")
    clock.set_show_background(False)
    clock.resize(200, 50)
    parent_widget.show()
    clock.show()
    
    # Visual offset should be zero for digital mode
    offset_x, offset_y = clock._compute_analog_visual_offset()
    assert offset_x == 0, "Visual X offset should be 0 for digital mode"
    assert offset_y == 0, "Visual Y offset should be 0 for digital mode"
    
    clock.cleanup()


def test_analog_clock_margin_alignment(qapp, parent_widget):
    """Test that analogue clock without background aligns correctly with margin.
    
    When positioned at TOP_RIGHT with margin=20, the visual top of the clock
    (XII numeral) should be at y=20, not the widget bounds.
    """
    margin = 20
    clock = ClockWidget(
        parent=parent_widget,
        position=ClockPosition.TOP_RIGHT,
    )
    clock.set_display_mode("analog")
    clock.set_show_background(False)
    clock.set_margin(margin)
    clock.resize(200, 220)  # Extra height for timezone
    parent_widget.resize(800, 600)
    parent_widget.show()
    clock.show()
    
    # Force position update
    clock._update_position()
    
    # Get the visual offset
    offset_x, offset_y = clock._compute_analog_visual_offset()
    
    # The widget's y position should be margin - offset_y
    # so that the visual top is at margin
    expected_y = margin - offset_y
    actual_y = clock.y()
    
    assert actual_y == expected_y, (
        f"Clock y={actual_y} but expected {expected_y} "
        f"(margin={margin}, visual_offset_y={offset_y})"
    )
    
    clock.cleanup()


def test_analog_clock_without_numerals_visual_offset(qapp, parent_widget):
    """Test visual offset when numerals are hidden.
    
    Without numerals, the clock face is larger (no clearance needed),
    so the offset from widget edge to face edge is larger.
    With numerals, they extend beyond the face, so offset is smaller.
    """
    clock = ClockWidget(
        parent=parent_widget,
        position=ClockPosition.TOP_RIGHT,
    )
    clock.set_display_mode("analog")
    clock.set_show_background(False)
    clock.set_show_numerals(False)
    clock.resize(200, 200)
    parent_widget.show()
    clock.show()

    offset_x_no_numerals, offset_y_no_numerals = clock._compute_analog_visual_offset()
    
    # Without numerals, offset should be non-zero
    assert offset_x_no_numerals > 0, "Should have some X offset for clock face"
    assert offset_y_no_numerals > 0, "Should have some Y offset for clock face"
    
    # Now enable numerals and check offset is smaller (numerals closer to edge)
    clock.set_show_numerals(True)
    offset_x_with_numerals, offset_y_with_numerals = clock._compute_analog_visual_offset()
    
    # With numerals, offset should be smaller (numerals are closer to widget edge)
    assert offset_x_with_numerals < offset_x_no_numerals, "Numeral offset should be smaller in X"
    assert offset_y_with_numerals < offset_y_no_numerals, "Numeral offset should be smaller in Y"
    assert offset_x_with_numerals > 0, "Numeral offset should still be positive"
    assert offset_y_with_numerals > 0, "Numeral offset should still be positive"
    
    clock.cleanup()


def test_analog_clock_with_timezone_visual_offset(qapp, parent_widget):
    """Test visual offset with timezone enabled.
    
    Timezone takes space at bottom, affecting the adjusted rect and center position.
    This means the visual offset will be different with timezone enabled.
    """
    clock = ClockWidget(
        parent=parent_widget,
        position=ClockPosition.TOP_RIGHT,
    )
    clock.set_display_mode("analog")
    clock.set_show_background(False)
    clock.resize(200, 220)
    parent_widget.show()
    clock.show()

    # Get offset without timezone
    clock.set_show_timezone(False)
    offset_without_tz = clock._compute_analog_visual_offset()
    
    # Get offset with timezone
    clock.set_show_timezone(True)
    offset_with_tz = clock._compute_analog_visual_offset()
    
    # Both should produce valid offsets
    assert offset_without_tz[0] > 0 and offset_without_tz[1] > 0
    assert offset_with_tz[0] > 0 and offset_with_tz[1] > 0
    
    # Timezone affects bottom margin, which affects center calculation,
    # so offsets may differ slightly
    
    clock.cleanup()


def test_analog_clock_all_scenarios_have_valid_offset(qapp, parent_widget):
    """Test all combinations of settings produce valid offsets.
    
    Scenarios:
    1. With background (should be 0,0)
    2. Without background + with numerals
    3. Without background + without numerals
    4. With/without timezone (shouldn't affect offset)
    """
    clock = ClockWidget(
        parent=parent_widget,
        position=ClockPosition.TOP_RIGHT,
    )
    clock.set_display_mode("analog")
    clock.resize(200, 220)
    parent_widget.show()
    clock.show()

    # Scenario 1: With background
    clock.set_show_background(True)
    offset = clock._compute_analog_visual_offset()
    assert offset == (0, 0), "With background should have zero offset"
    
    # Scenario 2: Without background + with numerals
    clock.set_show_background(False)
    clock.set_show_numerals(True)
    offset = clock._compute_analog_visual_offset()
    assert offset[0] > 0 and offset[1] > 0, "Should have positive offset with numerals"
    
    # Scenario 3: Without background + without numerals
    clock.set_show_background(False)
    clock.set_show_numerals(False)
    offset = clock._compute_analog_visual_offset()
    assert offset[0] > 0 and offset[1] > 0, "Should have positive offset without numerals"
    
    # Scenario 4: Timezone variations produce valid offsets
    for show_numerals in [True, False]:
        clock.set_show_numerals(show_numerals)
        
        clock.set_show_timezone(False)
        offset_no_tz = clock._compute_analog_visual_offset()
        assert offset_no_tz[0] > 0 and offset_no_tz[1] > 0, (
            f"Should have valid offset without timezone (numerals={show_numerals})"
        )
        
        clock.set_show_timezone(True)
        offset_with_tz = clock._compute_analog_visual_offset()
        assert offset_with_tz[0] > 0 and offset_with_tz[1] > 0, (
            f"Should have valid offset with timezone (numerals={show_numerals})"
        )
    
    clock.cleanup()


def test_analog_mode_rendering(qapp, parent_widget):
    """Test analog clock mode rendering."""
    clock = ClockWidget(parent=parent_widget)
    clock.set_display_mode("analog")
    clock.resize(200, 200)
    parent_widget.show()
    clock.show()
    
    assert clock._display_mode == "analog"
    assert clock.width() > 0
    assert clock.height() > 0
    
    clock.cleanup()


def test_analog_mode_with_numerals(qapp, parent_widget):
    """Test analog clock with numerals."""
    clock = ClockWidget(parent=parent_widget)
    clock.set_display_mode("analog")
    clock.set_show_numerals(True)
    clock.resize(200, 200)
    parent_widget.show()
    clock.show()
    
    assert clock._show_numerals is True
    
    clock.cleanup()


def test_analog_mode_without_numerals(qapp, parent_widget):
    """Test analog clock without numerals."""
    clock = ClockWidget(parent=parent_widget)
    clock.set_display_mode("analog")
    clock.set_show_numerals(False)
    clock.resize(200, 200)
    parent_widget.show()
    clock.show()
    
    assert clock._show_numerals is False
    
    clock.cleanup()


def test_clock_shadow_settings(qapp, parent_widget):
    """Test clock shadow configuration."""
    clock = ClockWidget(parent=parent_widget)
    
    # BaseOverlayWidget exposes shadow config helpers instead of direct flags.
    assert clock is not None
    initial_config = clock.get_shadow_config()
    assert initial_config is None
    
    sample_config = {"enabled": True, "blur_radius": 12, "offset": [2, 2]}
    clock.set_shadow_config(sample_config)
    
    assert clock.get_shadow_config() == sample_config
    
    clock.cleanup()


def test_clock_font_family(qapp, parent_widget):
    """Test setting font family."""
    clock = ClockWidget(parent=parent_widget)
    
    clock.set_font_family("Arial")
    assert clock._font_family == "Arial"
    
    clock.set_font_family("Courier New")
    assert clock._font_family == "Courier New"
    
    clock.cleanup()


def test_clock_timezone_display(qapp, parent_widget):
    """Test timezone display."""
    clock = ClockWidget(parent=parent_widget)
    clock.set_display_mode("analog")
    
    # Enable timezone
    clock.set_show_timezone(True)
    assert clock._show_timezone is True
    
    # Disable timezone
    clock.set_show_timezone(False)
    assert clock._show_timezone is False
    
    clock.cleanup()


def test_clock_background_toggle(qapp, parent_widget):
    """Test background toggle."""
    clock = ClockWidget(parent=parent_widget)
    
    # Enable background
    clock.set_show_background(True)
    assert clock._show_background is True
    
    # Disable background
    clock.set_show_background(False)
    assert clock._show_background is False
    
    clock.cleanup()
