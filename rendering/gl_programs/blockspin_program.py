"""Authored shader and mesh contract for the single-slab BlockSpin effect.

The module is deliberately free of OpenGL calls.  A presentation owner imports
it only when BlockSpin is enabled, then owns the context-local program and mesh
resources itself.
"""

from __future__ import annotations


BLOCK_SPIN_VERTEX_STRIDE_FLOATS = 8
BLOCK_SPIN_THICKNESS = 0.05


def block_spin_progress(progress: float) -> float:
    """Apply BlockSpin's authored cubic timing to a linear run sample."""

    value = max(0.0, min(1.0, float(progress)))
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def block_spin_specular_band_center(
    spin_progress: float,
    spin_direction: float,
) -> float:
    """Return the authored side-highlight centre for contract tests/tools."""

    timeline = max(0.0, min(1.0, float(spin_progress)))
    edge_timeline = 1.0 - timeline if float(spin_direction) < 0.0 else timeline
    band_half_width = 0.09
    return band_half_width + (1.0 - 2.0 * band_half_width) * edge_timeline


def _face_vertices(
    corners: tuple[
        tuple[tuple[float, float, float], tuple[float, float]],
        tuple[tuple[float, float, float], tuple[float, float]],
        tuple[tuple[float, float, float], tuple[float, float]],
        tuple[tuple[float, float, float], tuple[float, float]],
    ],
    normal: tuple[float, float, float],
) -> tuple[float, ...]:
    values: list[float] = []
    for index in (0, 1, 2, 0, 2, 3):
        position, uv = corners[index]
        values.extend((*position, *normal, *uv))
    return tuple(values)


_T = BLOCK_SPIN_THICKNESS
BLOCK_SPIN_BOX_VERTICES = (
    *_face_vertices(
        (
            ((-1.0, -1.0, 0.0), (0.0, 0.0)),
            ((1.0, -1.0, 0.0), (1.0, 0.0)),
            ((1.0, 1.0, 0.0), (1.0, 1.0)),
            ((-1.0, 1.0, 0.0), (0.0, 1.0)),
        ),
        (0.0, 0.0, 1.0),
    ),
    *_face_vertices(
        (
            ((-1.0, -1.0, -_T), (0.0, 0.0)),
            ((1.0, -1.0, -_T), (1.0, 0.0)),
            ((1.0, 1.0, -_T), (1.0, 1.0)),
            ((-1.0, 1.0, -_T), (0.0, 1.0)),
        ),
        (0.0, 0.0, -1.0),
    ),
    *_face_vertices(
        (
            ((-1.0, -1.0, 0.0), (0.0, 0.0)),
            ((-1.0, -1.0, -_T), (1.0, 0.0)),
            ((-1.0, 1.0, -_T), (1.0, 1.0)),
            ((-1.0, 1.0, 0.0), (0.0, 1.0)),
        ),
        (-1.0, 0.0, 0.0),
    ),
    *_face_vertices(
        (
            ((1.0, -1.0, 0.0), (1.0, 0.0)),
            ((1.0, -1.0, -_T), (0.0, 0.0)),
            ((1.0, 1.0, -_T), (0.0, 1.0)),
            ((1.0, 1.0, 0.0), (1.0, 1.0)),
        ),
        (1.0, 0.0, 0.0),
    ),
    *_face_vertices(
        (
            ((-1.0, 1.0, 0.0), (0.0, 0.0)),
            ((1.0, 1.0, 0.0), (1.0, 0.0)),
            ((1.0, 1.0, -_T), (1.0, 1.0)),
            ((-1.0, 1.0, -_T), (0.0, 1.0)),
        ),
        (0.0, 1.0, 0.0),
    ),
    *_face_vertices(
        (
            ((-1.0, -1.0, 0.0), (0.0, 0.0)),
            ((1.0, -1.0, 0.0), (1.0, 0.0)),
            ((1.0, -1.0, -_T), (1.0, 1.0)),
            ((-1.0, -1.0, -_T), (0.0, 1.0)),
        ),
        (0.0, -1.0, 0.0),
    ),
)
BLOCK_SPIN_BOX_VERTEX_COUNT = (
    len(BLOCK_SPIN_BOX_VERTICES) // BLOCK_SPIN_VERTEX_STRIDE_FLOATS
)


