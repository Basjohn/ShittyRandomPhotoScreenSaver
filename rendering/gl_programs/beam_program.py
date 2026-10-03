"""Beam: shaders and CPU mirrors (loaded only when Beam renders).

A straight beam of light, like a lightsaber's blade with no hilt, crosses the picture
(``direction``, world units, y up, the picture one unit high) at a steady pace over the first
part of the run (``beam_sweep_end``), starting and ending a full glow reach off the picture. Ahead of it
the old picture, behind it the new one. The beam is a white-hot core in a saturated band of its
colour inside a soft halo, and lights the picture near it; it never flickers, only brightening
slightly as it goes. Every glow term is windowed to exactly nothing at ``BEAM_REACH``, so the
pictures beyond it are exact.

Where it has passed, the new picture is lightly scorched (darker, warmer, with a brief hot rim in
the beam's colour) and cures back to the clean picture, unevenly as if drying. Cure Time sets how
long that takes (``beam_cure``); the sweep shortens to match, so the last point the beam crosses is
cured before the run ends.
Sparks (instanced streaks, nothing stored) spray from the cutting line, fall and fade from white
to the beam's colour; all are gone before the run ends.
"""

from __future__ import annotations

import math

# The share of the run a point takes to cure, from Cure Time's quickest to its slowest.
BEAM_CURE_RANGE = (0.22, 0.55)
# The cure's unevenness: each point cures over the cure time times a factor in this range.
BEAM_CURE_SPREAD = (0.8, 1.25)
# The last point crossed has cured by this much of the run.
BEAM_SETTLED = 0.995
BEAM_CORE = 0.0035
BEAM_HEAT = 0.04
BEAM_SPARKS = 900
BEAM_SPARK_LIFE = (0.22, 0.55)
_DIRECTIONS = {
    "left": (-1.0, 0.0), "right": (1.0, 0.0), "up": (0.0, 1.0), "down": (0.0, -1.0),
    "diag_tl_br": (1.0, -1.0), "diag_tr_bl": (-1.0, -1.0), "diag_bl_tr": (1.0, 1.0), "diag_br_tl": (-1.0, 1.0),
}


def beam_cure(cure_time: float) -> float:
    """The share of the run a point takes to cure (before its unevenness) at Cure Time
    ``cure_time`` (0 quickest, 1 slowest)."""
    lo, hi = BEAM_CURE_RANGE
    return lo + (hi - lo) * max(0.0, min(1.0, float(cure_time)))


def beam_cure_span(cure: float) -> float:
    """The longest any point takes to cure, as a share of the run."""
    return cure * BEAM_CURE_SPREAD[1]


def beam_sweep_end(cure: float) -> float:
    """When the beam leaves the picture: early enough that the last point it crosses cures in time."""
    return BEAM_SETTLED - beam_cure_span(cure)


def beam_direction(code: str, aspect: float) -> tuple[float, float]:
    """The unit direction the beam travels (world, y up); a diagonal runs corner to corner."""
    x, y = _DIRECTIONS[code]
    if x and y:
        x *= aspect
    length = math.hypot(x, y)
    return x / length, y / length


def beam_span(direction: tuple[float, float], aspect: float) -> tuple[float, float]:
    """Where along ``direction`` the picture begins and ends."""
    values = [direction[0] * x * aspect / 2 + direction[1] * y / 2 for x in (-1, 1) for y in (-1, 1)]
    return min(values), max(values)


def beam_reach(glow: float) -> float:
    """How far the beam's light reaches (world units): beyond it, nothing at all."""
    return 0.07 + 0.09 * max(0.0, min(1.0, glow))


def beam_path(near: float, far: float, reach: float) -> tuple[float, float]:
    """Where the beam starts and ends: a full reach off the picture at both ends."""
    return near - reach, far + reach


def beam_line(progress: float, start: float, end: float, sweep_end: float) -> float:
    """The beam's position at ``progress``: a steady pace over the sweep, then gone."""
    return start + (end - start) * max(0.0, min(1.0, float(progress) / sweep_end))


def beam_passed_at(along, start: float, end: float, sweep_end: float):
    """The progress at which the beam crossed the point ``along`` (arrays welcome)."""
    return sweep_end * (along - start) / (end - start)


def beam_intensity(progress: float, sweep_end: float) -> float:
    """The beam's steady brightness, gaining slightly as it goes; it never flickers."""
    return 0.9 + 0.25 * max(0.0, min(1.0, float(progress) / sweep_end))


def beam_spark_life_limit(duration_s: float, sweep_end: float) -> float:
    """The longest a spark may live (seconds) so the last one is gone before the run ends."""
    return min(BEAM_SPARK_LIFE[1], 0.9 * (1.0 - sweep_end) * duration_s)


_COMMON = f"""
uniform float uSweepEnd;     // when the beam leaves the picture (beam_sweep_end)
uniform vec2 uItemSize;
uniform vec2 uDirection;
uniform float uProgress;
uniform float uLine;
uniform vec2 uPath;          // where the beam starts and ends along uDirection
uniform float uReach;
uniform vec3 uColor;
uniform float uGlow;
uniform float uIntensity;
uniform float uSeed;
uint beamHash(uint x) {{
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}}
float beamRandom(uint id, uint salt) {{
    return float(beamHash(id * 0x9e3779b9u + salt * 0x85ebca6bu + uint(uSeed))) / 4294967295.0;
}}
"""

