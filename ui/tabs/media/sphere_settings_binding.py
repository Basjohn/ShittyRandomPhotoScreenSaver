"""Persistence binding for the lazy Sphere Settings body."""
from __future__ import annotations


_DEFAULTS = {
    "sphere_material": "Chrome", "sphere_deformation": 1.0,
    "sphere_rotation_speed": .35, "sphere_gloss": .65, "sphere_specular": .8,
    "sphere_light_direction": "NW", "sphere_idle_motion": .12, "sphere_surface_detail": 1.15,
    "sphere_bass_response": 1.0, "sphere_mid_response": 1.0,
    "sphere_high_response": 1.0, "sphere_vocal_response": 1.4,
    "sphere_bump_reactivity": .65,
    "sphere_size_response": 1.5,
    "sphere_energy_curve": .60,
    "sphere_material_fx": 1.0,
    "sphere_antialiasing": True,
    "sphere_shadow_enabled": True,
    "sphere_shadow_strength": .62,
}


def load_sphere_mode_settings(tab, config) -> None:
    for key, default in _DEFAULTS.items():
        control = getattr(tab, key, None)
        if control is None:
            continue
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
