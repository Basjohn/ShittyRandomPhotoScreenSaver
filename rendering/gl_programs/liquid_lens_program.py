"""Liquid Lens: shaders and CPU mirrors (loaded only when Liquid Lens renders).

A drop of water lands near an edge, a corner or the centre and rounds into a small, thick lens
(a plano-convex spherical cap, ``LENS_DEPTH`` as thick as it is wide in radius) that glides across
the old picture showing the new one through it, magnified and bent hard at its rim. It reads as a
solid lens: a window-shaped key-light reflection and a sharp sun glint on its dome, a Fresnel
reflection of a dim room around its rim, a dark glass edge where the surface turns away, the
light it gathers glowing on its far side, and a soft shadow thrown away from the light. Half way
the drop gives way: it spreads until it covers the picture, thinning as it goes (the dome flattening
as the cube of its growth) into a film whose meniscus rim catches the light.
Optional droplets splash off its rim on
ballistic arcs and vanish back into the water. The shared refraction helpers
(``rendering/gl_programs/refraction.py``) bend the view, with a little dispersion at the rim.

Picture heights, centred, y up. Timeline: the drop forms by ``LENS_FORM``, holds its size until
``LENS_SPREAD``, spreads to cover the farthest corner (even at its narrowest wobble) by
``LENS_GROW_END`` while its centre glides from its start to its end point; the water rises over
the first 8% and flattens out between ``LENS_FLATTEN``, so every light and bend is gone and the
frame is the new picture exactly before the end.
"""

from __future__ import annotations

import math

from rendering.gl_programs.refraction import REFRACTION_GLSL, REFRACTION_IOR_WATER

LENS_SIZE = 0.19            # the lens's radius while it glides, picture heights
LENS_DEPTH = 0.5            # its thickness at the centre, a share of its radius
LENS_FORM = 0.2
LENS_SPREAD = 0.5
LENS_GROW_END = 0.85
LENS_SPREAD_POWER = 1.8     # the spread accelerates, as water does
LENS_MAGNIFY = 0.3          # how far the full lens draws its centre's view in (1 / (1 - x) magnification)
LENS_RISE = 0.08
LENS_FLATTEN = (0.84, 0.97)
LENS_FILM = 0.012           # the spreading film's meniscus height, picture heights
LENS_RIM = 0.07             # meniscus width at full size
LENS_BULGE = 0.1
LENS_WOBBLE = (0.045, 0.03, 0.02, 0.014)       # modes 2-5, a share of the radius
LENS_ROUND = 0.3            # the gliding lens keeps this share of the wobble and bulge
LENS_THINNING = 3.0         # the dome thins as this power of its spread (2 would keep its volume)
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
    start = (sx * (hw - 0.22), sy * 0.26)
    end = (-sx * hw * 0.25, -sy * 0.1)
    return start, end


def lens_cover(end: tuple[float, float], aspect: float) -> float:
    """The full radius: past the farthest corner from the end point even where the wobbling,
    bulging boundary is narrowest, plus the rim."""
    hw = 0.5 * aspect
    farthest = max(math.hypot(cx - end[0], cy - end[1]) for cx in (-hw, hw) for cy in (-0.5, 0.5))
    return (farthest + LENS_RIM + LENS_MARGIN) / (1.0 - sum(LENS_WOBBLE) - LENS_BULGE)


def lens_spread(progress: float) -> float:
    """How far the drop has spread from its lens toward covering the picture, 0..1."""
    return max(0.0, min(1.0, (progress - LENS_SPREAD) / (LENS_GROW_END - LENS_SPREAD))) ** LENS_SPREAD_POWER


def lens_glide(progress: float) -> float:
    return _smooth(progress / LENS_GROW_END)


def lens_centre(start, end, progress: float) -> tuple[float, float]:
    g = lens_glide(progress)
    return start[0] + (end[0] - start[0]) * g, start[1] + (end[1] - start[1]) * g


