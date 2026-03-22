"""Sine wave mode uniform renderer."""
from __future__ import annotations

from widgets.spotify_visualizer.renderers.gl_helpers import set1f as _set1f, set1i as _set1i, set_color4 as _set_color4


def _compute_sine_reactivity_state(s) -> dict[str, float]:
    """Derive sine-only beat assist signals from scheduler + smoothed energy.

    This keeps the stronger beat response local to Sine Wave so Oscilloscope
    and other renderers do not inherit the same tuning by accident.
    """
    base_bass = max(0.0, float(getattr(s, '_osc_smoothed_bass', 0.0)))
    base_mid = max(0.0, float(getattr(s, '_osc_smoothed_mid', 0.0)))
    base_high = max(0.0, float(getattr(s, '_osc_smoothed_high', 0.0)))

    kick_evt = max(0.0, float(getattr(s, '_line_kick_event_strength', 0.0)))
    snare_evt = max(0.0, float(getattr(s, '_line_snare_event_strength', 0.0)))
    width_mix = max(0.0, min(1.0, float(getattr(s, '_sine_wave_transient_width_mix', 0.4))))

    beat_drive = max(base_bass, kick_evt * 0.95 + snare_evt * 0.35)
    event_drive = min(1.25, kick_evt * 1.00 + snare_evt * 0.55)

    boosted_bass = min(1.0, max(base_bass, base_bass + kick_evt * 0.55 + snare_evt * 0.12))
    boosted_mid = min(1.0, max(base_mid, base_mid + snare_evt * 0.32 + kick_evt * 0.10))
    boosted_high = min(1.0, max(base_high, base_high + snare_evt * 0.22))

    base_overall = max(0.0, float(getattr(getattr(s, '_energy_bands', None), 'overall', 0.0)))
    boosted_overall = min(
        1.0,
        max(
            base_overall,
            boosted_bass * 0.58 + boosted_mid * 0.27 + boosted_high * 0.15,
        ),
    )

    base_wr = max(0.0, min(1.0, float(getattr(s, '_sine_width_reaction', 0.0))))
    width_reaction = min(1.0, base_wr * (1.0 + beat_drive * width_mix + event_drive * 0.18))

    base_sensitivity = max(0.1, float(getattr(s, '_osc_line_amplitude', 1.0)))
    sensitivity = min(5.0, base_sensitivity * (1.0 + event_drive * 0.40))

    base_heartbeat = max(0.0, float(getattr(s, '_heartbeat_intensity', 0.0)))
    heartbeat_intensity = min(1.0, max(base_heartbeat, kick_evt * 0.85 + snare_evt * 0.20))

    return {
        'overall_energy': boosted_overall,
        'bass_energy': boosted_bass,
        'mid_energy': boosted_mid,
        'high_energy': boosted_high,
        'beat_drive': beat_drive,
        'event_drive': event_drive,
        'width_reaction': width_reaction,
        'sensitivity': sensitivity,
        'heartbeat_intensity': heartbeat_intensity,
    }


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
        # Ghost (peak-tracked energy envelope)
        "u_ghost_alpha", "u_ghost_bass", "u_ghost_mid", "u_ghost_high",
        # Shared line/glow
        "u_glow_enabled", "u_glow_intensity", "u_glow_size", "u_glow_reactivity", "u_glow_color",
        "u_reactive_glow", "u_sensitivity", "u_smoothing",
        "u_line_color", "u_line_count",
        "u_line2_color", "u_line2_glow_color",
        "u_line3_color", "u_line3_glow_color",
        # Energy bands (smoothed)
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    reactive = _compute_sine_reactivity_state(s)
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    # Ghost alpha (mode-specific: sine wave)
    loc = u.get("u_ghost_alpha", -1)
    if loc >= 0:
        try:
            ga = float(s._sine_ghost_alpha if s._sine_ghosting_enabled else 0.0)
        except Exception:
            ga = 0.0
        gl.glUniform1f(loc, max(0.0, min(1.0, ga)))
    _set1f(gl, u, "u_ghost_bass", getattr(s, '_sine_peak_bass', 0.0))
    _set1f(gl, u, "u_ghost_mid", getattr(s, '_sine_peak_mid', 0.0))
    _set1f(gl, u, "u_ghost_high", getattr(s, '_sine_peak_high', 0.0))
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
    _set1f(gl, u, "u_heartbeat_intensity", reactive['heartbeat_intensity'])
    _set1f(gl, u, "u_width_reaction", reactive['width_reaction'])
    _set1f(gl, u, "u_sine_density", s._sine_density)
    _set1f(gl, u, "u_sine_displacement", s._sine_displacement)
    _set1f(gl, u, "u_sine_line1_shift", s._sine_line1_shift)
    _set1f(gl, u, "u_sine_line2_shift", s._sine_line2_shift)
    _set1f(gl, u, "u_sine_line3_shift", s._sine_line3_shift)

    # Shared line/glow
    _upload_shared_line_glow(gl, u, s, reactive)

    # Energy bands (CPU-smoothed for anti-flicker)
    _set1f(gl, u, "u_overall_energy", reactive['overall_energy'])
    _set1f(gl, u, "u_bass_energy", reactive['bass_energy'])
    _set1f(gl, u, "u_mid_energy", reactive['mid_energy'])
    _set1f(gl, u, "u_high_energy", reactive['high_energy'])

    return True


def _upload_shared_line_glow(gl, u, s, reactive: dict[str, float] | None = None):
    _set1i(gl, u, "u_glow_enabled", 1 if s._glow_enabled else 0)
    _set1f(gl, u, "u_glow_intensity", s._glow_intensity)
    _set1f(gl, u, "u_glow_size", getattr(s, '_glow_size', 1.0))
    _set1f(gl, u, "u_glow_reactivity", getattr(s, '_glow_reactivity', 1.0))
    _set_color4(gl, u, "u_glow_color", s._glow_color)
    _set1i(gl, u, "u_reactive_glow", 1 if s._reactive_glow else 0)
    _set1f(gl, u, "u_sensitivity", (reactive or {}).get('sensitivity', s._osc_line_amplitude))
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

