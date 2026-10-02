"""Disintegrate: the old picture breaks into fine grains that blow away (loaded only when it renders).

The picture is a grid of grains (``grain_size`` device pixels each, at most
``DISINTEGRATE_MAX_GRAINS``; larger grains past that). A release front sweeps across it
along the wind's direction, roughened by smooth value noise on the exact integer lattice
hash (R-94) and a little per-grain jitter. Until its release a grain is part of the intact
picture; then it flies for its life (part of the run): pushed by the wind with a hard start
that keeps accelerating, swirling across the wind, lifting a little, shrinking and fading
out, revealing the new picture beneath. Every grain is gone by 0.97 of the run, so the run
ends on the new picture exactly; at release a grain covers its own cell exactly, so the
front has no seam.

The grains are a ``CompactedPopulation``: only live grains are evaluated (once each, in a
compute pass, instead of once per vertex) and drawn, with one indirect draw, in id order,
blended over each other deterministically. The CPU mirrors below define the same schedule
and flight for tests.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_GLSL, Scene3DBlockLayout, scene3d_random

DISINTEGRATE_MAX_GRAINS = 600_000
DISINTEGRATE_NOISE_SCALE = 5.0
DISINTEGRATE_VERTICES = 4


def disintegrate_grid(width: int, height: int, grain_size: int,
                      *, maximum: int = DISINTEGRATE_MAX_GRAINS) -> tuple[int, int, int]:
    """(columns, rows, size): the grain grid over ``width`` x ``height`` device pixels, never over ``maximum``."""
    if width <= 0 or height <= 0:
        raise ValueError("Disintegrate requires a positive viewport")
    size = max(1, int(grain_size))
    while math.ceil(width / size) * math.ceil(height / size) > maximum:
        size += 1
    return math.ceil(width / size), math.ceil(height / size), size


def _lattice(ix: int, iy: int, seed: int) -> float:
    return scene3d_random((ix * 0x8DA6B343 ^ iy * 0xD8163841) & 0xFFFFFFFF, 7, seed)


def disintegrate_noise(x: float, y: float, seed: int) -> float:
    """CPU mirror of ``grainNoise``: smooth value noise in [0, 1] on the exact integer lattice."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _lattice(ix, iy, seed), _lattice(ix + 1, iy, seed)
    c, d = _lattice(ix, iy + 1, seed), _lattice(ix + 1, iy + 1, seed)
    return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sy


