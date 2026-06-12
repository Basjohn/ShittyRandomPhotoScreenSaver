"""
Tests for WidgetManager lifecycle and coordination.

Tests cover:
- Widget registration and retrieval
- Lifecycle methods (initialize, activate, deactivate, cleanup)
- Fade coordination
- Raise operations with rate limiting
- Settings integration for live updates
- ResourceManager integration
"""
import time
import pytest
from unittest.mock import MagicMock
from typing import Dict, Any
from types import SimpleNamespace


class MockWidget:
    """Mock widget for testing."""
    
    def __init__(self, name: str = "mock"):
        self._name = name
        self._visible = False
        self._geometry = (0, 0, 100, 100)
        self._lifecycle_state = "CREATED"
        self._raised = False
        self._widget_manager = None
        
    def show(self):
        self._visible = True
        
    def hide(self):
        self._visible = False
        
    def isVisible(self):
        return self._visible
        
    def raise_(self):
        self._raised = True
        
    def setGeometry(self, x, y, w, h):
        self._geometry = (x, y, w, h)
        
    def geometry(self):
        from PySide6.QtCore import QRect
        return QRect(*self._geometry)
        
    def set_widget_manager(self, manager):
        self._widget_manager = manager
        
    def initialize(self):
        self._lifecycle_state = "INITIALIZED"
        
    def activate(self):
        self._lifecycle_state = "ACTIVE"
        
    def deactivate(self):
        self._lifecycle_state = "INACTIVE"
        
    def cleanup(self):
        self._lifecycle_state = "CLEANED"


class MockResourceManager:
    """Mock ResourceManager for testing."""
    
    def __init__(self):
        self._registered = {}
        
    def register_qt(self, widget, description=""):
        self._registered[id(widget)] = description


class MockSettingsManager:
    """Mock SettingsManager for testing."""
    
    def __init__(self):
        self._settings: Dict[str, Any] = {}
        self._handlers = []
        
    def get(self, key, default=None):
        return self._settings.get(key, default)
        
    def set(self, key, value):
        self._settings[key] = value
        for handler in self._handlers:
            handler(key, value)
            
    class settings_changed:
        _handlers = []
        
        @classmethod
        def connect(cls, handler):
            cls._handlers.append(handler)
            
        @classmethod
        def disconnect(cls, handler):
            if handler in cls._handlers:
                cls._handlers.remove(handler)


class TestWidgetRegistration:
    """Tests for widget registration."""
    
    def test_register_widget(self):
        """Test registering a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        assert manager.get_widget("test") is widget
    
    def test_unregister_widget(self):
        """Test unregistering a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        removed = manager.unregister_widget("test")
        assert removed is widget
        assert manager.get_widget("test") is None
    
    def test_get_all_widgets(self):
        """Test getting all widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        w1 = MockWidget("w1")
        w2 = MockWidget("w2")
        manager.register_widget("w1", w1)
        manager.register_widget("w2", w2)
        
        all_widgets = manager.get_all_widgets()
        assert len(all_widgets) == 2
        assert w1 in all_widgets
        assert w2 in all_widgets
    
    def test_widget_manager_set_on_register(self):
        """Test that widget manager is set on widget during registration."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        assert widget._widget_manager is manager


class TestWidgetLifecycle:
    """Tests for widget lifecycle methods."""
    
    def test_initialize_widget(self):
        """Test initializing a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.initialize_widget("test")
        assert result is True
        assert widget._lifecycle_state == "INITIALIZED"
    
    def test_activate_widget(self):
        """Test activating a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.activate_widget("test")
        assert result is True
        assert widget._lifecycle_state == "ACTIVE"
    
    def test_deactivate_widget(self):
        """Test deactivating a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.deactivate_widget("test")
        assert result is True
        assert widget._lifecycle_state == "INACTIVE"
    
    def test_cleanup_widget(self):
        """Test cleaning up a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.cleanup_widget("test")
        assert result is True
        assert widget._lifecycle_state == "CLEANED"
    
    def test_initialize_all_widgets(self):
        """Test initializing all widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        w1 = MockWidget("w1")
        w2 = MockWidget("w2")
        manager.register_widget("w1", w1)
        manager.register_widget("w2", w2)
        
        count = manager.initialize_all_widgets()
        assert count == 2
        assert w1._lifecycle_state == "INITIALIZED"
        assert w2._lifecycle_state == "INITIALIZED"


class TestWidgetVisibility:
    """Tests for widget visibility operations."""
    
    def test_show_widget(self):
        """Test showing a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.show_widget("test")
        assert result is True
        assert widget._visible is True
    
    def test_hide_widget(self):
        """Test hiding a widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        widget._visible = True
        manager.register_widget("test", widget)
        
        result = manager.hide_widget("test")
        assert result is True
        assert widget._visible is False
    
    def test_set_widget_geometry(self):
        """Test setting widget geometry."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.set_widget_geometry("test", 10, 20, 300, 200)
        assert result is True
        assert widget._geometry == (10, 20, 300, 200)


class TestRaiseOperations:
    """Tests for raise operations."""
    
    def test_raise_widget(self):
        """Test raising a specific widget."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        result = manager.raise_widget("test")
        assert result is True
        assert widget._raised is True
    
    def test_raise_all_widgets(self):
        """Test raising all widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        w1 = MockWidget("w1")
        w2 = MockWidget("w2")
        manager.register_widget("w1", w1)
        manager.register_widget("w2", w2)
        
        manager.raise_all_widgets()
        assert w1._raised is True
        assert w2._raised is True

    def test_raise_all_widgets_re_raises_widgets_after_main_window_raise(self):
        """Widget re-raise should happen synchronously after the main window raise path."""
        from rendering.widget_manager import WidgetManager

        order: list[str] = ["main-window"]

        class OrderedWidget(MockWidget):
            def raise_(self):
                order.append(self._name)
                super().raise_()

        parent = MagicMock()
        manager = WidgetManager(parent)

        w1 = OrderedWidget("clock")
        w2 = OrderedWidget("media")
        manager.register_widget("clock", w1)
        manager.register_widget("media", w2)

        manager.raise_all_widgets()

        assert order == ["main-window", "clock", "media"]

    def test_raise_all_widgets_re_raises_clock_tz_label_after_widget(self):
        """Clock timezone labels should be re-raised after their parent widget."""
        from rendering.widget_manager import WidgetManager

        order: list[str] = []

        class OrderedWidget(MockWidget):
            def raise_(self):
                order.append(self._name)
                super().raise_()

        class OrderedLabel:
            def raise_(self):
                order.append("clock_tz_label")

        parent = MagicMock()
        manager = WidgetManager(parent)

        clock = OrderedWidget("clock")
        clock._tz_label = OrderedLabel()  # type: ignore[attr-defined]
        manager.register_widget("clock", clock)

        manager.raise_all_widgets()

        assert order == ["clock", "clock_tz_label"]