def lens_radius(cover: float, progress: float) -> float:
    formed = 1.0 - (1.0 - max(0.0, min(1.0, progress / LENS_FORM))) ** 2
    return LENS_SIZE * formed + (cover - LENS_SIZE) * lens_spread(progress)


def lens_thickness(cover: float, progress: float) -> float:
    """The dome's thickness at the centre (before the envelope): in proportion while the drop
    forms, then thinning as the cube of its spread, a little faster than
    its volume would allow, so the spreading water reads as a film rather than a growing lens."""
    r = lens_radius(cover, progress)
    return LENS_DEPTH * (r if r <= LENS_SIZE else LENS_SIZE * (LENS_SIZE / r) ** LENS_THINNING)


def lens_envelope(progress: float) -> float:
    """The water's presence: rising, then flattening to nothing before the end."""
    t = max(0.0, min(1.0, float(progress)))
    return _smooth(t / LENS_RISE) * (1.0 - _smooth((t - LENS_FLATTEN[0]) / (LENS_FLATTEN[1] - LENS_FLATTEN[0])))


def lens_height(progress: float) -> float:
    """The film's meniscus height: 0 once the water has flattened out."""
    return LENS_FILM * lens_envelope(progress)


def lens_cap(reach: float, thickness: float, u: float) -> float:
    """A plano-convex spherical cap of ``thickness`` over radius ``reach`` at ``u`` = distance / reach,
    in the cancellation-free form that stays exact as it flattens."""
    if thickness <= 0.0 or u >= 1.0:
        return 0.0
    big = (reach * reach + thickness * thickness) / (2.0 * thickness)
    d = u * reach
    return reach * reach * (1.0 - u * u) / (math.sqrt(max(big * big - d * d, 0.0)) + big - thickness)


def lens_meniscus(x: float) -> float:
    """The rim's profile: 0 at the edge rising steeply to 1 at ``LENS_RIM`` inside."""
    x = max(0.0, min(1.0, x))
    return math.sqrt(max(0.0, 1.0 - (1.0 - x) * (1.0 - x)))


LIQUID_LENS_GLSL = f"""
const float LENS_SIZE = {LENS_SIZE:.6f};
const float LENS_DEPTH = {LENS_DEPTH:.6f};
const float LENS_FORM = {LENS_FORM:.6f};
const float LENS_SPREAD = {LENS_SPREAD:.6f};
const float LENS_GROW_END = {LENS_GROW_END:.6f};
const float LENS_SPREAD_POWER = {LENS_SPREAD_POWER:.6f};
const float LENS_MAGNIFY = {LENS_MAGNIFY:.6f};
const float LENS_RISE = {LENS_RISE:.6f};
const vec2 LENS_FLATTEN = vec2({LENS_FLATTEN[0]:.6f}, {LENS_FLATTEN[1]:.6f});
const float LENS_FILM = {LENS_FILM:.6f};
const float LENS_RIM = {LENS_RIM:.6f};
const float LENS_ROUND = {LENS_ROUND:.6f};
const float LENS_THINNING = {LENS_THINNING:.6f};
const vec4 LENS_WOBBLE = vec4({", ".join(f"{a:.6f}" for a in LENS_WOBBLE)});
float lensSpread(float t) {{ return pow(clamp((t - LENS_SPREAD) / (LENS_GROW_END - LENS_SPREAD), 0.0, 1.0), LENS_SPREAD_POWER); }}
float lensGlide(float t) {{ return smoothstep(0.0, 1.0, t / LENS_GROW_END); }}
vec2 lensCentre(vec2 start, vec2 end, float t) {{ return mix(start, end, lensGlide(t)); }}
float lensRadius(float cover, float t) {{
    float f = 1.0 - clamp(t / LENS_FORM, 0.0, 1.0);
    return LENS_SIZE * (1.0 - f * f) + (cover - LENS_SIZE) * lensSpread(t);
}}
float lensThickness(float cover, float t) {{
    float r = lensRadius(cover, t);
    return LENS_DEPTH * (r <= LENS_SIZE ? r : LENS_SIZE * pow(LENS_SIZE / r, LENS_THINNING));
}}
float lensEnvelope(float t) {{
    t = clamp(t, 0.0, 1.0);
    return smoothstep(0.0, 1.0, t / LENS_RISE)
         * (1.0 - smoothstep(0.0, 1.0, (t - LENS_FLATTEN.x) / (LENS_FLATTEN.y - LENS_FLATTEN.x)));
}}
float lensCap(float reach, float thickness, float u) {{
    if (thickness <= 0.0 || u >= 1.0) return 0.0;
    float big = (reach * reach + thickness * thickness) / (2.0 * thickness);
    float d = u * reach;
    return reach * reach * (1.0 - u * u) / (sqrt(max(big * big - d * d, 0.0)) + big - thickness);
}}
float lensMeniscus(float x) {{ x = clamp(x, 0.0, 1.0); return sqrt(max(0.0, 1.0 - (1.0 - x) * (1.0 - x))); }}
"""

