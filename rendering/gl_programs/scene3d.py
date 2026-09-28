"""Shared 3D scene library for mesh transitions: GLSL functions plus exact CPU mirrors.

World space: x right across ``[-aspect/2, aspect/2]``, y up across ``[-1/2, 1/2]``,
z toward the viewer. The photograph lies on z = 0 and fills the view exactly
there; one pinhole camera at z = ``SCENE3D_CAMERA`` looks down -z. Projection
keeps a real near plane, so a piece that flies past the camera is clipped by the
GPU instead of folding back through infinity.

What an effect gets from ``SCENE3D_GLSL``:

* ``sceneRandom`` -- integer lattice hash, identical on every GPU (R-94);
* ``sceneRotate`` / ``sceneProject`` / ``scenePlaneUv`` -- rigid motion and the camera;
* ``sceneImpulse`` -- drag-limited flight: a hard start that settles into a drift;
* ``sceneDepartureTravel`` -- the least travel that clears the frame for good,
  so departing pieces leave by construction rather than by tuning;
* ``sceneShade`` / ``scenePointLight`` / ``sceneEmber`` -- one key light with
  Blinn-Phong highlights and a Fresnel rim, local lights, hot-material colour;
* ``sceneCastOnPlane`` / ``sceneSoftRect`` -- soft planar shadows on the photograph;
* ``sceneStreak`` -- camera-facing motion streaks for sparks and debris.

Import-safe: strings and pure math only. Programs, buffers and every per-effect
decision stay with the consuming renderer; this owns no state or clock.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scene3DDetail:
    """One 3D Detail tier: multisampling, shadow pass and particle share."""

    name: str
    samples: int
    shadows: bool
    particles: float


# The canonical ``transitions.detail_3d`` values, cheapest last. High renders the
# scene into a 4x multisampled target; the others draw straight into Quick's.
SCENE3D_DETAIL_TIERS: dict[str, Scene3DDetail] = {
    "High": Scene3DDetail("High", 4, True, 1.0),
    "Balanced": Scene3DDetail("Balanced", 0, True, 0.6),
    "Performance": Scene3DDetail("Performance", 0, False, 0.3),
}
SCENE3D_DETAIL_NAMES = tuple(SCENE3D_DETAIL_TIERS)


def scene3d_detail(name: object) -> Scene3DDetail:
    detail = SCENE3D_DETAIL_TIERS.get(str(name))
    if detail is None:
        raise ValueError(f"unknown 3D Detail tier: {name!r}")
    return detail


SCENE3D_CAMERA = 3.4
SCENE3D_NEAR = 0.22
SCENE3D_FAR = 9.0
_KEY = (-0.38, 0.57, 0.73)
_KEY_LENGTH = math.sqrt(sum(value * value for value in _KEY))
SCENE3D_KEY_LIGHT = tuple(value / _KEY_LENGTH for value in _KEY)

SCENE3D_GLSL = f"""
const float SCENE_CAMERA = {SCENE3D_CAMERA:.6f};
const float SCENE_NEAR = {SCENE3D_NEAR:.6f};
const float SCENE_FAR = {SCENE3D_FAR:.6f};
const vec3 SCENE_KEY = vec3({SCENE3D_KEY_LIGHT[0]:.6f}, {SCENE3D_KEY_LIGHT[1]:.6f}, {SCENE3D_KEY_LIGHT[2]:.6f});

// Integer lattice hash: identical on every GPU and exact for any seed (R-94).
uint sceneMix(uint x) {{
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}}
float sceneRandom(uint key, uint salt, uint seed) {{
    return float(sceneMix(key * 0x9e3779b9u ^ sceneMix(seed * 0x85ebca6bu + salt))) * (1.0 / 4294967295.0);
}}

vec3 sceneRotate(vec3 p, vec3 axis, float angle) {{
    float c = cos(angle), s = sin(angle);
    return p * c + cross(axis, p) * s + axis * dot(axis, p) * (1.0 - c);
}}

float sceneClipDepth(float w) {{
    return ((SCENE_FAR + SCENE_NEAR) * w - 2.0 * SCENE_FAR * SCENE_NEAR) / (SCENE_FAR - SCENE_NEAR);
}}

// World point -> clip space through the Quick item matrix. w stays the distance
// in front of the camera, so attributes interpolate perspective-correctly and
// the GPU clips against the near plane.
vec4 sceneProject(mat4 matrix, vec2 itemSize, vec3 world) {{
    float aspect = itemSize.x / itemSize.y;
    float w = SCENE_CAMERA - world.z;
    vec2 scaled = vec2(world.x / aspect, -world.y) * SCENE_CAMERA + 0.5 * w;
    vec4 clip = matrix * vec4(scaled * itemSize, 0.0, w);
    clip.z = sceneClipDepth(w);
    return clip;
}}

// Item UV (0..1, y down) of a point on the photograph plane z = 0.
vec2 scenePlaneUv(vec2 world, float aspect) {{
    return vec2(world.x / aspect, -world.y) + 0.5;
}}

// Flight under drag: a hard start (slope drag*(1+drift)) that settles into a
// steady drift. 0 at t = 0, rising monotonically.
float sceneImpulse(float t, float drag, float drift) {{
    return 1.0 - exp(-drag * t) + drift * drag * t;
}}

// Least travel along the heading after which start + heading * s stays outside
// the box of half extents halfBox for every larger s (0 if the ray never enters).
float sceneDepartureTravel(vec2 start, vec2 heading, vec2 halfBox) {{
    float enter = -1e20, leave = 1e20;
    for (int axis = 0; axis < 2; ++axis) {{
        if (abs(heading[axis]) < 1e-6) {{
            if (abs(start[axis]) >= halfBox[axis]) return 0.0;
            continue;
        }}
        float a = (-halfBox[axis] - start[axis]) / heading[axis];
        float b = (halfBox[axis] - start[axis]) / heading[axis];
        enter = max(enter, min(a, b));
        leave = min(leave, max(a, b));
    }}
    return enter < leave ? max(leave, 0.0) : 0.0;
}}

