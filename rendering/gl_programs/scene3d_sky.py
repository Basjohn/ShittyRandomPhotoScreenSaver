"""Shared sky effects for 3D scenes: lattice noise, drifting clouds and nebulae.

Noise is value noise on the shared integer hash (``sceneRandom``), identical on every GPU and mirrored
exactly here on the CPU (checked on the GPU by ``tests/test_scene3d_sky.py``). The effects are pure
functions of a view ray and their parameters: a mode includes ``SCENE3D_SKY_GLSL`` and calls them from
its own sky shading, so they cost nothing where a mode does not call them and need no resources.

* ``skyNoise2``/``skyFbm2``, ``skyNoise3``/``skyFbm3`` -- smooth lattice noise and its octave sums, 0..1. Each
  octave is turned against the last, so the lattice's axes never line up into blocks.
* ``skyClouds`` -- clouds on a distant sky plane, thick where drifting noise passes the coverage
  threshold, lit from the light's side by comparing the noise a step toward the light (a cheap
  self-shadow), thinning toward the horizon; premultiplied colour and alpha.
* ``skyNebula`` -- emission nebulae in regions of the sky with dark space between them: warped, billowing gas
  that burns from a rim colour to a core colour toward white at its densest, bright ridged filaments, and dust
  lanes that absorb what lies behind. Additive light plus that absorption, and how deep in a nebula the ray is
  (for a caller's denser, tinted star field there).
"""
from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_HASH_GLSL, scene3d_random

_MASK32 = 0xFFFFFFFF
_X, _Y, _Z = 0x8DA6B343, 0xD8163841, 0xCB1AB31F

