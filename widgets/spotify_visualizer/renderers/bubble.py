"""Bubble mode uniform renderer."""
from __future__ import annotations

import numpy as np

from widgets.spotify_visualizer.renderers.gl_helpers import set1f as _set1f, set1i as _set1i, set_color4 as _set_color4


_DIRECTION_VECS = {
    'top_left': (-0.707, 0.707),
    'top': (0.0, 1.0),
    'top_right': (0.707, 0.707),
    'left': (-1.0, 0.0),
    'right': (1.0, 0.0),
    'bottom_left': (-0.707, -0.707),
    'bottom': (0.0, -1.0),
    'bottom_right': (0.707, -0.707),
    'center_out': (0.0, 0.0),
}


def get_uniform_names() -> list[str]:
    return [
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
        "u_playing", "u_bubble_count",
        "u_bubbles_pos", "u_bubbles_extra", "u_bubbles_trail",
        "u_trail_strength", "u_tail_opacity",
        "u_specular_dir", "u_gradient_dir",
        "u_outline_color", "u_specular_color",
        "u_gradient_light", "u_gradient_dark", "u_pop_color",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    # Energy bands
    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", eb.overall)
    _set1f(gl, u, "u_bass_energy", eb.bass)
    _set1f(gl, u, "u_mid_energy", eb.mid)
    _set1f(gl, u, "u_high_energy", eb.high)
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    # Bubble count
    bcount = min(s._bubble_count, 110)
    _set1i(gl, u, "u_bubble_count", bcount)

    # Bubble position data (vec4 array: x, y, radius, alpha)
    loc = u.get("u_bubbles_pos", -1)
    if loc >= 0 and bcount > 0:
        pos_data = s._bubble_pos_data
        pos_buf = np.zeros(110 * 4, dtype="float32")
        copy_len = min(len(pos_data), 110 * 4)
        for i in range(copy_len):
            pos_buf[i] = float(pos_data[i])
        gl.glUniform4fv(loc, 110, pos_buf)

    # Bubble extra data (vec4 array: spec_size, rotation, spec_ox, spec_oy)
    loc = u.get("u_bubbles_extra", -1)
    if loc >= 0 and bcount > 0:
        extra_data = s._bubble_extra_data
        extra_buf = np.zeros(110 * 4, dtype="float32")
        copy_len = min(len(extra_data), 110 * 4)
        for i in range(copy_len):
            extra_buf[i] = float(extra_data[i])
        gl.glUniform4fv(loc, 110, extra_buf)

    # Bubble trail data (vec3 array: TRAIL_STEPS xy + strength per bubble)
    loc = u.get("u_bubbles_trail", -1)
    if loc >= 0 and bcount > 0:
        trail_data = s._bubble_trail_data
        trail_buf = np.zeros(110 * 3 * 3, dtype="float32")
        copy_len = min(len(trail_data), 110 * 3 * 3)
        for i in range(copy_len):
            trail_buf[i] = float(trail_data[i])
        gl.glUniform3fv(loc, 110 * 3, trail_buf)

    _set1f(gl, u, "u_trail_strength", s._bubble_trail_strength)
    _set1f(gl, u, "u_tail_opacity", s._bubble_tail_opacity)

    # Specular direction
    sd = _DIRECTION_VECS.get(s._bubble_specular_direction, (-0.707, 0.707))
    loc = u.get("u_specular_dir", -1)
    if loc >= 0:
        gl.glUniform2f(loc, float(sd[0]), float(sd[1]))

    gd = _DIRECTION_VECS.get(s._bubble_gradient_direction, (0.0, 1.0))
    loc = u.get("u_gradient_dir", -1)
    if loc >= 0:
        gl.glUniform2f(loc, float(gd[0]), float(gd[1]))

    # Colour uniforms
    for uname, qc in (
        ("u_outline_color", s._bubble_outline_color),
        ("u_specular_color", s._bubble_specular_color),
        ("u_gradient_light", s._bubble_gradient_light),
        ("u_gradient_dark", s._bubble_gradient_dark),
        ("u_pop_color", s._bubble_pop_color),
    ):
        _set_color4(gl, u, uname, qc)

    return True

