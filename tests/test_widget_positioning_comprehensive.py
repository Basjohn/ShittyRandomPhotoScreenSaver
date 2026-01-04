"""
Comprehensive widget positioning tests.

These tests exercise the coordination between WidgetPositioner,
all widget positioning enums, and stacking/collision handling.

Phase 0.2 coverage:
- All 9 anchor positions
- MIDDLE_* anchor stacking
- All widget Position enum synchronization
- Reddit 2 middle/center positioning
- Cross-anchor collision detection
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QSize, QRect, QPoint

from rendering.widget_positioner import WidgetPositioner, PositionAnchor
from widgets.reddit_widget import RedditPosition
from widgets.clock_widget import ClockPosition
from widgets.weather_widget import WeatherPosition
from widgets.media_widget import MediaPosition


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


# ---------------------------------------------------------------------------
# Position Enum Synchronization Tests
# ---------------------------------------------------------------------------


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


def test_all_widget_enums_in_sync():
    """All widget-specific Position enums must match PositionAnchor values."""
    canonical = {anchor.value for anchor in PositionAnchor}
    
    clock_values = {pos.value for pos in ClockPosition}
    weather_values = {pos.value for pos in WeatherPosition}
    media_values = {pos.value for pos in MediaPosition}
    reddit_values = {pos.value for pos in RedditPosition}
    
    assert clock_values == canonical, f"ClockPosition mismatch: {clock_values ^ canonical}"
    assert weather_values == canonical, f"WeatherPosition mismatch: {weather_values ^ canonical}"
    assert media_values == canonical, f"MediaPosition mismatch: {media_values ^ canonical}"
    assert reddit_values == canonical, f"RedditPosition mismatch: {reddit_values ^ canonical}"


def test_enum_count_consistency():
    """All position enums must have exactly 9 values."""
    assert len(PositionAnchor) == 9
    assert len(ClockPosition) == 9
    assert len(WeatherPosition) == 9
    assert len(MediaPosition) == 9
    assert len(RedditPosition) == 9


# ---------------------------------------------------------------------------
# Basic Stacking Tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MIDDLE_* Anchor Stacking Tests (Phase 0.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "anchor",
    [
        PositionAnchor.MIDDLE_LEFT,
        PositionAnchor.CENTER,
        PositionAnchor.MIDDLE_RIGHT,
    ],
)
def test_middle_anchor_positioning_correct(anchor):
    """Verify MIDDLE_* anchors position widgets at vertical center."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    widget = DummyWidget(200, 100)
    
    pos = positioner.calculate_position(widget.size(), anchor, margin_x=20, margin_y=20)
    
    # Vertical center calculation: (container_h - widget_h) // 2
    expected_y = (1080 - 100) // 2
    assert pos.y() == expected_y, f"Expected y={expected_y}, got y={pos.y()}"


def test_middle_left_stacking():
    """Widgets stacked at MIDDLE_LEFT should not overlap."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    widget_a = DummyWidget(200, 100)
    widget_b = DummyWidget(200, 80)
    widget_c = DummyWidget(200, 60)
    
    widgets = [
        ("widget_a", widget_a, PositionAnchor.MIDDLE_LEFT),
        ("widget_b", widget_b, PositionAnchor.MIDDLE_LEFT),
        ("widget_c", widget_c, PositionAnchor.MIDDLE_LEFT),
    ]
    
    offsets = positioner.calculate_stack_offsets(widgets)
    
    for name, widget, anchor in widgets:
        positioner.position_widget(widget, anchor, stack_offset=offsets[name])
        positioner.register_widget_bounds(name, widget, anchor)
    
    # No widget should collide with any other
    assert positioner.find_collisions("widget_a", widget_a.geometry()) == []
    assert positioner.find_collisions("widget_b", widget_b.geometry()) == []
    assert positioner.find_collisions("widget_c", widget_c.geometry()) == []


def test_center_stacking():
    """Widgets stacked at CENTER should not overlap."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    widget_a = DummyWidget(300, 150)
    widget_b = DummyWidget(280, 120)
    
    widgets = [
        ("widget_a", widget_a, PositionAnchor.CENTER),
        ("widget_b", widget_b, PositionAnchor.CENTER),
    ]
    
    offsets = positioner.calculate_stack_offsets(widgets)
    
    for name, widget, anchor in widgets:
        positioner.position_widget(widget, anchor, stack_offset=offsets[name])
        positioner.register_widget_bounds(name, widget, anchor)
    
    assert positioner.find_collisions("widget_a", widget_a.geometry()) == []
    assert positioner.find_collisions("widget_b", widget_b.geometry()) == []


