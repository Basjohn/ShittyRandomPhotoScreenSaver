"""Smoke tests for WidgetManager widget creation paths via factory registry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.resources.manager import ResourceManager
from rendering import display_setup
from rendering.widget_manager import WidgetManager
from widgets.media_widget import MediaPosition
from widgets.clock_widget import ClockPosition
from widgets.weather_widget import WeatherPosition
from widgets.reddit_widget import RedditPosition
from rendering.widget_descriptors import get_factory_widget_descriptors


class _FakeSignal:
    def connect(self, *_args, **_kwargs) -> None:  # pragma: no cover - trivial
        return

    def disconnect(self, *_args, **_kwargs) -> None:  # pragma: no cover - trivial
        return


class _StubSettingsManager:
    """Minimal settings manager that exposes widget config + signal hooks."""

    def __init__(self, widgets_config: dict):
        self._widgets = widgets_config
        self.settings_changed = _FakeSignal()

    def get(self, key: str, default=None):
        if key == 'widgets':
            return self._widgets
        return default

    def get_widgets_map(self):
        return dict(self._widgets)


def _fake_qcolor(value, opacity_override=None):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = tuple(value)
    return (value, opacity_override)


class _BaseStubWidget:
    def __init__(self):
        self.shadow_config = None
        self.raised = False
        self.started = False

    def set_shadow_config(self, config):
        self.shadow_config = config

    def raise_(self):
        self.raised = True

    def start(self):
        self.started = True


class _StubMediaWidget(_BaseStubWidget):
    """Minimal stand-in for MediaWidget to record configuration calls."""

    def __init__(self, parent, position, provider="spotify"):
        super().__init__()
        self.parent = parent
        self.position = position
        self.provider = provider
        self.thread_manager = None
        self.font_family = None
        self.font_size = None
        self.margin = None
        self.artwork_size = None
        self.rounded_artwork = None
        self.show_controls = None
        self.show_header_frame = None
        self.text_color = None
        self.show_background = None
        self.background_color = None
        self.background_border = None
        self.background_opacity = None
        self.provider_runtime = []

    def set_thread_manager(self, thread_manager):
        self.thread_manager = thread_manager

    def set_font_family(self, value):
        self.font_family = value

    def set_font_size(self, value):
        self.font_size = value

    def set_background_opacity(self, value):
        self.background_opacity = value

    def set_margin(self, value):
        self.margin = value

    def set_artwork_size(self, value):
        self.artwork_size = value

    def set_rounded_artwork_border(self, value):
        self.rounded_artwork = value

    def set_show_controls(self, value):
        self.show_controls = value

    def set_show_header_frame(self, value):
        self.show_header_frame = value

    def set_text_color(self, value):
        self.text_color = value

    def set_show_background(self, value):
        self.show_background = value

    def set_background_color(self, value):
        self.background_color = value

    def set_background_border(self, width, color):
        self.background_border = (width, color)

    def set_provider_runtime(self, value):
        self.provider_runtime.append(value)
        self.provider = value


class _StubClockWidget(_BaseStubWidget):
    def __init__(
        self,
        parent,
        time_format,
        position,
        show_seconds,
        timezone_str=None,
        show_timezone=False,
        **_kwargs,
    ):
        super().__init__()
        self.parent = parent
        self.time_format = time_format
        self.position = position
        self.show_seconds = show_seconds
        self.timezone = timezone_str
        self.show_timezone = show_timezone
        self.font_family = None
        self.font_size = None
        self.margin = None
        self.text_color = None
        self.background_color = None
        self.background_border = None
        self.show_background = None
        self.background_opacity = None
        self.display_mode = None
        self.show_numerals = None
        self.analog_face_shadow = None
        self.overlay_name = None
        self.thread_manager = None

    def set_font_family(self, value):
        self.font_family = value

    def set_font_size(self, value):
        self.font_size = value

    def set_margin(self, value):
        self.margin = value

    def set_text_color(self, value):
        self.text_color = value

    def set_background_color(self, value):
        self.background_color = value

    def set_background_border(self, width, color):
        self.background_border = (width, color)

    def set_show_background(self, value):
        self.show_background = value

    def set_background_opacity(self, value):
        self.background_opacity = value

    def set_display_mode(self, value):
        self.display_mode = value

    def set_show_numerals(self, value):
        self.show_numerals = value

    def set_analog_face_shadow(self, value):
        self.analog_face_shadow = value

    def set_overlay_name(self, value):
        self.overlay_name = value

    def set_thread_manager(self, manager):
        self.thread_manager = manager


class _StubWeatherWidget(_BaseStubWidget):
    def __init__(self, parent, location, position):
        super().__init__()
        self.parent = parent
        self.location = location
        self.position = position
        self.thread_manager = None
        self.font_family = None
        self.font_size = None
        self.text_color = None
        self.show_background = None
        self.background_color = None
        self.background_opacity = None
        self.border = None
        self.show_forecast = None
        self.margin = None

    def set_thread_manager(self, manager):
        self.thread_manager = manager

    def set_font_family(self, value):
        self.font_family = value

    def set_font_size(self, value):
        self.font_size = value

    def set_text_color(self, value):
        self.text_color = value

    def set_show_background(self, value):
        self.show_background = value

    def set_background_color(self, value):
        self.background_color = value

    def set_background_opacity(self, value):
        self.background_opacity = value

    def set_background_border(self, width, color):
        self.border = (width, color)

    def set_show_forecast(self, value):
        self.show_forecast = value

    def set_margin(self, value):
        self.margin = value


class _StubRedditWidget(_BaseStubWidget):
    def __init__(self, parent, position):
        super().__init__()
        self.parent = parent
        self.position = position
        self.thread_manager = None
        self.font_family = None
        self.font_size = None
        self.margin = None
        self.header_logo_px_adjust = None
        self.text_color = None
        self.show_background = None
        self.show_separators = None
        self.show_refresh_spiral = None
        self.background_color = None
        self.background_opacity = None
        self.background_border = None
        self.item_limit = None
        self.limit = None
        self.overlay_name = None
        self.subreddit = None

    def set_thread_manager(self, manager):
        self.thread_manager = manager

    def set_font_family(self, value):
        self.font_family = value

    def set_font_size(self, value):
        self.font_size = value

    def set_margin(self, value):
        self.margin = value

    def set_header_logo_px_adjust(self, value):
        self.header_logo_px_adjust = value

    def set_text_color(self, value):
        self.text_color = value

    def set_show_background(self, value):
        self.show_background = value

    def set_show_separators(self, value):
        self.show_separators = value

    def set_show_refresh_spiral(self, value):
        self.show_refresh_spiral = value

    def set_background_color(self, value):
        self.background_color = value

    def set_background_opacity(self, value):
        self.background_opacity = value

    def set_background_border(self, width, color):
        self.background_border = (width, color)

    def set_item_limit(self, value):
        self.item_limit = value
        self.limit = value

    def set_overlay_name(self, value):
        self.overlay_name = value

    def set_subreddit(self, value):
        self.subreddit = value


@pytest.fixture(autouse=True)
def _patch_widget_classes(monkeypatch):
    """Route factory-created widgets to our recording stubs."""

    monkeypatch.setattr("rendering.widget_manager.parse_color_to_qcolor", _fake_qcolor)
    monkeypatch.setattr("rendering.widget_factories.parse_color_to_qcolor", _fake_qcolor)
    monkeypatch.setattr("widgets.media_widget.MediaWidget", _StubMediaWidget)
    monkeypatch.setattr("widgets.clock_widget.ClockWidget", _StubClockWidget)
    monkeypatch.setattr("widgets.weather_widget.WeatherWidget", _StubWeatherWidget)
    monkeypatch.setattr("widgets.reddit_widget.RedditWidget", _StubRedditWidget)
    monkeypatch.setattr(
        WidgetManager,
        "create_spotify_volume_widget",
        lambda self, *args, **kwargs: None,
    )
    monkeypatch.setattr(
        WidgetManager,
        "create_spotify_visualizer_widget",
        lambda self, *args, **kwargs: None,
    )


def _create_manager():
    parent = SimpleNamespace()
    return WidgetManager(parent, ResourceManager())


def _setup_widgets(widgets_config: dict):
    manager = _create_manager()
    settings = _StubSettingsManager(widgets_config)
    created = manager.setup_all_widgets(settings, screen_index=0, thread_manager=None)
    return manager, created


def test_media_widget_creation_handles_prefixed_positions():
    widgets_config = {
        "media": {
            "enabled": True,
            "monitor": "ALL",
            "position": "WidgetPosition.TOP_CENTER",
            "font_family": "Inter",
            "font_size": 42,
            "margin": 15,
            "artwork_size": 180,
            "rounded_artwork_border": False,
            "show_controls": False,
            "show_header_frame": False,
            "color": [10, 20, 30, 255],
            "bg_color": [1, 2, 3, 4],
            "bg_opacity": 0.8,
            "show_background": True,
            "border_color": [5, 6, 7, 128],
            "border_opacity": 0.5,
        },
        "shadows": {
            "enabled": True,
            "blur_radius": 18,
            "offset": [4, 4],
            "color": [0, 0, 0, 255],
            "frame_opacity": 0.7,
            "text_opacity": 0.3,
        },
    }

    _manager, created = _setup_widgets(widgets_config)
    widget = created['media_widget']

    assert isinstance(widget, _StubMediaWidget)
    assert widget.position == MediaPosition.TOP_CENTER
    assert widget.margin == 15
    assert widget.show_controls is False
    assert widget.background_border[0] >= 1
    assert widget.background_border[1] == (tuple([5, 6, 7, 128]), 0.5)
    assert widget.shadow_config == widgets_config["shadows"]
    assert widget.raised is True
    assert widget.started is True


def test_existing_media_widget_rebinds_thread_manager():
    """Reused media widgets should inherit the display's ThreadManager."""

    old_tm = object()
    new_tm = object()

    existing = _StubMediaWidget(parent=None, position=MediaPosition.BOTTOM_LEFT)
    existing.thread_manager = old_tm

    parent = SimpleNamespace(
        media_widget=existing,
        _thread_manager=new_tm,
        screen_index=0,
    )

    manager = WidgetManager(parent, ResourceManager())
    settings = _StubSettingsManager({
        "media": {
            "enabled": True,
            "monitor": "ALL",
        }
    })

    created = manager.setup_all_widgets(settings, screen_index=0, thread_manager=None)

    assert created["media_widget"] is existing
    assert existing.thread_manager is new_tm


