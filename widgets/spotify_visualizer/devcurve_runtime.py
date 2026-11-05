"""Dev Curve runtime spline solver.

Computes full-width smooth layered curves for bass/vocals/mids/transients.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List, Sequence

import numpy as np


DEVCURVE_SAMPLE_COUNT = 96
# Material/specular highlights travel continuously at this cruise rate in a usual passage.
# Per-frame audio never touches it (historic bug: an energy throttle swung it ~12x and
# lurched; a later +/-10% transient nudge still made it breathe with the beat, operator
# 2026-10-04): only the passage moves it, along the very gentle ramp below.
DEVCURVE_MATERIAL_TRAVEL_CRUISE_RATE = 0.23 / 1.35
# The passage drive, 0..1, scales from the track's quietest passage to its loudest: travel
# speed, the undulation's phase speed and the undulation's swing (its slope). Passage intensity
# flickers 0..1 with the beat, so it is eased into the passage level a viewer hears (2 s means
# on real music: ~0.25 in the quietest passages, ~0.65 usual, ~0.95 loudest) through two even
# stages of DEVCURVE_PASSAGE_TAU_S each: a change of passage then speeds up and slows down along
# an S-curve, with no kink where it starts or ends. Mapped through those points, a usual passage
# (drive 0.5) is the historical look. When paused the level eases back to usual.
DEVCURVE_PASSAGE_TRAVEL = (0.5, 1.6)
DEVCURVE_PASSAGE_PHASE_SPEED = (0.45, 1.65)
DEVCURVE_PASSAGE_SWING = (0.55, 1.45)
DEVCURVE_PASSAGE_POINTS = (0.25, 0.65, 0.95)
DEVCURVE_PASSAGE_USUAL = DEVCURVE_PASSAGE_POINTS[1]
DEVCURVE_PASSAGE_TAU_S = 1.2
# The reaction is the curves' height (operator 2026-10-04: a hit lifts it quickly, ramp-downs
# are gentle) plus a travelling swell (2026-11-05). Each layer's height drive passes through two
# cascaded followers of DEVCURVE_SWING_STAGE_S (attack, release) each, with the adaptive response
# gain between them, so the height's velocity is continuous (a single 45 ms first-order attack
# jumped the velocity on every transient: acceleration spikes > 4x the median on ~19% of the
# transients layer's ticks on recorded music).
DEVCURVE_SWING_STAGE_S = (0.04, 0.15)
# Real contrast (operator 2026-11-05: "its smoothness is great but it has almost no
# reactivity"). The shared control lanes are each band over a fast-adapting norm of the loudest
# band: the dominant band sits at 1.0 whatever the music does (bass/mids drives were above 0.9
# on 95-98% of playing ticks on three recordings). They are the band's SHARE; the band's level is
# that share times the bus loudness on the fixed real-music scale (3-17 in music).
#
# The height is a slow BODY plus fast ACCENTS (operator 2026-11-05: an adaptive gain that also
# normalised the beats muted kicks in sustained passages; the first cut here measured a kick 40-60 s
# into a sustained passage at 0.66 of the same kick near its start, and kicks in sustained loud
# passages moved the drive by only ~0.01-0.02). Only the body is normalised: adaptive response gain
# (guide 13D) divides the body (two slow stages, DEVCURVE_BODY_STAGE_S) by a memory of its own recent
# peak (reached in DEVCURVE_RESPONSE_REACH_S, relaxing over DEVCURVE_RESPONSE_MEMORY_S, never below
# its floor), so every song uses the whole body range, a quiet passage after a loud one stays quiet
# and the remembered peak lands at DEVCURVE_BODY_TOP. Accents are the fast level above the body, read
# on the fixed scale against DEVCURVE_ACCENT_REF (never against a memory) and eased into the reserved
# headroom DEVCURVE_ACCENT_ROOM above the body: a kick lifts the curves as much 60 s into a passage as
# at its start. Floors and references are fixed anchors: bass, vocals and mids in loudness units
# (usual music 8.5; eased levels sit ~5-14 on real music, beats stand ~3-6 above the body), the
# transients layer in units of its gated flux lane (its passage ramp keeps quiet passages small).
DEVCURVE_BODY_STAGE_S = (0.45, 0.8)
DEVCURVE_RESPONSE_REACH_S = 1.0
DEVCURVE_RESPONSE_MEMORY_S = 20.0
DEVCURVE_RESPONSE_GAMMA = 1.6
DEVCURVE_RESPONSE_FLOOR = {"bass": 6.0, "vocals": 6.0, "mids": 6.0, "transients": 0.25}
DEVCURVE_BODY_TOP, DEVCURVE_BODY_OVER = 0.55, 0.08
DEVCURVE_ACCENT_ROOM = 0.42
DEVCURVE_ACCENT_REF = {"bass": 4.0, "vocals": 4.0, "mids": 4.0, "transients": 0.35}
# Typed beats reach the body layers through their own flux lanes too (the swell's sources, already
# passage-ramped): on dense real music a kick barely lifts the loudness above its body, so the level
# excess alone left sustained-passage kicks at ~0.01 of drive. Fixed scale (lane units), no memory.
DEVCURVE_ACCENT_FLUX_REF = 0.8
# Travelling swell (guide 13D: energy moves with the shape). Each layer's accents (its flux lane
# above that lane's own recent mean) inject energy just beyond the right edge; it travels left
# with the material at Swell Speed x the passage travel factor, fades over
# DEVCURVE_SWELL_FADE_S and, wherever it is, swells that layer's OWN undulation: the reactive
# displacement is multiplied by a positive envelope, so crests rise and troughs deepen and no new
# bump is invented. Injection eases in through two stages (velocity-continuous, never a pop).
DEVCURVE_SWELL_GRID = np.linspace(-0.5, 1.5, 161)
DEVCURVE_SWELL_DX = float(DEVCURVE_SWELL_GRID[1] - DEVCURVE_SWELL_GRID[0])
DEVCURVE_SWELL_ORIGIN = 1.22          # born outside the view: it slides in already formed
DEVCURVE_SWELL_SIGMA = 0.12           # FWHM 0.28: at least 0.8 of the shortest carrier wavelength
DEVCURVE_SWELL_FADE_S = 1.3
DEVCURVE_SWELL_STAGE_S = 0.05
DEVCURVE_SWELL_ACCENT_S = 0.6         # the lane's recent mean an accent must stand above
DEVCURVE_SWELL_ACCENT_FLOOR = 0.04
DEVCURVE_SWELL_GAIN = 70.0            # injected energy per (lane excess x second): a strong hit ~1
DEVCURVE_SWELL_DEPTH = 0.6            # envelope gain of a full swell at Swell Strength 1
DEVCURVE_SWELL_SATURATION = 1.2
_SWELL_BIRTH = np.exp(-0.5 * ((DEVCURVE_SWELL_GRID - DEVCURVE_SWELL_ORIGIN) / DEVCURVE_SWELL_SIGMA) ** 2)
DEVCURVE_SWELL_SOURCES = {"bass": ("bass",), "vocals": ("mid", "high"), "mids": ("mid",), "transients": ("bass",)}
# Flow rule: for y = c(x) g(x) the envelope may deepen the carrier's curvature but never reverse
# it: |g'|/g <= SLOPE k and |g''|/g <= CURVE k^2, k the shortest reactive carrier's wavenumber
# (2.75 cycles per width). One share per layer bounds the envelope in closed form; it may fall at
# once and rises at most DEVCURVE_FLOW_SHARE_RISE per second (never a whole-curve pop).
DEVCURVE_FLOW_WAVENUMBER = 2.0 * math.pi * 2.75
DEVCURVE_FLOW_SLOPE, DEVCURVE_FLOW_CURVE = 0.2, 0.3
DEVCURVE_FLOW_SHARE_RISE = 1.5
# Height x swell eases toward a ceiling above 1 (the old pinned height): a swell over a loud
# passage still crests, smoothly bounded, never clipped.
DEVCURVE_REACTION_KNEE, DEVCURVE_REACTION_ROOM = 1.0, 0.4
# The drawn curves follow the solved shape within a few frames (playing, paused).
DEVCURVE_CURVE_FOLLOW_S = (0.03, 0.06)
_LAYER_ORDER = ("bass", "vocals", "mids", "transients")
_SAMPLE_XS = np.linspace(0.0, 1.0, DEVCURVE_SAMPLE_COUNT)
_BODY_LAYERS = frozenset(("bass", "vocals", "mids"))   # the transients layer's level already is its flux lane
_LAYER_INDEX = {name: idx for idx, name in enumerate(_LAYER_ORDER)}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _passage_position(intensity: float) -> float:
    """Passage intensity -> drive target: 0 at the quietest point, 0.5 usual, 1 loudest."""
    quiet, usual, loud = DEVCURVE_PASSAGE_POINTS
    value = float(intensity)
    if value <= usual:
        return 0.5 * _clamp((value - quiet) / (usual - quiet), 0.0, 1.0)
    return 0.5 + 0.5 * _clamp((value - usual) / (loud - usual), 0.0, 1.0)


def _passage_lerp(span: tuple[float, float], drive: float) -> float:
    """span[0] at drive 0 (quietest passage), exactly 1 at 0.5 (usual), span[1] at 1 (loudest)."""
    drive = _clamp(drive, 0.0, 1.0)
    if drive <= 0.5:
        return span[0] + (1.0 - span[0]) * (drive / 0.5)
    return 1.0 + (span[1] - 1.0) * ((drive - 0.5) / 0.5)


def _follow(value: float, target: float, dt: float, attack: float, release: float) -> float:
    tau = attack if target > value else release
    return target + (value - target) * math.exp(-dt / tau)


def _body_response(ratio: float) -> float:
    """Body over its remembered peak -> body drive: BODY_TOP x ratio^GAMMA (gamma > 1 keeps the
    middle of the range for ordinary music), easing exponentially above BODY_TOP by at most
    BODY_OVER (never flat, never into the accents' reserved room)."""
    value = max(0.0, ratio) ** DEVCURVE_RESPONSE_GAMMA
    if value > 1.0:
        value = 1.0 + DEVCURVE_BODY_OVER * (1.0 - math.exp(-(value - 1.0) / DEVCURVE_BODY_OVER))
    return DEVCURVE_BODY_TOP * value


def _accent_response(excess: float, reference: float, flux: float = 0.0) -> float:
    """Fast level above the body and the layer's flux lane, on fixed scales -> share of the reserved
    accent room."""
    strength = max(0.0, excess) / reference + max(0.0, flux) / DEVCURVE_ACCENT_FLUX_REF
    return DEVCURVE_ACCENT_ROOM * (1.0 - math.exp(-strength))


def _reaction_top(value: float) -> float:
    if value <= DEVCURVE_REACTION_KNEE:
        return value
    return DEVCURVE_REACTION_KNEE + DEVCURVE_REACTION_ROOM * (
        1.0 - math.exp(-(value - DEVCURVE_REACTION_KNEE) / DEVCURVE_REACTION_ROOM)
    )


def _reaction_top_array(values: np.ndarray) -> np.ndarray:
    """``_reaction_top`` element-wise (identical arithmetic)."""
    over = np.maximum(values - DEVCURVE_REACTION_KNEE, 0.0)
    eased = DEVCURVE_REACTION_KNEE + DEVCURVE_REACTION_ROOM * (1.0 - np.exp(-over / DEVCURVE_REACTION_ROOM))
    return np.where(values <= DEVCURVE_REACTION_KNEE, values, eased)


def _uniform_gradient(f: np.ndarray, spacing: float) -> np.ndarray:
    out = np.empty_like(f)
    out[1:-1] = (f[2:] - f[:-2]) / (2.0 * spacing)
    out[0] = (f[1] - f[0]) / spacing
    out[-1] = (f[-1] - f[-2]) / spacing
    return out


def flow_share(swell: np.ndarray) -> float:
    """The largest share in [0, 1] with |g'|/g <= SLOPE k and |g''|/g <= CURVE k^2 for
    g = 1 + share * swell (closed form: each ratio rises monotonically with the share)."""
    if not np.any(swell):
        return 1.0
    k = DEVCURVE_FLOW_WAVENUMBER
    first = _uniform_gradient(swell, DEVCURVE_SWELL_DX)
    second = _uniform_gradient(first, DEVCURVE_SWELL_DX)
    share = 1.0
    for slope, limit in ((np.abs(first), DEVCURVE_FLOW_SLOPE * k), (np.abs(second), DEVCURVE_FLOW_CURVE * k * k)):
        over = slope - limit * swell
        binding = over > limit
        if binding.any():
            share = min(share, float((limit / over[binding]).min()))
    return share


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


def _sample_curve_y_shader(curve: List[float], x: float) -> float:
    if not curve:
        return 0.5
    n = len(curve)
    p = _clamp(x, 0.0, 1.0) * (n - 1)
    i0 = int(math.floor(p))
    i1 = min(i0 + 1, n - 1)
    t = p - i0
    y = curve[i0] + (curve[i1] - curve[i0]) * t
    return _clamp(1.0 - y, 0.02, 0.98)


def _sample_curve_slope_shader(curve: List[float], x: float) -> float:
    if not curve:
        return 0.0
    dx = 1.0 / max(8.0, float(len(curve) - 1))
    y_l = _sample_curve_y_shader(curve, x - dx)
    y_r = _sample_curve_y_shader(curve, x + dx)
    return (y_r - y_l) / max(2.0 * dx, 1e-4)


def _visibility_from_stream_x(x: float) -> float:
    in_left = _smoothstep((x + 0.16) / 0.18)
    in_right = _smoothstep((1.24 - x) / 0.18)
    return _clamp(in_left * in_right, 0.0, 1.0)


def _spawn_specular_stream(
    state: "DevCurveRuntimeState",
    *,
    slot_idx: int,
    initial: bool,
) -> Dict[str, float]:
    seed = state.specular_spawn_counter * 17.0 + slot_idx * 3.71 + 11.0
    r0 = 0.5 + 0.5 * math.sin(seed * 1.923)
    r2 = 0.5 + 0.5 * math.sin(seed * 3.117 + 0.61)
    if initial:
        x = 1.06 - slot_idx * 0.52
    else:
        x = 1.14 + (r0 - 0.5) * 0.09
    return {
        "x": float(x),
        "speed": 1.0,
        "strength": 0.66 + r2 * 0.20,
        "variant": r0,
    }


def _ensure_specular_streams(state: "DevCurveRuntimeState") -> None:
    streams = state.specular_streams
    if len(streams) == 3:
        return
    streams.clear()
    for idx in range(3):
        streams.append(_spawn_specular_stream(state, slot_idx=idx, initial=True))


def _update_specular_streams(
    state: "DevCurveRuntimeState",
    *,
    dt: float,
    curve: List[float],
    energy_drive: float,
    passage_drive: float,
) -> List[List[float]]:
    _ensure_specular_streams(state)
    slots: List[List[float]] = []

    # Travel is a continuous authored motion that follows only the passage, whose drive is
    # already eased along a two-stage S-curve: the beat never touches it. Reaction belongs in
    # the curves' height, fill and highlights. (Historic bugs: an energy throttle swung it ~12x;
    # a transient nudge made it breathe with the beat.)
    material_rate = DEVCURVE_MATERIAL_TRAVEL_CRUISE_RATE * _passage_lerp(
        DEVCURVE_PASSAGE_TRAVEL, passage_drive
    )

    state.foreground_travel_rate = material_rate
    state.specular_travel_rate = material_rate
    state.foreground_travel_pos = (
        float(state.foreground_travel_pos) + dt * material_rate
    ) % 1.0
    for idx, stream in enumerate(state.specular_streams):
        x = float(stream.get("x", 1.0))
        strength = float(stream.get("strength", 0.75))
        variant = _clamp(float(stream.get("variant", 0.5)), 0.0, 1.0)
        x -= dt * material_rate

        if x < -0.40:
            state.specular_spawn_counter += 1
            spawned = _spawn_specular_stream(state, slot_idx=idx, initial=False)
            x = float(spawned["x"])
            strength = float(spawned["strength"])
            variant = float(spawned["variant"])

        target_strength = _clamp(0.48 + energy_drive * 0.58 + (strength - 0.66) * 0.35, 0.30, 1.0)
        strength += (target_strength - strength) * _clamp(dt / 0.20, 0.06, 0.30)
        stream["x"] = x
        stream["speed"] = 1.0
        stream["strength"] = strength
        stream["variant"] = variant

        x_curve = _clamp(x, 0.0, 1.0)
        y = _sample_curve_y_shader(curve, x_curve)
        y = _clamp(y + (variant - 0.5) * 0.010, 0.02, 0.98)
        visibility = _visibility_from_stream_x(x)
        amp = _clamp(strength * visibility, 0.0, 1.0)
        slots.append([float(x), float(y), float(amp), float(variant)])
    return slots


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
    foreground_travel_rate: float = 0.0
    foreground_travel_pos: float = 0.0
    specular_travel_rate: float = 0.0
    # The passage level's two easing stages and the drive mapped from the second (see
    # DEVCURVE_PASSAGE_*); the stages are negative until the first frame seeds them.
    passage_stage: float = -1.0
    passage_level: float = -1.0
    passage_drive: float = 0.5
    # The undulation's own phase, integrated at the passage's phase speed (seeded from the clock
    # on the first frame), so a speed change never jumps the curve.
    reactive_phase: float | None = None
    specular_streams: List[Dict[str, float]] = field(
        default_factory=lambda: [
            {"x": 1.06, "speed": 0.26, "strength": 0.72, "variant": 0.08},
            {"x": 0.54, "speed": 0.24, "strength": 0.70, "variant": 0.42},
            {"x": 0.02, "speed": 0.22, "strength": 0.68, "variant": 0.76},
        ]
    )
    specular_spawn_counter: int = 0
    # Reaction state per layer (see DEVCURVE_SWING_STAGE_S / RESPONSE / SWELL): the first height
    # stage, the remembered peak, the drive (second stage), the accent mean, the two injection
    # stages, the travelling field and the rate-limited flow-rule share.
    level_stage: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 0.0))
    body_stage: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 0.0))
    body: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 0.0))
    flux_stage: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 0.0))
    response_peak: Dict[str, float] = field(default_factory=lambda: dict(DEVCURVE_RESPONSE_FLOOR))
    drive: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 0.0))
    accent_mean: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 0.0))
    swell_pending: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 0.0))
    swell_stage: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 0.0))
    swell_field: Dict[str, np.ndarray] = field(
        default_factory=lambda: {name: np.zeros(DEVCURVE_SWELL_GRID.size) for name in _LAYER_ORDER}
    )
    flow_share: Dict[str, float] = field(default_factory=lambda: dict.fromkeys(_LAYER_ORDER, 1.0))


