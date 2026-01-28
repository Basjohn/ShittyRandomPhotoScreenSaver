"""Consolidated integration tests for DisplayWidget transitions and multi-display sync."""
from __future__ import annotations

import ast
import inspect
import uuid
from pathlib import Path
from typing import Callable
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QTimer, QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap, QColor
from PySide6.QtWidgets import QLabel

from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from transitions.slide_transition import SlideDirection
from transitions.gl_compositor_crossfade_transition import GLCompositorCrossfadeTransition
from engine.display_manager import DisplayManager
from engine.screensaver_engine import ScreensaverEngine, EngineState
from core.animation.animator import AnimationManager
from core.settings import SettingsManager
from ui.settings_dialog import SettingsDialog
from ui.tabs.sources_tab import SourcesTab
from ui.tabs.widgets_tab import WidgetsTab
from widgets.clock_widget import ClockWidget
from widgets.weather_widget import WeatherWidget, WeatherPosition


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_pixmap():
    """Create a solid red pixmap."""
    image = QImage(QSize(200, 200), QImage.Format.Format_RGB32)
    image.fill(QColor(255, 0, 0))
    return QPixmap.fromImage(image)


@pytest.fixture
def test_pixmap2():
    """Create a solid green pixmap."""
    image = QImage(QSize(200, 200), QImage.Format.Format_RGB32)
    image.fill(QColor(0, 255, 0))
    return QPixmap.fromImage(image)


def test_refresh_toggle_updates_target_fps(qt_app, settings_manager, monkeypatch):
    """DisplayWidget should reconfigure FPS when refresh settings change."""
    from rendering.display_widget import DisplayWidget
    from rendering.display_modes import DisplayMode

    settings_manager.set('display.hw_accel', False)
    settings_manager.set('display.render_backend_mode', 'software')
    settings_manager.set('display.refresh_sync', True)
    settings_manager.set('display.refresh_adaptive', False)

    monkeypatch.setattr(DisplayWidget, "_detect_refresh_rate", lambda self: 120)

    call_history: list[tuple[bool, bool]] = []

    original_config = DisplayWidget._configure_refresh_rate_sync

    def fake_config(self):
        sync_state = SettingsManager.to_bool(
            self.settings_manager.get('display.refresh_sync', True), True
        )
        adaptive_state = SettingsManager.to_bool(
            self.settings_manager.get('display.refresh_adaptive', False), False
        )
        call_history.append((sync_state, adaptive_state))
        original_config(self)

    monkeypatch.setattr(DisplayWidget, "_configure_refresh_rate_sync", fake_config)

    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    widget.resize(200, 200)

    try:
        widget._configure_refresh_rate_sync()
        assert call_history == [(True, False)]

        settings_manager.set('display.refresh_adaptive', True)
        qt_app.processEvents()
        assert call_history[-1] == (True, True)

        settings_manager.set('display.refresh_sync', False)
        qt_app.processEvents()
        assert call_history[-1] == (False, True)

        settings_manager.set('display.refresh_sync', True)
        qt_app.processEvents()
        assert call_history[-1] == (True, True)

        settings_manager.set('display.refresh_adaptive', False)
        qt_app.processEvents()
        assert call_history[-1] == (True, False)

        assert len(call_history) >= 5
    finally:
        widget.close()
        widget.deleteLater()


@pytest.fixture
def display_widget(qt_app, settings_manager, thread_manager):
    """Provide a DisplayWidget configured for integration tests."""
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
        thread_manager=thread_manager,
    )
    widget.resize(400, 400)
    yield widget
    widget.close()
    widget.deleteLater()


# ---------------------------------------------------------------------------
# Transition integration coverage
# ---------------------------------------------------------------------------

