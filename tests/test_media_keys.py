
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from rendering.input_handler import InputHandler

@pytest.fixture
def input_handler():
    """Create an InputHandler with a mock parent."""
    # We pass None as parent and inject a mock to satisfy QObject if needed
    handler = InputHandler(None)
    # The parent in InputHandler is stored in _parent
    handler._parent = MagicMock()
    return handler

def create_key_event(key, native_scan_code=0, native_virtual_key=0):
    """Create a mock QKeyEvent."""
    event = MagicMock(spec=QKeyEvent)
    event.key.return_value = key
    event.nativeScanCode.return_value = native_scan_code
    event.nativeVirtualKey.return_value = native_virtual_key
    event.text.return_value = ""
    return event

def test_media_keys_are_ignored_volume_up(input_handler):
    """Verify Volume Up key returns False (ignored)."""
    event = create_key_event(Qt.Key.Key_VolumeUp)
    # Mock _is_media_key to ensure we are testing the handler logic flow
    # But wait, we want to test _is_media_key too. 
    # Let's rely on the real _is_media_key implementation if possible.
    
    result = input_handler.handle_key_press(event)
    assert result is False, "Volume Up should be ignored"

def test_media_keys_are_ignored_volume_down(input_handler):
    """Verify Volume Down key returns False (ignored)."""
    event = create_key_event(Qt.Key.Key_VolumeDown)
    result = input_handler.handle_key_press(event)
    assert result is False, "Volume Down should be ignored"

def test_media_keys_are_ignored_mute(input_handler):
    """Verify Volume Mute key returns False (ignored)."""
    event = create_key_event(Qt.Key.Key_VolumeMute)
    result = input_handler.handle_key_press(event)
    assert result is False, "Volume Mute should be ignored"

def test_media_keys_are_ignored_play_pause(input_handler):
    """Verify Media Play/Pause key returns False (ignored)."""
    event = create_key_event(Qt.Key.Key_MediaTogglePlayPause)
    result = input_handler.handle_key_press(event)
    assert result is False, "Play/Pause should be ignored"

def test_standard_keys_are_handled(input_handler):
    """Verify a standard exit key (e.g. Esc) returns True (handled)."""
    event = create_key_event(Qt.Key.Key_Escape)
    
    # Connect a mock slot to exit_requested to verify it emits
    mock_slot = MagicMock()
    input_handler.exit_requested.connect(mock_slot)
    
    result = input_handler.handle_key_press(event)
    assert result is True, "Escape should be handled"
    mock_slot.assert_called_once()

def test_native_virtual_key_recognition(input_handler):
    """Verify recognition via native virtual key codes (Windows)."""
    # VK_VOLUME_MUTE = 0xAD (173)
    # Pass 0 as Qt key to force native check
    event = create_key_event(0, native_virtual_key=0xAD)

    result = input_handler.handle_key_press(event)
    assert result is False, "Native Volume Mute should be ignored"


class TestMediaKeyPassthrough:
    """Tests verifying media keys are passed through to OS (not consumed)."""

    def test_media_key_returns_false_for_passthrough(self, input_handler):
        """Verify media keys return False so DisplayWidget calls event.ignore()."""
        media_keys = [
            Qt.Key.Key_MediaPlay,
            Qt.Key.Key_MediaPause,
            Qt.Key.Key_MediaTogglePlayPause,
            Qt.Key.Key_MediaNext,
            Qt.Key.Key_MediaPrevious,
            Qt.Key.Key_VolumeUp,
            Qt.Key.Key_VolumeDown,
            Qt.Key.Key_VolumeMute,
        ]
        for key in media_keys:
            event = create_key_event(key)
            result = input_handler.handle_key_press(event)
            assert result is False, f"{key} should return False for OS passthrough"

    def test_media_key_does_not_trigger_exit(self, input_handler):
        """Verify media keys do not trigger exit_requested signal."""
        mock_slot = MagicMock()
        input_handler.exit_requested.connect(mock_slot)

        event = create_key_event(Qt.Key.Key_MediaTogglePlayPause)
        input_handler.handle_key_press(event)

        mock_slot.assert_not_called()

    def test_media_key_does_not_set_exiting_flag(self, input_handler):
        """Verify media keys do not set _exiting flag."""
        event = create_key_event(Qt.Key.Key_VolumeUp)
        input_handler.handle_key_press(event)

        assert input_handler._exiting is False
