"""Shockwave Grid: shaders and CPU mirrors (loaded only when the mode renders).

A neon grid floor seen in perspective. Musical onsets (the frame runtime's bounded event
ring, ``ShockwaveGridFrame.events``: each event's age, origin and strength, aged on the
logical clock at capture) launch circular shockwaves across it: a raised crest with a
shallow trough behind, travelling outward at ``speed`` and fading over ``SHOCKWAVE_DECAY``
seconds. ``shockwave_strength`` turns an onset into a strength (0 .. ``SHOCKWAVE_MAX_STRENGTH``):
near-silence gives none, a big hit far more than a medium one; above 1 a wave grows taller
(more slowly), wider, brighter, and trails an echo ring. The crest brightens the grid lines
toward the crest colour and its light blooms. Spectrum's bars raise a ridge along the far edge
(the horizon), brighter where they are loudest, and a soft idle swell sweeps from side to side,
so the grid moves between onsets too. The grid may scroll toward the viewer on the frame's
animation time.

World units are the bar field's height: x across, y up, z toward the viewer; the grid spans
``|x| <= half width`` and ``-SHOCKWAVE_DEPTH <= z <= 0``. The view turns about the vertical axis
(a full circle) and tilts down (0 level .. 90 degrees straight down) about the grid's centre,
then the camera looks from ``shockwave_camera`` away (farther for wider grids, so no point ever
reaches it). ``shockwave_fit`` frames the visible grid (and the highest horizon ridge) from
just above the field's bottom to just below its top, whatever the view; the grid's sides may
run past the field's sides, where they fade. The surface is the shared triangle grid displaced in the vertex shader (one draw),
the events one std430 array on the stream ring; lines are drawn analytically in the fragment
shader (anti-aliased by their screen-space width) and emit their light into the overlay's
emission attachment for the bloom.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_ORBIT_GLSL, Scene3DStorageLayout, scene3d_orbit_project

SHOCKWAVE_MAX_TILT = math.radians(90.0)
SHOCKWAVE_MAX_TURN = math.radians(180.0)
SHOCKWAVE_CAMERA = 2.6           # the camera's least distance from the grid's centre
SHOCKWAVE_NEAR_LINE = 0.96         # where the fit puts the lowest of the grid (share of the field)
SHOCKWAVE_FAR_LINE = 0.1           # and the highest
SHOCKWAVE_VISIBLE = 0.82           # the share of the grid's depth and half width before it fades
SHOCKWAVE_MAX_RIDGE = 0.6          # the horizon ridge's height at Horizon 1 and a full bar
SHOCKWAVE_DEPTH = 2.4             # the grid's length into the distance, in field heights
SHOCKWAVE_WIDTH = 0.16            # a crest's half width
SHOCKWAVE_DECAY = 1.1             # seconds for a wave to fall to 1/e
SHOCKWAVE_LIFETIME = 3.2          # seconds after which an event is dropped (all but invisible)
SHOCKWAVE_CAPACITY = 16           # events held at once (the bounded event buffer)
SHOCKWAVE_MIN_GAP = 0.09          # seconds between two admitted onsets
SHOCKWAVE_HORIZON_REACH = 0.45    # the far share of the grid the spectrum ridge rises over
SHOCKWAVE_CEILING = 0.95          # Spectrum's tallest bar, in field heights
SHOCKWAVE_MAX_BARS = 64
SHOCKWAVE_GRID_CELLS = (180, 120)  # the displaced surface's tessellation (columns, rows)
# Onset strength (``shockwave_strength``): absolute loudness below the first edge makes no wave;
# presence (loudness against the running level) below its first edge neither, so near-silence
# inside a loud track stays calm; an onset's presence against the track's usual onsets
# (``SHOCKWAVE_USUAL_RATE`` adapts that) sets how much it stands out.
SHOCKWAVE_QUIET = (0.08, 0.6)
SHOCKWAVE_PRESENCE = (0.15, 0.8)
SHOCKWAVE_USUAL_RATE = 0.12
SHOCKWAVE_MIN_STRENGTH = 0.12     # weaker onsets make no wave
SHOCKWAVE_MAX_STRENGTH = 2.0
SHOCKWAVE_ECHO_SPEED = 0.62       # a big hit's echo ring, as a share of the wave speed
SHOCKWAVE_IDLE_PERIOD = 11.0      # seconds for the idle swell to sweep across and back
SHOCKWAVE_IDLE_HEIGHT = 0.35      # the idle swell's height at Idle Swell 1, as a share of a wave's

SHOCKWAVE_EVENTS = Scene3DStorageLayout.of(
    "ShockwaveEvents", "ShockwaveEvent",
    (("age", "float"), ("x", "float"), ("z", "float"), ("strength", "float")), array="events")


def shockwave_grid_cells(tier_cells: int) -> tuple[int, int]:
    """The displaced grid's (columns, rows) for a 3D Detail tier: its density along the width,
    never more than ``SHOCKWAVE_GRID_CELLS``, the rows keeping the cells square."""
    columns = max(2, min(SHOCKWAVE_GRID_CELLS[0], int(tier_cells)))
    return columns, max(2, round(columns * SHOCKWAVE_GRID_CELLS[1] / SHOCKWAVE_GRID_CELLS[0]))


def shockwave_half_width(aspect: float) -> float:
    """The grid's half width for a field ``aspect`` times wider than tall (wide enough that
    its sides leave the view when it is turned)."""
    return 0.8 * max(1.0, float(aspect)) + 0.9


def shockwave_wave_speed(speed: float) -> float:
    """How fast a crest travels (field heights per second) for Wave Speed 0..1."""
    return 0.6 + 1.4 * max(0.0, min(1.0, float(speed)))


def shockwave_amplitude(height: float) -> float:
    """A full-strength wave's crest height (field heights) for Wave Height 0..1."""
    return 0.04 + 0.3 * max(0.0, min(1.0, float(height)))


