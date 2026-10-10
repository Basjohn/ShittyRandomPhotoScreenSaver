"""Vortex flow: a shared, seeded swirl of the plane for liquid effects (Surface Tension Merge,
Capillary Bloom, Liquid Lens). Import-safe: GLSL text and CPU mirrors, no GL.

Proved by Ink Bloom (retired 2026-10-10). Three seeded vortices of alternating spin, each turning
the plane around its centre by an angle that falls off as a Gaussian of the distance: a ring
turns rigidly, so the flow keeps area (dye neither thins nor piles up) and has an exact inverse
(the same vortices in reverse order, turning back), for sampling a picture where the flow
carried it from. ``strength`` is the twist at a vortex's centre, in radians; 0 is the identity.
Coordinates are centred, picture heights (x times the aspect); the vortices sit within 0.3 of
the middle.
"""

from __future__ import annotations

import math

VORTEX_COUNT = 3

VORTEX_FLOW_GLSL = f"""
vec2 vortexCentre(int i, float seed) {{
    float a = mod(seed, 997.0) * 0.021 + float(i) * 2.094;
    return vec2(cos(a), sin(a)) * (0.16 + 0.06 * float(i));
}}
vec2 vortexTurn(vec2 p, int i, float seed, float strength) {{
    vec2 centre = vortexCentre(i, seed), q = p - centre;
    float twist = strength * exp(-dot(q, q) * (6.0 + 3.0 * float(i))) * (i == 1 ? -1.0 : 1.0);
    float c = cos(twist), s = sin(twist);
    return centre + vec2(c * q.x - s * q.y, s * q.x + c * q.y);
}}
// Where the flow carries p.
vec2 vortexFlow(vec2 p, float seed, float strength) {{
    for (int i = 0; i < {VORTEX_COUNT}; ++i) p = vortexTurn(p, i, seed, strength);
    return p;
}}
// Where the flow carried p from: the exact inverse of vortexFlow.
vec2 vortexFlowInverse(vec2 p, float seed, float strength) {{
    for (int i = {VORTEX_COUNT - 1}; i >= 0; --i) p = vortexTurn(p, i, seed, -strength);
    return p;
}}
"""


def _centre(i: int, seed: float) -> tuple[float, float]:
    a = math.fmod(seed, 997.0) * 0.021 + i * 2.094
    radius = 0.16 + 0.06 * i
    return math.cos(a) * radius, math.sin(a) * radius


def _turn(p: tuple[float, float], i: int, seed: float, strength: float) -> tuple[float, float]:
    cx, cy = _centre(i, seed)
    qx, qy = p[0] - cx, p[1] - cy
    twist = strength * math.exp(-(qx * qx + qy * qy) * (6.0 + 3.0 * i)) * (-1.0 if i == 1 else 1.0)
    c, s = math.cos(twist), math.sin(twist)
    return cx + c * qx - s * qy, cy + s * qx + c * qy


def vortex_flow(p: tuple[float, float], seed: float, strength: float) -> tuple[float, float]:
    """CPU mirror of ``vortexFlow``."""
    for i in range(VORTEX_COUNT):
        p = _turn(p, i, seed, strength)
    return p


def vortex_flow_inverse(p: tuple[float, float], seed: float, strength: float) -> tuple[float, float]:
    """CPU mirror of ``vortexFlowInverse``."""
    for i in reversed(range(VORTEX_COUNT)):
        p = _turn(p, i, seed, -strength)
    return p
