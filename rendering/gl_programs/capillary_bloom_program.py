"""Capillary Bloom: shaders and CPU mirrors (loaded only when Capillary Bloom renders).

The new picture spreads through the old like dye through wet paper. A few seeded sources start
one after another; the dye reaches each point along the cheapest way through the paper's fibres,
a geodesic arrival map (``rendering/quick/scene3d/propagation_field.py``) over the shared fibre
cost (``rendering/gl_programs/capillary_field.py``: thin channels along a grain cost far less than
the paper between them), so fronts race along channels in branching tendrils, join and bloom out
to fill the gaps. Ahead of a front the paper darkens, wet; on the front, pigment gathers into a
darker line; behind it the dye first shows the new picture stained into the paper, then clears to
the new picture itself. The wet edge is a shallow meniscus (``meniscusSlope``) bending both
pictures a little through the shared refraction helpers.

The reach grows as ``extent * (t / CAPILLARY_FILL)^CAPILLARY_GROWTH``, where ``extent`` is the
field's own largest arrival (reduced on the GPU), so the last point is reached exactly at
``CAPILLARY_FILL`` whatever the layout; everything settles to the new picture exactly by
``CAPILLARY_SETTLE[1]``.
"""

from __future__ import annotations

import math
import random

from rendering.gl_programs.capillary_field import CAPILLARY_COST, CAPILLARY_FIELD_GLSL
from rendering.gl_programs.meniscus_field import MENISCUS_FIELD_GLSL
from rendering.gl_programs.refraction import REFRACTION_GLSL, REFRACTION_IOR_WATER
from rendering.gl_programs.scene3d import SCENE3D_GLSL

CAPILLARY_SOURCES_RANGE = (1, 6)
CAPILLARY_BIRTHS = (0.0, 0.18)
CAPILLARY_FILL = 0.8
CAPILLARY_GROWTH = 0.8           # reach grows as elapsed time to this power: a quick bloom that slows
CAPILLARY_SETTLE = (0.86, 0.94)
CAPILLARY_WARP = 0.012           # picture heights the arrival map is read off by, for organic edges
CAPILLARY_FEATHER = 0.006        # fine-fibre roughness of the front, cost units
CAPILLARY_FLOOD = 0.03           # after CAPILLARY_FILL, anything the interpolation left dry blooms in this fast


def capillary_sources(seed: int, count: int, aspect: float) -> tuple[list[tuple[float, float, float]], tuple[float, float]]:
    """([(x, y, head start in cost units)], grain direction): sources spread across the picture,
    picture heights, centred, y up; a later source starts behind by its birth times the costliest
    crossing of the picture."""
    rng = random.Random(seed ^ 0xCA91)
    crossing = math.hypot(aspect, 1.0) * CAPILLARY_COST
    sources = []
    for i in range(count):
        # One per vertical band, so several sources spread across the picture.
        x = ((i + rng.uniform(0.2, 0.8)) / count - 0.5) * aspect * 0.85
        y = rng.uniform(-0.38, 0.38)
        birth = rng.uniform(*CAPILLARY_BIRTHS) if i else 0.0
        sources.append((x, y, birth * crossing / CAPILLARY_FILL))
    angle = rng.uniform(0.0, math.pi)
    return sources, (math.cos(angle), math.sin(angle))


def capillary_reach(extent: float, progress: float) -> float:
    """CPU mirror of the dye's reach at ``progress`` (cost units)."""
    return extent * max(0.0, min(1.0, progress / CAPILLARY_FILL)) ** CAPILLARY_GROWTH


def capillary_settle(progress: float) -> float:
    x = max(0.0, min(1.0, (progress - CAPILLARY_SETTLE[0]) / (CAPILLARY_SETTLE[1] - CAPILLARY_SETTLE[0])))
    return 1.0 - x * x * (3.0 - 2.0 * x)


# The paper's cost for the propagation field (its seed stage), with the fibre helpers it needs.
CAPILLARY_COST_GLSL = (SCENE3D_GLSL + CAPILLARY_FIELD_GLSL
                       + "uniform vec2 uGrain;\nuniform float uFibres;\nuniform float uSeed;\n"
                       "float propagationCost(vec2 p) {\n"
                       "    return capillaryCost(fibreChannels(p, uGrain, uint(uSeed)), uFibres);\n"
                       "}\n")

