"""Shared 3D scene library for mesh transitions: GLSL functions plus exact CPU mirrors.

World space: x right across ``[-aspect/2, aspect/2]``, y up across ``[-1/2, 1/2]``,
z toward the viewer. The photograph lies on z = 0 and fills the view exactly
there; one pinhole camera at z = ``SCENE3D_CAMERA`` looks down -z. Projection
keeps a real near plane, so a piece that flies past the camera is clipped by the
GPU instead of folding back through infinity.

What an effect gets from ``SCENE3D_GLSL``:

* ``sceneRandom`` -- integer lattice hash, identical on every GPU (R-94);
* ``sceneRotate`` / ``sceneProject`` / ``sceneProjectAt`` / ``scenePlaneUv`` -- rigid motion and
  a resting camera at any distance; ``sceneProjectCamera`` -- a moving camera (offset, tilt,
  zoom), with ``scene3d_camera_overscan`` and ``scene3d_camera_shake`` on the CPU;
* ``sceneImpulse`` -- drag-limited flight: a hard start that settles into a drift;
* ``sceneDepartureTravel`` -- the least travel that clears the frame for good,
  so departing pieces leave by construction rather than by tuning;
* ``sceneShade`` / ``scenePointLight`` / ``sceneEmber`` -- one key light with
  Blinn-Phong highlights and a Fresnel rim, local lights, hot-material colour;
* ``sceneCastOnPlane`` / ``sceneSoftRect`` -- soft planar shadows on the photograph;
  ``ScenePiece`` / ``scenePiecePoint`` / ``scenePieceShadow`` -- any rigid piece and its shadow,
  drawn by ``rendering.quick.scene3d.shadows``;
* ``sceneStreak`` -- camera-facing motion streaks for sparks and debris;
* ``sceneParticleAt`` / ``sceneParticleStreak`` -- a particle's drag-and-fall flight and its
  streak (a streak with no trail is a soft sprite), drawn by ``rendering.quick.scene3d.particles``;
* ``scenePlanePoint`` / ``scene3d_grid_vertex_source`` -- the bendable grid surface: an effect
  writes ``vec3 sceneDisplace(vec2 uv)`` and gets a subdivided photograph (density by tier,
  ``scene3d_grid_size``) with normals, drawn by ``rendering.quick.scene3d.grid``;
* ``sceneEnvironment`` / ``sceneReflectionUv`` / ``sceneEnvironmentLight`` -- photo reflections:
  a glossy surface reflects a blurred, renderer-owned copy of a photograph
  (``rendering.quick.scene3d.environment``) where its reflected ray points;
* ``sceneVelocity`` -- a surface point's screen motion over the shutter, for motion blur
  (``SCENE3D_SHUTTER_SECONDS``, ``scene3d_shutter_progress``); ``scene3d_motion_vertex`` /
  ``scene3d_motion_fragment`` make any effect's shaders write it.

Import-safe: strings and pure math only. Programs, buffers and every per-effect
decision stay with the consuming renderer; this owns no state or clock.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class Scene3DDetail:
    """One 3D Detail tier: multisampling, shadow pass, particle share, post effects, grid density.

    ``post_effects`` admits a transition's own post-effect settings (Bloom and
    Motion Blur on its Settings page); a tier without multisampling then renders
    through a single-sample scene target only while one is in use. ``grid_cells``
    is the bendable grid's cells along the photograph's longer side.
    """

    name: str
    samples: int
    shadows: bool
    particles: float
    post_effects: bool = False
    grid_cells: int = 64


# The canonical ``transitions.detail_3d`` values, cheapest last. High renders the
# scene into a 4x multisampled target; the others draw straight into Quick's.
# High and Balanced honour each transition's post-effect settings; Performance none.
SCENE3D_DETAIL_TIERS: dict[str, Scene3DDetail] = {
    "High": Scene3DDetail("High", 4, True, 1.0, post_effects=True, grid_cells=192),
    "Balanced": Scene3DDetail("Balanced", 0, True, 0.6, post_effects=True, grid_cells=128),
    "Performance": Scene3DDetail("Performance", 0, False, 0.3, grid_cells=64),
}
SCENE3D_DETAIL_NAMES = tuple(SCENE3D_DETAIL_TIERS)


def scene3d_detail(name: object) -> Scene3DDetail:
    detail = SCENE3D_DETAIL_TIERS.get(str(name))
    if detail is None:
        raise ValueError(f"unknown 3D Detail tier: {name!r}")
    return detail


# Each 3D transition's own quality choices (on its Settings page). "Auto" follows the
# global tier; any other value is authoritative for that transition. Resolution
# (``resolve_scene_quality``) is the one place the two combine into effective values.
SCENE3D_ANTIALIASING_CHOICES = ("Auto", "Off", "2x", "4x", "8x")
SCENE3D_EFFECT_CHOICES = ("Auto", "Off", "On")


def scene3d_samples(detail: Scene3DDetail, choice: object) -> int:
    """Multisampling for one transition: its own choice, or the tier's for Auto."""
    if choice == "Off":
        return 0
    if choice in ("2x", "4x", "8x"):
        return int(str(choice)[0])
    return detail.samples


def scene3d_post_effect(detail: Scene3DDetail, choice: object) -> bool:
    """Whether one post effect (Bloom, Motion Blur) runs: the transition's choice, or the tier's."""
    if choice == "On":
        return True
    if choice == "Off":
        return False
    return detail.post_effects


