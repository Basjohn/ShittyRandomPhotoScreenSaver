"""Settings retirement must resume wallpaper acquisition through existing owners."""
from types import SimpleNamespace
import threading

import pytest
from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer


class Tasks:
    def __init__(self):
        self.io = []
        self.timers = []

    def submit_io_task(self, task, **kwargs):
        self.io.append((task, kwargs))

    def schedule_recurring(self, interval, callback):
        timer = QTimer()
        timer.setInterval(interval)
        self.timers.append(timer)
        return timer


@pytest.fixture
def resumed(qt_app, tmp_path, monkeypatch):
    from core.settings.settings_manager import SettingsManager
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    import engine.screensaver_engine as module
    from sources.rss.coordinator import RSSCoordinator
    from sources.rss.pools import WallpaperPoolSelection, write_pool_selection

    folder = tmp_path / "pictures"
    folder.mkdir()
    Image.new("RGB", (32, 24), "red").save(folder / "local.png")
    settings = SettingsManager(application="RssResume", storage_base_dir=tmp_path / "settings")
    settings.set("sources.folders", [str(folder)])
    settings.set("sources.rss_feeds", [])
    write_pool_selection(settings, WallpaperPoolSelection(True, ("wallhaven.nature",), "latest"))
    monkeypatch.setattr(module, "RSSCoordinator", lambda **kwargs: RSSCoordinator(cache_dir=tmp_path / "rss", **kwargs))
    engine = ScreensaverEngine()
    engine._state = EngineState.STOPPED
    engine.settings_manager = settings
    engine.thread_manager = Tasks()
    assert engine._initialize_image_sources()
    assert engine.image_queue.next() is not None
    old = SimpleNamespace(coordinator=engine.rss_coordinator, queue=engine.image_queue,
                          cache=engine._image_cache, prefetcher=engine._prefetcher,
                          folders=tuple(engine.folder_sources), history=engine.image_queue.get_history())
    engine._start_rss_background_refresh_if_needed()
    engine._state = EngineState.RUNNING
    engine.stop(exit_app=False)
    assert old.coordinator.is_stopped
    assert engine._rss_refresh_timer is None
    assert engine._image_sources_waiting_for_display
    yield engine, old
    engine.rss_coordinator.request_stop() if engine.rss_coordinator else None
    if engine.display_manager:
        engine.display_manager.disconnect_monitor_detection()
    if engine._refresh_transition_gate:
        engine._refresh_transition_gate.close()
    for timer in engine.thread_manager.timers:
        timer.deleteLater()
    from core.diagnostics import lifecycle_window
    lifecycle_window.close_window()
    engine._state = EngineState.SHUTTING_DOWN
    engine._end_replacement_watchdog("test_cleanup")


def _close_settings(engine, monkeypatch, *, changed=False):
    from engine import engine_handlers
    # Keep real post-dialog continuation and positive-display admission; no GL
    # window or product worker is needed to falsify source re-admission.
    from engine.display_manager import DisplayManager
    monkeypatch.setattr(DisplayManager, "initialize_displays", lambda self: 1)
    monkeypatch.setattr(engine, "_setup_rotation_timer", lambda: None)
    monkeypatch.setattr(engine, "start", lambda **kwargs: True)
    engine_handlers._restart_after_settings_dialog_destroyed(engine, 0, 0, changed)


def test_unchanged_settings_replace_terminal_source_and_resume_one_cadence_without_losing_playback(resumed, monkeypatch):
    engine, old = resumed
    _close_settings(engine, monkeypatch)
    assert engine.rss_coordinator is not old.coordinator
    assert not engine.rss_coordinator.is_stopped and old.coordinator.is_stopped
    assert engine.image_queue is old.queue
    assert engine.image_queue.get_history() == old.history
    assert engine._image_cache is old.cache and engine._prefetcher is old.prefetcher
    assert tuple(engine.folder_sources) == old.folders
    assert engine._rss_refresh_timer is not None
    assert len(engine.thread_manager.io) == 2  # old startup + new generation startup
    timer = engine._rss_refresh_timer
    engine._start_rss_background_refresh_if_needed()
    assert engine._rss_refresh_timer is timer


