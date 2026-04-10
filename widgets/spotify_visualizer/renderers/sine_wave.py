"""Sine wave mode uniform renderer."""
from __future__ import annotations

import time

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from widgets.spotify_visualizer.renderers.gl_helpers import set1f as _set1f, set1i as _set1i, set_color4 as _set_color4


logger = get_logger(__name__)


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge1 <= edge0:
        return 1.0 if value >= edge1 else 0.0
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _attack_release_step(
    current: float,
    target: float,
    dt: float,
    *,
    attack_ms: float,
    release_ms: float,
) -> float:
    if dt <= 0.0:
        return target
    tau_ms = attack_ms if target >= current else release_ms
    if tau_ms <= 0.0:
        return target
    alpha = 1.0 - pow(2.718281828459045, -dt / (tau_ms / 1000.0))
    return current + (target - current) * alpha


def _compute_sine_reactivity_targets(s) -> dict[str, float]:
    """Derive sine-only beat assist targets from scheduler + smoothed energy.

    This keeps the stronger beat response local to Sine Wave so Oscilloscope
    and other renderers do not inherit the same tuning by accident.
    """
    base_bass = max(0.0, float(getattr(s, '_line_smoothed_bass', 0.0)))
    base_mid = max(0.0, float(getattr(s, '_line_smoothed_mid', 0.0)))
    base_high = max(0.0, float(getattr(s, '_line_smoothed_high', 0.0)))

    kick_evt = max(0.0, float(getattr(s, '_line_kick_event_strength', 0.0)))
    snare_evt = max(0.0, float(getattr(s, '_line_snare_event_strength', 0.0)))
    width_mix = max(0.0, min(1.0, float(getattr(s, '_sine_wave_transient_width_mix', 0.4))))
    base_overall = max(0.0, float(getattr(getattr(s, '_energy_bands', None), 'overall', 0.0)))

    # Keep Sine's scheduler help as a beat-confirmation assist, not a second
    # independent heartbeat source. The actual heartbeat detector should remain
    # the only path capable of producing the larger amplitude swells.
    continuous_support = min(
        1.0,
        max(
            base_bass,
            base_overall * 0.98,
            base_mid * 0.52 + base_high * 0.22,
        ),
    )
    kick_support = min(kick_evt, 0.10 + continuous_support * 0.85)
    snare_support = min(snare_evt, 0.08 + continuous_support * 0.70)
    raw_event_drive = min(1.25, kick_evt * 1.00 + snare_evt * 0.55)
    event_drive = min(raw_event_drive, 0.16 + continuous_support * 0.82)
    beat_drive = min(
        1.0,
        max(
            base_bass * 1.08,
            continuous_support * 0.78 + kick_support * 0.22 + snare_support * 0.10,
        ),
    )

    boosted_bass = min(1.0, max(base_bass, base_bass + kick_support * 0.28 + snare_support * 0.09))
    boosted_mid = min(1.0, max(base_mid, base_mid + snare_support * 0.20 + kick_support * 0.07))
    boosted_high = min(1.0, max(base_high, base_high + snare_support * 0.15))

    boosted_overall = min(
        1.0,
        max(
            base_overall,
            boosted_bass * 0.58 + boosted_mid * 0.27 + boosted_high * 0.15,
        ),
    )

    base_wr = max(0.0, min(1.0, float(getattr(s, '_sine_width_reaction', 0.0))))
    width_boost = width_mix * (
        beat_drive * 0.55
        + kick_support * 0.22
        + snare_support * 0.11
    )
    width_reaction = min(
        1.0,
        max(base_wr, base_wr * (1.0 + continuous_support * 0.25))
        + width_boost,
    )

    raw_sensitivity = max(0.1, float(getattr(s, '_line_sensitivity', 1.0)))
    sensitivity = min(
        5.0,
        raw_sensitivity
        * (1.0 + continuous_support * 0.18 + kick_support * 0.26 + snare_support * 0.12),
    )

    base_heartbeat = max(0.0, float(getattr(s, '_heartbeat_intensity', 0.0)))
    hb_slider = max(0.0, min(1.0, float(getattr(s, '_sine_heartbeat', 0.0))))
    heartbeat_assist_cap = min(0.36, 0.05 + continuous_support * 0.28 + hb_slider * 0.12)
    heartbeat_assist = min(heartbeat_assist_cap, kick_support * 0.30 + snare_support * 0.14)
    heartbeat_intensity = min(1.0, max(base_heartbeat, heartbeat_assist))
    motion_support = min(
        1.0,
        max(
            base_overall * 1.30,
            base_bass * 1.15,
            beat_drive * 0.92,
            base_mid * 0.42 + base_high * 0.24,
            heartbeat_intensity * 0.78,
        ),
    )
    wave_effect_gate = 0.06 + _smoothstep(0.10, 0.42, motion_support) * 0.94

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
        'wave_effect_gate': wave_effect_gate,
        '_diag_kick_evt': kick_evt,
        '_diag_snare_evt': snare_evt,
        '_diag_raw_event_drive': raw_event_drive,
        '_diag_continuous_support': continuous_support,
        '_diag_base_heartbeat': base_heartbeat,
        '_diag_heartbeat_assist': heartbeat_assist,
        '_diag_raw_sensitivity': raw_sensitivity,
        '_diag_base_width_reaction': base_wr,
        '_diag_motion_support': motion_support,
    }