def scene3d_request_samples(parameters) -> int:
    """The resolved multisampling a request carries; a request built without it draws directly."""
    return int(parameters.get("samples", 0))


# Motion blur's shutter in real seconds: the whole frame interval at 60 Hz (a 360-degree
# shutter; 180 degrees read too weak on real photos). Real time, not progress, so a piece
# blurs by how fast it moves on screen whatever the run's duration.
SCENE3D_SHUTTER_SECONDS = 1.0 / 60.0


def scene3d_shutter_progress(duration_ms: float) -> float:
    """The shutter as a fraction of a run lasting ``duration_ms``."""
    return SCENE3D_SHUTTER_SECONDS * 1000.0 / max(float(duration_ms), 1.0)


# Photo reflections: the per-run copy's longer side, and the mip level a roughness of 1 reads
# (7 levels down from 512 px: about 4 px across, the photograph's broad colours).
SCENE3D_ENVIRONMENT_SIZE = 512
SCENE3D_ENVIRONMENT_ROUGH_LEVEL = 7.0

SCENE3D_CAMERA = 3.4
SCENE3D_NEAR = 0.22
SCENE3D_FAR = 9.0
_KEY = (-0.38, 0.57, 0.73)
_KEY_LENGTH = math.sqrt(sum(value * value for value in _KEY))
SCENE3D_KEY_LIGHT = tuple(value / _KEY_LENGTH for value in _KEY)

SCENE3D_VELOCITY_GLSL = """
// How far a surface point moved on screen over the shutter, in target pixels: its clip
// position now minus its clip position at t - shutter (both evaluated analytically).
// A point behind the camera at either time contributes no motion.
vec2 sceneVelocity(vec4 clipNow, vec4 clipPrevious, vec2 viewportPixels) {
    if (clipNow.w <= 0.0 || clipPrevious.w <= 0.0) return vec2(0.0);
    return (clipNow.xy / clipNow.w - clipPrevious.xy / clipPrevious.w) * 0.5 * viewportPixels;
}
"""

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

// World point -> clip space through the Quick item matrix for a camera resting at
// ``distance`` (each effect keeps its authored distance). w stays the distance in
// front of the camera, so attributes interpolate perspective-correctly and the GPU
// clips against the near plane.
vec4 sceneProjectAt(mat4 matrix, vec2 itemSize, vec3 world, float distance) {{
    float aspect = itemSize.x / itemSize.y;
    float w = distance - world.z;
    vec2 scaled = vec2(world.x / aspect, -world.y) * distance + 0.5 * w;
    vec4 clip = matrix * vec4(scaled * itemSize, 0.0, w);
    clip.z = sceneClipDepth(w);
    return clip;
}}

vec4 sceneProject(mat4 matrix, vec2 itemSize, vec3 world) {{
    return sceneProjectAt(matrix, itemSize, world, SCENE_CAMERA);
}}

// A moving camera: a = (distance, zoom, offset.x, offset.y), b = (tilt about x,
// tilt about y, 0, 0) in radians about the photograph's centre. At rest (zoom 1,
// no offset or tilt) it is exactly sceneProjectAt. A camera that moves must draw the
// photograph through it too (MeshResources.draw_camera_plane) with the zoom from
// scene3d_camera_overscan, so the frame edges are never exposed (R-63).
vec3 sceneCameraSpace(vec3 world, vec4 a, vec4 b) {{
    float cx = cos(b.x), sx = sin(b.x), cy = cos(b.y), sy = sin(b.y);
    vec3 p = vec3(world.x, world.y * cx - world.z * sx, world.y * sx + world.z * cx);
    p = vec3(p.x * cy + p.z * sy, p.y, -p.x * sy + p.z * cy);
    return vec3(p.xy - a.zw, p.z);
}}

vec4 sceneProjectCamera(mat4 matrix, vec2 itemSize, vec3 world, vec4 a, vec4 b) {{
    vec3 p = sceneCameraSpace(world, a, b);
    float aspect = itemSize.x / itemSize.y;
    float w = a.x - p.z;
    vec2 scaled = vec2(p.x / aspect, -p.y) * a.x * a.y + 0.5 * w;
    vec4 clip = matrix * vec4(scaled * itemSize, 0.0, w);
    clip.z = sceneClipDepth(w);
    return clip;
}}

// Item UV (0..1, y down) of a point on the photograph plane z = 0.
vec2 scenePlaneUv(vec2 world, float aspect) {{
    return vec2(world.x / aspect, -world.y) + 0.5;
}}

