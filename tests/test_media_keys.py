
import pytest
from unittest.mock import MagicMock
from types import SimpleNamespace
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from rendering.display_widget import DisplayWidget
from rendering.input_handler import InputHandler
from rendering.media_command_ingress import reset_media_command_ingress_for_tests


@pytest.fixture(autouse=True)
def _reset_process_media_gate():
    reset_media_command_ingress_for_tests()
    yield
    reset_media_command_ingress_for_tests()

@pytest.fixture
def input_handler():
    """Create an InputHandler with a mock parent."""
    # We pass None as parent and inject a mock to satisfy QObject if needed
    handler = InputHandler(None)
    # The parent in InputHandler is stored in _parent
    handler._parent = MagicMock()
    return handler

def create_key_event(key, native_scan_code=0, native_virtual_key=0, modifiers=Qt.KeyboardModifier.NoModifier):
    """Create a mock QKeyEvent."""
    event = MagicMock(spec=QKeyEvent)
    event.key.return_value = key
    event.nativeScanCode.return_value = native_scan_code
    event.nativeVirtualKey.return_value = native_virtual_key
    event.text.return_value = ""
    event.modifiers.return_value = modifiers
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
    input_handler.home_play_pause_requested.connect(mock_slot)

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


def test_digit_key_routes_layout_slot_load_without_exit(input_handler):
    event = create_key_event(Qt.Key.Key_1)

    load_slot = MagicMock()
    exit_slot = MagicMock()
    input_handler.layout_slot_load_requested.connect(load_slot)
    input_handler.exit_requested.connect(exit_slot)

    result = input_handler.handle_key_press(event)

    assert result is True
    load_slot.assert_called_once_with("1")
    exit_slot.assert_not_called()


def test_shift_digit_routes_layout_slot_save_without_exit(input_handler):
    event = create_key_event(
        Qt.Key.Key_0,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )

    save_slot = MagicMock()
    exit_slot = MagicMock()
    input_handler.layout_slot_save_requested.connect(save_slot)
    input_handler.exit_requested.connect(exit_slot)

    result = input_handler.handle_key_press(event)

    assert result is True
    save_slot.assert_called_once_with("0")
    exit_slot.assert_not_called()


def test_shifted_number_symbol_routes_layout_slot_save(input_handler):
    event = create_key_event(
        Qt.Key.Key_Exclam,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )

    save_slot = MagicMock()
    input_handler.layout_slot_save_requested.connect(save_slot)

    result = input_handler.handle_key_press(event)

    assert result is True
    save_slot.assert_called_once_with("1")


def test_bare_shift_is_consumed_without_exit(input_handler):
    event = create_key_event(Qt.Key.Key_Shift)

    exit_slot = MagicMock()
    input_handler.exit_requested.connect(exit_slot)

    result = input_handler.handle_key_press(event)

    assert result is True
    exit_slot.assert_not_called()


def test_display_edit_mode_routes_digit_slots_before_key_swallow():
    event = create_key_event(Qt.Key.Key_2)
    event.accept = MagicMock()
    event.ignore = MagicMock()
    stub = SimpleNamespace(
        _custom_layout_edit_active=True,
        _load_layout_slot=MagicMock(return_value=True),
        _save_layout_slot=MagicMock(return_value=True),
    )
    stub._layout_slot_id_for_key_event = lambda event: DisplayWidget._layout_slot_id_for_key_event(stub, event)

    DisplayWidget.keyPressEvent(stub, event)

    stub._load_layout_slot.assert_called_once_with("2", commit_edit_session=True)
    stub._save_layout_slot.assert_not_called()
    event.accept.assert_called_once()
    event.ignore.assert_not_called()


