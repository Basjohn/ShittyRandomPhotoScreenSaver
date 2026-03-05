"""Sine wave mode uniform renderer."""
from __future__ import annotations


def get_uniform_names() -> list[str]:
    return [
        "u_playing",
        "u_sine_speed", "u_sine_line_dim", "u_sine_line_offset_bias",
        "u_sine_travel", "u_card_adaptation",
        "u_sine_travel_line2", "u_sine_travel_line3",
        "u_wave_effect", "u_micro_wobble", "u_crawl_amount",
        "u_sine_vertical_shift",
        "u_heartbeat", "u_heartbeat_intensity", "u_width_reaction",
        "u_sine_density", "u_sine_displacement",
        "u_sine_line1_shift", "u_sine_line2_shift", "u_sine_line3_shift",
        # Shared line/glow
        "u_glow_enabled", "u_glow_intensity", "u_glow_color",
        "u_reactive_glow", "u_sensitivity", "u_smoothing",
        "u_line_color", "u_line_count",
        "u_line2_color", "u_line2_glow_color",
        "u_line3_color", "u_line3_glow_color",
        # Energy bands (smoothed)
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)
    _set1f(gl, u, "u_sine_speed", s._osc_speed)
    _set1i(gl, u, "u_sine_line_dim", 1 if s._osc_line_dim else 0)
    _set1f(gl, u, "u_sine_line_offset_bias", s._osc_line_offset_bias)
    _set1i(gl, u, "u_sine_travel", int(s._osc_sine_travel))
    _set1f(gl, u, "u_card_adaptation", s._sine_card_adaptation)
    _set1i(gl, u, "u_sine_travel_line2", int(s._sine_travel_line2))
    _set1i(gl, u, "u_sine_travel_line3", int(s._sine_travel_line3))
    _set1f(gl, u, "u_wave_effect", s._sine_wave_effect)
    _set1f(gl, u, "u_micro_wobble", s._sine_micro_wobble)
    _set1f(gl, u, "u_crawl_amount", s._sine_crawl_amount)
    _set1i(gl, u, "u_sine_vertical_shift", int(s._sine_vertical_shift))
    _set1f(gl, u, "u_heartbeat", s._sine_heartbeat)
    _set1f(gl, u, "u_heartbeat_intensity", s._heartbeat_intensity)
    _set1f(gl, u, "u_width_reaction", s._sine_width_reaction)
    _set1f(gl, u, "u_sine_density", s._sine_density)
    _set1f(gl, u, "u_sine_displacement", s._sine_displacement)
    _set1f(gl, u, "u_sine_line1_shift", s._sine_line1_shift)
    _set1f(gl, u, "u_sine_line2_shift", s._sine_line2_shift)
    _set1f(gl, u, "u_sine_line3_shift", s._sine_line3_shift)

    # Shared line/glow
    _upload_shared_line_glow(gl, u, s)

    # Energy bands (CPU-smoothed for anti-flicker)
    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", eb.overall)
    _set1f(gl, u, "u_bass_energy", s._osc_smoothed_bass)
    _set1f(gl, u, "u_mid_energy", s._osc_smoothed_mid)
    _set1f(gl, u, "u_high_energy", s._osc_smoothed_high)

    return True


def _upload_shared_line_glow(gl, u, s):
    _set1i(gl, u, "u_glow_enabled", 1 if s._glow_enabled else 0)
    _set1f(gl, u, "u_glow_intensity", s._glow_intensity)
    _set_color4(gl, u, "u_glow_color", s._glow_color)
    _set1i(gl, u, "u_reactive_glow", 1 if s._reactive_glow else 0)
    _set1f(gl, u, "u_sensitivity", s._osc_sensitivity)
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
