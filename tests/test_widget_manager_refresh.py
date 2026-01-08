"""Smoke tests for WidgetManager widget creation paths via factory registry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.resources.manager import ResourceManager
from rendering.widget_manager import WidgetManager
from widgets.media_widget import MediaPosition
from widgets.clock_widget import ClockPosition
from widgets.weather_widget import WeatherPosition
from widgets.reddit_widget import RedditPosition


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

    def __init__(self, parent, position):
        super().__init__()
        self.parent = parent
        self.position = position
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
        self.intense_shadow = None
        self.background_opacity = None

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

    def set_intense_shadow(self, value):
        self.intense_shadow = value


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
        self.analog_shadow_intense = None
        self.digital_shadow_intense = None
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

    def set_analog_shadow_intense(self, value):
        self.analog_shadow_intense = value

    def set_digital_shadow_intense(self, value):
        self.digital_shadow_intense = value

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
        self.intense_shadow = None

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

    def set_intense_shadow(self, value):
        self.intense_shadow = value


class _StubRedditWidget(_BaseStubWidget):
    def __init__(self, parent, position):
        super().__init__()
        self.parent = parent
        self.position = position
        self.thread_manager = None
        self.font_family = None
        self.font_size = None
        self.margin = None
        self.text_color = None
        self.show_background = None
        self.show_separators = None
        self.background_color = None
        self.background_opacity = None
        self.background_border = None
        self.item_limit = None
        self.limit = None
        self.intense_shadow = None
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

    def set_text_color(self, value):
        self.text_color = value

    def set_show_background(self, value):
        self.show_background = value

    def set_show_separators(self, value):
        self.show_separators = value

    def set_background_color(self, value):
        self.background_color = value

    def set_background_opacity(self, value):
        self.background_opacity = value

    def set_background_border(self, width, color):
        self.background_border = (width, color)

    def set_item_limit(self, value):
        self.item_limit = value
        self.limit = value

    def set_intense_shadow(self, value):
        self.intense_shadow = value

    def set_overlay_name(self, value):
        self.overlay_name = value

    def set_subreddit(self, value):
        self.subreddit = value


@pytest.fixture(autouse=True)
def _patch_widget_classes(monkeypatch):
    """Route factory-created widgets to our recording stubs."""

    monkeypatch.setattr("rendering.widget_manager.parse_color_to_qcolor", _fake_qcolor)
    monkeypatch.setattr("rendering.widget_factories.parse_color_to_qcolor", _fake_qcolor)
    monkeypatch.setattr("widgets.shadow_utils.apply_widget_shadow", lambda *args, **kwargs: None)
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
            "intense_shadow": True,
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
    assert widget.background_border == (2, (tuple([5, 6, 7, 128]), 0.5))
    assert widget.shadow_config == widgets_config["shadows"]
    assert widget.raised is True
    assert widget.started is True


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
            "analog_shadow_intense": True,
            "digital_shadow_intense": True,
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
    assert widget.analog_shadow_intense is True
    assert widget.digital_shadow_intense is True


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
            "intense_shadow": True,
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
    assert widget.intense_shadow is True
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
            "color": [255, 255, 255, 255],
            "bg_color": [0, 0, 0, 255],
            "border_color": [50, 50, 50, 255],
            "border_opacity": 0.5,
            "show_background": True,
            "show_separators": True,
            "limit": 9,
            "intense_shadow": True,
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
    assert widget.item_limit == 9
    assert widget.intense_shadow is True
    assert widget.raised is True
    assert widget.started is True

    assert isinstance(widget2, _StubRedditWidget)
    assert widget2.position == RedditPosition.BOTTOM_RIGHT
    assert widget2.subreddit == "python"
    assert widget2.item_limit == 4
    # inherits styling from reddit1
    assert widget2.font_family == "Inter"
    assert widget2.text_color == (tuple([255, 255, 255, 255]), None)
    assert widget2.raised is True
    assert widget2.started is True