// Key-light shading: wrapped Lambert, Blinn-Phong highlight and a Schlick rim.
vec3 sceneShade(vec3 albedo, vec3 normal, vec3 world, float ambient, float specular, float shininess, float rim) {{
    vec3 view = normalize(vec3(0.0, 0.0, SCENE_CAMERA) - world);
    float diffuse = max(dot(normal, SCENE_KEY), 0.0);
    float highlight = pow(max(dot(normal, normalize(SCENE_KEY + view)), 0.0), shininess);
    float fresnel = pow(1.0 - max(dot(normal, view), 0.0), 5.0);
    return albedo * (ambient + (1.0 - ambient) * diffuse) + vec3(specular * highlight + rim * fresnel);
}}

// A local light with smooth distance falloff; returns the added radiance.
vec3 scenePointLight(vec3 normal, vec3 world, vec3 light, vec3 colour, float falloff) {{
    vec3 toLight = light - world;
    float distance2 = dot(toLight, toLight);
    return colour * max(dot(normal, toLight * inversesqrt(max(distance2, 1e-6))), 0.0) / (1.0 + distance2 * falloff);
}}

// Blackbody-like ramp for hot material: dull red -> orange -> pale yellow.
vec3 sceneEmber(float t) {{
    t = clamp(t, 0.0, 1.0);
    return mix(mix(vec3(0.50, 0.05, 0.01), vec3(1.0, 0.42, 0.08), smoothstep(0.0, 0.55, t)),
               vec3(1.0, 0.90, 0.62), smoothstep(0.55, 1.0, t));
}}

// Where a point's shadow falls on the plane z = planeZ along the key light.
vec2 sceneCastOnPlane(vec3 world, float planeZ) {{
    return world.xy - SCENE_KEY.xy / SCENE_KEY.z * max(world.z - planeZ, 0.0);
}}

// Soft coverage of a rectangle in its local coordinates (edges at +-0.5).
float sceneSoftRect(vec2 local, float feather) {{
    vec2 edge = abs(local);
    return (1.0 - smoothstep(0.5 - feather, 0.5 + feather, edge.x))
         * (1.0 - smoothstep(0.5 - feather, 0.5 + feather, edge.y));
}}

// A camera-facing streak from tail to head. corner is the quad corner in [0,1]^2
// (x along the streak, y across); width is in item pixels on the photograph plane
// and grows with nearness. An end behind the near plane culls the streak.
vec4 sceneStreak(mat4 matrix, vec2 itemSize, vec3 tail, vec3 head, float width, vec2 corner) {{
    float aspect = itemSize.x / itemSize.y;
    float wt = SCENE_CAMERA - tail.z, wh = SCENE_CAMERA - head.z;
    if (min(wt, wh) <= SCENE_NEAR) return vec4(2.0, 2.0, 2.0, 1.0);
    vec2 a = (vec2(tail.x / aspect, -tail.y) * SCENE_CAMERA / wt + 0.5) * itemSize;
    vec2 b = (vec2(head.x / aspect, -head.y) * SCENE_CAMERA / wh + 0.5) * itemSize;
    vec2 axis = b - a;
    float span = length(axis);
    vec2 along = span > 1e-3 ? axis / span : vec2(1.0, 0.0);
    float size = width * SCENE_CAMERA / wh;
    vec2 point = mix(a - along * size * 0.5, b + along * size * 0.5, corner.x)
               + vec2(-along.y, along.x) * (corner.y - 0.5) * size;
    vec4 clip = matrix * vec4(point, 0.0, 1.0);
    float w = mix(wt, wh, corner.x);
    clip.z = sceneClipDepth(w) / w * clip.w;
    return clip;
}}
"""


def scene3d_screen_uv(world: tuple[float, float, float], aspect: float) -> tuple[float, float]:
    """CPU mirror of ``sceneProject`` after the perspective divide, as item UV."""
    x, y, z = world
    scale = SCENE3D_CAMERA / (SCENE3D_CAMERA - z)
    return x / aspect * scale + 0.5, -y * scale + 0.5


def scene3d_impulse(t: float, drag: float, drift: float) -> float:
    """CPU mirror of ``sceneImpulse``."""
    return 1.0 - math.exp(-drag * t) + drift * drag * t


def scene3d_departure_travel(
    start: tuple[float, float],
    heading: tuple[float, float],
    half_box: tuple[float, float],
) -> float:
    """CPU mirror of ``sceneDepartureTravel``."""
    enter, leave = -1e20, 1e20
    for axis in range(2):
        if abs(heading[axis]) < 1e-6:
            if abs(start[axis]) >= half_box[axis]:
                return 0.0
            continue
        a = (-half_box[axis] - start[axis]) / heading[axis]
        b = (half_box[axis] - start[axis]) / heading[axis]
        enter = max(enter, min(a, b))
        leave = min(leave, max(a, b))
    return max(leave, 0.0) if enter < leave else 0.0


def scene3d_cast_on_plane(world: tuple[float, float, float], plane_z: float) -> tuple[float, float]:
    """CPU mirror of ``sceneCastOnPlane``."""
    lift = max(world[2] - plane_z, 0.0)
    return (world[0] - SCENE3D_KEY_LIGHT[0] / SCENE3D_KEY_LIGHT[2] * lift,
            world[1] - SCENE3D_KEY_LIGHT[1] / SCENE3D_KEY_LIGHT[2] * lift)
