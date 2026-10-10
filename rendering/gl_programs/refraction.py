"""Refraction through thin layers: shared, import-safe GLSL and CPU mirrors (no GL).

For full-picture passes that see a photograph through a thin layer of liquid or glass lying on
the picture plane (Liquid Lens first; Chromatic Shear and Capillary Bloom are meant to reuse
it). Everything is restrained and screen-space: no ray marching, no second scene.

* ``layerNormal(gradient)``: the normal of a height field from its gradient (picture-height
  units per picture height);
* ``refractionOffset(normal, thickness, ior)``: where the bent view ray, entering the layer
  from straight above, meets the picture under it: the offset in picture heights;
* ``dispersedSample(photo, uv, offset, dispersion, aspect)``: the photograph seen through that
  offset with its channels bending by different amounts (red least, blue most), the rainbow
  fringe of real dispersion; 0 dispersion is one plain sample of all three;
* ``fresnelSchlick(cosTheta, f0)``: the share of light a surface reflects at an angle.

Glass Shatter and 3D Block Spins keep their own accepted (pixel-pinned) refraction code.
"""

from __future__ import annotations

import math

REFRACTION_IOR_WATER = 1.333
DISPERSION_SPREAD = 0.06        # the channel spread at dispersion 1, a share of the offset

REFRACTION_GLSL = f"""
const float DISPERSION_SPREAD = {DISPERSION_SPREAD:.6f};
vec3 layerNormal(vec2 gradient) {{
    return normalize(vec3(-gradient, 1.0));
}}
vec2 refractionOffset(vec3 normal, float thickness, float ior) {{
    vec3 bent = refract(vec3(0.0, 0.0, -1.0), normal, 1.0 / ior);
    return bent.xy / max(-bent.z, 0.2) * thickness;
}}
// offset is in picture heights with y up; uv is the picture's own (y down); aspect = width / height.
vec3 dispersedSample(sampler2D photo, vec2 uv, vec2 offset, float dispersion, float aspect) {{
    vec2 shift = vec2(offset.x / aspect, -offset.y);
    float spread = DISPERSION_SPREAD * dispersion;
    if (spread <= 0.0) return texture(photo, uv + shift).rgb;
    return vec3(texture(photo, uv + shift * (1.0 - spread)).r,
                texture(photo, uv + shift).g,
                texture(photo, uv + shift * (1.0 + spread)).b);
}}
float fresnelSchlick(float cosTheta, float f0) {{
    return f0 + (1.0 - f0) * pow(1.0 - clamp(cosTheta, 0.0, 1.0), 5.0);
}}
"""


def layer_normal(gradient: tuple[float, float]) -> tuple[float, float, float]:
    """CPU mirror of ``layerNormal``."""
    x, y = -gradient[0], -gradient[1]
    length = math.sqrt(x * x + y * y + 1.0)
    return x / length, y / length, 1.0 / length


def refraction_offset(normal: tuple[float, float, float], thickness: float, ior: float) -> tuple[float, float]:
    """CPU mirror of ``refractionOffset`` (GLSL ``refract`` with the view ray straight down)."""
    eta = 1.0 / ior
    incident = (0.0, 0.0, -1.0)
    cos_i = -sum(n * i for n, i in zip(normal, incident))
    k = 1.0 - eta * eta * (1.0 - cos_i * cos_i)
    if k < 0.0:
        bent = (0.0, 0.0, 0.0)
    else:
        scale = eta * cos_i - math.sqrt(k)
        bent = tuple(eta * i + scale * n for i, n in zip(incident, normal))
    depth = max(-bent[2], 0.2)
    return bent[0] / depth * thickness, bent[1] / depth * thickness


def dispersion_shifts(offset: tuple[float, float], dispersion: float, aspect: float) -> tuple[tuple[float, float], ...]:
    """The red, green and blue sampling shifts (picture uv, y down) of ``dispersedSample``."""
    shift = (offset[0] / aspect, -offset[1])
    spread = DISPERSION_SPREAD * dispersion
    return tuple((shift[0] * f, shift[1] * f) for f in (1.0 - spread, 1.0, 1.0 + spread))


def fresnel_schlick(cos_theta: float, f0: float) -> float:
    """CPU mirror of ``fresnelSchlick``."""
    return f0 + (1.0 - f0) * (1.0 - max(0.0, min(1.0, cos_theta))) ** 5
