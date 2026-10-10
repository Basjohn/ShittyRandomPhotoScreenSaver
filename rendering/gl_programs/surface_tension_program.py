"""Surface Tension Merge: shaders and CPU mirrors (loaded only when Surface Tension Merge renders).

The new picture arrives as a liquid that pools on the old one. Seeded pools (stratified over the
picture, born one after another) swell and drift; their compact kernels sum into one meniscus
field (``rendering/gl_programs/meniscus_field.py``), so neighbouring pools reach out, bridge and
merge as surface tension would, and the last islands of the old picture shrink and close as a
flood term rises over the end of the run. Along every boundary both liquids rise from a dark
contact line over ``TENSION_WIDTH``: the groove bends each side's picture toward the line through
the shared refraction helpers and catches a key highlight and a Fresnel sheen. The meniscus fades
out between ``TENSION_SETTLE`` while the flood finishes, so the frame is the new picture exactly
from ``TENSION_SETTLE[1]``.
"""

from __future__ import annotations

import math
import random

from rendering.gl_programs.meniscus_field import MENISCUS_FIELD_GLSL, pool_kernel
from rendering.gl_programs.refraction import REFRACTION_GLSL, REFRACTION_IOR_WATER

TENSION_MAX_POOLS = 20
TENSION_POOLS_RANGE = (4, 20)
TENSION_THRESHOLD = 0.3
TENSION_GROW = 0.5           # the share of the run a pool takes to swell to its full radius
TENSION_BIRTHS = (0.0, 0.45)
TENSION_FLOOD = (0.62, 0.88)
TENSION_SETTLE = (0.84, 0.92)
TENSION_WIDTH = 0.024        # meniscus width, picture heights
TENSION_DEPTH = 0.014        # groove depth, picture heights
TENSION_DRIFT = 0.07


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def tension_pools(seed: int, count: int, aspect: float) -> list[tuple[float, float, float, float, float, float]]:
    """(x, y, full radius, birth, drift x, drift y) per pool, picture heights, centred, y up:
    stratified over a grid of cells so the pools spread over the whole picture."""
    rng = random.Random(seed)
    columns = max(1, round(math.sqrt(count * aspect)))
    rows = max(1, math.ceil(count / columns))
    cells = [(c, r) for r in range(rows) for c in range(columns)]
    rng.shuffle(cells)
    scale = math.sqrt(10.0 / count)
    births = sorted(rng.uniform(*TENSION_BIRTHS) for _ in range(count))
    pools = []
    for i in range(count):
        c, r = cells[i]
        x = ((c + rng.uniform(0.2, 0.8)) / columns - 0.5) * aspect
        y = 0.5 - (r + rng.uniform(0.2, 0.8)) / rows
        angle = rng.uniform(0.0, 2.0 * math.pi)
        drift = rng.uniform(0.3, 1.0) * TENSION_DRIFT
        pools.append((x, y, rng.uniform(0.32, 0.55) * scale, births[i], math.cos(angle) * drift, math.sin(angle) * drift))
    return pools


def tension_flood(progress: float) -> float:
    """The field every point gains over the end, past the threshold by the flood's end."""
    return (TENSION_THRESHOLD + 0.05) * _smooth((progress - TENSION_FLOOD[0]) / (TENSION_FLOOD[1] - TENSION_FLOOD[0]))


def tension_settle(progress: float) -> float:
    """How much meniscus is left: fading out as the flood finishes."""
    return 1.0 - _smooth((progress - TENSION_SETTLE[0]) / (TENSION_SETTLE[1] - TENSION_SETTLE[0]))


def tension_field(point: tuple[float, float], pools, progress: float) -> float:
    """CPU mirror of ``tensionField``."""
    field = tension_flood(progress)
    for x, y, radius, birth, dx, dy in pools:
        age = progress - birth
        if age <= 0.0:
            continue
        r = radius * _smooth(age / TENSION_GROW)
        field += pool_kernel(point, (x + dx * age, y + dy * age), r)
    return field


