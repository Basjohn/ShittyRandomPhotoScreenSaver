"""Rendered geometry and semantic foreground checks using test-owned styles."""
from dataclasses import replace

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel, QWidget

from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba
from ui.widgets.control_shadow import ShadowConfig, attach_text_shadow


def _colored_bounds(image, channel):
    points = []
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            selected = color.red() if channel == "red" else color.green()
            other = color.green() if channel == "red" else color.red()
            if selected > 100 and selected > other + 50:
                points.append((x, y))
    assert points
    return min(x for x, _ in points), min(y for _, y in points)


@pytest.mark.parametrize("name", ["titleBarLabel", "ordinaryHeading"])
def test_text_shadow_uses_the_labels_already_padded_content_rect(qt_app, name):
    parent = QWidget()
    parent.resize(340, 100)
    label = QLabel("TEST TITLE", parent)
    label.setObjectName(name)
    label.setGeometry(0, 0, 300, 80)
    label.setFont(QFont("Arial", 20))
    label.setStyleSheet("color: rgb(0,255,0); padding-left: 10px; padding-top: 3px;")
    label.ensurePolished()
    attach_text_shadow(label, ShadowConfig(blur_radius=0, offset=QPointF(2, 2), color=QColor(255, 0, 0)))
    helper = label._settings_text_shadow_helper
    try:
        main = label.grab().toImage()
        shadow = helper.overlay.grab().toImage()
        main_x, main_y = _colored_bounds(main, "green")
        shadow_x, shadow_y = _colored_bounds(shadow, "red")
        expected = round(2 * main.devicePixelRatio())
        assert (shadow_x-main_x, shadow_y-main_y) == (expected, expected)
    finally:
        parent.deleteLater()
        qt_app.processEvents()


def test_shadow_direction_arrow_consumes_the_semantic_button_foreground(qt_app, monkeypatch):
    from ui.tabs import widgets_tab_defaults as defaults
    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    colors["control.button.text"] = Rgba(0, 255, 0)
    theme = replace(DEFAULT_DARK_SETTINGS_THEME, colors=colors)
    monkeypatch.setattr(defaults, "get_active_settings_theme", lambda: theme)
    button = defaults._ShadowDirectionButton(0, 0)
    button.resize(40, 40)
    button.setStyleSheet("background: black; border: none;")
    try:
        _colored_bounds(button.grab().toImage(), "green")
    finally:
        button.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize("state", ["normal", "hover", "pressed", "disabled"])
def test_combo_indicator_consumes_shared_stepper_state_roles(qt_app, monkeypatch, state):
    from ui.widgets import combo_knob_overlay as knobs
    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    role = "control.stepper." + ("surface" if state == "normal" else state + "_surface")
    colors[role] = Rgba(24, 110, 70, 210)
    theme = replace(DEFAULT_DARK_SETTINGS_THEME, colors=colors)
    monkeypatch.setattr(knobs, "get_active_settings_theme", lambda: theme)
    host = QWidget()
    overlay = knobs.ComboKnobOverlay(host)
    overlay.set_state(state)
    host.setEnabled(state != "disabled")
    try:
        assert overlay._resolve_color().getRgb() == colors[role].as_tuple()
        host.setProperty("previewKnob" + state.title(), "#123456")
        assert overlay._resolve_color() == QColor("#123456")
    finally:
        host.deleteLater()
        qt_app.processEvents()
