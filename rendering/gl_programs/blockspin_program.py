"""Authored shader and mesh contract for the single-slab BlockSpin effect.

The module is deliberately free of OpenGL calls.  A presentation owner imports
it only when BlockSpin is enabled, then owns the context-local program and mesh
resources itself.
"""

from __future__ import annotations

from rendering.gl_programs.blockspin_options import BLOCK_SPIN_EDGE_GLASS_CHOICES
from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_ghost_fragment, scene3d_motion_fragment, scene3d_motion_vertex


BLOCK_SPIN_VERTEX_STRIDE_FLOATS = 8
BLOCK_SPIN_THICKNESS = 0.05

def block_spin_edge_glass_mode(choice: object) -> int:
    """The shader's ``uEdgeGlass`` for a resolved Edge Glass choice (0 = Off).

    The sheen band and gloss outline are drawn over the glass unchanged; Off
    keeps them on black.
    """

    try:
        return BLOCK_SPIN_EDGE_GLASS_CHOICES.index(str(choice))
    except ValueError:
        raise ValueError(f"unknown resolved 3D Block Spins edge glass: {choice!r}") from None


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
out vec2 vScreenUv;
out float vDepthCoordinate;  // 0 at the front face, 1 at the back face
out vec3 vFrontNormal;
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
    vec3 front = vec3(0.0, 0.0, 1.0);
    if (uAxisMode == 1) {
        mat3 rotation = mat3(
            1.0, 0.0, 0.0,
            0.0, cosine, -sine,
            0.0, sine, cosine
        );
        position = rotation * aPosition;
        normal = normalize(rotation * aNormal);
        front = rotation * front;
    } else if (uAxisMode == 2) {
        vec3 axis = vec3(0.70710678, -0.70710678, 0.0);
        position = rotateAroundAxis(aPosition, axis, cosine, sine);
        normal = normalize(rotateAroundAxis(aNormal, axis, cosine, sine));
        front = rotateAroundAxis(front, axis, cosine, sine);
    } else if (uAxisMode == 3) {
        vec3 axis = vec3(0.70710678, 0.70710678, 0.0);
        position = rotateAroundAxis(aPosition, axis, cosine, sine);
        normal = normalize(rotateAroundAxis(aNormal, axis, cosine, sine));
        front = rotateAroundAxis(front, axis, cosine, sine);
    } else {
        mat3 rotation = mat3(
            cosine, 0.0, sine,
            0.0, 1.0, 0.0,
            -sine, 0.0, cosine
        );
        position = rotation * aPosition;
        normal = normalize(rotation * aNormal);
        front = rotation * front;
    }

    vNormal = normal;
    vFrontNormal = front;
    vDepthCoordinate = clamp(-aPosition.z / __THICKNESS__, 0.0, 1.0);
    vViewDirection = vec3(0.0, 0.0, 1.0);
    // The authored slab lives in OpenGL's bottom-up object coordinates while
    // Qt Quick item coordinates are top-down.
    vScreenUv = vec2(
        position.x * 0.5 + 0.5,
        0.5 - position.y * 0.5
    );
    vec2 localPosition = vScreenUv * uItemSize;
    vec4 projected = uMatrix * vec4(localPosition, 0.0, 1.0);
    projected.z = -position.z * 0.5 * projected.w;
    gl_Position = projected;
}
""".replace("__THICKNESS__", f"{BLOCK_SPIN_THICKNESS:.6f}")


BLOCK_SPIN_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
in vec3 vNormal;
in vec3 vViewDirection;
in float vEdgeCoordinate;
in vec2 vScreenUv;
in float vDepthCoordinate;
in vec3 vFrontNormal;
flat in int vFaceKind;
out vec4 FragColor;

uniform sampler2D uOldTexture;
uniform sampler2D uNewTexture;
uniform float uAngle;
uniform float uSpecDirection;
uniform int uAxisMode;
uniform int uEdgeGlass;  // 0 Off, 1 Reflection, 2 Refraction, 3 Both
uniform sampler2D uEnvironment;  // the next image as a blurred environment (photo reflections)
""" + SCENE3D_GLSL + """
vec2 mirroredUv(vec2 uv) {
    return 1.0 - abs(1.0 - mod(uv, 2.0));
}

// The next image in the slab's polished glass edge. The edge is rounded (bullnose):
// across the thickness its normal rolls from the front face's to the back face's, so
// the edge holds a compressed miniature of the picture rather than a smear of one
// column. Reflection reads the photo environment where the reflected ray points (its
// direction, not the edge's place on screen: an edge near the top of the screen no
// longer reflects only the picture's top border, which left early diagonal spins dark
// and flat); refraction bends the picture through the glass with a little dispersion;
// Fresnel weighs the two, so the rounded borders read as mirror and the middle as
// glass. The sheen keeps the flat normal.
vec3 edgeGlass(vec3 flatNormal, vec3 viewDirection) {
    float roll = (0.5 - vDepthCoordinate) * 2.2;
    vec3 normal = normalize(flatNormal * cos(roll) + normalize(vFrontNormal) * sin(roll));
    vec3 incident = -viewDirection;
    float facing = max(dot(normal, viewDirection), 0.0);
    float fresnel = 0.04 + 0.96 * pow(1.0 - facing, 5.0);
    vec3 reflection = vec3(0.0);
    vec3 refraction = vec3(0.0);
    if (uEdgeGlass != 2) {
        vec3 ray = reflect(incident, normal);
        reflection = sceneEnvironment(uEnvironment, sceneReflectionUv(ray), 0.12);
    }
    if (uEdgeGlass != 1) {
        vec3 red = refract(incident, normal, 1.0 / 1.50);
        vec3 green = refract(incident, normal, 1.0 / 1.52);
        vec3 blue = refract(incident, normal, 1.0 / 1.54);
        refraction = vec3(
            texture(uNewTexture, mirroredUv(vScreenUv + vec2(red.x, -red.y) * 0.12)).r,
            texture(uNewTexture, mirroredUv(vScreenUv + vec2(green.x, -green.y) * 0.12)).g,
            texture(uNewTexture, mirroredUv(vScreenUv + vec2(blue.x, -blue.y) * 0.12)).b
        );
    }
    if (uEdgeGlass == 1) {
        return reflection * mix(0.45, 1.0, fresnel);
    }
    if (uEdgeGlass == 2) {
        return refraction * 0.88 * (1.0 - fresnel);
    }
    return mix(refraction * 0.88, reflection, mix(0.2, 1.0, fresnel));
}

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
        vec3 surface = uEdgeGlass == 0 ? vec3(0.0) : edgeGlass(normal, viewDirection);
        color = mix(surface, vec3(1.0), clamp(4.0 * specular, 0.0, 1.0));

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

# With motion blur: the same shaders, also writing each point's screen motion (the
# slab's only moving input is its angle).
BLOCK_SPIN_MOTION_VERTEX_SOURCE = scene3d_motion_vertex(BLOCK_SPIN_QUICK_VERTEX_SOURCE, "uAngle")
BLOCK_SPIN_MOTION_FRAGMENT_SOURCE = scene3d_motion_fragment(BLOCK_SPIN_FRAGMENT_SOURCE)
# With motion trails: the same slab as a flat ghost silhouette.
BLOCK_SPIN_GHOST_FRAGMENT_SOURCE = scene3d_ghost_fragment(BLOCK_SPIN_MOTION_FRAGMENT_SOURCE)
