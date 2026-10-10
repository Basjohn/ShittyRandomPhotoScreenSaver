"""Photo surfaces: shared GLSL that reads a renderer-owned, mipmapped photo copy
(``rendering/quick/scene3d/environment.py::PhotoEnvironment``) as a surface. Import-safe: GLSL
text and CPU mirrors, no GL.

Proved by Relief Rise and Accordion Fold (both retired 2026-10-10) and kept for relief, terrain
and backdrop work:

* ``PHOTO_SURFACE_GLSL``: ``photoBrightness`` reads a copy's luminance at a blurred mip level,
  so a height field taken from it is smooth at any grid density (never read heights from the
  lent photographs, which have no mips); ``photoFrost`` is a smooth frosted backdrop, a tent of
  nine taps a blurred texel apart (one tap alone shows the texels);
* ``photo_occlusion_glsl``: contact occlusion for any height field, how far the surface around a
  point stands above it, sampled at six offsets, so hollows darken.
"""

from __future__ import annotations

import math
from collections.abc import Callable

PHOTO_LUMA = (0.2126, 0.7152, 0.0722)
PHOTO_OCCLUSION_TAPS = 6

PHOTO_SURFACE_GLSL = f"""
// The copy's luminance at uv, read at a blurred mip level.
float photoBrightness(sampler2D photo, vec2 uv, float level) {{
    return dot(textureLod(photo, uv, level).rgb, vec3({PHOTO_LUMA[0]}, {PHOTO_LUMA[1]}, {PHOTO_LUMA[2]}));
}}
// A smooth frosted backdrop of the copy at uv (y down), blurred around mip level.
vec3 photoFrost(sampler2D photo, vec2 uv, float level) {{
    vec2 texel = exp2(level) / vec2(textureSize(photo, 0));
    vec3 sum = vec3(0.0);
    for (int y = -1; y <= 1; ++y)
        for (int x = -1; x <= 1; ++x)
            sum += textureLod(photo, uv + vec2(x, y) * texel, level).rgb * float((2 - abs(x)) * (2 - abs(y)));
    return sum / 16.0;
}}
"""


def photo_occlusion_glsl(height_function: str, name: str = "photoOcclusion") -> str:
    """GLSL ``float name(vec2 uv, float here, vec2 reach, float scale)``: 0 (open) to 1 (deep
    hollow), how far ``height_function(vec2)`` stands above ``here`` at six points ``reach`` (uv
    units per axis) around ``uv``, against ``scale`` (the field's full height). Declare the height
    function first."""
    return f"""
float {name}(vec2 uv, float here, vec2 reach, float scale) {{
    float above = 0.0;
    for (int i = 0; i < {PHOTO_OCCLUSION_TAPS}; ++i) {{
        float angle = float(i) * {2.0 * math.pi / PHOTO_OCCLUSION_TAPS:.7f};
        above += max({height_function}(uv + vec2(cos(angle), sin(angle)) * reach) - here, 0.0);
    }}
    return clamp(above / ({PHOTO_OCCLUSION_TAPS:.1f} * max(scale, 1e-6)) * 4.0, 0.0, 1.0);
}}
"""


def photo_occlusion(height: Callable[[tuple[float, float]], float], uv: tuple[float, float], here: float,
                    reach: tuple[float, float], scale: float) -> float:
    """CPU mirror of a ``photo_occlusion_glsl`` function over ``height``."""
    above = 0.0
    for i in range(PHOTO_OCCLUSION_TAPS):
        angle = i * 2.0 * math.pi / PHOTO_OCCLUSION_TAPS
        above += max(height((uv[0] + math.cos(angle) * reach[0], uv[1] + math.sin(angle) * reach[1])) - here, 0.0)
    return max(0.0, min(1.0, above / (PHOTO_OCCLUSION_TAPS * max(scale, 1e-6)) * 4.0))