def _lane(transient_bus, name: str) -> float:
    if transient_bus is None:
        return 0.0
    return float(getattr(transient_bus, f"{name}_transient", getattr(transient_bus, name, 0.0)) or 0.0)


def _layer_levels(eb, transient_bus, loudness: float) -> Dict[str, float]:
    """Each layer's level on a real scale: its band share (control lane) x the bus loudness;
    the transients layer reads its (already passage-ramped) bass flux lane."""
    bass = _clamp(float(getattr(eb, "bass", 0.0) if eb is not None else 0.0), 0.0, 1.0)
    mid = _clamp(float(getattr(eb, "mid", 0.0) if eb is not None else 0.0), 0.0, 1.0)
    high = _clamp(float(getattr(eb, "high", 0.0) if eb is not None else 0.0), 0.0, 1.0)
    level = max(0.0, float(loudness))
    return {
        "bass": bass * level,
        "vocals": (mid * 0.62 + high * 0.38) * level,
        "mids": mid * level,
        "transients": _clamp(_lane(transient_bus, "bass"), 0.0, 2.0),
    }


def _advance_swell(state: "DevCurveRuntimeState", key: str, *, dt: float, accent: float,
                   speed: float, strength: float) -> np.ndarray | None:
    """Inject, carry and fade one layer's travelling energy; return its flow-bounded envelope
    on DEVCURVE_SWELL_GRID, or None while no swell exists (the envelope would be 1 everywhere)."""
    mean = state.accent_mean[key]
    excess = max(0.0, accent - mean - DEVCURVE_SWELL_ACCENT_FLOOR)
    state.accent_mean[key] = mean + (accent - mean) * (1.0 - math.exp(-dt / DEVCURVE_SWELL_ACCENT_S))
    state.swell_pending[key] += DEVCURVE_SWELL_GAIN * excess * dt
    ease = 1.0 - math.exp(-dt / DEVCURVE_SWELL_STAGE_S)
    moved = state.swell_pending[key] * ease
    release = state.swell_stage[key] * ease          # the second stage drains what the first held
    state.swell_pending[key] -= moved
    state.swell_stage[key] += moved - release
    swell = state.swell_field[key]
    if swell.any() or release > 0.0:
        shift = speed * dt
        if shift > 0.0:
            swell[:] = np.interp(DEVCURVE_SWELL_GRID + shift, DEVCURVE_SWELL_GRID, swell, left=0.0, right=0.0)
        swell *= math.exp(-dt / DEVCURVE_SWELL_FADE_S)
        if release > 0.0:
            swell += release * _SWELL_BIRTH
        swell[swell < 1e-7] = 0.0
    if strength <= 0.0 or not swell.any():
        state.flow_share[key] = min(1.0, state.flow_share[key] + DEVCURVE_FLOW_SHARE_RISE * dt)
        return None
    envelope = strength * DEVCURVE_SWELL_DEPTH * DEVCURVE_SWELL_SATURATION * np.tanh(swell / DEVCURVE_SWELL_SATURATION)
    share = min(flow_share(envelope), state.flow_share[key] + DEVCURVE_FLOW_SHARE_RISE * dt)
    state.flow_share[key] = share
    return 1.0 + share * envelope


