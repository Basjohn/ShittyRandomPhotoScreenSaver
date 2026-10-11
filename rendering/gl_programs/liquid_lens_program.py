"""Liquid Lens: the run's plan (CPU) and its shader (loaded only when Liquid Lens renders).

A small, thick lens of water appears in the middle of the old picture and grows, showing the new
picture through it. It then hops from pitstop to pitstop on a seeded, semi-random path, easing
between them; at each stop it swells to a larger size with a springy liquid settle, the view
through it twisting as it travels and as it grows, and rings of ripples run out from its rim
across the old picture, surging as it arrives. At the last stop (``stops``, 1-8: 1 floods from
the middle) it gives way and spreads until it covers the picture, thinning to a film, and the
water flattens out before the end.

The lens reads as solid glass: a plano-convex spherical cap (``LENS_DEPTH`` as thick as its
radius) magnifying its centre and bending hard at its rim through the shared refraction helpers
(``rendering/gl_programs/refraction.py``), a window-shaped key-light reflection and a sharp glint,
a Fresnel reflection of a dim room around the rim, a dark glass edge, the light it gathers glowing
on its far side and a soft shadow thrown away from the light.

Everything that moves is planned on the CPU (``lens_plan``, ``lens_state``: picture heights,
centred, y up) and reaches the shader as a few uniforms per frame.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from rendering.gl_programs.liquid_lens_options import LIQUID_LENS_STOPS_RANGE
from rendering.gl_programs.refraction import REFRACTION_GLSL, REFRACTION_IOR_WATER

LENS_FIRST = 0.085          # the lens's radius at its first stop (the middle), picture heights
LENS_LAST = 0.23            # at the last pitstop before the flood
LENS_DEPTH = 0.5            # its thickness at the centre, a share of its radius
LENS_DWELL = 1.0            # schedule weights: a pitstop's growth against a hop between stops
LENS_HOP = 1.35
LENS_SPREAD = (0.72, 0.87)  # the flood from the last stop until the lens covers the picture
LENS_SPREAD_POWER = 1.6
LENS_THINNING = 3.0         # the dome thins as this power of its growth while it floods
LENS_RISE = 0.04
LENS_FLATTEN = (0.86, 0.97)
LENS_FILM = 0.012           # the film's meniscus height, picture heights
LENS_RIM = 0.07             # meniscus width at full size
LENS_WOBBLE = (0.045, 0.03, 0.02, 0.014)       # modes 2-5, a share of the radius
LENS_ROUND = 0.3            # the travelling lens keeps this share of the wobble
LENS_BULGE = 0.12           # the most it stretches toward its travel
LENS_TWIST = 0.85           # radians: the view's twist at the lens centre at the height of a hop
LENS_MAGNIFY = 0.3          # how far the lens draws its centre's view in (1 / (1 - x) magnification)
LENS_MARGIN = 0.04          # a pitstop keeps the whole lens this far inside the picture
RIPPLE_SURGE = 1.0          # ripple strength on arriving at a stop, decaying over RIPPLE_DECAY seconds
RIPPLE_CALM = 0.3           # the ripples the lens keeps up while it exists
RIPPLE_DECAY = 0.8
RIPPLE_WAVELENGTH = 0.042   # picture heights
RIPPLE_SPEED = 0.11         # picture heights per second, outward
RIPPLE_REACH = 0.13         # how far out the rings carry
SPRING = (5.0, 10.0)        # the settle on growing: decay and angular frequency per unit of dwell


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _smoother(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * x * (x * (6.0 * x - 15.0) + 10.0)


def _spring(u: float) -> float:
    """0 -> 1 with one soft overshoot: a liquid settling into its new size."""
    u = max(0.0, min(1.0, u))
    if u >= 1.0:
        return 1.0
    return 1.0 - math.exp(-SPRING[0] * u) * math.cos(SPRING[1] * u) * (1.0 - u)


def lens_cover(end: tuple[float, float], aspect: float) -> float:
    """The flood radius: past the farthest corner from the last stop even where the wobbling,
    stretched boundary is narrowest, plus the rim."""
    hw = 0.5 * aspect
    farthest = max(math.hypot(cx - end[0], cy - end[1]) for cx in (-hw, hw) for cy in (-0.5, 0.5))
    return (farthest + LENS_RIM + 0.02) / (1.0 - sum(LENS_WOBBLE) - LENS_BULGE)


@dataclass(frozen=True)
class LensPlan:
    """One run's stops: positions, the radius reached at each pitstop, and the schedule."""

    stops: tuple[tuple[float, float], ...]
    radii: tuple[float, ...]                               # one per pitstop (every stop but the last)
    segments: tuple[tuple[str, int, float, float], ...]    # (dwell | hop, stop index, start, end)
    cover: float


