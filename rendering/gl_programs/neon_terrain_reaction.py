"""Neon Lake's Terrain Reaction: the shaper that biases where the land deforms, its bands, and its GLSL.

The shaper is the shared shape editor's data laid along the land's height, from the shoreline (0) to
the authored summit (1): its curve says how strongly each elevation deforms, its notches split that
axis into frequency lanes (Bass .. Treble: which part of the spectrum moves which elevation) and its
lane arrows weight each lane. It is baked once per settings change into small elevation tables the
height shader samples; nothing here runs per frame except ``reaction_band_energies``.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

REACTION_LANES = ("Bass", "Low-Mid", "Vocal", "Hi-Mid", "Treble")
REACTION_SAMPLES = 32          # elevation samples in the baked tables
REACTION_HEIGHT = 0.32         # the largest reshaping, as a share of Terrain Height
REACTION_FLOOR = 0.3           # land never sinks below this share of its authored height


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def normalize_terrain_shaper(value: object, default: Mapping) -> dict:
    """The shaper as stored: ``{"nodes": [[x, y]...], "notches": [[x, lane]...], "lanes": {lane: s}}``.
    A malformed part falls back to the default's; values are clamped into 0..1."""
    value = value if isinstance(value, Mapping) else {}

    nodes = []
    for node in value.get("nodes", ()) if isinstance(value.get("nodes"), (list, tuple)) else ():
        if isinstance(node, (list, tuple)) and len(node) == 2:
            x, y = _finite(node[0]), _finite(node[1])
            if x is not None and y is not None:
                nodes.append([max(0.0, min(1.0, x)), max(0.0, min(1.0, y))])
    if not 2 <= len(nodes) <= 5:
        nodes = [list(map(float, node)) for node in default["nodes"]]
    nodes.sort(key=lambda node: node[0])

    notches = {}
    for notch in value.get("notches", ()) if isinstance(value.get("notches"), (list, tuple)) else ():
        if isinstance(notch, (list, tuple)) and len(notch) == 2 and notch[1] in REACTION_LANES:
            position = _finite(notch[0])
            if position is not None:
                notches[notch[1]] = max(0.0, min(1.0, position))
    if set(notches) != set(REACTION_LANES):
        notches = {label: float(position) for position, label in default["notches"]}
    ordered = sorted(((position, label) for label, position in notches.items()),
                     key=lambda item: (item[0], REACTION_LANES.index(item[1])))
    ordered[0] = (0.0, ordered[0][1])

    lanes = {}
    source = value.get("lanes") if isinstance(value.get("lanes"), Mapping) else {}
    for label in REACTION_LANES:
        strength = _finite(source.get(label, default["lanes"][label]))
        lanes[label] = max(0.0, min(1.0, float(default["lanes"][label]) if strength is None else strength))
    return {"nodes": nodes, "notches": [[position, label] for position, label in ordered], "lanes": lanes}


def bake_terrain_shaper(shaper: Mapping) -> dict:
    """Elevation tables for the height shader: per sample, the lane's band index, its weight (curve x
    lane strength) and the curve alone (the bias Pulses and Swell follow)."""
    from ui.tabs.media.spectrum_shape_editor import interpolate_nodes

    curve = interpolate_nodes(shaper["nodes"], REACTION_SAMPLES)
    notches = shaper["notches"]
    lane, weight = [], []
    for index in range(REACTION_SAMPLES):
        height = index / (REACTION_SAMPLES - 1)
        label = notches[0][1]
        for position, name in notches:
            if position <= height + 1e-9:
                label = name
        lane.append(float(REACTION_LANES.index(label)))
        weight.append(float(curve[index]) * float(shaper["lanes"][label]))
    return {"lane": tuple(lane), "weight": tuple(weight), "bias": tuple(float(value) for value in curve)}


def reaction_band_energies(spectrum: Sequence[float]) -> tuple[float, ...]:
    """The analysis spectrum (log-spaced bands, low to high) as one energy per lane: its five equal
    stretches, so each lane is about an octave group whatever the band count."""
    values = [max(0.0, float(value)) for value in spectrum]
    count = len(values)
    if count == 0:
        return (0.0,) * len(REACTION_LANES)
    energies = []
    for lane in range(len(REACTION_LANES)):
        lo, hi = lane * count / len(REACTION_LANES), (lane + 1) * count / len(REACTION_LANES)
        total = width = 0.0
        for index in range(math.floor(lo), min(count, math.ceil(hi))):
            share = max(0.0, min(hi, index + 1) - max(lo, index))
            total += values[index] * share
            width += share
        energies.append(total / width if width > 0.0 else 0.0)
    return tuple(energies)


