"""Persistence binding for the lazy Sphere Settings body."""
from __future__ import annotations

from PySide6.QtGui import QColor
from ui.color_utils import qcolor_to_list as _qcolor_to_list


_SPHERE_SETTING_KEYS = (
    "sphere_finish",
    "sphere_edge_weight",
    "sphere_voxel_size_variation",
    "sphere_depth_shading_enabled",
    "sphere_depth_shading_strength",
    "sphere_allow_overflow",
    "sphere_cel_shading",
    "sphere_light_tracer_enabled",
    "sphere_fragment_interpolation_enabled",
    "sphere_incoming_density_response_enabled",
    "sphere_incoming_transient_velocity_enabled",
    "sphere_particle_outtake_enabled",
    "sphere_shadow_enabled",
    "sphere_shadow_opacity",
    "sphere_shadow_softness",
    "sphere_shadow_distance",
    "sphere_shadow_size",
    "sphere_fade_incoming_blocks",
    "sphere_fragment_strength",
    "sphere_particle_distance",
    "sphere_particle_amount",
    "sphere_perspective_strength",
    "sphere_taste_the_rainbow_enabled",
    "sphere_taste_the_rainbow_surfaces",
    "sphere_taste_the_rainbow_edges",
    "sphere_base_rotation_speed",
    "sphere_rotation_speed",
    "sphere_gloss",
    "sphere_specular",
    "sphere_light_direction",
    "sphere_vocal_response",
    "sphere_size_response",
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
        ("sphere_tracer_color", "_sphere_tracer_color", "sphere_tracer_color_btn"),
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
        "sphere_incoming_density_response_enabled": tab.sphere_incoming_density_response_enabled.isChecked(),
        "sphere_incoming_transient_velocity_enabled": tab.sphere_incoming_transient_velocity_enabled.isChecked(),
        "sphere_particle_outtake_enabled": tab.sphere_particle_outtake_enabled.isChecked(),
        "sphere_shadow_enabled": tab.sphere_shadow_enabled.isChecked(),
        "sphere_shadow_opacity": tab.sphere_shadow_opacity.value() / 100.0,
        "sphere_shadow_softness": tab.sphere_shadow_softness.value() / 100.0,
        "sphere_shadow_distance": tab.sphere_shadow_distance.value() / 100.0,
        "sphere_shadow_size": tab.sphere_shadow_size.value() / 100.0,
        "sphere_depth_shading_enabled": tab.sphere_depth_shading_enabled.isChecked(),
        "sphere_fill_color": _qcolor_to_list(getattr(tab, "_sphere_fill_color", None), tab._widget_default("spotify_visualizer", "sphere_fill_color")),
        "sphere_edge_color": _qcolor_to_list(getattr(tab, "_sphere_edge_color", None), tab._widget_default("spotify_visualizer", "sphere_edge_color")),
        "sphere_tracer_color": _qcolor_to_list(getattr(tab, "_sphere_tracer_color", None), tab._widget_default("spotify_visualizer", "sphere_tracer_color")),
        "sphere_fade_incoming_blocks": tab.sphere_fade_incoming_blocks.isChecked(),
        "sphere_taste_the_rainbow_enabled": tab.sphere_taste_the_rainbow_enabled.isChecked(),
        "sphere_taste_the_rainbow_surfaces": tab.sphere_taste_the_rainbow_surfaces.isChecked(),
        "sphere_taste_the_rainbow_edges": tab.sphere_taste_the_rainbow_edges.isChecked(),
        "sphere_light_direction": tab.sphere_light_direction.currentText(),
        "sphere_fragment_strength": tab.sphere_fragment_strength.value() / 100.0,
        "sphere_particle_distance": tab.sphere_particle_distance.value() / 100.0,
        "sphere_particle_amount": tab.sphere_particle_amount.value() / 100.0,
        "sphere_perspective_strength": tab.sphere_perspective_strength.value() / 100.0,
        "sphere_edge_weight": tab.sphere_edge_weight.value() / 100.0,
        "sphere_voxel_size_variation": tab.sphere_voxel_size_variation.value() / 100.0,
        "sphere_depth_shading_strength": tab.sphere_depth_shading_strength.value() / 100.0,
        "sphere_base_rotation_speed": tab.sphere_base_rotation_speed.value() / 100.0,
        "sphere_rotation_speed": tab.sphere_rotation_speed.value() / 100.0,
        "sphere_gloss": tab.sphere_gloss.value() / 100.0,
        "sphere_specular": tab.sphere_specular.value() / 100.0,
        "sphere_size_response": tab.sphere_size_response.value() / 100.0,
        "sphere_vocal_response": tab.sphere_vocal_response.value() / 100.0,
    }