def test_changed_pools_and_folders_reach_replacement_through_existing_rebuild(resumed, tmp_path, monkeypatch):
    from sources.rss.pools import WallpaperPoolSelection, write_pool_selection
    from engine import engine_handlers
    engine, old = resumed
    folder = tmp_path / "new_pictures"
    folder.mkdir()
    Image.new("RGB", (32, 24), "blue").save(folder / "new.png")
    engine.settings_manager.set("sources.folders", [str(folder)])
    write_pool_selection(engine.settings_manager, WallpaperPoolSelection(True, ("nasa.space",), "popular"))
    engine._settings_dialog_active = True
    engine_handlers.on_sources_changed(engine)
    events = []
    invalidate = old.prefetcher.clear_inflight
    clear = old.cache.clear
    monkeypatch.setattr(old.prefetcher, "clear_inflight", lambda: (events.append("invalidate"), invalidate())[1])
    monkeypatch.setattr(old.cache, "clear", lambda: (events.append("clear"), clear())[1])
    _close_settings(engine, monkeypatch, changed=True)
    assert events[:2] == ["invalidate", "clear"]
    assert engine.rss_coordinator._pool_selection.active_ids == ("nasa.space",)
    assert engine.rss_coordinator._pool_selection.discovery_order == "popular"
    assert [meta.local_path.name for meta in engine.image_queue.get_all_images()] == ["new.png"]
    assert engine.image_queue is not old.queue
    assert not engine._sources_changed_during_settings
    assert len(engine.folder_sources) == 1


def test_zero_display_defers_changed_sources_until_actual_positive_admission(resumed, monkeypatch):
    from engine import engine_handlers
    from engine.display_manager import DisplayManager
    from sources.rss.pools import WallpaperPoolSelection, write_pool_selection
    engine, old = resumed
    engine.settings_manager.set("display.show_on_monitors", "NONE")
    write_pool_selection(engine.settings_manager, WallpaperPoolSelection(True, ("nasa.space",), "latest"))
    engine._sources_changed_during_settings = True
    monkeypatch.setattr(engine, "_setup_rotation_timer", lambda: None)
    monkeypatch.setattr(engine, "start", lambda **kwargs: True)
    engine_handlers._restart_after_settings_dialog_destroyed(engine, 0, 0, True)
    assert engine.rss_coordinator is old.coordinator
    assert engine.image_queue is old.queue
    assert len(engine.thread_manager.io) == 1
    assert engine._rss_refresh_timer is None
    assert engine._image_sources_waiting_for_display and engine._sources_changed_during_settings
    engine.display_manager.disconnect_monitor_detection()
    engine._refresh_transition_gate.close()
    engine.settings_manager.set("display.show_on_monitors", "ALL")
    monkeypatch.setattr(DisplayManager, "initialize_displays", lambda self: 1)
    assert engine._initialize_display()
    assert engine.rss_coordinator._pool_selection.active_ids == ("nasa.space",)
    assert engine._rss_refresh_timer is not None
    assert not engine._sources_changed_during_settings


@pytest.mark.parametrize("invalidate", ["stop", "generation", "coordinator", "queue"])
def test_late_background_work_cannot_publish_to_resumed_sources(resumed, monkeypatch, invalidate):
    from engine import engine_rss
    from engine.screensaver_engine import EngineState
    engine, old = resumed
    engine._initialize_image_sources()
    engine._state = EngineState.RUNNING
    coordinator = engine.rss_coordinator
    monkeypatch.setattr(coordinator, "refresh_next_sources", lambda: [object()])
    published = []
    monkeypatch.setattr(engine_rss, "merge_rss_images_from_refresh", lambda *args: published.append(args))
    engine._background_refresh_rss()
    task, _ = engine.thread_manager.io[-1]
    assert task._srpss_runtime_generation == engine._runtime_generation
    if invalidate == "stop":
        coordinator.request_stop()
    elif invalidate == "generation":
        engine._runtime_generation += 1
    elif invalidate == "coordinator":
        engine.rss_coordinator = None
    else:
        engine.image_queue = None
    task()
    assert not published


def test_rss_startup_work_is_visible_to_real_retirement_barrier(qt_app, tmp_path, monkeypatch):
    from core.threading.manager import ThreadManager
    from engine.runtime_destruction import RuntimeDestructionBarrier
    from sources.rss.coordinator import RSSCoordinator
    manager = ThreadManager()
    engine = SimpleNamespace(thread_manager=manager, resource_manager=None, _terminal_shutdown_requested=False)
    coordinator = RSSCoordinator(feed_urls=[], cache_dir=tmp_path, thread_manager=manager)
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    def held(**kwargs):
        entered.set()
        assert release.wait(3)
        return []
    monkeypatch.setattr(coordinator, "load_sync", held)
    try:
        coordinator.load_async(runtime_generation=711, on_images=lambda _: done.set())
        assert entered.wait(1)
        barrier = RuntimeDestructionBarrier(engine, reason="settings", retiring_generation=711)
        assert barrier._remaining_thread_work()
        engine._pending_runtime_destruction_barrier = barrier
        loop = QEventLoop()
        continued = []
        barrier.then(lambda: (continued.append(done.is_set()), loop.quit()))
        barrier.seal()
        assert not barrier.is_complete
        QTimer.singleShot(50, release.set)
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        deadline.start(2000)
        loop.exec()
        deadline.stop()
        assert continued == [True], "source replacement must follow the complete tracked IO publication"
        assert barrier.is_complete
    finally:
        release.set()
        coordinator.request_stop()
        manager.shutdown()