// Where the photograph's point at uv (v down) lies at rest: the inverse of scenePlaneUv.
vec3 scenePlanePoint(vec2 uv, float aspect) {{
    return vec3((uv.x - 0.5) * aspect, 0.5 - uv.y, 0.0);
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

// Photo reflections. The environment is a photograph (a mipmapped, renderer-owned copy)
// taken as a mirror ball around the scene: a reflected ray looking straight back at the
// viewer sees its centre, one grazing sideways its edge, so a reflection travels across
// the picture as a piece turns, wherever it is on screen.
vec2 sceneReflectionUv(vec3 ray) {{
    return 0.5 + vec2(ray.x, -ray.y) * 0.5;
}}

// The photograph at uv (mirrored past its edges), blurred by roughness (0 sharp, 1 its
// broad colours).
vec3 sceneEnvironment(sampler2D environment, vec2 uv, float roughness) {{
    vec2 mirrored = 1.0 - abs(1.0 - mod(uv, 2.0));
    return textureLod(environment, mirrored, clamp(roughness, 0.0, 1.0) * {SCENE3D_ENVIRONMENT_ROUGH_LEVEL:.1f}).rgb;
}}

// Light a glossy surface reflects from the environment: the reflection where its ray
// points, weighted by Fresnel from reflectance (facing) to 1 (grazing).
vec3 sceneEnvironmentLight(sampler2D environment, vec3 normal, vec3 view, float roughness, float reflectance) {{
    vec3 ray = reflect(-view, normal);
    float fresnel = reflectance + (1.0 - reflectance) * pow(1.0 - max(dot(normal, view), 0.0), 5.0);
    return sceneEnvironment(environment, sceneReflectionUv(ray), roughness) * fresnel;
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
// A rigid piece: a unit box scaled per axis by extent (a negative component mirrors that
// axis), turned by tilt about tiltAxis and then by spin about spinAxis, at centre.
struct ScenePiece {{
    vec3 centre; vec3 extent; vec3 tiltAxis; float tilt; vec3 spinAxis; float spin;
}};

vec3 scenePiecePoint(ScenePiece piece, vec3 unit) {{
    return piece.centre + sceneRotate(sceneRotate(unit * piece.extent, piece.tiltAxis, piece.tilt),
                                      piece.spinAxis, piece.spin);
}}

// A piece's soft shadow on the plane z = plane, cast along the key light: its face grown by
// its thickness and by a penumbra that widens with height. corner is the item-quad corner in
// [0, 1]^2. screen is the shadow's point on the photograph (uv); local and feather feed
// sceneSoftRect; onScreen fades the shadow as its piece leaves the view and low as the
// piece rises (both 1 at rest). The effect multiplies in its own strength.
struct SceneShadow {{
    vec4 clip; vec2 screen; vec2 local; float feather; float onScreen; float low;
}};

SceneShadow scenePieceShadow(mat4 matrix, vec2 itemSize, ScenePiece piece, float plane, vec2 corner) {{
    SceneShadow shadow;
    float extent = min(abs(piece.extent.x), abs(piece.extent.y));
    float height = max(piece.centre.z - plane, 0.0);
    float thick = 1.0 + abs(piece.extent.z) / extent;
    float feather = 0.04 + 0.15 * height / extent;
    vec2 grown = (corner - 0.5) * (thick + 2.0 * feather);
    shadow.screen = scenePlaneUv(sceneCastOnPlane(scenePiecePoint(piece, vec3(grown, 0.5)), plane),
                                 itemSize.x / itemSize.y);
    shadow.clip = matrix * vec4(shadow.screen * itemSize, 0.0, 1.0);
    shadow.local = grown / thick;
    shadow.feather = feather / thick;
    float aspect = itemSize.x / itemSize.y;
    vec2 seen = scenePlaneUv(piece.centre.xy * SCENE_CAMERA / max(SCENE_CAMERA - piece.centre.z, SCENE_NEAR), aspect);
    vec2 outside = max(max(-seen, seen - 1.0), 0.0) * vec2(aspect, 1.0);
    shadow.onScreen = 1.0 - smoothstep(0.0, 0.12, max(outside.x, outside.y));
    shadow.low = 1.0 - smoothstep(0.04, 0.5, height);
    return shadow;
}}

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

// A particle launched from origin at velocity: exponential drag slows it, fall pulls it
// down (both per unit of the effect's time t).
vec3 sceneParticleAt(vec3 origin, vec3 velocity, float drag, float fall, float t) {{
    return origin + velocity * (1.0 - exp(-drag * t)) / drag + vec3(0.0, -fall * t * t, 0.0);
}}

// The particle as a camera-facing streak from where it was trail ago to where it is now
// (trail 0: a soft sprite of the given width).
vec4 sceneParticleStreak(mat4 matrix, vec2 itemSize, vec3 origin, vec3 velocity, float drag, float fall,
                         float t, float trail, float width, vec2 corner) {{
    vec3 head = sceneParticleAt(origin, velocity, drag, fall, t);
    vec3 tail = sceneParticleAt(origin, velocity, drag, fall, max(t - trail, 0.0));
    return sceneStreak(matrix, itemSize, tail, head, width, corner);
}}
""" + SCENE3D_VELOCITY_GLSL


_CULLED = "vec4(2.0, 2.0, 2.0, 1.0)"   # the effects' off-screen sentinel for a piece not yet in play
_UNIFORM_STATEMENT = re.compile(r"^\s*(?://[^\n]*\n\s*)*uniform\b")


def _after_version(source: str, insert: str) -> str:
    head, newline, rest = source.partition("\n")
    if not head.startswith("#version") or not newline:
        raise ValueError("a shader for motion blur must start with its #version line")
    return head + "\n" + insert + rest


def _rename_main(source: str, name: str) -> str:
    if len(re.findall(r"\bvoid\s+main\s*\(\s*\)", source)) != 1:
        raise ValueError("a shader for motion blur must define main() exactly once")
    return re.sub(r"\bvoid\s+main\s*\(\s*\)", f"void {name}()", source)


def scene3d_motion_vertex(source: str, time_uniform: str = "uProgress") -> str:
    """The same vertex shader, also giving where each point was one shutter ago.

    ``time_uniform`` must be the shader's only input that changes over the run.
    Every use of it (but its declaration) reads the global ``sceneTime``, and
    ``main`` runs twice: at ``<time_uniform>Before`` (the value one shutter ago,
    set by the renderer) and at ``time_uniform``, so every output is the current
    one. ``vClipNow`` / ``vClipBefore`` carry both clip positions to
    ``scene3d_motion_fragment``. A point that was not in play a shutter ago (the
    off-screen sentinel) has no motion.
    """
    uses = re.compile(rf"\b{re.escape(time_uniform)}\b")
    statements = source.split(";")
    if not any(_UNIFORM_STATEMENT.match(statement) and uses.search(statement) for statement in statements):
        raise ValueError(f"the shader does not declare {time_uniform}")
    source = ";".join(statement if _UNIFORM_STATEMENT.match(statement) else uses.sub("sceneTime", statement)
                      for statement in statements)
    source = _rename_main(source, "sceneVertexMain")
    source = _after_version(source, f"float sceneTime;\nuniform float {time_uniform}Before;\n"
                                    "out vec4 vClipNow;\nout vec4 vClipBefore;\n")
    return source + f"""
void main() {{
    sceneTime = {time_uniform}Before;
    sceneVertexMain();
    vec4 before = gl_Position;
    sceneTime = {time_uniform};
    sceneVertexMain();
    vClipNow = gl_Position;
    vClipBefore = before == {_CULLED} ? gl_Position : before;
}}
"""


def scene3d_motion_fragment(source: str) -> str:
    """The same fragment shader, also writing its screen motion to location 1."""
    if len(re.findall(r"\bout\s+vec4\s+FragColor\s*;", source)) != 1:
        raise ValueError("a shader for motion blur must write one vec4 FragColor")
    source = re.sub(r"(?:layout\s*\(\s*location\s*=\s*0\s*\)\s*)?\bout\s+vec4\s+FragColor\s*;",
                    "layout(location = 0) out vec4 FragColor;", source)
    source = _rename_main(source, "sceneFragmentMain")
    velocity = "" if "sceneVelocity" in source else SCENE3D_VELOCITY_GLSL
    source = _after_version(source, "in vec4 vClipNow;\nin vec4 vClipBefore;\nuniform vec2 uViewport;\n"
                                    "layout(location = 1) out vec4 SceneMotion;\n" + velocity)
    return source + """
void main() {
    sceneFragmentMain();
    SceneMotion = vec4(sceneVelocity(vClipNow, vClipBefore, uViewport), 0.0, 1.0);
}
"""


# ---- The bendable grid surface (Page Curl, Accordion, Relief Rise, terrains, ribbons) ----

def scene3d_grid_size(detail: Scene3DDetail, aspect: float) -> tuple[int, int]:
    """Grid cells (columns, rows): the tier's density along the longer side, square cells."""
    long_side = max(2, int(detail.grid_cells))
    if aspect >= 1.0:
        return long_side, max(2, round(long_side / aspect))
    return max(2, round(long_side * aspect)), long_side


@lru_cache(maxsize=8)
def scene3d_grid_vertices(columns: int, rows: int) -> tuple[float, ...]:
    """A static triangle list over the photograph: (u, v) per vertex, v down, uv in [0, 1].

    Two triangles per cell, wound consistently, so the displaced surface's normals and
    any face culling agree. Built once per size (cached), never per frame.
    """
    if columns < 1 or rows < 1:
        raise ValueError("a grid needs at least one cell each way")
    values: list[float] = []
    for row in range(rows):
        v0, v1 = row / rows, (row + 1) / rows
        for column in range(columns):
            u0, u1 = column / columns, (column + 1) / columns
            values.extend((u0, v0, u0, v1, u1, v1, u0, v0, u1, v1, u1, v0))
    return tuple(values)


def scene3d_grid_vertex_source(displacement_glsl: str, declarations_glsl: str = "") -> str:
    """The grid's vertex shader around an effect's ``vec3 sceneDisplace(vec2 uv)``.

    ``declarations_glsl`` holds the effect's uniforms (and helpers) that its
    displacement reads. The surface's normal comes from the displacement itself
    (central differences one cell apart), so any bend is lit correctly. With
    ``sceneDisplace`` returning ``scenePlanePoint`` the photograph is drawn exactly.
    Outputs: ``vUv`` (the photograph's uv at the point), ``vWorld``, ``vNormal``
    (toward the viewer at rest).
    """
    if not re.search(r"\bvec3\s+sceneDisplace\s*\(\s*vec2\s+\w+\s*\)", displacement_glsl):
        raise ValueError("the grid's displacement must define vec3 sceneDisplace(vec2 uv)")
    return ("#version 460 core\nlayout(location = 0) in vec2 aGrid;\n"
            "uniform mat4 uMatrix;\nuniform vec2 uItemSize;\nuniform vec2 uGridCells;\n"
            "out vec2 vUv;\nout vec3 vWorld;\nout vec3 vNormal;\n"
            + SCENE3D_GLSL + declarations_glsl + displacement_glsl + """
void main() {
    vec3 world = sceneDisplace(aGrid);
    vec2 cell = 1.0 / uGridCells;
    vec3 acrossU = sceneDisplace(aGrid + vec2(cell.x, 0.0)) - sceneDisplace(aGrid - vec2(cell.x, 0.0));
    vec3 acrossV = sceneDisplace(aGrid + vec2(0.0, cell.y)) - sceneDisplace(aGrid - vec2(0.0, cell.y));
    vNormal = normalize(cross(acrossV, acrossU));
    vUv = aGrid;
    vWorld = world;
    gl_Position = sceneProject(uMatrix, uItemSize, world);
}
""")


def scene3d_reflection_uv(ray: Vec3) -> tuple[float, float]:
    """CPU mirror of ``sceneReflectionUv``."""
    return 0.5 + ray[0] * 0.5, 0.5 - ray[1] * 0.5


def scene3d_ghost_fragment(source: str) -> str:
    """A piece's ghost for the motion trails: its motion-writing fragment shader writing only
    ``uGhostFade``, a flat silhouette of the piece's exact shape (its discards still apply).

    The ghost's vertex stage evaluates the piece at the ghost's moment (the time input) and
    *now* (the ``Before`` input), so the fragment knows how far the piece has moved since;
    a piece that moved less than the trail's line reaches (``trail_line``) draws no ghost,
    so a still or slow piece never trails or wears a halo of its own outline.
    """
    if len(re.findall(r"\bout\s+vec4\s+FragColor\s*;", source)) != 1:
        raise ValueError("a shader for motion trails must write one vec4 FragColor")
    if not all(name in source for name in ("vClipNow", "vClipBefore", "uViewport", "sceneVelocity")):
        raise ValueError("motion trails need a motion-writing fragment (a ghost must know how far its piece moved)")
    source = _rename_main(source, "sceneTrailMain")
    source = _after_version(source, "uniform float uGhostFade;\n")
    return source + """
void main() {
    sceneTrailMain();
    if (length(sceneVelocity(vClipNow, vClipBefore, uViewport)) < max(1.5, uViewport.y / 540.0) + 1.5) discard;
    FragColor = vec4(uGhostFade);
}
"""


# Motion trails: ghosts a fixed real time apart (like the shutter, whatever the run's length),
# oldest first and faintest; a fade per ghost, the newest brightest.
SCENE3D_TRAIL_GHOSTS = 3
SCENE3D_TRAIL_GAP_SECONDS = 0.045
SCENE3D_TRAIL_CHOICES = ("Off", "On")


def scene3d_trail_ghosts(progress: float, duration_ms: float) -> tuple[tuple[float, float], ...]:
    """(progress, fade) of each ghost, oldest first; a ghost before the run's start rests there."""
    step = SCENE3D_TRAIL_GAP_SECONDS * 1000.0 / max(float(duration_ms), 1.0)
    count = SCENE3D_TRAIL_GHOSTS
    return tuple((max(float(progress) - step * age, 0.0), 1.0 - age / (count + 1))
                 for age in range(count, 0, -1))


def scene3d_velocity(clip_now: tuple[float, float, float, float], clip_previous: tuple[float, float, float, float],
                     viewport_pixels: tuple[float, float]) -> tuple[float, float]:
    if clip_now[3] <= 0.0 or clip_previous[3] <= 0.0:
        return 0.0, 0.0
    return tuple((clip_now[i] / clip_now[3] - clip_previous[i] / clip_previous[3]) * 0.5 * viewport_pixels[i]
                 for i in range(2))


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


# ---- Remaining CPU mirrors (tests compare them with the GPU; see test_scene3d_glsl_mirrors) ----

_MASK32 = 0xFFFFFFFF
Vec3 = tuple[float, float, float]


def _mix_bits(x: int) -> int:
    x &= _MASK32
    x ^= x >> 16
    x = (x * 0x7FEB352D) & _MASK32
    x ^= x >> 15
    x = (x * 0x846CA68B) & _MASK32
    x ^= x >> 16
    return x


def scene3d_random(key: int, salt: int, seed: int) -> float:
    """CPU mirror of ``sceneRandom`` (exact 32-bit integer arithmetic)."""
    inner = _mix_bits((seed * 0x85EBCA6B + salt) & _MASK32)
    return _mix_bits(((key * 0x9E3779B9) & _MASK32) ^ inner) / 4294967295.0


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _normalize(a: Vec3) -> Vec3:
    length = math.sqrt(_dot(a, a))
    return (a[0] / length, a[1] / length, a[2] / length)


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _mix(a: Vec3, b: Vec3, t: float) -> Vec3:
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def scene3d_rotate(point: Vec3, axis: Vec3, angle: float) -> Vec3:
    """CPU mirror of ``sceneRotate`` (axis must be unit length)."""
    c, s = math.cos(angle), math.sin(angle)
    across, along = _cross(axis, point), _dot(axis, point) * (1.0 - c)
    return tuple(p * c + x * s + a * along for p, x, a in zip(point, across, axis))


def scene3d_clip_depth(w: float) -> float:
    """CPU mirror of ``sceneClipDepth``: clip z for a point w in front of the camera."""
    return ((SCENE3D_FAR + SCENE3D_NEAR) * w - 2.0 * SCENE3D_FAR * SCENE3D_NEAR) / (SCENE3D_FAR - SCENE3D_NEAR)


def scene3d_shade(albedo: Vec3, normal: Vec3, world: Vec3, ambient: float, specular: float,
                  shininess: float, rim: float) -> Vec3:
    """CPU mirror of ``sceneShade``."""
    view = _normalize((-world[0], -world[1], SCENE3D_CAMERA - world[2]))
    diffuse = max(_dot(normal, SCENE3D_KEY_LIGHT), 0.0)
    halfway = _normalize(tuple(k + v for k, v in zip(SCENE3D_KEY_LIGHT, view)))
    highlight = max(_dot(normal, halfway), 0.0) ** shininess
    fresnel = (1.0 - max(_dot(normal, view), 0.0)) ** 5.0
    extra = specular * highlight + rim * fresnel
    return tuple(a * (ambient + (1.0 - ambient) * diffuse) + extra for a in albedo)


def scene3d_point_light(normal: Vec3, world: Vec3, light: Vec3, colour: Vec3, falloff: float) -> Vec3:
    """CPU mirror of ``scenePointLight``."""
    to_light = tuple(l - w for l, w in zip(light, world))
    distance2 = _dot(to_light, to_light)
    inverse = 1.0 / math.sqrt(max(distance2, 1e-6))
    facing = max(_dot(normal, tuple(v * inverse for v in to_light)), 0.0)
    return tuple(c * facing / (1.0 + distance2 * falloff) for c in colour)


def scene3d_ember(t: float) -> Vec3:
    """CPU mirror of ``sceneEmber``."""
    t = max(0.0, min(1.0, t))
    warm = _mix((0.50, 0.05, 0.01), (1.0, 0.42, 0.08), _smoothstep(0.0, 0.55, t))
    return _mix(warm, (1.0, 0.90, 0.62), _smoothstep(0.55, 1.0, t))


def scene3d_soft_rect(local: tuple[float, float], feather: float) -> float:
    """CPU mirror of ``sceneSoftRect``."""
    return ((1.0 - _smoothstep(0.5 - feather, 0.5 + feather, abs(local[0])))
            * (1.0 - _smoothstep(0.5 - feather, 0.5 + feather, abs(local[1]))))


def _apply(matrix: tuple[float, ...], vector: tuple[float, float, float, float]) -> list[float]:
    # Column-major 4x4, as Qt/OpenGL uniforms.
    return [sum(matrix[column * 4 + row] * vector[column] for column in range(4)) for row in range(4)]


@dataclass(frozen=True)
class Scene3DPiece:
    """CPU mirror of ``ScenePiece``."""

    centre: Vec3
    extent: Vec3
    tilt_axis: Vec3
    tilt: float
    spin_axis: Vec3
    spin: float


def scene3d_piece_point(piece: Scene3DPiece, unit: Vec3) -> Vec3:
    """CPU mirror of ``scenePiecePoint``."""
    local = tuple(u * e for u, e in zip(unit, piece.extent))
    turned = scene3d_rotate(scene3d_rotate(local, piece.tilt_axis, piece.tilt), piece.spin_axis, piece.spin)
    return tuple(c + t for c, t in zip(piece.centre, turned))


def scene3d_piece_shadow(matrix: tuple[float, ...], item_size: tuple[float, float], piece: Scene3DPiece,
                         plane: float, corner: tuple[float, float]) -> dict[str, object]:
    """CPU mirror of ``scenePieceShadow``: clip, screen, local, feather, on_screen, low."""
    aspect = item_size[0] / item_size[1]
    extent = min(abs(piece.extent[0]), abs(piece.extent[1]))
    height = max(piece.centre[2] - plane, 0.0)
    thick = 1.0 + abs(piece.extent[2]) / extent
    feather = 0.04 + 0.15 * height / extent
    grown = tuple((c - 0.5) * (thick + 2.0 * feather) for c in corner)
    cast = scene3d_cast_on_plane(scene3d_piece_point(piece, (grown[0], grown[1], 0.5)), plane)
    screen = (cast[0] / aspect + 0.5, -cast[1] + 0.5)
    depth = max(SCENE3D_CAMERA - piece.centre[2], SCENE3D_NEAR)
    seen = (piece.centre[0] * SCENE3D_CAMERA / depth / aspect + 0.5, -piece.centre[1] * SCENE3D_CAMERA / depth + 0.5)
    outside = (max(-seen[0], seen[0] - 1.0, 0.0) * aspect, max(-seen[1], seen[1] - 1.0, 0.0))
    return {
        "clip": tuple(_apply(matrix, (screen[0] * item_size[0], screen[1] * item_size[1], 0.0, 1.0))),
        "screen": screen, "local": (grown[0] / thick, grown[1] / thick), "feather": feather / thick,
        "on_screen": 1.0 - _smoothstep(0.0, 0.12, max(outside)), "low": 1.0 - _smoothstep(0.04, 0.5, height),
    }


def scene3d_streak(matrix: tuple[float, ...], item_size: tuple[float, float], tail: Vec3, head: Vec3,
                   width: float, corner: tuple[float, float]) -> tuple[float, float, float, float]:
    """CPU mirror of ``sceneStreak``: clip position of one streak corner."""
    aspect = item_size[0] / item_size[1]
    wt, wh = SCENE3D_CAMERA - tail[2], SCENE3D_CAMERA - head[2]
    if min(wt, wh) <= SCENE3D_NEAR:
        return (2.0, 2.0, 2.0, 1.0)
    a = ((tail[0] / aspect * SCENE3D_CAMERA / wt + 0.5) * item_size[0], (-tail[1] * SCENE3D_CAMERA / wt + 0.5) * item_size[1])
    b = ((head[0] / aspect * SCENE3D_CAMERA / wh + 0.5) * item_size[0], (-head[1] * SCENE3D_CAMERA / wh + 0.5) * item_size[1])
    axis = (b[0] - a[0], b[1] - a[1])
    span = math.hypot(*axis)
    along = (axis[0] / span, axis[1] / span) if span > 1e-3 else (1.0, 0.0)
    size = width * SCENE3D_CAMERA / wh
    start = (a[0] - along[0] * size * 0.5, a[1] - along[1] * size * 0.5)
    end = (b[0] + along[0] * size * 0.5, b[1] + along[1] * size * 0.5)
    point = (start[0] + (end[0] - start[0]) * corner[0] - along[1] * (corner[1] - 0.5) * size,
             start[1] + (end[1] - start[1]) * corner[0] + along[0] * (corner[1] - 0.5) * size)
    clip = _apply(matrix, (point[0], point[1], 0.0, 1.0))
    w = wt + (wh - wt) * corner[0]
    clip[2] = scene3d_clip_depth(w) / w * clip[3]
    return tuple(clip)


def scene3d_particle_at(origin: Vec3, velocity: Vec3, drag: float, fall: float, t: float) -> Vec3:
    """CPU mirror of ``sceneParticleAt``."""
    reach = (1.0 - math.exp(-drag * t)) / drag
    return (origin[0] + velocity[0] * reach, origin[1] + velocity[1] * reach - fall * t * t,
            origin[2] + velocity[2] * reach)


def scene3d_particle_streak(matrix: tuple[float, ...], item_size: tuple[float, float], origin: Vec3, velocity: Vec3,
                            drag: float, fall: float, t: float, trail: float, width: float,
                            corner: tuple[float, float]) -> tuple[float, float, float, float]:
    """CPU mirror of ``sceneParticleStreak``."""
    head = scene3d_particle_at(origin, velocity, drag, fall, t)
    tail = scene3d_particle_at(origin, velocity, drag, fall, max(t - trail, 0.0))
    return scene3d_streak(matrix, item_size, tail, head, width, corner)


# ---- std140 uniform blocks (pure layout; the GL buffer is rendering.quick.scene3d.uniforms) ----

# type -> (base alignment, size, struct format), per the std140 rules for these types.
_STD140 = {
    "float": (4, 4, "f"), "int": (4, 4, "i"), "uint": (4, 4, "I"),
    "vec2": (8, 8, "2f"), "ivec2": (8, 8, "2i"),
    "vec3": (16, 12, "3f"), "vec4": (16, 16, "4f"),
    "mat4": (16, 64, "16f"),
}


@dataclass(frozen=True)
class Scene3DBlockLayout:
    """One per-frame uniform block: its GLSL declaration, std140 offsets and packing
    all come from one field list, so shader and Python cannot disagree."""

    name: str
    fields: tuple[tuple[str, str], ...]
    offsets: tuple[int, ...]
    size: int

    @classmethod
    def of(cls, name: str, fields: tuple[tuple[str, str], ...]) -> "Scene3DBlockLayout":
        offsets, cursor = [], 0
        for _field, glsl_type in fields:
            alignment, size, _format = _STD140[glsl_type]
            cursor = -(-cursor // alignment) * alignment
            offsets.append(cursor)
            cursor += size
        return cls(name, tuple(fields), tuple(offsets), -(-cursor // 16) * 16)

    def glsl(self) -> str:
        members = "".join(f"    {glsl_type} {field};\n" for field, glsl_type in self.fields)
        return f"layout(std140) uniform {self.name} {{\n{members}}};\n"

    def pack(self, values) -> bytes:
        import struct

        data = bytearray(self.size)
        for (field, glsl_type), offset in zip(self.fields, self.offsets):
            value = values[field]
            fmt = _STD140[glsl_type][2]
            items = tuple(value) if isinstance(value, (tuple, list)) else (value,)
            struct.pack_into("<" + fmt, data, offset, *items)
        return bytes(data)

    def pack_fields(self, values) -> tuple[tuple[int, bytes], ...]:
        """Pack selected named members at their std140 offsets."""
        import struct

        members = {field: (glsl_type, offset) for (field, glsl_type), offset in zip(self.fields, self.offsets)}
        packed = []
        for field, value in values.items():
            try:
                glsl_type, offset = members[field]
            except KeyError as exc:
                raise KeyError(f"{self.name} has no field {field!r}") from exc
            fmt = _STD140[glsl_type][2]
            items = tuple(value) if isinstance(value, (tuple, list)) else (value,)
            packed.append((offset, struct.pack("<" + fmt, *items)))
        return tuple(packed)


@dataclass(frozen=True)
class Scene3DStorageLayout:
    """One std430 shader-storage array of records (instances, events, history, materials).

    The GLSL struct and buffer declaration, member offsets, record stride and packing all
    come from one field list, like ``Scene3DBlockLayout``. Members are scalars, vectors
    and mat4 (std430 aligns them as std140 does); a record's stride is its size rounded to
    its largest member alignment, without std140's rounding to 16.
    """

    name: str
    record: str
    array: str
    fields: tuple[tuple[str, str], ...]
    offsets: tuple[int, ...]
    stride: int

    @classmethod
    def of(cls, name: str, record: str, fields: tuple[tuple[str, str], ...],
           array: str = "records") -> "Scene3DStorageLayout":
        offsets, cursor, largest = [], 0, 1
        for _field, glsl_type in fields:
            alignment, size, _format = _STD140[glsl_type]
            largest = max(largest, alignment)
            cursor = -(-cursor // alignment) * alignment
            offsets.append(cursor)
            cursor += size
        return cls(name, record, array, tuple(fields), tuple(offsets), -(-cursor // largest) * largest)

    def glsl(self, binding: int, qualifier: str = "readonly") -> str:
        members = "".join(f"    {glsl_type} {field};\n" for field, glsl_type in self.fields)
        return (f"struct {self.record} {{\n{members}}};\n"
                f"layout(std430, binding = {binding}) {qualifier} buffer {self.name} {{\n"
                f"    {self.record} {self.array}[];\n}};\n")

    def pack(self, records) -> bytes:
        import struct

        data = bytearray(self.stride * len(records))
        for index, values in enumerate(records):
            base = index * self.stride
            for (field, glsl_type), offset in zip(self.fields, self.offsets):
                value = values[field]
                items = tuple(value) if isinstance(value, (tuple, list)) else (value,)
                struct.pack_into("<" + _STD140[glsl_type][2], data, base + offset, *items)
        return bytes(data)

    def dtype(self):
        """The record as a numpy structured dtype, for packing many records without a loop."""
        import numpy as np

        kinds = {"f": "<f4", "i": "<i4", "I": "<u4"}
        formats = []
        for _field, glsl_type in self.fields:
            fmt = _STD140[glsl_type][2]
            count, kind = (int(fmt[:-1]), fmt[-1]) if len(fmt) > 1 else (1, fmt)
            formats.append(kinds[kind] if count == 1 else (kinds[kind], (count,)))
        return np.dtype({"names": [field for field, _type in self.fields], "formats": formats,
                         "offsets": list(self.offsets), "itemsize": self.stride})


# ---- Camera (CPU side: mirrors, overscan and shake) ----

def scene3d_screen_uv_at(world: Vec3, aspect: float, distance: float) -> tuple[float, float]:
    """CPU mirror of ``sceneProjectAt`` after the divide, as item UV."""
    scale = distance / (distance - world[2])
    return world[0] / aspect * scale + 0.5, -world[1] * scale + 0.5


def scene3d_camera_space(world: Vec3, a: tuple[float, float, float, float],
                         b: tuple[float, float, float, float]) -> Vec3:
    """CPU mirror of ``sceneCameraSpace``."""
    cx, sx, cy, sy = math.cos(b[0]), math.sin(b[0]), math.cos(b[1]), math.sin(b[1])
    x, y, z = world[0], world[1] * cx - world[2] * sx, world[1] * sx + world[2] * cx
    x, z = x * cy + z * sy, -x * sy + z * cy
    return x - a[2], y - a[3], z


def scene3d_camera_uv(world: Vec3, aspect: float, a: tuple[float, float, float, float],
                      b: tuple[float, float, float, float]) -> tuple[float, float]:
    """CPU mirror of ``sceneProjectCamera`` after the divide, as item UV."""
    x, y, z = scene3d_camera_space(world, a, b)
    scale = a[0] * a[1] / (a[0] - z)
    return x / aspect * scale + 0.5, -y * scale + 0.5


def _inside_convex(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    sign = 0.0
    for index, (x0, y0) in enumerate(polygon):
        x1, y1 = polygon[(index + 1) % len(polygon)]
        cross = (x1 - x0) * (point[1] - y0) - (y1 - y0) * (point[0] - x0)
        if abs(cross) < 1e-12:
            continue
        if sign == 0.0:
            sign = cross
        elif cross * sign < 0.0:
            return False
    return True


def scene3d_camera_overscan(distance: float, offset: tuple[float, float], tilt: tuple[float, float],
                            aspect: float) -> float:
    """Least zoom (>= 1) at which the photograph plane still covers the whole view.

    The plane z = 0 fills the item exactly at rest; an offset or tilt would expose
    its edges (R-63), so the camera zooms in by at least this much.
    """
    a = (distance, 1.0, offset[0], offset[1])
    b = (tilt[0], tilt[1], 0.0, 0.0)
    half = aspect * 0.5
    quad = [scene3d_camera_uv((x, y, 0.0), aspect, a, b) for x, y in ((-half, 0.5), (half, 0.5), (half, -0.5), (-half, -0.5))]
    zoom_low, zoom_high = 1.0, 1.0

    def covered(zoom: float) -> bool:
        # Zooming scales the projected plane about the view centre.
        scaled = [((u - 0.5) * zoom + 0.5, (v - 0.5) * zoom + 0.5) for u, v in quad]
        return all(_inside_convex(corner, scaled) for corner in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))

    if covered(1.0):
        return 1.0
    while not covered(zoom_high):
        zoom_high *= 1.25
        if zoom_high > 64.0:
            raise ValueError("camera motion too large to cover the view")
    for _ in range(40):
        middle = (zoom_low + zoom_high) * 0.5
        zoom_low, zoom_high = (zoom_low, middle) if covered(middle) else (middle, zoom_high)
    return zoom_high


def scene3d_camera_shake(seconds: float, amplitude: float, seed: int) -> tuple[float, float]:
    """A deterministic handheld shake at real-time rates (about 3-7 Hz), in world units.

    Stays within ``amplitude`` on each axis; the caller scales it by its own envelope
    (zero at rest and at both endpoints) and zooms by ``scene3d_camera_overscan``.
    """
    phase = [scene3d_random(index, 91, seed) * 2.0 * math.pi for index in range(4)]
    x = 0.6 * math.sin(seconds * 23.0 + phase[0]) + 0.4 * math.sin(seconds * 41.0 + phase[1])
    y = 0.6 * math.sin(seconds * 19.0 + phase[2]) + 0.4 * math.sin(seconds * 37.0 + phase[3])
    return x * amplitude, y * amplitude