SURFACE_TENSION_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform vec2 uItemSize;\n"
    f"uniform vec4 uPools[{TENSION_MAX_POOLS}];\nuniform vec2 uDrift[{TENSION_MAX_POOLS}];\nuniform int uPoolCount;\n"
    "uniform float uProgress;\nuniform float uGloss;\n"
    + REFRACTION_GLSL + MENISCUS_FIELD_GLSL
    + f"""
const float THRESHOLD = {TENSION_THRESHOLD:.6f};
const float GROW = {TENSION_GROW:.6f};
const vec2 FLOOD = vec2({TENSION_FLOOD[0]:.6f}, {TENSION_FLOOD[1]:.6f});
const vec2 SETTLE = vec2({TENSION_SETTLE[0]:.6f}, {TENSION_SETTLE[1]:.6f});
const float WIDTH = {TENSION_WIDTH:.6f};
const float DEPTH = {TENSION_DEPTH:.6f};

float tensionField(vec2 p) {{
    float field = (THRESHOLD + 0.05) * smoothstep(0.0, 1.0, (uProgress - FLOOD.x) / (FLOOD.y - FLOOD.x));
    for (int i = 0; i < uPoolCount; ++i) {{
        float age = uProgress - uPools[i].w;
        if (age <= 0.0) continue;
        float radius = uPools[i].z * smoothstep(0.0, 1.0, age / GROW);
        field += poolKernel(p, uPools[i].xy + uDrift[i] * age, radius);
    }}
    return field;
}}

void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float aspect = uItemSize.x / uItemSize.y;
    vec2 p = vec2((uv.x - 0.5) * aspect, 0.5 - uv.y);
    float e = 1.5 / uItemSize.y;
    float field = tensionField(p);
    vec2 gradient = vec2(tensionField(p + vec2(e, 0.0)) - tensionField(p - vec2(e, 0.0)),
                         tensionField(p + vec2(0.0, e)) - tensionField(p - vec2(0.0, e))) / (2.0 * e);
    float d = meniscusDistance(field, gradient, THRESHOLD);
    float settle = 1.0 - smoothstep(0.0, 1.0, (uProgress - SETTLE.x) / (SETTLE.y - SETTLE.x));

    // The groove: both liquids rise from the contact line; its slope along the field's gradient.
    vec2 inward = gradient / max(length(gradient), 1e-4);
    vec2 slope = meniscusSlope(d, WIDTH) * DEPTH * settle * inward;
    vec3 n = layerNormal(slope);
    float rise = meniscusProfile(abs(d) / WIDTH);
    vec2 offset = refractionOffset(n, DEPTH * 1.6 * settle * rise, {REFRACTION_IOR_WATER:.4f});
    vec3 fresh = dispersedSample(uNewTex, uv, offset, 0.6 * settle, aspect);
    vec3 old = dispersedSample(uOldTex, uv, offset, 0.6 * settle, aspect);
    float aa = 1.2 / uItemSize.y;
    vec3 colour = mix(old, fresh, smoothstep(-aa, aa, d));

    // Light on the slopes, a dark contact line, a sheen where the surface tilts most.
    vec3 halfway = normalize(normalize(vec3(-0.45, 0.6, 1.0)) + vec3(0.0, 0.0, 1.0));
    // Only a tilted surface catches light: a flat one is each picture exactly.
    float tilt = smoothstep(0.0, 0.01, 1.0 - n.z);
    float highlight = pow(max(dot(n, halfway), 0.0), 70.0) * uGloss * settle * tilt;
    float sheen = (fresnelSchlick(n.z, 0.02) - 0.02) * uGloss * settle;
    float line = exp(-pow(d / (2.0 / uItemSize.y), 2.0)) * 0.55 * settle;
    colour = colour * (1.0 - line) + vec3(0.88, 0.94, 1.0) * (highlight * 0.9 + sheen * 1.4);
    FragColor = vec4(colour, 1.0);
}}
"""
)