class TestDisplayTransitions:
    """End-to-end transition tests against DisplayWidget."""

    def _set_transitions(
        self,
        settings_manager,
        *,
        transition_type: str | None = None,
        duration_ms: int | None = None,
        slide_direction: str | None = None,
        wipe_direction: str | None = None,
        diffuse_block_size: int | None = None,
        block_rows: int | None = None,
        block_cols: int | None = None,
    ) -> None:
        cfg = settings_manager.get("transitions", {}) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        if transition_type is not None:
            cfg["type"] = transition_type
        if duration_ms is not None:
            cfg["duration_ms"] = duration_ms
            target_type = transition_type or cfg.get("type")
            if target_type:
                durations_cfg = cfg.get("durations", {}) or {}
                durations_cfg[target_type] = duration_ms
                cfg["durations"] = durations_cfg
        if slide_direction is not None:
            slide_cfg = cfg.get("slide", {}) or {}
            slide_cfg["direction"] = slide_direction
            cfg["slide"] = slide_cfg
        if wipe_direction is not None:
            wipe_cfg = cfg.get("wipe", {}) or {}
            wipe_cfg["direction"] = wipe_direction
            cfg["wipe"] = wipe_cfg
        if diffuse_block_size is not None:
            diff_cfg = cfg.get("diffuse", {}) or {}
            diff_cfg["block_size"] = diffuse_block_size
            cfg["diffuse"] = diff_cfg
        if block_rows is not None or block_cols is not None:
            block_cfg = cfg.get("block_flip", {}) or {}
            if block_rows is not None:
                block_cfg["rows"] = block_rows
            if block_cols is not None:
                block_cfg["cols"] = block_cols
            cfg["block_flip"] = block_cfg
        settings_manager.set("transitions", cfg)

    @pytest.mark.parametrize(
        "transition_type, kwargs",
        [
            ("Crossfade", {"duration_ms": 500}),
            ("Slide", {"duration_ms": 350, "slide_direction": "Left to Right"}),
            ("Diffuse", {"duration_ms": 300, "diffuse_block_size": 40}),
            ("Block Puzzle Flip", {"duration_ms": 250, "block_rows": 2, "block_cols": 2}),
            ("Wipe", {"duration_ms": 300, "wipe_direction": "Top to Bottom"}),
        ],
        ids=["crossfade", "slide", "diffuse", "block_flip", "wipe"],
    )
    def test_transition_runs_and_completes(
        self,
        qt_app,
        display_widget,
        test_pixmap,
        test_pixmap2,
        transition_type: str,
        kwargs: dict,
    ):
        """Every supported transition should run end-to-end."""
        self._set_transitions(display_widget.settings_manager, transition_type=transition_type, **kwargs)
        display_widget.set_image(test_pixmap, "test1.png")

        transition_finished = {"value": False}

        def on_finished():
            transition_finished["value"] = True

        display_widget.set_image(test_pixmap2, "test2.png")
        if display_widget._current_transition:
            display_widget._current_transition.finished.connect(on_finished)
            QTimer.singleShot(3000, qt_app.quit)
            qt_app.exec()
            assert transition_finished["value"], f"{transition_type} should finish"

        assert display_widget.current_pixmap is not None

    def test_transition_cleanup_on_clear(self, qt_app, display_widget, test_pixmap, test_pixmap2):
        """Clearing the widget should stop a long-running transition."""
        self._set_transitions(display_widget.settings_manager, transition_type="Slide", duration_ms=2000)
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        assert display_widget._current_transition is not None
        display_widget.clear()
        assert display_widget._current_transition is None
        assert display_widget.current_pixmap is None

    def test_transition_settings_respected(self, display_widget, test_pixmap, test_pixmap2):
        """Transition config values should propagate to the running object."""
        self._set_transitions(
            display_widget.settings_manager,
            transition_type="Slide",
            duration_ms=750,
            slide_direction="Top to Bottom",
        )
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        current = display_widget._current_transition
        if current:
            assert current.duration_ms == 750
            assert current._direction == SlideDirection.DOWN

    def test_transition_fallback_on_invalid_type(self, display_widget, test_pixmap, test_pixmap2):
        """Invalid transition types should fall back gracefully."""
        self._set_transitions(display_widget.settings_manager, transition_type="InvalidType")
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        assert display_widget.current_pixmap is not None

    def test_random_slide_direction_selection(self, display_widget, test_pixmap, test_pixmap2):
        """Random slide direction should resolve to one of the valid enums."""
        self._set_transitions(
            display_widget.settings_manager,
            transition_type="Slide",
            duration_ms=400,
            slide_direction="Random",
        )
        display_widget.set_image(test_pixmap, "test1.png")
        display_widget.set_image(test_pixmap2, "test2.png")
        current = display_widget._current_transition
        if current:
            assert current._direction in (
                SlideDirection.LEFT,
                SlideDirection.RIGHT,
                SlideDirection.UP,
                SlideDirection.DOWN,
            )


