"""Exploding Tiles: a beveled-slab mesh blown apart by an analytic blast.

Cracks race out from the blast point and glow; at the detonation a flash and a
shock front release each tile with an impulse (drag, then drift and gravity),
tumbling and flying toward the viewer, hot at the edges and lit by the fireball.
Sparks, soft shadows on the new photograph and multisampling come from the
shared 3D scene library and the run's 3D Detail tier. Every piece is clear of
the frame by ``EXPLODING_TILES_SETTLE`` by construction.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping

from rendering.gl_programs.scene3d import (
    SCENE3D_DETAIL_NAMES,
    SCENE3D_GLSL,
    Scene3DBlockLayout,
    scene3d_impulse,
)


EXPLODING_TILES_VERTEX_STRIDE_FLOATS = 8


def _triangle(result, first, second, third, normal) -> None:
    for position, uv in (first, second, third):
        result.extend((*position, *normal, *uv))


def exploding_tiles_box_vertices(bevel: float = 0.12) -> tuple[float, ...]:
    """Return a unit slab with broad faces and lit bevel bands.

    Depth is unit-relative here. The shader scales it from the physical grid
    cell, so density and viewport aspect cannot create a microscopic extrusion.
    """
    inset = max(0.02, min(0.22, float(bevel)))
    inner = (
        (-0.5 + inset, -0.5),
        (0.5 - inset, -0.5),
        (0.5, -0.5 + inset),
        (0.5, 0.5 - inset),
        (0.5 - inset, 0.5),
        (-0.5 + inset, 0.5),
        (-0.5, 0.5 - inset),
        (-0.5, -0.5 + inset),
    )
    outer = (
        (-0.5, -0.5),
        (0.5, -0.5),
        (0.5, 0.5),
        (-0.5, 0.5),
    )
    result: list[float] = []
    for z, normal, winding in (
        (0.5, (0.0, 0.0, 1.0), 1),
        (-0.5, (0.0, 0.0, -1.0), -1),
    ):
        centre = ((0.0, 0.0, z), (0.5, 0.5))
        for index, point in enumerate(inner):
            following = inner[(index + 1) % len(inner)]
            a = ((point[0], point[1], z), (point[0] + 0.5, point[1] + 0.5))
            b = (
                (following[0], following[1], z),
                (following[0] + 0.5, following[1] + 0.5),
            )
            _triangle(
                result, centre, a if winding > 0 else b, b if winding > 0 else a, normal
            )
    side_indices = ((0, 1), (2, 3), (4, 5), (6, 7))
    for side, (first, second) in enumerate(side_indices):
        point, following = outer[side], outer[(side + 1) % len(outer)]
        inner_point, inner_following = inner[first], inner[second]
        mid_x = (point[0] + following[0] + inner_point[0] + inner_following[0]) * 0.25
        mid_y = (point[1] + following[1] + inner_point[1] + inner_following[1]) * 0.25
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, 0.45)
        a = ((point[0], point[1], 0.38), (point[0] + 0.5, point[1] + 0.5))
        b = (
            (following[0], following[1], 0.38),
            (following[0] + 0.5, following[1] + 0.5),
        )
        c = (
            (inner_following[0], inner_following[1], 0.5),
            (inner_following[0] + 0.5, inner_following[1] + 0.5),
        )
        d = (
            (inner_point[0], inner_point[1], 0.5),
            (inner_point[0] + 0.5, inner_point[1] + 0.5),
        )
        _triangle(result, a, b, c, normal)
        _triangle(result, a, c, d, normal)
    for corner, previous, following in ((0, 7, 0), (1, 1, 2), (2, 3, 4), (3, 5, 6)):
        point = outer[corner]
        mid_x = point[0] + inner[previous][0] + inner[following][0]
        mid_y = point[1] + inner[previous][1] + inner[following][1]
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, 0.45)
        a = ((point[0], point[1], 0.38), (point[0] + 0.5, point[1] + 0.5))
        b = (
            (inner[following][0], inner[following][1], 0.5),
            (inner[following][0] + 0.5, inner[following][1] + 0.5),
        )
        c = (
            (inner[previous][0], inner[previous][1], 0.5),
            (inner[previous][0] + 0.5, inner[previous][1] + 0.5),
        )
        _triangle(result, a, b, c, normal)
    for index, point in enumerate(outer):
        following = outer[(index + 1) % len(outer)]
        mid_x, mid_y = (point[0] + following[0]) * 0.5, (point[1] + following[1]) * 0.5
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, 0.0)
        a = ((point[0], point[1], 0.38), (0.0, 0.0))
        b = ((following[0], following[1], 0.38), (1.0, 0.0))
        c = ((following[0], following[1], -0.38), (1.0, 1.0))
        d = ((point[0], point[1], -0.38), (0.0, 1.0))
        _triangle(result, a, c, b, normal)
        _triangle(result, a, d, c, normal)
    for side, (first, second) in enumerate(side_indices):
        point, following = outer[side], outer[(side + 1) % len(outer)]
        inner_point, inner_following = inner[first], inner[second]
        mid_x = (point[0] + following[0] + inner_point[0] + inner_following[0]) * 0.25
        mid_y = (point[1] + following[1] + inner_point[1] + inner_following[1]) * 0.25
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, -0.45)
        a = ((point[0], point[1], -0.38), (point[0] + 0.5, point[1] + 0.5))
        b = (
            (following[0], following[1], -0.38),
            (following[0] + 0.5, following[1] + 0.5),
        )
        c = (
            (inner_following[0], inner_following[1], -0.5),
            (inner_following[0] + 0.5, inner_following[1] + 0.5),
        )
        d = (
            (inner_point[0], inner_point[1], -0.5),
            (inner_point[0] + 0.5, inner_point[1] + 0.5),
        )
        _triangle(result, a, c, b, normal)
        _triangle(result, a, d, c, normal)
    for corner, previous, following in ((0, 7, 0), (1, 1, 2), (2, 3, 4), (3, 5, 6)):
        point = outer[corner]
        mid_x = point[0] + inner[previous][0] + inner[following][0]
        mid_y = point[1] + inner[previous][1] + inner[following][1]
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, -0.45)
        a = ((point[0], point[1], -0.38), (point[0] + 0.5, point[1] + 0.5))
        b = (
            (inner[previous][0], inner[previous][1], -0.5),
            (inner[previous][0] + 0.5, inner[previous][1] + 0.5),
        )
        c = (
            (inner[following][0], inner[following][1], -0.5),
            (inner[following][0] + 0.5, inner[following][1] + 0.5),
        )
        _triangle(result, a, b, c, normal)
    return tuple(result)


EXPLODING_TILES_BOX_VERTICES = exploding_tiles_box_vertices()
EXPLODING_TILES_VERTEX_COUNT = (
    len(EXPLODING_TILES_BOX_VERTICES) // EXPLODING_TILES_VERTEX_STRIDE_FLOATS
)

# The run's timeline (fractions of the transition). Cracks race out from the
# blast until the detonation; its shock front then releases each tile with an
# impulse, and every piece is clear of the frame by SETTLE.
EXPLODING_TILES_DETONATION = 0.09
EXPLODING_TILES_SETTLE = 0.98
EXPLODING_TILES_DRAG = 20.0
EXPLODING_TILES_DRIFT = 0.15
EXPLODING_TILES_SPARKS = 480
_FRONT_SPAN = {True: 0.10, False: 0.16}
_SPARK_LIFE_MAX = 0.30
_BLAST_FADE = (0.60, 0.85)


def exploding_tiles_parameters(
    parameters: Mapping[str, object],
) -> tuple[int, int, float, float, float, str, int, float, bool]:
    """Validate resolved-only tile controls before GL state changes."""
    seed, columns, depth = (
        parameters.get("seed"),
        parameters.get("columns"),
        parameters.get("depth"),
    )
    thickness, force = parameters.get("thickness"), parameters.get("force")
    detail, samples, bloom = parameters.get("detail"), parameters.get("samples"), parameters.get("bloom")
    motion_blur = parameters.get("motion_blur", False)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Exploding Tiles seed must be an integer between 1 and 65535")
    if (
        isinstance(columns, bool)
        or not isinstance(columns, int)
        or not 6 <= columns <= 48
    ):
        raise ValueError("Exploding Tiles columns must be an integer between 6 and 48")
    if (
        isinstance(depth, bool)
        or not isinstance(depth, (int, float))
        or not math.isfinite(float(depth))
        or not 0.2 <= float(depth) <= 1.5
    ):
        raise ValueError("Exploding Tiles depth must be finite and between 0.2 and 1.5")
    if (
        isinstance(thickness, bool)
        or not isinstance(thickness, (int, float))
        or not math.isfinite(float(thickness))
        or not 0.0 <= float(thickness) <= 1.0
    ):
        raise ValueError("Exploding Tiles thickness must be finite and between 0 and 1")
    if (
        isinstance(force, bool)
        or not isinstance(force, (int, float))
        or not math.isfinite(float(force))
        or not 0.5 <= float(force) <= 2.0
    ):
        raise ValueError("Exploding Tiles force must be finite and between 0.5 and 2")
    if detail not in SCENE3D_DETAIL_NAMES:
        raise ValueError(f"Exploding Tiles detail must be one of {', '.join(SCENE3D_DETAIL_NAMES)}")
    if (
        isinstance(bloom, bool)
        or not isinstance(bloom, (int, float))
        or not math.isfinite(float(bloom))
        or not 0.0 <= float(bloom) <= 1.0
    ):
        raise ValueError("Exploding Tiles bloom must be finite and between 0 and 1")
    if isinstance(samples, bool) or samples not in (0, 2, 4, 8):
        raise ValueError("Exploding Tiles samples must be 0, 2, 4 or 8")
    if not isinstance(motion_blur, bool):
        raise ValueError("Exploding Tiles motion blur must be on or off")
    return (seed, columns, float(depth), float(thickness), float(force), str(detail), int(samples), float(bloom),
            motion_blur)


def exploding_tiles_grid(columns: int, width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Exploding Tiles requires a positive viewport")
    return int(columns), max(6, min(48, int(round(columns * height / width))))


def exploding_tiles_epicentre(
    vector: tuple[float, float] | None, seed: int, aspect: float
) -> tuple[float, float, float]:
    """World position of the blast and its reach (distance to the farthest corner).

    Center Out blasts near the middle. A direction (screen vector, y down) blasts
    from the frame edge or corner the pieces fly away from, so they travel that way.
    """
    rng = random.Random(int(seed) * 7919 + 101)
    half_x, half_y = aspect * 0.5, 0.5
    if vector is None:
        x = (rng.random() - 0.5) * 0.16 * aspect
        y = (rng.random() - 0.5) * 0.16
    else:
        world_x, world_y = float(vector[0]), -float(vector[1])
        along = rng.random() - 0.5
        x = -math.copysign(half_x * 1.02, world_x) if abs(world_x) > 0.3 else along * half_x
        y = -math.copysign(half_y * 1.02, world_y) if abs(world_y) > 0.3 else along * half_y
    reach = max(math.hypot(cx - x, cy - y) for cx in (-half_x, half_x) for cy in (-half_y, half_y))
    return x, y, reach


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def exploding_tiles_blast(progress: float) -> tuple[float, float]:
    """(flash, fire): the detonation's light. Exactly zero before it and by 85%."""
    p = float(progress)
    fade = 1.0 - _smoothstep(*_BLAST_FADE, p)
    if fade <= 0.0 or p < EXPLODING_TILES_DETONATION - 0.004:
        return 0.0, 0.0
    age = max(p - EXPLODING_TILES_DETONATION, 0.0)
    fire = _smoothstep(EXPLODING_TILES_DETONATION - 0.004, EXPLODING_TILES_DETONATION + 0.006, p)
    flash = math.exp(-age * 70.0) if p >= EXPLODING_TILES_DETONATION else 0.0
    return flash * fade, fire * math.exp(-age * 7.5) * fade


