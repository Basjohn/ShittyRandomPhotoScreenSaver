"""An absent physical selection owns topology observation, without a render runtime."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.diagnostics import hang_watchdog, lifecycle_window
from core.settings import SettingsManager
from engine.display_manager import DisplayManager
from engine.screensaver_engine import EngineState, ScreensaverEngine
from tests.test_qtquick_monitor_wake_reconcile import _Screen, _manager


def _unexpected(*args, **kwargs):
    pytest.fail("Inactive selection admitted render, provider or scheduled image work")


def test_empty_manager_allocates_nothing_and_observes_return(qt_app, monkeypatch):
    import engine.display_manager as module

    manager, app, scheduler = _manager(monkeypatch, [_Screen("A", 0)])
    monkeypatch.setattr(manager, "_get_allowed_screen_indices", lambda count: set())
    monkeypatch.setattr(module, "QuickSceneFactory", _unexpected)
    changes = []
    manager.monitors_changed.connect(changes.append)
    try:
        assert manager.initialize_displays() == 0
        assert manager.is_selection_suspended()
        assert manager._quick_scene_factory is None
        assert not manager.displays
        assert not scheduler.calls
        returned = _Screen("B", 1920)
        app.screens.append(returned)
        app.screenAdded.emit(returned)
        scheduler.run_next()
        assert changes == [2]
    finally:
        manager.disconnect_monitor_detection()


@pytest.mark.parametrize("empty_selection", [True, False])
def test_initialization_distinguishes_selection_from_window_failure(
    qt_app, tmp_path, monkeypatch, empty_selection,
):
    import engine.display_manager as module

    settings = SettingsManager(application="SelectionLifecycle", storage_base_dir=tmp_path)
    engine = ScreensaverEngine()
    engine.settings_manager = settings
    monkeypatch.setattr(DisplayManager, "_get_allowed_screen_indices",
                        lambda self, count: set() if empty_selection else {0})
    monkeypatch.setattr(module, "QuickSceneFactory", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(DisplayManager, "_create_display_for_screen", lambda *args, **kwargs: None)
    for name in ("_admit_quick_visualizer", "_prime_quick_startup_desktop_sources", "_prepare_quick_startup_reveal"):
        monkeypatch.setattr(DisplayManager, name, lambda *args: None)
    try:
        assert engine._initialize_display() is empty_selection
        assert engine._display_initialized is empty_selection
        assert engine.display_manager.is_selection_suspended() is empty_selection
    finally:
        engine.display_manager.disconnect_monitor_detection()
        engine.display_manager._quick_scene_factory = None
        engine._refresh_transition_gate.close()
        engine._state = EngineState.SHUTTING_DOWN


def test_suspended_engine_has_no_queue_retry_workers_or_watchdog(qt_app, monkeypatch):
    import engine.screensaver_engine as module

    engine = ScreensaverEngine()
    engine.display_manager = SimpleNamespace(is_selection_suspended=lambda: True)
    engine.image_queue = SimpleNamespace(next=_unexpected)
    engine.thread_manager = SimpleNamespace(schedule_recurring=_unexpected)
    engine._process_supervisor = SimpleNamespace(start=_unexpected)
    engine._state = EngineState.STOPPED
    engine._replacement_watchdog_label = "selection_test"
    hang_watchdog.arm("selection_test", timeout_s=20)
    lifecycle_window.open_window("selection_test")
    monkeypatch.setattr(module.ThreadManager, "single_shot", _unexpected)
    monkeypatch.setattr(engine, "_load_and_display_image_async", _unexpected)
    try:
        engine._setup_rotation_timer()
        engine._start_workers()
        engine._start_rss_background_refresh_if_needed()
        engine._background_refresh_rss()
        engine._schedule_startup_first_image_retry()
        engine._schedule_prefetch()
        assert engine.start()
        assert engine._show_next_image() is False
        assert engine._admit_monitor_replay_image(object()) is False
        assert engine.is_running()
        assert engine._rotation_timer is None
        assert engine._workers_waiting_for_display
        assert not engine._loading_in_progress
        assert hang_watchdog.armed_label() is None
        assert not lifecycle_window.is_open()
    finally:
        hang_watchdog.disarm()
        lifecycle_window.close_window()
        engine._state = EngineState.SHUTTING_DOWN


def test_cold_empty_selection_defers_sources_until_selected_return(qt_app, tmp_path, monkeypatch):
    settings = SettingsManager(application="DeferredSelection", storage_base_dir=tmp_path)
    settings.set("display.show_on_monitors", "NONE")
    engine = ScreensaverEngine()
    engine.settings_manager = settings
    monkeypatch.setattr(engine, "_initialize_core_systems", lambda: True)
    monkeypatch.setattr(engine, "_load_settings", lambda: True)
    initialized = []
    monkeypatch.setattr(engine, "_initialize_sources", lambda: initialized.append("sources") or True)
    monkeypatch.setattr(engine, "_build_image_queue", lambda: initialized.append("queue") or True)
    monkeypatch.setattr(engine, "_initialize_cache_prefetcher", lambda: initialized.append("cache"))
    try:
        assert engine.initialize()
        assert engine.start()
        assert initialized == []
        assert engine._image_sources_waiting_for_display
        old = engine.display_manager
        old.disconnect_monitor_detection()
        engine._refresh_transition_gate.close()
        settings.set("display.show_on_monitors", "ALL")
        # Production replacement initialization; avoid constructing real GL units.
        monkeypatch.setattr(DisplayManager, "initialize_displays", lambda manager: 1)
        assert engine._initialize_display()
        assert initialized == ["sources", "queue", "cache"]
        assert not engine._image_sources_waiting_for_display
    finally:
        if engine.display_manager:
            engine.display_manager.disconnect_monitor_detection()
        if engine._refresh_transition_gate:
            engine._refresh_transition_gate.close()
        lifecycle_window.close_window()
        engine._state = EngineState.SHUTTING_DOWN