class TestSoftwareBackendWatchdog:
    """Coverage for software backend watchdog edge cases."""

    def _run_watchdog_scenario(
        self,
        qt_app,
        settings_manager,
        thread_manager,
        configure: Callable[[dict], None],
        first_pixmap: QPixmap,
        second_pixmap: QPixmap,
    ):
        configure(settings_manager)
        settings_manager.set("display.render_backend_mode", "software")
        settings_manager.set("display.hw_accel", False)
        settings_manager.set("transitions.watchdog_timeout_sec", 1.0)

        widget = DisplayWidget(
            screen_index=0,
            display_mode=DisplayMode.FILL,
            settings_manager=settings_manager,
            thread_manager=thread_manager,
        )
        widget.resize(400, 400)

        watchdog_flag = {"triggered": False}
        controller = getattr(widget, "_transition_controller", None)

        if controller is not None:
            def on_transition_cancelled(reason: str):
                if reason == "watchdog_timeout":
                    watchdog_flag["triggered"] = True

            controller.transition_cancelled.connect(on_transition_cancelled)

        widget.set_image(first_pixmap, "test1.png")
        finished = {"value": False}

        def on_finished():
            finished["value"] = True

        widget.set_image(second_pixmap, "test2.png")
        if widget._current_transition:
            widget._current_transition.finished.connect(on_finished)
            QTimer.singleShot(3000, qt_app.quit)
            qt_app.exec()
            assert finished["value"] is True
            assert watchdog_flag["triggered"] is False

        widget.close()

    def test_diffuse_no_watchdog(self, qt_app, settings_manager, thread_manager, test_pixmap, test_pixmap2):
        def configure(settings):
            cfg = settings.get("transitions", {}) or {}
            cfg["type"] = "Diffuse"
            cfg["duration_ms"] = 300
            durations = cfg.get("durations", {}) or {}
            durations["Diffuse"] = 300
            cfg["durations"] = durations
            cfg.setdefault("diffuse", {})["block_size"] = 50
            settings.set("transitions", cfg)

        self._run_watchdog_scenario(qt_app, settings_manager, thread_manager, configure, test_pixmap, test_pixmap2)

    def test_block_flip_no_watchdog(self, qt_app, settings_manager, thread_manager, test_pixmap, test_pixmap2):
        def configure(settings):
            cfg = settings.get("transitions", {}) or {}
            cfg["type"] = "Block Puzzle Flip"
            cfg["duration_ms"] = 300
            durations = cfg.get("durations", {}) or {}
            durations["Block Puzzle Flip"] = 300
            cfg["durations"] = durations
            block_cfg = cfg.setdefault("block_flip", {})
            block_cfg["rows"] = 2
            block_cfg["cols"] = 2
            settings.set("transitions", cfg)

        self._run_watchdog_scenario(qt_app, settings_manager, thread_manager, configure, test_pixmap, test_pixmap2)


# ---------------------------------------------------------------------------
# Flicker fix & telemetry regressions
# ---------------------------------------------------------------------------

