"""Smoke tests for WidgetManager widget creation paths."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.resources.manager import ResourceManager
from rendering.widget_manager import WidgetManager
from widgets.media_widget import MediaPosition


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

    def set_shadow_config(self, config):
        self.shadow_config = config

    def raise_(self):
        self.raised = True


class _StubMediaWidget(_BaseStubWidget):
    """Minimal stand-in for MediaWidget to record configuration calls."""

    instances: list["_StubMediaWidget"] = []

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
        _StubMediaWidget.instances.append(self)

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
    def __init__(self, parent, time_format, position, show_seconds, timezone, show_timezone):
        super().__init__()
        self.parent = parent
        self.time_format = time_format
        self.position = position
        self.show_seconds = show_seconds
        self.timezone = timezone
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
    def __init__(self, parent, subreddit, position):
        super().__init__()
        self.parent = parent
        self.subreddit = subreddit
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
        self.intense_shadow = None
        self.overlay_name = None

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

    def set_intense_shadow(self, value):
        self.intense_shadow = value

    def set_overlay_name(self, value):
        self.overlay_name = value


@pytest.fixture(autouse=True)
def _stub_qcolor_and_shadow(monkeypatch):
    monkeypatch.setattr("rendering.widget_manager.parse_color_to_qcolor", _fake_qcolor)
    monkeypatch.setattr("rendering.widget_manager.apply_widget_shadow", lambda *args, **kwargs: None)


def _create_manager():
    parent = SimpleNamespace()
    return WidgetManager(parent, ResourceManager())


def test_media_widget_creation_handles_prefixed_positions(monkeypatch):
    monkeypatch.setattr("rendering.widget_manager.MediaWidget", _StubMediaWidget)
    _StubMediaWidget.instances.clear()

    manager = _create_manager()
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
        }
    }

    widget = manager.create_media_widget(widgets_config, {"enabled": True}, screen_index=0)

    assert isinstance(widget, _StubMediaWidget)
    assert widget.position == MediaPosition.TOP_CENTER
    assert widget.margin == 15
    assert widget.raised is True


def test_clock_widget_creation_handles_prefixed_positions(monkeypatch):
    monkeypatch.setattr("rendering.widget_manager.ClockWidget", _StubClockWidget)

    manager = _create_manager()
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
        }
    }

    widget = manager.create_clock_widget(
        'clock',
        'clock_widget',
        'Top Right',
        48,
        widgets_config,
        {"enabled": True},
        widgets_config['clock'],
        screen_index=0,
        thread_manager=None,
    )

    assert isinstance(widget, _StubClockWidget)
    assert widget.position.value == "bottom_center"
    assert widget.font_family == "Segoe UI"
    assert widget.font_size == 60
    assert widget.margin == 25
    assert widget.raised is True


def test_weather_widget_creation_handles_prefixed_positions(monkeypatch):
    monkeypatch.setattr("rendering.widget_manager.WeatherWidget", _StubWeatherWidget)

    manager = _create_manager()
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
            "border_color": [2, 2, 2, 255],
            "border_opacity": 0.9,
            "margin": 10,
            "show_forecast": True,
        }
    }

    widget = manager.create_weather_widget(widgets_config, {"enabled": True}, screen_index=0)

    assert isinstance(widget, _StubWeatherWidget)
    assert widget.position.value == "middle_right"
    assert widget.location == "Berlin"
    assert widget.font_size == 30
    assert widget.margin == 10
    assert widget.raised is True


def test_reddit_widget_creation_handles_prefixed_positions(monkeypatch):
    monkeypatch.setattr("rendering.widget_manager.RedditWidget", _StubRedditWidget)

    manager = _create_manager()
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
        }
    }

    widget = manager.create_reddit_widget(
        'reddit',
        widgets_config,
        {"enabled": True},
        screen_index=0,
        thread_manager=None,
    )

    assert isinstance(widget, _StubRedditWidget)
    assert widget.position.value == "top_left"
    assert widget.subreddit == "all"
    assert widget.font_size == 18
    assert widget.margin == 12
    assert widget.item_limit == 9
    assert widget.raised is True
