"""Oscilloscope mode uniform renderer."""
from __future__ import annotations

import numpy as np

from widgets.spotify_visualizer.renderers.gl_helpers import set1f as _set1f, set1i as _set1i, set_color4 as _set_color4


def get_uniform_names() -> list[str]:
    return [
        "u_waveform_count", "u_waveform",
        "u_osc_ghost_alpha", "u_prev_waveform",
        "u_glow_enabled", "u_glow_intensity", "u_glow_size", "u_glow_color",
        "u_reactive_glow", "u_sensitivity", "u_smoothing",
        "u_line_color", "u_line_count",
        "u_line2_color", "u_line2_glow_color",
        "u_line3_color", "u_line3_glow_color",
        "u_osc_speed", "u_osc_line_dim", "u_osc_line_offset_bias",
        "u_osc_vertical_shift",
        # Energy bands (smoothed)
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    # Waveform data
    wf = s._waveform
    wf_count = min(len(wf), 256) if wf else 0
    _set1i(gl, u, "u_waveform_count", max(wf_count, 2))
    loc = u.get("u_waveform", -1)
    if loc >= 0 and wf_count > 0:
        wf_buf = np.zeros(256, dtype="float32")
        for i in range(wf_count):
            wf_buf[i] = float(wf[i])
        gl.glUniform1fv(loc, 256, wf_buf)

    # Ghost waveform
    _set1f(gl, u, "u_osc_ghost_alpha", s._osc_ghost_alpha)
    loc = u.get("u_prev_waveform", -1)
    if loc >= 0 and s._osc_ghost_alpha > 0.001:
        prev_wf = s._prev_waveform
        prev_count = min(len(prev_wf), 256) if prev_wf else 0
        prev_buf = np.zeros(256, dtype="float32")
        for i in range(prev_count):
            prev_buf[i] = float(prev_wf[i])
        gl.glUniform1fv(loc, 256, prev_buf)

    # Shared line/glow uniforms
    _upload_shared_line_glow(gl, u, s)

    # Energy bands (CPU-smoothed for anti-flicker)
    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", eb.overall)
    _set1f(gl, u, "u_bass_energy", s._osc_smoothed_bass)
    _set1f(gl, u, "u_mid_energy", s._osc_smoothed_mid)
    _set1f(gl, u, "u_high_energy", s._osc_smoothed_high)

    # Osc-specific
    _set1f(gl, u, "u_osc_speed", s._osc_speed)
    _set1i(gl, u, "u_osc_line_dim", 1 if s._osc_line_dim else 0)
    _set1f(gl, u, "u_osc_line_offset_bias", s._osc_line_offset_bias)
    _set1i(gl, u, "u_osc_vertical_shift", int(s._osc_vertical_shift))

    return True


def _upload_shared_line_glow(gl, u, s):
    """Upload uniforms shared between oscilloscope and sine_wave."""
    _set1i(gl, u, "u_glow_enabled", 1 if s._glow_enabled else 0)
    _set1f(gl, u, "u_glow_intensity", s._glow_intensity)
    _set1f(gl, u, "u_glow_size", getattr(s, '_glow_size', 1.0))
    _set_color4(gl, u, "u_glow_color", s._glow_color)
    _set1i(gl, u, "u_reactive_glow", 1 if s._reactive_glow else 0)
    _set1f(gl, u, "u_sensitivity", s._osc_line_amplitude)
    _set1f(gl, u, "u_smoothing", s._osc_smoothing)
    _set_color4(gl, u, "u_line_color", s._line_color)
    _set1i(gl, u, "u_line_count", s._osc_line_count)
    for uname, qc in (
        ("u_line2_color", s._osc_line2_color),
        ("u_line2_glow_color", s._osc_line2_glow_color),
        ("u_line3_color", s._osc_line3_color),
        ("u_line3_glow_color", s._osc_line3_glow_color),
    ):
        _set_color4(gl, u, uname, qc)