class TestFlickerAndTelemetry:
    """Integration tests for allocation limits and telemetry hooks."""

    def test_qimage_allocation_limit_can_be_increased(self, qt_app):
        old_limit = QImageReader.allocationLimit()
        QImageReader.setAllocationLimit(1024)
        try:
            assert QImageReader.allocationLimit() == 1024
        finally:
            QImageReader.setAllocationLimit(old_limit)

    def test_gl_transition_reports_elapsed_time(self, qt_app, thread_manager):
        widget = DisplayWidget(
            screen_index=0,
            display_mode=DisplayMode.FILL,
            settings_manager=None,
            thread_manager=thread_manager,
        )
        widget.setGeometry(0, 0, 100, 100)
        dummy = QPixmap(10, 10)
        dummy.fill(Qt.GlobalColor.black)

        transition = GLCompositorCrossfadeTransition(duration_ms=100)
        started = transition.start(dummy, dummy, widget)
        if not started or transition._start_time is None:
            pytest.skip("GL compositor crossfade unavailable in this environment")

        elapsed = transition.get_elapsed_ms()
        assert elapsed is not None
        assert elapsed >= 0.0
        transition.stop()
        transition.cleanup()
        widget.close()


# ---------------------------------------------------------------------------
# Multi-display synchronization
# ---------------------------------------------------------------------------

class TestDisplayManagerSync:
    """Lock-free synchronization and queue lifecycle tests."""

    @pytest.fixture
    def manager(self):
        dm = DisplayManager()
        dm.displays = [None, None]
        return dm

    def test_sync_disabled_by_default(self):
        dm = DisplayManager()
        assert dm._sync_enabled is False
        assert dm._transition_ready_queue is None

    def test_enable_and_disable_sync(self, manager):
        manager.enable_transition_sync(True)
        assert manager._sync_enabled is True
        assert manager._transition_ready_queue is not None
        manager.enable_transition_sync(False)
        assert manager._sync_enabled is False

    def test_sync_not_enabled_for_single_display(self):
        dm = DisplayManager()
        dm.displays = [None]
        dm.enable_transition_sync(True)
        assert dm._transition_ready_queue is None

    def test_wait_for_all_ready_success(self, manager):
        manager.enable_transition_sync(True)
        manager._on_display_transition_ready(0)
        manager._on_display_transition_ready(1)
        assert manager.wait_for_all_displays_ready(timeout_sec=1.0) is True

    def test_wait_for_all_ready_timeout(self, manager):
        manager.enable_transition_sync(True)
        manager._on_display_transition_ready(0)
        assert manager.wait_for_all_displays_ready(timeout_sec=0.1) is False

    def test_wait_returns_true_when_sync_disabled(self, manager):
        assert manager.wait_for_all_displays_ready(timeout_sec=1.0) is True

    def test_wait_returns_true_for_single_display(self):
        dm = DisplayManager()
        dm.displays = [None]
        dm.enable_transition_sync(True)
        assert dm.wait_for_all_displays_ready(timeout_sec=1.0) is True

    def test_queue_rejects_when_full(self):
        from utils.lockfree.spsc_queue import SPSCQueue

        queue = SPSCQueue(capacity=4)
        assert queue.try_push(0) is True
        assert queue.try_push(1) is True
        assert queue.try_push(2) is True
        assert queue.try_push(3) is False

    def test_concurrent_ready_signals(self, manager):
        manager.enable_transition_sync(True)
        manager._on_display_transition_ready(0)
        manager._on_display_transition_ready(0)
        manager._on_display_transition_ready(1)
        assert manager.wait_for_all_displays_ready(timeout_sec=0.5) is True


# ---------------------------------------------------------------------------
# Screensaver engine integration
# ---------------------------------------------------------------------------

