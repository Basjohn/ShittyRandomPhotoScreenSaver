"""Settings Arrange width-only / height-only resize: every axis a widget has, Runtime Edit's math.

Draft-only (no runtime). Sizes are measured through the family's own QML, so a
box with no saved extent starts from its real preferred size, exactly as
Runtime Edit's first side drag does. Children are carried, never shown.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from PySide6.QtCore import QPoint, QRect

from core.settings.default_settings import DEFAULT_SETTINGS
from rendering.widget_descriptors import get_widget_runtime_descriptor
from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel

pytestmark = pytest.mark.usefixtures("qt_app")


def _weather_family_only() -> dict:
    """TEST INPUT: every family explicit; an absent one would inherit its default."""

    return {family: family == "weather" for family in DEFAULT_SETTINGS["widgets"]["family_activation"]}


def _display() -> ArrangeDisplay:
    return ArrangeDisplay("screen:test", ("screen:test",), QRect(0, 0, 1000, 700), "1")


def _payload(widgets: dict) -> dict:
    return widgets["custom_layout"]["displays"]["screen:test"]["weather"]["default"]["size_payload"]


def _weather(**payload_edits) -> dict:
    """A weather entry saved by Runtime Edit: explicit size with a logical box."""

    seed = ArrangeModel({
        "family_activation": _weather_family_only(),
        "weather": {"enabled": True, "position": "Top Right", "monitor": "1", "margin": 24},
    }, (_display(),))
    seed.move(seed.session.items()[0].source_key, QRect(300, 60, 520, 310))
    widgets = seed.apply()
    payload = _payload(widgets)
    payload.pop("_size_from_content")
    payload.pop("_placement_anchor")
    payload["content_extent"] = [520.0, 310.0]
    payload.update(payload_edits)
    return widgets


def test_a_content_sized_placement_resizes_one_axis_from_its_measured_size() -> None:
    model = ArrangeModel({
        "family_activation": _weather_family_only(),
        "weather": {"enabled": True, "position": "Top Right", "monitor": "1", "margin": 24},
    }, (_display(),))
    key = model.session.items()[0].source_key
    item = model.item(key)
    model.move(key, QRect(300, 60, item.current_global_rect.width(), item.current_global_rect.height()), snap=False)
    measured = model._meter.measure("weather", model.widgets)
    assert item.content_sized
    assert set(model.side_edges(key)) == {"left", "right", "top", "bottom"}
    assert model.side_edges_note(key) == ""

    origin = QRect(item.current_global_rect)
    model.resize_edge(key, "right", origin, QPoint(40, 25))

    assert item.current_global_rect.height() == origin.height()
    # The untouched axis is the saver's measured size, not a guess.
    assert item.current_content_extent[1] == pytest.approx(measured[1] / item.resize_scale, abs=0.5)
    saved = _payload(model.apply())
    assert saved["content_extent"][1] == pytest.approx(measured[1], abs=0.5)
    assert "_size_from_content" not in saved  # a real resize is explicit, as in Runtime Edit


def test_saved_runtime_box_admits_all_four_side_handles() -> None:
    model = ArrangeModel(_weather(), (_display(),))
    key = model.session.items()[0].source_key

    assert set(model.side_edges(key)) == {"left", "right", "top", "bottom"}
    assert model.side_edges_note(key) == ""


def test_customized_children_are_carried_unchanged_through_an_outer_resize() -> None:
    children = {"condition_icon": {"width_scale": 1.25, "height_scale": 0.75}}
    widgets = _weather(child_geometry=children)
    model = ArrangeModel(widgets, (_display(),))
    key = model.session.items()[0].source_key
    origin = QRect(model.item(key).current_global_rect)

    assert set(model.side_edges(key)) == {"left", "right", "top", "bottom"}
    model.resize_edge(key, "bottom", origin, QPoint(0, 30))

    saved = _payload(model.apply())
    assert saved["child_geometry"] == _payload(widgets)["child_geometry"]


def test_natural_size_floor_families_cannot_shrink_below_their_measured_size() -> None:
    descriptor = get_widget_runtime_descriptor("achievement_pulse")
    assert descriptor.content_extent_floor_at_authored_size
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    widgets["family_activation"] = {family: family == "steam" for family in widgets["family_activation"]}
    for widget_id in ("steam_progress", "abandonment_issues", "friend_pulse"):
        widgets[widget_id]["enabled"] = False
    widgets["steam"]["enabled"] = True
    widgets["achievement_pulse"].update(enabled=True, monitor="1")
    display = _display()
    model = ArrangeModel(widgets, (display,))
    item = next(i for i in model.session.items() if i.model_identity == "achievement_pulse")
    natural = model._meter.measure("achievement_pulse", model.widgets)
    assert set(model.side_edges(item.source_key)) == {"left", "right", "top", "bottom"}

    origin = QRect(item.current_global_rect)
    model.resize_edge(item.source_key, "left", origin, QPoint(5000, 0))
    model.resize_edge(item.source_key, "top", QRect(item.current_global_rect), QPoint(0, 5000))

    assert item.current_global_rect.width() >= round(natural[0] * item.resize_scale) - 1
    assert item.current_global_rect.height() >= round(natural[1] * item.resize_scale) - 1
    assert display.geometry.contains(item.current_global_rect.center())


def test_visualizer_width_only_keeps_its_height_world_and_scale() -> None:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    widgets["family_activation"] = {family: family in {"media", "visualizers"} for family in widgets["family_activation"]}
    widgets["media"].update(enabled=True, position="Top Left", monitor="1")
    widgets["spotify_visualizer"]["enabled"] = True
    model = ArrangeModel(widgets, (_display(),))
    vis = next(i for i in model.session.items() if i.model_identity == "spotify_visualizer")
    origin = QRect(vis.current_global_rect)
    ppw = origin.height() / 280.0  # canonical 420x280 world, uniform scale

    assert set(model.side_edges(vis.source_key)) == {"left", "right", "top", "bottom"}
    model.resize_edge(vis.source_key, "right", origin, QPoint(90, 0))

    assert vis.current_global_rect.height() == origin.height()
    assert vis.current_viewport_extent[1] == 280.0  # the untouched axis keeps its world exactly
    assert vis.current_viewport_extent[0] == pytest.approx(vis.current_global_rect.width() / ppw)
    saved = model.apply()["custom_layout"]["displays"]["screen:test"]["spotify_visualizer"]["default"]["size_payload"]
    assert saved["viewport_extent"] == [pytest.approx(vis.current_viewport_extent[0]), 280.0]
    assert (saved["width"], saved["height"]) == (vis.current_global_rect.width(), vis.current_global_rect.height())


def test_visualizer_corner_changes_both_axes_with_the_opposite_corner_fixed() -> None:
    """Runtime Edit's Visualizer corner: a two-axis world resize, not a uniform scale."""

    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    widgets["family_activation"] = {family: family in {"media", "visualizers"} for family in widgets["family_activation"]}
    widgets["media"].update(enabled=True, position="Top Left", monitor="1")
    widgets["spotify_visualizer"]["enabled"] = True
    model = ArrangeModel(widgets, (_display(),))
    vis = next(i for i in model.session.items() if i.model_identity == "spotify_visualizer")
    origin = model.resize_origin(vis.source_key)
    before_scale = vis.resize_scale

    model.corner_resize(vis.source_key, "bottom_right", origin, QPoint(70, 45))

    rect = vis.current_global_rect
    assert rect.topLeft() == origin.rect.topLeft()  # the opposite corner stays put
    assert (rect.width(), rect.height()) != (origin.rect.width(), origin.rect.height())
    assert vis.resize_scale == before_scale  # pixels per world unit unchanged: the world grows
    assert vis.current_viewport_extent[0] == pytest.approx(rect.width() / origin.pixels_per_world)
    assert vis.current_viewport_extent[1] == pytest.approx(rect.height() / origin.pixels_per_world)


