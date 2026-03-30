"""Blob mode uniform renderer."""
from __future__ import annotations

import math
from typing import Sequence

from core.logging.logger import get_logger
from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1f as _set1f,
    set1i as _set1i,
    set1fv as _set1fv,
    set_color4 as _set_color4,
)

logger = get_logger(__name__)
_shaper_logged = False

_SHAPER_N = 8

_ENERGY_TYPE_INDEX = {
    "bass": 0,
    "mid": 1,
    "vocals": 2,
    "treble": 3,
    "transient": 4,
}


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _resample_nodes(nodes: Sequence[Sequence[float]], n: int) -> list[float]:
    """Resample piecewise-linear nodes [[x, y], ...] to *n* evenly-spaced samples.

    *x* values are in 0..1 (angle fraction), *y* values are the radius
    multiplier.  The output covers *n* evenly-spaced angles from 0 to just
    before 2*pi (i.e. sample *i* is at angle fraction *i/n*).
    """
    if not nodes or n <= 0:
        return [1.0] * n
    sorted_nodes = sorted(nodes, key=lambda p: p[0])
    out: list[float] = []
    for i in range(n):
        t = i / n
        # Find the surrounding segment
        lo_idx = 0
        for j in range(len(sorted_nodes) - 1):
            if sorted_nodes[j][0] <= t:
                lo_idx = j
        lo = sorted_nodes[lo_idx]
        hi = sorted_nodes[min(lo_idx + 1, len(sorted_nodes) - 1)]
        seg_len = hi[0] - lo[0]
        if seg_len > 1e-6:
            frac = (t - lo[0]) / seg_len
        else:
            frac = 0.0
        out.append(_lerp(lo[1], hi[1], max(0.0, min(1.0, frac))))
    return out


def _build_energy_routing(energy_nodes: list, n: int) -> list[list[float]]:
    """Build per-sector energy weight arrays from draggable energy nodes.

    Each energy node is a dict: {type, x, y, strength} where x,y are in
    0..1 square-editor space, mapped to polar.  Returns a list of 5
    float arrays (one per energy type) each of length *n*.
    """
    num_types = 5
    weights = [[0.0] * n for _ in range(num_types)]
    if not energy_nodes:
        # Default: bass everywhere at full strength
        weights[0] = [1.0] * n
        return weights
    for node in energy_nodes:
        etype = str(node.get("type", "bass")).lower()
        idx = _ENERGY_TYPE_INDEX.get(etype, 0)
        nx = float(node.get("x", 0.5))
        ny = float(node.get("y", 0.5))
        strength = float(node.get("strength", 1.0))
        # Map square (0..1, 0..1) to polar angle fraction
        cx, cy = nx - 0.5, ny - 0.5
        angle = math.atan2(cy, cx)
        if angle < 0:
            angle += 2.0 * math.pi
        angle_frac = angle / (2.0 * math.pi)
        # Spread: influence radius in angle-fraction space
        spread = 0.15
        for i in range(n):
            sample_frac = i / n
            # Circular distance
            diff = abs(sample_frac - angle_frac)
            diff = min(diff, 1.0 - diff)
            influence = max(0.0, 1.0 - diff / spread) * strength
            weights[idx][i] = max(weights[idx][i], influence)
    return weights