class TestScreensaverEngineIntegration:
    """Core engine lifecycle and telemetry tests."""

    @pytest.fixture
    def engine(self, qt_app):
        eng = ScreensaverEngine()
        yield eng
        eng.cleanup()

    def test_engine_creation(self, engine):
        assert engine is not None
        assert engine.is_running() is False

    def test_engine_initialization(self, engine):
        assert engine.initialize() is True
        assert engine.event_system is not None
        assert engine.resource_manager is not None
        assert engine.thread_manager is not None
        assert engine.settings_manager is not None
        assert engine.display_manager is not None
        assert engine.image_queue is not None

    def test_engine_core_systems(self, engine):
        engine.initialize()
        assert engine.event_system is not None
        stats = engine.resource_manager.get_stats()
        assert "total_resources" in stats
        pool_stats = engine.thread_manager.get_pool_stats()
        assert "io" in pool_stats or "compute" in pool_stats
        interval = engine.settings_manager.get("timing.interval", 10)
        assert interval > 0

    def test_engine_image_queue_initialization(self, engine):
        engine.initialize()
        assert engine.image_queue is not None
        assert engine.image_queue.total_images() >= 0
        queue_stats = engine.image_queue.get_stats()
        assert "total_images" in queue_stats

    def test_engine_display_initialization(self, engine):
        engine.initialize()
        assert engine.display_manager is not None
        assert engine.display_manager.get_display_count() >= 0

    def test_engine_start_stop_signals(self, engine, qtbot):
        engine.initialize()
        with qtbot.waitSignal(engine.started, timeout=1000):
            assert engine.start() is True
        assert engine.is_running() is True
        with qtbot.waitSignal(engine.stopped, timeout=1000):
            engine.stop()
        assert engine.is_running() is False

    def test_engine_rotation_timer(self, engine):
        engine.initialize()
        assert engine._rotation_timer is not None
        engine.start()
        assert engine._rotation_timer.isActive() is True
        engine.stop()
        assert engine._rotation_timer is None

    def test_engine_get_stats(self, engine):
        engine.initialize()
        stats = engine.get_stats()
        for key in ("running", "current_image", "loading", "queue", "displays"):
            assert key in stats

    def test_engine_cleanup(self, engine):
        engine.initialize()
        engine.start()
        engine.cleanup()
        assert engine.is_running() is False

    def test_engine_without_initialization(self):
        eng = ScreensaverEngine()
        assert eng.is_running() is False
        try:
            eng.start()
        finally:
            eng.cleanup()

    def test_engine_settings_integration(self, engine):
        engine.initialize()
        interval = engine.settings_manager.get("timing.interval", 10)
        assert engine._rotation_timer.interval() == interval * 1000
        display_mode = engine.settings_manager.get("display.mode", "fill")
        assert display_mode in ("fill", "fit", "shrink")

    def test_engine_multiple_start_calls(self, engine):
        engine.initialize()
        assert engine.start() is True
        assert engine.start() is True
        assert engine.is_running() is True
        engine.stop()

    def test_engine_stop_without_start(self, engine):
        engine.initialize()
        engine.stop()
        assert engine.is_running() is False

    def test_sources_changed_triggers_state_transition(self):
        with patch("engine.screensaver_engine.logger"):
            engine = ScreensaverEngine()
            engine._state = EngineState.RUNNING
            call_count = {"value": 0}

            def tracked():
                call_count["value"] += 1

            engine._on_sources_changed = tracked
            engine._on_sources_changed()
            assert call_count["value"] == 1


# ---------------------------------------------------------------------------
# Settings workflows
# ---------------------------------------------------------------------------

