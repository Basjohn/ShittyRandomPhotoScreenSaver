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
# Neighbouring lanes cross-fade over this much of the land's height either side of their boundary. A lane used to
# start at its boundary's contour: two different patterns met there, and loud music tore the land along every such
# contour into terraces and cliffs (1B.6).
REACTION_LANE_BLEND = 0.06
# Growth: landforms that stand only while the music holds them up, as a share of Terrain Height at full drive.
# Mounds (shape 0) are broad and low, spires (shape 1) slender and tall; both are sites on a fixed lattice of the
# land (world units a cell), each waking at its own level of the drive, so louder music raises more of them.
GROWTH_HEIGHT = (0.30, 0.72)
GROWTH_CELL = (1.05, 0.70)
GROWTH_SHARPNESS = (1.0, 2.6)   # the site profile's power: a rounded dome to a slender peak
INDENT_CELL = 0.85
# Indents carve bowls into visible land. The depth law, at full drive in a bowl's middle: a share of the land's own
# height there plus an absolute depth (a share of Terrain Height), eased onto a floor share of the authored height.
# The share alone left low land (dunes a tenth of the height scale) with dips too shallow to see; the absolute term
# is what carves them, and the floor is what keeps every bowl dry land above the water plane.
INDENT_SHARE = 0.65
INDENT_ABSOLUTE = 0.40
INDENT_FLOOR = 0.08
INDENT_SHARPNESS = 1.0
INDENT_PRESS = 1.5   # a bowl's middle (press 0.55..1 at full drive) takes 68..90% of the depth
# Indents only lower the land, so the camera floor never needs to know them: they give way round the eye only over
# a short reach (the ground just under the eye stays put), not Growth's wide one, which left the near dunes of
# every default view untouched.
INDENT_EYE_CLEAR = (0.25, 0.75)


# Growth stands back from the eye: nothing within the first distance (world units, along the ground), whole by
# the second. The camera floor does not know the music's landforms (a floor tall enough for a spire would lift
# every authored low view the moment Growth is turned on), so they give way to the eye instead and ease back in
# behind it as it flies on.
GROWTH_EYE_CLEAR = (0.8, 2.0)


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


def _ease(x: float) -> float:
    t = max(0.0, min(1.0, x))
    return t * t * (3.0 - 2.0 * t)


def lane_membership(notches: Sequence, height: float) -> tuple[float, ...]:
    """How much of each lane (in ``REACTION_LANES`` order) owns ``height`` (0..1 along the land's elevation): 1
    inside the lane's stretch, easing across each boundary over ``REACTION_LANE_BLEND`` either side, so neighbouring
    lanes cross-fade instead of switching. The five always sum to 1."""
    ordered = sorted(((float(position), label) for position, label in notches), key=lambda item: item[0])
    out = [0.0] * len(REACTION_LANES)
    for index, (start, label) in enumerate(ordered):
        rise = 1.0 if index == 0 else _ease((height - start) / (2.0 * REACTION_LANE_BLEND) + 0.5)
        fall = (0.0 if index + 1 == len(ordered)
                else _ease((height - ordered[index + 1][0]) / (2.0 * REACTION_LANE_BLEND) + 0.5))
        out[REACTION_LANES.index(label)] += max(0.0, rise - fall)
    return tuple(out)