def test_middle_right_stacking():
    """Widgets stacked at MIDDLE_RIGHT should not overlap."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    widget_a = DummyWidget(200, 100)
    widget_b = DummyWidget(200, 100)
    
    widgets = [
        ("widget_a", widget_a, PositionAnchor.MIDDLE_RIGHT),
        ("widget_b", widget_b, PositionAnchor.MIDDLE_RIGHT),
    ]
    
    offsets = positioner.calculate_stack_offsets(widgets)
    
    for name, widget, anchor in widgets:
        positioner.position_widget(widget, anchor, stack_offset=offsets[name])
        positioner.register_widget_bounds(name, widget, anchor)
    
    assert positioner.find_collisions("widget_a", widget_a.geometry()) == []
    assert positioner.find_collisions("widget_b", widget_b.geometry()) == []


# ---------------------------------------------------------------------------
# Reddit 2 Positioning Tests (Phase 0.2)
# ---------------------------------------------------------------------------


def test_reddit2_center_positioning():
    """Reddit 2 widget at CENTER position should be correctly placed."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    # Simulate Reddit 2 widget (typical Reddit widget size)
    reddit2_widget = DummyWidget(350, 300)  # Typical 4-item reddit widget
    
    pos = positioner.calculate_position(
        reddit2_widget.size(), 
        PositionAnchor.CENTER,
        margin_x=20,
        margin_y=20,
    )
    
    # Should be centered both horizontally and vertically
    expected_x = (1920 - 350) // 2
    expected_y = (1080 - 300) // 2
    
    assert pos.x() == expected_x, f"Reddit 2 CENTER x: expected {expected_x}, got {pos.x()}"
    assert pos.y() == expected_y, f"Reddit 2 CENTER y: expected {expected_y}, got {pos.y()}"


def test_reddit2_middle_left_positioning():
    """Reddit 2 widget at MIDDLE_LEFT position should be correctly placed."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    reddit2_widget = DummyWidget(350, 300)
    
    pos = positioner.calculate_position(
        reddit2_widget.size(),
        PositionAnchor.MIDDLE_LEFT,
        margin_x=30,
        margin_y=20,
    )
    
    # Left margin, vertically centered
    expected_x = 30
    expected_y = (1080 - 300) // 2
    
    assert pos.x() == expected_x
    assert pos.y() == expected_y


def test_reddit2_middle_right_positioning():
    """Reddit 2 widget at MIDDLE_RIGHT position should be correctly placed."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    reddit2_widget = DummyWidget(350, 300)
    
    pos = positioner.calculate_position(
        reddit2_widget.size(),
        PositionAnchor.MIDDLE_RIGHT,
        margin_x=30,
        margin_y=20,
    )
    
    # Right margin, vertically centered
    expected_x = 1920 - 350 - 30
    expected_y = (1080 - 300) // 2
    
    assert pos.x() == expected_x
    assert pos.y() == expected_y


def test_reddit1_and_reddit2_different_positions():
    """Reddit 1 and Reddit 2 at different anchors should not collide."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    reddit1 = DummyWidget(350, 400)  # 10-item reddit
    reddit2 = DummyWidget(350, 250)  # 4-item reddit
    
    # Reddit 1 at TOP_RIGHT, Reddit 2 at MIDDLE_LEFT
    widgets = [
        ("reddit1", reddit1, PositionAnchor.TOP_RIGHT),
        ("reddit2", reddit2, PositionAnchor.MIDDLE_LEFT),
    ]
    
    offsets = positioner.calculate_stack_offsets(widgets)
    
    for name, widget, anchor in widgets:
        positioner.position_widget(widget, anchor, stack_offset=offsets[name])
        positioner.register_widget_bounds(name, widget, anchor)
    
    # Different corners should never collide
    assert positioner.find_collisions("reddit1", reddit1.geometry()) == []
    assert positioner.find_collisions("reddit2", reddit2.geometry()) == []


# ---------------------------------------------------------------------------
# Cross-Anchor Collision Tests (Phase 0.2)
# ---------------------------------------------------------------------------


def test_top_and_middle_vertical_separation():
    """TOP_* and MIDDLE_* anchors should have vertical separation."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    top_widget = DummyWidget(300, 200)
    middle_widget = DummyWidget(300, 200)
    
    widgets = [
        ("top", top_widget, PositionAnchor.TOP_CENTER),
        ("middle", middle_widget, PositionAnchor.CENTER),
    ]
    
    for name, widget, anchor in widgets:
        positioner.position_widget(widget, anchor)
        positioner.register_widget_bounds(name, widget, anchor)
    
    # With a ~400px gap between TOP and CENTER, these shouldn't collide
    # TOP_CENTER: y = 20 (margin), ends at 220
    # CENTER: y = (1080-200)//2 = 440
    assert positioner.find_collisions("top", top_widget.geometry()) == []
    assert positioner.find_collisions("middle", middle_widget.geometry()) == []


