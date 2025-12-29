"""Tests for pixel shift manager."""
import pytest
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import QPoint

from widgets.pixel_shift_manager import PixelShiftManager


@pytest.fixture
def pixel_shift_manager():
    """Create a PixelShiftManager for testing."""
    manager = PixelShiftManager()
    yield manager
    manager.cleanup()


def test_pixel_shift_manager_creation():
    """Test PixelShiftManager can be created."""
    manager = PixelShiftManager()
    assert manager is not None
    assert manager._enabled is False
    assert manager._offset_x == 0
    assert manager._offset_y == 0
    manager.cleanup()


def test_pixel_shift_max_drift_constant():
    """Test MAX_DRIFT is set correctly."""
    assert PixelShiftManager.MAX_DRIFT == 4


def test_pixel_shift_calculate_next_offset_from_center(pixel_shift_manager):
    """Test that first shift moves away from center."""
    manager = pixel_shift_manager
    manager._offset_x = 0
    manager._offset_y = 0
    
    # Run multiple times to check statistical behavior
    outward_count = 0
    for _ in range(100):
        manager._offset_x = 0
        manager._offset_y = 0
        new_x, new_y = manager._calculate_next_offset()
        # From center, any movement is outward
        if abs(new_x) + abs(new_y) > 0:
            outward_count += 1
    
    # Should mostly move outward from center (at least 70%)
    # Some staying in place is acceptable due to probability distribution
    assert outward_count >= 70, f"Expected mostly outward movement, got {outward_count}/100"


def test_pixel_shift_no_immediate_shift_back(pixel_shift_manager):
    """Test that pixel shift doesn't immediately shift back to center.
    
    This is the key bug fix - after moving away from center, the next
    shift should NOT immediately return to center.
    """
    manager = pixel_shift_manager
    
    # Start at (1, 0) - one step away from center
    immediate_returns = 0
    trials = 100
    
    for _ in range(trials):
        manager._offset_x = 1
        manager._offset_y = 0
        new_x, new_y = manager._calculate_next_offset()
        
        # Check if we immediately returned to center
        if new_x == 0 and new_y == 0:
            immediate_returns += 1
    
    # With the fix, immediate returns should be rare (< 10%)
    assert immediate_returns < 15, (
        f"Too many immediate returns to center: {immediate_returns}/{trials}. "
        "Pixel shift should bias toward continuing outward."
    )


def test_pixel_shift_respects_max_drift(pixel_shift_manager):
    """Test that pixel shift never exceeds MAX_DRIFT."""
    manager = pixel_shift_manager
    max_drift = PixelShiftManager.MAX_DRIFT
    
    # Start at max drift
    manager._offset_x = max_drift
    manager._offset_y = 0
    
    for _ in range(50):
        new_x, new_y = manager._calculate_next_offset()
        assert abs(new_x) <= max_drift, f"X offset {new_x} exceeds MAX_DRIFT {max_drift}"
        assert abs(new_y) <= max_drift, f"Y offset {new_y} exceeds MAX_DRIFT {max_drift}"
        manager._offset_x = new_x
        manager._offset_y = new_y


def test_pixel_shift_drifts_back_at_max(pixel_shift_manager):
    """Test that pixel shift drifts back toward center when at max drift."""
    manager = pixel_shift_manager
    max_drift = PixelShiftManager.MAX_DRIFT
    
    # Start at max drift corner
    manager._offset_x = max_drift
    manager._offset_y = max_drift
    
    # Should eventually drift back toward center
    moved_back = False
    for _ in range(20):
        new_x, new_y = manager._calculate_next_offset()
        if abs(new_x) < max_drift or abs(new_y) < max_drift:
            moved_back = True
            break
        manager._offset_x = new_x
        manager._offset_y = new_y
    
    assert moved_back, "Should drift back from max drift position"


def test_pixel_shift_outward_bias_statistics(pixel_shift_manager):
    """Test the statistical distribution of shift directions.
    
    When not at max drift, outward movement should be strongly preferred.
    """
    manager = pixel_shift_manager
    
    # Start at (2, 0) - halfway to max drift
    outward = 0
    neutral = 0
    inward = 0
    trials = 200
    
    for _ in range(trials):
        manager._offset_x = 2
        manager._offset_y = 0
        initial_dist = abs(manager._offset_x) + abs(manager._offset_y)
        
        new_x, new_y = manager._calculate_next_offset()
        new_dist = abs(new_x) + abs(new_y)
        
        if new_dist > initial_dist:
            outward += 1
        elif new_dist == initial_dist:
            neutral += 1
        else:
            inward += 1
    
    # Outward should be most common (around 80%)
    assert outward > neutral, f"Outward ({outward}) should exceed neutral ({neutral})"
    assert outward > inward, f"Outward ({outward}) should exceed inward ({inward})"
    # Inward should be rare (< 20%)
    assert inward < trials * 0.20, f"Inward ({inward}) should be < 20% of {trials}"


@pytest.mark.qt
def test_pixel_shift_widget_registration(qapp, pixel_shift_manager):
    """Test that widgets can be registered and unregistered."""
    manager = pixel_shift_manager
    
    widget = QLabel("Test")
    widget.move(100, 100)
    widget.show()
    
    manager.register_widget(widget)
    assert len(manager._widgets) == 1
    assert id(widget) in manager._original_positions
    
    orig_pos = manager._original_positions[id(widget)]
    assert orig_pos.x() == 100
    assert orig_pos.y() == 100
    
    manager.unregister_widget(widget)
    assert id(widget) not in manager._original_positions
    
    widget.deleteLater()


@pytest.mark.qt
def test_pixel_shift_applies_offset_to_widgets(qapp, pixel_shift_manager):
    """Test that offset is correctly applied to registered widgets."""
    manager = pixel_shift_manager
    
    widget = QLabel("Test")
    widget.move(100, 100)
    widget.show()
    
    manager.register_widget(widget)
    
    # Manually set offset and apply
    manager._offset_x = 2
    manager._offset_y = -1
    manager._apply_offset()
    
    # Widget should have moved by the offset
    assert widget.x() == 102, f"Expected x=102, got {widget.x()}"
    assert widget.y() == 99, f"Expected y=99, got {widget.y()}"
    
    widget.deleteLater()
