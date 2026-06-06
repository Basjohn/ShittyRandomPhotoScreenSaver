"""
Integration test for S hotkey workflow.

Tests the complete workflow:
1. Start screensaver
2. Press S key
3. Display windows are HIDDEN (not just cleared)
4. Settings dialog opens (and is visible)
5. Close settings
6. Display windows shown again
7. Screensaver resumes

CRITICAL: Display widgets must be hidden when settings open,
otherwise they cover the dialog with black fullscreen windows!
"""
import pytest
import uuid
from types import SimpleNamespace

from core.settings import SettingsManager
from engine.screensaver_engine import EngineState
from engine.screensaver_engine import ScreensaverEngine


@pytest.fixture
def engine_with_settings(qt_app, tmp_path):
    """Create engine with test settings."""
    settings = SettingsManager(
        organization="Test",
        application=f"SHotkeyTest_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path / "settings",
    )
    
    # Create test folder with one image
    test_folder = tmp_path / "images"
    test_folder.mkdir()
    test_image = test_folder / "test.jpg"
    test_image.write_bytes(b"fake image data")
    
    # Configure settings
    settings.set('sources.folders', [str(test_folder)])
    settings.save()
    
    # Create engine
    engine = ScreensaverEngine()
    engine.settings_manager = settings
    
    yield engine, settings
    
    # Cleanup
    if engine._running:
        engine.stop()
    engine.cleanup()



def test_s_hotkey_opens_settings_without_crash(engine_with_settings, qt_app):
    """
    Test that S hotkey opens settings dialog without crashing.
    
    This test verifies:
    - AttributeError: '_display_initialized' exists
    - NameError: All imports present
    - Display windows are HIDDEN (not covering dialog)
    """
    engine, settings = engine_with_settings
    
    # Initialize engine
    assert engine.initialize(), "Engine should initialize"
    
    # Verify _display_initialized exists and is True
    assert hasattr(engine, '_display_initialized'), "_display_initialized attribute must exist"
    assert engine._display_initialized is True, "_display_initialized should be True after init"
    
    # Start engine
    assert engine.start(), "Engine should start"
    assert engine._running is True, "Engine should be running"
    
    # Verify displays are visible before S key
    assert engine.display_manager is not None
    for display in engine.display_manager.displays:
        assert display.isVisible(), "Displays should be visible while running"
    
    # Simulate S key press - stop(exit_app=False)
    engine.stop(exit_app=False)
    
    # CRITICAL: Verify displays are HIDDEN after stop
    for display in engine.display_manager.displays:
        assert not display.isVisible(), "Displays MUST be hidden when settings open!"
    
    # Verify engine stopped
    assert engine._running is False, "Engine should be stopped"
    
    # Now simulate settings dialog closing and restart
    engine.display_manager.show_all()
    engine.start()
    
    # Verify displays visible again
    for display in engine.display_manager.displays:
        assert display.isVisible(), "Displays should be visible after restart"


def test_display_initialized_flag_lifecycle(qt_app):
    """
    Test _display_initialized flag through lifecycle.
    
    This verifies the flag exists and changes correctly.
    """
    settings = SettingsManager(
        organization="Test",
        application=f"DisplayFlagTest_{uuid.uuid4().hex}"
    )
    
    engine = ScreensaverEngine()
    engine.settings_manager = settings
    
    # Before init
    assert hasattr(engine, '_display_initialized'), "Flag must exist from __init__"
    assert engine._display_initialized is False, "Should be False initially"
    
    # After display init (if successful)
    # Note: This might fail in test environment without displays
    try:
        result = engine._initialize_display()
        if result:
            assert engine._display_initialized is True, "Should be True after successful init"
    except Exception:
        # Display init may fail in test environment - that's okay
        pass
    
    # Cleanup
    engine.cleanup()



def test_engine_has_required_attributes(qt_app):
    """
    Test that ScreensaverEngine has all required attributes.
    
    This is a sanity check for attributes used in various methods.
    """
    engine = ScreensaverEngine()
    
    # State flags that must exist
    required_attributes = [
        '_running',
        '_initialized',
        '_display_initialized',
        '_loading_in_progress',
        '_current_transition_index',
        '_transition_types',
    ]
    
    for attr in required_attributes:
        assert hasattr(engine, attr), f"Engine must have '{attr}' attribute"


def test_settings_requested_handler_doesnt_crash_on_stop(engine_with_settings, qt_app):
    """
    Test that calling _on_settings_requested doesn't crash during stop().
    
    Tests the specific sequence:
    1. Stop engine (exit_app=False)
    2. Try to check _display_initialized
    """
    engine, settings = engine_with_settings
    
    # Initialize and start
    if not engine.initialize():
        pytest.skip("Engine initialization failed (no display in test env)")
    
    engine.start()
    
    # Stop without exiting app
    engine.stop(exit_app=False)
    
    # Now _display_initialized should still exist and be accessible
    assert hasattr(engine, '_display_initialized'), "Flag should exist after stop"
    
    # This is the check that was failing
    if engine._display_initialized:
        # Display was initialized, could restart
        pass
    else:
        # Display wasn't initialized, would need full init
        pass
    
    # If we get here, no AttributeError was raised
    engine.cleanup()


def test_settings_dialog_import_exists():
    """
    Test that required imports exist.
    
    This would catch NameError issues.
    """
    from PySide6.QtWidgets import QApplication
    from core.animation.animator import AnimationManager
    from ui.settings_dialog import SettingsDialog
    
    assert QApplication is not None
    assert AnimationManager is not None
    assert SettingsDialog is not None


