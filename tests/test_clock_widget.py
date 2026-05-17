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
