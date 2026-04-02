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

_SHAPER_N = 64
_SHAPER_REST_DEADZONE = 0.12
_SHAPER_DRIVE_GAIN = 2.4
_SHAPER_ROUTING_PRIMARY_SPREAD = 0.22
_SHAPER_ROUTING_SECONDARY_SPREAD = 0.38
_SHAPER_ROUTING_SMOOTH_PASSES = 2

_ENERGY_TYPE_INDEX = {
    "bass": 0,
    "mid": 1,
    "vocals": 2,
    "treble": 3,
    "transient": 4,
}


def _catmull_rom(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    """Catmull-Rom spline interpolation between p1 and p2."""
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def _editor_angle_fraction_from_cartesian(x: float, y: float) -> float:
    """Map Cartesian coordinates to the editor's angular convention.

    The Blob Shape Editor defines 0.0 at the top, 0.25 at the right,
    0.5 at the bottom, and 0.75 at the left. Runtime sampling must use the
    same convention or authored shapes appear rotated relative to the GUI.
    """
    angle = math.atan2(y, x) / (2.0 * math.pi)
    return (angle + 0.25) % 1.0


def _routing_falloff(diff: float, spread: float) -> float:
    """Return a smooth 0..1 falloff for cyclic angular routing influence."""
    if spread <= 1e-6 or diff >= spread:
        return 0.0
    return 0.5 * (1.0 + math.cos(math.pi * diff / spread))


def _smooth_cyclic_series(values: Sequence[float], passes: int = _SHAPER_ROUTING_SMOOTH_PASSES) -> list[float]:
    """Apply a light cyclic low-pass filter to authored routing weights."""
    out = [float(v) for v in values]
    if len(out) < 3:
        return out
    for _ in range(max(0, int(passes))):
        prev = out[-1]
        cur = out[0]
        smoothed: list[float] = []
        for idx in range(len(out)):
            nxt = out[(idx + 1) % len(out)]
            smoothed.append(prev * 0.2 + cur * 0.6 + nxt * 0.2)
            prev, cur = cur, nxt
        out = smoothed
    return out


def _resample_nodes(nodes: Sequence[Sequence[float]], n: int) -> list[float]:
    """Resample nodes [[x, y], ...] to *n* evenly-spaced samples using catmull-rom.

    *x* values are in 0..1 (angle fraction), *y* values are the radius
    multiplier.  The profile is cyclic (wraps around).
    """
    if not nodes or n <= 0:
        return [1.0] * n
    normalized_map: dict[float, float] = {}
    for point in nodes:
        try:
            raw_x = float(point[0])
            x = raw_x % 1.0
            y = float(point[1])
        except Exception:
            continue
        key = round(x, 6)
        previous = normalized_map.get(key)
        is_wrap_alias = key == 0.0 and abs(raw_x) > 1e-6
        if previous is None:
            normalized_map[key] = y
        elif not is_wrap_alias and y > previous:
            normalized_map[key] = y
    normalized = [[key, value] for key, value in normalized_map.items()]
    sn = sorted(normalized, key=lambda p: p[0])
    nn = len(sn)
    if nn == 1:
        return [sn[0][1]] * n
    out: list[float] = []
    for i in range(n):
        t = i / n
        # Wrap segment: past last node or before first node
        if t >= sn[-1][0] or t < sn[0][0]:
            seg_idx = nn - 1
        else:
            seg_idx = 0
            for j in range(nn - 1):
                if sn[j][0] <= t:
                    seg_idx = j
        lo_x = sn[seg_idx][0]
        hi_x = sn[(seg_idx + 1) % nn][0]
        if seg_idx == nn - 1:
            seg_len = (1.0 - lo_x) + hi_x
            if t >= lo_x:
                local_t = (t - lo_x) / seg_len if seg_len > 1e-6 else 0.0
            else:
                local_t = (t + 1.0 - lo_x) / seg_len if seg_len > 1e-6 else 0.0
        else:
            seg_len = hi_x - lo_x
            local_t = (t - lo_x) / seg_len if seg_len > 1e-6 else 0.0
        local_t = max(0.0, min(1.0, local_t))
        p0 = sn[(seg_idx - 1) % nn][1]
        p1 = sn[seg_idx][1]
        p2 = sn[(seg_idx + 1) % nn][1]
        p3 = sn[(seg_idx + 2) % nn][1]
        out.append(_catmull_rom(p0, p1, p2, p3, local_t))
    return out


def _build_energy_routing(energy_nodes: list, n: int) -> list[list[float]]:
    """Build per-sector energy weight arrays from draggable energy nodes.

    Each energy node is a dict: {type, x, y, strength} where x,y are in
    0..1 square-editor space, mapped to polar.  Returns a list of 5
    float arrays (one per energy type) each of length *n*.
    """
    num_types = 5
    weights = [[0.0] * n for _ in range(num_types)]
    runtime_nodes = _runtime_energy_nodes(energy_nodes)
    if not runtime_nodes:
        # Default: bass drives the authored reaction shape everywhere outward.
        weights[0] = [1.0] * n
        return weights
    for node in runtime_nodes:
        etype = str(node.get("type", "bass")).lower()
        idx = _ENERGY_TYPE_INDEX.get(etype, 0)
        nx = float(node.get("x", 0.5))
        ny = float(node.get("y", 0.5))
        strength = float(node.get("strength", 1.0))
        dir_x = float(node.get("dir_x", 0.0))
        dir_y = float(node.get("dir_y", -1.0))
        # Map square (0..1, 0..1) to polar angle fraction
        cx, cy = nx - 0.5, ny - 0.5
        angle_frac = _editor_angle_fraction_from_cartesian(cx, cy)
        radial_len = math.hypot(cx, cy)
        if radial_len > 1e-6:
            radial_x = cx / radial_len
            radial_y = cy / radial_len
        else:
            radial_x = 0.0
            radial_y = -1.0
        dir_len = math.hypot(dir_x, dir_y)
        if dir_len > 1e-6:
            dir_x /= dir_len
            dir_y /= dir_len
        else:
            dir_x = radial_x
            dir_y = radial_y
        radial_alignment = max(-1.0, min(1.0, dir_x * radial_x + dir_y * radial_y))
        signed_strength = strength * radial_alignment
        for i in range(n):
            sample_frac = i / n
            # Circular distance
            diff = abs(sample_frac - angle_frac)
            diff = min(diff, 1.0 - diff)
            primary = _routing_falloff(diff, _SHAPER_ROUTING_PRIMARY_SPREAD)
            secondary = _routing_falloff(diff, _SHAPER_ROUTING_SECONDARY_SPREAD)
            influence = (primary * 0.74 + secondary * 0.26) * signed_strength
            weights[idx][i] += influence
    weights = [_smooth_cyclic_series(channel) for channel in weights]
    return weights


def _runtime_energy_nodes(energy_nodes: list) -> list[dict]:
    """Return the energy nodes that should participate in runtime routing.

    Reaction-canvas nodes are authoritative when present. Older presets and
    configs that only stored base/unqualified nodes still need to work, so we
    fall back to all non-react-tagged nodes when no react nodes exist.
    """
    if not energy_nodes:
        return []
    react_nodes: list[dict] = []
    legacy_nodes: list[dict] = []
    for raw_node in energy_nodes:
        if not isinstance(raw_node, dict):
            continue
        canvas = str(raw_node.get("canvas", "")).strip().lower()
        if canvas == "react":
            react_nodes.append(dict(raw_node))
        else:
            legacy_nodes.append(dict(raw_node))
    return react_nodes if react_nodes else legacy_nodes


def _prepare_shaper_signed_energy(signed_energy: float) -> float:
    """Apply the runtime shaper gain before deadzone/easing."""
    return max(-1.0, min(1.0, float(signed_energy) * _SHAPER_DRIVE_GAIN))


def _remap_shaper_drive(signed_energy: float, *, playing: bool) -> float:
    """Mirror the shader's shaper-drive rest logic for regression tests.

    Low-level floor/noise energy must not park the blob on the reaction shape.
    When playback is paused the shaper should rest entirely on the base shape.
    """
    if not playing:
        return 0.0
    signed_energy = _prepare_shaper_signed_energy(signed_energy)
    magnitude = abs(float(signed_energy))
    if magnitude <= _SHAPER_REST_DEADZONE:
        return 0.0
    t = (magnitude - _SHAPER_REST_DEADZONE) / max(1e-6, 1.0 - _SHAPER_REST_DEADZONE)
    t = max(0.0, min(1.0, t))
    eased = t * t * (3.0 - 2.0 * t)
    return math.copysign(eased, float(signed_energy))


def _resolve_shaper_radius(
    base_radius: float,
    react_radius: float,
    signed_energy: float,
    *,
    playing: bool,
) -> float:
    """Pure-Python mirror of the shader's per-angle shaper radius contract."""
    drive = _remap_shaper_drive(signed_energy, playing=playing)
    return float(base_radius) + (float(react_radius) - float(base_radius)) * drive


def _resolve_shaper_wobble_scales(
    constant_wobble: float,
    reactive_wobble: float,
    signed_energy: float,
    *,
    playing: bool,
) -> tuple[float, float]:
    """Mirror the shader's wobble suppression when Blob Shaper is active.

    The authored base/reaction contours should stay visually authoritative.
    At rest, the shaper should not smear the silhouette with residual wobble.
    """
    drive = abs(_remap_shaper_drive(signed_energy, playing=playing))
    return (
        float(constant_wobble) * drive * 0.08,
        float(reactive_wobble) * drive * 0.35,
    )


def _get_shaper_energy_bands(s) -> tuple[float, float, float, float]:
    """Return the more expressive energy bands used for Blob Shaper drive.

    Whole-body blob size is intentionally fed with calmer live bands so the
    silhouette does not explode on every hit. Blob Shaper deformation needs a
    more responsive source, so it prefers the stage-driving inputs that retain
    stronger musical/transient support and falls back to the regular live bands.
    """
    eb = getattr(s, "_energy_bands", None)
    fallback = (
        float(getattr(s, "_blob_live_bass_energy", getattr(eb, "bass", 0.0)) or 0.0),
        float(getattr(s, "_blob_live_mid_energy", getattr(eb, "mid", 0.0)) or 0.0),
        float(getattr(s, "_blob_live_high_energy", getattr(eb, "high", 0.0)) or 0.0),
        float(getattr(s, "_blob_live_overall_energy", getattr(eb, "overall", 0.0)) or 0.0),
    )
    def _stage_band(attr: str, fallback_value: float) -> float:
        raw = getattr(s, attr, None)
        if raw is None:
            return float(fallback_value)
        return float(raw)
    def _blend(stage_value: float, live_value: float, mix: float) -> float:
        stage = float(stage_value)
        live = float(live_value)
        return max(live, live + (stage - live) * mix)
    return (
        _blend(_stage_band("_blob_stage_input_bass", fallback[0]), fallback[0], 0.78),
        _blend(_stage_band("_blob_stage_input_mid", fallback[1]), fallback[1], 0.55),
        _blend(_stage_band("_blob_stage_input_high", fallback[2]), fallback[2], 0.52),
        _blend(_stage_band("_blob_stage_input_overall", fallback[3]), fallback[3], 0.72),
    )


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
        "u_blob_shaper_bass_energy", "u_blob_shaper_mid_energy",
        "u_blob_shaper_high_energy", "u_blob_shaper_overall_energy",
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
    shaper_bass, shaper_mid, shaper_high, shaper_overall = _get_shaper_energy_bands(s)
    _set1f(gl, u, "u_blob_shaper_bass_energy", shaper_bass)
    _set1f(gl, u, "u_blob_shaper_mid_energy", shaper_mid)
    _set1f(gl, u, "u_blob_shaper_high_energy", shaper_high)
    _set1f(gl, u, "u_blob_shaper_overall_energy", shaper_overall)

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