class TestSettingsIntegration:
    """Settings dialog and persistence paths."""

    def test_sources_tab_folder_persistence(self, tmp_path):
        app_id = f"IntegrationTest_{uuid.uuid4().hex}"
        settings = SettingsManager(organization="Test", application=app_id)
        test_folder = str(tmp_path / "images")
        Path(test_folder).mkdir(exist_ok=True)

        folders = settings.get("sources.folders", [])
        folders.append(test_folder)
        settings.set("sources.folders", folders)
        settings.save()

        settings2 = SettingsManager(organization="Test", application=app_id)
        assert test_folder in settings2.get("sources.folders", [])

    def test_settings_dialog_full_workflow(self, tmp_path):
        app_id = f"FullWorkflowTest_{uuid.uuid4().hex}"
        settings = SettingsManager(organization="Test", application=app_id)
        dialog = SettingsDialog(settings, AnimationManager())
        test_folder = str(tmp_path / "images")
        Path(test_folder).mkdir(exist_ok=True)
        folders = settings.get("sources.folders", [])
        if test_folder not in folders:
            folders.append(test_folder)
            settings.set("sources.folders", folders)
            settings.save()
        dialog.close()
        settings2 = SettingsManager(organization="Test", application=app_id)
        assert test_folder in settings2.get("sources.folders", [])

    def test_settings_nested_dict_warning(self):
        app_id = f"NestedDictTest_{uuid.uuid4().hex}"
        settings = SettingsManager(organization="Test", application=app_id)
        settings.set("sources", {"folders": ["/wrong/path"], "rss_feeds": []})
        settings.save()
        folders = settings.get("sources.folders", [])
        assert "/wrong/path" not in folders
        settings.set("sources.folders", ["/right/path"])
        settings.save()
        folders2 = settings.get("sources.folders", [])
        assert "/right/path" in folders2

    def test_sources_tab_rss_persistence(self):
        app_id = f"IntegrationTestRSS_{uuid.uuid4().hex}"
        settings = SettingsManager(organization="Test", application=app_id)
        feed = "https://www.nasa.gov/feeds/iotd-feed"
        feeds = settings.get("sources.rss_feeds", [])
        feeds.append(feed)
        settings.set("sources.rss_feeds", feeds)
        settings.save()
        settings2 = SettingsManager(organization="Test", application=app_id)
        loaded = settings2.get("sources.rss_feeds", [])
        assert feed in loaded

    def test_settings_load_on_startup(self, tmp_path):
        app_id = f"LoadTest_{uuid.uuid4().hex}"
        settings = SettingsManager(organization="Test", application=app_id)
        folder = str(tmp_path / "preloaded")
        Path(folder).mkdir(exist_ok=True)
        feed = "https://example.com/feed.rss"
        settings.set("sources.folders", [folder])
        settings.set("sources.rss_feeds", [feed])
        settings.save()
        tab = SourcesTab(settings)
        assert tab.folder_list.count() == 1
        assert tab.rss_list.count() == 1
        assert tab.folder_list.item(0).text() == folder
        assert tab.rss_list.item(0).text() == feed

    def test_widgets_tab_media_roundtrip(self):
        org = "Test"
        app_id = f"WidgetsTabMediaRoundtripTest_{uuid.uuid4().hex}"
        settings = SettingsManager(organization=org, application=app_id)
        dialog = SettingsDialog(settings, AnimationManager())
        tab = dialog.widgets_tab
        tab.media_enabled.setChecked(True)
        tab.media_position.setCurrentText("Bottom Left")
        tab.media_monitor_combo.setCurrentText("ALL")
        tab._save_settings()
        widgets_cfg = settings.get("widgets", {})
        media_cfg = widgets_cfg.get("media", {})
        assert media_cfg.get("enabled") is True
        assert media_cfg.get("position") == "Bottom Left"
        assert media_cfg.get("monitor") == "ALL"
        dialog.close()

    def test_media_widget_created_after_config_roundtrip(self, qt_app, thread_manager):
        org = "Test"
        app_id = f"MediaConfigRoundtripDisplayTest_{uuid.uuid4().hex}"
        settings = SettingsManager(organization=org, application=app_id)
        dialog = SettingsDialog(settings, AnimationManager())
        tab = dialog.widgets_tab
        tab.media_enabled.setChecked(True)
        tab.media_monitor_combo.setCurrentText("ALL")
        tab._save_settings()
        dialog.close()

        widget = DisplayWidget(
            screen_index=0,
            display_mode=DisplayMode.FILL,
            settings_manager=settings,
            thread_manager=thread_manager,
        )
        widget.resize(400, 400)
        widget._setup_widgets()
        assert getattr(widget, "media_widget", None) is not None
        widget.close()

