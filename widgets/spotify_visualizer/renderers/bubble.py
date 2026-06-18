"""Bubble mode uniform renderer."""
from __future__ import annotations

import numpy as np

from core.settings.bubble_gradient_semantics import (
    get_bubble_gradient_shader_mode,
    get_bubble_gradient_shader_vector,
)
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

_MAX_BUBBLES = 110
_BUBBLE_POS_SIZE = _MAX_BUBBLES * 4
_BUBBLE_EXTRA_SIZE = _MAX_BUBBLES * 4
_BUBBLE_TRAIL_SIZE = _MAX_BUBBLES * 3 * 3


def _copy_float_buffer(state, attr_name: str, source, size: int, *, active_size: int):
    """Reuse a persistent float32 buffer on the overlay state.

    Bubble's runtime output is already behavior-authoritative by the time it
    reaches this seam; the hot path work here should stay transport-only.
    """
    buf = getattr(state, attr_name, None)
    active_attr = f"{attr_name}_active_size"
    if not isinstance(buf, np.ndarray) or buf.dtype != np.float32 or int(buf.size) != int(size):
        buf = np.zeros(size, dtype=np.float32)
        setattr(state, attr_name, buf)
        setattr(state, active_attr, 0)

    prev_active = int(getattr(state, active_attr, 0) or 0)
    clear_upto = max(0, min(int(size), max(prev_active, int(active_size))))
    if clear_upto > 0:
        buf[:clear_upto].fill(0.0)

    if source is None:
        setattr(state, active_attr, clear_upto)
        return buf

    try:
        source_len = len(source)
    except Exception:
        source_len = 0
    copy_len = min(int(source_len), int(size), max(0, int(active_size)))
    setattr(state, active_attr, clear_upto)
    if copy_len <= 0:
        return buf

    if source_len == copy_len:
        buf[:copy_len] = source
    else:
        buf[:copy_len] = source[:copy_len]
    return buf


def get_uniform_names() -> list[str]:
    return [
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
        "u_playing", "u_ghost_alpha", "u_bubble_count",
        "u_bubbles_pos", "u_bubbles_extra", "u_bubbles_trail",
        "u_trail_strength", "u_tail_opacity",
        "u_specular_dir", "u_gradient_dir", "u_gradient_mode",
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

    # Ghost alpha (mode-specific: bubble)
    loc = u.get("u_ghost_alpha", -1)
    if loc >= 0:
        try:
            ga = float(s._bubble_ghost_alpha if s._bubble_ghosting_enabled else 0.0)
        except Exception:
            ga = 0.0
        gl.glUniform1f(loc, max(0.0, min(1.0, ga)))

    # Bubble count
    bcount = min(s._bubble_count, _MAX_BUBBLES)
    _set1i(gl, u, "u_bubble_count", bcount)

    # Bubble position data (vec4 array: x, y, radius, alpha)
    loc = u.get("u_bubbles_pos", -1)
    if loc >= 0 and bcount > 0:
        pos_buf = _copy_float_buffer(
            s,
            "_bubble_uniform_pos_buf",
            s._bubble_pos_data,
            _BUBBLE_POS_SIZE,
            active_size=bcount * 4,
        )
        gl.glUniform4fv(loc, bcount, pos_buf)

    # Bubble extra data (vec4 array: spec_size, rotation, spec_ox, spec_oy)
    loc = u.get("u_bubbles_extra", -1)
    if loc >= 0 and bcount > 0:
        extra_buf = _copy_float_buffer(
            s,
            "_bubble_uniform_extra_buf",
            s._bubble_extra_data,
            _BUBBLE_EXTRA_SIZE,
            active_size=bcount * 4,
        )
        gl.glUniform4fv(loc, bcount, extra_buf)

    # Bubble trail data (vec3 array: TRAIL_STEPS xy + strength per bubble)
    loc = u.get("u_bubbles_trail", -1)
    trail_enabled = (
        bcount > 0
        and float(getattr(s, "_bubble_trail_strength", 0.0) or 0.0) > 0.001
        and float(getattr(s, "_bubble_tail_opacity", 0.0) or 0.0) > 0.001
    )
    if loc >= 0 and trail_enabled:
        trail_buf = _copy_float_buffer(
            s,
            "_bubble_uniform_trail_buf",
            s._bubble_trail_data,
            _BUBBLE_TRAIL_SIZE,
            active_size=bcount * 9,
        )
        gl.glUniform3fv(loc, bcount * 3, trail_buf)

    _set1f(gl, u, "u_trail_strength", s._bubble_trail_strength)
    _set1f(gl, u, "u_tail_opacity", s._bubble_tail_opacity)

    # Specular direction
    sd = _DIRECTION_VECS.get(s._bubble_specular_direction, (-0.707, 0.707))
    loc = u.get("u_specular_dir", -1)
    if loc >= 0:
        gl.glUniform2f(loc, float(sd[0]), float(sd[1]))

    gd = get_bubble_gradient_shader_vector(getattr(s, "_bubble_gradient_direction", "top"))
    loc = u.get("u_gradient_dir", -1)
    if loc >= 0:
        gl.glUniform2f(loc, float(gd[0]), float(gd[1]))
    _set1i(gl, u, "u_gradient_mode", get_bubble_gradient_shader_mode(getattr(s, "_bubble_gradient_direction", "top")))

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

