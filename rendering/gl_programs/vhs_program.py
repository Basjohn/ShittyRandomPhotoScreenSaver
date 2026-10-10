"""VHS Distortion: shader and CPU mirrors (loaded only when VHS Distortion renders).

The tape loses tracking and the picture rolls. As tracking degrades (``vhs_envelope``) lines jitter
and sway, tearing bands smear across the picture, colour bleeds and rings, snow, dropouts and an
interference band crawl over it. Then vertical hold slips (``vhs_roll``): the old picture rolls off,
followed by the black blanking bar between frames (with its sync band and the dancing caption-data
dashes) and the new picture rolling in behind it, the roll slipping unevenly and catching with a
small jolt when hold locks. Each frame tears hardest near its own edges, where the seam is: its top
lines flag sideways as sync recovers and its bottom lines carry head-switching noise. Tracking then
settles and every distortion fades to nothing well before the end (``VHS_SETTLED``), so both ends
are the exact photographs.

Settings scale three families: Tracking (jitter, sway, tears, flagging, head switching), Colour Bleed (chroma delay,
smear and luma ringing) and Noise (snow, dropouts, scanlines, flicker, interference, vignette).
All three at zero leave a clean roll. The analog
primitives live in ``analog_signal``; this module owns only the VHS timeline and composition.
"""

from __future__ import annotations

import math

from rendering.gl_programs.analog_signal import ANALOG_SIGNAL_GLSL

# Height of the blanking bar between frames, in picture heights, and the rolled strip's period.
VHS_BAR = 0.12
VHS_PERIOD = 1.0 + VHS_BAR
# Signal structure: lines per picture and fields per second (the noise changes once a field).
VHS_LINES = 480.0
VHS_FIELD_RATE = 30.0
# Tracking degrades over the run's start and settles at its end; all distortion is gone from here.
VHS_DEGRADE = 0.2
VHS_SETTLE = (0.8, 0.97)
VHS_SETTLED = VHS_SETTLE[1]
# The roll happens inside this share of the run: a slipping roll, then hold catches with a jolt.
VHS_ROLL_WINDOW = (0.1, 0.84)
VHS_ROLL_MAIN = 0.88            # share of the window spent rolling; the rest is the catch
VHS_ROLL_RAMP = (0.22, 0.3)     # share of the roll spent speeding up / slowing down
VHS_ROLL_STUTTER = 0.03         # the roll slipping unevenly (picture heights over the period)
VHS_ROLL_CATCH = 0.045          # overshoot when hold catches


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def vhs_envelope(progress: float) -> float:
    """How lost tracking is at ``progress``: 0 at both ends, 1 through the middle of the run."""
    p = float(progress)
    return _smoothstep(0.0, VHS_DEGRADE, p) * (1.0 - _smoothstep(*VHS_SETTLE, p))


def _ramped(m: float) -> float:
    """Distance over a roll that speeds up, runs steadily and slows down (0..1 over m in 0..1)."""
    up, down = VHS_ROLL_RAMP
    peak = 1.0 / (1.0 - 0.5 * up - 0.5 * down)
    if m < up:
        return peak * m * m / (2.0 * up)
    if m < 1.0 - down:
        return peak * (0.5 * up + m - up)
    rest = 1.0 - m
    return 1.0 - peak * rest * rest / (2.0 * down)


def vhs_roll(progress: float) -> float:
    """How far the strip (old picture, bar, new picture) has rolled at ``progress``, in picture
    heights: 0 before the roll, ``VHS_PERIOD`` (the new picture exactly in place) after it."""
    start, end = VHS_ROLL_WINDOW
    u = (float(progress) - start) / (end - start)
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return VHS_PERIOD
    if u < VHS_ROLL_MAIN:
        m = u / VHS_ROLL_MAIN
        stutter = VHS_ROLL_STUTTER * math.sin(4.0 * math.pi * m) * math.sin(math.pi * m) ** 2
        return VHS_PERIOD * (_ramped(m) + stutter)
    w = (u - VHS_ROLL_MAIN) / (1.0 - VHS_ROLL_MAIN)
    return VHS_PERIOD * (1.0 + VHS_ROLL_CATCH * math.sin(math.pi * w) * (1.0 - w))


