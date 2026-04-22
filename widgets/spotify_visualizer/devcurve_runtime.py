"""Dev Curve runtime spline solver.

Computes full-width smooth layered curves for bass/vocals/mids/transients.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List


DEVCURVE_SAMPLE_COUNT = 96
_LAYER_ORDER = ("bass", "vocals", "mids", "transients")
_LAYER_INDEX = {name: idx for idx, name in enumerate(_LAYER_ORDER)}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _smoothstep(x: float) -> float:
    x = _clamp(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _smooth_points(nodes: List[List[float]], count: int) -> List[float]:
    if not nodes:
        return [0.5] * count
    pts = sorted(
        [[_clamp(float(n[0]), 0.0, 1.0), _clamp(float(n[1]), 0.0, 1.0)] for n in nodes if isinstance(n, (list, tuple)) and len(n) >= 2],
        key=lambda p: p[0],
    )
    if not pts:
        return [0.5] * count
    if len(pts) == 1:
        return [pts[0][1]] * count
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    out: List[float] = []
    for i in range(count):
        t = i / max(1, count - 1)
        if t <= xs[0]:
            out.append(ys[0])
            continue
        if t >= xs[-1]:
            out.append(ys[-1])
            continue
        v = ys[-1]
        for j in range(len(xs) - 1):
            x0, x1 = xs[j], xs[j + 1]
            if x0 <= t <= x1:
                u = (t - x0) / max(1e-6, (x1 - x0))
                u = _smoothstep(u)
                v = ys[j] + (ys[j + 1] - ys[j]) * u
                break
        out.append(v)
    return out


def _moving_average(values: List[float], radius: int) -> List[float]:
    if radius <= 0 or len(values) <= 2:
        return list(values)
    out = [0.0] * len(values)
    for i in range(len(values)):
        s = 0.0
        w = 0
        for j in range(max(0, i - radius), min(len(values), i + radius + 1)):
            s += values[j]
            w += 1
        out[i] = s / max(1, w)
    return out


def _slope_limit(values: List[float], max_step: float) -> List[float]:
    out = list(values)
    for i in range(1, len(out)):
        d = out[i] - out[i - 1]
        if d > max_step:
            out[i] = out[i - 1] + max_step
        elif d < -max_step:
            out[i] = out[i - 1] - max_step
    for i in range(len(out) - 2, -1, -1):
        d = out[i] - out[i + 1]
        if d > max_step:
            out[i] = out[i + 1] + max_step
        elif d < -max_step:
            out[i] = out[i + 1] - max_step
    return out


def _phase_rand(seed: float, idx: int) -> float:
    return math.sin(seed * 0.017 + idx * 1.3127) * 43758.5453


@dataclass
class DevCurveRuntimeState:
    phase: float = 0.0
    smooth_energy: Dict[str, float] = field(
        default_factory=lambda: {"bass": 0.0, "vocals": 0.0, "mids": 0.0, "transients": 0.0}
    )
    previous_layers: Dict[str, List[float]] = field(default_factory=dict)
    smoothness_max_step: float = 0.0
    active_amplitude: float = 0.0
    idle_amplitude: float = 0.0


def _layer_energy_map(eb, transient_bus, playing: bool) -> Dict[str, float]:
    bass = float(getattr(eb, "bass", 0.0) if eb is not None else 0.0)
    mid = float(getattr(eb, "mid", 0.0) if eb is not None else 0.0)
    high = float(getattr(eb, "high", 0.0) if eb is not None else 0.0)
    transient = float(getattr(transient_bus, "bass_transient", 0.0) if transient_bus is not None else 0.0)
    return {
        "bass": _clamp(bass, 0.0, 2.0),
        "vocals": _clamp(mid * 0.62 + high * 0.38, 0.0, 2.0),
        "mids": _clamp(mid, 0.0, 2.0),
        "transients": _clamp(transient if playing else 0.0, 0.0, 2.0),
    }


def _build_curve(
    *,
    sample_count: int,
    base_level: float,
    profile: List[float],
    seed: int,
    phase: float,
    idle_motion: float,
    idle_speed: float,
    smoothness: float,
    reactive: float,
    power: float,
    offset: float,
    growth: float,
) -> List[float]:
    out: List[float] = [0.0] * sample_count
    amp_idle = 0.018 * idle_motion
    amp_reactive = 0.135 * reactive * power
    growth = _clamp(float(growth), 1.0, 5.0)
    growth_push = _clamp((growth - 3.0) / 2.0, -1.0, 1.0)
    # Guardrail: authored spline Y maps directly to runtime Y at idle
    # (0.0->bottom, 1.0->top in authored space). Growth only compresses
    # upward excursions to preserve headroom under hot reactivity.
    _ = base_level
    center_shift = 0.0
    base_bias = 0.0
    up_comp = 1.0 - 0.15 * max(0.0, growth_push)
    down_comp = 1.0
    top_soft = 0.95 - 0.02 * max(0.0, growth_push)
    for i in range(sample_count):
        x = i / max(1, sample_count - 1)
        p = _clamp(profile[i], 0.0, 1.0)
        # Author nodes define the pre-energy resting contour; base_level acts
        # as a global vertical bias around that authored shape.
        base = _clamp(p + base_bias + offset + center_shift, 0.02, 0.98)
        w1 = math.sin((x * 2.0 + phase * idle_speed * 0.28) * math.tau + _phase_rand(seed, 1))
        w2 = math.sin((x * 3.4 + phase * idle_speed * 0.17) * math.tau + _phase_rand(seed, 2))
        w3 = math.sin((x * 5.1 + phase * idle_speed * 0.11) * math.tau + _phase_rand(seed, 3))
        idle_wave = (w1 * 0.52 + w2 * 0.31 + w3 * 0.17)
        ar1 = math.sin((x * 1.35 + phase * 0.23) * math.tau + _phase_rand(seed, 4))
        ar2 = math.sin((x * 2.75 + phase * 0.18) * math.tau + _phase_rand(seed, 5))
        reactive_wave = ar1 * 0.64 + ar2 * 0.36
        y = base + idle_wave * amp_idle + reactive_wave * amp_reactive * (0.55 + p * 0.45)
        d = y - base
        d *= up_comp if d >= 0.0 else down_comp
        y = base + d
        if y > top_soft:
            y = top_soft + (y - top_soft) * 0.34
        out[i] = _clamp(y, 0.04, 0.96)
    smooth01 = _clamp(float(smoothness), 0.0, 1.0)
    pre_radius = 1 + int(round(2.0 * smooth01))
    post_radius = 1 + int(round(1.0 * smooth01))
    max_step = 0.040 - 0.020 * smooth01
    out = _moving_average(out, pre_radius)
    out = _slope_limit(out, max_step)
    out = _moving_average(out, post_radius)
    return out


def solve_devcurve_frame(
    state: DevCurveRuntimeState,
    *,
    dt: float,
    now_ts: float,
    playing: bool,
    energy_bands,
    transient_bus,
    layer_shape_nodes: Dict[str, List[List[float]]],
    base_level: float,
    motion_power: float,
    idle_motion: float,
    idle_speed: float,
    smoothness: float,
    layer_settings: Dict[str, Dict[str, float | bool]],
    growth: float,
) -> Dict[str, object]:
    dt = _clamp(float(dt), 0.001, 0.1)
    state.phase += dt
    energies = _layer_energy_map(energy_bands, transient_bus, playing)
    for key in _LAYER_ORDER:
        target = energies[key]
        alpha = 0.30 if playing else 0.14
        state.smooth_energy[key] = state.smooth_energy[key] + (target - state.smooth_energy[key]) * alpha
    layers_out: Dict[str, List[float]] = {}
    aggregate_energy = (
        state.smooth_energy["bass"] * 0.34
        + state.smooth_energy["vocals"] * 0.30
        + state.smooth_energy["mids"] * 0.24
        + state.smooth_energy["transients"] * 0.12
    )
    aggregate_energy = _clamp(aggregate_energy, 0.0, 2.0)

    for idx, key in enumerate(_LAYER_ORDER):
        ls = layer_settings.get(key, {})
        enabled = bool(ls.get("enabled", True))
        power = float(ls.get("power", 1.0))
        offset = float(ls.get("offset", 0.0))
        reactive = state.smooth_energy[key] if enabled else 0.0
        raw_nodes = layer_shape_nodes.get(key) if isinstance(layer_shape_nodes, dict) else None
        nodes = raw_nodes if isinstance(raw_nodes, list) and raw_nodes else [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
        profile = _smooth_points(nodes, DEVCURVE_SAMPLE_COUNT)
        c = _build_curve(
            sample_count=DEVCURVE_SAMPLE_COUNT,
            base_level=base_level,
            profile=profile,
            seed=idx * 997 + 13,
            phase=now_ts,
            idle_motion=idle_motion,
            idle_speed=idle_speed,
            smoothness=smoothness,
            reactive=reactive,
            power=motion_power * power,
            offset=offset,
            growth=growth,
        )
        prev = state.previous_layers.get(key)
        if prev and len(prev) == len(c):
            lerp = 0.44 if playing else 0.24
            c = [prev[i] + (c[i] - prev[i]) * lerp for i in range(len(c))]
        state.previous_layers[key] = c
        layers_out[key] = c

    all_curves = list(layers_out.values())
    max_step = 0.0
    for curve in all_curves:
        for i in range(1, len(curve)):
            max_step = max(max_step, abs(curve[i] - curve[i - 1]))
    state.smoothness_max_step = max_step
    state.idle_amplitude = idle_motion * 0.018
    state.active_amplitude = aggregate_energy * motion_power * 0.135
    draw_order = sorted(
        _LAYER_ORDER,
        key=lambda src: (
            int(layer_settings.get(src, {}).get("order", _LAYER_INDEX[src] + 1)),
            _LAYER_INDEX[src],
        ),
    )

    return {
        "layers": layers_out,
        "draw_order": draw_order,
        "sample_count": DEVCURVE_SAMPLE_COUNT,
        "smoothness_max_step": state.smoothness_max_step,
        "active_amplitude": state.active_amplitude,
        "idle_amplitude": state.idle_amplitude,
        "energies": dict(state.smooth_energy),
    }