def test_clock_widget_creation_handles_prefixed_positions():
    widgets_config = {
        "clock": {
            "enabled": True,
            "monitor": "ALL",
            "position": "WidgetPosition.BOTTOM_CENTER",
            "font_family": "Segoe UI",
            "font_size": 60,
            "margin": 25,
            "color": [1, 2, 3, 255],
            "bg_color": [9, 9, 9, 255],
            "border_color": [4, 4, 4, 255],
            "border_opacity": 0.7,
            "show_background": True,
            "bg_opacity": 0.85,
            "display_mode": "analog",
            "show_numerals": False,
            "analog_face_shadow": True,
            "timezone": "UTC",
        },
        "shadows": {"enabled": True},
    }

    _manager, created = _setup_widgets(widgets_config)
    widget = created['clock_widget']

    assert isinstance(widget, _StubClockWidget)
    assert widget.position == ClockPosition.BOTTOM_CENTER
    assert widget.font_family == "Segoe UI"
    assert widget.font_size == 60
    assert widget.margin == 25
    assert widget.display_mode == "analog"
    assert widget.show_numerals is False


def test_weather_widget_creation_handles_prefixed_positions():
    widgets_config = {
        "weather": {
            "enabled": True,
            "monitor": "ALL",
            "position": "WidgetPosition.MIDDLE_RIGHT",
            "location": "Berlin",
            "font_family": "Inter",
            "font_size": 30,
            "color": [5, 5, 5, 255],
            "show_background": True,
            "bg_color": [1, 1, 1, 255],
            "bg_opacity": 0.75,
            "border_color": [2, 2, 2, 255],
            "border_opacity": 0.9,
            "margin": 10,
            "show_forecast": True,
        },
        "shadows": {"enabled": True},
    }

    _manager, created = _setup_widgets(widgets_config)
    widget = created['weather_widget']

    assert isinstance(widget, _StubWeatherWidget)
    assert widget.position == WeatherPosition.MIDDLE_RIGHT
    assert widget.location == "Berlin"
    assert widget.font_size == 30
    assert widget.margin == 10
    assert widget.background_opacity == 0.75
    assert widget.raised is True
    assert widget.started is True