BEAM_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform float uScorch;\nuniform float uCure;\n"
    + _COMMON
    + f"""
float beamNoise(vec2 p) {{
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    uint ix = uint(int(i.x) + 4096), iy = uint(int(i.y) + 4096);
    float a = beamRandom(ix + iy * 8192u, 7u), b = beamRandom(ix + 1u + iy * 8192u, 7u);
    float c = beamRandom(ix + (iy + 1u) * 8192u, 7u), d = beamRandom(ix + 1u + (iy + 1u) * 8192u, 7u);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}}
void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float aspect = uItemSize.x / uItemSize.y;
    vec2 p = vec2((uv.x - 0.5) * aspect, 0.5 - uv.y);
    float along = dot(p, uDirection);
    float offset = along - uLine;                 // ahead of the beam > 0
    vec3 color;
    if (offset > 0.0) {{
        color = texture(uOldTex, uv).rgb;
    }} else {{
        vec3 fresh = texture(uNewTex, uv).rgb;
        float age = uProgress - uSweepEnd * (along - uPath.x) / (uPath.y - uPath.x);
        // Scorched, then cured back to the clean picture, unevenly as if drying.
        float cure = uCure * mix({BEAM_CURE_SPREAD[0]:.6f}, {BEAM_CURE_SPREAD[1]:.6f},
                                 beamNoise(p * 9.0) * 0.6 + beamNoise(p * 23.0) * 0.4);
        float scorch = uScorch * (1.0 - smoothstep(0.0, cure, age));
        float heat = uScorch * (1.0 - smoothstep(0.0, {BEAM_HEAT:.6f}, age));
        color = mix(fresh, fresh * vec3(0.5, 0.37, 0.27) + vec3(0.03, 0.012, 0.0), scorch)
              + uColor * 0.45 * heat * heat;
    }}
    // The beam: steady, windowed to exactly nothing at its reach.
    float d = abs(offset);
    float window = 1.0 - smoothstep(0.5 * uReach, uReach, d);
    if (window > 0.0) {{
        float core = exp(-pow(d / {BEAM_CORE:.6f}, 2.0));
        float band = exp(-pow(d / {3.2 * BEAM_CORE:.6f}, 2.0));
        float halo = exp(-d / (0.26 * uReach));
        vec3 lit = color * uColor * (0.35 + 0.65 * uGlow) * exp(-d / (0.33 * uReach));
        color += window * uIntensity * (lit + vec3(1.0) * core * 1.15 + uColor * (band * 1.25 + halo * uGlow * 0.75));
    }}
    FragColor = vec4(min(color, vec3(1.0)), 1.0);
}}
"""
)

BEAM_SPARK_VERTEX_SOURCE = (
    "#version 460 core\nlayout(location = 0) in vec2 aPosition;\n"
    "uniform mat4 uMatrix;\nuniform float uDurationS;\nuniform float uMaxLife;\nuniform vec2 uSpan;\n"
    "out vec3 vColor;\nout float vAcross;\n"
    + _COMMON
    + f"""
void main() {{
    uint id = uint(gl_InstanceID);
    float aspect = uItemSize.x / uItemSize.y;
    vec2 across = vec2(-uDirection.y, uDirection.x);
    // Born where the beam cuts the picture, at a moment it is on it.
    float first = uSweepEnd * (uSpan.x - uPath.x) / (uPath.y - uPath.x);
    float last = uSweepEnd * (uSpan.y - uPath.x) / (uPath.y - uPath.x);
    float born = mix(first, last, beamRandom(id, 1u));
    float at = uPath.x + (uPath.y - uPath.x) * born / uSweepEnd;
    float reach = 0.5 * sqrt(aspect * aspect + 1.0);
    vec2 origin = uDirection * at + across * mix(-reach, reach, beamRandom(id, 2u));
    float age = (uProgress - born) * uDurationS;
    float life = min(mix({BEAM_SPARK_LIFE[0]:.6f}, {BEAM_SPARK_LIFE[1]:.6f}, beamRandom(id, 3u)), uMaxLife);
    bool inside = abs(origin.x) <= 0.5 * aspect && abs(origin.y) <= 0.5;
    if (!inside || age < 0.0 || age > life) {{
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);    // not alive: outside the clip volume
        vColor = vec3(0.0);
        vAcross = 0.0;
        return;
    }}
    vec2 velocity = uDirection * mix(0.25, 0.95, beamRandom(id, 4u))
                  + across * (beamRandom(id, 5u) - 0.5) * 1.3 + vec2(0.0, 0.45 * beamRandom(id, 6u));
    vec2 gravity = vec2(0.0, -2.4);
    vec2 position = origin + velocity * age + 0.5 * gravity * age * age;
    vec2 now = velocity + gravity * age;
    vec2 heading = normalize(now + vec2(1e-6, 0.0));
    float streak = clamp(length(now) * 0.045, 0.006, 0.06);
    vec2 world = position - heading * streak * (1.0 - aPosition.x)
               + vec2(-heading.y, heading.x) * 0.0036 * (aPosition.y - 0.5);
    float fade = 1.0 - age / life;
    vColor = mix(vec3(1.0, 0.98, 0.92), uColor, smoothstep(0.0, 0.6, age / life)) * fade * fade * 1.9 * uIntensity;
    vAcross = aPosition.y - 0.5;
    vec2 item = vec2((world.x / aspect + 0.5) * uItemSize.x, (0.5 - world.y) * uItemSize.y);
    gl_Position = uMatrix * vec4(item, 0.0, 1.0);
}}
"""
)

BEAM_SPARK_FRAGMENT_SOURCE = """#version 460 core
in vec3 vColor;
in float vAcross;
out vec4 FragColor;
void main() {
    FragColor = vec4(vColor * (1.0 - 4.0 * vAcross * vAcross), 1.0);
}
"""
