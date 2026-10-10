"""Liquid Lens: shaders and CPU mirrors (loaded only when Liquid Lens renders).

A lens of water comes in from an edge, a corner or the centre and grows until it covers the
picture. Through it the new picture shows, bent by the water; outside, the old picture lies
untouched but for the lens's contact shadow. The water is a height field over the picture
plane (picture heights, centred, y up): a rounded meniscus rim rising steeply from the edge
(``sqrt(1 - (1 - x)^2)`` over ``LENS_RIM``), a gentle dome over the middle (so a small lens
magnifies) and slow seeded ripples; the boundary is a wobbling circle bulging toward its travel.
The shared refraction helpers (``rendering/gl_programs/refraction.py``) bend the view through it
with a little dispersion at the steep rim; key-light highlights, a Fresnel sheen and the light
the rim focuses into a bright caustic line make it read as liquid. Optional droplets fling off
the leading rim on ballistic arcs and vanish back into the water.

Timeline: the lens grows over ``LENS_GROW_END`` of the run (centre gliding from its start to its
end point, radius easing up to cover the farthest corner even at its narrowest wobble), its water
rises over the first 8% and flattens out between ``LENS_FLATTEN``, so every light and bend is
gone and the frame is the new picture exactly before the end.
"""

from __future__ import annotations

import math

from rendering.gl_programs.refraction import REFRACTION_GLSL, REFRACTION_IOR_WATER
from rendering.gl_programs.vortex_flow import VORTEX_FLOW_GLSL