class TestFadeCallbacks:
    """Tests for fade callback coordination."""
    
    def test_register_fade_callback(self):
        """Test registering a fade callback."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        callback = MagicMock()
        manager.register_fade_callback("test", callback)
        
        manager.invoke_fade_callbacks(0.5)
        callback.assert_called_once_with(0.5)
    
    def test_multiple_fade_callbacks(self):
        """Test invoking multiple fade callbacks."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        cb1 = MagicMock()
        cb2 = MagicMock()
        manager.register_fade_callback("cb1", cb1)
        manager.register_fade_callback("cb2", cb2)
        
        manager.invoke_fade_callbacks(0.75)
        cb1.assert_called_once_with(0.75)
        cb2.assert_called_once_with(0.75)


class TestStartupCoordination:
    """Tests for centralized startup fade + Spotify secondary-stage ownership."""

    def test_expected_overlays_are_mirrored_to_parent(self):
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        manager = WidgetManager(parent)

        manager.add_expected_overlay("clock")
        manager.add_expected_overlay("media")

        assert parent._overlay_fade_expected == {"clock", "media"}

    def test_secondary_fades_queue_until_compositor_ready_then_use_startup_delay(self, monkeypatch):
        from rendering.widget_manager import WidgetManager
        from rendering.overlay_startup_policy import get_overlay_startup_fade_policy

        parent = MagicMock()
        parent.screen_index = 1
        parent._has_rendered_first_frame = False
        parent.image_displayed = MagicMock()
        manager = WidgetManager(parent)
        manager.add_expected_overlay("clock")

        scheduled: list[int] = []
        monkeypatch.setattr(
            "rendering.widget_manager.QTimer.singleShot",
            lambda delay_ms, starter: scheduled.append(int(delay_ms)),
        )
        prewarm_calls: list[str] = []
        monkeypatch.setattr(
            manager,
            "_prewarm_spotify_visualizer_overlay",
            lambda: prewarm_calls.append("prewarm") or True,
        )

        manager.register_spotify_secondary_fade(lambda: None)

        assert len(manager._spotify_secondary_fade_starters) == 1

        manager._on_compositor_ready("first-image")

        policy = get_overlay_startup_fade_policy()

        assert parent._overlay_fade_started is True
        assert parent._overlay_fade_expected == {"clock"}
        assert scheduled == [policy.spotify_secondary_startup_delay_ms]
        assert prewarm_calls == ["prewarm"]
        assert len(manager._spotify_secondary_fade_starters) == 0
        assert parent._spotify_secondary_not_before_ts > 0.0

    def test_secondary_fades_use_direct_delay_when_registered_after_compositor_ready(self, monkeypatch):
        from rendering.widget_manager import WidgetManager
        from rendering.overlay_startup_policy import get_overlay_startup_fade_policy

        parent = MagicMock()
        parent.screen_index = 1
        parent._has_rendered_first_frame = False
        parent.image_displayed = MagicMock()
        manager = WidgetManager(parent)
        manager.add_expected_overlay("clock")

        scheduled: list[int] = []
        monkeypatch.setattr(
            "rendering.widget_manager.QTimer.singleShot",
            lambda delay_ms, starter: scheduled.append(int(delay_ms)),
        )
        prewarm_calls: list[str] = []
        monkeypatch.setattr(
            manager,
            "_prewarm_spotify_visualizer_overlay",
            lambda: prewarm_calls.append("prewarm") or True,
        )

        manager._on_compositor_ready("first-image")
        scheduled.clear()
        prewarm_calls.clear()

        manager.register_spotify_secondary_fade(lambda: None)

        assert scheduled == [get_overlay_startup_fade_policy().spotify_secondary_direct_delay_ms]
        assert prewarm_calls == ["prewarm"]

    def test_secondary_fades_use_live_policy_object(self, monkeypatch):
        from rendering.overlay_startup_policy import OverlayStartupFadePolicy
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        parent.screen_index = 1
        parent._has_rendered_first_frame = False
        parent.image_displayed = MagicMock()
        manager = WidgetManager(parent)
        manager.add_expected_overlay("clock")

        scheduled: list[int] = []
        monkeypatch.setattr(
            "rendering.widget_manager.QTimer.singleShot",
            lambda delay_ms, starter: scheduled.append(int(delay_ms)),
        )
        monkeypatch.setattr(
            manager,
            "_get_overlay_startup_policy",
            lambda: OverlayStartupFadePolicy(
                primary_warmup_ms=0,
                primary_post_fade_buffer_ms=555,
                spotify_secondary_startup_delay_ms=2345,
                spotify_secondary_direct_delay_ms=1234,
            ),
        )

        manager.register_spotify_secondary_fade(lambda: None)
        manager._on_compositor_ready("first-image")
        assert scheduled == [2345]

        scheduled.clear()
        manager.register_spotify_secondary_fade(lambda: None)
        assert scheduled == [1234]

    def test_startup_staging_fires_secondary_reveal_through_coordinator(self, monkeypatch):
        from rendering.widget_manager import WidgetManager

        class _Widget:
            def __init__(self):
                self.begin_calls = 0
                self.sync_calls = 0
                self._spotify_secondary_stage_registered = False
                self._anchor_media = None

            def objectName(self):
                return "spotify_visualizer"

            def begin_spotify_secondary_stage(self):
                self.begin_calls += 1

            def sync_visibility_with_anchor(self):
                self.sync_calls += 1

        parent = MagicMock()
        manager = WidgetManager(parent)
        widget = _Widget()

        starters = []
        monkeypatch.setattr(manager, "register_spotify_secondary_fade", lambda starter: starters.append(starter))

        manager._register_spotify_secondary_fade(widget)

        assert widget._spotify_secondary_stage_registered is True
        assert len(starters) == 1
        assert widget.begin_calls == 0
        assert widget.sync_calls == 0

        starters[0]()

        assert widget.begin_calls == 1
        assert widget.sync_calls == 0

    def test_overlay_fade_request_tracks_pending_until_compositor_ready(self):
        from rendering.widget_manager import WidgetManager

        class _Signal:
            def connect(self, _callback):
                return None

        parent = MagicMock()
        parent.screen_index = 0
        parent._has_rendered_first_frame = False
        parent.image_displayed = _Signal()
        parent._overlay_fade_pending = {}

        manager = WidgetManager(parent)
        manager.add_expected_overlay("weather")

        calls = []
        manager.request_overlay_fade_sync("weather", lambda: calls.append("started"))

        assert calls == []
        assert set(parent._overlay_fade_pending.keys()) == {"weather"}

        manager._on_compositor_ready("first-image")

        assert calls == ["started"]
        assert parent._overlay_fade_pending == {}

    def test_overlay_fade_request_after_compositor_ready_starts_immediately(self):
        from rendering.widget_manager import WidgetManager

        class _Signal:
            def connect(self, _callback):
                return None

        parent = MagicMock()
        parent.screen_index = 1
        parent._has_rendered_first_frame = True
        parent.image_displayed = _Signal()
        parent._overlay_fade_pending = {}
        parent._first_frame_committed_ts = time.monotonic() - 0.25

        manager = WidgetManager(parent)
        manager.add_expected_overlay("gmail")

        calls = []
        manager.request_overlay_fade_sync("gmail", lambda: calls.append("started"))

        assert calls == ["started"]
        assert parent._overlay_fade_pending == {}

    def test_reset_fade_coordination_clears_spotify_overlay_prewarm_flags(self):
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        manager = WidgetManager(parent)
        manager._spotify_overlay_prewarm_attempted = True
        manager._spotify_overlay_prewarmed = True

        manager.reset_fade_coordination()

        assert manager._spotify_overlay_prewarm_attempted is False
        assert manager._spotify_overlay_prewarmed is False

    def test_reset_fade_coordination_reprimes_ready_compositor_state(self):
        from rendering.widget_manager import WidgetManager
        from rendering.fade_coordinator import FadeState

        parent = MagicMock()
        manager = WidgetManager(parent)
        manager._compositor_ready = True

        manager.reset_fade_coordination()

        assert parent._overlay_fade_started is True
        assert manager._fade_coordinator.get_state() == FadeState.READY

    def test_reset_fade_coordination_clears_stale_fade_participants(self):
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        manager = WidgetManager(parent)
        manager._fade_coordinator.register_participant("clock")
        manager._fade_coordinator.register_participant("weather")

        manager.reset_fade_coordination()

        desc = manager._fade_coordinator.describe()
        assert desc["participants"] == []

    def test_apply_widget_stacking_skips_widgets_in_custom_position_mode(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._stack_offset = QPoint(0, 0)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return 20 + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: 100)

            def height(self):
                return 100

        parent = MagicMock()
        parent.height.return_value = 1000
        manager = WidgetManager(parent)
        clock = _StackWidget("TOP_RIGHT")
        weather = _StackWidget("TOP_RIGHT")

        manager.apply_widget_stacking(
            [
                (clock, "clock_widget"),
                (weather, "weather_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "clock": {"position": "Custom"},
                "weather": {"position": "Top Right"},
            },
        )

        assert clock.stack_offsets[-1] == QPoint(0, 0)
        assert weather.stack_offsets[-1] == QPoint(0, 0)

    def test_apply_widget_stacking_skips_widgets_with_active_custom_layout_rect_even_without_custom_route(self):
        from PySide6.QtCore import QPoint, QRect
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str, base_y: int, height: int, *, custom_rect: QRect | None = None):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._height = height
                self._base_y = base_y
                self._stack_offset = QPoint(0, 0)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []
                if custom_rect is not None:
                    self._custom_layout_local_rect = QRect(custom_rect)

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return self._base_y + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: self._height)

            def height(self):
                return self._height

            def get_bounding_size(self):
                return SimpleNamespace(height=lambda: self._height)

        parent = MagicMock()
        parent.height.return_value = 1439
        parent.screen_index = 1
        manager = WidgetManager(parent)
        weather = _StackWidget("TOP_LEFT", 20, 267)
        reddit = _StackWidget("MIDDLE_LEFT", 357, 724, custom_rect=QRect(200, 357, 600, 724))
        gmail = _StackWidget("BOTTOM_LEFT", 1066, 353)

        manager.apply_widget_stacking(
            [
                (weather, "weather_widget"),
                (reddit, "reddit_widget"),
                (gmail, "gmail_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "weather": {"position": "Top Left"},
                "reddit": {"position": "Middle Left"},
                "gmail": {"position": "Bottom Left"},
            },
        )

        assert weather.stack_offsets[-1] == QPoint(0, 0)
        assert reddit.stack_offsets[-1] == QPoint(0, 0)
        assert gmail.stack_offsets[-1] == QPoint(0, 0)
        assert weather.y() == 20
        assert reddit.y() == 357
        assert gmail.y() == 1066

    def test_apply_widget_stacking_is_disabled_by_default_and_clears_offsets(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._stack_offset = QPoint(0, 99)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return 100 + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: 120)

            def height(self):
                return 120

        parent = MagicMock()
        parent.height.return_value = 1000
        manager = WidgetManager(parent)
        weather = _StackWidget("TOP_LEFT")
        gmail = _StackWidget("MIDDLE_LEFT")

        manager.apply_widget_stacking(
            [
                (weather, "weather_widget"),
                (gmail, "gmail_widget"),
            ],
            {
                "global": {"stacking_enabled": False},
                "weather": {"position": "Top Left"},
                "gmail": {"position": "Middle Left"},
            },
        )

        assert weather.stack_offsets[-1] == QPoint(0, 0)
        assert gmail.stack_offsets[-1] == QPoint(0, 0)

    def test_apply_widget_stacking_is_disabled_for_entire_display_during_custom_edit_mode(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._stack_offset = QPoint(0, 99)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return 100 + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: 120)

            def height(self):
                return 120

        parent = MagicMock()
        parent.height.return_value = 1000
        parent._custom_layout_edit_active = True
        manager = WidgetManager(parent)
        reddit = _StackWidget("MIDDLE_LEFT")
        gmail = _StackWidget("BOTTOM_LEFT")

        manager.apply_widget_stacking(
            [
                (reddit, "reddit_widget"),
                (gmail, "gmail_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "reddit": {"position": "Middle Left"},
                "gmail": {"position": "Bottom Left"},
            },
        )

        assert reddit.stack_offsets[-1] == QPoint(0, 0)
        assert gmail.stack_offsets[-1] == QPoint(0, 0)

    def test_apply_widget_stacking_is_disabled_globally_when_any_widget_family_uses_custom_mode(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str, base_y: int):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._stack_offset = QPoint(0, 33)
                self._pixel_shift_offset = QPoint(0, 0)
                self._base_y = base_y
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return self._base_y + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: 160)

            def height(self):
                return 160

        parent = MagicMock()
        parent.height.return_value = 1200
        manager = WidgetManager(parent)
        weather = _StackWidget("TOP_LEFT", 20)
        reddit = _StackWidget("MIDDLE_LEFT", 320)
        gmail = _StackWidget("BOTTOM_LEFT", 900)

        manager.apply_widget_stacking(
            [
                (weather, "weather_widget"),
                (reddit, "reddit_widget"),
                (gmail, "gmail_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "weather": {"position": "Top Left"},
                "reddit": {"position": "Custom"},
                "gmail": {"position": "Middle Left"},
            },
        )

        assert weather.stack_offsets[-1] == QPoint(0, 0)
        assert reddit.stack_offsets[-1] == QPoint(0, 0)
        assert gmail.stack_offsets[-1] == QPoint(0, 0)

    def test_apply_widget_stacking_reflows_same_column_across_top_middle_bottom(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str, base_y: int, height: int):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._height = height
                self._base_y = base_y
                self._stack_offset = QPoint(0, 0)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return self._base_y + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: self._height)

            def height(self):
                return self._height

            def get_bounding_size(self):
                return SimpleNamespace(height=lambda: self._height)

        parent = MagicMock()
        parent.height.return_value = 1000
        parent.screen_index = 0
        manager = WidgetManager(parent)
        weather = _StackWidget("TOP_LEFT", 20, 220)
        gmail = _StackWidget("MIDDLE_LEFT", 340, 320)
        reddit = _StackWidget("BOTTOM_LEFT", 720, 260)

        manager.apply_widget_stacking(
            [
                (weather, "weather_widget"),
                (gmail, "gmail_widget"),
                (reddit, "reddit_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "weather": {"position": "Top Left"},
                "gmail": {"position": "Middle Left"},
                "reddit": {"position": "Bottom Left"},
            },
        )

        assert weather.stack_offsets[-1] == QPoint(0, 0)
        weather_top = weather.y()
        gmail_top = gmail.y()
        reddit_top = reddit.y()

        assert gmail_top >= weather_top + weather._height
        assert reddit_top >= gmail_top + gmail._height

    def test_apply_widget_stacking_preserves_authored_positions_when_lane_already_fits(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str, base_y: int, height: int):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._height = height
                self._base_y = base_y
                self._stack_offset = QPoint(0, 0)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return self._base_y + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: self._height)

            def height(self):
                return self._height

            def get_bounding_size(self):
                return SimpleNamespace(height=lambda: self._height)

        parent = MagicMock()
        parent.height.return_value = 1439
        parent.screen_index = 1
        manager = WidgetManager(parent)
        clock = _StackWidget("TOP_RIGHT", 20, 491)
        media = _StackWidget("BOTTOM_RIGHT", 1159, 260)

        manager.apply_widget_stacking(
            [
                (clock, "clock_widget"),
                (media, "media_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "clock": {"position": "Top Right"},
                "media": {"position": "Bottom Right"},
            },
        )

        assert clock.stack_offsets[-1] == QPoint(0, 0)
        assert media.stack_offsets[-1] == QPoint(0, 0)

    def test_apply_widget_stacking_compresses_only_when_needed_near_bottom_boundary(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str, base_y: int, height: int):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._height = height
                self._base_y = base_y
                self._stack_offset = QPoint(0, 0)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return self._base_y + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: self._height)

            def height(self):
                return self._height

            def get_bounding_size(self):
                return SimpleNamespace(height=lambda: self._height)

        parent = MagicMock()
        parent.height.return_value = 1439
        parent.screen_index = 1
        manager = WidgetManager(parent)
        weather = _StackWidget("TOP_LEFT", 20, 267)
        reddit = _StackWidget("MIDDLE_LEFT", 357, 724)
        gmail = _StackWidget("BOTTOM_LEFT", 1066, 353)

        manager.apply_widget_stacking(
            [
                (weather, "weather_widget"),
                (reddit, "reddit_widget"),
                (gmail, "gmail_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "weather": {"position": "Top Left"},
                "reddit": {"position": "Middle Left"},
                "gmail": {"position": "Bottom Left"},
            },
        )

        weather_top = weather.y()
        reddit_top = reddit.y()
        gmail_top = gmail.y()

        assert weather_top == 20
        assert reddit_top < reddit._base_y
        assert gmail_top >= reddit_top + reddit._height
        assert gmail_top + gmail._height <= 1439 - 20

    def test_apply_widget_stacking_preserves_top_middle_bottom_band_order_when_bottom_base_drifts_up(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str, base_y: int, height: int):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._height = height
                self._base_y = base_y
                self._stack_offset = QPoint(0, 0)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return self._base_y + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: self._height)

            def height(self):
                return self._height

            def get_bounding_size(self):
                return SimpleNamespace(height=lambda: self._height)

        parent = MagicMock()
        parent.height.return_value = 1000
        parent.screen_index = 0
        manager = WidgetManager(parent)
        weather = _StackWidget("TOP_LEFT", 20, 220)
        gmail = _StackWidget("MIDDLE_LEFT", 340, 320)
        reddit = _StackWidget("BOTTOM_LEFT", 720, 260)

        manager.apply_widget_stacking(
            [
                (weather, "weather_widget"),
                (gmail, "gmail_widget"),
                (reddit, "reddit_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "weather": {"position": "Top Left"},
                "gmail": {"position": "Middle Left"},
                "reddit": {"position": "Bottom Left"},
            },
        )

        weather_top = weather.y()
        gmail_top = gmail.y()
        reddit_top = reddit.y()

        assert weather_top == 20
        assert gmail_top >= weather_top + weather._height
        assert reddit_top >= gmail_top + gmail._height

    def test_apply_widget_stacking_keeps_bottom_band_anchored_when_middle_yields(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str, base_y: int, height: int):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._height = height
                self._base_y = base_y
                self._stack_offset = QPoint(0, 0)
                self._pixel_shift_offset = QPoint(0, 0)
                self.stack_offsets: list[QPoint] = []

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)
                self.stack_offsets.append(QPoint(offset))

            def y(self):
                return self._base_y + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: self._height)

            def height(self):
                return self._height

            def get_bounding_size(self):
                return SimpleNamespace(height=lambda: self._height)

        parent = MagicMock()
        parent.height.return_value = 1439
        parent.screen_index = 1
        manager = WidgetManager(parent)
        weather = _StackWidget("TOP_LEFT", 20, 267)
        reddit = _StackWidget("MIDDLE_LEFT", 357, 724)
        gmail = _StackWidget("BOTTOM_LEFT", 1066, 353)

        manager.apply_widget_stacking(
            [
                (weather, "weather_widget"),
                (reddit, "reddit_widget"),
                (gmail, "gmail_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "weather": {"position": "Top Left"},
                "reddit": {"position": "Middle Left"},
                "gmail": {"position": "Bottom Left"},
            },
        )

        weather_top = weather.y()
        reddit_top = reddit.y()
        gmail_top = gmail.y()

        assert weather_top == 20
        assert gmail_top == 1066
        assert reddit_top + reddit._height <= gmail_top - 10
        assert reddit_top < reddit._base_y

    def test_get_widget_stack_base_y_removes_existing_stack_and_pixel_shift(self):
        from PySide6.QtCore import QPoint
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self):
                self._stack_offset = QPoint(0, -80)
                self._pixel_shift_offset = QPoint(0, 6)

            def y(self):
                return 390 + self._stack_offset.y() + self._pixel_shift_offset.y()

        parent = MagicMock()
        manager = WidgetManager(parent)

        assert manager._get_widget_stack_base_y(_StackWidget()) == 390

    def test_get_widget_stack_base_y_uses_canonical_bottom_anchor_when_live_y_is_stale(self):
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self):
                self._position = SimpleNamespace(name="BOTTOM_LEFT")
                self._margin = 30

            def y(self):
                return 994

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: 353)

            def height(self):
                return 353

            def get_bounding_size(self):
                return SimpleNamespace(height=lambda: 353)

        parent = MagicMock()
        parent.height.return_value = 1439
        manager = WidgetManager(parent)

        assert manager._get_widget_stack_base_y(_StackWidget()) == 1056

    def test_get_widget_stack_height_prefers_live_runtime_height_when_larger_than_hint(self):
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def get_bounding_size(self):
                return SimpleNamespace(height=lambda: 260)

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: 260)

            def height(self):
                return 420

            def minimumHeight(self):
                return 420

        parent = MagicMock()
        manager = WidgetManager(parent)

        assert manager._get_widget_stack_height(_StackWidget()) == 420

    def test_get_widget_stack_height_prefers_visible_stacking_footprint_over_shadow_inflation(self):
        from PySide6.QtCore import QSize
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def get_stacking_footprint_size(self):
                return QSize(600, 353)

            def get_bounding_size(self):
                return QSize(654, 407)

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: 407)

            def height(self):
                return 353

            def minimumHeight(self):
                return 407

        parent = MagicMock()
        manager = WidgetManager(parent)

        assert manager._get_widget_stack_height(_StackWidget()) == 353

    def test_reserved_media_visualizer_stack_obstacle_blocks_follow_media_footprint(self):
        from PySide6.QtCore import QRect
        from rendering.widget_manager import WidgetManager

        class _MediaWidget:
            def __init__(self):
                self._position = SimpleNamespace(name="BOTTOM_RIGHT")

            def geometry(self):
                return QRect(1930, 1073, 600, 336)

        class _VisualizerWidget:
            def __init__(self):
                self._vis_mode_str = "devcurve"
                self._base_height = 80
                self._blob_width = 1.0

        parent = MagicMock()
        parent.width.return_value = 2560
        parent.height.return_value = 1439
        parent.media_widget = _MediaWidget()
        parent.spotify_visualizer_widget = _VisualizerWidget()
        manager = WidgetManager(parent)

        obstacle = manager._build_reserved_media_visualizer_stack_obstacle(
            {"global": {"stacking_enabled": True}, "media": {"position": "Bottom Right"}},
        )

        assert obstacle is not None
        assert obstacle.lane == "right"
        assert obstacle.top_y == 773
        assert obstacle.height == 636

    def test_apply_widget_stacking_keeps_media_fixed_and_moves_gmail_above_reserved_visualizer_block(self):
        from PySide6.QtCore import QPoint, QRect
        from rendering.widget_manager import WidgetManager

        class _StackWidget:
            def __init__(self, position_name: str, base_y: int, height: int):
                self._position = SimpleNamespace(name=position_name)
                self._margin = 20
                self._height = height
                self._base_y = base_y
                self._stack_offset = QPoint(0, 0)
                self._pixel_shift_offset = QPoint(0, 0)

            def set_stack_offset(self, offset: QPoint) -> None:
                self._stack_offset = QPoint(offset)

            def y(self):
                return self._base_y + self._stack_offset.y()

            def sizeHint(self):
                return SimpleNamespace(isValid=lambda: True, height=lambda: self._height)

            def height(self):
                return self._height

            def geometry(self):
                return QRect(1930, self._base_y, 600, self._height)

        class _VisualizerWidget:
            def __init__(self):
                self._vis_mode_str = "devcurve"
                self._base_height = 80
                self._blob_width = 1.0

        parent = MagicMock()
        parent.width.return_value = 2560
        parent.height.return_value = 1439
        parent.screen_index = 1
        clock = _StackWidget("TOP_RIGHT", 20, 491)
        gmail = _StackWidget("BOTTOM_RIGHT", 1056, 353)
        media = _StackWidget("BOTTOM_RIGHT", 1073, 336)
        parent.media_widget = media
        parent.spotify_visualizer_widget = _VisualizerWidget()
        manager = WidgetManager(parent)

        manager.apply_widget_stacking(
            [
                (clock, "clock_widget"),
                (gmail, "gmail_widget"),
                (media, "media_widget"),
            ],
            {
                "global": {"stacking_enabled": True},
                "clock": {"position": "Top Right"},
                "gmail": {"position": "Bottom Right"},
                "media": {"position": "Bottom Right"},
            },
        )

        assert media.y() == 1073
        assert gmail.y() + gmail._height <= 773 - 10

    def test_spotify_overlay_prewarm_can_retry_after_early_unavailable_widget(self):
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        parent.spotify_visualizer_widget = None
        manager = WidgetManager(parent)

        assert manager._prewarm_spotify_visualizer_overlay() is False
        assert manager._spotify_overlay_prewarm_attempted is False
        assert manager._spotify_overlay_prewarmed is False

    def test_sync_spotify_dependents_for_media_widget_reaches_cross_display_visualizer(self, monkeypatch):
        from rendering.widget_manager import WidgetManager

        class _Dependent:
            def __init__(self, anchor):
                self._anchor_media = anchor
                self.sync_calls = 0

            def sync_visibility_with_anchor(self):
                self.sync_calls += 1

        media_anchor = object()
        local_display = SimpleNamespace(
            spotify_visualizer_widget=None,
            spotify_volume_widget=None,
            mute_button_widget=None,
        )
        remote_visualizer = _Dependent(media_anchor)
        remote_display = SimpleNamespace(
            spotify_visualizer_widget=remote_visualizer,
            spotify_volume_widget=None,
            mute_button_widget=None,
        )

        class _CoordinatorStub:
            def get_all_instances(self):
                return [local_display, remote_display]

        monkeypatch.setattr("rendering.widget_manager.get_coordinator", lambda: _CoordinatorStub())

        manager = WidgetManager(local_display)
        manager.sync_spotify_dependents_for_media_widget(media_anchor)

        assert remote_visualizer.sync_calls == 1