def _compute_sine_reactivity_state(s, *, now_ts: float | None = None) -> dict[str, float]:
    """Return smoothed sine-only assist signals with fast attack / slow release."""
    reactive = _compute_sine_reactivity_targets(s)

    now = time.time() if now_ts is None else float(now_ts)
    last_ts = float(getattr(s, '_sine_reactivity_state_ts', 0.0))
    if last_ts > 0.0:
        dt = max(1.0 / 240.0, min(0.050, now - last_ts))
    else:
        dt = 1.0 / 60.0

    prev = getattr(s, '_sine_reactivity_state_smoothed', None)
    if not isinstance(prev, dict):
        prev = {}

    smoothed = {
        'overall_energy': _attack_release_step(
            float(prev.get('overall_energy', reactive['overall_energy'])),
            reactive['overall_energy'],
            dt,
            attack_ms=28.0,
            release_ms=140.0,
        ),
        'bass_energy': _attack_release_step(
            float(prev.get('bass_energy', reactive['bass_energy'])),
            reactive['bass_energy'],
            dt,
            attack_ms=24.0,
            release_ms=125.0,
        ),
        'mid_energy': _attack_release_step(
            float(prev.get('mid_energy', reactive['mid_energy'])),
            reactive['mid_energy'],
            dt,
            attack_ms=28.0,
            release_ms=150.0,
        ),
        'high_energy': _attack_release_step(
            float(prev.get('high_energy', reactive['high_energy'])),
            reactive['high_energy'],
            dt,
            attack_ms=28.0,
            release_ms=150.0,
        ),
        'beat_drive': _attack_release_step(
            float(prev.get('beat_drive', reactive['beat_drive'])),
            reactive['beat_drive'],
            dt,
            attack_ms=24.0,
            release_ms=150.0,
        ),
        'event_drive': _attack_release_step(
            float(prev.get('event_drive', reactive['event_drive'])),
            reactive['event_drive'],
            dt,
            attack_ms=18.0,
            release_ms=170.0,
        ),
        'width_reaction': _attack_release_step(
            float(prev.get('width_reaction', reactive['width_reaction'])),
            reactive['width_reaction'],
            dt,
            attack_ms=24.0,
            release_ms=185.0,
        ),
        'sensitivity': _attack_release_step(
            float(prev.get('sensitivity', reactive['sensitivity'])),
            reactive['sensitivity'],
            dt,
            attack_ms=22.0,
            release_ms=175.0,
        ),
        'heartbeat_intensity': _attack_release_step(
            float(prev.get('heartbeat_intensity', reactive['heartbeat_intensity'])),
            reactive['heartbeat_intensity'],
            dt,
            attack_ms=16.0,
            release_ms=210.0,
        ),
        'wave_effect_gate': _attack_release_step(
            float(prev.get('wave_effect_gate', reactive['wave_effect_gate'])),
            reactive['wave_effect_gate'],
            dt,
            attack_ms=36.0,
            release_ms=240.0,
        ),
    }

    setattr(s, '_sine_reactivity_state_smoothed', smoothed)
    setattr(s, '_sine_reactivity_state_ts', now)

    if is_viz_diagnostics_enabled():
        last_diag_ts = float(getattr(s, '_sine_reactivity_diag_last_ts', 0.0))
        if (
            reactive['event_drive'] > smoothed['event_drive'] + 0.10
            or reactive['heartbeat_intensity'] > smoothed['heartbeat_intensity'] + 0.06
            or (now - last_diag_ts) >= 0.75
        ):
            logger.debug(
                (
                    "[SPOTIFY_VIS][SINE][ASSIST] bass=%.3f mid=%.3f high=%.3f overall=%.3f "
                    "kick=%.3f snare=%.3f raw_evt=%.3f evt=%.3f support=%.3f "
                    "hb_base=%.3f hb_assist=%.3f hb=%.3f sens_raw=%.3f sens=%.3f "
                    "wr_base=%.3f wr=%.3f motion=%.3f wave_gate=%.3f "
                    "evt_s=%.3f hb_s=%.3f wr_s=%.3f sens_s=%.3f gate_s=%.3f dt=%.3f"
                ),
                max(0.0, float(getattr(s, '_line_smoothed_bass', 0.0))),
                max(0.0, float(getattr(s, '_line_smoothed_mid', 0.0))),
                max(0.0, float(getattr(s, '_line_smoothed_high', 0.0))),
                max(0.0, float(getattr(getattr(s, '_energy_bands', None), 'overall', 0.0))),
                reactive['_diag_kick_evt'],
                reactive['_diag_snare_evt'],
                reactive['_diag_raw_event_drive'],
                reactive['event_drive'],
                reactive['_diag_continuous_support'],
                reactive['_diag_base_heartbeat'],
                reactive['_diag_heartbeat_assist'],
                reactive['heartbeat_intensity'],
                reactive['_diag_raw_sensitivity'],
                reactive['sensitivity'],
                reactive['_diag_base_width_reaction'],
                reactive['width_reaction'],
                reactive['_diag_motion_support'],
                reactive['wave_effect_gate'],
                smoothed['event_drive'],
                smoothed['heartbeat_intensity'],
                smoothed['width_reaction'],
                smoothed['sensitivity'],
                smoothed['wave_effect_gate'],
                dt,
            )
            setattr(s, '_sine_reactivity_diag_last_ts', now)

    return smoothed


