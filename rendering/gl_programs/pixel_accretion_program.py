"""Pure mesh, bounded-grid math and shaders for Directional Pixel Accretion."""

from __future__ import annotations

import math
from collections.abc import Mapping


PIXEL_ACCRETION_MAX_INSTANCES = 60_000
PIXEL_ACCRETION_FLIGHT_PROGRESS = .28
PIXEL_ACCRETION_QUAD_VERTICES = (
    -.5, -.5, 0., 0., .5, -.5, 1., 0., .5, .5, 1., 1.,
    -.5, -.5, 0., 0., .5, .5, 1., 1., -.5, .5, 0., 1.,
)


def pixel_accretion_parameters(parameters: Mapping[str, object]) -> tuple[int, int, float]:
    seed, tile_size, travel = parameters.get("seed"), parameters.get("tile_size"), parameters.get("travel")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Directional Pixel Accretion seed must be an integer between 1 and 65535")
    if isinstance(tile_size, bool) or not isinstance(tile_size, int) or not 4 <= tile_size <= 32:
        raise ValueError("Directional Pixel Accretion tile_size must be an integer between 4 and 32")
    if isinstance(travel, bool) or not isinstance(travel, (int, float)) or not math.isfinite(float(travel)) or not .1 <= float(travel) <= 1.0:
        raise ValueError("Directional Pixel Accretion travel must be finite and between 0.1 and 1.0")
    return seed, tile_size, float(travel)


def pixel_accretion_grid(width: int, height: int, tile_size: int, *, maximum: int = PIXEL_ACCRETION_MAX_INSTANCES) -> tuple[int, int, int]:
    """Return an adaptive physical-pixel grid that cannot exceed ``maximum``."""

    if width <= 0 or height <= 0:
        raise ValueError("Directional Pixel Accretion requires a positive viewport")
    if maximum < 1:
        raise ValueError("Directional Pixel Accretion maximum must be positive")
    size = int(tile_size)
    while math.ceil(width / size) * math.ceil(height / size) > maximum:
        size += 1
    columns, rows = math.ceil(width / size), math.ceil(height / size)
    return columns, rows, size


def pixel_accretion_tile_state(progress: float, start: float) -> tuple[float, float]:
    """Return local arrival and geometry scale; inactive tiles cover nothing."""

    raw = max(0.0, min(1.0, (float(progress) - float(start)) / PIXEL_ACCRETION_FLIGHT_PROGRESS))
    local = raw * raw * (3.0 - 2.0 * raw)
    appearance = max(0.0, min(1.0, raw / .08))
    return local, appearance * appearance * (3.0 - 2.0 * appearance)


PIXEL_ACCRETION_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec2 aPosition;
layout(location = 1) in vec2 aUv;
uniform mat4 uMatrix;
uniform vec2 uItemSize;
uniform vec2 uGrid;
uniform vec2 uDirection;
uniform float uProgress;
uniform float uTravel;
uniform float uSeed;
out vec2 vUv;
float hash1(vec2 p) { return fract(sin(dot(p, vec2(41.37, 289.19)) + uSeed) * 43758.5453); }
void main() {
    float id = float(gl_InstanceID);
    vec2 cell = vec2(mod(id, uGrid.x), floor(id / uGrid.x));
    vec2 centre = (cell + vec2(.5)) / uGrid;
    vec2 direction = normalize(uDirection);
    float rank = .5 + dot(centre - vec2(.5), direction) / (abs(direction.x) + abs(direction.y));
    float start = clamp(.025 + rank * .64 + (hash1(cell) - .5) * .075, 0., .70);
    // Each tile has a bounded flight. This leaves landed destination tiles
    // behind while the coherent front advances, instead of one shared finale.
    float raw = clamp((uProgress - start) / .28, 0., 1.);
    if (raw <= 0.) {
        gl_Position = vec4(2., 2., 2., 1.);
        vUv = (cell + aUv) / uGrid;
        return;
    }
    float local = raw * raw * (3. - 2. * raw);
    float appearance = smoothstep(0., .08, raw);
    float landing = 1. + (1. - local) * (.08 + hash1(cell + 5.) * .08);
    vec2 size = landing * appearance / uGrid;
    // A tile comes from the opposite side and travels *toward* uDirection.
    vec2 translation = -direction * uTravel * (1. - local);
    vec2 point = centre + aPosition * size + translation;
    float height = (1. - local) * (.008 + hash1(cell + 9.) * .014);
    float aspect = uItemSize.x / uItemSize.y;
    vec3 world = vec3((point.x - .5) * aspect, .5 - point.y, height);
    float cameraW = 3.0 - world.z;
    vec2 uv = vec2(world.x / aspect, -world.y) * 3.0 / cameraW + .5;
    vec4 projected = uMatrix * vec4(uv * uItemSize, 0., 1.);
    projected *= cameraW;
    projected.z = clamp(-world.z / 5.0, -.9, .9) * projected.w;
    gl_Position = projected;
    vUv = (cell + aUv) / uGrid;
}
"""

PIXEL_ACCRETION_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
void main() { FragColor = texture(uNewTex, vUv); }
"""