class TestCleanup:
    """Tests for cleanup operations."""
    
    def test_cleanup_clears_widgets(self):
        """Test that cleanup clears all widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        w1 = MockWidget("w1")
        w2 = MockWidget("w2")
        manager.register_widget("w1", w1)
        manager.register_widget("w2", w2)
        
        manager.cleanup()
        
        assert len(manager.get_all_widgets()) == 0
    
    def test_cleanup_calls_widget_cleanup(self):
        """Test that cleanup calls cleanup on widgets."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        manager.cleanup()
        
        assert widget._lifecycle_state == "CLEANED"

    def test_cleanup_stops_and_clears_raise_timer(self, monkeypatch):
        """Deferred raise timer should be stopped and cleared during cleanup."""
        from rendering.widget_manager import WidgetManager

        class _FakeSignal:
            def __init__(self):
                self._callback = None

            def connect(self, callback):
                self._callback = callback

        class _FakeTimer:
            def __init__(self):
                self.timeout = _FakeSignal()
                self.single_shot = False
                self.started_with: list[int] = []
                self.stop_calls = 0

            def setSingleShot(self, value):
                self.single_shot = bool(value)

            def start(self, interval_ms):
                self.started_with.append(int(interval_ms))

            def stop(self):
                self.stop_calls += 1

        parent = MagicMock()
        resource_manager = MockResourceManager()
        manager = WidgetManager(parent, resource_manager)

        fake_timer_instances: list[_FakeTimer] = []

        def _timer_factory():
            timer = _FakeTimer()
            fake_timer_instances.append(timer)
            return timer

        monkeypatch.setattr("rendering.widget_manager.QTimer", _timer_factory)

        manager._last_raise_time = time.time()
        manager.raise_all()

        assert manager._pending_raise is True
        assert len(fake_timer_instances) == 1
        timer = fake_timer_instances[0]
        assert timer.single_shot is True
        assert timer.started_with
        assert id(timer) in resource_manager._registered

        manager.cleanup()

        assert timer.stop_calls == 1
        assert manager._raise_timer is None

    def test_prepare_for_runtime_pause_detaches_settings_stops_raise_and_widgets(self, monkeypatch):
        """Runtime-pause prep should suppress late work without full cleanup."""
        from rendering.widget_manager import WidgetManager

        class _FakeSignal:
            def __init__(self):
                self._callback = None

            def connect(self, callback):
                self._callback = callback

        class _FakeTimer:
            def __init__(self):
                self.timeout = _FakeSignal()
                self.single_shot = False
                self.started_with = []
                self.stop_calls = 0

            def setSingleShot(self, value):
                self.single_shot = bool(value)

            def start(self, interval_ms):
                self.started_with.append(int(interval_ms))

            def stop(self):
                self.stop_calls += 1

        class _StoppableWidget(MockWidget):
            def __init__(self, name="stoppable"):
                super().__init__(name)
                self.stop_calls = 0

            def stop(self):
                self.stop_calls += 1

        parent = MagicMock()
        manager = WidgetManager(parent)
        settings = MockSettingsManager()
        widget = _StoppableWidget()
        manager.register_widget("test", widget)

        fake_timer_instances = []

        def _timer_factory():
            timer = _FakeTimer()
            fake_timer_instances.append(timer)
            return timer

        monkeypatch.setattr("rendering.widget_manager.QTimer", _timer_factory)

        manager._attach_settings_manager(settings)
        manager._last_raise_time = time.time()
        manager.raise_all()
        manager._pending_spotify_visibility_sync = True
        manager._spotify_secondary_fade_starters = [lambda: None]

        timer = fake_timer_instances[0]
        assert manager._settings_manager is settings
        assert manager._pending_raise is True

        manager.prepare_for_runtime_pause()

        assert manager._settings_manager is None
        assert manager._pending_raise is False
        assert manager._pending_spotify_visibility_sync is False
        assert manager._spotify_secondary_fade_starters == []
        assert manager._raise_timer is None
        assert timer.stop_calls == 1
        assert widget.stop_calls == 1
        assert manager.get_widget("test") is widget