def _layer_energy_map(eb, transient_bus, playing: bool) -> Dict[str, float]:
    bass = float(getattr(eb, "bass", 0.0) if eb is not None else 0.0)
    mid = float(getattr(eb, "mid", 0.0) if eb is not None else 0.0)
    high = float(getattr(eb, "high", 0.0) if eb is not None else 0.0)
    transient = float(
        getattr(
            transient_bus,
            "bass_transient",
            getattr(transient_bus, "bass", 0.0),
        )
        if transient_bus is not None
        else 0.0
    )
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
    reactive_phase: float,
    idle_motion: float,
    idle_speed: float,
    smoothness: float,
    reactive: Sequence[float],
    power: float,
    offset: float,
) -> List[float]:
    """``reactive``: the layer's reaction at each sample (height drive x travelling swell)."""
    out: List[float] = [0.0] * sample_count
    amp_idle = 0.018 * idle_motion
    amp_reactive = 0.135 * power
    # Authored spline Y maps directly to runtime Y at idle (0.0->bottom,
    # 1.0->top in authored space). The old devcurve_growth card-height
    # control is deliberately absent from this authored field solver.
    _ = base_level
    center_shift = 0.0
    base_bias = 0.0
    top_soft = 0.95
    # The per-layer phase offsets depend only on the seed: computed once per curve, not per sample
    # (identical values; ~2300 fewer calls a tick).
    r1, r2, r3, r4, r5 = (_phase_rand(seed, k) for k in range(1, 6))
    for i in range(sample_count):
        x = i / max(1, sample_count - 1)
        p = _clamp(profile[i], 0.0, 1.0)
        # Author nodes define the pre-energy resting contour; base_level acts
        # as a global vertical bias around that authored shape.
        base = _clamp(p + base_bias + offset + center_shift, 0.02, 0.98)
        w1 = math.sin((x * 2.0 + phase * idle_speed * 0.28) * math.tau + r1)
        w2 = math.sin((x * 3.4 + phase * idle_speed * 0.17) * math.tau + r2)
        w3 = math.sin((x * 5.1 + phase * idle_speed * 0.11) * math.tau + r3)
        idle_wave = (w1 * 0.52 + w2 * 0.31 + w3 * 0.17)
        ar1 = math.sin((x * 1.35 + reactive_phase * 0.23) * math.tau + r4)
        ar2 = math.sin((x * 2.75 + reactive_phase * 0.18) * math.tau + r5)
        reactive_wave = ar1 * 0.64 + ar2 * 0.36
        y = base + idle_wave * amp_idle + reactive_wave * amp_reactive * reactive[i] * (0.55 + p * 0.45)
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
    passage_intensity: float,
    loudness: float = 0.0,
    swell_strength: float = 1.0,
    swell_speed: float = 1.2,
) -> Dict[str, object]:
    """``passage_intensity`` is where the music sits in the track's own range
    (``BeatEngine.get_musical_intensity``); it is eased into the slow passage drive.
    ``loudness`` is the bus loudness on the fixed real-music scale (``get_musical_level()[0]``):
    with the control lanes' band shares it gives each layer a real level (0 when not ready).
    ``swell_strength`` / ``swell_speed`` are the travelling swell's controls."""
    dt = _clamp(float(dt), 0.001, 0.1)
    state.phase += dt
    passage_target = (
        _clamp(float(passage_intensity), 0.0, 1.0) if playing else DEVCURVE_PASSAGE_USUAL
    )
    if state.passage_level < 0.0:
        state.passage_stage = state.passage_level = passage_target
    else:
        ease = 1.0 - math.exp(-dt / DEVCURVE_PASSAGE_TAU_S)
        state.passage_stage += (passage_target - state.passage_stage) * ease
        state.passage_level += (state.passage_stage - state.passage_level) * ease
    state.passage_drive = _passage_position(state.passage_level)
    if state.reactive_phase is None:
        state.reactive_phase = float(now_ts)
    state.reactive_phase += dt * _passage_lerp(DEVCURVE_PASSAGE_PHASE_SPEED, state.passage_drive)
    swing = _passage_lerp(DEVCURVE_PASSAGE_SWING, state.passage_drive)
    attack, release = DEVCURVE_SWING_STAGE_S
    if playing:
        targets = _layer_levels(energy_bands, transient_bus, loudness)
    else:
        # Paused: the authored idle lanes, below any gain (silence is never amplified).
        targets = _layer_energy_map(energy_bands, transient_bus, playing)
    body_attack, body_release = DEVCURVE_BODY_STAGE_S
    for key in _LAYER_ORDER:
        # Every second stage follows its first stage as it stood at the start of this tick, so a hit's
        # first tick moves the drive by (almost) nothing: the velocity is continuous on the logical clock.
        stage, body_stage, body = state.level_stage[key], state.body_stage[key], state.body[key]
        flux = state.flux_stage[key]
        lanes = DEVCURVE_SWELL_SOURCES[key]
        flux_target = 0.0
        if playing and key in _BODY_LAYERS:
            # An accent is the lane above its own recent mean (the swell's accent test), never a steady level.
            lane_level = sum(_lane(transient_bus, lane) for lane in lanes) / len(lanes)
            flux_target = max(0.0, lane_level - state.accent_mean[key] - DEVCURVE_SWELL_ACCENT_FLOOR)
        state.flux_stage[key] = _follow(flux, flux_target, dt, attack, release)
        state.level_stage[key] = _follow(stage, targets[key], dt, attack, release)
        state.body_stage[key] = _follow(body_stage, targets[key], dt, body_attack, body_release)
        state.body[key] = _follow(body, body_stage, dt, body_attack, body_release)
        if playing:
            peak = max(DEVCURVE_RESPONSE_FLOOR[key], _follow(
                state.response_peak[key], body, dt, DEVCURVE_RESPONSE_REACH_S, DEVCURVE_RESPONSE_MEMORY_S))
            state.response_peak[key] = peak
            gained = _body_response(body / peak) + _accent_response(stage - body, DEVCURVE_ACCENT_REF[key], flux)
        else:
            gained = stage
        state.drive[key] = _follow(state.drive[key], gained, dt, attack, release)
        state.smooth_energy[key] = state.drive[key]
    travel = _passage_lerp(DEVCURVE_PASSAGE_TRAVEL, state.passage_drive)
    swell_speed = _clamp(float(swell_speed), 0.0, 3.0) * travel
    swell_strength = _clamp(float(swell_strength), 0.0, 2.0)
    layers_out: Dict[str, List[float]] = {}
    aggregate_energy = (
        state.smooth_energy["bass"] * 0.34
        + state.smooth_energy["vocals"] * 0.30
        + state.smooth_energy["mids"] * 0.24
        + state.smooth_energy["transients"] * 0.12
    )
    aggregate_energy = _clamp(aggregate_energy, 0.0, 2.0)
    follow = 1.0 - math.exp(-dt / DEVCURVE_CURVE_FOLLOW_S[0 if playing else 1])
    swell_peaks: Dict[str, float] = {}
    reactions: Dict[str, float] = {}

    for idx, key in enumerate(_LAYER_ORDER):
        ls = layer_settings[key]
        enabled = bool(ls["enabled"])
        power = float(ls["power"])
        offset = float(ls["offset"])
        sources = DEVCURVE_SWELL_SOURCES[key]
        accent = sum(_lane(transient_bus, lane) for lane in sources) / len(sources) if playing and enabled else 0.0
        envelope = _advance_swell(state, key, dt=dt, accent=accent, speed=swell_speed, strength=swell_strength)
        drive = state.drive[key] if enabled else 0.0
        if envelope is None:
            swell_peaks[key] = 0.0
            reactive = [_reaction_top(drive)] * DEVCURVE_SAMPLE_COUNT
        else:
            gain = np.interp(_SAMPLE_XS, DEVCURVE_SWELL_GRID, envelope)
            swell_peaks[key] = float(gain.max() - 1.0)
            reactive = _reaction_top_array(drive * gain).tolist()
        # The visible reaction: the mean multiplier the music puts on this layer's undulation.
        reactions[key] = sum(reactive) / DEVCURVE_SAMPLE_COUNT
        nodes = layer_shape_nodes[key]
        if len(nodes) < 2:
            raise ValueError(f"DevCurve layer {key!r} requires resolved shape nodes")
        profile = _smooth_points(nodes, DEVCURVE_SAMPLE_COUNT)
        c = _build_curve(
            sample_count=DEVCURVE_SAMPLE_COUNT,
            base_level=base_level,
            profile=profile,
            seed=idx * 997 + 13,
            phase=now_ts,
            reactive_phase=state.reactive_phase,
            idle_motion=idle_motion,
            idle_speed=idle_speed,
            smoothness=smoothness,
            reactive=reactive,
            power=motion_power * power * swing,
            offset=offset,
        )
        prev = state.previous_layers.get(key)
        if prev and len(prev) == len(c):
            c = [prev[i] + (c[i] - prev[i]) * follow for i in range(len(c))]
        state.previous_layers[key] = c
        layers_out[key] = c

    all_curves = list(layers_out.values())
    max_step = 0.0
    for curve in all_curves:
        for i in range(1, len(curve)):
            max_step = max(max_step, abs(curve[i] - curve[i - 1]))
    state.smoothness_max_step = max_step
    state.idle_amplitude = idle_motion * 0.018
    state.active_amplitude = aggregate_energy * motion_power * 0.135 * swing
    draw_order = sorted(
        _LAYER_ORDER,
        key=lambda src: (
            int(layer_settings[src]["order"]),
            _LAYER_INDEX[src],
        ),
    )
    enabled_order = [
        src for src in draw_order if bool(layer_settings[src]["enabled"])
    ]
    foreground_layer = enabled_order[-1] if enabled_order else ""
    foreground_layer_id = _LAYER_INDEX[foreground_layer] if foreground_layer else -1
    specular_slots: List[List[float]] = [[0.0, 0.0, 0.0, 0.0] for _ in range(3)]
    if foreground_layer and foreground_layer in layers_out:
        curve = layers_out[foreground_layer]
        energy_drive = _clamp(
            state.smooth_energy.get("bass", 0.0) * 0.34
            + state.smooth_energy.get("vocals", 0.0) * 0.33
            + state.smooth_energy.get("mids", 0.0) * 0.23
            + state.smooth_energy.get("transients", 0.0) * 0.10,
            0.0,
            2.0,
        )
        specular_slots = _update_specular_streams(
            state,
            dt=dt,
            curve=curve,
            energy_drive=energy_drive,
            passage_drive=state.passage_drive,
        )

    return {
        "layers": layers_out,
        "draw_order": draw_order,
        "foreground_layer": foreground_layer,
        "foreground_layer_id": foreground_layer_id,
        "specular_slots": specular_slots,
        "sample_count": DEVCURVE_SAMPLE_COUNT,
        "smoothness_max_step": state.smoothness_max_step,
        "active_amplitude": state.active_amplitude,
        "idle_amplitude": state.idle_amplitude,
        "foreground_travel_rate": state.foreground_travel_rate,
        "foreground_travel_pos": state.foreground_travel_pos,
        "specular_travel_rate": state.specular_travel_rate,
        "passage_drive": state.passage_drive,
        "energies": dict(state.smooth_energy),
        "drives": {
            **{f"height_{key}": state.drive[key] for key in _LAYER_ORDER},
            **{f"swell_{key}": swell_peaks.get(key, 0.0) for key in _LAYER_ORDER},
            **{f"reaction_{key}": reactions.get(key, 0.0) for key in _LAYER_ORDER},
        },
    }