REACTION_GLSL = f"""
const int REACTION_SAMPLES = {REACTION_SAMPLES};
const float REACTION_HEIGHT = {REACTION_HEIGHT:.6f};
const float REACTION_FLOOR = {REACTION_FLOOR:.6f};
const float GROUND_PULSE_SPEED = 0.55;   // world units per second through the land
const float GROUND_PULSE_WIDTH = 0.42;
const float GROUND_PULSE_DECAY = 1.6;
uniform vec4 uReaction;                  // strength (0 = off), peaks, pulses, swell
uniform float uReactionBands[5];         // eased lane drives, 0..1
uniform float uReactionPhase;            // the landforms' wander, advanced by the music
uniform float uReactionMaximum;          // the authored summit: the shaper's right edge
uniform float uReactionLane[REACTION_SAMPLES];
uniform float uReactionWeight[REACTION_SAMPLES];
uniform float uReactionBias[REACTION_SAMPLES];
// Each lane reshapes with its own pattern: low lanes heave broad ground up and down, high lanes
// lift finer crests. Signed patterns raise some places and lower others, so the land changes shape.
float basinLanePattern(int lane, vec2 p, float phase) {{
    float scale = 1.6 + 1.6 * float(lane);
    float speed = 0.8 + 0.25 * float(lane);
    float signed = sin(scale * (0.83 * p.x + 0.55 * p.y) + speed * phase)
                 * cos(scale * (0.61 * p.y - 0.47 * p.x) - 0.7 * speed * phase);
    return mix(signed, 0.55 + 0.45 * signed, float(lane) / 4.0);
}}
float basinGroundPulses(vec2 p) {{
    float pulse = 0.0;
    for (int i = 0; i < uEventCount; ++i) {{
        ShockwaveEvent e = events[i];
        float d = length(p - vec2(e.x, e.z)) - GROUND_PULSE_SPEED * e.age;
        float fade = exp(-e.age / GROUND_PULSE_DECAY) * shockwaveSmooth(0.0, 0.12, e.age);
        // A broad heave with a softer sink behind it: the ground rolls as the hit passes.
        pulse += min(e.strength, 1.5) * fade
               * (exp(-pow(d / GROUND_PULSE_WIDTH, 2.0))
                  - 0.45 * exp(-pow((d + 1.6 * GROUND_PULSE_WIDTH) / GROUND_PULSE_WIDTH, 2.0)));
    }}
    return tanh(pulse);   // overlapping hits stay bounded
}}
// The reshaping at a land point, in Terrain Height units: zero on water and at the shore, faded on the
// distant continuation, biased along the land's height by the shaper.
float basinReaction(vec2 uv, float base, vec2 p, float landFade) {{
    if (uReaction.x <= 0.0 || landFade <= 0.0) return 0.0;
    float f = clamp(base / max(uReactionMaximum, 1e-3), 0.0, 1.0) * float(REACTION_SAMPLES - 1);
    int i0 = int(floor(f)), i1 = min(i0 + 1, REACTION_SAMPLES - 1);
    float t = fract(f);
    int lane0 = int(uReactionLane[i0] + 0.5), lane1 = int(uReactionLane[i1] + 0.5);
    float phase = uReactionPhase;
    float peaks = (1.0 - t) * uReactionWeight[i0] * uReactionBands[lane0] * basinLanePattern(lane0, p, phase)
                + t * uReactionWeight[i1] * uReactionBands[lane1] * basinLanePattern(lane1, p, phase);
    float bias = mix(uReactionBias[i0], uReactionBias[i1], t);
    float drive = (uReactionBands[0] + uReactionBands[1] + uReactionBands[2] + uReactionBands[3]
                   + uReactionBands[4]) / 5.0;
    float swell = drive * sin(0.9 * p.x + 0.6 * p.y + 0.35 * phase) * cos(0.7 * p.y - 0.5 * p.x + 0.25 * phase);
    float shape = uReaction.y * peaks + bias * (uReaction.z * basinGroundPulses(p) + uReaction.w * swell);
    return uReaction.x * landFade * REACTION_HEIGHT * shape;
}}
"""

__all__ = [
    "REACTION_FLOOR",
    "REACTION_GLSL",
    "REACTION_HEIGHT",
    "REACTION_LANES",
    "REACTION_SAMPLES",
    "bake_terrain_shaper",
    "normalize_terrain_shaper",
    "reaction_band_energies",
]