VHS_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform vec2 uItemSize;\n"
    "uniform float uEnvelope;\nuniform float uRoll;\nuniform float uRollSign;\nuniform float uTime;\n"
    "uniform float uSeed;\nuniform float uTracking;\nuniform float uBleed;\nuniform float uNoise;\n"
    + ANALOG_SIGNAL_GLSL
    + f"""
const float VHS_BAR = {VHS_BAR:.6f};
const float VHS_PERIOD = {VHS_PERIOD:.6f};
const float VHS_LINES = {VHS_LINES:.1f};
const float VHS_FIELD_RATE = {VHS_FIELD_RATE:.1f};

void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    uint seed = uint(uSeed);
    float e = uEnvelope;
    float track = e * uTracking, bleed = e * uBleed, noise = e * uNoise;
    float field = floor(uTime * VHS_FIELD_RATE);
    uint fieldKey = uint(field);
    float line = floor(uv.y * VHS_LINES);

    // Where this row is on the rolled strip. While tracking is lost the picture jumps on some fields.
    float jump = signalRandom(fieldKey, 1u, seed) < 0.3 ? (signalRandom(fieldKey, 2u, seed) - 0.5) * 0.01 * track : 0.0;
    float t = uv.y + jump + uRollSign * uRoll;
    float k = floor(t / VHS_PERIOD);
    float local = t - k * VHS_PERIOD;       // below 1: a picture row; from 1 to the period: the blanking bar
    bool blank = local >= 1.0;
    bool newer = k != 0.0;

    // Horizontal displacement. Rows near a frame's edges, where the roll's seam is, tear most.
    float seam = blank ? 1.0 : max(exp(-local / 0.09), exp(-(1.0 - local) / 0.09));
    float tear = track * signalTear(uv.y, uTime, mix(0.76, 0.6, seam), seed);
    float band = floor(uv.y * 48.0);
    float dx = 0.003 * track * signalLineJitter(line, field, seed)
             + 0.004 * track * signalWobble(uv.y, uTime)
             + tear * (signalRandom(uint(band) + fieldKey * 97u, 3u, seed) - 0.3) * 0.06;
    if (!blank) {{
        // Flagging: each frame's top lines bend sideways as sync recovers.
        dx += 0.05 * track * exp(-local / 0.03) * (0.75 + 0.25 * sin(uTime * 9.0 + local * 60.0));
        // Head switching: ragged, shifted lines at the bottom of each frame.
        dx += track * smoothstep(0.975, 1.0, local)
                * (0.012 + 0.05 * signalRandom(uint(line) + fieldKey * 977u, 4u, seed));
    }}
    float x = uv.x - dx;
    // Inside a tear the line smears, stretched about a point of its own.
    float anchor = signalRandom(uint(band), 5u, seed);
    x = anchor + (x - anchor) * (1.0 - 0.25 * tear);

    vec3 colour;
    if (blank) {{
        float b = (local - 1.0) / VHS_BAR;  // 0 under one frame's last line, 1 at the next frame's first
        colour = vec3(0.018) * (1.0 - 0.8 * smoothstep(0.3, 0.36, b) * (1.0 - smoothstep(0.58, 0.64, b)));
        colour += vec3(0.07) * step(0.86, signalRandom(uint(line) * 7u + fieldKey, 6u, seed));
        // Caption data: a line of dancing white dashes just above the next frame.
        if (b > 0.84 && b < 0.88 && x > 0.18 && x < 0.82) {{
            float dash = step(0.45, signalRandom(uint(floor(x * 40.0)) + fieldKey * 61u, 7u, seed))
                       * step(0.2, fract(x * 40.0));
            colour = mix(colour, vec3(0.78), dash);
        }}
    }} else {{
        vec2 st = vec2(x, local);
        float shift = bleed * (0.007 + 0.002 * signalLineJitter(line, field, seed ^ 0x5bd1e995u));
        float spread = 0.0025 * bleed;
        float split = bleed * (0.0035 + 0.003 * tear);
        colour = newer ? signalBleed(uNewTex, st, shift, spread, 0.9 * bleed, split)
                       : signalBleed(uOldTex, st, shift, spread, 0.9 * bleed, split);
        colour *= step(0.0, x) * step(x, 1.0);   // displaced lines leave black at the edge
    }}

    // Noise: field flicker, line structure, snow, a drifting interference band and dropouts.
    colour *= 1.0 + 0.07 * noise * (signalRandom(fieldKey, 8u, seed) - 0.5);
    colour *= 1.0 - 0.14 * noise * signalScanline(uv.y * uItemSize.y, 3.0);
    float roller = fract(uTime * 0.21 + signalRandom(0u, 9u, seed));
    float interference = exp(-pow((1.0 - uv.y - roller) / 0.04, 2.0));
    colour += 0.17 * noise * (1.0 + 2.5 * interference)
            * signalSnow(vec2(floor(uv.x * uItemSize.x / 2.5), line), field, seed);
    colour += 0.05 * noise * interference;
    vec4 drop = signalDropout(x, line, field, noise * (0.012 + 0.05 * seam * track), seed);
    colour = mix(colour, drop.rgb, drop.a);
    vec2 c = uv - 0.5;
    colour *= 1.0 - 0.45 * noise * dot(c, c);
    FragColor = vec4(clamp(colour, 0.0, 1.0), 1.0);
}}
"""
)