def test_bottom_and_middle_vertical_separation():
    """BOTTOM_* and MIDDLE_* anchors should have vertical separation."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    bottom_widget = DummyWidget(300, 200)
    middle_widget = DummyWidget(300, 200)
    
    widgets = [
        ("bottom", bottom_widget, PositionAnchor.BOTTOM_CENTER),
        ("middle", middle_widget, PositionAnchor.CENTER),
    ]
    
    for name, widget, anchor in widgets:
        positioner.position_widget(widget, anchor)
        positioner.register_widget_bounds(name, widget, anchor)
    
    # BOTTOM_CENTER: y = 1080 - 200 - 20 = 860
    # CENTER: y = 440, ends at 640
    # Well separated vertically
    assert positioner.find_collisions("bottom", bottom_widget.geometry()) == []
    assert positioner.find_collisions("middle", middle_widget.geometry()) == []


def test_left_right_horizontal_separation():
    """LEFT and RIGHT anchors at same vertical should have horizontal separation."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    left_widget = DummyWidget(300, 200)
    right_widget = DummyWidget(300, 200)
    
    widgets = [
        ("left", left_widget, PositionAnchor.MIDDLE_LEFT),
        ("right", right_widget, PositionAnchor.MIDDLE_RIGHT),
    ]
    
    for name, widget, anchor in widgets:
        positioner.position_widget(widget, anchor)
        positioner.register_widget_bounds(name, widget, anchor)
    
    # MIDDLE_LEFT: x = 20, ends at 320
    # MIDDLE_RIGHT: x = 1920 - 300 - 20 = 1600
    # Well separated horizontally
    assert positioner.find_collisions("left", left_widget.geometry()) == []
    assert positioner.find_collisions("right", right_widget.geometry()) == []


def test_large_widgets_may_collide_at_center():
    """Very large widgets at adjacent anchors might collide."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    
    # Large widgets that extend significantly from their anchors
    top_center = DummyWidget(600, 500)
    center = DummyWidget(600, 400)
    
    positioner.position_widget(top_center, PositionAnchor.TOP_CENTER)
    positioner.position_widget(center, PositionAnchor.CENTER)
    
    positioner.register_widget_bounds("top_center", top_center, PositionAnchor.TOP_CENTER)
    positioner.register_widget_bounds("center", center, PositionAnchor.CENTER)
    
    # TOP_CENTER: y = 20, ends at 520
    # CENTER: y = (1080-400)//2 = 340
    # These DO overlap (520 > 340)
    collisions = positioner.find_collisions("center", center.geometry())
    assert "top_center" in collisions, "Large widgets at adjacent vertical anchors should collide"


# ---------------------------------------------------------------------------
# Edge Cases and Bounds Tests
# ---------------------------------------------------------------------------


def test_widget_clamped_to_container():
    """Widget with large offset should be clamped to container bounds."""
    positioner = WidgetPositioner(QSize(1920, 1080))
    widget = DummyWidget(200, 100)
    
    # Large negative offset that would place widget off-screen
    pos = positioner.calculate_position(
        widget.size(),
        PositionAnchor.TOP_LEFT,
        margin_x=20,
        margin_y=20,
        stack_offset=QPoint(-100, -100),
    )
    
    # Should be clamped to (0, 0) minimum
    assert pos.x() >= 0
    assert pos.y() >= 0


def test_small_container_handles_large_widget():
    """Small container should still position large widget at edges."""
    positioner = WidgetPositioner(QSize(400, 300))  # Small display
    widget = DummyWidget(350, 250)  # Nearly fills display
    
    pos = positioner.calculate_position(
        widget.size(),
        PositionAnchor.CENTER,
        margin_x=10,
        margin_y=10,
    )
    
    # Should still center the widget
    expected_x = (400 - 350) // 2
    expected_y = (300 - 250) // 2
    assert pos.x() == expected_x
    assert pos.y() == expected_y
