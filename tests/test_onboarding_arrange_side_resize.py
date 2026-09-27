"""Settings Arrange width-only / height-only resize: admission and shared runtime math.

Draft-only (no runtime). Settings measures a family's preferred size, not a
live content box, so side handles are admitted only when every input Runtime
Edit would use is persisted.
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


def test_content_sized_placement_has_no_side_handles_and_says_why() -> None:
    model = ArrangeModel({
        "family_activation": _weather_family_only(),
        "weather": {"enabled": True, "position": "Top Right", "monitor": "1", "margin": 24},
    }, (_display(),))
    key = model.session.items()[0].source_key
    model.move(key, QRect(300, 60, 360, 240))

    # The box is an estimate; a side drag would bake its untouched axis from a guess.
    assert model.item(key).content_sized
    assert model.side_edges(key) == ()
    assert model.side_edges_note(key)


def test_saved_runtime_box_admits_all_four_side_handles() -> None:
    model = ArrangeModel(_weather(), (_display(),))
    key = model.session.items()[0].source_key

    assert set(model.side_edges(key)) == {"left", "right", "top", "bottom"}
    assert model.side_edges_note(key) == ""


def test_customized_children_keep_side_resize_in_runtime_edit() -> None:
    widgets = _weather(child_geometry={"condition_icon": {"width_scale": 1.25, "height_scale": 0.75}})
    model = ArrangeModel(widgets, (_display(),))
    key = model.session.items()[0].source_key

    assert model.side_edges(key) == ()
    assert model.side_edges_note(key)


def test_live_authored_floor_families_are_never_admitted() -> None:
    from rendering.quick.custom_layout_size import settings_content_extent_edges
    from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSessionItem

    descriptor = get_widget_runtime_descriptor("achievement_pulse")
    assert descriptor.content_extent_floor_at_authored_size
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey("achievement_pulse", "screen:test", "default"),
        model_identity="achievement_pulse",
        baseline_global_rect=QRect(0, 0, 600, 300), current_global_rect=QRect(0, 0, 600, 300),
        baseline_size_payload={}, current_size_payload={},
        baseline_enabled=True, current_enabled=True,
        resize_capable=True,
        content_extent_axes=frozenset(descriptor.content_extent_axes),
        baseline_content_extent=(600.0, 300.0), current_content_extent=(600.0, 300.0),
    )
    assert settings_content_extent_edges(item, descriptor) == ()


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
