"""Persistence binding for the lazy Sphere Settings body."""
from __future__ import annotations


_SPHERE_SETTING_KEYS = (
    "sphere_material",
    "sphere_deformation",
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
    "sphere_material_fx",
    "sphere_antialiasing",
    "sphere_shadow_enabled",
    "sphere_shadow_strength",
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


def collect_sphere_mode_settings(tab) -> dict:
    return {
        "sphere_material": tab.sphere_material.currentText(),
        "sphere_light_direction": tab.sphere_light_direction.currentText(),
        "sphere_deformation": tab.sphere_deformation.value() / 100.0,
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
        "sphere_material_fx": tab.sphere_material_fx.value() / 100.0,
        "sphere_antialiasing": tab.sphere_antialiasing.isChecked(),
        "sphere_shadow_enabled": tab.sphere_shadow_enabled.isChecked(),
        "sphere_shadow_strength": tab.sphere_shadow_strength.value() / 100.0,
    }
