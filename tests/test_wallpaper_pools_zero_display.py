"""Configured online pools stay dormant when no live display can consume them."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("physical_screens_absent", [False, True])
def test_zero_live_displays_defer_real_source_startup_and_refresh(
    qt_app, tmp_path, monkeypatch, physical_screens_absent,
):
    from PySide6.QtGui import QGuiApplication
    from core.diagnostics import lifecycle_window
    from core.settings.settings_manager import SettingsManager
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    import engine.screensaver_engine as module
    from sources.rss.pools import WallpaperPoolSelection, write_pool_selection

    settings = SettingsManager(application="PoolZeroDisplay", storage_base_dir=tmp_path)
    settings.set("sources.rss_feeds", ["https://custom.invalid/feed"])
    write_pool_selection(settings, WallpaperPoolSelection(True, ("wallhaven.nature", "nasa.space"), "latest"))
    if physical_screens_absent:
        monkeypatch.setattr(QGuiApplication, "screens", staticmethod(lambda: []))
    settings.set("display.show_on_monitors", "ALL" if physical_screens_absent else "NONE")
    engine = ScreensaverEngine()
    engine.settings_manager = settings
    # Keep unrelated process/service setup outside this focused admission case.
    # The production initialize/display/start/source decision chain stays intact.
    monkeypatch.setattr(engine, "_initialize_core_systems", lambda: True)
    monkeypatch.setattr(engine, "_load_settings", lambda: True)
    def forbidden(*args, **kwargs):
        pytest.fail("Zero-display engine admitted wallpaper provider/queue work")
    monkeypatch.setattr(module, "RSSCoordinator", forbidden)
    monkeypatch.setattr(engine, "_build_image_queue", forbidden)
    monkeypatch.setattr(engine, "_initialize_cache_prefetcher", forbidden)
    try:
        assert engine.initialize()
        assert engine.start()
        engine._start_rss_background_refresh_if_needed()
        engine._background_refresh_rss()
        assert engine.display_manager.is_selection_suspended()
        assert engine._image_sources_waiting_for_display
        assert engine.rss_coordinator is None
        assert not engine.folder_sources
        assert engine.display_manager._quick_scene_factory is None
        assert not engine.display_manager.displays
    finally:
        if engine.display_manager:
            engine.display_manager.disconnect_monitor_detection()
        if engine._refresh_transition_gate:
            engine._refresh_transition_gate.close()
        lifecycle_window.close_window()
        engine._state = EngineState.SHUTTING_DOWN
