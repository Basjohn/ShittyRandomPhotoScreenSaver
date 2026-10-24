"""Neon Basin's preserved musical onset/wave contract and CPU/GL mirrors.

The existing mode identity and bounded event ring retain their musical timing,
strength, spacing, deterministic origins and decay. Terrain projection and the
new distinct materials live in neon_lake_basin_program.py.
"""

from __future__ import annotations

import math

from core.constants.neon_lake_world import DEPTH as NEON_LAKE_DEPTH, half_width as neon_lake_half_width
from rendering.gl_programs.scene3d import Scene3DStorageLayout
from widgets.spotify_visualizer.transient_bus import musical_emphasis, musical_weight, passage_ramp

SHOCKWAVE_MAX_TILT = math.radians(90.0)
SHOCKWAVE_MAX_TURN = math.radians(180.0)
SHOCKWAVE_MAX_RIDGE = 0.6          # the horizon ridge's height at Horizon 1 and a full bar
SHOCKWAVE_DEPTH = NEON_LAKE_DEPTH   # the grid's length into the distance, in field heights
SHOCKWAVE_WIDTH = 0.16            # a crest's half width
SHOCKWAVE_DECAY = 1.1             # seconds for a wave to fall to 1/e
SHOCKWAVE_LIFETIME = 3.2          # seconds after which an event is dropped (all but invisible)
SHOCKWAVE_CAPACITY = 16           # events the water draws at once (the bounded GPU event buffer)
# The onset ring remembers events longer and more of them than the water draws, for consumers with longer
# tails (Neon's beat stars); the water still takes only its newest live events (``shockwave_event_records``).
SHOCKWAVE_EVENT_MEMORY = 6.0
SHOCKWAVE_EVENT_RING = 48
SHOCKWAVE_MIN_GAP = 0.09          # seconds between two admitted onsets in the loudest passage
SHOCKWAVE_MAX_BARS = 64
SHOCKWAVE_GRID_CELLS = (180, 120)  # the displaced surface's tessellation (columns, rows)
# Onset strength (``shockwave_strength``) follows the shared musical rule (``musical_weight``,
# ``musical_emphasis`` in the transient bus): near-silence and quiet passages inside a loud track
# make no wave, and an onset louder than the track's usual ones stands out.
# Everything ramps on the passage (``PassageIntensity``): how often waves may come (the gap from
# ``SHOCKWAVE_QUIET_GAP`` in the track's quietest passage to ``SHOCKWAVE_MIN_GAP`` in its loudest)
# and how strong they are (``passage_ramp``, ``SHOCKWAVE_QUIET_SHARE`` in the quietest). The
# emphasis is relative to the track's usual onset, so without the ramp a soft passage's onsets
# stood out as much as a loud one's: ~9 waves/s at every level, big waves commonest when quiet.
SHOCKWAVE_QUIET_GAP = 0.6
SHOCKWAVE_QUIET_SHARE = 0.3
SHOCKWAVE_MIN_STRENGTH = 0.12     # weaker onsets make no wave
SHOCKWAVE_MAX_STRENGTH = 2.0
# An onset's magnitude where its hit counts fully: about the p90 onset on the recorded songs (0.85-1.04,
# 2026-10-24). The earlier 3.0 left nearly every hit near its 0.4 floor, so waves stayed a third of full height.
SHOCKWAVE_HIT_MAGNITUDE = 1.0
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


shockwave_half_width = neon_lake_half_width


def shockwave_wave_speed(speed: float) -> float:
    """How fast a crest travels (field heights per second) for Wave Speed 0..1."""
    return 0.6 + 1.4 * max(0.0, min(1.0, float(speed)))


def shockwave_amplitude(height: float) -> float:
    """A full-strength wave's crest height (field heights) for Wave Height 0..1."""
    return 0.04 + 0.3 * max(0.0, min(1.0, float(height)))


def shockwave_strength(magnitude: float, loudness: float, presence: float) -> float:
    """A wave's strength (0 .. ``SHOCKWAVE_MAX_STRENGTH``) for an onset (``MusicalOnset``'s
    magnitude, loudness and presence), its emphasis read on the fixed loudness scale."""
    hit = 0.4 + 0.6 * max(0.0, min(1.0, float(magnitude) / SHOCKWAVE_HIT_MAGNITUDE))
    strength = musical_weight(loudness, presence) * musical_emphasis(loudness) * hit
    return max(0.0, min(SHOCKWAVE_MAX_STRENGTH, strength))


def shockwave_gap(intensity: float) -> float:
    """The least time between two waves at passage ``intensity`` (0 quietest .. 1 loudest)."""
    level = max(0.0, min(1.0, float(intensity)))
    return SHOCKWAVE_QUIET_GAP + (SHOCKWAVE_MIN_GAP - SHOCKWAVE_QUIET_GAP) * level


def shockwave_passage_share(intensity: float) -> float:
    """The share of an onset's strength (``shockwave_strength``) a wave keeps at passage ``intensity``."""
    return passage_ramp(intensity, SHOCKWAVE_QUIET_SHARE)


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


def shockwave_event_records(events, half_width: float) -> list[dict[str, float]]:
    """The std430 records for ``events`` [(age, x share, z, strength), ..., oldest first]: x in world units.
    Only the newest ``SHOCKWAVE_CAPACITY`` younger than ``SHOCKWAVE_LIFETIME`` (the ring remembers longer)."""
    live = [event for event in events if float(event[0]) < SHOCKWAVE_LIFETIME][-SHOCKWAVE_CAPACITY:]
    return [{"age": float(age), "x": float(x) * half_width, "z": float(z), "strength": float(strength)}
            for age, x, z, strength in live]


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


SHOCKWAVE_WAVE_GLSL = f"""
const float SHOCKWAVE_WIDTH = {SHOCKWAVE_WIDTH:.6f};
const float SHOCKWAVE_DECAY = {SHOCKWAVE_DECAY:.6f};
const float SHOCKWAVE_ECHO_SPEED = {SHOCKWAVE_ECHO_SPEED:.6f};
uniform int uEventCount;
uniform vec2 uWave;
uniform vec2 uIdle;
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
"""