LENS_GROW_END = 0.85
LENS_GROW_POWER = 1.6       # the spread accelerates, as water does, so the edge crosses most of the run
LENS_RISE = 0.08
LENS_FLATTEN = (0.84, 0.97)
LENS_SWIRL = 0.4            # vortex twist (radians) stirring the new picture inside the water
LENS_HEIGHT = 0.05          # water thickness at the plateau, picture heights
LENS_RIM = 0.07             # meniscus width at full size
LENS_DOME = 0.6
LENS_BULGE = 0.1
LENS_WOBBLE = (0.045, 0.03, 0.02, 0.014)       # modes 2-5, a share of the radius
LENS_DROPLETS = 26
LENS_MARGIN = 0.02


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def lens_path(origin: str, aspect: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """(start, end) of the lens centre for an origin code (picture heights, centred, y up)."""
    hw = 0.5 * aspect
    sx = {"left": -1.0, "right": 1.0, "top_left": -1.0, "bottom_left": -1.0,
          "top_right": 1.0, "bottom_right": 1.0}.get(origin, 0.0)
    sy = {"top": 1.0, "bottom": -1.0, "top_left": 1.0, "top_right": 1.0,
          "bottom_left": -1.0, "bottom_right": -1.0}.get(origin, 0.0)
    if origin not in ("left", "right", "top", "bottom", "top_left", "top_right", "bottom_left",
                      "bottom_right", "center"):
        raise ValueError(f"unknown Liquid Lens origin: {origin!r}")
    start = (sx * (hw - 0.22), sy * 0.3)
    end = (-sx * hw * 0.25, -sy * 0.1)
    return start, end


def lens_cover(end: tuple[float, float], aspect: float) -> float:
    """The full radius: past the farthest corner from the end point even where the wobbling,
    bulging boundary is narrowest, plus the rim."""
    hw = 0.5 * aspect
    farthest = max(math.hypot(cx - end[0], cy - end[1]) for cx in (-hw, hw) for cy in (-0.5, 0.5))
    return (farthest + LENS_RIM + LENS_MARGIN) / (1.0 - sum(LENS_WOBBLE) - LENS_BULGE)


def lens_growth(progress: float) -> float:
    return max(0.0, min(1.0, progress / LENS_GROW_END)) ** LENS_GROW_POWER


def lens_glide(progress: float) -> float:
    return _smooth(progress / LENS_GROW_END)


def lens_swirl(progress: float) -> float:
    """How hard the water stirs the new picture: settling as the lens fills the picture."""
    return LENS_SWIRL * (1.0 - _smooth((progress - 0.45) / 0.4))


def lens_centre(start, end, progress: float) -> tuple[float, float]:
    g = lens_glide(progress)
    return start[0] + (end[0] - start[0]) * g, start[1] + (end[1] - start[1]) * g


def lens_radius(cover: float, progress: float) -> float:
    return cover * lens_growth(progress)


def lens_height(progress: float) -> float:
    """The water's plateau thickness: rising, then flattening to nothing before the end."""
    t = max(0.0, min(1.0, float(progress)))
    return LENS_HEIGHT * _smooth(t / LENS_RISE) * (1.0 - _smooth((t - LENS_FLATTEN[0]) / (LENS_FLATTEN[1] - LENS_FLATTEN[0])))


def lens_meniscus(x: float) -> float:
    """The rim's profile: 0 at the edge rising steeply to 1 at ``LENS_RIM`` inside."""
    x = max(0.0, min(1.0, x))
    return math.sqrt(max(0.0, 1.0 - (1.0 - x) * (1.0 - x)))


LIQUID_LENS_GLSL = f"""
const float LENS_GROW_END = {LENS_GROW_END:.6f};
const float LENS_GROW_POWER = {LENS_GROW_POWER:.6f};
const float LENS_SWIRL = {LENS_SWIRL:.6f};
const float LENS_RISE = {LENS_RISE:.6f};
const vec2 LENS_FLATTEN = vec2({LENS_FLATTEN[0]:.6f}, {LENS_FLATTEN[1]:.6f});
const float LENS_HEIGHT = {LENS_HEIGHT:.6f};
const float LENS_RIM = {LENS_RIM:.6f};
const float LENS_DOME = {LENS_DOME:.6f};
const vec4 LENS_WOBBLE = vec4({", ".join(f"{a:.6f}" for a in LENS_WOBBLE)});
float lensGrowth(float t) {{ return pow(clamp(t / LENS_GROW_END, 0.0, 1.0), LENS_GROW_POWER); }}
float lensGlide(float t) {{ return smoothstep(0.0, 1.0, t / LENS_GROW_END); }}
float lensSwirl(float t) {{ return LENS_SWIRL * (1.0 - smoothstep(0.0, 1.0, (t - 0.45) / 0.4)); }}
vec2 lensCentre(vec2 start, vec2 end, float t) {{ return mix(start, end, lensGlide(t)); }}
float lensRadius(float cover, float t) {{ return cover * lensGrowth(t); }}
float lensHeight(float t) {{
    t = clamp(t, 0.0, 1.0);
    return LENS_HEIGHT * smoothstep(0.0, 1.0, t / LENS_RISE)
         * (1.0 - smoothstep(0.0, 1.0, (t - LENS_FLATTEN.x) / (LENS_FLATTEN.y - LENS_FLATTEN.x)));
}}
float lensMeniscus(float x) {{ x = clamp(x, 0.0, 1.0); return sqrt(max(0.0, 1.0 - (1.0 - x) * (1.0 - x))); }}
"""

LIQUID_LENS_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform vec2 uItemSize;\n"
    "uniform float uProgress;\nuniform float uTime;\nuniform float uDuration;\nuniform float uSeed;\n"
    "uniform vec2 uStart;\nuniform vec2 uEnd;\nuniform float uTravel;\nuniform float uBulge;\nuniform float uCover;\n"
    "uniform float uRefraction;\nuniform float uDispersion;\nuniform int uDroplets;\n"
    + REFRACTION_GLSL + VORTEX_FLOW_GLSL + LIQUID_LENS_GLSL
    + f"""
const float IOR = {REFRACTION_IOR_WATER:.4f};
const int DROPLETS = {LENS_DROPLETS};
float aspect;
vec2 centre;
float radius, plateau, rim;

float hash1(float n) {{ return fract(sin(n * 12.9898 + uSeed * 0.0137) * 43758.5453); }}

// Signed distance-like value to the wobbling boundary (negative inside) and the distance to the centre.
float boundary(vec2 p, vec2 c, float r, float time, out float dist) {{
    vec2 d = p - c;
    dist = length(d);
    float a = atan(d.y, d.x);
    float shape = 1.0 + uBulge * cos(a - uTravel);
    for (int k = 0; k < 4; ++k) {{
        float kf = float(k + 2);
        shape += LENS_WOBBLE[k] * sin(kf * a + hash1(kf) * 6.2832 + (0.6 + 0.35 * kf) * time * (hash1(kf + 9.0) < 0.5 ? -1.0 : 1.0));
    }}
    return dist - r * shape;
}}

float waterHeight(vec2 p) {{
    float dist;
    float s = boundary(p, centre, radius, uTime, dist);
    if (s >= 0.0 || plateau <= 0.0) return 0.0;
    float x = -s / rim;
    float dome = 1.0 + LENS_DOME * max(0.0, 1.0 - (dist / max(radius, 1e-4)) * (dist / max(radius, 1e-4)));
    vec2 q = p * 7.0;
    float ripple = 0.14 * (sin(q.x * 1.3 + q.y * 0.7 + uTime * 2.3 + uSeed) + sin(q.y * 1.1 - q.x * 0.5 - uTime * 1.9))
                 + 0.07 * sin(length(p - centre) * 38.0 - uTime * 5.0);
    return plateau * lensMeniscus(x) * (dome + ripple * smoothstep(0.0, 1.0, x));
}}

vec3 droplets(vec2 p, vec3 colour, vec2 uv) {{
    for (int i = 0; i < DROPLETS; ++i) {{
        float fi = float(i);
        float born = mix(0.08, 0.62, hash1(fi * 3.1 + 1.0));
        float age = (uProgress - born) * uDuration;
        if (age <= 0.0 || age > 1.3 || uProgress > 0.9) continue;
        float spread = uBulge > 0.0 ? 2.2 : 6.2832;
        float a = uTravel + (hash1(fi * 5.7 + 2.0) - 0.5) * spread;
        vec2 dir = vec2(cos(a), sin(a));
        vec2 from = lensCentre(uStart, uEnd, born) + dir * lensRadius(uCover, born) * (1.0 + uBulge * cos(a - uTravel));
        vec2 velocity = dir * mix(0.35, 0.8, hash1(fi * 7.3 + 3.0)) + vec2(0.0, mix(0.1, 0.45, hash1(fi * 1.9 + 4.0)));
        vec2 at = from + velocity * age + vec2(0.0, -0.8) * age * age;
        float size = mix(0.006, 0.02, hash1(fi * 2.3 + 5.0)) * smoothstep(0.0, 0.08, age) * (1.0 - smoothstep(0.84, 0.9, uProgress));
        float d0;
        if (boundary(at, centre, radius, uTime, d0) < 0.0) continue;      // back in the water
        vec2 q = (p - at) / max(size, 1e-5);
        float r2 = dot(q, q);
        if (r2 >= 1.0) continue;
        float nz = sqrt(1.0 - r2);
        // A droplet is a tiny ball lens: it shows what lies under it, flipped and gathered.
        vec2 under = uv + vec2(-q.x / aspect, q.y) * size * 0.9;
        vec3 seen = texture(uOldTex, clamp(under, 0.0, 1.0)).rgb;
        vec3 n = vec3(q, nz);
        float highlight = pow(max(dot(n, normalize(vec3(-0.45, 0.6, 1.0) + vec3(0.0, 0.0, 1.0))), 0.0), 60.0);
        float edge = smoothstep(0.55, 1.0, sqrt(r2));
        vec3 drop = seen * (1.0 - 0.45 * edge) + vec3(1.0) * (highlight * 1.2 + fresnelSchlick(nz, 0.02) * 0.35);
        float cover = 1.0 - smoothstep(0.85, 1.0, sqrt(r2));
        colour = mix(colour, drop, cover);
    }}
    return colour;
}}

void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    aspect = uItemSize.x / uItemSize.y;
    vec2 p = vec2((uv.x - 0.5) * aspect, 0.5 - uv.y);
    centre = lensCentre(uStart, uEnd, uProgress);
    radius = lensRadius(uCover, uProgress);
    plateau = lensHeight(uProgress);
    rim = LENS_RIM * clamp(radius / 0.25, 0.3, 1.0);

    float dist;
    float s = boundary(p, centre, radius, uTime, dist);
    vec3 old = texture(uOldTex, uv).rgb;
    float aa = 1.5 / uItemSize.y;
    float strength = plateau / LENS_HEIGHT;
    vec3 colour;
    if (s > aa) {{
        // Outside: the old picture under the lens's contact shadow.
        colour = old * (1.0 - 0.28 * strength * exp(-s / 0.012));
    }} else {{
        float e = 1.5 / uItemSize.y;
        float h = waterHeight(p);
        float hx0 = waterHeight(p - vec2(e, 0.0)), hx1 = waterHeight(p + vec2(e, 0.0));
        float hy0 = waterHeight(p - vec2(0.0, e)), hy1 = waterHeight(p + vec2(0.0, e));
        vec2 gradient = vec2(hx1 - hx0, hy1 - hy0) / (2.0 * e);
        vec3 n = layerNormal(gradient);
        float optics = 0.25 + 1.5 * uRefraction;
        vec2 offset = refractionOffset(n, h * optics, IOR);
        // The water stirs what lies under it: seen through seeded vortices about the lens centre.
        float span = max(radius, 0.3);
        vec2 stirred = centre + vortexFlowInverse((p - centre) / span * 0.4, uSeed, lensSwirl(uProgress) * strength) * span / 0.4;
        // Near the picture's own edges the water may not pull in what lies beyond them (clamped
        // samples smear into streaks): the stir and the bend fade out over the outer 8%.
        vec2 border = min(uv, 1.0 - uv);
        float edgeFade = smoothstep(0.0, 0.08, min(border.x * aspect, border.y));
        vec2 stirredUv = mix(uv, vec2(stirred.x / aspect + 0.5, 0.5 - stirred.y), edgeFade);
        vec3 seen = dispersedSample(uNewTex, clamp(stirredUv, 0.0, 1.0), offset * edgeFade,
                                    uDispersion * strength * 10.0, aspect);
        // Light the water: a key highlight, a Fresnel sheen of the sky, and the light the rim
        // focuses into a bright line just inside it (where the surface curves down).
        float laplacian = (hx0 + hx1 + hy0 + hy1 - 4.0 * h) / (e * e);
        float caustic = clamp(-laplacian * rim * rim / LENS_HEIGHT * 0.18, 0.0, 1.0) * strength;
        vec3 halfway = normalize(normalize(vec3(-0.45, 0.6, 1.0)) + vec3(0.0, 0.0, 1.0));
        float highlight = pow(max(dot(n, halfway), 0.0), 90.0) * strength;
        float sheen = fresnelSchlick(n.z, 0.02) * strength;
        colour = seen * (1.0 + 0.55 * caustic) + vec3(0.85, 0.93, 1.0) * (0.9 * highlight + 0.55 * sheen);
        // Across the edge the two pictures meet over a pixel and a half, under a thin bright rim.
        float inside = smoothstep(aa, -aa, s);
        colour = mix(old * (1.0 - 0.28 * strength), colour, inside);
        colour += vec3(0.9, 0.95, 1.0) * 0.35 * strength * exp(-abs(s) * uItemSize.y / 1.2);
    }}
    if (uDroplets != 0) colour = droplets(p, colour, uv);
    FragColor = vec4(colour, 1.0);
}}
"""
)