def shockwave_strength(magnitude: float, loudness: float, presence: float, usual: float) -> float:
    """A wave's strength (0 .. ``SHOCKWAVE_MAX_STRENGTH``) for an onset (``MusicalOnset``'s
    magnitude, loudness and presence) when the track's usual onset presence is ``usual``."""
    quiet = _smoothstep(SHOCKWAVE_QUIET[0], SHOCKWAVE_QUIET[1], float(loudness))
    present = _smoothstep(SHOCKWAVE_PRESENCE[0], SHOCKWAVE_PRESENCE[1], float(presence))
    emphasis = max(0.5, min(2.0, float(presence) / max(float(usual), 1e-3))) ** 1.5
    hit = 0.4 + 0.6 * max(0.0, min(1.0, float(magnitude) / 3.0))
    return max(0.0, min(SHOCKWAVE_MAX_STRENGTH, quiet * present * emphasis * hit))


def shockwave_idle(height: float, idle: float, time: float, half_width: float) -> tuple[float, float]:
    """The idle swell: (height, centre x) at ``time`` seconds of animation for Wave Height and
    Idle Swell 0..1: a soft ridge sweeping smoothly from one side to the other and back."""
    amplitude = shockwave_amplitude(height) * SHOCKWAVE_IDLE_HEIGHT * max(0.0, min(1.0, float(idle)))
    return amplitude, 1.1 * float(half_width) * math.sin(2.0 * math.pi * float(time) / SHOCKWAVE_IDLE_PERIOD)


def shockwave_origin(serial: int, kind: str) -> tuple[float, float]:
    """Where the ``serial``-th event starts, deterministically: kicks near the front middle,
    snares and the rest further out. x is a share of the half width; z is in field heights."""
    def unit(salt: int) -> float:
        value = (serial * 2654435761 + salt * 40503) & 0xFFFFFFFF
        value ^= value >> 15
        value = (value * 2246822519) & 0xFFFFFFFF
        value ^= value >> 13
        return value / 4294967295.0

    spread, near, far = (0.35, 0.18, 0.45) if kind == "kick" else (0.65, 0.25, 0.8)
    x = (unit(1) * 2.0 - 1.0) * spread
    z = -SHOCKWAVE_DEPTH * (near + (far - near) * unit(2))
    return x, z


