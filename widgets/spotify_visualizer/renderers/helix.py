"""Helix mode uniform renderer."""
from __future__ import annotations

from PySide6.QtGui import QColor

from widgets.spotify_visualizer.renderers.gl_helpers import set1f as _set1f, set1i as _set1i, set_color4 as _set_color4


def get_uniform_names() -> list[str]:
    return [
        "u_helix_turns", "u_helix_double", "u_helix_speed",
        "u_helix_glow_enabled", "u_helix_glow_intensity",
        "u_helix_glow_color", "u_helix_reactive_glow",
        "u_fill_color", "u_border_color",
        # Energy bands
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    _set1i(gl, u, "u_helix_turns", int(s._helix_turns))
    _set1i(gl, u, "u_helix_double", 1 if s._helix_double else 0)
    _set1f(gl, u, "u_helix_speed", s._helix_speed)
    _set1i(gl, u, "u_helix_glow_enabled", 1 if s._helix_glow_enabled else 0)
    _set1f(gl, u, "u_helix_glow_intensity", s._helix_glow_intensity)
    _set_color4(gl, u, "u_helix_glow_color", s._helix_glow_color)
    _set1i(gl, u, "u_helix_reactive_glow", 1 if s._helix_reactive_glow else 0)

    # Fill / border colours (shared with spectrum)
    _set_color4(gl, u, "u_fill_color", QColor(s._fill_color))
    _set_color4(gl, u, "u_border_color", QColor(s._border_color))

    # Energy bands
    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", eb.overall)
    _set1f(gl, u, "u_bass_energy", eb.bass)
    _set1f(gl, u, "u_mid_energy", eb.mid)
    _set1f(gl, u, "u_high_energy", eb.high)

    return True

