"""Persistence binding for the lazy Sphere Settings body."""
from __future__ import annotations


_DEFAULTS = {
    "sphere_material": "Chrome", "sphere_deformation": 1.0,
    "sphere_rotation_speed": .35, "sphere_gloss": .65, "sphere_specular": .8,
    "sphere_light_direction": "NW", "sphere_idle_motion": .12, "sphere_surface_detail": 1.0,
}


def load_sphere_mode_settings(tab, config) -> None:
    for key, default in _DEFAULTS.items():
        control = getattr(tab, key, None)
        if control is None:
            continue
        value = config.get(key, default)
        if hasattr(control, "setCurrentText"):
            control.setCurrentText(str(value))
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
    }