def shockwave_height(x: float, z: float, events, amplitude: float, speed: float) -> tuple[float, float]:
    """CPU mirror of ``shockwaveHeight``: (surface height, crest light) at grid point (x, z)
    from ``events`` [(age, ox, oz, strength), ...] (``ox`` already in world units)."""
    height = crest = 0.0
    for age, ox, oz, strength in events:
        fade = math.exp(-age / SHOCKWAVE_DECAY) * _smoothstep(0.0, 0.06, age)
        over = max(0.0, strength - 1.0)                    # a big hit's share above a full wave
        lift = min(strength, 1.0) + 0.5 * over             # taller, but more slowly
        width = SHOCKWAVE_WIDTH * (1.0 + 0.6 * over)       # and wider
        distance = math.hypot(x - ox, z - oz)
        d = distance - speed * age
        bump = math.exp(-(d / width) ** 2)
        trough = math.exp(-((d + 1.8 * width) / width) ** 2)
        echo = math.exp(-((distance - SHOCKWAVE_ECHO_SPEED * speed * age) / width) ** 2)
        height += amplitude * fade * (lift * (bump - 0.35 * trough) + 0.6 * over * echo)
        crest += fade * (strength * bump + 0.6 * over * echo)
    return height, crest


def shockwave_camera(half_width: float) -> float:
    """The camera's distance from the grid's centre: at least ``SHOCKWAVE_CAMERA`` and beyond the
    grid's farthest reach, so turned or wide grids never reach it."""
    return max(SHOCKWAVE_CAMERA, 1.15 * math.hypot(float(half_width), 0.5 * SHOCKWAVE_DEPTH))


def shockwave_project(point: tuple[float, float, float], tilt: float, turn: float,
                      camera: float = SHOCKWAVE_CAMERA) -> tuple[float, float, float]:
    """CPU mirror of ``shockwaveProject``: (screen x, screen y up, view depth) of a world point."""
    return scene3d_orbit_project(point, tilt, turn, camera=camera, pivot=(0.0, 0.0, -0.5 * SHOCKWAVE_DEPTH))


def shockwave_fit(tilt: float, turn: float, half_width: float, ridge: float) -> tuple[float, float]:
    """(scale, base): an item point is ``field top + height * (base - screen y * scale)`` and
    ``field centre x + height * screen x * scale``, so the visible grid (its faded edges and the
    horizon ridge up to ``ridge``) spans ``SHOCKWAVE_FAR_LINE`` .. ``SHOCKWAVE_NEAR_LINE`` of the
    field's height. Fixed per view and shape, never per frame of music."""
    camera = shockwave_camera(half_width)
    reach = SHOCKWAVE_VISIBLE * half_width
    points = [shockwave_project((x, y, z), tilt, turn, camera)
              for x in (-reach, 0.0, reach)
              for z in (0.0, -SHOCKWAVE_VISIBLE * SHOCKWAVE_DEPTH)
              for y in ((0.0, ridge) if z < 0.0 else (0.0,))]
    low = min(p[1] for p in points)
    high = max(p[1] for p in points)
    scale = (SHOCKWAVE_NEAR_LINE - SHOCKWAVE_FAR_LINE) / max(high - low, 1e-3)
    return scale, SHOCKWAVE_NEAR_LINE + low * scale


def shockwave_event_records(events, half_width: float) -> list[dict[str, float]]:
    """The std430 records for ``events`` [(age, x share, z, strength), ...]: x in world units."""
    return [{"age": float(age), "x": float(x) * half_width, "z": float(z), "strength": float(strength)}
            for age, x, z, strength in events[:SHOCKWAVE_CAPACITY]]


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


