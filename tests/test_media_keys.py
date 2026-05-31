
import pytest
from unittest.mock import MagicMock
from types import SimpleNamespace
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from rendering.display_widget import DisplayWidget
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


def test_space_key_routes_play_pause_signal(input_handler):
    """Verify Space is treated as a focused play/pause hotkey."""
    event = create_key_event(Qt.Key.Key_Space)

    mock_slot = MagicMock()
    input_handler.play_pause_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "Space should be handled as a hotkey"
    mock_slot.assert_called_once()


def test_left_key_routes_previous_track_signal(input_handler):
    event = create_key_event(Qt.Key.Key_Left)

    mock_slot = MagicMock()
    input_handler.previous_track_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "Left should be handled as a focused transport hotkey"
    mock_slot.assert_called_once()


def test_right_key_routes_next_track_signal(input_handler):
    event = create_key_event(Qt.Key.Key_Right)

    mock_slot = MagicMock()
    input_handler.next_track_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "Right should be handled as a focused transport hotkey"
    mock_slot.assert_called_once()


def test_up_key_routes_slider_volume_up_signal(input_handler):
    event = create_key_event(Qt.Key.Key_Up)

    mock_slot = MagicMock()
    input_handler.slider_volume_up_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "Up should be handled as a focused slider-volume hotkey"
    mock_slot.assert_called_once()


def test_down_key_routes_slider_volume_down_signal(input_handler):
    event = create_key_event(Qt.Key.Key_Down)

    mock_slot = MagicMock()
    input_handler.slider_volume_down_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "Down should be handled as a focused slider-volume hotkey"
    mock_slot.assert_called_once()


def test_pageup_key_routes_global_volume_up_signal(input_handler):
    event = create_key_event(Qt.Key.Key_PageUp)

    mock_slot = MagicMock()
    input_handler.global_volume_up_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "Page Up should be handled as a focused global-volume hotkey"
    mock_slot.assert_called_once()


def test_pagedown_key_routes_global_volume_down_signal(input_handler):
    event = create_key_event(Qt.Key.Key_PageDown)

    mock_slot = MagicMock()
    input_handler.global_volume_down_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "Page Down should be handled as a focused global-volume hotkey"
    mock_slot.assert_called_once()


def test_home_key_routes_play_pause_signal(input_handler):
    event = create_key_event(Qt.Key.Key_Home)

    mock_slot = MagicMock()
    input_handler.play_pause_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "Home should be handled as a focused play/pause hotkey"
    mock_slot.assert_called_once()


def test_end_key_routes_global_mute_toggle_signal(input_handler):
    event = create_key_event(Qt.Key.Key_End)

    mock_slot = MagicMock()
    input_handler.global_mute_toggle_requested.connect(mock_slot)

    result = input_handler.handle_key_press(event)
    assert result is True, "End should be handled as a focused global-mute hotkey"
    mock_slot.assert_called_once()


def test_display_widget_play_pause_hotkey_dispatches_media_feedback():
    media_widget = MagicMock()
    media_widget.handle_transport_command.return_value = True
    stub = MagicMock()
    stub._resolve_media_widget_for_transport.return_value = media_widget

    DisplayWidget._on_play_pause_requested(stub)

    media_widget.handle_transport_command.assert_called_once_with(
        "play",
        source="keyboard_space",
        execute=True,
    )


def test_display_widget_previous_track_hotkey_dispatches_media_feedback():
    media_widget = MagicMock()
    media_widget.handle_transport_command.return_value = True
    stub = MagicMock()
    stub._resolve_media_widget_for_transport.return_value = media_widget

    DisplayWidget._on_previous_track_requested(stub)

    media_widget.handle_transport_command.assert_called_once_with(
        "prev",
        source="keyboard_left",
        execute=True,
    )


def test_display_widget_next_track_hotkey_dispatches_media_feedback():
    media_widget = MagicMock()
    media_widget.handle_transport_command.return_value = True
    stub = MagicMock()
    stub._resolve_media_widget_for_transport.return_value = media_widget

    DisplayWidget._on_next_track_requested(stub)

    media_widget.handle_transport_command.assert_called_once_with(
        "next",
        source="keyboard_right",
        execute=True,
    )


def test_display_widget_slider_volume_up_hotkey_dispatches_volume_widget():
    volume_widget = MagicMock()
    volume_widget.handle_step.return_value = True
    stub = SimpleNamespace(_resolve_volume_widget_for_hotkeys=lambda: volume_widget)

    DisplayWidget._handle_slider_volume_step(stub, 1, source="keyboard_up")

    volume_widget.handle_step.assert_called_once_with(1)


def test_display_widget_slider_volume_down_hotkey_dispatches_volume_widget():
    volume_widget = MagicMock()
    volume_widget.handle_step.return_value = True
    stub = SimpleNamespace(_resolve_volume_widget_for_hotkeys=lambda: volume_widget)

    DisplayWidget._handle_slider_volume_step(stub, -1, source="keyboard_down")

    volume_widget.handle_step.assert_called_once_with(-1)


def test_display_widget_resolves_cross_display_volume_widget_for_hotkeys():
    remote_volume_widget = MagicMock()
    remote_display = SimpleNamespace(spotify_volume_widget=remote_volume_widget)
    stub = SimpleNamespace(
        spotify_volume_widget=None,
        _widget_manager=None,
        get_all_instances=lambda: [remote_display],
    )

    resolved = DisplayWidget._resolve_volume_widget_for_hotkeys(stub)

    assert resolved is remote_volume_widget


def test_display_widget_global_volume_up_hotkey_uses_system_audio(monkeypatch):
    refreshes = []
    stub = SimpleNamespace(_refresh_mute_button_after_system_audio_change=lambda: refreshes.append(True))
    monkeypatch.setattr("rendering.display_widget.system_mute.step_volume", lambda delta: 0.55)

    DisplayWidget._handle_global_volume_step(stub, 0.05, source="keyboard_pageup")

    assert refreshes == [True]


def test_display_widget_global_mute_hotkey_uses_mute_button_when_available():
    mute_button = MagicMock()
    mute_button.handle_click.return_value = True
    stub = SimpleNamespace(mute_button_widget=mute_button)

    DisplayWidget._on_global_mute_toggle_requested(stub)

    mute_button.handle_click.assert_called_once_with()

def test_native_virtual_key_recognition(input_handler):
    """Verify recognition via native virtual key codes (Windows)."""
    # VK_VOLUME_MUTE = 0xAD (173)
    # Pass 0 as Qt key to force native check
    event = create_key_event(0, native_virtual_key=0xAD)
    
    result = input_handler.handle_key_press(event)
    assert result is False, "Native Volume Mute should be ignored"