def disintegrate_release(grain: int, columns: int, rows: int, direction: tuple[float, float], aspect: float,
                         seed: int) -> float:
    """CPU mirror of ``grainRelease``: when the grain leaves the picture (run progress)."""
    cx, cy = (grain % columns + 0.5) / columns, (grain // columns + 0.5) / rows
    rank = 0.5 + ((cx - 0.5) * direction[0] + (cy - 0.5) * direction[1]) / (abs(direction[0]) + abs(direction[1]))
    noise = disintegrate_noise(cx * DISINTEGRATE_NOISE_SCALE * aspect, cy * DISINTEGRATE_NOISE_SCALE, seed)
    front = max(0.0, min(1.0, rank + 0.22 * (noise - 0.5)))
    return 0.03 + 0.55 * front + 0.03 * scene3d_random(grain, 1, seed)


def disintegrate_life(grain: int, seed: int) -> float:
    """CPU mirror of ``grainLife``: how long the grain flies (run progress)."""
    return 0.26 + 0.1 * scene3d_random(grain, 2, seed)


# One frame's values for the intact pass and both population passes, streamed once per frame.
# uDirection is the wind in item space (y down), unit length; uFrameSize the item's size.
DISINTEGRATE_FRAME_BLOCK = Scene3DBlockLayout.of("DisintegrateFrame", (
    ("uGrid", "uvec2"), ("uDirection", "vec2"), ("uFrameSize", "vec2"), ("uProgress", "float"), ("uSeed", "uint"),
    ("uWind", "float"),
))

_COMMON_GLSL = SCENE3D_GLSL + DISINTEGRATE_FRAME_BLOCK.glsl() + f"""

float grainLattice(int x, int y) {{
    return sceneRandom(uint(x) * 0x8DA6B343u ^ uint(y) * 0xD8163841u, 7u, uSeed);
}}
float grainNoise(vec2 p) {{
    vec2 cell = floor(p), f = p - cell;
    int x = int(cell.x), y = int(cell.y);
    vec2 s = f * f * (3.0 - 2.0 * f);
    float a = grainLattice(x, y), b = grainLattice(x + 1, y), c = grainLattice(x, y + 1), d = grainLattice(x + 1, y + 1);
    float top = a + (b - a) * s.x;
    return top + ((c + (d - c) * s.x) - top) * s.y;
}}
vec2 grainCentre(uint id) {{
    return (vec2(id % uGrid.x, id / uGrid.x) + 0.5) / vec2(uGrid);
}}
float grainRelease(uint id) {{
    vec2 c = grainCentre(id);
    float rank = 0.5 + dot(c - 0.5, uDirection) / (abs(uDirection.x) + abs(uDirection.y));
    float noise = grainNoise(c * vec2({DISINTEGRATE_NOISE_SCALE:.1f} * uFrameSize.x / uFrameSize.y,
                                      {DISINTEGRATE_NOISE_SCALE:.1f}));
    return 0.03 + 0.55 * clamp(rank + 0.22 * (noise - 0.5), 0.0, 1.0) + 0.03 * sceneRandom(id, 1u, uSeed);
}}
float grainLife(uint id) {{
    return 0.26 + 0.1 * sceneRandom(id, 2u, uSeed);
}}
"""

# The population hooks: a grain is live from its release for its life; its state is
# (item-pixel centre, scale of its cell, opacity).
DISINTEGRATE_HOOKS = _COMMON_GLSL + """
bool populationActive(uint id) {
    float release = grainRelease(id);
    return uProgress >= release && uProgress < release + grainLife(id);
}
vec4 populationState(uint id) {
    float s = clamp((uProgress - grainRelease(id)) / grainLife(id), 0.0, 1.0);
    float height = uFrameSize.y;
    float strength = 0.6 + 0.8 * sceneRandom(id, 3u, uSeed);
    vec2 push = uDirection * (uWind * 0.9 * height * (0.25 * s + 0.75 * s * s) * strength);
    vec2 across = vec2(-uDirection.y, uDirection.x)
        * (sin(6.2831853 * (sceneRandom(id, 4u, uSeed) + s * (1.0 + sceneRandom(id, 5u, uSeed)))) * 0.05 * height * s);
    vec2 lift = vec2(0.0, -0.12 * height * s * s * sceneRandom(id, 6u, uSeed));
    return vec4(grainCentre(id) * uFrameSize + push + across + lift, 1.0 - 0.7 * s, 1.0 - smoothstep(0.45, 1.0, s));
}
"""

# The picture where its grains have not left: the old picture before a grain's release, the new after.
DISINTEGRATE_INTACT_FRAGMENT_SOURCE = (
    "#version 460 core\nin vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\n" + _COMMON_GLSL + """
void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    uvec2 cell = min(uvec2(uv * vec2(uGrid)), uGrid - 1u);
    float release = grainRelease(cell.y * uGrid.x + cell.x);
    FragColor = vec4(uProgress < release ? texture(uOldTex, uv).rgb : texture(uNewTex, uv).rgb, 1.0);
}
"""
)


def _draw_vertex() -> str:
    from rendering.quick.scene3d.population import POPULATION_DRAW_GLSL   # loaded with this module, when it renders

    return ("#version 460 core\n" + POPULATION_DRAW_GLSL + """
uniform mat4 uMatrix;
uniform vec2 uItemSize;
uniform uvec2 uGrid;
out vec2 vUv;
out float vAlpha;
void main() {
    uint id = populationIds[gl_InstanceID];
    vec4 state = populationStates[gl_InstanceID];
    vec2 corner = vec2(gl_VertexID & 1, gl_VertexID >> 1);
    vec2 cells = vec2(uGrid);
    vec2 pixel = state.xy + (corner - 0.5) * (uItemSize / cells) * state.z;
    vUv = (vec2(id % uGrid.x, id / uGrid.x) + corner) / cells;   // the grain's own cell of the old picture
    vAlpha = state.w;
    gl_Position = uMatrix * vec4(pixel, 0.0, 1.0);
}
""")


DISINTEGRATE_GRAIN_VERTEX_SOURCE = _draw_vertex()
DISINTEGRATE_GRAIN_FRAGMENT_SOURCE = """#version 460 core
in vec2 vUv;
in float vAlpha;
out vec4 FragColor;
uniform sampler2D uOldTex;
void main() {
    FragColor = vec4(texture(uOldTex, vUv).rgb * vAlpha, vAlpha);   // premultiplied, blended over
}
"""