_COMMON = f"""
const float SHOCKWAVE_DEPTH = {SHOCKWAVE_DEPTH:.6f};
const float SHOCKWAVE_WIDTH = {SHOCKWAVE_WIDTH:.6f};
const float SHOCKWAVE_DECAY = {SHOCKWAVE_DECAY:.6f};
const float SHOCKWAVE_ECHO_SPEED = {SHOCKWAVE_ECHO_SPEED:.6f};
uniform mat4 uMatrix;
uniform vec4 uField;          // field in item coordinates: left, top, width, height
uniform vec2 uView;           // tilt, turn (radians)
uniform float uCamera;        // the camera's distance from the grid's centre (shockwave_camera)
uniform vec2 uFit;            // scale, base (shockwave_fit)
uniform float uHalfWidth;     // the grid's half width (field heights)
uniform int uEventCount;
uniform vec2 uWave;           // crest amplitude (field heights), speed (field heights per second)
uniform float uHorizon;       // the spectrum ridge's height (field heights at a full bar)
uniform vec2 uIdle;           // the idle swell: height (field heights), centre x (shockwave_idle)
uniform int uBarCount;
uniform float uBars[{SHOCKWAVE_MAX_BARS}];
uniform float uHeightScale;
float shockwaveSmooth(float edge0, float edge1, float value) {{
    float t = clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}}
// (surface height, crest light) at grid point (x, z): the mirror of shockwave_height.
vec2 shockwaveHeight(vec2 p) {{
    float height = 0.0, crest = 0.0;
    for (int i = 0; i < uEventCount; ++i) {{
        ShockwaveEvent e = events[i];
        float fade = exp(-e.age / SHOCKWAVE_DECAY) * shockwaveSmooth(0.0, 0.06, e.age);
        float over = max(0.0, e.strength - 1.0);
        float lift = min(e.strength, 1.0) + 0.5 * over;
        float width = SHOCKWAVE_WIDTH * (1.0 + 0.6 * over);
        float distance = length(p - vec2(e.x, e.z));
        float d = distance - uWave.y * e.age;
        float bump = exp(-pow(d / width, 2.0));
        float trough = exp(-pow((d + 1.8 * width) / width, 2.0));
        float echo = exp(-pow((distance - SHOCKWAVE_ECHO_SPEED * uWave.y * e.age) / width, 2.0));
        height += uWave.x * fade * (lift * (bump - 0.35 * trough) + 0.6 * over * echo);
        crest += fade * (e.strength * bump + 0.6 * over * echo);
    }}
    // The idle swell: a soft ridge along z, its centre sweeping across x; a little light.
    float swell = exp(-pow((p.x - uIdle.y) / 0.55, 2.0)) * (0.75 + 0.25 * sin(2.4 * p.y + 0.8 * uIdle.y));
    height += uIdle.x * swell;
    crest += 0.6 * swell * uIdle.x / max(uWave.x, 1e-3);
    return vec2(height, crest);
}}
// Spectrum's ridge along the far edge: the bar under x, by Spectrum's level transfer.
float shockwaveRidge(vec2 p) {{
    if (uBarCount <= 0 || uHorizon <= 0.0) return 0.0;
    float u = clamp(p.x / (2.0 * uHalfWidth) + 0.5, 0.0, 0.9999);
    float f = u * float(uBarCount) - 0.5;
    int i0 = clamp(int(floor(f)), 0, uBarCount - 1), i1 = clamp(i0 + 1, 0, uBarCount - 1);
    float level = mix(uBars[i0], uBars[i1], clamp(f - floor(f), 0.0, 1.0));
    float bar = min({SHOCKWAVE_CEILING:.6f}, pow(clamp(level, 0.0, 1.0), 1.15) * clamp(max(1.0, uHeightScale), 1.0, 1.85));
    float reach = shockwaveSmooth(-SHOCKWAVE_DEPTH * (1.0 - {SHOCKWAVE_HORIZON_REACH:.6f}), -SHOCKWAVE_DEPTH, p.y);
    return uHorizon * bar * reach;
}}
// The shared orbit (scene3d.py) about the grid's centre, which the camera faces.
vec3 shockwaveView(vec3 p) {{ return sceneOrbitView(p, uView); }}
vec3 shockwaveViewPoint(vec3 p) {{
    return sceneOrbitPoint(p, uView, vec3(0.0, 0.0, -0.5 * SHOCKWAVE_DEPTH), vec3(0.0));
}}
vec3 shockwaveProject(vec3 p) {{
    return sceneOrbitProject(p, uView, vec3(0.0, 0.0, -0.5 * SHOCKWAVE_DEPTH), vec3(0.0), uCamera);
}}
"""

