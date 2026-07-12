"""Uniform transport shared by the two Blob renderer programs.

Only paint, colour, stage, energy, ghost, and inward-liquid state belongs
here.  Contour generation and subtype-specific uniforms remain in the Mighty
and Shaped renderer modules.
"""
from __future__ import annotations

from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1f as _set1f,
    set1i as _set1i,
    set4fv as _set4fv,
    set_color4 as _set_color4,
)
from core.settings.visualizer_blob_contract import normalize_blob_type
from widgets.spotify_visualizer.blob_tendril_runtime import (
    TENDRIL_COUNT,
    gpu_vocal_wobble_strength,
)


def get_common_uniform_names() -> list[str]:
    return [
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
        "u_blob_tendril_count",
        "u_blob_tendril_geometry",
        "u_blob_tendril_motion",
        "u_blob_vocal_wobble_strength",
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

    tendril_geometry = getattr(s, "_blob_tendril_geometry", None)
    tendril_motion = getattr(s, "_blob_tendril_motion", None)
    tendril_ready = (
        tendril_geometry is not None
        and tendril_motion is not None
        and len(tendril_geometry) >= TENDRIL_COUNT * 4
        and len(tendril_motion) >= TENDRIL_COUNT * 4
    )
    _set1i(gl, u, "u_blob_tendril_count", TENDRIL_COUNT if tendril_ready else 0)
    if tendril_ready:
        _set4fv(gl, u, "u_blob_tendril_geometry", tendril_geometry, TENDRIL_COUNT)
        _set4fv(gl, u, "u_blob_tendril_motion", tendril_motion, TENDRIL_COUNT)
    blob_type = normalize_blob_type(
        getattr(s, "_blob_type", None),
        legacy_shaper_enabled=getattr(s, "_blob_shaper_enabled", None),
    )
    _set1f(
        gl,
        u,
        "u_blob_vocal_wobble_strength",
        gpu_vocal_wobble_strength(s, blob_type=blob_type),
    )

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
    """Emit low-rate Blob contour diagnostics with temporal evidence."""
    try:
        runtime_ts = getattr(s, "_blob_runtime_time", None)
        if runtime_ts is None:
            import time as _time

            current_ts = _time.monotonic()
        else:
            current_ts = max(0.0, float(runtime_ts))
        previous_profile = getattr(s, "_blob_runtime_diag_profile", None)
        previous_ts = float(getattr(s, "_blob_runtime_diag_ts", 0.0) or 0.0)
        if not profile or (
            previous_profile is not None and current_ts - previous_ts < 0.75
        ):
            return
        profile_min = min(float(value) for value in profile)
        profile_max = max(float(value) for value in profile)
        profile_mean = sum(float(value) for value in profile) / len(profile)
        profile_rms = (
            sum((float(value) - profile_mean) ** 2 for value in profile) / len(profile)
        ) ** 0.5
        target_attr = (
            "_blob_shaper_runtime_target_profile"
            if blob_type == "shaped"
            else "_blob_unshaped_runtime_target_profile"
        )
        target_profile = getattr(s, target_attr, None)
        target_spread = 0.0
        transfer_ratio = 0.0
        if target_profile is not None and len(target_profile) == len(profile):
            target_min = min(float(value) for value in target_profile)
            target_max = max(float(value) for value in target_profile)
            target_mean = sum(float(value) for value in target_profile) / len(target_profile)
            target_rms = (
                sum((float(value) - target_mean) ** 2 for value in target_profile)
                / len(target_profile)
            ) ** 0.5
            target_spread = target_max - target_min
            transfer_ratio = profile_rms / max(target_rms, 1e-6)
        rms_delta = 0.0
        centered_rms_delta = 0.0
        max_delta = 0.0
        mean_delta = 0.0
        if previous_profile is not None and len(previous_profile) == len(profile):
            deltas = [
                float(profile[idx]) - float(previous_profile[idx])
                for idx in range(len(profile))
            ]
            rms_delta = (sum(delta * delta for delta in deltas) / len(deltas)) ** 0.5
            max_delta = max(abs(delta) for delta in deltas)
            mean_delta = profile_mean - (
                sum(float(value) for value in previous_profile) / len(previous_profile)
            )
            centered_rms_delta = (
                sum((delta - mean_delta) ** 2 for delta in deltas) / len(deltas)
            ) ** 0.5

        # Describe contour language rather than spread alone. Spread can stay
        # large while one frozen silhouette only rotates or scales. Peak count,
        # high-detail RMS, and mean-removed temporal change expose that failure.
        smooth_profile = [
            sum(
                float(profile[(idx + offset) % len(profile)])
                for offset in (-2, -1, 0, 1, 2)
            ) / 5.0
            for idx in range(len(profile))
        ]
        prominence = max(0.004, profile_rms * 0.10)
        peak_indices = [
            idx
            for idx, value in enumerate(smooth_profile)
            if value > smooth_profile[(idx - 1) % len(profile)]
            and value >= smooth_profile[(idx + 1) % len(profile)]
            and value > profile_mean + prominence
        ]
        strongest_anchors = sorted(
            peak_indices,
            key=lambda idx: smooth_profile[idx],
            reverse=True,
        )[:4]
        detail_profile = [
            float(profile[idx])
            - sum(
                float(profile[(idx + offset) % len(profile)])
                for offset in range(-4, 5)
            ) / 9.0
            for idx in range(len(profile))
        ]
        detail_rms = (
            sum(value * value for value in detail_profile) / len(detail_profile)
        ) ** 0.5
        morphology_ratio = centered_rms_delta / max(rms_delta, 1e-6)
        transient = getattr(s, "_transient_energy", None)
        transient_peak = max(
            float(getattr(transient, "bass_transient", 0.0) if transient else 0.0),
            float(getattr(transient, "mid_transient", 0.0) if transient else 0.0),
            float(getattr(transient, "high_transient", 0.0) if transient else 0.0),
            float(getattr(s, "_blob_kick_event_envelope", 0.0) or 0.0),
            float(getattr(s, "_blob_snare_event_envelope", 0.0) or 0.0),
        )
        if blob_type == "shaped":
            control_label = "shaped(base,react,idle,music)"
            controls = (
                float(getattr(s, "_blob_shaper_base_strength", 0.0) or 0.0),
                float(getattr(s, "_blob_shaper_react_strength", 0.0) or 0.0),
                float(getattr(s, "_blob_shaper_idle_motion", 0.0) or 0.0),
                float(getattr(s, "_blob_shaper_audio_motion", 0.0) or 0.0),
            )
        else:
            control_label = "mighty(shape,idle,music,stretch)"
            controls = (
                float(getattr(s, "_blob_reactive_deformation", 0.0) or 0.0),
                float(getattr(s, "_blob_constant_wobble", 0.0) or 0.0),
                float(getattr(s, "_blob_reactive_wobble", 0.0) or 0.0),
                float(getattr(s, "_blob_stretch_tendency", 0.0) or 0.0),
            )
        height_getter = getattr(s, "height", None)
        height_px = float(height_getter()) if callable(height_getter) else 0.0
        base_radius_px = max(0.0, height_px - 12.0) * 0.31 * float(
            getattr(s, "_blob_size", 1.0) or 1.0
        )
        logger.debug(
            "[SPOTIFY_VIS][BLOB_PROFILE] type=%s samples=%d playing=%s liquid=%s "
            "bands=(%.3f,%.3f,%.3f,%.3f) transient=%.3f "
            "%s=(%.2f,%.2f,%.2f,%.2f) "
            "min=%.3f max=%.3f spread=%.3f avg=%.3f "
            "target_spread=%.3f transfer=%.2f rms_delta=%.4f "
            "centered_delta=%.4f morph_ratio=%.2f max_delta=%.4f mean_delta=%+.4f "
            "peaks=%d anchors=%s detail_rms=%.4f "
            "solve_ms(last=%.2f,avg=%.2f,max=%.2f) generation=%d "
            "cadence(requests=%d,computed=%d,skipped=%d) geometry_builds=%d "
            "tendrils(active=%d,max_reach=%.3f) "
            "est_px(span=%.1f,centered_delta=%.1f)",
            blob_type,
            len(profile),
            bool(getattr(s, "_playing", False)),
            bool(getattr(s, "_blob_inward_liquid_enabled", False)),
            float(getattr(s, "_blob_live_bass_energy", 0.0) or 0.0),
            float(getattr(s, "_blob_live_mid_energy", 0.0) or 0.0),
            float(getattr(s, "_blob_live_high_energy", 0.0) or 0.0),
            float(getattr(s, "_blob_live_overall_energy", 0.0) or 0.0),
            transient_peak,
            control_label,
            controls[0],
            controls[1],
            controls[2],
            controls[3],
            profile_min,
            profile_max,
            profile_max - profile_min,
            profile_mean,
            target_spread,
            transfer_ratio,
            rms_delta,
            centered_rms_delta,
            morphology_ratio,
            max_delta,
            mean_delta,
            len(peak_indices),
            strongest_anchors,
            detail_rms,
            float(getattr(s, "_blob_profile_compute_ms", 0.0) or 0.0),
            float(getattr(s, "_blob_profile_compute_total_ms", 0.0) or 0.0)
            / max(1, int(getattr(s, "_blob_profile_compute_count", 0) or 0)),
            float(getattr(s, "_blob_profile_compute_max_ms", 0.0) or 0.0),
            int(getattr(s, "_blob_profile_generation", 0) or 0),
            int(getattr(s, "_blob_profile_advance_request_count", 0) or 0),
            int(getattr(s, "_blob_profile_compute_count", 0) or 0),
            int(getattr(s, "_blob_profile_skip_count", 0) or 0),
            int(getattr(s, "_blob_shaper_geometry_build_count", 0) or 0),
            int(getattr(s, "_blob_tendril_active_count", 0) or 0),
            float(getattr(s, "_blob_tendril_max_reach", 0.0) or 0.0),
            (profile_max - profile_min) * base_radius_px,
            centered_rms_delta * base_radius_px,
        )
        setattr(s, "_blob_runtime_diag_profile", list(profile))
        setattr(s, "_blob_runtime_diag_ts", current_ts)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to log Blob runtime profile", exc_info=True)