BLOCK_SPIN_QUICK_VERTEX_SOURCE = """#version 410 core
layout(location = 0) in vec3 aPosition;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUv;

out vec2 vUv;
out vec3 vNormal;
out vec3 vViewDirection;
out float vEdgeCoordinate;
flat out int vFaceKind;

uniform mat4 uMatrix;
uniform vec2 uItemSize;
uniform float uAngle;
uniform int uAxisMode;

vec3 rotateAroundAxis(vec3 value, vec3 axis, float cosine, float sine) {
    float projection = dot(axis, value);
    return value * cosine
        + cross(axis, value) * sine
        + axis * projection * (1.0 - cosine);
}

void main() {
    vUv = aUv;
    vEdgeCoordinate = aUv.x;
    if (abs(aNormal.z) > 0.5) {
        vFaceKind = aNormal.z > 0.0 ? 1 : 2;
    } else {
        vFaceKind = 3;
    }

    float cosine = cos(uAngle);
    float sine = sin(uAngle);
    vec3 position;
    vec3 normal;
    if (uAxisMode == 1) {
        mat3 rotation = mat3(
            1.0, 0.0, 0.0,
            0.0, cosine, -sine,
            0.0, sine, cosine
        );
        position = rotation * aPosition;
        normal = normalize(rotation * aNormal);
    } else if (uAxisMode == 2) {
        vec3 axis = vec3(0.70710678, -0.70710678, 0.0);
        position = rotateAroundAxis(aPosition, axis, cosine, sine);
        normal = normalize(rotateAroundAxis(aNormal, axis, cosine, sine));
    } else if (uAxisMode == 3) {
        vec3 axis = vec3(0.70710678, 0.70710678, 0.0);
        position = rotateAroundAxis(aPosition, axis, cosine, sine);
        normal = normalize(rotateAroundAxis(aNormal, axis, cosine, sine));
    } else {
        mat3 rotation = mat3(
            cosine, 0.0, sine,
            0.0, 1.0, 0.0,
            -sine, 0.0, cosine
        );
        position = rotation * aPosition;
        normal = normalize(rotation * aNormal);
    }

    vNormal = normal;
    vViewDirection = vec3(0.0, 0.0, 1.0);
    // The authored slab lives in OpenGL's bottom-up object coordinates while
    // Qt Quick item coordinates are top-down.
    vec2 localPosition = vec2(
        position.x * 0.5 + 0.5,
        0.5 - position.y * 0.5
    ) * uItemSize;
    vec4 projected = uMatrix * vec4(localPosition, 0.0, 1.0);
    projected.z = -position.z * 0.5 * projected.w;
    gl_Position = projected;
}
"""


BLOCK_SPIN_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
in vec3 vNormal;
in vec3 vViewDirection;
in float vEdgeCoordinate;
flat in int vFaceKind;
out vec4 FragColor;

uniform sampler2D uOldTexture;
uniform sampler2D uNewTexture;
uniform float uAngle;
uniform float uSpecDirection;
uniform int uAxisMode;

void main() {
    vec2 frontUv = vec2(vUv.x, 1.0 - vUv.y);
    vec2 backUv;
    if (uAxisMode == 0) {
        backUv = vec2(1.0 - vUv.x, 1.0 - vUv.y);
    } else if (uAxisMode == 1) {
        backUv = vec2(vUv.x, vUv.y);
    } else if (uAxisMode == 2) {
        backUv = vec2(1.0 - vUv.y, vUv.x);
    } else {
        backUv = vec2(vUv.y, 1.0 - vUv.x);
    }

    vec3 normal = normalize(vNormal);
    vec3 viewDirection = normalize(vViewDirection);
    vec3 lightDirection = normalize(vec3(-0.15, 0.35, 0.9));
    float timeline = clamp(abs(uAngle) / 3.14159265, 0.0, 1.0);
    float edgeFactor = abs(timeline - 0.5) * 2.0;
    float highlightPhase = edgeFactor * edgeFactor;
    float midpointPhase = 1.0 - edgeFactor;
    midpointPhase *= midpointPhase;

    vec3 color;
    if (vFaceKind == 3) {
        vec3 halfVector = normalize(lightDirection + viewDirection);
        float normalHighlight = max(dot(normal, halfVector), 0.0);
        float edgeTimeline = uSpecDirection < 0.0
            ? 1.0 - timeline
            : timeline;
        float bandHalfWidth = 0.09;
        float bandCenter = mix(
            bandHalfWidth,
            1.0 - bandHalfWidth,
            edgeTimeline
        );
        float distanceToBand = abs(vEdgeCoordinate - bandCenter);
        float bandMask = 1.0 - smoothstep(
            bandHalfWidth,
            bandHalfWidth * 1.6,
            distanceToBand
        );
        float specular = pow(normalHighlight, 6.0)
            * bandMask
            * highlightPhase;
        color = mix(vec3(0.0), vec3(1.0), clamp(4.0 * specular, 0.0, 1.0));

        float xEdge = min(vEdgeCoordinate, 1.0 - vEdgeCoordinate);
        float yEdge = min(vUv.y, 1.0 - vUv.y);
        float outlineMask = 1.0 - smoothstep(0.02, 0.08, min(xEdge, yEdge));
        float outlinePhase = outlineMask * midpointPhase;
        if (outlinePhase > 0.0) {
            color = mix(
                color,
                vec3(1.0),
                clamp(1.2 * outlinePhase, 0.0, 1.0)
            );
        }
    } else if (vFaceKind == 1) {
        color = texture(uOldTexture, frontUv).rgb;
    } else {
        color = texture(uNewTexture, backUv).rgb;
    }
    FragColor = vec4(color, 1.0);
}
"""