def exploding_tiles_dominant_colour(
    rgba8: bytes, pixel_size: tuple[int, int], row_stride: int
) -> tuple[float, float, float]:
    """The photograph's most used colour, as 0..1 RGB.

    The fullest bin of a coarse (3 bits per channel) histogram over a sparse
    64 x 36 sample grid, averaged within that bin: cheap enough to run once per
    run, and a real majority colour rather than a muddy mean.
    """
    width, height = int(pixel_size[0]), int(pixel_size[1])
    data = memoryview(rgba8)
    bins: dict[int, list[int]] = {}
    for row in range(36):
        base = ((2 * row + 1) * height // 72) * row_stride
        for column in range(64):
            index = base + 4 * ((2 * column + 1) * width // 128)
            red, green, blue = data[index], data[index + 1], data[index + 2]
            entry = bins.setdefault((red >> 5) << 6 | (green >> 5) << 3 | blue >> 5, [0, 0, 0, 0])
            entry[0] += 1
            entry[1] += red
            entry[2] += green
            entry[3] += blue
    count, red, green, blue = max(bins.values(), key=lambda entry: entry[0])
    return red / (255.0 * count), green / (255.0 * count), blue / (255.0 * count)


def exploding_tile_release(reach: float, force: float, center_out: bool, jitter: float = 0.0) -> float:
    """CPU mirror of ``tileRelease``: when the shock front frees a tile."""
    span = _FRONT_SPAN[bool(center_out)] / math.sqrt(force)
    return EXPLODING_TILES_DETONATION + span * max(0.0, min(1.0, reach)) ** 0.85 + jitter * 0.012


def exploding_tile_travel(tau: float) -> float:
    """CPU mirror of a tile's flight curve: an impulse, not an ease-in."""
    return scene3d_impulse(max(0.0, tau), EXPLODING_TILES_DRAG, EXPLODING_TILES_DRIFT)


def exploding_tiles_sparks_live(progress: float, force: float, center_out: bool) -> bool:
    """Whether any spark can be alive; outside this window the pass is skipped."""
    last = exploding_tile_release(1.0, force, center_out, 1.0) + _SPARK_LIFE_MAX
    return EXPLODING_TILES_DETONATION <= float(progress) <= last


# Everything the passes share per frame travels in one uniform block (one upload per frame);
# the matrix, item size and textures stay per pass because the shared item quad uses them.
EXPLODING_TILES_FRAME_BLOCK = Scene3DBlockLayout.of("ExplodingTilesFrame", (
    ("uGrid", "vec2"), ("uProgress", "float"), ("uSeed", "float"), ("uDepth", "float"),
    ("uThickness", "float"), ("uForce", "float"), ("uCenterOut", "int"), ("uEpicentre", "vec3"),
    ("uSeconds", "float"), ("uBlast", "vec2"), ("uBody", "vec3"), ("uEmissive", "float"),
    ("uShutter", "float"), ("uViewport", "vec2"),
))
_FRAME_GLSL = EXPLODING_TILES_FRAME_BLOCK.glsl()
_MOTION_UNIFORMS_GLSL = "uniform mat4 uMatrix; uniform vec2 uItemSize;\n" + _FRAME_GLSL

_TILE_MOTION_GLSL = f"""
const float DETONATE = {EXPLODING_TILES_DETONATION:.6f};
const float SETTLE = {EXPLODING_TILES_SETTLE:.6f};
const float DRAG = {EXPLODING_TILES_DRAG:.6f};
const float DRIFT = {EXPLODING_TILES_DRIFT:.6f};

struct Tile {{
    vec2 size; vec2 cellUv; float slab; float slabFull; vec3 centre;
    vec3 tiltAxis; float tilt; vec3 spinAxis; float spin;
    float released; float lit; float crack; float glow; float heat; float near;
}};

float tileRelease(float reach, float jitter) {{
    return DETONATE + (uCenterOut == 1 ? {_FRONT_SPAN[True]:.6f} : {_FRONT_SPAN[False]:.6f}) / sqrt(uForce)
        * pow(reach, 0.85) + jitter * 0.012;
}}

Tile tileAtTime(uint id, float progress) {{
    Tile t;
    uint seed = uint(uSeed + 0.5);
    uint columns = uint(uGrid.x + 0.5);
    vec2 cell = vec2(float(id % columns), float(id / columns));
    float aspect = uItemSize.x / uItemSize.y;
    t.size = vec2(aspect / uGrid.x, 1.0 / uGrid.y);
    t.cellUv = (cell + 0.5) / uGrid;
    vec2 home = vec2((t.cellUv.x - 0.5) * aspect, 0.5 - t.cellUv.y);
    vec2 away = home - uEpicentre.xy;
    float reach = clamp(length(away) / uEpicentre.z, 0.0, 1.0);
    t.near = 1.0 - reach;
    float near2 = t.near * t.near;
    float r0 = sceneRandom(id, 1u, seed), r1 = sceneRandom(id, 2u, seed), r2 = sceneRandom(id, 3u, seed);
    float r3 = sceneRandom(id, 4u, seed), r4 = sceneRandom(id, 5u, seed), r5 = sceneRandom(id, 6u, seed);
    float r6 = sceneRandom(id, 7u, seed), r7 = sceneRandom(id, 8u, seed), r8 = sceneRandom(id, 9u, seed);

    // Cracks race out from the blast, then its shock front releases each tile.
    float release = tileRelease(reach, r0);
    float cracked = 0.015 + (DETONATE - 0.025) * pow(reach, 0.7);
    float p = min(progress, SETTLE);
    float tau = max(p - release, 0.0);
    float flight = SETTLE - release;
    float build = smoothstep(cracked, release, progress);
    t.crack = smoothstep(cracked, cracked + 0.02, progress);
    // Cracks glow at the heart of the blast as it builds, then in a ring racing
    // just ahead of the shock front: each tile heats in the moment before it breaks free.
    t.glow = max(smoothstep(cracked + 0.01, DETONATE + 0.01, progress) * smoothstep(0.6, 0.95, t.near),
                 smoothstep(release - 0.025, release, progress));
    t.released = smoothstep(0.0, 0.015, tau);
    // Only the heart of the blast domes and tilts before release; the rest of the
    // wall stays exactly on the photograph so its seams line up to the pixel.
    float core = smoothstep(0.55, 0.95, t.near);
    float dome = core * build * build;
    t.lit = max(t.released, dome);
    // The front face stays on the photograph; thickness grows in behind it once cracked.
    t.slabFull = min(t.size.x, t.size.y) * (0.10 + 0.90 * uThickness);
    t.slab = t.slabFull * t.crack;
    // Rumble: a low shudder through the cracked wall over the last part of each tile's
    // wait for the shock front (from 40% of the way between cracking and release),
    // hardest near the blast and building to the release, where the flight takes over
    // smoothly. The rate is real time (about 2.7-5 Hz) whatever the run's duration, and
    // neighbouring tiles move nearly together, so the wall shakes rather than jitters.
    float rumbleStart = mix(cracked, release, 0.4);
    float shake = smoothstep(rumbleStart, rumbleStart + 0.03, progress) * (1.0 - t.released)
                * (0.2 + 0.8 * t.near) * (0.5 + 0.5 * smoothstep(rumbleStart, release, progress)) * sqrt(uForce);
    float seconds = progress * uSeconds;
    float phase = dot(home, vec2(2.1, 1.7)) + r6 * 1.2;
    vec2 rumble = 0.0022 * shake * vec2(
        sin(seconds * 17.0 + phase) + 0.5 * sin(seconds * 27.0 + phase * 1.3 + r7 * 2.0),
        sin(seconds * 19.0 + phase * 0.9 + 1.7) + 0.5 * sin(seconds * 31.0 + phase * 1.1 + r5 * 2.0));
    float radius = 0.5 * length(vec3(t.size, t.slab)) + 0.02;

    // Heading: away from the blast, loosened by a seeded scatter that grows at its heart.
    float turn = r1 * 6.2831853;
    vec2 scatter = vec2(cos(turn), sin(turn));
    vec2 radial = length(away) > 1e-4 ? normalize(away) : scatter;
    vec2 heading = normalize(radial + scatter * (0.18 + 0.55 * near2));
    vec2 fall = vec2(0.0, -(0.8 + 0.5 * r2));

    // Speed: the blast's own push, raised only as far as needed for the tile to be
    // clear of the frame by its exit time, and still clear when the run settles.
    vec2 halfBox = vec2(aspect * 0.5, 0.5) + radius;
    float exitTau = min(0.40 + 0.40 * r8, 0.86 - release);
    float speed = uForce * (0.12 + 0.35 * near2) * (0.7 + 0.6 * r3);
    speed = max(speed, sceneDepartureTravel(home + fall * exitTau * exitTau, heading, halfBox)
                       / sceneImpulse(exitTau, DRAG, DRIFT));
    speed = max(speed, sceneDepartureTravel(home + fall * flight * flight, heading, halfBox)
                       / sceneImpulse(flight, DRAG, DRIFT));

    // Toward the viewer: strongest at the blast; a few pieces fly past the camera.
    // Settled pieces sit in front of the photograph, so perspective only pushes them out.
    float lift = uDepth * (0.05 + 0.45 * near2) * (0.45 + 0.55 * r4);
    if (r5 < 0.10 * t.near) lift *= 2.6;
    lift = max(lift, (radius + 0.5 * t.slab) / sceneImpulse(flight, DRAG, DRIFT));
    float bulge = uDepth * 0.018 * dome;

    float travel = sceneImpulse(tau, DRAG, DRIFT);
    t.centre = vec3(home + rumble + heading * speed * travel + fall * tau * tau,
                    -0.5 * t.slab + bulge + lift * travel);
    t.tiltAxis = vec3(-radial.y, radial.x, 0.0);
    t.tilt = 0.09 * dome + 0.03 * shake * sin(seconds * 21.0 + phase + r1 * 2.0);
    t.spinAxis = normalize(vec3(-heading.y, heading.x, 0.0) * 1.2 + (vec3(r6, r7, r2) - 0.5) * 1.2);
    t.spin = uForce * (1.8 + 2.8 * r3) * (0.6 + 0.8 * t.near) * sceneImpulse(tau, 8.0, 0.35);
    // A brief white-hot flash on pieces near the blast, cooled to nothing within ~0.04 of the run.
    t.heat = t.released * t.near * t.near * exp(-tau * 30.0);
    return t;
}}

Tile tileAt(uint id) {{
    return tileAtTime(id, uProgress);
}}

// The tile as a rigid piece (its mesh is authored y-down, hence the mirrored y).
ScenePiece tilePiece(Tile t) {{
    return ScenePiece(t.centre, vec3(t.size.x, -t.size.y, t.slab), t.tiltAxis, t.tilt, t.spinAxis, t.spin);
}}

vec3 tilePoint(Tile t, vec3 unit) {{
    return scenePiecePoint(tilePiece(t), unit);
}}

vec3 tileNormal(Tile t, vec3 normal) {{
    return normalize(sceneRotate(sceneRotate(vec3(normal.x, -normal.y, normal.z), t.tiltAxis, t.tilt),
                                 t.spinAxis, t.spin));
}}
"""

_BACKDROP_GLSL = """
const vec3 BLAST_FIRE = vec3(1.0, 0.5, 0.18);
// The blast's light on the new photograph: a warm fireball glow and the flash.
vec3 blastLight(vec2 uv, vec3 photo) {
    vec2 world = vec2((uv.x - 0.5) * uItemSize.x / uItemSize.y, 0.5 - uv.y) - uEpicentre.xy;
    float d2 = dot(world, world);
    vec3 fire = BLAST_FIRE * uBlast.y * (0.45 * exp(-d2 * 9.0) + 0.10 * exp(-d2 * 1.5)) * (0.4 + photo);
    return fire + uBlast.x * 0.25 * (photo + fire + 0.15);
}
vec3 blastBackdrop(vec2 uv) {
    vec3 photo = texture(uNewTex, uv).rgb;
    return photo + blastLight(uv, photo);
}
// What glows (bloom) on the photograph: only the flash. The fireball is light cast on the
// picture over a wide area; blooming it would bloom the picture's own colours.
vec3 blastGlow(vec3 photo) {
    return uBlast.x * 0.25 * (photo + 0.15);
}
"""

_OUTPUT_GLSL = """
// While the scene renders into a bloom target, alpha is the brightness of the light the
// pixel emits (additive passes add theirs), so the bloom takes the light, never the photograph.
vec4 sceneOutput(vec3 colour, vec3 emitted) {
    return vec4(colour, uEmissive > 0.5 ? clamp(dot(emitted, vec3(0.2126, 0.7152, 0.0722)), 0.0, 1.0) : 1.0);
}
"""

EXPLODING_TILES_VERTEX_SOURCE = (
    "#version 410 core\n"
    "layout(location=0) in vec3 aPosition;\n"
    "layout(location=1) in vec3 aNormal;\n"
    "layout(location=2) in vec2 aUv;\n"
    + _MOTION_UNIFORMS_GLSL
    + SCENE3D_GLSL
    + _TILE_MOTION_GLSL
    + """
out vec2 vUv; out vec2 vFace; out vec3 vNormal; out vec3 vWorld;
out float vSurface; out float vLit; out float vCrack; out float vHeat;
out float vReleased; out vec3 vFront;
out vec4 vClipNow; out vec4 vClipBefore;
void main() {
    Tile t = tileAt(uint(gl_InstanceID));
    vec3 world = tilePoint(t, aPosition);
    gl_Position = sceneProject(uMatrix, uItemSize, world);
    // Where this point was one shutter ago (only with motion blur on).
    vClipNow = gl_Position;
    vClipBefore = gl_Position;
    if (uShutter > 0.0) {
        Tile before = tileAtTime(uint(gl_InstanceID), max(uProgress - uShutter, 0.0));
        vClipBefore = sceneProject(uMatrix, uItemSize, tilePoint(before, aPosition));
    }
    // Every surface shows the photograph at its own position in the tile, so the
    // thickness carries the edge colours through: a solid chunk of the picture.
    vFace = aPosition.xy + 0.5;
    vUv = t.cellUv + aPosition.xy / uGrid;
    vNormal = tileNormal(t, aNormal);
    vWorld = world;
    vSurface = aNormal.z;
    vLit = t.lit;
    vCrack = t.crack * (0.35 + 0.65 * t.glow) * (1.0 - t.released);
    vHeat = t.heat;
    vReleased = t.released;
    vFront = tileNormal(t, vec3(0.0, 0.0, 1.0));
}
"""
)

EXPLODING_TILES_FRAGMENT_SOURCE = (
    "#version 410 core\n"
    + """
in vec2 vUv; in vec2 vFace; in vec3 vNormal; in vec3 vWorld;
in float vSurface; in float vLit; in float vCrack; in float vHeat;
in float vReleased; in vec3 vFront;
in vec4 vClipNow; in vec4 vClipBefore;
layout(location = 0) out vec4 FragColor;
layout(location = 1) out vec4 SceneMotion;   // only kept while the target takes motion
uniform sampler2D uOldTex; uniform vec2 uItemSize;
uniform sampler2D uEnvironment;   // the new picture as a blurred environment (photo reflections)
"""
    + _FRAME_GLSL
    + SCENE3D_GLSL
    + _OUTPUT_GLSL
    + """
void main() {
    // Bevels read as flat face until their tile leaves the wall, so the fireball
    // does not paint a grid across the unbroken picture.
    vec3 normal = normalize(vSurface > 0.3 ? mix(vFront, vNormal, vReleased) : vNormal);
    vec3 fire = scenePointLight(normal, vWorld, vec3(uEpicentre.xy, 0.35), vec3(1.0, 0.55, 0.22) * uBlast.y * 1.2, 9.0);
    // Photo reflections: a released tile reflects the new picture it flies over, glossier
    // on its photograph face than on its stone. Nothing before release (the wall is exact).
    vec3 view = normalize(vec3(0.0, 0.0, SCENE_CAMERA) - vWorld);
    vec3 source = texture(uOldTex, vUv).rgb;
    vec3 colour;
    vec3 glow = vec3(0.0);   // emitted light (hot cracks, embers, flash), for the bloom
    if (vSurface > 0.3) {
        // Photograph face and its bevel: exactly the source until the tile is lit.
        float bevel = vSurface < 0.9 ? 1.0 : 0.0;
        vec3 lit = sceneShade(source, normal, vWorld, 0.55, (0.10 + 0.35 * bevel) * vReleased, 36.0, 0.10 * vReleased)
                 + fire * (0.25 + 0.6 * source)
                 + sceneEnvironmentLight(uEnvironment, normal, view, 0.35 - 0.2 * bevel, 0.04) * 0.5 * vReleased;
        colour = mix(source, lit, vLit);
        // Cracks along the tile border, glowing hotter toward the detonation.
        vec2 edge = min(vFace, 1.0 - vFace) * uItemSize / uGrid;
        float gap = min(edge.x, edge.y);
        vec3 hot = sceneEmber(vCrack);
        float line = vCrack * (1.0 - smoothstep(0.0, 0.5 + 0.7 * vCrack, gap));
        // Dark hairlines, glowing only where the crack has heated.
        float heat = smoothstep(0.55, 1.0, vCrack);
        colour = mix(colour, mix(vec3(0.02), hot * 1.3, heat), line);
        glow = hot * 1.3 * heat * line + hot * heat * heat * 0.25 * (1.0 - smoothstep(0.0, 2.0 + 4.0 * vCrack, gap))
             + sceneEmber(vHeat) * vHeat * vHeat * bevel * 0.6;
        colour += glow - hot * 1.3 * heat * line;
    } else {
        // Thickness and back: dark grey stone tinted slightly toward the photograph's
        // most used colour, glowing where the blast heated it.
        vec3 body = mix(vec3(0.25), uBody, 0.44) * 0.75 * (vSurface > -0.3 ? 1.0 : 0.8);
        glow = sceneEmber(vHeat) * vHeat * vHeat * (vSurface > -0.3 ? 0.9 : 0.3);
        colour = sceneShade(body, normal, vWorld, 0.5, 0.12, 28.0, 0.05) + fire * 0.12 + glow
               + sceneEnvironmentLight(uEnvironment, normal, view, 0.8, 0.03) * 0.35 * vReleased;
    }
    vec3 flash = uBlast.x * 0.3 * (colour + 0.1);
    colour += flash;
    FragColor = sceneOutput(colour, glow + flash);
    SceneMotion = vec4(sceneVelocity(vClipNow, vClipBefore, uViewport), 0.0, 1.0);
}
"""
)

EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE = (
    "#version 410 core\n"
    "in vec2 vUv;\nout vec4 FragColor;\n"
    "uniform sampler2D uNewTex; uniform vec2 uItemSize;\n"
    + _FRAME_GLSL
    + _BACKDROP_GLSL
    + _OUTPUT_GLSL
    + "void main() { vec2 uv = vec2(vUv.x, 1.0 - vUv.y); vec3 photo = texture(uNewTex, uv).rgb;"
    " FragColor = sceneOutput(photo + blastLight(uv, photo), blastGlow(photo)); }\n"
)

EXPLODING_TILES_SHADOW_VERTEX_SOURCE = (
    "#version 410 core\n"
    "layout(location=0) in vec2 aPosition;\n"
    + _MOTION_UNIFORMS_GLSL
    + SCENE3D_GLSL
    + _TILE_MOTION_GLSL
    + """
out vec2 vScreen; out vec2 vLocal; flat out float vFeather; flat out float vStrength;
void main() {
    // Each tile's shadow on the plane behind the wall (the shared piece shadow); it
    // leaves with its tile and softens as the tile rises.
    Tile t = tileAt(uint(gl_InstanceID));
    SceneShadow shadow = scenePieceShadow(uMatrix, uItemSize, tilePiece(t), -t.slabFull, aPosition);
    gl_Position = shadow.clip;
    vScreen = shadow.screen;
    vLocal = shadow.local;
    vFeather = shadow.feather;
    vStrength = 0.5 * t.crack * shadow.onScreen * shadow.low * (1.0 - smoothstep(0.85, 0.97, uProgress));
}
"""
)

EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE = (
    "#version 410 core\n"
    "in vec2 vScreen; in vec2 vLocal; flat in float vFeather; flat in float vStrength;\nout vec4 FragColor;\n"
    "uniform sampler2D uNewTex; uniform vec2 uItemSize;\n"
    + _FRAME_GLSL
    + SCENE3D_GLSL
    + _BACKDROP_GLSL
    + """
void main() {
    // Drawn with MIN blending, so overlapping shadows never darken twice.
    FragColor = vec4(blastBackdrop(vScreen) * (1.0 - sceneSoftRect(vLocal, vFeather) * vStrength), 1.0);
}
"""
)

EXPLODING_TILES_SPARK_VERTEX_SOURCE = (
    "#version 410 core\n"
    "layout(location=0) in vec2 aPosition;\n"
    + _MOTION_UNIFORMS_GLSL
    + SCENE3D_GLSL
    + f"""
const float DETONATE = {EXPLODING_TILES_DETONATION:.6f};
out vec2 vQuad; out float vHeat; out float vGlow;
void main() {{
    uint id = uint(gl_InstanceID);
    uint seed = uint(uSeed + 0.5) ^ 0x5bd1e995u;
    float r0 = sceneRandom(id, 11u, seed), r1 = sceneRandom(id, 12u, seed), r2 = sceneRandom(id, 13u, seed);
    float r3 = sceneRandom(id, 14u, seed), r4 = sceneRandom(id, 15u, seed), r5 = sceneRandom(id, 16u, seed);
    float r6 = sceneRandom(id, 17u, seed), r7 = sceneRandom(id, 18u, seed);
    // Born where the shock front passes, crowded toward the heart of the blast.
    float reach = uCenterOut == 1 ? pow(r0, 1.6) : pow(r0, 1.1);
    float turn = r1 * 6.2831853;
    vec2 direction = vec2(cos(turn), sin(turn));
    if (uCenterOut != 1) direction = normalize(normalize(-uEpicentre.xy) + direction * 0.85);
    vec3 origin = vec3(uEpicentre.xy + direction * reach * uEpicentre.z, 0.02);
    float birth = DETONATE + (uCenterOut == 1 ? {_FRONT_SPAN[True]:.6f} : {_FRONT_SPAN[False]:.6f}) / sqrt(uForce)
        * pow(reach, 0.85) + r2 * 0.01;
    float life = 0.06 + {_SPARK_LIFE_MAX - 0.06:.6f} * r3 * r3;
    float t = uProgress - birth;
    vQuad = aPosition;
    if (t <= 0.0 || t >= life) {{
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
        vHeat = 0.0; vGlow = 0.0;
        return;
    }}
    float speed = uForce * (1.5 + 5.5 * r4 * r4) * (1.2 - 0.6 * reach);
    vec3 velocity = vec3(normalize(direction + (vec2(r5, r6) - 0.5) * 0.6) * speed, (0.2 + 1.4 * r7) * uForce);
    gl_Position = sceneParticleStreak(uMatrix, uItemSize, origin, velocity, 11.0, 1.4, t, 0.006,
                                      (0.0016 + 0.0028 * r5) * uItemSize.y, aPosition);
    float age = t / life;
    vHeat = 1.0 - age;
    vGlow = (1.0 - age) * (1.0 - age) * (0.55 + 0.45 * r6);
}}
"""
)

EXPLODING_TILES_SPARK_FRAGMENT_SOURCE = (
    "#version 410 core\n"
    "in vec2 vQuad; in float vHeat; in float vGlow;\nout vec4 FragColor;\n"
    + _FRAME_GLSL
    + SCENE3D_GLSL
    + """
void main() {
    float across = 1.0 - smoothstep(0.15, 0.5, abs(vQuad.y - 0.5));
    float along = smoothstep(0.0, 0.45, vQuad.x);
    float light = vGlow * across * along;
    // Additive: colour adds light; alpha (blended additively too) adds emitted light for the bloom.
    vec3 spark = sceneEmber(0.2 + 0.8 * vHeat) * light * 1.8;
    FragColor = vec4(spark, uEmissive * dot(spark, vec3(0.2126, 0.7152, 0.0722)));
}
"""
)