def test_width_only_drag_changes_one_logical_axis_and_keeps_the_rest_exact() -> None:
    widgets = _weather(future_payload={"nested": [True, "keep", 9]})
    before = deepcopy(_payload(widgets))
    model = ArrangeModel(widgets, (_display(),))
    item = model.session.items()[0]
    origin = QRect(item.current_global_rect)

    model.resize_edge(item.source_key, "right", origin, QPoint(80, 40))

    assert item.current_global_rect.left() == origin.left()
    assert item.current_global_rect.top() == origin.top()
    assert item.current_global_rect.height() == origin.height()
    assert item.current_global_rect.width() > origin.width()
    assert item.current_content_extent[1] == before["content_extent"][1]
    assert item.current_content_extent[0] == item.current_global_rect.width() / item.resize_scale

    saved = _payload(model.apply())
    assert saved["content_extent"] == [item.current_content_extent[0], before["content_extent"][1]]
    assert saved["future_payload"] == before["future_payload"]
    assert "_size_from_content" not in saved


def test_height_only_drag_respects_the_family_declared_floor() -> None:
    model = ArrangeModel(_weather(), (_display(),))
    item = model.session.items()[0]
    descriptor = get_widget_runtime_descriptor("weather")
    origin = QRect(item.current_global_rect)

    model.resize_edge(item.source_key, "top", origin, QPoint(0, 5000))

    assert item.current_global_rect.bottom() == origin.bottom()
    assert item.current_global_rect.height() >= round(descriptor.content_extent_minimum_size[1] * item.resize_scale)
    assert item.current_content_extent[0] == 520.0


def test_reset_drops_the_saved_box_so_a_later_move_cannot_write_it_back() -> None:
    model = ArrangeModel(_weather(), (_display(),))
    key = model.session.items()[0].source_key

    model.reset(key)
    model.move(key, QRect(200, 100, 360, 240))

    assert "content_extent" not in _payload(model.apply())