def bake_terrain_shaper(shaper: Mapping) -> dict:
    """Elevation tables for the height shader: per lane (``REACTION_LANES`` order, ``REACTION_SAMPLES`` each, one
    flat tuple) its weight along the land's height (curve x lane strength x the lane's eased share of that height),
    and the curve alone (the bias Pulses and Swell follow). The shader reads them through a smooth (cubic) filter,
    so a lane's pattern fades in and out along the slope instead of starting at a contour."""
    from utils.curve_nodes import interpolate_nodes

    curve = interpolate_nodes(shaper["nodes"], REACTION_SAMPLES)
    weights = [[0.0] * REACTION_SAMPLES for _ in REACTION_LANES]
    for index in range(REACTION_SAMPLES):
        share = lane_membership(shaper["notches"], index / (REACTION_SAMPLES - 1))
        for lane, label in enumerate(REACTION_LANES):
            weights[lane][index] = float(curve[index]) * float(shaper["lanes"][label]) * share[lane]
    return {"lanes": tuple(value for lane in weights for value in lane),
            "bias": tuple(float(value) for value in curve)}


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
uniform float uReactionLanes[5 * REACTION_SAMPLES];   // per lane, its eased weight along the land's height
uniform float uReactionBias[REACTION_SAMPLES];
uniform vec4 uReactionForms;             // Growth (amount), its shape (0 mounds .. 1 spires), Indents (amount)
uniform vec2 uReactionDrives;            // the music's fixed-scale drive of Growth and of Indents, 0..1
const vec2 GROWTH_HEIGHT = vec2({GROWTH_HEIGHT[0]:.6f}, {GROWTH_HEIGHT[1]:.6f});
const vec2 GROWTH_CELL = vec2({GROWTH_CELL[0]:.6f}, {GROWTH_CELL[1]:.6f});
const vec2 GROWTH_SHARPNESS = vec2({GROWTH_SHARPNESS[0]:.6f}, {GROWTH_SHARPNESS[1]:.6f});
const float INDENT_CELL = {INDENT_CELL:.6f};
const float INDENT_SHARE = {INDENT_SHARE:.6f};
const float INDENT_ABSOLUTE = {INDENT_ABSOLUTE:.6f};
const float INDENT_FLOOR = {INDENT_FLOOR:.6f};
const float INDENT_SHARPNESS = {INDENT_SHARPNESS:.6f};
const float INDENT_PRESS = {INDENT_PRESS:.6f};
// The tables are read through the land's own cubic filter: a weight that changes along the slope does so with a
// continuous slope and curvature, so the surface it scales keeps continuous normals.
vec4 reactionFilter(float t) {{
    float t2 = t * t, t3 = t2 * t;
    return vec4(pow(1.0 - t, 3.0), 3.0 * t3 - 6.0 * t2 + 4.0, -3.0 * t3 + 3.0 * t2 + 3.0 * t + 1.0, t3) / 6.0;
}}
// Three fixed numbers (0..1) for a lattice cell: an integer hash, the same on every GPU.
vec3 reactionSite(ivec2 cell, uint seed) {{
    uint n = uint(cell.x) * 0x9E3779B1u ^ uint(cell.y) * 0x85EBCA77u ^ seed * 0xC2B2AE3Du;
    n ^= n >> 15; n *= 0x2C1B3C6Du; n ^= n >> 12; n *= 0x297A2D39u; n ^= n >> 15;
    return vec3(float(n & 1023u), float((n >> 10) & 1023u), float((n >> 20) & 1023u)) / 1023.0;
}}
// Landforms the music holds up (or presses in): one site in every cell of a fixed lattice of the land, a smooth
// compact bump (zero height and slope at its rim) that wakes as the drive passes the site's own level, so more of
// them stand the louder the music is and each eases in and out. A pure function of the place and the drive.
float basinSites(vec2 p, float cell, float sharpness, float drive, uint seed) {{
    if (drive <= 0.0) return 0.0;
    vec2 q = p / cell;
    ivec2 home = ivec2(floor(q));
    float total = 0.0;
    for (int j = -1; j <= 1; ++j) for (int i = -1; i <= 1; ++i) {{
        ivec2 c = home + ivec2(i, j);
        vec3 place = reactionSite(c, seed);
        vec3 kind = reactionSite(c, seed + 7u);
        float radius = 0.36 + 0.14 * place.z;                    // at most half a cell: its 3x3 block holds it
        vec2 site = vec2(c) + 0.25 + 0.5 * place.xy;
        vec2 offset = (q - site) / radius;
        float d2 = dot(offset, offset);
        if (d2 >= 1.0) continue;
        float wake = 0.6 * kind.x;
        float rise = smoothstep(wake, wake + 0.4, drive);
        float bump = (1.0 - d2) * (1.0 - d2);
        total += rise * (0.55 + 0.45 * kind.y) * pow(bump, sharpness);
    }}
    return total;
}}
// The music's landforms give way round the eye (0 beside it, 1 clear of it) instead of moving the camera floor.
float reactionEyeClear(vec2 p) {{
    return smoothstep({GROWTH_EYE_CLEAR[0]:.6f}, {GROWTH_EYE_CLEAR[1]:.6f}, length(p - uEye.xz));
}}
// Growth, in Terrain Height units: mounds to spires by its shape.
float basinGrowth(vec2 p) {{
    if (uReactionForms.x <= 0.0) return 0.0;
    float shape = uReactionForms.y;
    float clear = reactionEyeClear(p);
    if (clear <= 0.0) return 0.0;
    return clear * uReactionForms.x * mix(GROWTH_HEIGHT.x, GROWTH_HEIGHT.y, shape)
           * basinSites(p, mix(GROWTH_CELL.x, GROWTH_CELL.y, shape), mix(GROWTH_SHARPNESS.x, GROWTH_SHARPNESS.y, shape),
                        uReactionDrives.x, 11u);
}}
// Indents: how hard the land is pressed in here, 0 (not at all) .. 1 (a bowl's middle at full drive).
float basinIndent(vec2 p) {{
    if (uReactionForms.z <= 0.0) return 0.0;
    float clear = smoothstep({INDENT_EYE_CLEAR[0]:.6f}, {INDENT_EYE_CLEAR[1]:.6f}, length(p - uEye.xz));
    if (clear <= 0.0) return 0.0;
    // Uncapped: overlapping bowls add, and the depth law's own easing bounds them (a cap creased where it bit).
    return clear * uReactionForms.z * basinSites(p, INDENT_CELL, INDENT_SHARPNESS, uReactionDrives.y, 29u);
}}
// How far that press sinks land standing at ``height`` whose authored height is ``authored`` (both world units;
// ``scale`` is Terrain Height): a share of the authored height plus an absolute depth, eased onto the floor share
// so a bowl in low land flattens toward the water plane without ever reaching it.
float basinIndentDepth(float press, float height, float authored, float scale) {{
    float space = max(height - INDENT_FLOOR * authored, 0.0);
    // The deepest this point may sink: the law, eased under the room above the floor (never all of it).
    float most = space * tanh((INDENT_SHARE * authored + INDENT_ABSOLUTE * scale) / max(space, 1e-6));
    // The bowl's own profile scales that depth. Saturating the press against the room instead flattened a bowl in
    // low land into a shelf with a sharp rim; overlapping bowls ease toward the most rather than adding past it.
    return most * tanh(INDENT_PRESS * press);
}}
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
// distant continuation, biased along the land's height by the shaper. ``elevation`` is the land's smooth (cubic)
// height: read off the bilinear cells it creased the reshaping along every cell line.
float basinReaction(vec2 uv, float elevation, vec2 p, float landFade) {{
    if (uReaction.x <= 0.0 || landFade <= 0.0) return 0.0;
    float f = clamp(elevation / max(uReactionMaximum, 1e-3), 0.0, 1.0) * float(REACTION_SAMPLES - 1);
    int i = min(int(floor(f)), REACTION_SAMPLES - 1);
    vec4 w = reactionFilter(f - float(i));
    ivec4 at = clamp(ivec4(i - 1, i, i + 1, i + 2), 0, REACTION_SAMPLES - 1);
    float phase = uReactionPhase;
    // Every lane with a share of this height adds its own pattern: lanes cross-fade along the slope.
    float peaks = 0.0;
    for (int lane = 0; lane < 5; ++lane) {{
        if (uReactionBands[lane] <= 0.0) continue;
        int row = lane * REACTION_SAMPLES;
        float weight = w.x * uReactionLanes[row + at.x] + w.y * uReactionLanes[row + at.y]
                     + w.z * uReactionLanes[row + at.z] + w.w * uReactionLanes[row + at.w];
        if (weight > 0.0) peaks += weight * uReactionBands[lane] * basinLanePattern(lane, p, phase);
    }}
    float bias = w.x * uReactionBias[at.x] + w.y * uReactionBias[at.y] + w.z * uReactionBias[at.z]
               + w.w * uReactionBias[at.w];
    float drive = (uReactionBands[0] + uReactionBands[1] + uReactionBands[2] + uReactionBands[3]
                   + uReactionBands[4]) / 5.0;
    float swell = drive * sin(0.9 * p.x + 0.6 * p.y + 0.35 * phase) * cos(0.7 * p.y - 0.5 * p.x + 0.25 * phase);
    float shape = uReaction.y * peaks + bias * (uReaction.z * basinGroundPulses(p) + uReaction.w * swell);
    return uReaction.x * landFade * REACTION_HEIGHT * shape;
}}
"""

__all__ = [
    "GROWTH_CELL",
    "GROWTH_HEIGHT",
    "INDENT_CELL",
    "INDENT_EYE_CLEAR",
    "INDENT_FLOOR",
    "REACTION_FLOOR",
    "REACTION_LANE_BLEND",
    "GROWTH_EYE_CLEAR",
    "lane_membership",
    "REACTION_GLSL",
    "REACTION_HEIGHT",
    "REACTION_LANES",
    "REACTION_SAMPLES",
    "bake_terrain_shaper",
    "normalize_terrain_shaper",
    "reaction_band_energies",
]
