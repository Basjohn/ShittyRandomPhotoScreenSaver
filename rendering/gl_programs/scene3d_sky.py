"""Shared sky effects for 3D scenes: lattice noise, drifting clouds and nebulae.

Noise is value noise on the shared integer hash (``sceneRandom``), identical on every GPU and mirrored
exactly here on the CPU (checked on the GPU by ``tests/test_scene3d_sky.py``). The effects are pure
functions of a view ray and their parameters: a mode includes ``SCENE3D_SKY_GLSL`` and calls them from
its own sky shading, so they cost nothing where a mode does not call them and need no resources.

* ``skyNoise2``/``skyFbm2``, ``skyNoise3``/``skyFbm3`` -- smooth lattice noise and its octave sums, 0..1.
* ``skyClouds`` -- clouds on a distant sky plane, thick where drifting noise passes the coverage
  threshold, lit from the light's side by comparing the noise a step toward the light (a cheap
  self-shadow), thinning toward the horizon; premultiplied colour and alpha.
* ``skyNebula`` -- two-colour wisps of 3D noise over the sky directions; additive light.
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
        p = p * 2.03 + vec2(17.1, 9.4);
        amplitude *= 0.5;
    }
    return sum / total;
}
float skyFbm3(vec3 p, int octaves, uint seed) {
    float sum = 0.0, amplitude = 0.5, total = 0.0;
    for (int i = 0; i < octaves; ++i) {
        sum += amplitude * skyNoise3(p, seed + uint(i));
        total += amplitude;
        p = p * 2.03 + vec3(17.1, 9.4, 4.7);
        amplitude *= 0.5;
    }
    return sum / total;
}
// cloud: coverage, softness, scale, opacity (all 0..1). shade/light: the dark and lit colours.
vec4 skyClouds(vec3 ray, vec3 toLight, vec4 cloud, vec2 drift, vec3 shade, vec3 light, uint seed) {
    if (ray.y <= 0.02 || cloud.w <= 0.0 || cloud.x <= 0.0) return vec4(0.0);
    vec2 p = ray.xz / ray.y * mix(0.35, 1.6, cloud.z) + drift;
    float n = skyFbm2(p, 5, seed);
    float threshold = 1.0 - cloud.x;
    float density = smoothstep(threshold, threshold + mix(0.03, 0.4, cloud.y), n);
    if (density <= 0.0) return vec4(0.0);
    vec2 towardLight = toLight.xz / max(length(toLight.xz), 1e-4);
    float ahead = skyFbm2(p + towardLight * 0.09, 3, seed);
    float lit = clamp(0.55 + (n - ahead) * 5.0, 0.0, 1.0);
    float alpha = density * cloud.w * smoothstep(0.02, 0.2, ray.y);
    return vec4(mix(shade, light, lit) * alpha, alpha);
}
// nebula: intensity, scale (0..1). Two colours wind through each other.
vec3 skyNebula(vec3 ray, vec3 first, vec3 second, vec2 nebula, uint seed) {
    if (nebula.x <= 0.0) return vec3(0.0);
    vec3 p = ray * mix(1.2, 4.5, nebula.y);
    float body = skyFbm3(p, 4, seed);
    float mixer = skyFbm3(p * 2.1 + vec3(7.3, 1.9, 4.4), 3, seed + 11u);
    float wisp = smoothstep(0.42, 0.82, body);
    return mix(first, second, mixer) * wisp * nebula.x * (0.6 + 0.4 * mixer);
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
        x, y = x * 2.03 + 17.1, y * 2.03 + 9.4
        amplitude *= 0.5
    return total / amplitude_sum


def sky_fbm3(x: float, y: float, z: float, octaves: int, seed: int) -> float:
    """CPU mirror of ``skyFbm3``."""
    total = amplitude_sum = 0.0
    amplitude = 0.5
    for octave in range(octaves):
        total += amplitude * sky_noise3(x, y, z, seed + octave)
        amplitude_sum += amplitude
        x, y, z = x * 2.03 + 17.1, y * 2.03 + 9.4, z * 2.03 + 4.7
        amplitude *= 0.5
    return total / amplitude_sum


__all__ = ["SCENE3D_SKY_GLSL", "sky_fbm2", "sky_fbm3", "sky_noise2", "sky_noise3"]
