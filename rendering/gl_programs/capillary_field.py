"""Capillary fields: a shared organic-propagation helper (GLSL plus CPU mirrors, no GL) for effects
where something spreads through a material faster along its fibres (Capillary Bloom first; it pairs
with the meniscus field, rendering/gl_programs/meniscus_field.py, for the wet edge).

The material is a fibre field: value noise on the exact integer lattice hash (``sceneRandom``,
identical on every GPU), stretched along a grain direction and ridged (``1 - |2n - 1|``) over three
octaves, so it is near 1 along thin connected channels and low between them. Spreading costs less
along channels: ``capillaryCost`` falls from ``CAPILLARY_COST`` on bare paper toward
``CAPILLARY_COST_MIN`` along a full channel, as the cube of what the channel leaves (a contrast of
several times, which is what makes fronts finger along channels rather than swell round). A
geodesic arrival map over it (rendering/quick/scene3d/propagation_field.py) gives the true
cheapest way; ``capillaryArrival`` is the straight-line estimate for per-pixel use.

* ``fibreNoise(p, salt, seed)``: smooth value noise, 0..1;
* ``fibreChannels(p, grain, seed)``: the ridged, grain-stretched channel field, 0..1;
* ``capillaryCost(channels, fibres)``: the cost per picture height at a point;
* ``capillaryArrival(p, source, channels, fibres)``: the cost-weighted distance from ``source``.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import scene3d_random

CAPILLARY_COST = 2.0             # cost per picture height through bare paper
CAPILLARY_COST_MIN = 0.25        # along a full channel at fibres 1
CAPILLARY_SCALE = 7.0            # channels per picture height (coarsest octave)
CAPILLARY_STRETCH = 5.0          # how much longer than wide the channels run along the grain

CAPILLARY_FIELD_GLSL = f"""
const float CAPILLARY_COST = {CAPILLARY_COST:.6f};
const float CAPILLARY_COST_MIN = {CAPILLARY_COST_MIN:.6f};
const float CAPILLARY_SCALE = {CAPILLARY_SCALE:.6f};
const float CAPILLARY_STRETCH = {CAPILLARY_STRETCH:.6f};
float fibreLattice(ivec2 cell, uint salt, uint seed) {{
    return sceneRandom(uint(cell.x) * 73856093u ^ uint(cell.y) * 19349663u, salt, seed);
}}
float fibreNoise(vec2 p, uint salt, uint seed) {{
    vec2 i = floor(p), f = p - i;
    vec2 w = f * f * (3.0 - 2.0 * f);
    ivec2 c = ivec2(i);
    float a = fibreLattice(c, salt, seed), b = fibreLattice(c + ivec2(1, 0), salt, seed);
    float d = fibreLattice(c + ivec2(0, 1), salt, seed), e = fibreLattice(c + ivec2(1, 1), salt, seed);
    return mix(mix(a, b, w.x), mix(d, e, w.x), w.y);
}}
float fibreChannelsOctaves(vec2 p, vec2 grain, uint seed, int octaves) {{
    vec2 across = vec2(-grain.y, grain.x);
    vec2 q = vec2(dot(p, grain) / CAPILLARY_STRETCH, dot(p, across)) * CAPILLARY_SCALE;
    float sum = 0.0, weight = 0.0, amplitude = 1.0;
    for (int octave = 0; octave < octaves; ++octave) {{
        float n = fibreNoise(q, uint(octave) + 11u, seed);
        sum += amplitude * (1.0 - abs(2.0 * n - 1.0));
        weight += amplitude;
        amplitude *= 0.5;
        q = q * 2.03 + vec2(17.1, 5.3);
    }}
    float ridge = sum / weight;
    return ridge * ridge;
}}
float fibreChannels(vec2 p, vec2 grain, uint seed) {{ return fibreChannelsOctaves(p, grain, seed, 3); }}
float capillaryCost(float channels, float fibres) {{
    float left = 1.0 - clamp(fibres * channels, 0.0, 1.0);
    return CAPILLARY_COST_MIN + (CAPILLARY_COST - CAPILLARY_COST_MIN) * left * left * left;
}}
float capillaryArrival(vec2 p, vec2 source, float channels, float fibres) {{
    return distance(p, source) * capillaryCost(channels, fibres);
}}
"""


def _lattice(cx: int, cy: int, salt: int, seed: int) -> float:
    key = ((cx * 73856093) & 0xFFFFFFFF) ^ ((cy * 19349663) & 0xFFFFFFFF)
    return scene3d_random(key, salt, seed)


def fibre_noise(p: tuple[float, float], salt: int, seed: int) -> float:
    """CPU mirror of ``fibreNoise``."""
    ix, iy = math.floor(p[0]), math.floor(p[1])
    fx, fy = p[0] - ix, p[1] - iy
    wx, wy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _lattice(ix, iy, salt, seed), _lattice(ix + 1, iy, salt, seed)
    d, e = _lattice(ix, iy + 1, salt, seed), _lattice(ix + 1, iy + 1, salt, seed)
    return (a + (b - a) * wx) + ((d + (e - d) * wx) - (a + (b - a) * wx)) * wy


def fibre_channels(p: tuple[float, float], grain: tuple[float, float], seed: int, octaves: int = 3) -> float:
    """CPU mirror of ``fibreChannels`` (``fibreChannelsOctaves`` for other octave counts)."""
    across = (-grain[1], grain[0])
    q = ((p[0] * grain[0] + p[1] * grain[1]) / CAPILLARY_STRETCH * CAPILLARY_SCALE,
         (p[0] * across[0] + p[1] * across[1]) * CAPILLARY_SCALE)
    total = weight = 0.0
    amplitude = 1.0
    for octave in range(octaves):
        n = fibre_noise(q, octave + 11, seed)
        total += amplitude * (1.0 - abs(2.0 * n - 1.0))
        weight += amplitude
        amplitude *= 0.5
        q = (q[0] * 2.03 + 17.1, q[1] * 2.03 + 5.3)
    ridge = total / weight
    return ridge * ridge


def capillary_cost(channels: float, fibres: float) -> float:
    """CPU mirror of ``capillaryCost``."""
    left = 1.0 - max(0.0, min(1.0, fibres * channels))
    return CAPILLARY_COST_MIN + (CAPILLARY_COST - CAPILLARY_COST_MIN) * left ** 3


def capillary_arrival(p, source, channels: float, fibres: float) -> float:
    """CPU mirror of ``capillaryArrival``."""
    return math.dist(p, source) * capillary_cost(channels, fibres)
