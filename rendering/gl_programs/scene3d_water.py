"""Underwater light for 3D scenes: ripples, the surface seen from below, caustics and the water's own colour.
Import-safe GLSL plus CPU mirrors (no GL), on the shared integer hash.

* ``waterWaves(p, t, choppiness)``: the surface height at ``p`` (surface units) and its gradient (``vec3(h, dh/dx,
  dh/dz)``), a sum of eight directional waves spread by the golden angle, wavelengths falling geometrically from 1
  to about 0.12, each travelling at deep-water speed (sqrt of its wavenumber), so the pattern never repeats visibly
  and short ripples outrun long swells. ``waterNormal`` turns it into the surface normal (y up).
* ``waterCaustics(p, t)``: the bright, shifting network light draws on the bottom: the edges between moving Voronoi
  cells (``F2 - F1`` sharpened), two layers at different scales and speeds; 0..1.
* ``waterSurfaceFromBelow(ray, normal, sun, sky, deep, sunPower)``: what a ray rising to the surface sees. Inside
  Snell's window (incidence below the critical angle, about 48.8 degrees) the sky and a refracted sun glare come
  through, dimmed by the transmission; outside it, the surface is a mirror of the deep below (total internal
  reflection).
* ``waterWindow(ray, normal, skyward)``: the share of light Snell's window lets through along a rising ray (0
  outside the window, where the surface mirrors the deep) and the direction it continues above the water, so a
  consumer lights the window with its own sky (brighter toward the zenith, its sun); ``waterSurfaceFromBelow`` is
  the same with one flat sky colour.
* ``waterSunBelow(sun)``: the direction toward the sun as seen from under the water (bent toward the vertical).
* ``waterMedium(colour, distance, absorption, scatter)``: light crossing ``distance`` of water: absorbed per channel
  (red first) and replaced by the water's in-scattered colour.
"""
from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_HASH_GLSL, scene3d_random

_GOLDEN = 2.39996322972865332
WATER_IOR = 1.33

SCENE3D_WATER_GLSL = SCENE3D_HASH_GLSL + """
#ifndef SCENE3D_WATER_GLSL
#define SCENE3D_WATER_GLSL
vec3 waterWaves(vec2 p, float t, float choppiness) {
    vec3 sum = vec3(0.0);
    float wavelength = 1.0;
    for (int i = 0; i < 8; ++i) {
        float angle = float(i) * 2.39996322972865332;
        vec2 direction = vec2(cos(angle), sin(angle));
        float k = 6.28318530718 / wavelength;
        float amplitude = wavelength * 0.035 * choppiness;
        float phase = k * dot(direction, p) - sqrt(9.81 * k) * t;
        sum += vec3(amplitude * sin(phase), amplitude * k * cos(phase) * direction);
        wavelength *= 0.74;
    }
    return sum;
}
vec3 waterNormal(vec2 p, float t, float choppiness) {
    vec3 wave = waterWaves(p, t, choppiness);
    return normalize(vec3(-wave.y, 1.0, -wave.z));
}
vec2 waterCellPoint(ivec2 cell, float t, uint seed) {
    uint key = (uint(cell.x) * 0x8da6b343u) ^ (uint(cell.y) * 0xd8163841u);
    vec2 base = vec2(sceneRandom(key, 2u, seed), sceneRandom(key, 3u, seed));
    float speed = 0.6 + 0.8 * sceneRandom(key, 4u, seed);
    float turn = 6.28318530718 * sceneRandom(key, 5u, seed);
    return vec2(cell) + 0.5 + 0.38 * vec2(sin(t * speed + turn + base.x * 6.28318530718),
                                          cos(t * speed * 0.83 + turn + base.y * 6.28318530718));
}
float waterCellEdge(vec2 p, float t, uint seed) {
    ivec2 cell = ivec2(floor(p));
    float f1 = 9.0, f2 = 9.0;
    for (int y = -1; y <= 1; ++y)
        for (int x = -1; x <= 1; ++x) {
            float d = distance(p, waterCellPoint(cell + ivec2(x, y), t, seed));
            if (d < f1) { f2 = f1; f1 = d; } else if (d < f2) { f2 = d; }
        }
    return f2 - f1;
}
float waterCaustics(vec2 p, float t) {
    float coarse = exp(-waterCellEdge(p * 1.0, t * 0.9, 61u) * 9.0);
    float fine = exp(-waterCellEdge(p * 2.3 + vec2(3.7, 1.1), t * 1.4, 67u) * 11.0);
    return clamp(0.65 * coarse + 0.45 * fine * (0.4 + 0.6 * coarse), 0.0, 1.0);
}
vec3 waterSurfaceFromBelow(vec3 ray, vec3 normal, vec3 sun, vec3 sky, vec3 deep, float sunPower) {
    // The surface normal points up; a rising ray meets it from below.
    vec3 down = -normal;
    vec3 out_ = refract(ray, down, 1.33);
    float cosI = clamp(dot(-ray, down), 0.0, 1.0);
    if (dot(out_, out_) < 1e-8) return deep;           // outside Snell's window: a mirror of the deep
    float sinT2 = 1.33 * 1.33 * (1.0 - cosI * cosI);
    float cosT = sqrt(max(1.0 - sinT2, 0.0));
    float rs = (1.33 * cosI - cosT) / max(1.33 * cosI + cosT, 1e-6);
    float rp = (cosI - 1.33 * cosT) / max(cosI + 1.33 * cosT, 1e-6);
    float transmission = 1.0 - 0.5 * (rs * rs + rp * rp);
    float glare = pow(max(dot(normalize(out_), sun), 0.0), 220.0) * sunPower;
    return mix(deep, sky + vec3(glare), transmission);
}
float waterWindow(vec3 ray, vec3 normal, out vec3 skyward) {
    vec3 out_ = refract(ray, -normal, 1.33);
    skyward = vec3(0.0, 1.0, 0.0);
    if (dot(out_, out_) < 1e-8) return 0.0;
    skyward = normalize(out_);
    float cosI = clamp(dot(ray, normal), 0.0, 1.0);
    float sinT2 = 1.33 * 1.33 * (1.0 - cosI * cosI);
    float cosT = sqrt(max(1.0 - sinT2, 0.0));
    float rs = (1.33 * cosI - cosT) / max(1.33 * cosI + cosT, 1e-6);
    float rp = (cosI - 1.33 * cosT) / max(cosI + 1.33 * cosT, 1e-6);
    return 1.0 - 0.5 * (rs * rs + rp * rp);
}
vec3 waterSunBelow(vec3 sun) {
    return normalize(-refract(-normalize(sun), vec3(0.0, 1.0, 0.0), 1.0 / 1.33));
}
vec3 waterMedium(vec3 colour, float distance_, vec3 absorption, vec3 scatter) {
    vec3 kept = exp(-absorption * max(distance_, 0.0));
    return colour * kept + scatter * (1.0 - kept);
}
#endif
"""


