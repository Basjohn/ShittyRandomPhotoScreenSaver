from __future__ import annotations

from datetime import datetime
from copy import deepcopy

import widgets.clock_widget as clock_mod
from widgets.clock_widget import ClockWidget
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QFont, QFontMetrics, QImage, QPainter
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from rendering.custom_layout_contract import get_screen_signature


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


def test_analog_clock_font_size_refreshes_minimum_footprint(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_display_mode("analog")

    initial_min_width = clock.minimumWidth()
    initial_min_height = clock.minimumHeight()

    clock.set_font_size(24)

    assert clock.minimumWidth() < initial_min_width
    assert clock.minimumHeight() < initial_min_height
    assert clock.minimumWidth() == max(160, int(clock._font_size * 4.5))
    assert clock.minimumHeight() == int(clock.minimumWidth() * 1.3)


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


def test_digital_clock_timezone_label_stays_inside_widget_bounds(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.resize(240, 180)
    clock.set_display_mode("digital")
    clock.set_show_background(False)
    clock.set_show_timezone(True)
    clock.set_font_size(42)
    clock.setText("11:59 PM")
    clock._update_stylesheet()
    assert clock._tz_label is not None
    clock._tz_label.setText("SAST")
    clock._tz_label.adjustSize()
    clock._update_position()

    assert clock._tz_label.y() >= 0
    assert clock._tz_label.y() + clock._tz_label.height() <= clock.height()


def test_digital_clock_framed_padding_leaves_room_for_wide_time_text(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.resize(189, 246)
    clock.set_display_mode("digital")
    clock.set_show_background(True)
    clock.set_show_timezone(True)
    clock.set_font_size(42)
    clock.setText("11:59 PM")
    clock._update_stylesheet()

    margins = clock.contentsMargins()
    available_width = clock.width() - margins.left() - margins.right()
    text_width = QFontMetrics(clock.font()).horizontalAdvance(clock.text())

    assert available_width >= text_width


def test_digital_clock_fit_and_font_features_stay_stable_across_second_shapes(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.resize(220, 140)
    clock.set_display_mode("digital")
    clock.set_show_background(True)
    clock.set_show_timezone(False)
    clock.set_time_format(clock_mod.TimeFormat.TWELVE_HOUR)
    clock.set_font_size(84)

    clock.setText("11:11:11 PM")
    clock._apply_digital_font_fit()
    narrow_size = clock._effective_digital_font_size

    clock.setText("08:58:58 PM")
    clock._apply_digital_font_fit()
    wide_size = clock._effective_digital_font_size

    tabular_tag = clock_mod.QFont.Tag.fromString("tnum")
    assert narrow_size == wide_size
    assert clock.font().isFeatureSet(tabular_tag)
    assert clock.font().featureValue(tabular_tag) == 1


def test_digital_clock_custom_rect_fit_stays_stable_across_wide_second_shapes(qtbot):
    parent = QWidget()
    parent.resize(1600, 900)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.setGeometry(0, 24, 676, 196)
    clock.set_display_mode("digital")
    clock.set_show_background(True)
    clock.set_show_timezone(True)
    clock.set_time_format(clock_mod.TimeFormat.TWENTY_FOUR_HOUR)
    clock.set_font_size(130)
    clock._custom_layout_local_rect = QRect(clock.geometry())

    observed: list[tuple[QRect, int, tuple[int, int, int, int]]] = []
    for text in ("08:08:08", "11:11:11", "18:49:11", "23:59:59"):
        clock.setText(text)
        clock._apply_digital_font_fit()
        clock._update_stylesheet()
        clock._position_timezone_label()
        margins = clock.contentsMargins()
        observed.append(
            (
                QRect(clock.geometry()),
                clock._effective_digital_font_size,
                (margins.left(), margins.top(), margins.right(), margins.bottom()),
            )
        )

    assert {entry[0].getRect() for entry in observed} == {(0, 24, 676, 196)}
    assert len({entry[1] for entry in observed}) == 1
    assert len({entry[2] for entry in observed}) == 1


def test_digital_clock_fit_ignores_stale_timezone_label_height_in_tight_custom_rect(qtbot):
    parent = QWidget()
    parent.resize(1600, 900)
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.setGeometry(456, 60, 786, 221)
    clock.set_display_mode("digital")
    clock.set_show_background(True)
    clock.set_show_timezone(True)
    clock.set_time_format(clock_mod.TimeFormat.TWENTY_FOUR_HOUR)
    clock.set_font_size(129)
    clock._custom_layout_local_rect = QRect(clock.geometry())
    assert clock._tz_label is not None

    observed: list[tuple[int, tuple[int, int, int, int], tuple[int, int, int, int]]] = []
    for stale_tz_size in (8, 60, 12, 48):
        clock._tz_label.setFont(QFont(clock._font_family, stale_tz_size, QFont.Weight.Bold))
        clock._tz_label.setText("SAST")
        clock._tz_label.adjustSize()
        clock.setText("18:49:11")
        clock._apply_digital_font_fit()
        clock._update_stylesheet()
        clock._position_timezone_label()
        margins = clock.contentsMargins()
        observed.append(
            (
                clock._effective_digital_font_size,
                clock._tz_label.geometry().getRect(),
                (margins.left(), margins.top(), margins.right(), margins.bottom()),
            )
        )

    assert len({entry[0] for entry in observed}) == 1
    assert len({entry[1] for entry in observed}) == 1
    assert len({entry[2] for entry in observed}) == 1
    assert clock.geometry().getRect() == (456, 60, 786, 221)


def test_digital_clock_tick_does_not_rebuild_stylesheet_for_time_only_change(qtbot, monkeypatch):
    clock = ClockWidget()
    qtbot.addWidget(clock)
    clock.set_display_mode("digital")
    clock.set_show_background(True)
    clock.set_font_size(72)

    calls: list[str] = []
    monkeypatch.setattr(clock, "_update_stylesheet", lambda: calls.append("style"))

    clock._update_time()

    assert calls == []


def test_digital_clock_timezone_label_biases_upward_inside_reserved_bottom_band(qtbot):
    parent = QWidget()
    parent.resize(900, 600)
    parent._screen = QGuiApplication.primaryScreen()
    qtbot.addWidget(parent)
    parent.show()

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.resize(871, 371)
    clock.set_display_mode("digital")
    clock.set_show_background(True)
    clock.set_show_timezone(True)
    clock.set_font_size(130)
    clock.setText("18:49:11")
    clock._update_stylesheet()
    assert clock._tz_label is not None
    clock._tz_label.setText("SAST")
    clock._tz_label.adjustSize()
    clock._update_position()

    _, _, _, bottom_pad = clock._compute_digital_padding(clock._tz_label.height())
    reserved_top = max(0, clock.height() - bottom_pad)
    reserved_height = max(clock._tz_label.height(), clock.height() - reserved_top)
    available_slack = max(0, reserved_height - clock._tz_label.height())
    expected_y = reserved_top + max(
        0,
        int(round(available_slack * clock.DIGITAL_TZ_UPPER_SLACK_RATIO)),
    )
    bottom_gap = clock.height() - (clock._tz_label.y() + clock._tz_label.height())
    top_gap = clock._tz_label.y() - reserved_top

    assert clock._tz_label.y() == expected_y
    assert bottom_gap > top_gap


def test_clock_double_click_rebuilds_custom_runtime_rect_from_digital_to_analog(qtbot):
    class _SettingsStub:
        def __init__(self, widgets_map: dict) -> None:
            self.widgets_map = deepcopy(widgets_map)
            self.emit_change_calls: list[bool] = []
            self.saved = False

        def get_widgets_map(self) -> dict:
            return deepcopy(self.widgets_map)

        def set_widgets_map(self, widgets: dict, *, emit_change: bool = True) -> None:
            self.widgets_map = deepcopy(widgets)
            self.emit_change_calls.append(bool(emit_change))

        def save(self) -> None:
            self.saved = True

    class _WidgetManagerStub:
        def __init__(self, settings_manager) -> None:
            self._settings_manager = settings_manager

    parent = QWidget()
    parent.resize(1400, 1000)
    parent._screen = QGuiApplication.primaryScreen()
    qtbot.addWidget(parent)
    parent.show()

    screen_signature = get_screen_signature(parent._screen)
    widgets_map = {
        "clock": {
            "position": "Custom",
            "display_mode": "digital",
            "clock_analog_mode": False,
        },
        "custom_layout": {
            "version": 1,
            "displays": {
                screen_signature: {
                    "clock": {
                        "rect": {"x": 0.10, "y": 0.20, "width": 0.35, "height": 0.25},
                        "size_payload": {"display_mode": "digital", "font_size": 55},
                        "resize_mode": "clock_font",
                    }
                }
            },
        },
    }
    settings_stub = _SettingsStub(widgets_map)

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_show_timezone(True)
    clock.set_show_background(True)
    clock.resize(400, 160)
    clock.move(300, 180)
    clock._custom_layout_local_rect = QRect(300, 180, 400, 160)
    clock.set_widget_manager(_WidgetManagerStub(settings_stub))
    clock.set_display_mode("digital")
    clock.set_font_size(55)

    assert clock.handle_double_click(QPoint(40, 40)) is True
    analog_rect = QRect(clock._custom_layout_local_rect)
    saved_entry = settings_stub.widgets_map["custom_layout"]["displays"][screen_signature]["clock"]
    saved_payload = saved_entry["size_payload"]

    assert clock._display_mode == "analog"
    assert clock._font_size == 55
    assert analog_rect.height() > analog_rect.width()
    assert analog_rect == QRect(376, 99, 248, 322)
    assert saved_payload["display_mode"] == "analog"
    assert saved_payload["font_size"] == 55
    assert saved_entry["rect"] == {
        "x": analog_rect.x() / parent.width(),
        "y": analog_rect.y() / parent.height(),
        "width": analog_rect.width() / parent.width(),
        "height": analog_rect.height() / parent.height(),
    }
    assert settings_stub.widgets_map["clock"]["display_mode"] == "analog"
    assert settings_stub.widgets_map["clock"]["clock_analog_mode"] is True
    assert settings_stub.emit_change_calls == [False]
    assert settings_stub.saved is True

def test_clock_double_click_rebuilds_custom_runtime_rect_from_analog_to_digital(qtbot):
    class _SettingsStub:
        def __init__(self, widgets_map: dict) -> None:
            self.widgets_map = deepcopy(widgets_map)
            self.emit_change_calls: list[bool] = []
            self.saved = False

        def get_widgets_map(self) -> dict:
            return deepcopy(self.widgets_map)

        def set_widgets_map(self, widgets: dict, *, emit_change: bool = True) -> None:
            self.widgets_map = deepcopy(widgets)
            self.emit_change_calls.append(bool(emit_change))

        def save(self) -> None:
            self.saved = True

    class _WidgetManagerStub:
        def __init__(self, settings_manager) -> None:
            self._settings_manager = settings_manager

    parent = QWidget()
    parent.resize(1400, 1000)
    parent._screen = QGuiApplication.primaryScreen()
    qtbot.addWidget(parent)
    parent.show()

    screen_signature = get_screen_signature(parent._screen)
    widgets_map = {
        "clock": {
            "position": "Custom",
            "display_mode": "analog",
            "clock_analog_mode": True,
        },
        "custom_layout": {
            "version": 1,
            "displays": {
                screen_signature: {
                    "clock": {
                        "rect": {"x": 0.25, "y": 0.12, "width": 0.18, "height": 0.34},
                        "size_payload": {"display_mode": "analog", "font_size": 55},
                        "resize_mode": "clock_font",
                    }
                }
            },
        },
    }
    settings_stub = _SettingsStub(widgets_map)

    clock = ClockWidget(parent=parent)
    qtbot.addWidget(clock)
    clock.set_show_timezone(True)
    clock.set_show_background(True)
    clock.resize(248, 322)
    clock.move(326, 99)
    clock._custom_layout_local_rect = QRect(326, 99, 248, 322)
    clock.set_widget_manager(_WidgetManagerStub(settings_stub))
    clock.set_display_mode("analog")
    clock.set_font_size(55)

    assert clock.handle_double_click(QPoint(40, 40)) is True
    digital_rect = QRect(clock._custom_layout_local_rect)
    saved_entry = settings_stub.widgets_map["custom_layout"]["displays"][screen_signature]["clock"]
    saved_payload = saved_entry["size_payload"]

    assert clock._display_mode == "digital"
    assert clock._font_size == 55
    assert digital_rect.width() > digital_rect.height() * 2
    assert digital_rect.width() > 248
    assert digital_rect.height() < 322
    assert saved_payload["display_mode"] == "digital"
    assert saved_payload["font_size"] == 55
    assert saved_entry["rect"] == {
        "x": digital_rect.x() / parent.width(),
        "y": digital_rect.y() / parent.height(),
        "width": digital_rect.width() / parent.width(),
        "height": digital_rect.height() / parent.height(),
    }
    assert settings_stub.widgets_map["clock"]["display_mode"] == "digital"
    assert settings_stub.widgets_map["clock"]["clock_analog_mode"] is False
    assert settings_stub.emit_change_calls == [False]
    assert settings_stub.saved is True
