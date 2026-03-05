"""Blob mode uniform renderer."""
from __future__ import annotations


def get_uniform_names() -> list[str]:
    return [
        "u_playing", "u_ghost_alpha",
        "u_blob_color", "u_blob_glow_color", "u_blob_edge_color",
        "u_blob_pulse", "u_blob_width", "u_blob_size",
        "u_blob_glow_intensity", "u_blob_glow_reactivity", "u_blob_glow_max_size",
        "u_blob_reactive_glow", "u_blob_outline_color",
        "u_blob_smoothed_energy", "u_blob_peak_energy",
        "u_blob_reactive_deformation", "u_blob_stage_gain",
        "u_blob_core_scale", "u_blob_core_floor_bias", "u_blob_stage_bias",
        "u_blob_stage_progress_override",
        "u_blob_constant_wobble", "u_blob_reactive_wobble", "u_blob_stretch_tendency",
        # Energy bands (shared)
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    # Ghost alpha
    loc = u.get("u_ghost_alpha", -1)
    if loc >= 0:
        try:
            ga = float(s._ghost_alpha if s._ghosting_enabled else 0.0)
        except Exception:
            ga = 0.0
        gl.glUniform1f(loc, max(0.0, min(1.0, ga)))

    _set_color4(gl, u, "u_blob_color", s._blob_color)
    _set_color4(gl, u, "u_blob_glow_color", s._blob_glow_color)
    _set_color4(gl, u, "u_blob_edge_color", s._blob_edge_color)
    _set1f(gl, u, "u_blob_pulse", s._blob_pulse)
    _set1f(gl, u, "u_blob_width", s._blob_width)
    _set1f(gl, u, "u_blob_size", s._blob_size)
    _set1f(gl, u, "u_blob_glow_intensity", s._blob_glow_intensity)
    _set1f(gl, u, "u_blob_glow_reactivity", s._blob_glow_reactivity)
    _set1f(gl, u, "u_blob_glow_max_size", s._blob_glow_max_size)
    _set1i(gl, u, "u_blob_reactive_glow", 1 if s._blob_reactive_glow else 0)
    _set_color4(gl, u, "u_blob_outline_color", s._blob_outline_color)
    _set1f(gl, u, "u_blob_smoothed_energy", s._blob_smoothed_energy)
    _set1f(gl, u, "u_blob_peak_energy", s._blob_peak_energy)
    _set1f(gl, u, "u_blob_reactive_deformation", s._blob_reactive_deformation)
    _set1f(gl, u, "u_blob_stage_gain", s._blob_stage_gain)
    _set1f(gl, u, "u_blob_core_scale", s._blob_core_scale)
    _set1f(gl, u, "u_blob_core_floor_bias", s._blob_core_floor_bias)
    _set1f(gl, u, "u_blob_stage_bias", s._blob_stage_bias)

    loc = u.get("u_blob_stage_progress_override", -1)
    if loc >= 0:
        stage_vals = (
            s._blob_stage_progress_filtered
            if s._blob_stage_progress_ready
            else (-1.0, -1.0, -1.0)
        )
        gl.glUniform3f(loc, float(stage_vals[0]), float(stage_vals[1]), float(stage_vals[2]))

    _set1f(gl, u, "u_blob_constant_wobble", s._blob_constant_wobble)
    _set1f(gl, u, "u_blob_reactive_wobble", s._blob_reactive_wobble)
    _set1f(gl, u, "u_blob_stretch_tendency", s._blob_stretch_tendency)

    # Energy bands
    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", eb.overall)
    _set1f(gl, u, "u_bass_energy", eb.bass)
    _set1f(gl, u, "u_mid_energy", eb.mid)
    _set1f(gl, u, "u_high_energy", eb.high)

    return True


def _set1f(gl, u, name, val):
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform1f(loc, float(val))

def _set1i(gl, u, name, val):
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform1i(loc, int(val))

def _set_color4(gl, u, name, qc):
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform4f(loc, float(qc.redF()), float(qc.greenF()),
                        float(qc.blueF()), float(qc.alphaF()))