def water_waves(x: float, z: float, t: float, choppiness: float) -> tuple[float, float, float]:
    """CPU mirror of ``waterWaves``."""
    height = gx = gz = 0.0
    wavelength = 1.0
    for i in range(8):
        angle = i * _GOLDEN
        dx, dz = math.cos(angle), math.sin(angle)
        k = 2.0 * math.pi / wavelength
        amplitude = wavelength * 0.035 * choppiness
        phase = k * (dx * x + dz * z) - math.sqrt(9.81 * k) * t
        height += amplitude * math.sin(phase)
        gx += amplitude * k * math.cos(phase) * dx
        gz += amplitude * k * math.cos(phase) * dz
        wavelength *= 0.74
    return height, gx, gz


def _cell_point(cx: int, cy: int, t: float, seed: int) -> tuple[float, float]:
    key = ((cx * 0x8DA6B343) & 0xFFFFFFFF) ^ ((cy * 0xD8163841) & 0xFFFFFFFF)
    bx, by = scene3d_random(key, 2, seed), scene3d_random(key, 3, seed)
    speed = 0.6 + 0.8 * scene3d_random(key, 4, seed)
    turn = 2.0 * math.pi * scene3d_random(key, 5, seed)
    return (cx + 0.5 + 0.38 * math.sin(t * speed + turn + bx * 2.0 * math.pi),
            cy + 0.5 + 0.38 * math.cos(t * speed * 0.83 + turn + by * 2.0 * math.pi))


def _cell_edge(x: float, y: float, t: float, seed: int) -> float:
    cx, cy = math.floor(x), math.floor(y)
    f1 = f2 = 9.0
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            px, py = _cell_point(cx + ox, cy + oy, t, seed)
            d = math.hypot(x - px, y - py)
            if d < f1:
                f1, f2 = d, f1
            elif d < f2:
                f2 = d
    return f2 - f1


def water_caustics(x: float, y: float, t: float) -> float:
    """CPU mirror of ``waterCaustics``."""
    coarse = math.exp(-_cell_edge(x, y, t * 0.9, 61) * 9.0)
    fine = math.exp(-_cell_edge(x * 2.3 + 3.7, y * 2.3 + 1.1, t * 1.4, 67) * 11.0)
    return max(0.0, min(1.0, 0.65 * coarse + 0.45 * fine * (0.4 + 0.6 * coarse)))


def water_sun_below(sun: tuple[float, float, float]) -> tuple[float, float, float]:
    """CPU mirror of ``waterSunBelow``."""
    length = math.sqrt(sum(c * c for c in sun))
    ix, iy, iz = (-c / length for c in sun)
    eta = 1.0 / WATER_IOR
    cos_i = -iy
    k = 1.0 - eta * eta * (1.0 - cos_i * cos_i)
    bx, by, bz = eta * ix, eta * iy + (eta * cos_i - math.sqrt(k)), eta * iz
    norm = math.sqrt(bx * bx + by * by + bz * bz)
    return -bx / norm, -by / norm, -bz / norm


__all__ = ["SCENE3D_WATER_GLSL", "WATER_IOR", "water_caustics", "water_sun_below", "water_waves"]