def test_reddit_widgets_support_inheritance_and_limit():
    widgets_config = {
        "reddit": {
            "enabled": True,
            "monitor": "ALL",
            "position": "WidgetPosition.TOP_LEFT",
            "subreddit": "all",
            "font_family": "Inter",
            "font_size": 18,
            "margin": 12,
            "header_logo_px_adjust": 5,
            "color": [255, 255, 255, 255],
            "bg_color": [0, 0, 0, 255],
            "border_color": [50, 50, 50, 255],
            "border_opacity": 0.5,
            "show_background": True,
            "show_separators": True,
            "show_refresh_spiral": False,
            "limit": 9,
        },
        "reddit2": {
            "enabled": True,
            "monitor": "ALL",
            "position": "WidgetPosition.BOTTOM_RIGHT",
            "subreddit": "python",
            "limit": 4,
        },
        "shadows": {"enabled": True},
    }

    _manager, created = _setup_widgets(widgets_config)
    widget = created['reddit_widget']
    widget2 = created['reddit2_widget']

    assert isinstance(widget, _StubRedditWidget)
    assert widget.position == RedditPosition.TOP_LEFT
    assert widget.subreddit == "all"
    assert widget.font_size == 18
    assert widget.margin == 12
    assert widget.header_logo_px_adjust == 5
    assert widget.show_refresh_spiral is False
    assert widget.item_limit == 9
    assert widget.raised is True
    assert widget.started is True

    assert isinstance(widget2, _StubRedditWidget)
    assert widget2.position == RedditPosition.BOTTOM_RIGHT
    assert widget2.subreddit == "python"
    assert widget2.item_limit == 5
    # inherits styling from reddit1
    assert widget2.font_family == "Inter"
    assert widget2.header_logo_px_adjust == 5
    assert widget2.show_refresh_spiral is False
    assert widget2.text_color == (tuple([255, 255, 255, 255]), None)
    assert widget2.raised is True
    assert widget2.started is True


def test_factory_widget_descriptors_cover_factory_backed_widget_families():
    descriptors = get_factory_widget_descriptors()
    descriptor_names = [descriptor.settings_key for descriptor in descriptors]

    expected = [
        "clock",
        "clock2",
        "clock3",
        "weather",
        "media",
        "reddit",
        "reddit2",
        "gmail",
    ]
    if any(descriptor.settings_key == "imgur" for descriptor in descriptors):
        expected.insert(7, "imgur")

    assert descriptor_names == expected

    gmail = next(descriptor for descriptor in descriptors if descriptor.settings_key == "gmail")
    reddit2 = next(descriptor for descriptor in descriptors if descriptor.settings_key == "reddit2")
    clock2 = next(descriptor for descriptor in descriptors if descriptor.settings_key == "clock2")

    assert gmail.inject_shadows_into_config is True
    assert reddit2.base_settings_key == "reddit"
    assert reddit2.base_settings_kwarg == "base_reddit_settings"
    assert clock2.base_settings_key == "clock"
    assert clock2.overlay_name == "clock2"


def test_setup_all_widgets_routes_gmail_through_descriptor_shadow_injection(monkeypatch):
    manager = _create_manager()
    settings = _StubSettingsManager({
        "gmail": {
            "enabled": True,
            "monitor": "ALL",
        },
        "shadows": {
            "enabled": True,
            "blur_radius": 19,
        },
    })

    captured: dict = {}

    class _StubGmailWidget(_BaseStubWidget):
        def set_thread_manager(self, *_args, **_kwargs):
            return

    def _fake_create(self, parent, config):
        captured["config"] = dict(config)
        return _StubGmailWidget()

    monkeypatch.setattr("rendering.widget_factories.GmailWidgetFactory.create", _fake_create)

    created = manager.setup_all_widgets(settings, screen_index=0, thread_manager=None)

    assert "gmail_widget" in created
    assert captured["config"]["_shadows_config"] == {"enabled": True, "blur_radius": 19}


def test_setup_all_widgets_runs_spotify_setup_phases_in_explicit_order(monkeypatch):
    from rendering import widget_setup_all

    manager = _create_manager()
    settings = _StubSettingsManager(
        {
            "media": {"enabled": True, "monitor": "ALL"},
            "spotify_visualizer": {"enabled": True, "monitor": "ALL"},
        }
    )

    phase_calls: list[str] = []

    monkeypatch.setattr(
        widget_setup_all,
        "_create_factory_widgets",
        lambda mgr, created, widgets_config, shadows_config, screen_index: (
            phase_calls.append("factory"),
            created.__setitem__("media_widget", _StubMediaWidget(mgr._parent, MediaPosition.TOP_LEFT)),
        )[-1],
    )
    monkeypatch.setattr(
        widget_setup_all,
        "_setup_media_owned_spotify_dependents",
        lambda *args, **kwargs: phase_calls.append("spotify_media_owned_dependents"),
    )
    monkeypatch.setattr(
        widget_setup_all,
        "_setup_spotify_visualizer",
        lambda *args, **kwargs: phase_calls.append("spotify_visualizer_local"),
    )
    monkeypatch.setattr(
        widget_setup_all,
        "_reconcile_remote_custom_visualizer",
        lambda *args, **kwargs: phase_calls.append("spotify_visualizer_remote_reconcile"),
    )
    monkeypatch.setattr(
        widget_setup_all,
        "_finalize_widget_startup",
        lambda mgr, created: phase_calls.append("finalize"),
    )

    widget_setup_all.setup_all_widgets(manager, settings, screen_index=0, thread_manager=None)

    assert phase_calls == [
        "factory",
        "spotify_media_owned_dependents",
        "spotify_visualizer_local",
        "spotify_visualizer_remote_reconcile",
        "finalize",
    ]