LIQUID_LENS_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform vec2 uItemSize;\n"
    "uniform float uProgress;\nuniform float uTime;\nuniform float uDuration;\nuniform float uSeed;\n"
    "uniform vec2 uStart;\nuniform vec2 uEnd;\nuniform float uTravel;\nuniform float uBulge;\nuniform float uCover;\n"
    "uniform float uRefraction;\nuniform float uDispersion;\nuniform int uDroplets;\n"
    + REFRACTION_GLSL + LIQUID_LENS_GLSL
    + f"""
const float IOR = {REFRACTION_IOR_WATER:.4f};
const int DROPLETS = {LENS_DROPLETS};
const vec3 LIGHT = vec3(-0.45, 0.6, 1.0);
float aspect;
vec2 centre;
float radius, plateau, thick, envelope, rim, rounding;

float hash1(float n) {{ return fract(sin(n * 12.9898 + uSeed * 0.0137) * 43758.5453); }}

// Signed distance-like value to the wobbling boundary (negative inside), the distance to the
// centre and the boundary's own radius in that direction.
float boundary(vec2 p, vec2 c, float r, float time, out float dist, out float reach) {{
    vec2 d = p - c;
    dist = length(d);
    float a = atan(d.y, d.x);
    float shape = 1.0 + rounding * uBulge * cos(a - uTravel);
    for (int k = 0; k < 4; ++k) {{
        float kf = float(k + 2);
        shape += rounding * LENS_WOBBLE[k] * sin(kf * a + hash1(kf) * 6.2832 + (0.6 + 0.35 * kf) * time * (hash1(kf + 9.0) < 0.5 ? -1.0 : 1.0));
    }}
    reach = r * shape;
    return dist - reach;
}}

// The water's height: the lens's spherical dome plus the film's meniscus rim and ripples.
float waterHeight(vec2 p, out float dome) {{
    float dist, reach;
    float s = boundary(p, centre, radius, uTime, dist, reach);
    dome = 0.0;
    if (s >= 0.0 || envelope <= 0.0) return 0.0;
    dome = lensCap(reach, thick, dist / max(reach, 1e-5));
    float x = -s / rim;
    vec2 q = p * 7.0;
    float ripple = 0.14 * (sin(q.x * 1.3 + q.y * 0.7 + uTime * 2.3 + uSeed) + sin(q.y * 1.1 - q.x * 0.5 - uTime * 1.9))
                 + 0.07 * sin(length(p - centre) * 38.0 - uTime * 5.0);
    return dome + plateau * lensMeniscus(x) * (1.0 + ripple * smoothstep(0.0, 1.0, x));
}}

vec3 droplets(vec2 p, vec3 colour, vec2 uv) {{
    for (int i = 0; i < DROPLETS; ++i) {{
        float fi = float(i);
        float born = mix(0.04, 0.66, hash1(fi * 3.1 + 1.0));
        float age = (uProgress - born) * uDuration;
        if (age <= 0.0 || age > 1.3 || uProgress > 0.9) continue;
        float spread = uBulge > 0.0 ? 2.2 : 6.2832;
        float a = uTravel + (hash1(fi * 5.7 + 2.0) - 0.5) * spread;
        vec2 dir = vec2(cos(a), sin(a));
        vec2 from = lensCentre(uStart, uEnd, born) + dir * lensRadius(uCover, born) * (1.0 + uBulge * cos(a - uTravel));
        vec2 velocity = dir * mix(0.35, 0.8, hash1(fi * 7.3 + 3.0)) + vec2(0.0, mix(0.1, 0.45, hash1(fi * 1.9 + 4.0)));
        vec2 at = from + velocity * age + vec2(0.0, -0.8) * age * age;
        float size = mix(0.006, 0.02, hash1(fi * 2.3 + 5.0)) * smoothstep(0.0, 0.08, age) * (1.0 - smoothstep(0.84, 0.9, uProgress));
        float d0, r0;
        if (boundary(at, centre, radius, uTime, d0, r0) < 0.0) continue;      // back in the water
        vec2 q = (p - at) / max(size, 1e-5);
        float r2 = dot(q, q);
        if (r2 >= 1.0) continue;
        float nz = sqrt(1.0 - r2);
        // A droplet is a tiny ball lens: it shows what lies under it, flipped and gathered.
        vec2 under = uv + vec2(-q.x / aspect, q.y) * size * 0.9;
        vec3 seen = texture(uOldTex, clamp(under, 0.0, 1.0)).rgb;
        vec3 n = vec3(q, nz);
        float highlight = pow(max(dot(n, normalize(normalize(LIGHT) + vec3(0.0, 0.0, 1.0))), 0.0), 60.0);
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
    envelope = lensEnvelope(uProgress);
    plateau = LENS_FILM * envelope;
    thick = lensThickness(uCover, uProgress) * envelope;
    rounding = mix(LENS_ROUND, 1.0, lensSpread(uProgress));
    rim = LENS_RIM * clamp(radius / 0.25, 0.3, 1.0);
    // 1 for the full gliding lens, falling as it spreads thin.
    float volume = thick / (LENS_DEPTH * LENS_SIZE);
    vec3 light = normalize(LIGHT);
    vec2 away = -normalize(light.xy);

    float dist, reach;
    float s = boundary(p, centre, radius, uTime, dist, reach);
    vec3 old = texture(uOldTex, uv).rgb;
    float aa = 1.5 / uItemSize.y;
    // Outside: the old picture under the lens's contact shadow and the shadow it throws away
    // from the light.
    float sd, sr;
    vec2 shift = away * (thick * 1.1 + 0.004);
    float thrown = boundary(p - shift, centre, radius, uTime, sd, sr);
    float shadow = max(0.28 * envelope * exp(-max(s, 0.0) / 0.012),
                       0.5 * volume * (1.0 - smoothstep(-0.03, 0.04 + 0.3 * thick, thrown)));
    vec3 outside = old * (1.0 - shadow);
    vec3 colour;
    if (s > aa) {{
        colour = outside;
    }} else {{
        float e = 1.5 / uItemSize.y;
        float dome, dx0, dx1, dy0, dy1;
        float h = waterHeight(p, dome);
        float hx0 = waterHeight(p - vec2(e, 0.0), dx0), hx1 = waterHeight(p + vec2(e, 0.0), dx1);
        float hy0 = waterHeight(p - vec2(0.0, e), dy0), hy1 = waterHeight(p + vec2(0.0, e), dy1);
        vec2 gradient = vec2(hx1 - hx0, hy1 - hy0) / (2.0 * e);
        vec3 n = layerNormal(gradient);
        float optics = 0.25 + 1.5 * uRefraction;
        // A convex lens draws its view in toward its centre (magnifying it) and crowds it at the rim.
        vec2 magnified = p - (p - centre) * LENS_MAGNIFY * (0.4 + 0.6 * uRefraction) * dome / (LENS_DEPTH * LENS_SIZE);
        vec2 offset = refractionOffset(n, h * optics * 2.0, IOR);
        // Near the picture's own edges the water may not pull in what lies beyond them (clamped
        // samples smear into streaks): the bend fades out over the outer 8%, and what remains is
        // folded back at the edges.
        vec2 border = min(uv, 1.0 - uv);
        float edgeFade = smoothstep(0.0, 0.08, min(border.x * aspect, border.y));
        vec2 viewUv = mix(uv, vec2(magnified.x / aspect + 0.5, 0.5 - magnified.y), edgeFade);
        viewUv = 1.0 - abs(1.0 - abs(viewUv));
        vec3 seen = dispersedSample(uNewTex, viewUv, offset * edgeFade,
                                    uDispersion * envelope * 10.0, aspect);
        // The light the lens gathers glows on its far side, away from the light.
        vec2 focus = centre + away * radius * 0.42;
        float gathered = exp(-dot(p - focus, p - focus) / max(radius * radius * 0.09, 1e-6)) * volume;
        seen *= 1.0 + 0.45 * gathered;
        // Where the glass turns steeply away it shows mostly the dark room: a dark edge.
        float steep = 1.0 - smoothstep(0.55, 0.96, n.z);
        seen *= 1.0 - 0.55 * steep * envelope;
        // Reflections: a dim room brighter toward the light, a soft window and a sharp sun glint.
        vec3 mirror = reflect(vec3(0.0, 0.0, -1.0), n);
        float fresnel = fresnelSchlick(n.z, 0.03);
        float towards = clamp(dot(mirror.xy, normalize(light.xy)) * 1.6, -1.0, 1.0);
        vec3 room = mix(vec3(0.05, 0.06, 0.08), vec3(0.78, 0.85, 0.95), 0.5 + 0.5 * towards);
        vec2 pane = abs(mirror.xy - light.xy) - vec2(0.085, 0.055);
        float window = (1.0 - smoothstep(-0.04, 0.035, max(pane.x, pane.y)))
                     * (1.0 - 0.5 * (1.0 - smoothstep(0.0, 0.012, min(abs(mirror.x - light.x), abs(mirror.y - light.y)))));
        vec3 halfway = normalize(light + vec3(0.0, 0.0, 1.0));
        float glint = pow(max(dot(n, halfway), 0.0), 700.0);
        // The film's rim focuses light into a bright line just inside it (where it curves down).
        float film = h - dome;
        float filmLaplacian = ((hx0 - dx0) + (hx1 - dx1) + (hy0 - dy0) + (hy1 - dy1) - 4.0 * film) / (e * e);
        float caustic = clamp(-filmLaplacian * rim * rim / LENS_FILM * 0.04, 0.0, 1.0) * envelope * (1.0 - volume);
        colour = seen * (1.0 + 0.55 * caustic)
               + envelope * (room * fresnel * 0.9 + vec3(0.92, 0.96, 1.0) * (window * 0.5 + glint * 1.4));
        // Across the edge the two pictures meet over a pixel and a half, under a thin bright rim.
        float inside = smoothstep(aa, -aa, s);
        colour = mix(outside, colour, inside);
        colour += vec3(0.9, 0.95, 1.0) * 0.3 * envelope * exp(-abs(s) * uItemSize.y / 1.2);
    }}
    if (uDroplets != 0) colour = droplets(p, colour, uv);
    FragColor = vec4(colour, 1.0);
}}
"""
)