def lens_radii(stops: int) -> tuple[float, ...]:
    """The radius at each pitstop, growing geometrically from the first to the last."""
    pitstops = max(1, stops - 1)
    if pitstops == 1:
        return (LENS_FIRST if stops > 1 else LENS_LAST,)
    return tuple(LENS_FIRST * (LENS_LAST / LENS_FIRST) ** (k / (pitstops - 1)) for k in range(pitstops))


def lens_plan(stops: int, seed: int, aspect: float) -> LensPlan:
    """The run's path: the middle first, then seeded semi-random pitstops a comfortable hop apart,
    each keeping the lens inside the picture, then the stop it floods from."""
    low, high = LIQUID_LENS_STOPS_RANGE
    stops = max(low, min(high, int(stops)))
    rng = random.Random(seed)
    radii = lens_radii(stops)
    hw = 0.5 * aspect
    positions = [(0.0, 0.0)]
    for index in range(1, stops):
        # The lens arrives at its departing size and grows here, so it must fit the size it grows to.
        radius = radii[index] if index < len(radii) else radii[-1]
        bound = (max(0.0, hw - radius - LENS_MARGIN), max(0.0, 0.5 - radius - LENS_MARGIN))
        previous = positions[-1]
        best, best_score = previous, -1e9
        for _candidate in range(24):
            point = (rng.uniform(-bound[0], bound[0]), rng.uniform(-bound[1], bound[1]))
            hop = math.hypot(point[0] - previous[0], point[1] - previous[1])
            nearest = min(math.hypot(point[0] - p[0], point[1] - p[1]) for p in positions)
            # A hop of about 0.45 picture heights, away from where it has already been.
            score = -abs(hop - 0.45) * 2.0 + min(nearest, 0.5) + rng.uniform(0.0, 0.15)
            if score > best_score:
                best, best_score = point, score
        positions.append(best)
    if stops == 1:
        weights = [("dwell", 0, LENS_DWELL)]
    else:
        weights = []
        for index in range(stops - 1):
            weights += [("dwell", index, LENS_DWELL), ("hop", index, LENS_HOP)]
    total = sum(weight for _kind, _index, weight in weights)
    segments, at = [], 0.0
    for kind, index, weight in weights:
        span = LENS_SPREAD[0] * weight / total
        segments.append((kind, index, at, at + span))
        at += span
    return LensPlan(tuple(positions), radii, tuple(segments), lens_cover(positions[-1], aspect))


@dataclass(frozen=True)
class LensState:
    centre: tuple[float, float]
    radius: float
    thickness: float              # the dome's centre thickness (with the envelope)
    reference: float              # the full dome's thickness at this size: magnification and glass
    envelope: float
    rounding: float
    bulge: tuple[float, float]    # direction of travel times how far the lens stretches
    twist: float
    ripple: float
    spread: float


def lens_envelope(progress: float) -> float:
    """The water's presence: rising, then flattening to nothing before the end."""
    t = max(0.0, min(1.0, float(progress)))
    return _smooth(t / LENS_RISE) * (1.0 - _smooth((t - LENS_FLATTEN[0]) / (LENS_FLATTEN[1] - LENS_FLATTEN[0])))


def lens_height(progress: float) -> float:
    """The film's meniscus height: 0 once the water has flattened out."""
    return LENS_FILM * lens_envelope(progress)


def lens_spread(progress: float) -> float:
    return max(0.0, min(1.0, (progress - LENS_SPREAD[0]) / (LENS_SPREAD[1] - LENS_SPREAD[0]))) ** LENS_SPREAD_POWER