class TestSettingsRouting:
    """Tests for descriptor-driven live settings routing."""

    def test_handle_settings_changed_uses_descriptor_owned_handlers_for_widgets_root(self):
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        manager = WidgetManager(parent)
        manager._refresh_media_config = MagicMock()
        manager._refresh_reddit_configs = MagicMock()
        manager._refresh_spotify_visualizer_config = MagicMock()

        payload = {"media": {"enabled": True}}
        manager._handle_settings_changed("widgets", payload)

        manager._refresh_media_config.assert_called_once_with(payload)
        manager._refresh_reddit_configs.assert_called_once_with(payload)
        manager._refresh_spotify_visualizer_config.assert_called_once_with(payload)

    def test_handle_settings_changed_routes_reddit2_through_shared_reddit_refresh(self):
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        manager = WidgetManager(parent)
        manager._refresh_media_config = MagicMock()
        manager._refresh_reddit_configs = MagicMock()
        manager._refresh_spotify_visualizer_config = MagicMock()

        manager._handle_settings_changed("widgets.reddit2.limit", 7)

        manager._refresh_reddit_configs.assert_called_once_with()
        manager._refresh_media_config.assert_not_called()
        manager._refresh_spotify_visualizer_config.assert_not_called()

    def test_handle_settings_changed_routes_visualizer_mode_without_refreshing_media(self):
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        manager = WidgetManager(parent)
        manager._refresh_media_config = MagicMock()
        manager._refresh_reddit_configs = MagicMock()
        manager._refresh_spotify_visualizer_config = MagicMock()

        manager._handle_settings_changed("widgets.spotify_visualizer.mode", "bubble")

        manager._refresh_spotify_visualizer_config.assert_called_once_with()
        manager._refresh_media_config.assert_not_called()
        manager._refresh_reddit_configs.assert_not_called()
        parent._apply_saved_custom_layouts.assert_called_once_with()

    def test_handle_settings_changed_suppresses_live_widget_refresh_during_custom_reload(self):
        from rendering.widget_manager import WidgetManager

        parent = MagicMock()
        parent._custom_layout_runtime_reload_pending = True
        manager = WidgetManager(parent)
        manager._refresh_media_config = MagicMock()
        manager._refresh_reddit_configs = MagicMock()
        manager._refresh_spotify_visualizer_config = MagicMock()

        manager._handle_settings_changed("widgets", {"media": {"enabled": True}})
        manager._handle_settings_changed("widgets.reddit.limit", 7)

        manager._refresh_media_config.assert_not_called()
        manager._refresh_reddit_configs.assert_not_called()
        manager._refresh_spotify_visualizer_config.assert_not_called()
        parent._apply_saved_custom_layouts.assert_not_called()

    def test_refresh_media_config_reapplies_artwork_font_and_rounding(self):
        from rendering.widget_manager import WidgetManager

        class _FakeMediaWidget:
            def __init__(self):
                self.font_family = None
                self.font_size = None
                self.artwork_size = None
                self.rounded_artwork = None
                self.text_color = None
                self.show_controls = None
                self.show_header_frame = None

            def set_font_family(self, value):
                self.font_family = value

            def set_font_size(self, value):
                self.font_size = value

            def set_artwork_size(self, value):
                self.artwork_size = value

            def set_rounded_artwork_border(self, value):
                self.rounded_artwork = value

            def set_text_color(self, value):
                self.text_color = value

            def set_show_controls(self, value):
                self.show_controls = value

            def set_show_header_frame(self, value):
                self.show_header_frame = value

        parent = MagicMock()
        manager = WidgetManager(parent)
        fake_media = _FakeMediaWidget()
        fake_media._custom_layout_local_rect = object()
        manager._widgets["media"] = fake_media

        payload = {
            "media": {
                "font_family": "Inter",
                "font_size": 31,
                "artwork_size": 188,
                "rounded_artwork_border": False,
                "show_controls": False,
                "show_header_frame": False,
                "color": [1, 2, 3, 255],
            }
        }

        manager._refresh_media_config(payload)

        assert fake_media.font_family == "Inter"
        assert fake_media.font_size == 31
        assert fake_media.artwork_size == 188
        assert fake_media.rounded_artwork is False
        assert fake_media.show_controls is False
        assert fake_media.show_header_frame is False

    def test_refresh_spotify_visualizer_config_repositions_using_live_growth_contract(self):
        from PySide6.QtCore import QRect
        from core.settings.visualizer_presets import get_custom_preset_index
        from rendering.widget_manager import WidgetManager

        class _FakeVisualizer:
            def __init__(self):
                self._vis_mode_str = "spectrum"
                self._base_height = 80
                self._spectrum_growth = 2.0
                self._osc_growth = 2.0
                self._blob_growth = 3.5
                self._sine_wave_growth = 2.0
                self._bubble_growth = 3.0
                self._devcurve_growth = 3.5
                self._blob_width = 1.0
                self._geometry = None
                self._style = None
                self._model = None

            def set_settings_model(self, model):
                self._model = model

            def apply_vis_mode_config(self, **kwargs):
                self._vis_mode_str = kwargs["mode"]
                self._spectrum_growth = kwargs["spectrum_growth"]
                self._osc_growth = kwargs["osc_growth"]
                self._blob_growth = kwargs["blob_growth"]
                self._sine_wave_growth = kwargs["sine_wave_growth"]
                self._bubble_growth = kwargs["bubble_growth"]
                self._devcurve_growth = kwargs["devcurve_growth"]
                self._blob_width = kwargs["blob_width"]

            def set_bar_style(self, **kwargs):
                self._style = dict(kwargs)

            def setGeometry(self, x, y, w, h):
                self._geometry = (x, y, w, h)

            def raise_(self):
                pass

        class _FakeMedia:
            def __init__(self):
                self._position = SimpleNamespace(name="BOTTOM_LEFT")

            def geometry(self):
                return QRect(100, 700, 300, 100)

        parent = MagicMock()
        manager = WidgetManager(parent)
        vis = _FakeVisualizer()
        media = _FakeMedia()
        manager._widgets["spotify_visualizer"] = vis

        widgets_cfg = {
            "spotify_visualizer": {
                "enabled": True,
                "mode": "bubble",
                "preset_bubble": get_custom_preset_index("bubble"),
                "bubble_growth": 4.5,
            },
            "media": {
                "show_background": True,
                "bg_color": [32, 32, 32, 255],
                "border_color": [255, 255, 255, 255],
            },
        }

        manager._refresh_spotify_visualizer_config(widgets_cfg)
        manager.position_spotify_visualizer(vis, media, 1920, 1080)

        assert vis._model is not None
        assert vis._vis_mode_str == "bubble"
        assert vis._bubble_growth == pytest.approx(4.5)
        assert vis._geometry == (100, 320, 300, 360)

    def test_refresh_spotify_visualizer_config_repositions_blob_width_contract(self):
        from PySide6.QtCore import QRect
        from core.settings.visualizer_presets import get_custom_preset_index
        from rendering.widget_manager import WidgetManager

        class _FakeVisualizer:
            def __init__(self):
                self._vis_mode_str = "spectrum"
                self._base_height = 80
                self._spectrum_growth = 2.0
                self._osc_growth = 2.0
                self._blob_growth = 3.5
                self._sine_wave_growth = 2.0
                self._bubble_growth = 3.0
                self._devcurve_growth = 3.5
                self._blob_width = 1.0
                self._geometry = None

            def set_settings_model(self, model):
                self._model = model

            def apply_vis_mode_config(self, **kwargs):
                self._vis_mode_str = kwargs["mode"]
                self._spectrum_growth = kwargs["spectrum_growth"]
                self._osc_growth = kwargs["osc_growth"]
                self._blob_growth = kwargs["blob_growth"]
                self._sine_wave_growth = kwargs["sine_wave_growth"]
                self._bubble_growth = kwargs["bubble_growth"]
                self._devcurve_growth = kwargs["devcurve_growth"]
                self._blob_width = kwargs["blob_width"]

            def set_bar_style(self, **kwargs):
                pass

            def setGeometry(self, x, y, w, h):
                self._geometry = (x, y, w, h)

            def raise_(self):
                pass

        class _FakeMedia:
            def __init__(self):
                self._position = SimpleNamespace(name="BOTTOM_LEFT")

            def geometry(self):
                return QRect(100, 700, 300, 100)

        parent = MagicMock()
        manager = WidgetManager(parent)
        vis = _FakeVisualizer()
        media = _FakeMedia()
        manager._widgets["spotify_visualizer"] = vis

        widgets_cfg = {
            "spotify_visualizer": {
                "enabled": True,
                "mode": "blob",
                "preset_blob": get_custom_preset_index("blob"),
                "blob_growth": 3.5,
                "blob_width": 0.5,
            },
            "media": {
                "show_background": True,
            },
        }

        manager._refresh_spotify_visualizer_config(widgets_cfg)
        manager.position_spotify_visualizer(vis, media, 1920, 1080)

        assert vis._vis_mode_str == "blob"
        assert vis._blob_width == pytest.approx(0.5)
        assert vis._geometry == (175, 400, 150, 280)

    def test_position_spotify_visualizer_honors_custom_rect_even_if_settings_snapshot_is_stale(self):
        from PySide6.QtCore import QRect
        from rendering.widget_manager import WidgetManager

        class _FakeMedia:
            def geometry(self):
                return QRect(50, 50, 300, 100)

        class _FakeVisualizer:
            def __init__(self):
                self._custom_layout_local_rect = QRect(333, 444, 555, 280)
                self._custom_layout_visualizer_scale_payload = {"width_scale": 1.0, "height_scale": 1.0}
                self._vis_mode_str = "spectrum"
                self._base_height = 80
                self._blob_width = 1.0
                self._spectrum_growth = 2.0
                self._blob_growth = 3.5
                self._osc_growth = 2.0
                self._bubble_growth = 3.0
                self._devcurve_growth = 3.0
                self._sine_wave_growth = 2.0
                self._anchor_media = _FakeMedia()
                self._geometry = None
                self.raised = False

            def setGeometry(self, *args):
                if len(args) == 1 and isinstance(args[0], QRect):
                    rect = args[0]
                    self._geometry = (rect.x(), rect.y(), rect.width(), rect.height())
                else:
                    x, y, w, h = args
                    self._geometry = (x, y, w, h)

            def raise_(self):
                self.raised = True

        settings = MagicMock()
        settings.get_widgets_map.return_value = {
            "media": {"position": "Bottom Left"},
        }
        manager = WidgetManager(MagicMock())
        manager._settings_manager = settings

        vis = _FakeVisualizer()

        manager.position_spotify_visualizer(vis, None, 1920, 1080)

        assert vis._geometry == (333, 444, 555, 280)
        assert vis.raised is True

    def test_position_spotify_visualizer_custom_rect_keeps_committed_rect_even_if_scale_payload_differs(self):
        from PySide6.QtCore import QRect
        from rendering.widget_manager import WidgetManager

        class _FakeMedia:
            def geometry(self):
                return QRect(0, 0, 280, 100)

        class _FakeVisualizer:
            def __init__(self):
                self._custom_layout_local_rect = QRect(210, 310, 420, 280)
                self._custom_layout_visualizer_scale_payload = {"width_scale": 1.5, "height_scale": 1.25}
                self._vis_mode_str = "blob"
                self._base_height = 80
                self._blob_width = 0.5
                self._spectrum_growth = 2.0
                self._blob_growth = 3.5
                self._osc_growth = 2.0
                self._bubble_growth = 3.0
                self._devcurve_growth = 3.0
                self._sine_wave_growth = 2.0
                self._anchor_media = _FakeMedia()
                self._geometry = None
                self.raised = False

            def setGeometry(self, *args):
                if len(args) == 1 and isinstance(args[0], QRect):
                    rect = args[0]
                    self._geometry = (rect.x(), rect.y(), rect.width(), rect.height())
                else:
                    x, y, w, h = args
                    self._geometry = (x, y, w, h)

            def raise_(self):
                self.raised = True

        settings = MagicMock()
        settings.get_widgets_map.return_value = {}
        manager = WidgetManager(MagicMock())
        manager._settings_manager = settings

        vis = _FakeVisualizer()

        manager.position_spotify_visualizer(vis, None, 1920, 1080)

        assert vis._geometry == (210, 310, 420, 280)
        assert vis.raised is True

    @pytest.mark.qt
    def test_position_spotify_visualizer_real_widget_applies_custom_constraints_before_replay(self, qt_app, qtbot):
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QWidget
        from rendering.widget_manager import WidgetManager
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        parent = QWidget()
        parent.resize(1920, 1080)
        qtbot.addWidget(parent)
        parent.show()

        settings = MagicMock()
        settings.get_widgets_map.return_value = {}
        manager = WidgetManager(parent)
        manager._settings_manager = settings

        vis = SpotifyVisualizerWidget(parent=parent, bar_count=8)
        vis._custom_layout_local_rect = QRect(210, 310, 420, 280)
        vis.setMinimumHeight(400)
        vis.setGeometry(0, 0, 100, 400)

        manager.position_spotify_visualizer(vis, None, 1920, 1080)

        assert vis.geometry() == QRect(210, 310, 420, 280)
        assert vis.minimumHeight() == 280
        assert vis.maximumHeight() == 280

    def test_position_spotify_volume_honors_custom_rect_even_if_settings_snapshot_is_stale(self):
        from PySide6.QtCore import QRect
        from rendering.widget_manager import WidgetManager

        class _FakeVolume:
            def __init__(self):
                self._custom_layout_local_rect = QRect(111, 222, 144, 320)
                self._geometry = None
                self.raised = False

            def setGeometry(self, *args):
                if len(args) == 1 and isinstance(args[0], QRect):
                    rect = args[0]
                    self._geometry = (rect.x(), rect.y(), rect.width(), rect.height())
                else:
                    x, y, w, h = args
                    self._geometry = (x, y, w, h)

            def isVisible(self):
                return True

            def raise_(self):
                self.raised = True

            def minimumWidth(self):
                return 32

            def minimumHeight(self):
                return 180

            def height(self):
                return 180

        settings = MagicMock()
        settings.get_widgets_map.return_value = {}
        manager = WidgetManager(MagicMock())
        manager._settings_manager = settings

        volume = _FakeVolume()

        manager.position_spotify_volume(volume, None, 1920, 1080)

        assert volume._geometry == (111, 222, 144, 320)
        assert volume.raised is True


class TestPositioning:
    """Tests for widget positioning."""
    
    def test_set_container_size(self):
        """Test setting container size."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        manager = WidgetManager(parent)
        
        manager.set_container_size(1920, 1080)
        
        positioner = manager.get_positioner()
        assert positioner is not None


class TestResourceManagerIntegration:
    """Tests for ResourceManager integration."""
    
    def test_widget_registered_with_resource_manager(self):
        """Test that widgets are registered with ResourceManager."""
        from rendering.widget_manager import WidgetManager
        
        parent = MagicMock()
        resource_manager = MockResourceManager()
        manager = WidgetManager(parent, resource_manager)
        
        widget = MockWidget("test")
        manager.register_widget("test", widget)
        
        assert id(widget) in resource_manager._registered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
