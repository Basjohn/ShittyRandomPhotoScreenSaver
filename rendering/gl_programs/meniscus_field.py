"""Meniscus fields: a shared organic-boundary helper for liquid effects (Surface Tension Merge
first; Capillary Bloom is meant to reuse it). Import-safe GLSL and CPU mirrors, no GL.

A field is a sum of compactly supported pool kernels (Wyvill's ``(1 - (d / r)^2)^3``): where it
passes a threshold, one liquid has taken the picture. Summed kernels bridge into necks as pools
near each other, the way surface tension merges drops, and the boundary stays smooth. From the
field and its gradient (central differences) comes a signed distance to the boundary
(``(field - threshold) / |gradient|``, good near it), and from that a meniscus: both liquids
rise from the contact line over ``width`` (``sqrt(1 - (1 - x)^2)``), a groove whose slopes bend
each side's picture toward the line and catch the light.

* ``poolKernel(p, centre, radius)``: one pool's contribution, 0 beyond its radius;
* ``meniscusDistance(field, gradient, threshold)``: signed distance, positive inside;
* ``meniscusProfile(x)`` and ``meniscusSlope(distance, width)``: the groove's height (0 on the
  line, 1 from ``width`` on) and its slope along the distance.
"""

from __future__ import annotations

import math

MENISCUS_FIELD_GLSL = """
float poolKernel(vec2 p, vec2 centre, float radius) {
    if (radius <= 0.0) return 0.0;
    vec2 d = p - centre;
    float q = dot(d, d) / (radius * radius);
    if (q >= 1.0) return 0.0;
    float k = 1.0 - q;
    return k * k * k;
}
float meniscusDistance(float field, vec2 gradient, float threshold) {
    return (field - threshold) / max(length(gradient), 1e-4);
}
float meniscusProfile(float x) {
    x = clamp(x, 0.0, 1.0);
    return sqrt(max(0.0, 1.0 - (1.0 - x) * (1.0 - x)));
}
// d(height)/d(distance) of the groove at signed distance d: rising away from the line on both sides.
float meniscusSlope(float d, float width) {
    float x = clamp(abs(d) / width, 0.0, 1.0);
    if (x >= 1.0) return 0.0;
    float profile = max(meniscusProfile(x), 0.05);
    return sign(d) * (1.0 - x) / profile / width;
}
"""


def pool_kernel(p: tuple[float, float], centre: tuple[float, float], radius: float) -> float:
    """CPU mirror of ``poolKernel``."""
    if radius <= 0.0:
        return 0.0
    q = ((p[0] - centre[0]) ** 2 + (p[1] - centre[1]) ** 2) / (radius * radius)
    return 0.0 if q >= 1.0 else (1.0 - q) ** 3


def meniscus_distance(field: float, gradient: tuple[float, float], threshold: float) -> float:
    """CPU mirror of ``meniscusDistance``."""
    return (field - threshold) / max(math.hypot(*gradient), 1e-4)


def meniscus_profile(x: float) -> float:
    """CPU mirror of ``meniscusProfile``."""
    x = max(0.0, min(1.0, x))
    return math.sqrt(max(0.0, 1.0 - (1.0 - x) ** 2))


def meniscus_slope(d: float, width: float) -> float:
    """CPU mirror of ``meniscusSlope``."""
    x = max(0.0, min(1.0, abs(d) / width))
    if x >= 1.0:
        return 0.0
    return math.copysign(1.0, d) * (1.0 - x) / max(meniscus_profile(x), 0.05) / width if d else 0.0


def pool_kernel_radius_at(value: float) -> float:
    """Where a pool's kernel falls to ``value``, as a share of its radius."""
    return math.sqrt(1.0 - value ** (1.0 / 3.0))