def lens_state(plan: LensPlan, progress: float, duration_s: float) -> LensState:
    t = max(0.0, min(1.0, float(progress)))
    envelope = lens_envelope(t)
    last = len(plan.stops) - 1
    centre, radius, base = plan.stops[last], plan.radii[-1], plan.radii[-1]
    velocity, twist = (0.0, 0.0), 0.0
    arrivals = [0.0] + [end for kind, _index, _start, end in plan.segments if kind == "hop"]
    for kind, index, start, end in plan.segments:
        if not start <= t < end:
            continue
        u = (t - start) / (end - start)
        sign = -1.0 if index % 2 else 1.0
        if kind == "dwell":
            grown_from = plan.radii[index - 1] if index > 0 else 0.0
            centre = plan.stops[index]
            radius = grown_from + (plan.radii[index] - grown_from) * _spring(u)
            base = plan.radii[index]
            twist = 0.45 * LENS_TWIST * sign * math.sin(math.pi * u)
        else:
            a, b = plan.stops[index], plan.stops[index + 1]
            g = _smoother(u)
            centre = (a[0] + (b[0] - a[0]) * g, a[1] + (b[1] - a[1]) * g)
            radius = base = plan.radii[index]
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy) or 1.0
            # Picture heights per second at this moment (smootherstep's slope peaks at 1.875).
            speed = 30.0 * u * u * (1.0 - u) * (1.0 - u) * length / max(1e-6, (end - start) * duration_s)
            stretch = min(LENS_BULGE, 0.12 * speed)
            velocity = (dx / length * stretch, dy / length * stretch)
            twist = LENS_TWIST * sign * math.sin(math.pi * u)
        break
    spread = lens_spread(t)
    if t >= LENS_SPREAD[0]:
        centre = plan.stops[last]
        radius = base + (plan.cover - base) * spread
    reference = LENS_DEPTH * base
    thickness = LENS_DEPTH * (radius if radius <= base else base * (base / radius) ** LENS_THINNING)
    elapsed = t * duration_s
    surge = sum(RIPPLE_SURGE * math.exp(-(elapsed - at * duration_s) / RIPPLE_DECAY) for at in arrivals if at <= t)
    ripple = (RIPPLE_CALM + surge) * (1.0 - spread) * envelope
    return LensState(centre, radius, thickness * envelope, reference, envelope,
                     LENS_ROUND + (1.0 - LENS_ROUND) * spread, velocity, twist * (1.0 - spread),
                     ripple, spread)


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


def lens_twist_angle(twist: float, u: float) -> float:
    """The view's rotation at ``u`` = distance / radius: full at the centre, none at the rim."""
    u = max(0.0, min(1.0, u))
    return twist * (1.0 - u * u) ** 2


LIQUID_LENS_GLSL = f"""
const float LENS_MAGNIFY = {LENS_MAGNIFY:.6f};
const float LENS_FILM = {LENS_FILM:.6f};
const float LENS_RIM = {LENS_RIM:.6f};
const vec4 LENS_WOBBLE = vec4({", ".join(f"{a:.6f}" for a in LENS_WOBBLE)});
const float RIPPLE_K = {2.0 * math.pi / RIPPLE_WAVELENGTH:.6f};
const float RIPPLE_W = {2.0 * math.pi / RIPPLE_WAVELENGTH * RIPPLE_SPEED:.6f};
const float RIPPLE_REACH = {RIPPLE_REACH:.6f};
float lensCap(float reach, float thickness, float u) {{
    if (thickness <= 0.0 || u >= 1.0) return 0.0;
    float big = (reach * reach + thickness * thickness) / (2.0 * thickness);
    float d = u * reach;
    return reach * reach * (1.0 - u * u) / (sqrt(max(big * big - d * d, 0.0)) + big - thickness);
}}
float lensMeniscus(float x) {{ x = clamp(x, 0.0, 1.0); return sqrt(max(0.0, 1.0 - (1.0 - x) * (1.0 - x))); }}
float lensTwistAngle(float twist, float u) {{ u = clamp(u, 0.0, 1.0); float f = 1.0 - u * u; return twist * f * f; }}
"""

