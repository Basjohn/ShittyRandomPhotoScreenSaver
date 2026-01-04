"""Regression tests for widget positioning and stacking edge cases."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from widgets.weather_widget import WeatherWidget, WeatherPosition
from widgets.clock_widget import ClockWidget, ClockPosition


def _make_parent(qtbot, width: int = 1920, height: int = 1080) -> QWidget:
    parent = QWidget()
    parent.resize(width, height)
    qtbot.addWidget(parent)
    parent.show()
    return parent


def test_weather_widget_bottom_right_padding_alignment(qtbot):
    parent = _make_parent(qtbot)
    widget = WeatherWidget(parent, location="Test", position=WeatherPosition.BOTTOM_RIGHT)
    qtbot.addWidget(widget)

    widget.resize(320, 140)
    margin = 20
    widget.set_margin(margin)
    widget._update_position()

    pad_adjust = max(0, widget._padding_right - widget._padding_left)
    expected_horizontal = max(0, margin - pad_adjust)

    right_gap = parent.width() - (widget.x() + widget.width())
    bottom_gap = parent.height() - (widget.y() + widget.height())

    assert right_gap == expected_horizontal
    assert bottom_gap == margin


def test_clock_widget_stack_offset_applies_for_top_right(qtbot):
    parent = _make_parent(qtbot)
    widget = ClockWidget(parent, position=ClockPosition.TOP_RIGHT)
    qtbot.addWidget(widget)

    widget.resize(360, 120)
    widget.set_margin(25)

    offset = QPoint(0, 150)
    widget.set_stack_offset(offset)
    widget._update_position()

    _, visual_offset_y = widget._compute_analog_visual_offset()
    expected_y = widget._margin - visual_offset_y + offset.y()

    assert widget.y() == expected_y


@pytest.mark.parametrize(
    "position,anchor",
    [
        (WeatherPosition.TOP_LEFT, "left"),
        (WeatherPosition.TOP_RIGHT, "right"),
        (WeatherPosition.BOTTOM_LEFT, "left"),
        (WeatherPosition.BOTTOM_RIGHT, "right"),
    ],
)
def test_weather_widget_margin_respected_across_positions(qtbot, position, anchor):
    parent = _make_parent(qtbot)
    widget = WeatherWidget(parent, location="Test", position=position)
    qtbot.addWidget(widget)

    widget.resize(280, 120)
    margin = 30
    widget.set_margin(margin)
    widget._update_position()

    if anchor == "left":
        assert widget.x() == margin
    else:
        pad_adjust = max(0, widget._padding_right - widget._padding_left)
        expected = max(0, margin - pad_adjust)
        right_gap = parent.width() - (widget.x() + widget.width())
        assert right_gap == expected

    if "BOTTOM" in position.name:
        bottom_gap = parent.height() - (widget.y() + widget.height())
        assert bottom_gap == margin
    elif "TOP" in position.name:
        assert widget.y() == margin


def test_clock_and_weather_stack_offsets_do_not_overlap_top_right(qtbot):
    parent = _make_parent(qtbot)
    clock = ClockWidget(parent, position=ClockPosition.TOP_RIGHT)
    weather = WeatherWidget(parent, location="Test", position=WeatherPosition.TOP_RIGHT)
    qtbot.addWidget(clock)
    qtbot.addWidget(weather)

    margin = 25
    clock.set_margin(margin)
    weather.set_margin(margin)

    clock.resize(320, 120)
    weather.resize(320, 110)

    weather_offset = QPoint(0, 150)
    weather.set_stack_offset(weather_offset)

    clock._update_position()
    weather._update_position()

    assert weather.y() == clock.y() + weather_offset.y()
