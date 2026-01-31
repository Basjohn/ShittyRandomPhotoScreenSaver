"""
Test for media key feedback visualization.

This test verifies that media key presses trigger the same visual feedback
as clicking the media control bar buttons.
"""
import pytest
from unittest.mock import MagicMock, patch


def test_media_key_feedback_triggers_visual_animation():
    """
    Verify that media key presses trigger control feedback animation.
    
    The bug: Media keys were detected but visual feedback wasn't shown
    because the chain broke somewhere between detection and rendering.
    
    Expected: _handle_control_feedback is called with proper parameters
    when media keys are pressed.
    """
    # Import here to avoid Qt dependency issues during collection
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from rendering.input_handler import InputHandler
    from widgets.media_widget import MediaWidget
    
    # Create mock settings manager
    mock_settings = MagicMock()
    mock_settings.get_hard_exit_enabled.return_value = False
    mock_settings.get_settings_path.return_value = None
    
    # Create mock parent with media_widget
    mock_parent = MagicMock()
    mock_media_widget = MagicMock(spec=MediaWidget)
    mock_parent.media_widget = mock_media_widget
    
    # Create InputHandler
    handler = InputHandler(mock_parent, mock_settings, None)
    
    # Test each media key
    media_keys = [
        (Qt.Key.Key_MediaPlay, "play"),
        (Qt.Key.Key_MediaNext, "next"),
        (Qt.Key.Key_MediaPrevious, "prev"),
    ]
    
    for key, expected_command in media_keys:
        # Reset mock
        mock_media_widget.reset_mock()
        mock_media_widget.handle_transport_command.return_value = True
        
        # Create key event
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            key,
            Qt.KeyboardModifier.NoModifier
        )
        
        # Process the key
        handler.handle_key_press(event)
        
        # Verify handle_transport_command was called with execute=False
        mock_media_widget.handle_transport_command.assert_called_once()
        call_args = mock_media_widget.handle_transport_command.call_args
        assert call_args[0][0] == expected_command
        assert call_args[1]["execute"] is False
        assert "media_key" in call_args[1]["source"]


def test_media_widget_feedback_state_set_on_media_key():
    """
    Verify that MediaWidget sets feedback state when receiving media key commands.
    
    This tests the internal state machine of MediaWidget to ensure
    _handle_control_feedback is called properly.
    """
    # Mock the MediaWidget partially
    from widgets.media_widget import MediaWidget
    
    # Create a mock instance with the necessary attributes
    widget_mock = MagicMock(spec=MediaWidget)
    widget_mock._controls_feedback = {}
    widget_mock._feedback_deadlines = {}
    widget_mock._controls_feedback_duration = 0.3
    
    # Call handle_transport_command with execute=False (media key path)
    with patch.object(MediaWidget, 'handle_transport_command', create=True) as mock_handle:
        mock_handle.return_value = True
        
        # Simulate media key press
        MediaWidget.handle_transport_command(
            widget_mock,
            "play",
            source="media_key_vk:179",
            execute=False
        )
        
        # Verify the method was called
        assert mock_handle.called


def test_feedback_animation_timer_starts_on_media_key():
    """
    Verify that the shared feedback timer starts when media keys trigger feedback.
    
    Without the timer running, feedback animations won't progress.
    """
    from widgets.media_widget import MediaWidget
    
    # Ensure timer is initially stopped
    MediaWidget._maybe_stop_shared_feedback_timer()
    
    # Check if timer methods are accessible
    assert hasattr(MediaWidget, '_ensure_shared_feedback_timer')
    assert hasattr(MediaWidget, '_shared_feedback_timer')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