SHOCKWAVE_VERTEX_SOURCE = (
    "#version 460 core\nlayout(location = 0) in vec2 aUv;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_ORBIT_GLSL + _COMMON
    + """
out vec3 vWorld;      // the displaced point, in the camera's frame (lighting)
out vec2 vGrid;       // the point on the flat grid (x, z)
out float vCrest;
out float vRidge;
out float vRidgeLevel;  // the ridge as a share of its tallest (0..1): its loudness
out vec3 vNormal;
vec3 shockwaveSurface(vec2 p, out float crest, out float ridge) {
    vec2 wave = shockwaveHeight(p);
    crest = wave.y;
    ridge = shockwaveRidge(p);
    return vec3(p.x, wave.x + ridge, p.y);
}
void main() {
    vec2 p = vec2((aUv.x * 2.0 - 1.0) * uHalfWidth, -aUv.y * SHOCKWAVE_DEPTH);
    float crest, ridge, unused;
    vec3 surface = shockwaveSurface(p, crest, ridge);
    float e = 0.02;
    vec3 dx = shockwaveSurface(p + vec2(e, 0.0), unused, unused) - surface;
    vec3 dz = shockwaveSurface(p + vec2(0.0, e), unused, unused) - surface;
    vNormal = shockwaveView(normalize(cross(dz, dx)));
    vWorld = shockwaveViewPoint(surface);
    vGrid = p;
    vCrest = crest;
    vRidge = ridge;
    vRidgeLevel = uHorizon > 0.0 ? clamp(ridge / (uHorizon * 0.95), 0.0, 1.0) : 0.0;
    vec3 screen = shockwaveProject(surface);
    float h = uField.w;
    vec2 item = vec2(uField.x + 0.5 * uField.z + screen.x * uFit.x * h, uField.y + h * (uFit.y - screen.y * uFit.x));
    vec4 clip = uMatrix * vec4(item, 0.0, 1.0);
    clip.z = clamp(-screen.z / uCamera, -1.0, 1.0) * clip.w;
    gl_Position = clip;
}
"""
)

SHOCKWAVE_FRAGMENT_SOURCE = (
    "#version 460 core\nlayout(location = 0) out vec4 FragColor;\nlayout(location = 1) out vec4 Emission;\n"
    "in vec3 vWorld;\nin vec2 vGrid;\nin float vCrest;\nin float vRidge;\nin float vRidgeLevel;\nin vec3 vNormal;\n"
    "uniform float uHalfWidth;\nuniform float uCells;     // grid cells per field height\n"
    "uniform float uScroll;    // the lines' travel toward the viewer (field heights)\n"
    "uniform vec4 uLineColor;\nuniform vec4 uCrestColor;\nuniform float uFloor;\nuniform float uGlow;\n"
    "uniform float uEdgePx;\n"
    + SCENE3D_ORBIT_GLSL
    + f"const float SHOCKWAVE_DEPTH = {SHOCKWAVE_DEPTH:.6f};\n"
    + """
vec4 sceneEmission(vec3 light) { return vec4(light, dot(light, vec3(0.2126, 0.7152, 0.0722))); }
void main() {
    // Fade out at the far edge and the sides, so the grid has no hard border.
    float fade = smoothstep(uHalfWidth, uHalfWidth * 0.7, abs(vGrid.x))
               * smoothstep(-SHOCKWAVE_DEPTH, -SHOCKWAVE_DEPTH * 0.82, vGrid.y)
               * smoothstep(0.0, -0.04, vGrid.y);
    if (fade <= 0.0) discard;
    // Lines from the grid coordinates, anti-aliased by their width on screen.
    vec2 cell = vec2(vGrid.x, vGrid.y + uScroll) * uCells;
    vec2 width = max(fwidth(cell), vec2(1e-5));
    float line = sceneLineCoverage(sceneGridLineDistancePx(cell, width), vec2(uEdgePx));
    // Lines thinner than a pixel fade instead of shimmering.
    line *= clamp(1.2 / max(max(width.x, width.y) * 6.0, 1.0), 0.0, 1.0) * 0.6 + 0.4;
    float crest = clamp(vCrest, 0.0, 2.5);
    vec3 colour = mix(uLineColor.rgb, uCrestColor.rgb, clamp(crest * 1.2 + vRidge * 1.5, 0.0, 1.0));
    // Brighter where the wave is stronger, and along the ridge where the bars are loudest.
    float bright = (1.0 + 1.8 * crest) * (1.0 + 0.4 * vRidgeLevel);
    vec3 lit = colour * bright;
    // The floor between the lines: dark, catching a little light on the waves' slopes.
    vec3 n = normalize(vNormal);
    vec3 floorColour = vec3(0.015, 0.02, 0.04) + colour * 0.08 * max(dot(n, normalize(vec3(-0.3, 0.6, 0.75))), 0.0);
    float floorAlpha = uFloor * fade;
    float lineAlpha = line * fade * uLineColor.a;
    float alpha = max(floorAlpha, lineAlpha);
    vec3 rgb = mix(floorColour, lit, lineAlpha / max(alpha, 1e-4));
    FragColor = vec4(min(rgb, vec3(1.0)), alpha);
    Emission = sceneEmission(lit * lineAlpha * uGlow);
}
"""
)