def test_display_edit_mode_routes_shift_digit_save_before_key_swallow():
    event = create_key_event(
        Qt.Key.Key_3,
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )
    event.accept = MagicMock()
    event.ignore = MagicMock()
    stub = SimpleNamespace(
        _custom_layout_edit_active=True,
        _load_layout_slot=MagicMock(return_value=True),
        _save_layout_slot=MagicMock(return_value=True),
    )
    stub._layout_slot_id_for_key_event = lambda event: DisplayWidget._layout_slot_id_for_key_event(stub, event)

    DisplayWidget.keyPressEvent(stub, event)

    stub._save_layout_slot.assert_called_once_with("3", commit_edit_session=True)
    stub._load_layout_slot.assert_not_called()
    event.accept.assert_called_once()
    event.ignore.assert_not_called()


def test_display_widget_play_pause_hotkey_dispatches_media_feedback():
    media_widget = MagicMock()
    media_widget.handle_transport_command.return_value = True
    stub = SimpleNamespace(_resolve_media_widget_for_transport=lambda: media_widget)

    DisplayWidget._dispatch_play_pause_hotkey(stub, source="keyboard_space")

    media_widget.handle_transport_command.assert_called_once_with(
        "play",
        source="keyboard_space",
        execute=True,
    )


def test_display_widget_home_play_pause_hotkey_dispatches_guarded_media_feedback():
    media_widget = MagicMock()
    media_widget.handle_transport_command.return_value = True
    stub = SimpleNamespace(_resolve_media_widget_for_transport=lambda: media_widget)

    DisplayWidget._dispatch_play_pause_hotkey(stub, source="keyboard_home")

    media_widget.handle_transport_command.assert_called_once_with(
        "play",
        source="keyboard_home",
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


def test_display_widget_slider_volume_up_hotkey_dispatches_media_owner():
    media_owner = MagicMock()
    media_owner.request_app_volume_step.return_value = True
    stub = SimpleNamespace(_resolve_media_widget_for_transport=lambda: media_owner)

    DisplayWidget._handle_slider_volume_step(stub, 1, source="keyboard_up")

    media_owner.request_app_volume_step.assert_called_once_with(1)


def test_display_widget_slider_volume_down_hotkey_dispatches_media_owner():
    media_owner = MagicMock()
    media_owner.request_app_volume_step.return_value = True
    stub = SimpleNamespace(_resolve_media_widget_for_transport=lambda: media_owner)

    DisplayWidget._handle_slider_volume_step(stub, -1, source="keyboard_down")

    media_owner.request_app_volume_step.assert_called_once_with(-1)


def test_display_widget_global_volume_up_hotkey_uses_system_audio(monkeypatch):
    refreshes = []
    stub = SimpleNamespace(
        media_widget=None,
        _widget_manager=None,
        get_all_instances=lambda: [],
        _refresh_system_audio_state_after_direct_action=lambda: refreshes.append(True),
    )
    backend = SimpleNamespace(step_volume=lambda delta: 0.55)
    monkeypatch.setattr(
        "rendering.display_widget._load_system_audio_backend", lambda: backend
    )

    DisplayWidget._handle_global_volume_step(stub, 0.05, source="keyboard_pageup")

    assert refreshes == [True]


def test_display_widget_global_volume_uses_cross_display_shared_audio_owner():
    audio_owner = MagicMock()
    audio_owner.has_live_system_mute_runtime.return_value = True
    audio_owner.request_system_volume_step.return_value = 0.65
    remote_display = SimpleNamespace(media_widget=audio_owner, _widget_manager=None)
    stub = SimpleNamespace(
        media_widget=None,
        _widget_manager=None,
        get_all_instances=lambda: [remote_display],
    )

    DisplayWidget._handle_global_volume_step(stub, 0.05, source="keyboard_pageup")

    audio_owner.request_system_volume_step.assert_called_once_with(0.05)


def test_display_widget_global_volume_does_not_retry_after_owner_attempt(monkeypatch):
    audio_owner = MagicMock()
    audio_owner.has_live_system_mute_runtime.return_value = True
    audio_owner.request_system_volume_step.return_value = None
    backend_loader = MagicMock()
    monkeypatch.setattr(
        "rendering.display_widget._load_system_audio_backend", backend_loader
    )
    stub = SimpleNamespace(media_widget=audio_owner, _widget_manager=None, get_all_instances=lambda: [])

    DisplayWidget._handle_global_volume_step(stub, 0.05, source="keyboard_pageup")

    audio_owner.request_system_volume_step.assert_called_once_with(0.05)
    backend_loader.assert_not_called()


def test_display_widget_global_volume_skips_stale_local_for_live_remote(monkeypatch):
    stale_local = MagicMock()
    stale_local.has_live_system_mute_runtime.return_value = False
    live_remote = MagicMock()
    live_remote.has_live_system_mute_runtime.return_value = True
    live_remote.request_system_volume_step.return_value = 0.7
    backend_loader = MagicMock()
    monkeypatch.setattr(
        "rendering.display_widget._load_system_audio_backend", backend_loader
    )
    remote_display = SimpleNamespace(media_widget=live_remote, _widget_manager=None)
    stub = SimpleNamespace(
        media_widget=stale_local,
        _widget_manager=None,
        get_all_instances=lambda: [remote_display],
    )

    DisplayWidget._handle_global_volume_step(stub, 0.05, source="keyboard_pageup")

    stale_local.request_system_volume_step.assert_not_called()
    live_remote.request_system_volume_step.assert_called_once_with(0.05)
    backend_loader.assert_not_called()


def test_display_widget_global_mute_hotkey_uses_shared_owner_when_available():
    audio_owner = MagicMock()
    audio_owner.has_live_system_mute_runtime.return_value = True
    audio_owner.request_system_mute_toggle.return_value = True
    stub = SimpleNamespace(media_widget=audio_owner, _widget_manager=None, get_all_instances=lambda: [])

    DisplayWidget._on_global_mute_toggle_requested(stub)

    audio_owner.request_system_mute_toggle.assert_called_once_with()


def test_display_widget_global_mute_does_not_retry_after_owner_exception(monkeypatch):
    audio_owner = MagicMock()
    audio_owner.has_live_system_mute_runtime.return_value = True
    audio_owner.request_system_mute_toggle.side_effect = RuntimeError("post-toggle owner failure")
    backend_loader = MagicMock()
    monkeypatch.setattr(
        "rendering.display_widget._load_system_audio_backend", backend_loader
    )
    stub = SimpleNamespace(media_widget=audio_owner, _widget_manager=None, get_all_instances=lambda: [])

    DisplayWidget._on_global_mute_toggle_requested(stub)

    audio_owner.request_system_mute_toggle.assert_called_once_with()
    backend_loader.assert_not_called()


def test_display_widget_global_mute_skips_stale_local_for_live_remote(monkeypatch):
    stale_local = MagicMock()
    stale_local.has_live_system_mute_runtime.return_value = False
    live_remote = MagicMock()
    live_remote.has_live_system_mute_runtime.return_value = True
    live_remote.request_system_mute_toggle.return_value = True
    backend_loader = MagicMock()
    monkeypatch.setattr(
        "rendering.display_widget._load_system_audio_backend", backend_loader
    )
    remote_display = SimpleNamespace(media_widget=live_remote, _widget_manager=None)
    stub = SimpleNamespace(
        media_widget=stale_local,
        _widget_manager=None,
        get_all_instances=lambda: [remote_display],
    )

    DisplayWidget._on_global_mute_toggle_requested(stub)

    stale_local.request_system_mute_toggle.assert_not_called()
    live_remote.request_system_mute_toggle.assert_called_once_with()
    backend_loader.assert_not_called()

def test_native_virtual_key_recognition(input_handler):
    """Verify recognition via native virtual key codes (Windows)."""
    # VK_VOLUME_MUTE = 0xAD (173)
    # Pass 0 as Qt key to force native check
    event = create_key_event(0, native_virtual_key=0xAD)
    
    result = input_handler.handle_key_press(event)
    assert result is False, "Native Volume Mute should be ignored"