LIQUID_LENS_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform vec2 uItemSize;\n"
    "uniform float uTime;\nuniform float uSeed;\n"
    "uniform vec2 uCentre;\nuniform float uRadius;\nuniform float uThick;\nuniform float uReference;\n"
    "uniform float uEnvelope;\nuniform float uRound;\nuniform vec2 uBulge;\nuniform float uTwist;\n"
    "uniform float uRipple;\nuniform float uRefraction;\nuniform float uDispersion;\n"
    + REFRACTION_GLSL + LIQUID_LENS_GLSL
    + f"""
const float IOR = {REFRACTION_IOR_WATER:.4f};
const vec3 LIGHT = vec3(-0.45, 0.6, 1.0);
float aspect, rim, plateau;

float hash1(float n) {{ return fract(sin(n * 12.9898 + uSeed * 0.0137) * 43758.5453); }}

// Signed distance-like value to the wobbling, stretched boundary (negative inside), the distance
// to the centre and the boundary's own radius in that direction.
float boundary(vec2 p, vec2 c, out float dist, out float reach) {{
    vec2 d = p - c;
    dist = length(d);
    float a = atan(d.y, d.x);
    float stretch = length(uBulge);
    float shape = 1.0 + (stretch > 0.0 ? stretch * cos(a - atan(uBulge.y, uBulge.x)) : 0.0);
    for (int k = 0; k < 4; ++k) {{
        float kf = float(k + 2);
        shape += uRound * LENS_WOBBLE[k] * sin(kf * a + hash1(kf) * 6.2832 + (0.6 + 0.35 * kf) * uTime * (hash1(kf + 9.0) < 0.5 ? -1.0 : 1.0));
    }}
    reach = uRadius * shape;
    return dist - reach;
}}

// The water's height: the lens's spherical dome plus the film's meniscus rim and ripples.
float waterHeight(vec2 p, out float dome) {{
    float dist, reach;
    float s = boundary(p, uCentre, dist, reach);
    dome = 0.0;
    if (s >= 0.0 || uEnvelope <= 0.0) return 0.0;
    dome = lensCap(reach, uThick, dist / max(reach, 1e-5));
    float x = -s / rim;
    vec2 q = p * 7.0;
    float ripple = 0.14 * (sin(q.x * 1.3 + q.y * 0.7 + uTime * 2.3 + uSeed) + sin(q.y * 1.1 - q.x * 0.5 - uTime * 1.9))
                 + 0.07 * sin(dist * 38.0 - uTime * 5.0);
    return dome + plateau * lensMeniscus(x) * (1.0 + ripple * smoothstep(0.0, 1.0, x));
}}

void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    aspect = uItemSize.x / uItemSize.y;
    vec2 p = vec2((uv.x - 0.5) * aspect, 0.5 - uv.y);
    plateau = LENS_FILM * uEnvelope;
    rim = LENS_RIM * clamp(uRadius / 0.25, 0.3, 1.0);
    float volume = uReference > 0.0 ? clamp(uThick / uReference, 0.0, 1.0) : 0.0;
    vec3 light = normalize(LIGHT);
    vec2 away = -normalize(light.xy);
    vec2 border = min(uv, 1.0 - uv);
    float edgeFade = smoothstep(0.0, 0.08, min(border.x * aspect, border.y));

    float dist, reach;
    float s = boundary(p, uCentre, dist, reach);
    float aa = 1.5 / uItemSize.y;
    // Outside: the old picture, rippled by rings running out from the rim, under the lens's
    // contact shadow and the shadow it throws away from the light.
    float beyond = max(s, 0.0);
    float rings = uRipple * exp(-beyond / RIPPLE_REACH);
    float phase = beyond * RIPPLE_K - uTime * RIPPLE_W;
    vec2 outward = dist > 1e-5 ? (p - uCentre) / dist : vec2(0.0);
    vec2 ringShift = outward * rings * 0.011 * sin(phase) * edgeFade;
    vec3 old = texture(uOldTex, uv - vec2(ringShift.x / aspect, -ringShift.y)).rgb;
    // Each ring's slope shades the picture and its crest catches the light.
    old *= 1.0 + 0.14 * rings * cos(phase);
    old += vec3(0.9, 0.95, 1.0) * 0.16 * rings * pow(max(cos(phase), 0.0), 6.0);
    float sd, sr;
    vec2 shift = away * (uThick * 1.1 + 0.004);
    float thrown = boundary(p - shift, uCentre, sd, sr);
    float shadow = max(0.28 * uEnvelope * exp(-beyond / 0.012),
                       0.5 * volume * uEnvelope * (1.0 - smoothstep(-0.03, 0.04 + 0.3 * uThick, thrown)));
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
        // A convex lens draws its view in toward its centre (magnifying it) and crowds it at the
        // rim; the view through it twists, most at the centre.
        vec2 rel = (p - uCentre) * (1.0 - LENS_MAGNIFY * (0.4 + 0.6 * uRefraction) * dome / max(uReference, 1e-4));
        float angle = lensTwistAngle(uTwist, dist / max(reach, 1e-5));
        vec2 viewed = uCentre + vec2(cos(angle) * rel.x - sin(angle) * rel.y, sin(angle) * rel.x + cos(angle) * rel.y);
        vec2 offset = refractionOffset(n, h * optics * 2.0, IOR);
        // Near the picture's own edges the water may not pull in what lies beyond them: the bend
        // fades out over the outer 8%, and what remains is folded back at the edges.
        vec2 viewUv = mix(uv, vec2(viewed.x / aspect + 0.5, 0.5 - viewed.y), edgeFade);
        viewUv = 1.0 - abs(1.0 - abs(viewUv));
        vec3 seen = dispersedSample(uNewTex, viewUv, offset * edgeFade, uDispersion * uEnvelope * 10.0, aspect);
        // The light the lens gathers glows on its far side, away from the light.
        vec2 focus = uCentre + away * uRadius * 0.42;
        float gathered = exp(-dot(p - focus, p - focus) / max(uRadius * uRadius * 0.09, 1e-6)) * volume;
        seen *= 1.0 + 0.45 * gathered;
        // Where the glass turns steeply away it shows mostly the dark room: a dark edge.
        float steep = 1.0 - smoothstep(0.55, 0.96, n.z);
        seen *= 1.0 - 0.55 * steep * uEnvelope;
        // Reflections: a dim room brighter toward the light, a soft window and a sharp glint.
        vec3 mirror = reflect(vec3(0.0, 0.0, -1.0), n);
        float fresnel = fresnelSchlick(n.z, 0.03);
        float towards = clamp(dot(mirror.xy, normalize(light.xy)) * 1.6, -1.0, 1.0);
        vec3 room = mix(vec3(0.05, 0.06, 0.08), vec3(0.78, 0.85, 0.95), 0.5 + 0.5 * towards);
        vec2 pane = abs(mirror.xy - light.xy) - vec2(0.085, 0.055);
        float window = (1.0 - smoothstep(-0.04, 0.035, max(pane.x, pane.y)))
                     * (1.0 - 0.5 * (1.0 - smoothstep(0.0, 0.012, min(abs(mirror.x - light.x), abs(mirror.y - light.y)))));
        vec3 halfway = normalize(light + vec3(0.0, 0.0, 1.0));
        float glint = pow(max(dot(n, halfway), 0.0), 700.0);
        // The film's rim focuses light into a bright line just inside it once the lens floods.
        float film = h - dome;
        float filmLaplacian = ((hx0 - dx0) + (hx1 - dx1) + (hy0 - dy0) + (hy1 - dy1) - 4.0 * film) / (e * e);
        float caustic = clamp(-filmLaplacian * rim * rim / LENS_FILM * 0.04, 0.0, 1.0) * uEnvelope * (1.0 - volume);
        colour = seen * (1.0 + 0.55 * caustic)
               + uEnvelope * (room * fresnel * 0.9 + vec3(0.92, 0.96, 1.0) * (window * 0.5 + glint * 1.4));
        // Across the edge the two pictures meet over a pixel and a half, under a thin bright rim.
        float inside = smoothstep(aa, -aa, s);
        colour = mix(outside, colour, inside);
        colour += vec3(0.9, 0.95, 1.0) * 0.3 * uEnvelope * exp(-abs(s) * uItemSize.y / 1.2);
    }}
    FragColor = vec4(colour, 1.0);
}}
"""
)