def get_uniform_names() -> list[str]:
    return [
        "u_playing",
        "u_sine_speed", "u_sine_line_dim", "u_sine_line_offset_bias",
        "u_sine_travel", "u_card_adaptation",
        "u_sine_travel_line2", "u_sine_travel_line3",
        "u_wave_effect", "u_micro_wobble", "u_crawl_amount",
        "u_wave_effect_gate",
        "u_sine_vertical_shift",
        "u_heartbeat", "u_heartbeat_intensity", "u_width_reaction",
        "u_sine_density", "u_sine_displacement",
        "u_sine_line1_shift", "u_sine_line2_shift", "u_sine_line3_shift",
        # Ghost (peak-tracked energy envelope)
        "u_ghost_alpha", "u_ghost_bass", "u_ghost_mid", "u_ghost_high",
        "u_ghost_line2_enabled", "u_ghost_line3_enabled",
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
    _set1i(gl, u, "u_ghost_line2_enabled", 1 if getattr(s, "_sine_ghost_line2_enabled", True) else 0)
    _set1i(gl, u, "u_ghost_line3_enabled", 1 if getattr(s, "_sine_ghost_line3_enabled", True) else 0)
    _set1f(gl, u, "u_ghost_bass", getattr(s, '_sine_peak_bass', 0.0))
    _set1f(gl, u, "u_ghost_mid", getattr(s, '_sine_peak_mid', 0.0))
    _set1f(gl, u, "u_ghost_high", getattr(s, '_sine_peak_high', 0.0))
    _set1f(gl, u, "u_sine_speed", s._line_speed)
    _set1i(gl, u, "u_sine_line_dim", 1 if s._line_dim else 0)
    _set1f(gl, u, "u_sine_line_offset_bias", s._line_offset_bias)
    _set1i(gl, u, "u_sine_travel", int(s._sine_wave_travel))
    _set1f(gl, u, "u_card_adaptation", s._sine_card_adaptation)
    _set1i(gl, u, "u_sine_travel_line2", int(s._sine_travel_line2))
    _set1i(gl, u, "u_sine_travel_line3", int(s._sine_travel_line3))
    _set1f(gl, u, "u_wave_effect", s._sine_wave_effect)
    _set1f(gl, u, "u_micro_wobble", s._sine_micro_wobble)
    _set1f(gl, u, "u_crawl_amount", s._sine_crawl_amount)
    _set1f(gl, u, "u_wave_effect_gate", reactive['wave_effect_gate'])
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
    _set1f(gl, u, "u_sensitivity", (reactive or {}).get('sensitivity', s._line_sensitivity))
    _set1f(gl, u, "u_smoothing", s._line_smoothing)
    _set_color4(gl, u, "u_line_color", s._line_color)
    _set1i(gl, u, "u_line_count", s._line_count)
    for uname, qc in (
        ("u_line2_color", s._line2_color),
        ("u_line2_glow_color", s._line2_glow_color),
        ("u_line3_color", s._line3_color),
        ("u_line3_glow_color", s._line3_glow_color),
    ):
        _set_color4(gl, u, uname, qc)

