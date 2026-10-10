"""Analog-signal distortion primitives: GLSL plus CPU mirrors (import-safe, no GL).

Shared building blocks for effects that imitate a degraded analog video signal (VHS Distortion first;
Chromatic Shear or a CRT/broadcast look can reuse them). Each is a pure function of screen position,
a signal time and a seed, so an effect owns no state, history or texture for them:

* ``signalRandom`` -- the exact integer lattice hash (identical to ``sceneRandom``, R-94);
* ``signalNoise1`` -- smooth value noise along one axis;
* ``signalLineJitter`` -- per-scanline horizontal jitter that changes every field;
* ``signalTear`` -- tearing bands that drift and churn down the picture;
* ``signalWobble`` -- slow horizontal sway of the lines (tape stretch);
* ``signalBleed`` -- one picture sample as a band-limited video signal: sharp luma with ringing,
  chroma delayed and smeared along the line (the colour fringing of composite video);
* ``signalScanline``, ``signalSnow``, ``signalDropout`` -- line structure, snow and oxide dropouts.

Every function returns its neutral value (no displacement, the exact sample, no snow) when its
strength is zero, so callers keep exact endpoints by scaling strengths to zero.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import scene3d_random

# Luma weights (ITU-R BT.601) and the YIQ chroma axes used by the bleed.
SIGNAL_LUMA = (0.299, 0.587, 0.114)
# Smear weights across the chroma taps (sum to 1).
SIGNAL_CHROMA_TAPS = (0.1, 0.2, 0.4, 0.2, 0.1)

ANALOG_SIGNAL_GLSL = f"""
uint signalMix(uint x) {{
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}}
float signalRandom(uint key, uint salt, uint seed) {{
    return float(signalMix(key * 0x9e3779b9u ^ signalMix(seed * 0x85ebca6bu + salt))) * (1.0 / 4294967295.0);
}}
float signalNoise1(float x, uint salt, uint seed) {{
    float i = floor(x), f = x - i;
    uint k = uint(int(i) + 1048576);
    f = f * f * (3.0 - 2.0 * f);
    return mix(signalRandom(k, salt, seed), signalRandom(k + 1u, salt, seed), f);
}}
// Per-scanline horizontal jitter in [-0.5, 0.5], new every field.
float signalLineJitter(float line, float field, uint seed) {{
    return signalRandom(uint(line) + uint(field) * 7919u, 31u, seed) - 0.5;
}}
// Tearing bands in [0, 1]: two drifting noise octaves down the picture, thresholded so most lines
// are clean. ``threshold`` lowers to let more bands through.
float signalTear(float y, float time, float threshold, uint seed) {{
    float n = 0.65 * signalNoise1(y * 7.0 + time * 0.9, 32u, seed)
            + 0.35 * signalNoise1(y * 23.0 - time * 2.3, 33u, seed);
    return smoothstep(threshold, threshold + 0.12, n);
}}
// Slow horizontal sway of the lines in [-1, 1].
float signalWobble(float y, float time) {{
    return 0.75 * sin(y * 7.0 + time * 1.7) + 0.25 * sin(y * 31.0 - time * 5.3);
}}
vec3 signalYiq(vec3 c) {{
    return vec3(dot(c, vec3({SIGNAL_LUMA[0]}, {SIGNAL_LUMA[1]}, {SIGNAL_LUMA[2]})),
                dot(c, vec3(0.595716, -0.274453, -0.321263)),
                dot(c, vec3(0.211456, -0.522591, 0.311135)));
}}
vec3 signalRgb(vec3 yiq) {{
    return vec3(dot(yiq, vec3(1.0, 0.9563, 0.6210)),
                dot(yiq, vec3(1.0, -0.2721, -0.6474)),
                dot(yiq, vec3(1.0, -1.1070, 1.7046)));
}}
// One sample of ``tex`` at ``uv`` as a band-limited video signal: luma stays sharp but rings
// (``sharpen`` overshoots it against the smeared neighbourhood); chroma is delayed by ``shift`` and
// smeared over five taps ``spread`` apart along the line; ``split`` misregisters red and blue to
// either side (the red/cyan fringes of a worn signal). All zero: the exact sample.
vec3 signalBleed(sampler2D tex, vec2 uv, float shift, float spread, float sharpen, float split) {{
    vec3 centre = texture(tex, uv).rgb;
    if (shift == 0.0 && spread == 0.0 && sharpen == 0.0 && split == 0.0) {{
        return centre;
    }}
    if (split != 0.0) {{
        centre = vec3(texture(tex, uv + vec2(split, 0.0)).r, centre.g, texture(tex, uv - vec2(split, 0.0)).b);
    }}
    const float W[5] = float[5]({", ".join(f"{w:.3f}" for w in SIGNAL_CHROMA_TAPS)});
    vec2 chroma = vec2(0.0);
    float around = 0.0;
    for (int k = 0; k < 5; ++k) {{
        vec3 yiq = signalYiq(texture(tex, uv + vec2(shift + float(k - 2) * spread, 0.0)).rgb);
        chroma += yiq.yz * W[k];
        around += yiq.x * W[k];
    }}
    float luma = signalYiq(centre).x;
    return signalRgb(vec3(luma + sharpen * (luma - around), chroma));
}}
// Line structure in [0, 1] (1 between lines) for a position in pixels and a line period in pixels.
float signalScanline(float pixelY, float period) {{
    return 0.5 + 0.5 * cos(6.28318530718 * pixelY / period);
}}
// Snow in [-0.5, 0.5] for one signal cell (column, line), new every field.
float signalSnow(vec2 cell, float field, uint seed) {{
    return signalRandom(uint(cell.x) * 92821u + uint(cell.y) * 4099u + uint(field) * 131u, 34u, seed) - 0.5;
}}
// An oxide dropout on ``line`` this field, with probability ``rate``: a short horizontal streak
// with a hard head and a fading tail, mostly dark with coloured grain, sometimes white.
// Returns colour and coverage (0 where there is none).
vec4 signalDropout(float x, float line, float field, float rate, uint seed) {{
    uint key = uint(line) * 4099u + uint(field) * 131u;
    if (signalRandom(key, 35u, seed) >= rate) {{
        return vec4(0.0);
    }}
    float start = signalRandom(key, 36u, seed) * 1.1 - 0.1;
    float span = 0.02 + 0.22 * pow(signalRandom(key, 37u, seed), 2.0);
    float at = (x - start) / span;
    if (at < 0.0 || at > 1.0) {{
        return vec4(0.0);
    }}
    uint grainKey = key ^ uint(x * 1200.0) * 2654435761u;
    float grain = signalRandom(grainKey, 38u, seed);
    vec3 colour = signalRandom(key, 39u, seed) < 0.35
        ? vec3(0.82 + 0.18 * grain)
        : vec3(0.03) + 0.4 * grain * vec3(signalRandom(grainKey, 40u, seed), signalRandom(grainKey, 41u, seed),
                                          signalRandom(grainKey, 42u, seed));
    return vec4(colour, smoothstep(0.0, 0.06, at) * (0.35 + 0.65 * (1.0 - at)));
}}
"""


def signal_random(key: int, salt: int, seed: int) -> float:
    """CPU mirror of ``signalRandom`` (the same integer hash as ``sceneRandom``)."""
    return scene3d_random(key, salt, seed)


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def signal_noise1(x: float, salt: int, seed: int) -> float:
    """CPU mirror of ``signalNoise1``."""
    i = math.floor(x)
    f = x - i
    k = int(i) + 1048576
    f = f * f * (3.0 - 2.0 * f)
    a, b = signal_random(k, salt, seed), signal_random(k + 1, salt, seed)
    return a + (b - a) * f


def signal_tear(y: float, time: float, threshold: float, seed: int) -> float:
    """CPU mirror of ``signalTear``."""
    n = 0.65 * signal_noise1(y * 7.0 + time * 0.9, 32, seed) + 0.35 * signal_noise1(y * 23.0 - time * 2.3, 33, seed)
    return _smoothstep(threshold, threshold + 0.12, n)
