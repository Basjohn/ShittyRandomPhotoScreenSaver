"""Sine wave mode uniform renderer."""
from __future__ import annotations

import math
import time

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from widgets.spotify_visualizer.renderers.gl_helpers import set1f as _set1f, set1i as _set1i, set_color4 as _set_color4
from widgets.spotify_visualizer.sine_reactivity import (
    advance_sine_reactivity,
    compute_sine_reactivity_targets,
)


logger = get_logger(__name__)


def _compute_sine_reactivity_targets(s) -> dict[str, float]:
    """Derive sine-only beat assist targets from scheduler + smoothed energy.

    This keeps the stronger beat response local to Sine Wave so Oscilloscope
    and other renderers do not inherit the same tuning by accident.
    """
    return compute_sine_reactivity_targets(
        smoothed_bass=float(getattr(s, '_line_smoothed_bass', 0.0)),
        smoothed_mid=float(getattr(s, '_line_smoothed_mid', 0.0)),
        smoothed_high=float(getattr(s, '_line_smoothed_high', 0.0)),
        overall_energy=float(
            getattr(getattr(s, '_energy_bands', None), 'overall', 0.0)
        ),
        kick_event=float(getattr(s, '_line_kick_event_strength', 0.0)),
        snare_event=float(getattr(s, '_line_snare_event_strength', 0.0)),
        transient_width_mix=float(
            getattr(s, '_sine_wave_transient_width_mix', 0.4)
        ),
        base_width_reaction=float(getattr(s, '_sine_width_reaction', 0.0)),
        base_sensitivity=float(getattr(s, '_line_sensitivity', 1.0)),
        base_heartbeat=float(getattr(s, '_heartbeat_intensity', 0.0)),
        heartbeat_slider=float(getattr(s, '_sine_heartbeat', 0.0)),
    )


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

    smoothed = advance_sine_reactivity(prev, reactive, dt=dt)

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
        "u_sine_travel_line4", "u_sine_travel_line5", "u_sine_travel_line6",
        "u_wave_effect", "u_micro_wobble", "u_crawl_amount",
        "u_wave_effect_gate",
        "u_sine_vertical_shift",
        "u_heartbeat", "u_heartbeat_intensity", "u_width_reaction",
        "u_sine_density", "u_sine_displacement",
        "u_sine_line1_shift", "u_sine_line2_shift", "u_sine_line3_shift",
        "u_sine_line4_shift", "u_sine_line5_shift", "u_sine_line6_shift",
        # Ghost (peak-tracked energy envelope)
        "u_ghost_alpha", "u_ghost_bass", "u_ghost_mid", "u_ghost_high",
        "u_ghost_line2_enabled", "u_ghost_line3_enabled",
        "u_ghost_line4_enabled", "u_ghost_line5_enabled", "u_ghost_line6_enabled",
        # Shared line/glow
        "u_glow_enabled", "u_glow_intensity", "u_glow_size", "u_glow_reactivity", "u_glow_color",
        "u_reactive_glow", "u_sensitivity", "u_smoothing",
        "u_line_color", "u_line_count",
        "u_line2_color", "u_line2_glow_color",
        "u_line3_color", "u_line3_glow_color",
        "u_line4_color", "u_line4_glow_color",
        "u_line5_color", "u_line5_glow_color",
        "u_line6_color", "u_line6_glow_color",
        # Energy bands (smoothed)
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    now = time.time()
    reactive = _compute_sine_reactivity_state(s)
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    line_count = max(1, min(6, int(getattr(s, "_line_count", 1))))
    t1 = int(getattr(s, "_sine_wave_travel", 0))
    t2 = int(getattr(s, "_sine_travel_line2", 0))
    t3 = int(getattr(s, "_sine_travel_line3", 0))
    t4 = int(getattr(s, "_sine_travel_line4", 0))
    t5 = int(getattr(s, "_sine_travel_line5", 0))
    t6 = int(getattr(s, "_sine_travel_line6", 0))
    speed = float(getattr(s, "_line_speed", 0.5))
    paused = not bool(getattr(s, "_playing", False))
    if paused:
        # Idle guardrail: presets can legitimately carry "no travel", but idle
        # Sine must still drift. Keep existing directions when present and only
        # inject minimum travel for lanes that would otherwise be static.
        preferred = next((d for d in (t1, t2, t3, t4, t5, t6) if d in (1, 2)), 2)
        if t1 == 0:
            t1 = preferred
        if line_count >= 2 and t2 == 0:
            t2 = preferred
        if line_count >= 3 and t3 == 0:
            t3 = preferred
        if line_count >= 4 and t4 == 0:
            t4 = preferred
        if line_count >= 5 and t5 == 0:
            t5 = preferred
        if line_count >= 6 and t6 == 0:
            t6 = preferred
        speed = max(0.22, speed)

    def _dir_sign(travel: int) -> float:
        if travel == 1:
            return 1.0
        if travel == 2:
            return -1.0
        return 0.0

    base_shift1 = float(getattr(s, "_sine_line1_shift", 0.0))
    base_shift2 = float(getattr(s, "_sine_line2_shift", 0.0))
    base_shift3 = float(getattr(s, "_sine_line3_shift", 0.0))
    base_shift4 = float(getattr(s, "_sine_line4_shift", 0.0))
    base_shift5 = float(getattr(s, "_sine_line5_shift", 0.0))
    base_shift6 = float(getattr(s, "_sine_line6_shift", 0.0))
    if paused:
        # Hard idle movement guarantee with bounded phase accumulation.
        # Never feed huge phase values into the shader: that can flatten lines
        # due to float precision loss in the fragment arithmetic.
        last_idle_ts = float(getattr(s, "_sine_idle_shift_ts", 0.0))
        if last_idle_ts > 0.0:
            dt = max(1.0 / 240.0, min(0.100, now - last_idle_ts))
        else:
            dt = 1.0 / 60.0
        idle_phase = float(getattr(s, "_sine_idle_shift_phase", 0.0))
        idle_phase = math.fmod(idle_phase + dt * (0.12 * speed), 1.0)
        if idle_phase < 0.0:
            idle_phase += 1.0
        setattr(s, "_sine_idle_shift_phase", idle_phase)
        setattr(s, "_sine_idle_shift_ts", now)

        base_shift1 += _dir_sign(t1) * idle_phase
        base_shift2 += _dir_sign(t2) * idle_phase
        base_shift3 += _dir_sign(t3) * idle_phase
        base_shift4 += _dir_sign(t4) * idle_phase
        base_shift5 += _dir_sign(t5) * idle_phase
        base_shift6 += _dir_sign(t6) * idle_phase
    else:
        setattr(s, "_sine_idle_shift_ts", now)

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
    _set1i(gl, u, "u_ghost_line4_enabled", 1 if getattr(s, "_sine_ghost_line4_enabled", True) else 0)
    _set1i(gl, u, "u_ghost_line5_enabled", 1 if getattr(s, "_sine_ghost_line5_enabled", True) else 0)
    _set1i(gl, u, "u_ghost_line6_enabled", 1 if getattr(s, "_sine_ghost_line6_enabled", True) else 0)
    _set1f(gl, u, "u_ghost_bass", getattr(s, '_sine_peak_bass', 0.0))
    _set1f(gl, u, "u_ghost_mid", getattr(s, '_sine_peak_mid', 0.0))
    _set1f(gl, u, "u_ghost_high", getattr(s, '_sine_peak_high', 0.0))
    _set1f(gl, u, "u_sine_speed", speed)
    _set1i(gl, u, "u_sine_line_dim", 1 if s._line_dim else 0)
    _set1f(gl, u, "u_sine_line_offset_bias", s._line_offset_bias)
    _set1i(gl, u, "u_sine_travel", t1)
    _set1f(gl, u, "u_card_adaptation", s._sine_card_adaptation)
    _set1i(gl, u, "u_sine_travel_line2", t2)
    _set1i(gl, u, "u_sine_travel_line3", t3)
    _set1i(gl, u, "u_sine_travel_line4", t4)
    _set1i(gl, u, "u_sine_travel_line5", t5)
    _set1i(gl, u, "u_sine_travel_line6", t6)
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
    _set1f(gl, u, "u_sine_line1_shift", base_shift1)
    _set1f(gl, u, "u_sine_line2_shift", base_shift2)
    _set1f(gl, u, "u_sine_line3_shift", base_shift3)
    _set1f(gl, u, "u_sine_line4_shift", base_shift4)
    _set1f(gl, u, "u_sine_line5_shift", base_shift5)
    _set1f(gl, u, "u_sine_line6_shift", base_shift6)

    # Shared line/glow
    _upload_shared_line_glow(gl, u, s, reactive)

    # Energy bands (CPU-smoothed for anti-flicker)
    _set1f(gl, u, "u_overall_energy", reactive['overall_energy'])
    _set1f(gl, u, "u_bass_energy", reactive['bass_energy'])
    _set1f(gl, u, "u_mid_energy", reactive['mid_energy'])
    _set1f(gl, u, "u_high_energy", reactive['high_energy'])

    if is_viz_diagnostics_enabled():
        last_diag = float(getattr(s, '_sine_idle_uniform_diag_ts', 0.0))
        if now - last_diag >= 0.9:
            logger.debug(
                "[SPOTIFY_VIS][SINE][IDLE_UNIFORMS] playing=%s speed=%.3f line_count=%d travel=(%d,%d,%d,%d,%d,%d) shift1=%.4f",
                bool(getattr(s, "_playing", False)),
                speed,
                line_count,
                t1,
                t2,
                t3,
                t4,
                t5,
                t6,
                float(base_shift1),
            )
            setattr(s, '_sine_idle_uniform_diag_ts', now)

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
        ("u_line4_color", s._line4_color),
        ("u_line4_glow_color", s._line4_glow_color),
        ("u_line5_color", s._line5_color),
        ("u_line5_glow_color", s._line5_glow_color),
        ("u_line6_color", s._line6_color),
        ("u_line6_glow_color", s._line6_glow_color),
    ):
        _set_color4(gl, u, uname, qc)
