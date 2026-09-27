"""One selected display keeps every widget on it; resolution text is device pixels.

Layout stays in Qt logical pixels (the saver and Arrange both use
``QScreen.geometry()``); only text shown to people states the monitor's own
device resolution.
"""
from __future__ import annotations

from copy import deepcopy
import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from core.settings.defaults import get_default_settings
from core.windows.monitor_resolution import describe_screen_resolution, screen_device_size
from rendering.custom_layout_contract import (
    get_custom_layout_restore_entry,
    load_custom_layout_restore_map,
    set_custom_layout_restore_entry,
    write_custom_layout_restore_map,
)
from rendering.widget_descriptors import (
    get_effective_monitor_value_for_widget,
    get_widget_runtime_descriptors,
    monitor_route_admits_screen,
    route_widgets_to_single_monitor,
)
from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel

pytestmark = pytest.mark.usefixtures("qt_app")


def _routes(widgets) -> dict[str, str]:
    routes = {}
    for descriptor in get_widget_runtime_descriptors():
        try:
            routes[descriptor.widget_id] = get_effective_monitor_value_for_widget(descriptor.widget_id, widgets)
        except (KeyError, ValueError):
            continue
    return routes


def _off_screen_widgets() -> dict:
    """TEST INPUT routes: widgets on another monitor, on ALL, and one restore route."""

    widgets = deepcopy(get_default_settings()["widgets"])
    for widget_id in ("weather", "feeds_news_anime", "feeds_news_tech", "system_audio_osd", "media"):
        widgets[widget_id]["monitor"] = "1"
    widgets["weather"]["monitor"] = 1  # an int route written by an older Settings build
    widgets["clock"]["monitor"] = "ALL"
    restore = load_custom_layout_restore_map(widgets)
    set_custom_layout_restore_entry(restore, "reddit", position="Top Right", monitor="1")
    write_custom_layout_restore_map(widgets, restore)
    return widgets


def test_single_display_routes_every_widget_it_could_not_show() -> None:
    widgets = _off_screen_widgets()
    changed = route_widgets_to_single_monitor(widgets, 2)

    assert {"weather", "feeds_news_anime", "feeds_news_tech", "system_audio_osd", "media"} <= set(changed)
    routes = _routes(widgets)
    assert all(monitor_route_admits_screen(value, 1) for value in routes.values()), routes
    assert routes["spotify_visualizer"] == routes["media"] == "2"  # a following Visualizer moves with Media
    assert widgets["clock"]["monitor"] == "ALL"  # ALL already includes the display
    restore = get_custom_layout_restore_entry(load_custom_layout_restore_map(widgets), "reddit")
    assert restore == {"position": "Top Right", "monitor": "2"}  # Reset cannot send it back
    assert route_widgets_to_single_monitor(widgets, 2) == ()  # idempotent


def _page_settings(widgets, selected):
    class Settings:
        def __init__(self):
            self.values = {"widgets": deepcopy(widgets), "display": {"show_on_monitors": selected}}

        def get(self, key, default=None):
            value = self.values
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    return default
                value = value[part]
            return deepcopy(value)

        def set(self, key, value):
            target = self.values
            parts = key.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = deepcopy(value)

    return Settings()


@pytest.mark.parametrize("selected, routed", [([2], True), ([1, 2], False), ("ALL", False)])
def test_leaving_displays_routes_only_when_exactly_one_display_is_shown(monkeypatch, selected, routed) -> None:
    from ui.onboarding import basic_pages

    screens = [
        SimpleNamespace(name=lambda: "Left", geometry=lambda: QRect(0, 0, 1920, 1080), devicePixelRatio=lambda: 1.0),
        SimpleNamespace(name=lambda: "Right", geometry=lambda: QRect(1920, 0, 2560, 1440), devicePixelRatio=lambda: 1.5),
    ]
    monkeypatch.setattr(basic_pages.QGuiApplication, "screens", staticmethod(lambda: screens))
    widgets = _off_screen_widgets()
    settings = _page_settings(widgets, selected)
    page = basic_pages.DisplaysPage(settings)
    try:
        assert settings.get("widgets") == widgets  # showing the page writes nothing
        assert page.leave() is True
        after = settings.get("widgets")
        assert (after != widgets) is routed
        if routed:
            assert all(monitor_route_admits_screen(v, 1) for v in _routes(after).values())
        # The label is a resolution with its scale, never a logical size.
        assert "logical" not in page.checks[1].text().lower()
        assert "150%" in page.checks[1].text()
    finally:
        page.deleteLater()


def test_resolution_text_is_the_monitors_device_size() -> None:
    from PySide6.QtGui import QGuiApplication

    for screen in QGuiApplication.screens():
        size = screen_device_size(screen)
        ratio = screen.devicePixelRatio()
        geometry = screen.geometry()
        if sys.platform == "win32":
            assert size is not None
        if size is None:
            continue
        # Windows' own figure; Qt's rounded logical size only agrees to within rounding.
        assert abs(size[0] - geometry.width() * ratio) <= ratio
        assert abs(size[1] - geometry.height() * ratio) <= ratio
        assert describe_screen_resolution(screen).startswith(f"{size[0]} × {size[1]} · ")

    # A screen whose device size is unknown says so rather than presenting a guess.
    fake = SimpleNamespace(geometry=lambda: QRect(0, 0, 1707, 960), devicePixelRatio=lambda: 1.5)
    assert describe_screen_resolution(fake) == "≈2560 × 1440 · 150%"


def test_arrange_states_device_pixels_while_laying_out_in_logical_ones() -> None:
    widgets = deepcopy(get_default_settings()["widgets"])
    display = ArrangeDisplay("screen:msi", ("screen:msi",), QRect(0, 0, 1707, 960), "1", 1.5, (2560, 1440))
    model = ArrangeModel(widgets, (display,))
    assert display.resolution() == (2560, 1440)
    for item in model.session.items():
        rect = item.current_global_rect
        assert model.device_size(item.source_key) == (round(rect.width() * 1.5), round(rect.height() * 1.5))
        assert display.geometry.contains(rect.center())  # geometry itself stays logical