def get_uniform_names() -> list[str]:
    return [
        "u_playing", "u_ghost_alpha",
        "u_blob_color", "u_blob_glow_color", "u_blob_edge_color",
        "u_blob_pulse", "u_blob_width", "u_blob_size",
        "u_blob_glow_intensity", "u_blob_glow_reactivity", "u_blob_glow_max_size",
        "u_blob_reactive_glow", "u_blob_outline_color",
        "u_blob_smoothed_energy", "u_blob_glow_energy", "u_blob_peak_energy",
        "u_blob_peak_bass", "u_blob_peak_mid", "u_blob_peak_high", "u_blob_peak_overall",
        "u_blob_reactive_deformation", "u_blob_stage_gain",
        "u_blob_core_scale", "u_blob_core_floor_bias", "u_blob_stage_bias",
        "u_blob_stage_progress_override",
        "u_blob_constant_wobble", "u_blob_reactive_wobble", "u_blob_stretch_tendency",
        "u_blob_stretch_inner", "u_blob_stretch_outer",
        # Energy bands (shared)
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
        # Transient bus (Approach A dual-path)
        "u_transient_bass", "u_transient_mid", "u_transient_high",
        # Blob Shaper
        "u_blob_shaper_enabled", "u_blob_shaper_base_strength",
        "u_blob_shaper_react_strength",
        "u_blob_ring_mode", "u_blob_ring_thickness",
        "u_blob_base_profile", "u_blob_react_profile",
        "u_blob_energy_bass", "u_blob_energy_mid", "u_blob_energy_vocals",
        "u_blob_energy_treble", "u_blob_energy_transient",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    # Ghost alpha (mode-specific: blob)
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
        stage_vals = (
            s._blob_stage_progress_filtered
            if s._blob_stage_progress_ready
            else (-1.0, -1.0, -1.0)
        )
        gl.glUniform3f(loc, float(stage_vals[0]), float(stage_vals[1]), float(stage_vals[2]))

    _set1f(gl, u, "u_blob_constant_wobble", s._blob_constant_wobble)
    _set1f(gl, u, "u_blob_reactive_wobble", s._blob_reactive_wobble)
    _set1f(gl, u, "u_blob_stretch_tendency", s._blob_stretch_tendency)
    _set1f(gl, u, "u_blob_stretch_inner", getattr(s, '_blob_stretch_inner', 0.5))
    _set1f(gl, u, "u_blob_stretch_outer", getattr(s, '_blob_stretch_outer', 0.5))

    # Energy bands
    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", getattr(s, "_blob_live_overall_energy", eb.overall))
    _set1f(gl, u, "u_bass_energy", getattr(s, "_blob_live_bass_energy", eb.bass))
    _set1f(gl, u, "u_mid_energy", getattr(s, "_blob_live_mid_energy", eb.mid))
    _set1f(gl, u, "u_high_energy", getattr(s, "_blob_live_high_energy", eb.high))

    # Transient bus (Approach A dual-path)
    tb = getattr(s, '_transient_energy', None)
    _set1f(gl, u, "u_transient_bass", getattr(tb, 'bass_transient', 0.0) if tb else 0.0)
    _set1f(gl, u, "u_transient_mid", getattr(tb, 'mid_transient', 0.0) if tb else 0.0)
    _set1f(gl, u, "u_transient_high", getattr(tb, 'high_transient', 0.0) if tb else 0.0)

    # Blob Shaper
    shaper_on = getattr(s, '_blob_shaper_enabled', False)
    _set1i(gl, u, "u_blob_shaper_enabled", 1 if shaper_on else 0)
    _set1f(gl, u, "u_blob_shaper_base_strength", getattr(s, '_blob_shaper_base_strength', 0.5))
    _set1f(gl, u, "u_blob_shaper_react_strength", getattr(s, '_blob_shaper_react_strength', 0.5))
    ring_on = getattr(s, '_blob_topology', 'circle') == 'ring'
    _set1i(gl, u, "u_blob_ring_mode", 1 if ring_on else 0)
    _set1f(gl, u, "u_blob_ring_thickness", getattr(s, '_blob_ring_thickness', 0.3))

    base_nodes = getattr(s, '_blob_shape_base_nodes', [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]])
    react_nodes = getattr(s, '_blob_shape_reaction_nodes', [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]])
    energy_node_list = getattr(s, '_blob_shape_energy_nodes', [])

    base_profile = _resample_nodes(base_nodes, _SHAPER_N)
    react_profile = _resample_nodes(react_nodes, _SHAPER_N)

    global _shaper_logged
    if shaper_on and not _shaper_logged:
        shaper_locs = {k: u.get(k, -1) for k in (
            "u_blob_shaper_enabled", "u_blob_base_profile", "u_blob_ring_mode",
        )}
        logger.info(
            "[SPOTIFY_VIS] Blob shaper upload: enabled=%s ring=%s ring_thick=%.2f "
            "base_str=%.2f react_str=%.2f base_profile=%s react_profile=%s "
            "energy_nodes=%d uniform_locs=%s",
            shaper_on, ring_on, getattr(s, '_blob_ring_thickness', 0.3),
            getattr(s, '_blob_shaper_base_strength', 0.5),
            getattr(s, '_blob_shaper_react_strength', 0.5),
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

    energy_weights = _build_energy_routing(energy_node_list, _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_bass", energy_weights[0], _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_mid", energy_weights[1], _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_vocals", energy_weights[2], _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_treble", energy_weights[3], _SHAPER_N)
    _set1fv(gl, u, "u_blob_energy_transient", energy_weights[4], _SHAPER_N)

    return True