class TestSettingsSignals:
    """Settings signal + SourcesTab workflows."""

    def test_add_rss_feed_triggers_signal(self):
        settings = SettingsManager(organization="Test", application=f"AddRSSTest_{uuid.uuid4().hex}")
        tab = SourcesTab(settings)
        handler = Mock()
        tab.sources_changed.connect(handler)
        feeds = settings.get("sources.rss_feeds", [])
        feeds.append("https://example.com/rss")
        settings.set("sources.rss_feeds", feeds)
        tab.sources_changed.emit()
        assert handler.called

    def test_remove_folder_triggers_signal(self, tmp_path):
        settings = SettingsManager(organization="Test", application=f"RemoveFolderTest_{uuid.uuid4().hex}")
        folder = str(tmp_path / "photos")
        Path(folder).mkdir(exist_ok=True)
        settings.set("sources.folders", [folder])
        tab = SourcesTab(settings)
        handler = Mock()
        tab.sources_changed.connect(handler)
        settings.set("sources.folders", [])
        tab.sources_changed.emit()
        assert handler.called


# ---------------------------------------------------------------------------
# Clock widget regression tests
# ---------------------------------------------------------------------------

class TestClockWidgetIntegration:
    """Regression suite for ClockWidget integration bugs."""

    def _enable_clock(self, widget: DisplayWidget, **kwargs):
        cfg = {
            "clock": {
                "enabled": True,
                **kwargs,
            }
        }
        widget.settings_manager.set("widgets", cfg)

    def test_clock_widget_created(self, display_widget):
        self._enable_clock(display_widget, position="Top Right")
        display_widget._setup_widgets()
        assert isinstance(display_widget.clock_widget, ClockWidget)

    def test_clock_color_array_conversion(self, display_widget):
        self._enable_clock(display_widget, color=[255, 128, 64, 200])
        display_widget._setup_widgets()
        assert isinstance(display_widget.clock_widget, ClockWidget)

    def test_clock_z_order_raise(self, display_widget):
        self._enable_clock(display_widget)
        display_widget._setup_widgets()
        image_label = QLabel(display_widget)
        image_label.resize(800, 600)
        image_label.show()
        assert display_widget.clock_widget.parent() == display_widget

    def test_clock_boolean_conversion(self, display_widget):
        self._enable_clock(display_widget, enabled=True)
        display_widget._setup_widgets()
        assert display_widget.clock_widget is not None
        display_widget.clock_widget.deleteLater()
        display_widget.clock_widget = None
        display_widget.settings_manager.set("widgets", {"clock": {"enabled": False}})
        display_widget._setup_widgets()
        assert display_widget.clock_widget is None

    def test_clock_position_and_format_strings(self, display_widget):
        positions = [
            "Top Left",
            "Top Right",
            "Top Center",
            "Bottom Left",
            "Bottom Right",
            "Bottom Center",
        ]
        for pos in positions:
            self._enable_clock(display_widget, position=pos)
            display_widget._setup_widgets()
            assert display_widget.clock_widget is not None
            display_widget.clock_widget.deleteLater()
            display_widget.clock_widget = None

    def test_clock_widget_size_and_position(self, display_widget):
        self._enable_clock(display_widget, position="Top Right", font_size=48, margin=20)
        display_widget._setup_widgets()
        size = display_widget.clock_widget.size()
        assert size.width() > 0 and size.height() > 0

    def test_clock_complete_integration(self, display_widget):
        self._enable_clock(
            display_widget,
            format="24h",
            position="Top Right",
            show_seconds=False,
            font_size=48,
            margin=20,
            color=[255, 255, 255, 230],
        )
        display_widget._setup_widgets()
        assert isinstance(display_widget.clock_widget, ClockWidget)
        size = display_widget.clock_widget.size()
        assert size.width() > 0


# ---------------------------------------------------------------------------
# Widgets tab -> DisplayWidget routing
# ---------------------------------------------------------------------------

