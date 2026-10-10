"""Chromatic Shear: shaders and CPU mirrors (loaded only when Chromatic Shear renders).

The picture splits into broad slices that shear apart along one axis, and every slice fans into
spectral layers (``rendering/gl_programs/spectral.py``) offset by different amounts, a clean
prism fringe rather than a red/green/blue ghost. Each layer turns from the old picture to the new
at its own moment, red first and violet last, so the change passes through the spectrum while the
slices are furthest apart; then they slide back together on the new picture. Slices meet in a
soft seam a pixel and a half wide that catches a faint line of light; samples beyond the picture
mirror back in, so no edge smears.

The separation envelope is ``sin(pi t)^1.4``: no offset at either end, where the layers add back
up to each photograph exactly.
"""

from __future__ import annotations

import math

from rendering.gl_programs.spectral import SPECTRAL_GLSL, SPECTRAL_LAYERS, spectral_position

SHEAR_SLICES_RANGE = (3, 14)
SHEAR_AMOUNT = 0.16          # largest slice offset at full spread, picture heights
SHEAR_FAN = 0.045            # spectral fan across the layers at full spread
SHEAR_SWITCH = (0.44, 0.56)  # when the first (red) and last (violet) layer turn to the new picture
SHEAR_SWITCH_WIDTH = 0.06
SHEAR_AXES = {"horizontal": (1.0, 0.0), "vertical": (0.0, 1.0), "diagonal": (0.94, 0.34)}


def shear_envelope(progress: float) -> float:
    t = max(0.0, min(1.0, float(progress)))
    return math.sin(math.pi * t) ** 1.4


def shear_switch(progress: float, layer: int) -> float:
    """How far layer ``layer`` has turned to the new picture."""
    centre = SHEAR_SWITCH[0] + (SHEAR_SWITCH[1] - SHEAR_SWITCH[0]) * spectral_position(layer)
    x = max(0.0, min(1.0, (progress - centre + SHEAR_SWITCH_WIDTH) / (2.0 * SHEAR_SWITCH_WIDTH)))
    return x * x * (3.0 - 2.0 * x)


CHROMATIC_SHEAR_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform vec2 uItemSize;\n"
    "uniform float uProgress;\nuniform vec2 uAxis;\nuniform float uSpread;\nuniform float uSlices;\n"
    "uniform float uSeed;\n"
    + SPECTRAL_GLSL
    + f"""
const float SHEAR_AMOUNT = {SHEAR_AMOUNT:.6f};
const float SHEAR_FAN = {SHEAR_FAN:.6f};
const vec2 SHEAR_SWITCH = vec2({SHEAR_SWITCH[0]:.6f}, {SHEAR_SWITCH[1]:.6f});
const float SHEAR_SWITCH_WIDTH = {SHEAR_SWITCH_WIDTH:.6f};

float hash1(float n) {{ return fract(sin(n * 91.3458 + uSeed * 0.0173) * 47453.5453); }}
float sliceOffset(float k, float across) {{
    return (hash1(k) * 2.0 - 1.0) + 0.35 * sin(across * 2.3 + uSeed);
}}
// Mirror a uv back into the picture: what lies beyond an edge is its reflection.
vec2 mirrored(vec2 uv) {{ return 1.0 - abs(1.0 - mod(uv, 2.0)); }}

void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float aspect = uItemSize.x / uItemSize.y;
    vec2 p = vec2((uv.x - 0.5) * aspect, 0.5 - uv.y);
    float t = clamp(uProgress, 0.0, 1.0);
    float envelope = pow(sin(3.14159265 * t), 1.4);
    vec2 across = vec2(-uAxis.y, uAxis.x);
    float extent = abs(across.x) * aspect + abs(across.y);
    float c = (dot(p, across) / extent + 0.5) * uSlices;          // position in slices across the axis
    float k = floor(c), f = c - k;
    float px = uSlices / (extent * uItemSize.y);                   // one pixel, in slices
    // The slice's offset, easing into its neighbour's over a pixel and a half at each seam.
    float own = sliceOffset(k, c / uSlices), next = f < 0.5 ? sliceOffset(k - 1.0, c / uSlices) : sliceOffset(k + 1.0, c / uSlices);
    float seam = min(f, 1.0 - f);
    float blend = smoothstep(0.0, 1.5 * px, seam);
    float offset = mix(0.5 * (own + next), own, blend) * SHEAR_AMOUNT * uSpread * envelope;
    vec3 colour = vec3(0.0);
    for (int i = 0; i < SPECTRAL_LAYERS; ++i) {{
        float position = spectralPosition(i);
        float layer = offset + (position - 0.5) * SHEAR_FAN * uSpread * envelope * (1.0 + 0.6 * abs(own));
        vec2 shift = uAxis * layer;
        vec2 at = mirrored(uv - vec2(shift.x / aspect, -shift.y));
        float centre = mix(SHEAR_SWITCH.x, SHEAR_SWITCH.y, position);
        float turned = smoothstep(centre - SHEAR_SWITCH_WIDTH, centre + SHEAR_SWITCH_WIDTH, t);
        vec3 seen = mix(texture(uOldTex, at).rgb, texture(uNewTex, at).rgb, turned);
        colour += seen * spectralWeight(i);
    }}
    // A faint line of light where slices that moved apart meet.
    float gap = abs(own - next) * envelope * uSpread;
    colour += vec3(0.9, 0.95, 1.0) * 0.18 * gap * (1.0 - smoothstep(0.0, 1.2 * px, seam));
    FragColor = vec4(colour, 1.0);
}}
"""
)
