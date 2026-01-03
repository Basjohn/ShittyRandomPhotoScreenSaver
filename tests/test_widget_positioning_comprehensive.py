"""
Comprehensive widget positioning tests.

These tests exercise the coordination between WidgetPositioner,
Reddit widget positioning enums, and stacking/collision handling.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, QRect

from rendering.widget_positioner import WidgetPositioner, PositionAnchor
from widgets.reddit_widget import RedditPosition


class DummyWidget:
    """Minimal QWidget-like helper for geometry tests."""

    def __init__(self, width: int, height: int):
        self._size = QSize(width, height)
        self._geometry = QRect(0, 0, width, height)

    def sizeHint(self) -> QSize:
        return self._size

    def size(self) -> QSize:
        return self._size

    def setGeometry(self, rect: QRect) -> None:
        self._geometry = rect

    def geometry(self) -> QRect:
        return self._geometry


def test_positioning_systems_in_sync():
    """Ensure all positioning enums share the same canonical keys."""
    canonical = {
        "top_left",
        "top_center",
        "top_right",
        "middle_left",
        "center",
        "middle_right",
        "bottom_left",
        "bottom_center",
        "bottom_right",
    }

    anchor_values = {anchor.value for anchor in PositionAnchor}
    reddit_values = {anchor.value for anchor in RedditPosition}

    assert anchor_values == canonical
    assert reddit_values == canonical


def test_stack_offsets_prevent_collisions():
    """Stacking offsets should keep widgets from overlapping."""
    positioner = WidgetPositioner(QSize(1920, 1080))

    widget_a = DummyWidget(220, 140)
    widget_b = DummyWidget(210, 120)

    offsets = positioner.calculate_stack_offsets(
        [
            ("widget_a", widget_a, PositionAnchor.TOP_LEFT),
            ("widget_b", widget_b, PositionAnchor.TOP_LEFT),
        ]
    )

    positioner.position_widget(widget_a, PositionAnchor.TOP_LEFT, stack_offset=offsets["widget_a"])
    positioner.position_widget(widget_b, PositionAnchor.TOP_LEFT, stack_offset=offsets["widget_b"])

    positioner.register_widget_bounds("widget_a", widget_a, PositionAnchor.TOP_LEFT)
    positioner.register_widget_bounds("widget_b", widget_b, PositionAnchor.TOP_LEFT)

    assert positioner.find_collisions("widget_b", widget_b.geometry()) == []


def test_missing_stack_offsets_trigger_collision():
    """Without stack offsets, widgets at same anchor should collide."""
    positioner = WidgetPositioner(QSize(1920, 1080))

    widget_primary = DummyWidget(200, 110)
    widget_secondary = DummyWidget(200, 110)

    positioner.position_widget(widget_primary, PositionAnchor.TOP_RIGHT)
    positioner.position_widget(widget_secondary, PositionAnchor.TOP_RIGHT)

    positioner.register_widget_bounds("primary", widget_primary, PositionAnchor.TOP_RIGHT)
    collisions = positioner.find_collisions("secondary", widget_secondary.geometry())

    assert "primary" in collisions


def test_multi_anchor_stack_offsets():
    """Verify stacking works independently across different anchors."""
    positioner = WidgetPositioner(QSize(1920, 1080))

    widgets = [
        ("top_widget", DummyWidget(240, 130), PositionAnchor.TOP_CENTER),
        ("bottom_widget", DummyWidget(240, 130), PositionAnchor.BOTTOM_CENTER),
    ]

    offsets = positioner.calculate_stack_offsets(widgets)

    for name, widget, anchor in widgets:
        positioner.position_widget(widget, anchor, stack_offset=offsets[name])
        positioner.register_widget_bounds(name, widget, anchor)

    # Top and bottom center widgets should never collide due to vertical separation
    assert positioner.find_collisions("top_widget", widgets[0][1].geometry()) == []
    assert positioner.find_collisions("bottom_widget", widgets[1][1].geometry()) == []