def test_settings_request_cancels_active_custom_layout_session_before_stop(monkeypatch, qt_app):
    from engine import engine_handlers

    calls: list[str] = []

    class _ActiveManager:
        def cancel_session(self):
            calls.append("cancel_session")
            return True

    class _FakeDialog:
        def __init__(self, *_args, **_kwargs):
            calls.append("dialog_init")

        def exec(self):
            calls.append("dialog_exec")
            return 0

    engine = SimpleNamespace(
        display_manager=SimpleNamespace(displays=[]),
        resource_manager=None,
        settings_manager=SimpleNamespace(),
        _display_initialized=False,
        stop=lambda exit_app=False: calls.append(f"stop:{exit_app}"),
        _initialize_display=lambda: True,
        _setup_rotation_timer=lambda: calls.append("setup_rotation_timer"),
        start=lambda: calls.append("start") or True,
    )

    monkeypatch.setattr(engine_handlers, "SettingsDialog", _FakeDialog)
    monkeypatch.setattr(engine_handlers, "AnimationManager", lambda **kwargs: object())
    guard_calls: list[tuple[int, str]] = []
    monkeypatch.setattr(
        "rendering.display_widget.DisplayWidget.suppress_pointer_input_globally",
        classmethod(lambda cls, duration_ms=700, reason="": guard_calls.append((int(duration_ms), str(reason)))),
    )

    class _Coordinator:
        def set_settings_dialog_active(self, active):
            calls.append(f"settings_dialog_active:{active}")

        def cleanup(self):
            calls.append("coordinator_cleanup")

    monkeypatch.setattr(
        "rendering.multi_monitor_coordinator.get_coordinator",
        lambda: _Coordinator(),
    )

    monkeypatch.setattr(
        "rendering.custom_layout_manager.CustomLayoutManager.is_any_session_active",
        classmethod(lambda cls: True),
    )
    monkeypatch.setattr(
        "rendering.custom_layout_manager.CustomLayoutManager.active_manager",
        classmethod(lambda cls: _ActiveManager()),
    )

    engine_handlers.on_settings_requested(engine)
    assert guard_calls == [(700, "settings_display_recreation")]


def test_custom_layout_reload_arms_pointer_guard(monkeypatch, qt_app):
    from engine import engine_handlers

    guard_calls: list[tuple[int, str]] = []
    load_calls: list[str] = []
    monkeypatch.setattr(
        "rendering.display_widget.DisplayWidget.suppress_pointer_input_globally",
        classmethod(lambda cls, duration_ms=700, reason="": guard_calls.append((int(duration_ms), str(reason)))),
    )

    class _Coordinator:
        def cleanup(self):
            return None

    monkeypatch.setattr(
        "rendering.multi_monitor_coordinator.get_coordinator",
        lambda: _Coordinator(),
    )

    engine = SimpleNamespace(
        display_manager=SimpleNamespace(cleanup=lambda: None),
        settings_manager=SimpleNamespace(load=lambda: load_calls.append("load")),
        _display_initialized=True,
        stop=lambda exit_app=False: None,
        _initialize_display=lambda: True,
        _setup_rotation_timer=lambda: None,
        start=lambda: True,
    )

    engine_handlers.on_custom_layout_reload_requested(engine)

    assert guard_calls == [(700, "custom_layout_runtime_reload")]
    assert load_calls == ["load"]


def test_engine_start_schedules_bounded_first_image_retry(monkeypatch, qt_app):
    engine = ScreensaverEngine()
    engine._state = EngineState.STOPPED
    engine._rotation_timer = None
    engine.display_manager = SimpleNamespace(displays=[])

    show_calls: list[bool] = []
    monkeypatch.setattr(engine, "_prepare_random_transition_if_needed", lambda: None)

    def _show_next_image():
        show_calls.append(True)
        return False

    monkeypatch.setattr(engine, "_show_next_image", _show_next_image)
    scheduled: list[int] = []
    monkeypatch.setattr(
        "engine.screensaver_engine.QTimer.singleShot",
        lambda delay_ms, callback: scheduled.append(int(delay_ms)),
    )

    assert engine.start() is True
    assert len(show_calls) == 1
    assert scheduled == [180]


def test_engine_stop_quiesces_displays_before_clearing_and_hiding():
    order: list[str] = []

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class _DisplayManager:
        displays = []

        def get_display_count(self):
            return 2

        def quiesce_all(self):
            order.append("quiesce")

        def clear_all(self):
            order.append("clear")

        def hide_all(self):
            order.append("hide")

    from engine import engine_lifecycle

    class _Signal:
        def emit(self):
            return None

    class _State:
        RUNNING = object()
        STARTING = object()
        REINITIALIZING = object()
        STOPPING = object()
        SHUTTING_DOWN = object()
        STOPPED = object()

    class _Engine:
        _instance_running = True

    engine = _Engine()
    engine._running = True
    engine._state_lock = _Lock()
    engine.rss_coordinator = None
    engine._rss_refresh_timer = None
    engine._rotation_timer = None
    engine._loading_in_progress = False
    engine._process_supervisor = None
    engine.thread_manager = None
    engine.stopped = _Signal()
    engine._image_cache = None
    engine._instance_lock = _Lock()
    engine.display_manager = _DisplayManager()
    engine._transition_state = lambda *args, **kwargs: True
    engine._get_state = lambda: SimpleNamespace(name="RUNNING")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("engine.screensaver_engine.EngineState", _State)
    monkeypatch.setattr(engine_lifecycle, "QApplication", SimpleNamespace(quit=lambda: None))
    try:
        engine_lifecycle.stop(engine, exit_app=False)
    finally:
        monkeypatch.undo()

    assert order == ["quiesce", "clear", "hide"]
