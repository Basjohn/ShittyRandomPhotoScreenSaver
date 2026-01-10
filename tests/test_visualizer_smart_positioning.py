
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from rendering.widget_manager import WidgetManager

# Mock Position Enum to match what might be used in the app
class MockPosition:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name

@pytest.fixture
def widget_manager():
    """Create a WidgetManager with a mock parent."""
    parent = MagicMock()
    # We mock pixel_shift_manager on parent to avoid errors in position_spotify_visualizer
    parent._pixel_shift_manager = MagicMock()
    manager = WidgetManager(parent)
    return manager

@pytest.fixture
def media_widget():
    """Create a mock MediaWidget."""
    widget = MagicMock(spec=QWidget)
    # Default geometry: 300x100 at 0,0
    widget.geometry.return_value = QRect(100, 100, 300, 100)
    widget.width.return_value = 300
    widget.height.return_value = 100
    # Simulate the _position attribute used in the manager
    widget._position = MockPosition("BOTTOM_LEFT") 
    return widget

@pytest.fixture
def vis_widget():
    """Create a mock SpotifyVisualizerWidget."""
    widget = MagicMock(spec=QWidget)
    widget.height.return_value = 50
    widget.minimumHeight.return_value = 50
    widget.geometry.return_value = QRect(0, 0, 300, 50)
    return widget

def test_visualizer_below_media_at_top_left(widget_manager, media_widget, vis_widget):
    """Visualizer should be BELOW media widget when media is at TOP_LEFT."""
    media_widget._position = MockPosition("TOP_LEFT")
    # Setup media geometry at top of screen
    media_widget.geometry.return_value = QRect(20, 20, 300, 100)
    
    # Check logic
    widget_manager.position_spotify_visualizer(vis_widget, media_widget, 1920, 1080)
    
    # We expect setGeometry to be called. 
    # Current logic: if place_above (default unless TOP_LEFT/RIGHT?), it goes above.
    # We want it to be BELOW for TOP anchors.
    # Logic in manager: place_above = position not in ("TOP_LEFT", "TOP_RIGHT")
    # So TOP_LEFT should result in place_above=False -> BELOW.
    
    args = vis_widget.setGeometry.call_args[0]
    x, y, w, h = args
    
    # Media bottom is at 20+100=120. Gap is 20. Expected Y = 140.
    assert y > 20, f"Visualizer Y ({y}) should be below Media Y (20)"
    assert y == 140, f"Expected Y=140 (120+20), got {y}"

def test_visualizer_below_media_at_top_center(widget_manager, media_widget, vis_widget):
    """Visualizer should be BELOW media widget when media is at TOP_CENTER."""
    media_widget._position = MockPosition("TOP_CENTER")
    # Setup media geometry at top center
    media_widget.geometry.return_value = QRect(810, 20, 300, 100)
    
    widget_manager.position_spotify_visualizer(vis_widget, media_widget, 1920, 1080)
    
    args = vis_widget.setGeometry.call_args[0]
    x, y, w, h = args
    
    # Logic bug verification: 
    # Current code: place_above = position not in ("TOP_LEFT", "TOP_RIGHT")
    # TOP_CENTER is not in that list, so place_above becomes True.
    # Above: Top (20) - Gap (20) - Height (50) = -50 (clamped to 0).
    # We WANT it below: 140.
    
    # If the bug exists, this assertion might fail or show it at 0.
    # We assert what we WANT:
    assert y > 20, f"Visualizer Y ({y}) should be below Media Y (20)"
    assert y == 140, f"Expected Y=140 (120+20), got {y}"

def test_visualizer_below_media_at_top_right(widget_manager, media_widget, vis_widget):
    """Visualizer should be BELOW media widget when media is at TOP_RIGHT."""
    media_widget._position = MockPosition("TOP_RIGHT")
    media_widget.geometry.return_value = QRect(1600, 20, 300, 100)
    
    widget_manager.position_spotify_visualizer(vis_widget, media_widget, 1920, 1080)
    
    args = vis_widget.setGeometry.call_args[0]
    x, y, w, h = args
    
    assert y > 20
    assert y == 140

def test_visualizer_above_media_at_bottom_left(widget_manager, media_widget, vis_widget):
    """Visualizer should be ABOVE media widget when media is at BOTTOM_LEFT."""
    media_widget._position = MockPosition("BOTTOM_LEFT")
    # Bottom of screen is 1080. Widget height 100. Top at 960.
    media_widget.geometry.return_value = QRect(20, 960, 300, 100)
    
    widget_manager.position_spotify_visualizer(vis_widget, media_widget, 1920, 1080)
    
    args = vis_widget.setGeometry.call_args[0]
    x, y, w, h = args
    
    # Media top 960. Gap 20. Vis height 50.
    # Expected Y = 960 - 20 - 50 = 890.
    # This expects "place_above" = True.
    assert y < 960
    assert y == 890

