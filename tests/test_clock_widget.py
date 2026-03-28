from __future__ import annotations

import widgets.clock_widget as clock_mod
from widgets.clock_widget import ClockWidget
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
            "apply_shadow_on_finish": False,
        }
    ]
