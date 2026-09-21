"""Pure mesh and shader contract for the instanced Exploding Tiles effect."""

from __future__ import annotations

import math
from collections.abc import Mapping


EXPLODING_TILES_VERTEX_STRIDE_FLOATS = 8
EXPLODING_TILES_VERTEX_COUNT = 36


def _face(corners, normal: tuple[float, float, float]) -> tuple[float, ...]:
    result: list[float] = []
    for index in (0, 1, 2, 0, 2, 3):
        position, uv = corners[index]
        result.extend((*position, *normal, *uv))
    return tuple(result)


def exploding_tiles_box_vertices(depth: float = 0.06) -> tuple[float, ...]:
    """Return one shallow, unit-sized cuboid; instances supply their own cells."""

    thickness = max(0.005, min(0.20, float(depth)))
    front = 0.5 * thickness
    back = -front
    return (
        *_face((((-.5, -.5, front), (0., 0.)), ((.5, -.5, front), (1., 0.)), ((.5, .5, front), (1., 1.)), ((-.5, .5, front), (0., 1.))), (0., 0., 1.)),
        *_face((((.5, -.5, back), (0., 0.)), ((-.5, -.5, back), (1., 0.)), ((-.5, .5, back), (1., 1.)), ((.5, .5, back), (0., 1.))), (0., 0., -1.)),
        *_face((((-.5, -.5, back), (0., 0.)), ((-.5, -.5, front), (1., 0.)), ((-.5, .5, front), (1., 1.)), ((-.5, .5, back), (0., 1.))), (-1., 0., 0.)),
        *_face((((.5, -.5, front), (0., 0.)), ((.5, -.5, back), (1., 0.)), ((.5, .5, back), (1., 1.)), ((.5, .5, front), (0., 1.))), (1., 0., 0.)),
        *_face((((-.5, .5, front), (0., 0.)), ((.5, .5, front), (1., 0.)), ((.5, .5, back), (1., 1.)), ((-.5, .5, back), (0., 1.))), (0., 1., 0.)),
        *_face((((-.5, -.5, back), (0., 0.)), ((.5, -.5, back), (1., 0.)), ((.5, -.5, front), (1., 1.)), ((-.5, -.5, front), (0., 1.))), (0., -1., 0.)),
    )


EXPLODING_TILES_BOX_VERTICES = exploding_tiles_box_vertices()


def exploding_tiles_parameters(parameters: Mapping[str, object]) -> tuple[int, int, float]:
    """Validate the immutable request contract before any GL state changes."""

    seed = parameters.get("seed")
    columns = parameters.get("columns")
    depth = parameters.get("depth")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Exploding Tiles seed must be an integer between 1 and 65535")
    if isinstance(columns, bool) or not isinstance(columns, int) or not 6 <= columns <= 48:
        raise ValueError("Exploding Tiles columns must be an integer between 6 and 48")
    if isinstance(depth, bool) or not isinstance(depth, (int, float)) or not math.isfinite(float(depth)) or not .2 <= float(depth) <= 1.5:
        raise ValueError("Exploding Tiles depth must be finite and between 0.2 and 1.5")
    return seed, columns, float(depth)


def exploding_tiles_grid(columns: int, width: int, height: int) -> tuple[int, int]:
    """Keep regular cells visually near-square while retaining a hard small cap."""

    if width <= 0 or height <= 0:
        raise ValueError("Exploding Tiles requires a positive viewport")
    rows = max(6, min(48, int(round(columns * height / width))))
    return int(columns), rows


def exploding_tile_state(progress: float, start: float) -> tuple[float, float]:
    """Return analytic local motion and visible scale for one seeded tile."""

    raw = max(0.0, min(1.0, (float(progress) - float(start)) / max(.001, .96 - float(start))))
    local = raw * raw * (3.0 - 2.0 * raw)
    shrink_raw = max(0.0, min(1.0, (local - .76) / .24))
    shrink = 1.0 - shrink_raw * shrink_raw * (3.0 - 2.0 * shrink_raw)
    return local, shrink


