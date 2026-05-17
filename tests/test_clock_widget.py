from __future__ import annotations

from datetime import datetime

import widgets.clock_widget as clock_mod
from widgets.clock_widget import ClockWidget
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget


def test_analog_clock_fade_in_uses_shared_fade_without_direct_show(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    clock._display_mode = "analog"

    direct_show_calls: list[str] = []
    fade_calls: list[dict[str, object]] = []

    monkeypatch.setattr(clock, "show", lambda: direct_show_calls.append("show"))
    monkeypatch.setattr(
        clock_mod.ShadowFadeProfile,
        "start_fade_in",
        staticmethod(
            lambda widget, config, *, duration_ms=None, has_background_frame, apply_shadow_on_finish=True, on_finished=None: fade_calls.append(
                {
                    "widget": widget,
                    "duration_ms": duration_ms,
                    "has_background_frame": has_background_frame,
                    "apply_shadow_on_finish": apply_shadow_on_finish,
                }
            )
        ),
    )

    clock._start_widget_fade_in()

    assert direct_show_calls == []
    assert fade_calls == [
        {
            "widget": clock,
            "duration_ms": clock_mod.ShadowFadeProfile.default_duration_ms(),
            "has_background_frame": clock._show_background,
            "apply_shadow_on_finish": True,
        }
    ]


def test_analog_clock_background_renders_circular_card(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_display_mode("analog")
    clock.set_show_background(True)
    clock.resize(320, 320)
    clock._current_dt = datetime(2026, 1, 1, 12, 0, 0)
    clock.show()
    qtbot.waitExposed(clock)
    qtbot.wait(20)

    image = QImage(clock.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    try:
        clock.render(painter, QPoint(0, 0))
    finally:
        painter.end()

    center_right = image.pixelColor(int(clock.width() * 0.72), clock.height() // 2)
    corner = image.pixelColor(0, 0)

    assert center_right.alpha() > 0
    assert corner.alpha() == 0


def test_analog_clock_layout_metrics_expand_ring_and_shrink_numerals(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_display_mode("analog")
    clock.set_show_background(True)
    clock.resize(320, 320)

    metrics = clock._compute_analog_layout_metrics()

    assert metrics is not None

    base_numeral_pt = max(8, min(int(clock._font_size * 0.25), max(9, metrics.side // 18)))
    assert metrics.numeral_pt <= int(round(base_numeral_pt * 0.85))

    base_ring_width = metrics.numeral_height + max(6, metrics.numeral_height // 3) - 2
    assert (metrics.card_radius - metrics.radius) > base_ring_width


def test_analog_clock_framed_metrics_reduce_timezone_size_and_keep_extra_gap(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_display_mode("analog")
    clock.set_show_background(True)
    clock.set_show_timezone(True)
    clock.resize(320, 360)

    metrics = clock._compute_analog_layout_metrics()

    assert metrics is not None
    assert metrics.tz_font_size <= int(round(max(8, clock._font_size // 3) * 0.85))
    assert clock._compute_analog_timezone_top(metrics.center_y, metrics.radius, metrics.numeral_height, metrics) == (
        metrics.center_y + metrics.card_radius + clock.ANALOG_FRAMED_TIMEZONE_GAP_PX
    )


def test_analog_clock_framed_metrics_keep_larger_outer_ring_margin_than_unframed(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_display_mode("analog")
    clock.resize(320, 360)

    clock.set_show_background(True)
    framed_metrics = clock._compute_analog_layout_metrics()
    assert framed_metrics is not None

    clock.set_show_background(False)
    unframed_metrics = clock._compute_analog_layout_metrics()
    assert unframed_metrics is not None

    framed_outer_margin = framed_metrics.card_radius - framed_metrics.numeral_outer_radius
    unframed_outer_margin = unframed_metrics.card_radius - unframed_metrics.numeral_outer_radius

    assert framed_outer_margin > unframed_outer_margin


def test_analog_clock_unframed_metrics_use_tighter_numeral_shadow_offset(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_display_mode("analog")
    clock.set_show_background(False)
    clock.resize(320, 360)

    metrics = clock._compute_analog_layout_metrics()

    assert metrics is not None
    assert metrics.numeral_shadow_offset_px == 1


def test_analog_clock_outer_edge_layout_pulls_wider_numerals_further_in(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_display_mode("analog")
    clock.set_show_background(False)
    clock.resize(320, 360)

    metrics = clock._compute_analog_layout_metrics()
    assert metrics is not None

    numeral_font = clock_mod.QFont(clock._font_family, metrics.numeral_pt, clock_mod.QFont.Weight.Bold)
    numeral_metrics = clock_mod.QFontMetrics(numeral_font)

    viii_x, viii_y = clock._compute_analog_text_draw_origin(
        numeral_metrics,
        "VIII",
        angle=clock_mod.math.radians((8 / 12.0) * 360.0 - 90.0),
        outer_radius=metrics.numeral_outer_radius,
        center_x=metrics.center_x,
        center_y=metrics.center_y,
    )
    i_x, i_y = clock._compute_analog_text_draw_origin(
        numeral_metrics,
        "I",
        angle=clock_mod.math.radians((1 / 12.0) * 360.0 - 90.0),
        outer_radius=metrics.numeral_outer_radius,
        center_x=metrics.center_x,
        center_y=metrics.center_y,
    )

    viii_rect = numeral_metrics.tightBoundingRect("VIII")
    if viii_rect.isNull():
        viii_rect = numeral_metrics.boundingRect("VIII")
    i_rect = numeral_metrics.tightBoundingRect("I")
    if i_rect.isNull():
        i_rect = numeral_metrics.boundingRect("I")

    viii_center_radius = ((viii_x + viii_rect.x() + (viii_rect.width() / 2.0) - metrics.center_x) ** 2 + (viii_y + viii_rect.y() + (viii_rect.height() / 2.0) - metrics.center_y) ** 2) ** 0.5
    i_center_radius = ((i_x + i_rect.x() + (i_rect.width() / 2.0) - metrics.center_x) ** 2 + (i_y + i_rect.y() + (i_rect.height() / 2.0) - metrics.center_y) ** 2) ** 0.5

    assert i_center_radius - viii_center_radius < metrics.numeral_height * 0.55


def test_analog_clock_numeral_layout_map_pushes_viii_outward(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_display_mode("analog")
    clock.set_show_background(False)
    clock.resize(320, 360)

    metrics = clock._compute_analog_layout_metrics()
    assert metrics is not None

    numeral_font = clock_mod.QFont(clock._font_family, metrics.numeral_pt, clock_mod.QFont.Weight.Black)
    numeral_metrics = clock_mod.QFontMetrics(numeral_font)

    viii_x, viii_y = clock._compute_analog_text_draw_origin(
        numeral_metrics,
        "VIII",
        angle=clock_mod.math.radians((8 / 12.0) * 360.0 - 90.0),
        outer_radius=metrics.numeral_outer_radius,
        center_x=metrics.center_x,
        center_y=metrics.center_y,
    )
    vii_x, vii_y = clock._compute_analog_text_draw_origin(
        numeral_metrics,
        "VII",
        angle=clock_mod.math.radians((7 / 12.0) * 360.0 - 90.0),
        outer_radius=metrics.numeral_outer_radius,
        center_x=metrics.center_x,
        center_y=metrics.center_y,
    )

    viii_rect = numeral_metrics.tightBoundingRect("VIII")
    if viii_rect.isNull():
        viii_rect = numeral_metrics.boundingRect("VIII")
    vii_rect = numeral_metrics.tightBoundingRect("VII")
    if vii_rect.isNull():
        vii_rect = numeral_metrics.boundingRect("VII")

    viii_center_radius = ((viii_x + viii_rect.x() + (viii_rect.width() / 2.0) - metrics.center_x) ** 2 + (viii_y + viii_rect.y() + (viii_rect.height() / 2.0) - metrics.center_y) ** 2) ** 0.5
    vii_center_radius = ((vii_x + vii_rect.x() + (vii_rect.width() / 2.0) - metrics.center_x) ** 2 + (vii_y + vii_rect.y() + (vii_rect.height() / 2.0) - metrics.center_y) ** 2) ** 0.5

    assert viii_center_radius >= vii_center_radius - (metrics.numeral_height * 0.10)
