"""Bespoke Frequency Zones, Finish and RGBA editors for Sphere's spec-built Settings body."""
from __future__ import annotations

from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel
from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import bind_color_button, bind_setting_signal
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox

_FINISH_PRESETS: dict[str, tuple[float, float]] = {
    "Neutral": (0.20, 0.25),
    "Matte": (0.05, 0.08),
    "Plastic": (0.55, 0.45),
    "Polished": (0.82, 0.70),
    "Metallic": (0.72, 1.00),
    "Glassy": (0.95, 0.75),
}


def row(layout, label):
    widget, content, _ = add_aligned_row_widget(layout, label, label_width=150)
    return widget, content


def build_sphere_ui(tab, parent_layout) -> None:
    from ui.tabs.media.spec_mode_builder import build_spec_mode_ui

    build_spec_mode_ui(tab, parent_layout, "sphere")


def build_sphere_analysis(tab, analysis) -> None:
    tab._sphere_analysis_notch_positions = deepcopy(tab._widget_default("spotify_visualizer", "sphere_analysis_notch_positions"))

    for name, index, title in (("bass", 1, "Bass / Mid:"), ("high", 2, "Mid / Treble:")):
        _widget, content = row(analysis, title)
        control = NoWheelSlider(Qt.Orientation.Horizontal)
        control.setRange(0, 1000)
        control.setValue(round(tab._sphere_analysis_notch_positions[index][0] * 1000))
        control.setToolTip("Boundary within the shared logarithmic analysis bands. This changes Sphere's frequency routing only.")
        value = QLabel()

        def refresh(control=control, value=value):
            value.setText(f"{control.value() / 1000.0:.3f}")

        def update(number, index=index, control=control, refresh=refresh):
            notches = tab._sphere_analysis_notch_positions
            position = min(number / 1000.0, notches[2][0]) if index == 1 else max(number / 1000.0, notches[1][0])
            notches[index][0] = position
            previous = control.blockSignals(True)
            control.setValue(round(position * 1000))
            control.blockSignals(previous)
            refresh()

        refresh()
        control._sphere_refresh_label = refresh
        bind_setting_signal(tab, control.valueChanged, updater=update, auto_switch=True)
        setattr(tab, f"sphere_analysis_{name}_boundary", control)
        content.addWidget(control)
        content.addWidget(value)



def build_sphere_finish(tab, appearance) -> None:
    from core.settings.visualizer_mode_settings import require_mode_settings

    _widget, content = row(appearance, "Finish Preset:")
    tab.sphere_finish = StyledComboBox()
    tab.sphere_finish.addItems(list(require_mode_settings("sphere").control("sphere_finish").choices))
    tab.sphere_finish.setCurrentText(tab._default_str("spotify_visualizer", "sphere_finish"))
    tab.sphere_finish.setToolTip(
        "Convenience only: choosing a finish writes the visible Gloss and Specular sliders. "
        "The finish name is never sent to the voxel renderer and cannot recolour blocks."
    )
    content.addWidget(tab.sphere_finish)
    content.addStretch()



def bind_sphere_finish_axes(tab, appearance) -> None:
    # Finish is a UI bundle only. Any manual finish-axis edit immediately marks
    # the bundle Custom so the label never becomes a second hidden authority.
    finish_edit = {"applying": False}

    def apply_finish(name: str) -> None:
        values = _FINISH_PRESETS.get(str(name))
        if values is None:
            return
        finish_edit["applying"] = True
        try:
            tab.sphere_gloss.setValue(round(values[0] * 100.0))
            tab.sphere_specular.setValue(round(values[1] * 100.0))
        finally:
            finish_edit["applying"] = False

    def mark_finish_custom(_value: int) -> None:
        if finish_edit["applying"]:
            return
        if tab.sphere_finish.currentText() != "Custom":
            tab.sphere_finish.setCurrentText("Custom")

    tab.sphere_finish.currentTextChanged.connect(apply_finish)
    bind_setting_signal(tab, tab.sphere_finish.currentTextChanged, auto_switch=True)
    tab.sphere_gloss.valueChanged.connect(mark_finish_custom)
    tab.sphere_specular.valueChanged.connect(mark_finish_custom)



def _alpha(tab, layout, channel, title):
    _widget, content = row(layout, title)
    control = NoWheelSlider(Qt.Orientation.Horizontal)
    control.setRange(0, 255)
    control.setValue(getattr(tab, f"_sphere_{channel}_color").alpha())
    control.setToolTip("Independent opacity stored in this colour's existing RGBA value.")
    value = QLabel()

    def update(number):
        value.setText(f"{number / 255.0:.0%}")

    def set_alpha(number):
        color = QColor(getattr(tab, f"_sphere_{channel}_color"))
        color.setAlpha(number)
        setattr(tab, f"_sphere_{channel}_color", color)
        getattr(tab, f"sphere_{channel}_color_btn").set_color(color)
        update(number)

    def color_changed(color):
        previous = control.blockSignals(True)
        control.setValue(color.alpha())
        control.blockSignals(previous)
        update(control.value())

    update(control.value())
    control._sphere_refresh_label = lambda: update(control.value())
    bind_setting_signal(tab, control.valueChanged, updater=set_alpha, auto_switch=True)
    getattr(tab, f"sphere_{channel}_color_btn").color_changed.connect(color_changed)
    setattr(tab, f"sphere_{channel}_alpha", control)
    content.addWidget(control)
    content.addWidget(value)
    return control



def _build_colour(tab, layout, channel, alpha_label) -> None:
    from core.settings.visualizer_mode_settings import require_mode_settings

    key = f"sphere_{channel}_color"
    spec = require_mode_settings("sphere").control(key)
    _widget, content = row(layout, spec.label)
    color = tab._color_from_default("spotify_visualizer", key)
    setattr(tab, f"_{key}", color)
    button = ColorSwatchButton(title=spec.title)
    button.setToolTip(spec.tooltip)
    bind_color_button(tab, button, f"_{key}", auto_switch=True, initial_color=color)
    setattr(tab, f"{key}_btn", button)
    content.addWidget(button)
    content.addStretch()
    alpha = _alpha(tab, layout, channel, alpha_label)
    if channel == "tracer":
        def apply(enabled):
            button.setEnabled(bool(enabled))
            alpha.setEnabled(bool(enabled))

        tab.sphere_light_tracer_enabled.toggled.connect(apply)
        tab._sphere_apply_tracer_dependency = lambda: apply(tab.sphere_light_tracer_enabled.isChecked())
        tab._sphere_apply_tracer_dependency()


def build_sphere_fill_colour(tab, layout) -> None:
    _build_colour(tab, layout, "fill", "Fill Opacity:")


def build_sphere_edge_colour(tab, layout) -> None:
    _build_colour(tab, layout, "edge", "Edge Opacity:")


def build_sphere_tracer_colour(tab, layout) -> None:
    _build_colour(tab, layout, "tracer", "Tracer Opacity:")