EXPLODING_TILES_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec3 aPosition;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUv;

uniform mat4 uMatrix;
uniform vec2 uItemSize;
uniform vec2 uGrid;
uniform vec2 uDirection;
uniform float uProgress;
uniform float uSeed;
uniform float uDepth;
uniform int uCenterOut;

out vec2 vUv;
out vec3 vNormal;
out float vMotion;

float hash1(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7)) + uSeed) * 43758.5453123); }
vec3 rotateAxis(vec3 p, vec3 axis, float angle) {
    float c = cos(angle), s = sin(angle);
    return p * c + cross(axis, p) * s + axis * dot(axis, p) * (1.0 - c);
}
void main() {
    float id = float(gl_InstanceID);
    float col = mod(id, uGrid.x);
    float row = floor(id / uGrid.x);
    vec2 cell = vec2(col, row);
    vec2 gridUv = (cell + aUv) / uGrid;
    vec2 centre = (cell + vec2(.5)) / uGrid;
    vec2 direction = uCenterOut == 1 ? vec2(0.) : normalize(uDirection);
    float wave = uCenterOut == 1 ? length(centre - vec2(.5)) * 1.41421356 : dot(centre - vec2(.5), direction) + .5;
    float jitter = (hash1(cell) - .5) * .11;
    float begin = clamp(.035 + wave * .48 + jitter, 0., .72);
    float raw = clamp((uProgress - begin) / max(.001, .96 - begin), 0., 1.);
    float local = raw * raw * (3. - 2. * raw);
    float shrink = 1. - smoothstep(.76, 1., local);
    float randomA = hash1(cell + 17.);
    vec3 axis = normalize(vec3(hash1(cell + 2.) - .5, hash1(cell + 5.) - .5, .65));
    float aspect = uItemSize.x / uItemSize.y;
    vec2 launch = uCenterOut == 1 ? normalize(centre - vec2(.5) + vec2(.0001)) : direction;
    vec2 worldDirection = vec2(launch.x * aspect, -launch.y);
    vec3 offset = vec3(worldDirection * (local * local * (.26 + .36 * randomA)), local * (.22 + .44 * randomA) * uDepth);
    // Convert XY to height-based world coordinates before rotation. The front
    // face starts at z=0, so dormant source tiles remain pixel-identical.
    vec3 localPosition = vec3(aPosition.x * aspect / uGrid.x, -aPosition.y / uGrid.y, (aPosition.z - .03) * .18 * uDepth) * shrink;
    localPosition = rotateAxis(localPosition, axis, local * (1.3 + randomA * 2.1));
    vec3 normal = normalize(rotateAxis(aNormal, axis, local * (1.3 + randomA * 2.1)));
    vec3 position = vec3((centre.x - .5) * aspect, .5 - centre.y, 0.) + localPosition + offset;
    float cameraW = 3.0 - position.z;
    vec2 uv = vec2(position.x / aspect, -position.y) * 3.0 / cameraW + .5;
    vec4 projected = uMatrix * vec4(uv * uItemSize, 0., 1.);
    projected *= cameraW;
    projected.z = clamp(-position.z / 5.0, -.9, .9) * projected.w;
    gl_Position = projected;
    vUv = gridUv;
    vNormal = normal;
    vMotion = local;
}
"""

EXPLODING_TILES_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
in vec3 vNormal;
in float vMotion;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
void main() {
    vec3 normal = normalize(vNormal);
    vec3 light = normalize(vec3(-.35, .48, .82));
    float diffuse = .30 + .70 * max(dot(normal, light), 0.);
    float rim = pow(1. - max(normal.z, 0.), 3.) * .18;
    vec3 old = texture(uOldTex, vUv).rgb;
    FragColor = vec4(old * mix(1., diffuse + rim, vMotion), 1.);
}
"""