def test_finalize_widget_startup_reapplies_saved_custom_layouts_after_startup(monkeypatch):
    from rendering import widget_setup_all

    class _Parent:
        def __init__(self):
            self.apply_calls: list[str] = []
            self._custom_layout_runtime_stabilize_pending = False

        def _apply_saved_custom_layouts(self):
            self.apply_calls.append("apply")

    class _Widget:
        def __init__(self):
            self.raised = 0

        def raise_(self):
            self.raised += 1

    parent = _Parent()
    manager = SimpleNamespace(_parent=parent, _fade_coordinator=SimpleNamespace(describe=lambda: {"participants": []}))
    created = {"reddit_widget": _Widget()}
    startup_calls: list[str] = []
    deferred_calls: list[int] = []

    monkeypatch.setattr(widget_setup_all, "_start_widgets", lambda widgets: startup_calls.append("start"))
    monkeypatch.setattr(
        widget_setup_all.QTimer,
        "singleShot",
        lambda delay, callback: (deferred_calls.append(delay), callback()),
    )

    widget_setup_all._finalize_widget_startup(manager, created)

    assert startup_calls == ["start"]
    assert parent.apply_calls == ["apply", "apply", "apply"]
    assert deferred_calls == [0]
    assert created["reddit_widget"].raised == 1