SCENE3D_SKY_GLSL = SCENE3D_HASH_GLSL + """
#ifndef SCENE3D_SKY_GLSL
#define SCENE3D_SKY_GLSL
float skyLattice2(ivec2 c, uint seed) {
    return sceneRandom((uint(c.x) * 0x8da6b343u) ^ (uint(c.y) * 0xd8163841u), 0u, seed);
}
float skyLattice3(ivec3 c, uint seed) {
    return sceneRandom((uint(c.x) * 0x8da6b343u) ^ (uint(c.y) * 0xd8163841u) ^ (uint(c.z) * 0xcb1ab31fu), 1u, seed);
}
float skyNoise2(vec2 p, uint seed) {
    vec2 cell = floor(p);
    vec2 f = p - cell;
    vec2 u = f * f * (3.0 - 2.0 * f);
    ivec2 c = ivec2(cell);
    float a = skyLattice2(c, seed), b = skyLattice2(c + ivec2(1, 0), seed);
    float d = skyLattice2(c + ivec2(0, 1), seed), e = skyLattice2(c + ivec2(1, 1), seed);
    return mix(mix(a, b, u.x), mix(d, e, u.x), u.y);
}
float skyNoise3(vec3 p, uint seed) {
    vec3 cell = floor(p);
    vec3 f = p - cell;
    vec3 u = f * f * (3.0 - 2.0 * f);
    ivec3 c = ivec3(cell);
    float x00 = mix(skyLattice3(c, seed), skyLattice3(c + ivec3(1, 0, 0), seed), u.x);
    float x10 = mix(skyLattice3(c + ivec3(0, 1, 0), seed), skyLattice3(c + ivec3(1, 1, 0), seed), u.x);
    float x01 = mix(skyLattice3(c + ivec3(0, 0, 1), seed), skyLattice3(c + ivec3(1, 0, 1), seed), u.x);
    float x11 = mix(skyLattice3(c + ivec3(0, 1, 1), seed), skyLattice3(c + ivec3(1, 1, 1), seed), u.x);
    return mix(mix(x00, x10, u.y), mix(x01, x11, u.y), u.z);
}
float skyFbm2(vec2 p, int octaves, uint seed) {
    float sum = 0.0, amplitude = 0.5, total = 0.0;
    for (int i = 0; i < octaves; ++i) {
        sum += amplitude * skyNoise2(p, seed + uint(i));
        total += amplitude;
        p = mat2(0.8, 0.6, -0.6, 0.8) * p * 2.03 + vec2(17.1, 9.4);
        amplitude *= 0.5;
    }
    return sum / total;
}
float skyFbm3(vec3 p, int octaves, uint seed) {
    float sum = 0.0, amplitude = 0.5, total = 0.0;
    for (int i = 0; i < octaves; ++i) {
        sum += amplitude * skyNoise3(p, seed + uint(i));
        total += amplitude;
        p = mat3(0.00, -0.80, -0.60, 0.80, 0.36, -0.48, 0.60, -0.48, 0.64) * p * 2.03 + vec3(17.1, 9.4, 4.7);
        amplitude *= 0.5;
    }
    return sum / total;
}
// cloud: coverage, softness, scale, opacity (all 0..1). shade/light: the dark and lit colours. octaves: the
// detail (5 for a visible sky; 2 is enough for a reflection, which roughness blurs anyway).
vec4 skyClouds(vec3 ray, vec3 toLight, vec4 cloud, vec2 drift, vec3 shade, vec3 light, uint seed, int octaves) {
    if (ray.y <= 0.02 || cloud.w <= 0.0 || cloud.x <= 0.0) return vec4(0.0);
    // A sky plane, flattened near the horizon so far clouds stay readable instead of shrinking to specks.
    vec2 p = ray.xz / (ray.y + 0.12) * mix(0.35, 1.6, cloud.z) + drift;
    float n = skyFbm2(p, octaves, seed);
    // Octave sums gather around 0.5: coverage spans the range they actually take.
    float threshold = mix(0.72, 0.32, cloud.x);
    float density = smoothstep(threshold, threshold + mix(0.03, 0.4, cloud.y), n);
    if (density <= 0.0) return vec4(0.0);
    vec2 towardLight = toLight.xz / max(length(toLight.xz), 1e-4);
    float ahead = skyFbm2(p + towardLight * 0.09, max(1, octaves - 2), seed);
    float lit = clamp(0.55 + (n - ahead) * 5.0, 0.0, 1.0);
    float alpha = density * cloud.w * smoothstep(0.0, 0.08, ray.y);
    return vec4(mix(shade, light, lit) * alpha, alpha);
}
// nebula: intensity, scale, filaments, dust (0..1). rim: the outer gas and its filaments; core: the dense heart,
// which burns toward white. focus: a unit direction the gas gathers around and thins away from (zero: anywhere).
// octaves: as for the clouds (5 for a visible sky). At 2 or fewer (a reflection, which roughness blurs) only the
// gas's broad body and colour are drawn: no warp, filaments or dust. Returns additive light (rgb) and the dust's
// absorption of whatever lies behind (a); region is how deep in a nebula the ray is.
vec4 skyNebula(vec3 ray, vec3 rim, vec3 core, vec4 nebula, vec3 focus, uint seed, int octaves, out float region) {
    region = 0.0;
    if (nebula.x <= 0.0) return vec4(0.0);
    vec3 p = ray * mix(0.9, 3.2, nebula.y);
    // Bodies of gas with dark space between them, ragged at their edges, rather than a fill.
    float gather = 0.3 * dot(ray, focus) - 0.12 * length(focus);
    region = smoothstep(0.47, 0.76, skyFbm3(p * 0.5 + vec3(3.1, 7.7, 1.3), min(octaves, 3), seed + 40u) + gather);
    if (region <= 0.0) return vec4(0.0);
    if (octaves <= 2) {
        float broad = smoothstep(0.32, 0.80, skyFbm3(p * 1.4, octaves, seed) * (0.35 + 0.85 * region));
        vec3 glow = mix(rim, core, smoothstep(0.30, 1.0, broad)) * broad * mix(0.85, 0.3, nebula.z);
        return vec4(glow / (1.0 + 0.6 * max(max(glow.r, glow.g), glow.b)) * nebula.x, 0.0);
    }
    // Warped so the gas billows and folds instead of sitting on the lattice.
    vec3 warp = vec3(skyNoise3(p * 1.2, seed + 3u), skyNoise3(p * 1.2 + vec3(5.2, 1.3, 2.8), seed + 4u),
                     skyNoise3(p * 1.2 + vec3(9.1, 4.4, 7.6), seed + 5u)) - 0.5;
    vec3 q = p + warp * 1.6;
    float body = smoothstep(0.32, 0.80, skyFbm3(q * 1.4, octaves, seed) * (0.35 + 0.85 * region));
    // Filaments: thin bright ridges where a second sum crosses its middle, sharper as they rise.
    float strand = 1.0 - abs(2.0 * skyFbm3(q * 2.2 + vec3(1.7), max(1, octaves - 1), seed + 7u) - 1.0);
    strand = pow(strand, mix(3.0, 14.0, nebula.z)) * smoothstep(0.0, 0.5, region);
    float dust = nebula.w <= 0.0 ? 0.0
               : smoothstep(0.46, 0.64, skyFbm3(q * 2.8 + vec3(4.3, 2.1, 8.8), 3, seed + 13u))
                 * nebula.w * smoothstep(0.0, 0.4, region);
    float heat = smoothstep(0.30, 1.0, body);
    vec3 light = mix(rim, core, heat) * body * mix(0.85, 0.3, nebula.z)
               + mix(rim, core, heat * 0.5) * strand * mix(0.25, 0.9, nebula.z)
               + mix(core, vec3(1.0), 0.4) * heat * heat * heat * 0.6;
    // Highlights roll off instead of clipping into flat plateaus.
    light /= 1.0 + 0.6 * max(max(light.r, light.g), light.b);
    return vec4(light * (1.0 - dust * 0.95) * nebula.x, dust * 0.9 * min(1.0, nebula.x * 2.0));
}
#endif
"""