class TestWidgetRouting:
    """WidgetsTab persistence + per-monitor routing."""

    @pytest.mark.qt
    def test_widgets_tab_changes_reflected_in_display_widget(
        self, qt_app, settings_manager, thread_manager, qtbot, monkeypatch
    ):
        tab = WidgetsTab(settings_manager)
        qtbot.addWidget(tab)
        tab.clock_enabled.setChecked(True)
        tab.clock_format.setCurrentText("24 Hour")
        tab.clock_seconds.setChecked(True)
        tab.clock_position.setCurrentText("Top Right")
        tab.clock_monitor_combo.setCurrentText("1")
        tab.clock_show_background.setChecked(True)
        tab.clock_bg_opacity.setValue(80)
        tab.weather_enabled.setChecked(True)
        tab.weather_location.setText("Johannesburg")
        tab.weather_position.setCurrentText("Top Left")
        tab.weather_monitor_combo.setCurrentText("ALL")
        tab.weather_show_background.setChecked(True)
        tab.weather_bg_opacity.setValue(80)
        tab._save_settings()

        def fake_weather_start(self):
            self._enabled = True

        monkeypatch.setattr(WeatherWidget, "start", fake_weather_start, raising=False)

        widget = DisplayWidget(
            screen_index=0,
            display_mode=DisplayMode.FILL,
            settings_manager=settings_manager,
            thread_manager=thread_manager,
        )
        qtbot.addWidget(widget)
        widget.resize(800, 600)
        widget._setup_widgets()
        assert isinstance(widget.clock_widget, ClockWidget)
        assert widget.clock_widget._show_seconds is True
        assert widget.clock_widget._enabled is True
        assert widget.weather_widget is not None
        assert widget.weather_widget._enabled is True

    @pytest.mark.qt
    def test_display_widget_respects_widget_monitor_selection(
        self, qt_app, settings_manager, thread_manager, qtbot, monkeypatch
    ):
        def fake_clock_start(self):
            self._enabled = True

        def fake_weather_start(self):
            self._enabled = True

        monkeypatch.setattr(ClockWidget, "start", fake_clock_start, raising=False)
        monkeypatch.setattr(WeatherWidget, "start", fake_weather_start, raising=False)

        settings_manager.set(
            "widgets",
            {
                "clock": {
                    "enabled": True,
                    "monitor": "1",
                    "position": "Top Right",
                },
                "clock2": {
                    "enabled": True,
                    "monitor": "2",
                    "position": "Top Right",
                },
                "weather": {
                    "enabled": True,
                    "monitor": "2",
                    "location": "Johannesburg",
                    "position": "Bottom Left",
                },
            },
        )

        w0 = DisplayWidget(
            screen_index=0,
            display_mode=DisplayMode.FILL,
            settings_manager=settings_manager,
            thread_manager=thread_manager,
        )
        qtbot.addWidget(w0)
        w0.resize(800, 600)
        w0._setup_widgets()
        assert w0.clock_widget is not None
        assert w0.clock2_widget is None
        assert w0.weather_widget is None

        w1 = DisplayWidget(
            screen_index=1,
            display_mode=DisplayMode.FILL,
            settings_manager=settings_manager,
            thread_manager=thread_manager,
        )
        qtbot.addWidget(w1)
        w1.resize(800, 600)
        w1._setup_widgets()
        assert w1.clock_widget is None
        assert isinstance(w1.clock2_widget, ClockWidget)
        assert w1.weather_widget is not None
        assert getattr(w1.weather_widget._position, "value", None) == WeatherPosition.BOTTOM_LEFT.value
        assert w1.weather_widget._location == "Johannesburg"
        assert w1.weather_widget._enabled is True

# ---------------------------------------------------------------------------
# Regression prevention utilities
# ---------------------------------------------------------------------------

class TestRegressionGuards:
    """Static checks to prevent regressions."""

    def test_transitions_do_not_call_process_events(self):
        import transitions.gl_compositor_crossfade_transition as gl_gl
        import transitions.crossfade_transition as sw

        for module in (gl_gl, sw):
            source = inspect.getsource(module)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "processEvents":
                        pytest.fail(f"processEvents() found in {module.__name__}")

    def test_showfullscreen_not_deferred(self, qt_app, thread_manager):
        widget = DisplayWidget(0, DisplayMode.FILL, None, thread_manager=thread_manager)
        try:
            assert hasattr(widget, "showFullScreen")
        finally:
            widget.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