def test_reconcile_remote_custom_visualizer_reapplies_saved_layouts_after_secondary_start(monkeypatch):
    from PySide6.QtCore import QRect
    from rendering import widget_setup_all
    from rendering import spotify_display_participation as display_participation

    class _Overlay:
        def __init__(self):
            self._geometry = QRect(0, 0, 100, 400)
            self.history = [QRect(self._geometry)]

        def setGeometry(self, rect):
            self._geometry = QRect(rect)
            self.history.append(QRect(self._geometry))

        def geometry(self):
            return QRect(self._geometry)

    class _Visualizer:
        def __init__(self):
            self._geometry = QRect(0, 0, 100, 400)
            self.geometry_history = [QRect(self._geometry)]
            self.raised = 0
            self._custom_layout_local_rect = QRect(700, 520, 420, 280)

        def setGeometry(self, rect):
            target = QRect(rect)
            custom_rect = getattr(self, "_custom_layout_local_rect", None)
            if isinstance(custom_rect, QRect) and custom_rect.width() > 0 and custom_rect.height() > 0:
                target = QRect(custom_rect)
            self._geometry = QRect(target)
            self.geometry_history.append(QRect(self._geometry))

        def geometry(self):
            return QRect(self._geometry)

        def raise_(self):
            self.raised += 1

    class _TargetManager:
        def __init__(self, target):
            self._target = target
            self.registered = []

        def create_spotify_visualizer_widget(self, *args, **kwargs):
            vis = _Visualizer()
            self._target.spotify_visualizer_widget = vis
            return vis

        def _register_spotify_secondary_fade(self, widget):
            self.registered.append(widget)

    class _TargetDisplay:
        def __init__(self):
            self.screen_index = 1
            self.media_widget = object()
            self.spotify_visualizer_widget = None
            self._spotify_bars_overlay = _Overlay()
            self._widget_manager = _TargetManager(self)
            self._screen = SimpleNamespace(
                geometry=lambda: SimpleNamespace(
                    isValid=lambda: True,
                    width=lambda: 1920,
                    height=lambda: 1080,
                )
            )
            self._exiting = False
            self.apply_calls = 0

        def _apply_saved_custom_layouts(self):
            self.apply_calls += 1
            vis = self.spotify_visualizer_widget
            if vis is not None:
                rect = QRect(700, 520, 420, 280)
                vis.setGeometry(rect)
                self._spotify_bars_overlay.setGeometry(rect)

    source_display = SimpleNamespace(
        screen_index=0,
        _screen=SimpleNamespace(
            geometry=lambda: SimpleNamespace(
                isValid=lambda: True,
                width=lambda: 1920,
                height=lambda: 1080,
            )
        ),
        _widget_manager=object(),
        _exiting=False,
    )
    target_display = _TargetDisplay()

    class _Coordinator:
        def get_all_instances(self):
            return [source_display, target_display]

    monkeypatch.setattr(widget_setup_all, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(display_participation, "get_coordinator", lambda: _Coordinator())

    def _simulate_start(_widgets):
        vis = target_display.spotify_visualizer_widget
        assert vis is not None
        vis.setGeometry(QRect(0, 0, 357, 357))
        target_display._spotify_bars_overlay.setGeometry(QRect(0, 0, 357, 357))

    monkeypatch.setattr(widget_setup_all, "_start_widgets", _simulate_start)

    widget_setup_all._reconcile_remote_custom_visualizer(
        SimpleNamespace(_parent=source_display),
        {
            "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
        },
        shadows_config={},
        screen_index=0,
        thread_manager=None,
        media_widget=object(),
    )

    vis = target_display.spotify_visualizer_widget
    assert vis is not None
    assert target_display.apply_calls >= 2, (
        "Remote CUSTOM visualizer reconcile must reapply committed layouts "
        "again after secondary-stage startup pressure."
    )
    assert vis.geometry() == QRect(700, 520, 420, 280)
    assert target_display._spotify_bars_overlay.geometry() == QRect(700, 520, 420, 280)
    assert QRect(0, 0, 357, 357) not in vis.geometry_history, (
        "Remote CUSTOM visualizer startup must not accept a square fallback rect "
        "once the committed startup rect has been attached."
    )
    assert QRect(0, 0, 357, 357) in target_display._spotify_bars_overlay.history


def test_reconcile_remote_custom_visualizer_falls_back_to_participating_display_when_requested_target_is_absent(monkeypatch, caplog):
    import logging

    from rendering import widget_setup_all
    from rendering import spotify_display_participation as display_participation

    class _Visualizer:
        def raise_(self):
            return None

    class _TargetManager:
        def __init__(self, target):
            self._target = target
            self.registered = []

        def create_spotify_visualizer_widget(self, *args, **kwargs):
            vis = _Visualizer()
            self._target.spotify_visualizer_widget = vis
            return vis

        def _register_spotify_secondary_fade(self, widget):
            self.registered.append(widget)

    class _Display:
        def __init__(self, screen_index, *, participating=True):
            self.screen_index = screen_index
            self.media_widget = object()
            self.spotify_visualizer_widget = None
            self._screen = SimpleNamespace(
                geometry=lambda: SimpleNamespace(
                    isValid=lambda: True,
                    width=lambda: 1920,
                    height=lambda: 1080,
                )
            )
            self._exiting = not participating
            self._widget_manager = _TargetManager(self) if participating else None
            self.apply_calls = 0

        def _apply_saved_custom_layouts(self):
            self.apply_calls += 1

    source_display = _Display(0, participating=True)
    class _Coordinator:
        def get_all_instances(self):
            return [source_display]

    monkeypatch.setattr(widget_setup_all, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(display_participation, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(widget_setup_all, "_start_widgets", lambda _widgets: None)
    mgr = SimpleNamespace(_parent=source_display)

    widgets_config = {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
    }

    with caplog.at_level(logging.WARNING):
        widget_setup_all._reconcile_remote_custom_visualizer(
            mgr,
            widgets_config,
            shadows_config={},
            screen_index=0,
            thread_manager=None,
            media_widget=object(),
        )

    assert source_display.spotify_visualizer_widget is not None, (
        "If the requested CUSTOM monitor is not participating in the active "
        "display/compositor set, remote reconcile must choose a participating "
        "display owner instead of spawning into an unseen target."
    )
    assert "Requested CUSTOM monitor 1 is not participating" in caplog.text
    assert "[SPOTIFY_VIS][FALLBACK]" in caplog.text


def test_reconcile_remote_custom_visualizer_defers_fallback_when_requested_target_is_temporarily_unavailable_but_recovers(monkeypatch, caplog):
    import logging

    from rendering import widget_setup_all
    from rendering import spotify_display_participation as display_participation

    scheduled_calls: list[tuple[int, object]] = []
    class _Visualizer:
        def raise_(self):
            return None

    class _TargetManager:
        def __init__(self, target):
            self._target = target
            self.registered = []

        def create_spotify_visualizer_widget(self, *args, **kwargs):
            vis = _Visualizer()
            self._target.spotify_visualizer_widget = vis
            return vis

        def _register_spotify_secondary_fade(self, widget):
            self.registered.append(widget)

    class _Display:
        def __init__(self, screen_index, *, awake):
            self.screen_index = screen_index
            self.media_widget = object()
            self.spotify_visualizer_widget = None
            self.awake = bool(awake)
            self._exiting = False
            self._widget_manager = _TargetManager(self)
            self.apply_calls = 0

        @property
        def _screen(self):
            if self.awake:
                return SimpleNamespace(
                    geometry=lambda: SimpleNamespace(
                        isValid=lambda: True,
                        width=lambda: 1920,
                        height=lambda: 1080,
                    )
                )
            return SimpleNamespace(
                geometry=lambda: SimpleNamespace(
                    isValid=lambda: False,
                    width=lambda: 0,
                    height=lambda: 0,
                )
            )

        def _apply_saved_custom_layouts(self):
            self.apply_calls += 1

    source_display = _Display(0, awake=True)
    waking_target_display = _Display(1, awake=False)

    class _Coordinator:
        def get_all_instances(self):
            return [source_display, waking_target_display]

    def _capture_single_shot(delay_ms, callback, *args):
        def _invoke(_callback=callback, _args=args):
            _callback(*_args)

        scheduled_calls.append((int(delay_ms), _invoke))

    monkeypatch.setattr(widget_setup_all, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(display_participation, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(widget_setup_all.ThreadManager, "single_shot", _capture_single_shot)
    monkeypatch.setattr(widget_setup_all, "_start_widgets", lambda _widgets: None)
    mgr = SimpleNamespace(_parent=source_display)
    widgets_config = {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
    }

    with caplog.at_level(logging.WARNING):
        widget_setup_all._reconcile_remote_custom_visualizer(
            mgr,
            widgets_config,
            shadows_config={},
            screen_index=0,
            thread_manager=None,
            media_widget=object(),
        )

    assert source_display.spotify_visualizer_widget is None
    assert waking_target_display.spotify_visualizer_widget is None
    assert len(scheduled_calls) == 1
    assert scheduled_calls[0][0] == widget_setup_all.REMOTE_CUSTOM_VISUALIZER_FALLBACK_RECHECK_MS
    assert "delaying fallback recheck" in caplog.text

    waking_target_display.awake = True
    resolution = display_participation.describe_visualizer_spawn_display(
        1,
        current_display=source_display,
    )
    assert source_display.spotify_visualizer_widget is None
    assert waking_target_display.spotify_visualizer_widget is None
    assert resolution.requested_is_participating is True, (
        "Once the requested runtime display wakes back up, the cautious recheck should see it as the "
        "real owner again rather than keeping fallback pressure on another display."
    )
    assert resolution.chosen_display is waking_target_display
    assert resolution.fallback_display is None


def test_reconcile_remote_custom_visualizer_falls_back_after_delayed_recheck_when_requested_target_stays_unavailable(monkeypatch, caplog):
    import logging

    from rendering import widget_setup_all
    from rendering import spotify_display_participation as display_participation

    create_calls: list[int] = []

    class _Visualizer:
        def raise_(self):
            return None

    class _TargetManager:
        def __init__(self, target):
            self._target = target
            self.registered = []

        def create_spotify_visualizer_widget(self, *args, **kwargs):
            vis = _Visualizer()
            self._target.spotify_visualizer_widget = vis
            return vis

        def _register_spotify_secondary_fade(self, widget):
            self.registered.append(widget)

    class _Display:
        def __init__(self, screen_index, *, awake):
            self.screen_index = screen_index
            self.media_widget = object()
            self.spotify_visualizer_widget = None
            self.awake = bool(awake)
            self._exiting = False
            self._widget_manager = _TargetManager(self)
            self.apply_calls = 0

        @property
        def _screen(self):
            if self.awake:
                return SimpleNamespace(
                    geometry=lambda: SimpleNamespace(
                        isValid=lambda: True,
                        width=lambda: 1920,
                        height=lambda: 1080,
                    )
                )
            return SimpleNamespace(
                geometry=lambda: SimpleNamespace(
                    isValid=lambda: False,
                    width=lambda: 0,
                    height=lambda: 0,
                )
            )

        def _apply_saved_custom_layouts(self):
            self.apply_calls += 1

    source_display = _Display(0, awake=True)
    sleeping_target_display = _Display(1, awake=False)

    class _Coordinator:
        def get_all_instances(self):
            return [source_display, sleeping_target_display]

    def _record_create(target, widgets_config, shadows_config, target_screen_index, thread_manager):
        create_calls.append(int(getattr(target, "screen_index", -1)))
        target.spotify_visualizer_widget = _Visualizer()

    monkeypatch.setattr(widget_setup_all, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(display_participation, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(widget_setup_all, "_create_remote_custom_visualizer_on_target", _record_create)
    monkeypatch.setattr(widget_setup_all, "_start_widgets", lambda _widgets: None)
    mgr = SimpleNamespace(_parent=source_display)
    mgr._remote_custom_visualizer_reconcile_token = 1

    widgets_config = {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
    }

    with caplog.at_level(logging.WARNING):
        widget_setup_all._run_remote_custom_visualizer_fallback_recheck(
            mgr,
            widgets_config,
            {},
            0,
            None,
            object(),
            1,
            1,
        )

    assert create_calls == [0]
    assert source_display.spotify_visualizer_widget is not None, (
        "If the requested runtime display still is not participating after the cautious recheck, "
        "the last-resort fallback should restore one visible owner on a participating display."
    )
    assert sleeping_target_display.spotify_visualizer_widget is None
    assert "still not participating after" in caplog.text


def test_reconcile_remote_custom_visualizer_rejects_foreign_saved_rect_when_requested_target_is_absent(monkeypatch, caplog):
    import logging

    from PySide6.QtCore import QRect
    from rendering import widget_setup_all
    from rendering import spotify_display_participation as display_participation
    from rendering import spotify_widget_creators as creators

    class _Visualizer:
        def __init__(self):
            self._geometry = QRect(0, 0, 357, 357)
            self.geometry_history = [QRect(self._geometry)]
            self._minimum_size = (0, 0)
            self._maximum_size = (16777215, 16777215)

        def setGeometry(self, rect):
            self._geometry = QRect(rect)
            self.geometry_history.append(QRect(self._geometry))

        def geometry(self):
            return QRect(self._geometry)

        def setMinimumWidth(self, value):
            self._minimum_size = (int(value), self._minimum_size[1])

        def setMaximumWidth(self, value):
            self._maximum_size = (int(value), self._maximum_size[1])

        def setMinimumHeight(self, value):
            self._minimum_size = (self._minimum_size[0], int(value))

        def setMaximumHeight(self, value):
            self._maximum_size = (self._maximum_size[0], int(value))

        def minimumWidth(self):
            return int(self._minimum_size[0])

        def maximumWidth(self):
            return int(self._maximum_size[0])

        def minimumHeight(self):
            return int(self._minimum_size[1])

        def maximumHeight(self):
            return int(self._maximum_size[1])

        def _apply_custom_layout_size_constraints_if_active(self):
            rect = getattr(self, "_custom_layout_local_rect", None)
            if not isinstance(rect, QRect):
                return False
            self.setMinimumWidth(rect.width())
            self.setMaximumWidth(rect.width())
            self.setMinimumHeight(rect.height())
            self.setMaximumHeight(rect.height())
            return True

        def raise_(self):
            return None

    class _TargetManager:
        def __init__(self, target):
            self._target = target
            self.registered = []
            self._parent = target
            self._widgets = {}
            self._settings_manager = None

        def create_spotify_visualizer_widget(self, *args, **kwargs):
            vis = creators.create_spotify_visualizer_widget(self, *args, **kwargs)
            self._target.spotify_visualizer_widget = vis
            return vis

        def _register_spotify_secondary_fade(self, widget):
            self.registered.append(widget)

        def _log_spotify_vis_config(self, *args, **kwargs):
            return None

        def register_widget(self, name, widget):
            self._widgets[name] = widget

        def _bind_parent_attribute(self, name, widget):
            setattr(self._target, name, widget)

        def _refresh_spotify_visualizer_config(self, payload=None):
            return None

    class _Display:
        def __init__(self, screen_index, *, participating=True):
            self.screen_index = screen_index
            self.media_widget = object()
            self.spotify_visualizer_widget = None
            self._screen = SimpleNamespace(
                geometry=lambda: QRect(0, 0, 1920, 1080)
            )
            self._exiting = not participating
            self._widget_manager = _TargetManager(self) if participating else None
            self.apply_calls = 0

        def _apply_saved_custom_layouts(self):
            self.apply_calls += 1

    source_display = _Display(0, participating=True)
    class _Coordinator:
        def get_all_instances(self):
            return [source_display]

    monkeypatch.setattr(widget_setup_all, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(display_participation, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(creators, "SpotifyVisualizerWidget", lambda *args, **kwargs: _Visualizer())
    monkeypatch.setattr(creators, "parse_color_to_qcolor", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(creators, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(widget_setup_all, "_start_widgets", lambda _widgets: None)
    monkeypatch.setattr(widget_setup_all.ThreadManager, "single_shot", lambda *args, **kwargs: None)
    mgr = SimpleNamespace(_parent=source_display)

    with caplog.at_level(logging.WARNING):
        widget_setup_all._reconcile_remote_custom_visualizer(
            mgr,
            {
                "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
                "custom_layout": {
                    "version": 1,
                    "displays": {
                        "screen:missing-monitor": {
                            "spotify_visualizer": {
                                "rect": {"x": 0.108, "y": 0.287, "width": 0.219, "height": 0.259},
                                "size_payload": {"width": 420, "height": 280},
                                "resize_mode": "visualizer_rect",
                            }
                        }
                    },
                },
            },
            shadows_config={},
            screen_index=0,
            thread_manager=None,
            media_widget=object(),
        )

    vis = source_display.spotify_visualizer_widget
    assert vis is None
    assert "foreign-bucket geometry priming rejected" in caplog.text
    assert "Suppressing CUSTOM visualizer creation because no exact local custom rect is available" in caplog.text
    assert "[SPOTIFY_VIS][FALLBACK]" in caplog.text


def test_reconcile_remote_custom_visualizer_repairs_single_foreign_rect_when_active_target_signature_changes(monkeypatch, caplog):
    import logging

    from PySide6.QtCore import QRect
    from rendering import widget_setup_all
    from rendering import spotify_display_participation as display_participation
    from rendering import spotify_widget_creators as creators

    class _Visualizer:
        def __init__(self):
            self._geometry = QRect(0, 0, 357, 357)
            self.geometry_history = [QRect(self._geometry)]
            self._minimum_size = (0, 0)
            self._maximum_size = (16777215, 16777215)

        def setGeometry(self, rect):
            self._geometry = QRect(rect)
            self.geometry_history.append(QRect(self._geometry))

        def geometry(self):
            return QRect(self._geometry)

        def setMinimumWidth(self, value):
            self._minimum_size = (int(value), self._minimum_size[1])

        def setMaximumWidth(self, value):
            self._maximum_size = (int(value), self._maximum_size[1])

        def setMinimumHeight(self, value):
            self._minimum_size = (self._minimum_size[0], int(value))

        def setMaximumHeight(self, value):
            self._maximum_size = (self._maximum_size[0], int(value))

        def minimumWidth(self):
            return int(self._minimum_size[0])

        def maximumWidth(self):
            return int(self._maximum_size[0])

        def minimumHeight(self):
            return int(self._minimum_size[1])

        def maximumHeight(self):
            return int(self._maximum_size[1])

        def _apply_custom_layout_size_constraints_if_active(self):
            rect = getattr(self, "_custom_layout_local_rect", None)
            if not isinstance(rect, QRect):
                return False
            self.setMinimumWidth(rect.width())
            self.setMaximumWidth(rect.width())
            self.setMinimumHeight(rect.height())
            self.setMaximumHeight(rect.height())
            return True

        def raise_(self):
            return None

    class _TargetManager:
        def __init__(self, target):
            self._target = target
            self.registered = []
            self._parent = target
            self._widgets = {}
            self._settings_manager = None

        def create_spotify_visualizer_widget(self, *args, **kwargs):
            vis = creators.create_spotify_visualizer_widget(self, *args, **kwargs)
            self._target.spotify_visualizer_widget = vis
            return vis

        def _register_spotify_secondary_fade(self, widget):
            self.registered.append(widget)

        def _log_spotify_vis_config(self, *args, **kwargs):
            return None

        def register_widget(self, name, widget):
            self._widgets[name] = widget

        def _bind_parent_attribute(self, name, widget):
            setattr(self._target, name, widget)

        def _refresh_spotify_visualizer_config(self, payload=None):
            return None

    class _Display:
        def __init__(self, screen_index):
            self.screen_index = screen_index
            self.media_widget = object()
            self.spotify_visualizer_widget = None
            self._screen = SimpleNamespace(
                geometry=lambda: QRect(0, 0, 1920, 1080)
            )
            self._exiting = False
            self._widget_manager = _TargetManager(self)
            self.apply_calls = 0

        def _apply_saved_custom_layouts(self):
            self.apply_calls += 1

    source_display = _Display(0)
    target_display = _Display(1)

    class _Coordinator:
        def get_all_instances(self):
            return [source_display, target_display]

    monkeypatch.setattr(widget_setup_all, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(display_participation, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(creators, "SpotifyVisualizerWidget", lambda *args, **kwargs: _Visualizer())
    monkeypatch.setattr(creators, "parse_color_to_qcolor", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(creators, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(widget_setup_all, "_start_widgets", lambda _widgets: None)
    monkeypatch.setattr(widget_setup_all.ThreadManager, "single_shot", lambda *args, **kwargs: None)

    widgets_config = {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
        "custom_layout": {
            "version": 1,
            "displays": {
                "screen:stale-signature": {
                    "spotify_visualizer": {
                        "rect": {"x": 0.108, "y": 0.287, "width": 0.219, "height": 0.259},
                        "size_payload": {"width": 420, "height": 280},
                        "resize_mode": "visualizer_rect",
                    }
                }
            },
        },
    }
    with caplog.at_level(logging.WARNING):
        widget_setup_all._reconcile_remote_custom_visualizer(
            SimpleNamespace(_parent=source_display),
            widgets_config,
            shadows_config={},
            screen_index=0,
            thread_manager=None,
            media_widget=object(),
        )

    vis = target_display.spotify_visualizer_widget
    assert vis is not None
    assert vis.geometry() == QRect(207, 310, 420, 280)
    displays = widgets_config["custom_layout"]["displays"]
    assert "screen:stale-signature" not in displays
    assert any("spotify_visualizer" in layouts for layouts in displays.values())
    assert "Repaired spotify_visualizer CUSTOM rect bucket from single foreign saved rect" in caplog.text
    assert "[SPOTIFY_VIS][FALLBACK]" in caplog.text


def test_visualizer_custom_route_recovers_from_single_live_foreign_rect_instead_of_moving_it(monkeypatch, caplog):
    import logging

    from rendering import spotify_widget_creators as creators

    class _Display:
        def __init__(self, screen_index, signature):
            self.screen_index = screen_index
            self._screen = SimpleNamespace(signature=signature)
            self._exiting = False

    display_0 = _Display(0, "screen:display-0")
    display_1 = _Display(1, "screen:display-1")

    class _Coordinator:
        def get_all_instances(self):
            return [display_0, display_1]

    widgets_config = {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                "screen:display-1": {
                    "spotify_visualizer": {
                        "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
                    }
                }
            },
        },
    }
    monkeypatch.setattr(creators, "get_coordinator", lambda: _Coordinator())
    monkeypatch.setattr(creators, "_resolve_parent_screen", lambda parent: getattr(parent, "_screen", parent))
    monkeypatch.setattr(
        creators,
        "resolve_screen_layout_signature",
        lambda _custom_layout_map, screen: getattr(screen, "signature", None),
    )

    with caplog.at_level(logging.WARNING):
        recovered = creators._recover_visualizer_custom_monitor_from_single_live_saved_rect(
            SimpleNamespace(_settings_manager=None),
            widgets_config,
            effective_monitor_sel="1",
        )

    assert recovered == "2"
    assert widgets_config["spotify_visualizer"]["monitor"] == "2"
    assert "screen:display-1" in widgets_config["custom_layout"]["displays"]
    assert "screen:display-0" not in widgets_config["custom_layout"]["displays"]
    assert "Recovered spotify_visualizer CUSTOM route from sole live saved rect" in caplog.text


def test_visualizer_custom_foreign_bucket_repair_rejects_ambiguous_rects(monkeypatch, caplog):
    import logging

    from rendering import spotify_widget_creators as creators

    widgets_config = {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
        "custom_layout": {
            "version": 1,
            "displays": {
                "screen:old-a": {
                    "spotify_visualizer": {
                        "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
                    }
                },
                "screen:old-b": {
                    "spotify_visualizer": {
                        "rect": {"x": 0.4, "y": 0.3, "width": 0.2, "height": 0.1},
                    }
                },
            },
        },
    }
    monkeypatch.setattr(creators, "_resolve_parent_screen", lambda _parent: object())
    monkeypatch.setattr(
        creators,
        "get_screen_layout_entries_for_screen",
        lambda custom_layout_map, _screen: ("screen:live", custom_layout_map["displays"].get("screen:live", {})),
    )
    monkeypatch.setattr(
        creators,
        "canonicalize_screen_layout_bucket",
        lambda custom_layout_map, _screen: custom_layout_map["displays"].setdefault("screen:live", {}) and "screen:live",
    )
    mgr = SimpleNamespace(_parent=SimpleNamespace(screen_index=1), _settings_manager=None)

    with caplog.at_level(logging.WARNING):
        repaired = creators._repair_single_foreign_visualizer_custom_rect_for_startup(
            mgr,
            widgets_config,
            screen_index=1,
            effective_monitor_sel="2",
        )

    assert repaired is False
    assert "screen:old-a" in widgets_config["custom_layout"]["displays"]
    assert "screen:old-b" in widgets_config["custom_layout"]["displays"]
    assert "screen:live" not in widgets_config["custom_layout"]["displays"]
    assert "Repaired spotify_visualizer CUSTOM rect bucket" not in caplog.text


def test_visualizer_custom_foreign_bucket_repair_rejects_parent_monitor_mismatch(monkeypatch):
    from rendering import spotify_widget_creators as creators

    widgets_config = {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
        "custom_layout": {
            "version": 1,
            "displays": {
                "screen:old": {
                    "spotify_visualizer": {
                        "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
                    }
                },
            },
        },
    }
    monkeypatch.setattr(creators, "_resolve_parent_screen", lambda _parent: object())
    mgr = SimpleNamespace(_parent=SimpleNamespace(screen_index=0), _settings_manager=None)

    repaired = creators._repair_single_foreign_visualizer_custom_rect_for_startup(
        mgr,
        widgets_config,
        screen_index=1,
        effective_monitor_sel="2",
    )

    assert repaired is False
    assert "screen:old" in widgets_config["custom_layout"]["displays"]


def test_visualizer_custom_foreign_bucket_repair_refuses_active_source_bucket(monkeypatch, caplog):
    import logging

    from rendering import spotify_widget_creators as creators

    widgets_config = {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                "screen:display-1": {
                    "spotify_visualizer": {
                        "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
                    }
                },
            },
        },
    }
    monkeypatch.setattr(creators, "_resolve_parent_screen", lambda _parent: object())
    monkeypatch.setattr(
        creators,
        "get_screen_layout_entries_for_screen",
        lambda custom_layout_map, _screen: ("screen:display-0", custom_layout_map["displays"].get("screen:display-0", {})),
    )
    monkeypatch.setattr(
        creators,
        "_live_visualizer_bucket_monitor_map",
        lambda _custom_layout_map: {"screen:display-1": "2"},
    )
    mgr = SimpleNamespace(_parent=SimpleNamespace(screen_index=0), _settings_manager=None)

    with caplog.at_level(logging.WARNING):
        repaired = creators._repair_single_foreign_visualizer_custom_rect_for_startup(
            mgr,
            widgets_config,
            screen_index=0,
            effective_monitor_sel="1",
        )

    assert repaired is False
    assert "screen:display-1" in widgets_config["custom_layout"]["displays"]
    assert "screen:display-0" not in widgets_config["custom_layout"]["displays"]
    assert "Refused spotify_visualizer CUSTOM rect bucket repair" in caplog.text


def test_display_setup_does_not_run_second_lifecycle_initialize_pass():
    lifecycle_initialize_calls: list[str] = []
    spotify_calls: list[str] = []
    stacking_calls: list[dict] = []

    class _ManagerStub:
        def configure_expected_overlays(self, widgets_config):
            return None

        def setup_all_widgets(self, settings_manager, screen_index, thread_manager):
            return {"clock_widget": SimpleNamespace(name="clock")}

        def initialize_all_widgets(self):
            lifecycle_initialize_calls.append("initialize_all_widgets")
            return 1

    class _SettingsStub:
        def get(self, key, default=None):
            if key == "widgets":
                return {"clock": {"enabled": True}}
            return default

        def get_widgets_map(self):
            return {"clock": {"enabled": True}}

    widget = SimpleNamespace(
        settings_manager=_SettingsStub(),
        screen_index=0,
        _thread_manager=None,
        _widget_manager=_ManagerStub(),
        _setup_dimming=lambda: None,
        _setup_spotify_widgets=lambda: spotify_calls.append("spotify"),
        _setup_pixel_shift=lambda: None,
        _apply_widget_stacking=lambda widgets: stacking_calls.append(dict(widgets)),
    )

    display_setup.setup_widgets(widget)

    assert hasattr(widget, "clock_widget")
    assert lifecycle_initialize_calls == []
    assert spotify_calls == ["spotify"]
    assert stacking_calls == [{"clock": {"enabled": True}}]


def test_display_setup_apply_widget_stacking_includes_gmail_widget():
    from rendering import display_setup

    captured: dict[str, object] = {}

    class _ManagerStub:
        def apply_widget_stacking(self, widget_list, widgets_config):
            captured["attrs"] = [attr_name for _widget, attr_name in widget_list]
            captured["widgets_config"] = widgets_config

    widget = SimpleNamespace(
        _widget_manager=_ManagerStub(),
        clock_widget=None,
        clock2_widget=None,
        clock3_widget=None,
        weather_widget=None,
        media_widget=None,
        spotify_visualizer_widget=None,
        reddit_widget=None,
        reddit2_widget=None,
        gmail_widget=SimpleNamespace(),
        imgur_widget=None,
    )

    display_setup.apply_widget_stacking(widget, {"gmail": {"enabled": True}})

    assert "gmail_widget" in captured["attrs"]
    assert "spotify_visualizer_widget" not in captured["attrs"]
    assert captured["widgets_config"] == {"gmail": {"enabled": True}}
