"""Uniform transport shared by the two Blob renderer programs.

Only paint, colour, stage, energy, ghost, and inward-liquid state belongs
here.  Contour generation and subtype-specific uniforms remain in the Mighty
and Shaped renderer modules.
"""
from __future__ import annotations

from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1f as _set1f,
    set1i as _set1i,
    set_color4 as _set_color4,
)


def get_common_uniform_names() -> list[str]:
    return [
        "u_playing",
        "u_ghost_alpha",
        "u_blob_color",
        "u_blob_glow_color",
        "u_blob_edge_color",
        "u_blob_outline_color",
        "u_blob_inward_liquid_color",
        "u_blob_pulse",
        "u_blob_size",
        "u_blob_glow_intensity",
        "u_blob_glow_reactivity",
        "u_blob_glow_max_size",
        "u_blob_reactive_glow",
        "u_blob_smoothed_energy",
        "u_blob_glow_energy",
        "u_blob_peak_energy",
        "u_blob_peak_bass",
        "u_blob_peak_mid",
        "u_blob_peak_high",
        "u_blob_peak_overall",
        "u_blob_stage_gain",
        "u_blob_core_scale",
        "u_blob_stage_bias",
        "u_blob_stage_progress_override",
        "u_blob_runtime_profile",
        "u_blob_inward_liquid_enabled",
        "u_blob_inward_liquid_reactivity",
        "u_blob_inward_liquid_max_size",
        "u_overall_energy",
        "u_bass_energy",
        "u_mid_energy",
        "u_high_energy",
        "u_transient_bass",
        "u_transient_mid",
        "u_transient_high",
    ]


def upload_common_uniforms(gl, u: dict, s) -> tuple[float, float, float, float]:
    """Upload subtype-neutral Blob state and return live band values."""
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    loc = u.get("u_ghost_alpha", -1)
    if loc >= 0:
        try:
            ghost_alpha = float(s._blob_ghost_alpha if s._blob_ghosting_enabled else 0.0)
        except Exception:
            ghost_alpha = 0.0
        gl.glUniform1f(loc, max(0.0, min(1.0, ghost_alpha)))

    _set_color4(gl, u, "u_blob_color", s._blob_color)
    _set_color4(gl, u, "u_blob_glow_color", s._blob_glow_color)
    _set_color4(gl, u, "u_blob_edge_color", s._blob_edge_color)
    _set_color4(gl, u, "u_blob_outline_color", s._blob_outline_color)
    _set_color4(
        gl,
        u,
        "u_blob_inward_liquid_color",
        getattr(s, "_blob_inward_liquid_color", s._blob_glow_color),
    )
    _set1f(gl, u, "u_blob_pulse", s._blob_pulse)
    _set1f(gl, u, "u_blob_size", s._blob_size)
    _set1f(gl, u, "u_blob_glow_intensity", s._blob_glow_intensity)
    _set1f(gl, u, "u_blob_glow_reactivity", s._blob_glow_reactivity)
    _set1f(gl, u, "u_blob_glow_max_size", s._blob_glow_max_size)
    _set1i(gl, u, "u_blob_reactive_glow", 1 if s._blob_reactive_glow else 0)
    _set1f(gl, u, "u_blob_smoothed_energy", s._blob_smoothed_energy)
    _set1f(gl, u, "u_blob_glow_energy", getattr(s, "_blob_glow_energy", s._blob_smoothed_energy))
    _set1f(gl, u, "u_blob_peak_energy", s._blob_peak_energy)
    _set1f(gl, u, "u_blob_peak_bass", s._blob_peak_bass)
    _set1f(gl, u, "u_blob_peak_mid", s._blob_peak_mid)
    _set1f(gl, u, "u_blob_peak_high", s._blob_peak_high)
    _set1f(gl, u, "u_blob_peak_overall", s._blob_peak_overall)
    _set1f(gl, u, "u_blob_stage_gain", s._blob_stage_gain)
    _set1f(gl, u, "u_blob_core_scale", s._blob_core_scale)
    _set1f(gl, u, "u_blob_stage_bias", s._blob_stage_bias)

    loc = u.get("u_blob_stage_progress_override", -1)
    if loc >= 0:
        stage_values = (
            s._blob_stage_progress_filtered
            if s._blob_stage_progress_ready
            else (-1.0, -1.0, -1.0)
        )
        gl.glUniform3f(
            loc,
            float(stage_values[0]),
            float(stage_values[1]),
            float(stage_values[2]),
        )

    _set1i(
        gl,
        u,
        "u_blob_inward_liquid_enabled",
        1 if getattr(s, "_blob_inward_liquid_enabled", False) else 0,
    )
    _set1f(
        gl,
        u,
        "u_blob_inward_liquid_reactivity",
        getattr(s, "_blob_inward_liquid_reactivity", 1.0),
    )
    _set1f(
        gl,
        u,
        "u_blob_inward_liquid_max_size",
        getattr(s, "_blob_inward_liquid_max_size", 0.28),
    )

    energy = s._energy_bands
    bass = float(getattr(s, "_blob_live_bass_energy", energy.bass))
    mid = float(getattr(s, "_blob_live_mid_energy", energy.mid))
    high = float(getattr(s, "_blob_live_high_energy", energy.high))
    overall = float(getattr(s, "_blob_live_overall_energy", energy.overall))
    _set1f(gl, u, "u_bass_energy", bass)
    _set1f(gl, u, "u_mid_energy", mid)
    _set1f(gl, u, "u_high_energy", high)
    _set1f(gl, u, "u_overall_energy", overall)

    transient = getattr(s, "_transient_energy", None)
    _set1f(gl, u, "u_transient_bass", getattr(transient, "bass_transient", 0.0) if transient else 0.0)
    _set1f(gl, u, "u_transient_mid", getattr(transient, "mid_transient", 0.0) if transient else 0.0)
    _set1f(gl, u, "u_transient_high", getattr(transient, "high_transient", 0.0) if transient else 0.0)
    return bass, mid, high, overall


def maybe_log_runtime_profile(logger, s, *, blob_type: str, profile: list[float]) -> None:
    """Emit the existing low-rate profile diagnostic with subtype identity."""
    try:
        current_ts = float(getattr(s, "_last_update_ts", 0.0) or 0.0)
        if current_ts <= 0.0:
            import time as _time

            current_ts = _time.monotonic()
        previous_ts = float(getattr(s, "_blob_runtime_diag_ts", 0.0) or 0.0)
        if current_ts - previous_ts < 0.75 or not profile:
            return
        profile_min = min(float(value) for value in profile)
        profile_max = max(float(value) for value in profile)
        logger.debug(
            "[SPOTIFY_VIS][BLOB_PROFILE] type=%s liquid=%s min=%.3f max=%.3f spread=%.3f avg=%.3f",
            blob_type,
            bool(getattr(s, "_blob_inward_liquid_enabled", False)),
            profile_min,
            profile_max,
            profile_max - profile_min,
            sum(float(value) for value in profile) / len(profile),
        )
        setattr(s, "_blob_runtime_diag_ts", current_ts)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to log Blob runtime profile", exc_info=True)
