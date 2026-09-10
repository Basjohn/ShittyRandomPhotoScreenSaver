"""Persistence binding for the lazy Sphere Settings body."""
from __future__ import annotations

from PySide6.QtGui import QColor
from ui.color_utils import qcolor_to_list as _qcolor_to_list


_SPHERE_SETTING_KEYS = (
    "sphere_finish",
    "sphere_allow_overflow",
    "sphere_cel_shading",
    "sphere_light_tracer_enabled",
    "sphere_fragment_interpolation_enabled",
    "sphere_rainbow_ghosting",
    "sphere_shadow_enabled",
    "sphere_fade_incoming_blocks",
    "sphere_deformation",
    "sphere_base_rotation_speed",
    "sphere_rotation_speed",
    "sphere_gloss",
    "sphere_specular",
    "sphere_light_direction",
    "sphere_idle_motion",
    "sphere_surface_detail",
    "sphere_bass_response",
    "sphere_mid_response",
    "sphere_high_response",
    "sphere_vocal_response",
    "sphere_bump_reactivity",
    "sphere_size_response",
    "sphere_energy_curve",
)


def load_sphere_mode_settings(tab, config) -> None:
    for key in _SPHERE_SETTING_KEYS:
        control = getattr(tab, key, None)
        if control is None:
            continue
        default = tab._widget_default("spotify_visualizer", key)
        value = config.get(key, default)
        if hasattr(control, "setCurrentText"):
            control.setCurrentText(str(value))
        elif hasattr(control, "setChecked"):
            control.setChecked(bool(value))
        else:
            control.setValue(round(float(value) * 100))

    for key, attr, button_attr in (
        ("sphere_fill_color", "_sphere_fill_color", "sphere_fill_color_btn"),
        ("sphere_edge_color", "_sphere_edge_color", "sphere_edge_color_btn"),
    ):
        default = tab._widget_default("spotify_visualizer", key)
        raw = config.get(key, default)
        try:
            color = QColor(*raw)
        except Exception:
            color = QColor(*default)
        setattr(tab, attr, color)
        button = getattr(tab, button_attr, None)
        if button is not None and hasattr(button, "set_color"):
            button.set_color(color)


def collect_sphere_mode_settings(tab) -> dict:
    return {
        "sphere_finish": tab.sphere_finish.currentText(),
        "sphere_allow_overflow": tab.sphere_allow_overflow.isChecked(),
        "sphere_cel_shading": tab.sphere_cel_shading.isChecked(),
        "sphere_light_tracer_enabled": tab.sphere_light_tracer_enabled.isChecked(),
        "sphere_fragment_interpolation_enabled": tab.sphere_fragment_interpolation_enabled.isChecked(),
        "sphere_rainbow_ghosting": tab.sphere_rainbow_ghosting.isChecked(),
        "sphere_shadow_enabled": tab.sphere_shadow_enabled.isChecked(),
        "sphere_fill_color": _qcolor_to_list(getattr(tab, "_sphere_fill_color", None), tab._widget_default("spotify_visualizer", "sphere_fill_color")),
        "sphere_edge_color": _qcolor_to_list(getattr(tab, "_sphere_edge_color", None), tab._widget_default("spotify_visualizer", "sphere_edge_color")),
        "sphere_fade_incoming_blocks": tab.sphere_fade_incoming_blocks.isChecked(),
        "sphere_light_direction": tab.sphere_light_direction.currentText(),
        "sphere_deformation": tab.sphere_deformation.value() / 100.0,
        "sphere_base_rotation_speed": tab.sphere_base_rotation_speed.value() / 100.0,
        "sphere_rotation_speed": tab.sphere_rotation_speed.value() / 100.0,
        "sphere_gloss": tab.sphere_gloss.value() / 100.0,
        "sphere_specular": tab.sphere_specular.value() / 100.0,
        "sphere_idle_motion": tab.sphere_idle_motion.value() / 100.0,
        "sphere_surface_detail": tab.sphere_surface_detail.value() / 100.0,
        "sphere_size_response": tab.sphere_size_response.value() / 100.0,
        "sphere_bass_response": tab.sphere_bass_response.value() / 100.0,
        "sphere_mid_response": tab.sphere_mid_response.value() / 100.0,
        "sphere_high_response": tab.sphere_high_response.value() / 100.0,
        "sphere_vocal_response": tab.sphere_vocal_response.value() / 100.0,
        "sphere_bump_reactivity": tab.sphere_bump_reactivity.value() / 100.0,
        "sphere_energy_curve": tab.sphere_energy_curve.value() / 100.0,
    }
