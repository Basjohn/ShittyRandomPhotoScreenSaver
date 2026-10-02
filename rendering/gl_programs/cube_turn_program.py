"""Cube Turn: shaders and CPU mirrors (loaded only when Cube Turn renders).

The old picture is the front of a box as deep as the picture is wide (turning left or right)
or tall (turning up or down), so its side is the new picture's shape. The box turns a quarter
about its centre, eased in and out, while the camera draws back (``CUBE_TURN_DOLLY``) so the
whole box stays in view and returns: at rest the front lies exactly on the photograph, and once
turned the side does. The side shows the new picture where it rests after the turn, so it
arrives upright. Behind the box, a dim blur of the new picture (its renderer-owned copy).

Faces are lit by the shared physically based material, blended in by ``sin(2 angle)`` (zero at
both ends), with a reflection of the new picture.
"""

from __future__ import annotations

import math

from rendering.gl_programs.scene3d import SCENE3D_GLSL

CUBE_TURN_DOLLY = 0.22
CUBE_TURN_BACKDROP = 0.35
_TURNS = {"left": (0, -1.0), "right": (0, 1.0), "up": (1, -1.0), "down": (1, 1.0)}


def cube_turn_axis(direction: str) -> tuple[int, float]:
    """(axis: 0 vertical, 1 horizontal; the sign of the quarter turn) for the way the front moves."""
    return _TURNS[direction]


def cube_turn_state(progress: float, sign: float) -> tuple[float, float]:
    """(angle, camera zoom) at ``progress``: an eased quarter turn and a dolly back and in."""
    t = max(0.0, min(1.0, float(progress)))
    e = t * t * (3.0 - 2.0 * t)
    return sign * 0.5 * math.pi * e, 1.0 - CUBE_TURN_DOLLY * math.sin(math.pi * e)


def cube_turn_lift(angle: float) -> float:
    """How far the box is from resting square on: 0 at both ends of the turn."""
    return abs(math.sin(2.0 * angle))


CUBE_TURN_VERTEX_SOURCE = (
    "#version 460 core\n"
    "layout(location = 0) in vec3 aPosition;\nlayout(location = 1) in vec3 aNormal;\n"
    "uniform mat4 uMatrix;\nuniform vec2 uItemSize;\n"
    "uniform float uAngle;\nuniform float uFinal;\nuniform int uAxis;\nuniform float uZoom;\n"
    "out vec2 vSourceUv;\nout vec2 vDestinationUv;\nout vec3 vWorld;\nout vec3 vNormal;\nflat out int vFace;\n"
    + SCENE3D_GLSL
    + """
vec3 cubeTurn(vec3 p, float angle) {
    float c = cos(angle), s = sin(angle);
    return uAxis == 0 ? vec3(p.x * c + p.z * s, p.y, -p.x * s + p.z * c)
                      : vec3(p.x, p.y * c - p.z * s, p.y * s + p.z * c);
}
void main() {
    float aspect = uItemSize.x / uItemSize.y;
    float depth = uAxis == 0 ? aspect : 1.0;
    vec3 local = aPosition * vec3(aspect, 1.0, depth);       // about the box's centre
    vec3 centre = vec3(0.0, 0.0, -0.5 * depth);              // the front rests on z = 0
    vec3 world = cubeTurn(local, uAngle) + centre;
    vWorld = world;
    vNormal = cubeTurn(aNormal, uAngle);
    vSourceUv = scenePlaneUv(local.xy, aspect);
    vDestinationUv = scenePlaneUv((cubeTurn(local, uFinal) + centre).xy, aspect);
    vFace = aNormal.z > 0.5 ? 0 : (cubeTurn(aNormal, uFinal).z > 0.5 ? 1 : 2);
    gl_Position = sceneProjectCamera(uMatrix, uItemSize, world, vec4(SCENE_CAMERA, uZoom, 0.0, 0.0), vec4(0.0));
}
"""
)

CUBE_TURN_FRAGMENT_SOURCE = (
    "#version 460 core\n"
    "in vec2 vSourceUv;\nin vec2 vDestinationUv;\nin vec3 vWorld;\nin vec3 vNormal;\nflat in int vFace;\n"
    "out vec4 FragColor;\n"
    "uniform sampler2D uOldTex;\nuniform sampler2D uNewTex;\nuniform sampler2D uEnvironment;\n"
    "uniform float uGloss;\nuniform float uLift;\n"
    + SCENE3D_GLSL
    + """
void main() {
    vec3 photo = vFace == 0 ? texture(uOldTex, vSourceUv).rgb
               : (vFace == 1 ? texture(uNewTex, vDestinationUv).rgb : vec3(0.08));
    if (uLift <= 0.0) {
        FragColor = vec4(photo, 1.0);   // square on: the photograph exactly
        return;
    }
    vec3 n = normalize(vNormal);
    SceneMaterial surface = SceneMaterial(photo, mix(0.7, 0.2, uGloss), 0.0, 0.5, vec3(0.0));
    vec3 lit = sceneMaterialLit(surface, n, vWorld, vec3(2.6), vec3(0.32))
             + uGloss * sceneMaterialEnvironment(uEnvironment, surface, n, vWorld);
    FragColor = vec4(mix(photo, lit, uLift), 1.0);
}
"""
)

CUBE_TURN_BACKDROP_FRAGMENT_SOURCE = f"""#version 460 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uEnvironment;
void main() {{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    FragColor = vec4(textureLod(uEnvironment, uv, 5.0).rgb * {CUBE_TURN_BACKDROP:.6f}, 1.0);
}}
"""