CAPILLARY_BLOOM_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform sampler2D uArrival;\nuniform sampler2D uExtent;\n"
    "uniform vec2 uItemSize;\nuniform float uProgress;\nuniform float uSeed;\n"
    + SCENE3D_GLSL + CAPILLARY_FIELD_GLSL + MENISCUS_FIELD_GLSL + REFRACTION_GLSL
    + f"""
const float WARP = {CAPILLARY_WARP:.6f};
const float FEATHER = {CAPILLARY_FEATHER:.6f};
const vec2 SETTLE = vec2({CAPILLARY_SETTLE[0]:.6f}, {CAPILLARY_SETTLE[1]:.6f});
const float FILL = {CAPILLARY_FILL:.6f};
const float FLOOD = {CAPILLARY_FLOOD:.6f};
const float GROWTH = {CAPILLARY_GROWTH:.6f};

vec3 saturate3(vec3 c, float amount) {{
    float grey = dot(c, vec3(0.299, 0.587, 0.114));
    return clamp(mix(vec3(grey), c, amount), 0.0, 1.0);
}}

void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float aspect = uItemSize.x / uItemSize.y;
    vec2 p = vec2((uv.x - 0.5) * aspect, 0.5 - uv.y);
    uint seed = uint(uSeed);
    float settle = 1.0 - smoothstep(0.0, 1.0, (uProgress - SETTLE.x) / (SETTLE.y - SETTLE.x));
    // How far behind the front this point lies (cost units; negative while still dry), read off the
    // arrival map a little warped, roughened by fine fibres.
    vec2 warp = WARP * 2.0 * vec2(fibreNoise(p * 9.0, 3u, seed) - 0.5, fibreNoise(p * 9.0 + 9.7, 4u, seed) - 0.5);
    float arrival = texture(uArrival, uv + vec2(warp.x / aspect, -warp.y)).r
                  + FEATHER * 2.0 * (fibreNoise(p * 70.0, 5u, seed) - 0.5);
    float extent = texelFetch(uExtent, ivec2(0), 0).r;
    float g = extent * pow(clamp(uProgress / FILL, 0.0, 1.0), GROWTH) - arrival;
    g = max(g, (uProgress - FILL) / FLOOD * 0.05);
    // Screen-space derivatives give the front's gradient for one evaluation per pixel.
    vec2 gradient = vec2(dFdx(g), -dFdy(g)) * uItemSize.y;
    float d = g / max(length(gradient), 1e-3);                     // picture heights behind the front

    // The wet edge: a shallow meniscus that bends both pictures a little.
    vec2 slope = meniscusSlope(d, 0.02) * 0.006 * settle * gradient / max(length(gradient), 1e-3);
    vec2 offset = refractionOffset(layerNormal(slope), 0.012 * settle, {REFRACTION_IOR_WATER:.4f});
    vec3 old = dispersedSample(uOldTex, uv, offset, 0.0, aspect);
    vec3 fresh = dispersedSample(uNewTex, uv, offset, 0.0, aspect);

    float aa = 1.2 / uItemSize.y;
    float dyed = smoothstep(-aa, aa, d);
    float wet = exp(-max(-d, 0.0) / 0.03) * (1.0 - dyed);
    float rim = exp(-pow(d / 0.006, 2.0)) * dyed;
    float clean = smoothstep(0.0, 0.14, d);
    vec3 paper = old * (1.0 - 0.2 * wet * settle);
    // Fresh dye shows the new picture stained into the paper, richer at first; then it clears.
    vec3 stained = saturate3(fresh * mix(vec3(1.0), old * 1.3, 0.45), 1.35);
    vec3 dye = mix(stained, fresh, clean);
    vec3 colour = mix(paper, dye, dyed) * (1.0 - 0.38 * rim * settle);
    FragColor = vec4(mix(fresh, colour, settle), 1.0);
}}
"""
)
