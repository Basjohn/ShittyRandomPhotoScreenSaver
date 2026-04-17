"""Blob mode uniform renderer.

The upload facade stays shared because GL transport is common, but shaped and
unshaped runtime ownership now lives in dedicated helper modules so each Blob
type can evolve without cross-contaminating the other.
"""
from __future__ import annotations

from core.logging.logger import get_logger
from widgets.spotify_visualizer.blob_pockets import build_blob_pocket_uniform_payload
from widgets.spotify_visualizer.renderers.blob_shaper_runtime import (
    _build_energy_routing,
    _get_shaper_energy_bands,
    _resample_nodes,
    _resolve_runtime_shaper_profile,
    _resolve_shaper_radius_at_angle,
    _resolve_shaper_radius,
    _resolve_shaper_targets,
    _sample_routed_shaper_energy,
    _solve_runtime_shaper_profile_step,
)
from widgets.spotify_visualizer.renderers.blob_unshaped_runtime import _resolve_runtime_unshaped_profile
from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1f as _set1f,
    set1fv as _set1fv,
    set1i as _set1i,
    set4fv as _set4fv,
    set_color4 as _set_color4,
)

logger = get_logger(__name__)
_shaper_logged = False
_SHAPER_N = 64


def get_uniform_names() -> list[str]:
    return [
        "u_playing", "u_ghost_alpha",
        "u_blob_color", "u_blob_glow_color", "u_blob_edge_color", "u_blob_inward_liquid_color",
        "u_blob_pulse", "u_blob_width", "u_blob_size",
        "u_blob_glow_intensity", "u_blob_glow_reactivity", "u_blob_glow_max_size",
        "u_blob_reactive_glow", "u_blob_outline_color",
        "u_blob_smoothed_energy", "u_blob_glow_energy", "u_blob_peak_energy",
        "u_blob_peak_bass", "u_blob_peak_mid", "u_blob_peak_high", "u_blob_peak_overall",
        "u_blob_reactive_deformation", "u_blob_stage_gain",
        "u_blob_core_scale", "u_blob_core_floor_bias", "u_blob_stage_bias",
        "u_blob_stage_progress_override",
        "u_blob_pockets", "u_blob_pocket_mix",
        "u_blob_constant_wobble", "u_blob_reactive_wobble", "u_blob_stretch_tendency",
        "u_blob_stretch_inner", "u_blob_stretch_outer",
        "u_blob_inward_liquid_enabled", "u_blob_inward_liquid_reactivity", "u_blob_inward_liquid_max_size",
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
        "u_transient_bass", "u_transient_mid", "u_transient_high",
        "u_blob_shaper_enabled", "u_blob_shaper_base_strength",
        "u_blob_shaper_react_strength",
        "u_blob_ring_mode", "u_blob_ring_thickness",
        "u_blob_base_profile", "u_blob_react_profile", "u_blob_runtime_profile",
        "u_blob_energy_bass", "u_blob_energy_mid", "u_blob_energy_vocals",
        "u_blob_energy_treble", "u_blob_energy_transient",
        "u_blob_shaper_bass_energy", "u_blob_shaper_mid_energy",
        "u_blob_shaper_high_energy", "u_blob_shaper_overall_energy",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    loc = u.get("u_ghost_alpha", -1)
    if loc >= 0:
        try:
            ga = float(s._blob_ghost_alpha if s._blob_ghosting_enabled else 0.0)
        except Exception:
            ga = 0.0
        gl.glUniform1f(loc, max(0.0, min(1.0, ga)))

    _set_color4(gl, u, "u_blob_color", s._blob_color)
    _set_color4(gl, u, "u_blob_glow_color", s._blob_glow_color)
    _set_color4(gl, u, "u_blob_edge_color", s._blob_edge_color)
    _set_color4(gl, u, "u_blob_inward_liquid_color", getattr(s, "_blob_inward_liquid_color", s._blob_glow_color))
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
    _set1f(gl, u, "u_blob_peak_bass", s._blob_peak_bass)
    _set1f(gl, u, "u_blob_peak_mid", s._blob_peak_mid)
    _set1f(gl, u, "u_blob_peak_high", s._blob_peak_high)
    _set1f(gl, u, "u_blob_peak_overall", s._blob_peak_overall)
    _set1f(gl, u, "u_blob_reactive_deformation", s._blob_reactive_deformation)
    _set1f(gl, u, "u_blob_glow_energy", getattr(s, "_blob_glow_energy", s._blob_smoothed_energy))
    _set1f(gl, u, "u_blob_stage_gain", s._blob_stage_gain)
    _set1f(gl, u, "u_blob_core_scale", s._blob_core_scale)
    _set1f(gl, u, "u_blob_core_floor_bias", s._blob_core_floor_bias)
    _set1f(gl, u, "u_blob_stage_bias", s._blob_stage_bias)

    loc = u.get("u_blob_stage_progress_override", -1)
    if loc >= 0:
        stage_vals = s._blob_stage_progress_filtered if s._blob_stage_progress_ready else (-1.0, -1.0, -1.0)
        gl.glUniform3f(loc, float(stage_vals[0]), float(stage_vals[1]), float(stage_vals[2]))

    pocket_data, pocket_mix = build_blob_pocket_uniform_payload(getattr(s, "_blob_pocket_state", None))
    _set4fv(gl, u, "u_blob_pockets", pocket_data, 6)
    _set4fv(gl, u, "u_blob_pocket_mix", pocket_mix, 6)

    _set1f(gl, u, "u_blob_constant_wobble", s._blob_constant_wobble)
    _set1f(gl, u, "u_blob_reactive_wobble", s._blob_reactive_wobble)
    _set1f(gl, u, "u_blob_stretch_tendency", s._blob_stretch_tendency)
    _set1f(gl, u, "u_blob_stretch_inner", getattr(s, "_blob_stretch_inner", 0.0))
    _set1f(gl, u, "u_blob_stretch_outer", getattr(s, "_blob_stretch_outer", 0.35))
    _set1i(gl, u, "u_blob_inward_liquid_enabled", 1 if getattr(s, "_blob_inward_liquid_enabled", False) else 0)
    _set1f(gl, u, "u_blob_inward_liquid_reactivity", getattr(s, "_blob_inward_liquid_reactivity", 1.0))
    _set1f(gl, u, "u_blob_inward_liquid_max_size", getattr(s, "_blob_inward_liquid_max_size", 0.28))

    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", getattr(s, "_blob_live_overall_energy", eb.overall))
    _set1f(gl, u, "u_bass_energy", getattr(s, "_blob_live_bass_energy", eb.bass))
    _set1f(gl, u, "u_mid_energy", getattr(s, "_blob_live_mid_energy", eb.mid))
    _set1f(gl, u, "u_high_energy", getattr(s, "_blob_live_high_energy", eb.high))
    shaper_bass, shaper_mid, shaper_high, shaper_overall = _get_shaper_energy_bands(s)
    _set1f(gl, u, "u_blob_shaper_bass_energy", shaper_bass)
    _set1f(gl, u, "u_blob_shaper_mid_energy", shaper_mid)
    _set1f(gl, u, "u_blob_shaper_high_energy", shaper_high)
    _set1f(gl, u, "u_blob_shaper_overall_energy", shaper_overall)

    tb = getattr(s, "_transient_energy", None)
    _set1f(gl, u, "u_transient_bass", getattr(tb, "bass_transient", 0.0) if tb else 0.0)
    _set1f(gl, u, "u_transient_mid", getattr(tb, "mid_transient", 0.0) if tb else 0.0)
    _set1f(gl, u, "u_transient_high", getattr(tb, "high_transient", 0.0) if tb else 0.0)

    shaper_on = getattr(s, "_blob_shaper_enabled", False)
    _set1i(gl, u, "u_blob_shaper_enabled", 1 if shaper_on else 0)
    _set1f(gl, u, "u_blob_shaper_base_strength", getattr(s, "_blob_shaper_base_strength", 0.5))
    _set1f(gl, u, "u_blob_shaper_react_strength", getattr(s, "_blob_shaper_react_strength", 0.5))
    ring_on = getattr(s, "_blob_topology", "circle") == "ring"
    _set1i(gl, u, "u_blob_ring_mode", 1 if ring_on else 0)
    _set1f(gl, u, "u_blob_ring_thickness", getattr(s, "_blob_ring_thickness", 0.3))

    base_nodes = getattr(s, "_blob_shape_base_nodes", [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]])
    react_nodes = getattr(s, "_blob_shape_reaction_nodes", [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]])
    energy_node_list = getattr(s, "_blob_shape_energy_nodes", [])

    base_profile = _resample_nodes(base_nodes, _SHAPER_N)
    react_profile = _resample_nodes(react_nodes, _SHAPER_N)

    global _shaper_logged
    if shaper_on and not _shaper_logged:
        shaper_locs = {k: u.get(k, -1) for k in ("u_blob_shaper_enabled", "u_blob_base_profile", "u_blob_ring_mode")}
        logger.info(
            "[SPOTIFY_VIS] Blob shaper upload: enabled=%s ring=%s ring_thick=%.2f "
            "base_str=%.2f react_str=%.2f base_profile=%s react_profile=%s energy_nodes=%d uniform_locs=%s",
            shaper_on, ring_on, getattr(s, "_blob_ring_thickness", 0.3),
            getattr(s, "_blob_shaper_base_strength", 0.5),
            getattr(s, "_blob_shaper_react_strength", 0.5),
            [f"{v:.3f}" for v in base_profile],
            [f"{v:.3f}" for v in react_profile],
            len(energy_node_list),
            shaper_locs,
        )
        _shaper_logged = True
    elif not shaper_on:
        _shaper_logged = False

    _set1fv(gl, u, "u_blob_base_profile", base_profile, _SHAPER_N)
    _set1fv(gl, u, "u_blob_react_profile", react_profile, _SHAPER_N)

    energy_weights = _build_energy_routing(
        energy_node_list,
        _SHAPER_N,
        base_profile=base_profile,
        react_profile=react_profile,
    )
    _set1fv(gl, u, "u_blob_energy_bass", energy_weights[0], _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_mid", energy_weights[1], _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_vocals", energy_weights[2], _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_treble", energy_weights[3], _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_transient", energy_weights[4], _SHAPER_N)

    if shaper_on:
        runtime_profile = _resolve_runtime_shaper_profile(
            s,
            base_profile=base_profile,
            react_profile=react_profile,
            weights=energy_weights,
            bass=shaper_bass,
            mid=shaper_mid,
            high=shaper_high,
            overall=shaper_overall,
        )
    else:
        setattr(s, "_blob_shaper_runtime_profile", list(base_profile))
        setattr(s, "_blob_shaper_runtime_velocity", [0.0] * _SHAPER_N)
        setattr(s, "_blob_shaper_runtime_target_profile", list(base_profile))
        runtime_profile = _resolve_runtime_unshaped_profile(
            s,
            pocket_data=pocket_data,
            pocket_mix=pocket_mix,
            bass=float(getattr(s, "_blob_live_bass_energy", eb.bass)),
            mid=float(getattr(s, "_blob_live_mid_energy", eb.mid)),
            high=float(getattr(s, "_blob_live_high_energy", eb.high)),
            overall=float(getattr(s, "_blob_live_overall_energy", eb.overall)),
        )
    _set1fv(gl, u, "u_blob_runtime_profile", runtime_profile, _SHAPER_N)
    return True