def _u32(value: int) -> int:
    return value & _MASK32


def _lattice2(cx: int, cy: int, seed: int) -> float:
    return scene3d_random(_u32(cx * _X) ^ _u32(cy * _Y), 0, seed)


def _lattice3(cx: int, cy: int, cz: int, seed: int) -> float:
    return scene3d_random(_u32(cx * _X) ^ _u32(cy * _Y) ^ _u32(cz * _Z), 1, seed)


def _smooth(f: float) -> float:
    return f * f * (3.0 - 2.0 * f)


def _mix(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def sky_noise2(x: float, y: float, seed: int) -> float:
    """CPU mirror of ``skyNoise2``."""
    cx, cy = math.floor(x), math.floor(y)
    ux, uy = _smooth(x - cx), _smooth(y - cy)
    a, b = _lattice2(cx, cy, seed), _lattice2(cx + 1, cy, seed)
    d, e = _lattice2(cx, cy + 1, seed), _lattice2(cx + 1, cy + 1, seed)
    return _mix(_mix(a, b, ux), _mix(d, e, ux), uy)


def sky_noise3(x: float, y: float, z: float, seed: int) -> float:
    """CPU mirror of ``skyNoise3``."""
    cx, cy, cz = math.floor(x), math.floor(y), math.floor(z)
    ux, uy, uz = _smooth(x - cx), _smooth(y - cy), _smooth(z - cz)
    x00 = _mix(_lattice3(cx, cy, cz, seed), _lattice3(cx + 1, cy, cz, seed), ux)
    x10 = _mix(_lattice3(cx, cy + 1, cz, seed), _lattice3(cx + 1, cy + 1, cz, seed), ux)
    x01 = _mix(_lattice3(cx, cy, cz + 1, seed), _lattice3(cx + 1, cy, cz + 1, seed), ux)
    x11 = _mix(_lattice3(cx, cy + 1, cz + 1, seed), _lattice3(cx + 1, cy + 1, cz + 1, seed), ux)
    return _mix(_mix(x00, x10, uy), _mix(x01, x11, uy), uz)


def sky_fbm2(x: float, y: float, octaves: int, seed: int) -> float:
    """CPU mirror of ``skyFbm2``."""
    total = amplitude_sum = 0.0
    amplitude = 0.5
    for octave in range(octaves):
        total += amplitude * sky_noise2(x, y, seed + octave)
        amplitude_sum += amplitude
        # GLSL mat2(a, b, c, d) is column-major: columns (a, b) and (c, d).
        x, y = (0.8 * x - 0.6 * y) * 2.03 + 17.1, (0.6 * x + 0.8 * y) * 2.03 + 9.4
        amplitude *= 0.5
    return total / amplitude_sum


def sky_fbm3(x: float, y: float, z: float, octaves: int, seed: int) -> float:
    """CPU mirror of ``skyFbm3``."""
    total = amplitude_sum = 0.0
    amplitude = 0.5
    for octave in range(octaves):
        total += amplitude * sky_noise3(x, y, z, seed + octave)
        amplitude_sum += amplitude
        x, y, z = ((0.00 * x + 0.80 * y + 0.60 * z) * 2.03 + 17.1,
                   (-0.80 * x + 0.36 * y - 0.48 * z) * 2.03 + 9.4,
                   (-0.60 * x - 0.48 * y + 0.64 * z) * 2.03 + 4.7)
        amplitude *= 0.5
    return total / amplitude_sum


__all__ = ["SCENE3D_SKY_GLSL", "sky_fbm2", "sky_fbm3", "sky_noise2", "sky_noise3"]
