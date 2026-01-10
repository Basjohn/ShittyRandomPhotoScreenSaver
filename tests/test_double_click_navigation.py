import pytest
import sys
from unittest.mock import MagicMock, patch
from PySide6.QtGui import QMouseEvent

# Ensure project root is in path for running as script or via pytest
if __name__ == "__main__":
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    sys.exit(pytest.main(["-v", __file__]))

from rendering.input_handler import InputHandler

@pytest.fixture
def mock_desktop_services():
    with patch('rendering.input_handler.QDesktopServices') as mock:
        yield mock





def test_double_click_triggers_next_image():
    """Double click event should trigger next_image_requested signal."""
    handler = InputHandler(None)
    
    # Create a mock slot to verify signal emission
    mock_slot = MagicMock()
    handler.next_image_requested.connect(mock_slot)
    
    event = MagicMock(spec=QMouseEvent)
    handler.handle_mouse_double_click(event)
    
    # Verify signal was emitted
    mock_slot.assert_called_once()


def test_double_click_ignored_when_menu_active():
    """Double click should be ignored if context menu is active."""
    handler = InputHandler(None)
    handler.set_context_menu_active(True)
    
    mock_slot = MagicMock()
    handler.next_image_requested.connect(mock_slot)
    
    event = MagicMock(spec=QMouseEvent)
    handler.handle_mouse_double_click(event)
    
    # Verify signal was NOT emitted
    mock_slot.assert_not_called()
