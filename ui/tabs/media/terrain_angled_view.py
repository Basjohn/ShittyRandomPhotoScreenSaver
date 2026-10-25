"""The terrain editor's angled view: the heightfield in the scene's own proportions, seen from a raised camera.

Pure geometry (numpy, no Qt painting): build a preview mesh of the authored grid, project it through a small
perspective camera fitted into a rectangle, order its quads back to front, and pick the visible surface point under
the cursor (exact barycentric hits on the projected triangles, nearest to the eye wins), so the editor paints the
same uv in either view. World proportions follow the basin: its width is the nominal 16:9 card's, its depth
``DEPTH``; an extended grid reaches past it as in the scene.

The surface is the scene's own (``scene_surface``, the CPU mirror of ``basinCurve`` / ``basinLandHeight``): the
smooth cubic land with its soft banks, scaled by Terrain Height, never the raw cells. Past the authored grid the
scene's continuation carries the land and water on toward the horizon; the view shows it too (not paintable).

The scene's Sun / Moon sits at infinity in the direction of its authored position seen from the scene's reference
viewpoint (``neon_celestial``). A diorama's raised camera would see the scene's horizon above its frame, so the view
shows the body on a sky dome round the basin at the scene's eye height, in that direction and at its apparent size
(a body on the scene's horizon sits behind the far edge at eye level), and turns a drag of it into authored
X / Y / Z at the same distance (so its apparent size never changes).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from core.constants.neon_lake_world import DEPTH, NOMINAL_HALF_WIDTH
from rendering.gl_programs.neon_celestial import CELESTIAL_REFERENCE

MAX_PREVIEW_QUADS = 64        # per side over the authored grid (the scene's smooth surface, sampled)
CONTINUATION_STEP = 1.0 / 16.0   # the continuation's quads, in grid uv (aligned with the grid's edges)
CONTINUATION_REACH = (0.625, 0.625, 0.0625, 1.75)   # grid uv shown past the grid: left, right, front, back
DEFAULT_YAW, DEFAULT_PITCH = math.radians(28.0), math.radians(30.0)   # a three-quarter view
SKY_SHARE = 0.30              # the upper part of the view kept for the sky and its Sun / Moon
SKY_DOME = 0.5                # the Sun / Moon sky dome's radius, in grid diagonals
PITCH_RANGE = (math.radians(12.0), math.radians(80.0))
YAW_RANGE = (math.radians(-75.0), math.radians(75.0))
_FOCAL = 1.0 / math.tan(math.radians(17.0))   # a 34-degree field of view


@dataclass(frozen=True)
class AngledProjection:
    """Projected preview vertices (``screen`` rows x columns x 2, ``depth`` from the eye) and their uv.

    ``uv`` .. ``depth`` are the authored grid's mesh; ``beyond`` is the continuation's coarser mesh around it
    (``uv``, ``world``, ``screen``, ``depth``, ``height``, ``water``, ``inside``: which quads the grid covers)."""
    stride: int
    uv: np.ndarray        # (rows, cols, 2) grid uv of each preview vertex
    world: np.ndarray     # (rows, cols, 3)
    screen: np.ndarray    # (rows, cols, 2) pixels
    depth: np.ndarray     # (rows, cols) distance along the view axis
    project: object       # world (..., 3) -> (screen (..., 2), depth (...))
    eye: np.ndarray = None        # the view's camera
    direction_at: object = None   # screen point (x, y) -> the world direction of the view ray there
    dome: tuple = ()              # (centre, radius) of the Sun / Moon's sky dome
    height: np.ndarray = None     # (rows, cols) the scene's land height (Terrain Height 1) at each vertex
    water: np.ndarray = None      # (rows, cols) True where the scene has water
    beyond: dict = None           # the continuation's mesh (see the class doc)


def preview_stride(size: int) -> int:
    return max(1, math.ceil((size - 1) / MAX_PREVIEW_QUADS))


def world_points(size: int, basin, u: np.ndarray, v: np.ndarray, height: np.ndarray) -> np.ndarray:
    """World positions of grid uv points (u right, v toward the back) at world ``height``."""
    x0, y0, cells = basin
    n1 = size - 1
    x = ((u * n1 - x0) / cells - 0.5) * 2.0 * NOMINAL_HALF_WIDTH
    z = -((v * n1 - y0) / cells) * DEPTH
    return np.stack([x, np.broadcast_to(height, np.shape(x)), z], axis=-1)


def _smoothstep(low, high, x):
    t = np.clip((x - low) / (high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _bilinear(grid: np.ndarray, gu, gv):
    n1 = grid.shape[0] - 1
    x, y = np.clip(gu, 0.0, 1.0) * n1, np.clip(gv, 0.0, 1.0) * n1
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, n1), np.minimum(y0 + 1, n1)
    fx, fy = x - x0, y - y0
    near = grid[y0, x0] * (1.0 - fx) + grid[y0, x1] * fx
    far = grid[y1, x0] * (1.0 - fx) + grid[y1, x1] * fx
    return near * (1.0 - fy) + far * fy


def _cubic(grid: np.ndarray, gu, gv):
    """The scene's positive cubic B-spline surface (``sceneHeightfieldCurve``)."""
    n1 = grid.shape[0] - 1
    x, y = np.clip(gu, 0.0, 1.0) * n1, np.clip(gv, 0.0, 1.0) * n1
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)

    def weights(t):
        t2, t3 = t * t, t * t * t
        return ((1.0 - t) ** 3 / 6.0, (3.0 * t3 - 6.0 * t2 + 4.0) / 6.0, (-3.0 * t3 + 3.0 * t2 + 3.0 * t + 1.0) / 6.0,
                t3 / 6.0)

    wx, wy = weights(x - ix), weights(y - iy)
    total = np.zeros(np.shape(x))
    for b in range(4):
        rows = np.clip(iy + b - 1, 0, n1)
        for a in range(4):
            total = total + wx[a] * wy[b] * grid[rows, np.clip(ix + a - 1, 0, n1)]
    return total


def scene_surface(grid, basin, gu, gv):
    """(land height at Terrain Height 1, water) of the scene at grid uv, inside the grid or past it: the CPU mirror
    of ``basinBase`` / ``basinCurve`` / ``basinLandHeight`` (without the music's reaction or fine detail)."""
    grid = np.asarray(grid, dtype=np.float64)
    n1 = grid.shape[0] - 1
    x0, y0, cells = basin
    scale = cells / n1
    gu, gv = np.asarray(gu, dtype=np.float64), np.asarray(gv, dtype=np.float64)
    eu, ev = np.clip(gu, 0.0, 1.0), np.clip(gv, 0.0, 1.0)
    du, dv = gu - eu, gv - ev
    outside = np.hypot(du, dv) / scale
    boundary = _bilinear(grid, eu, ev)
    # basinContinuation: the edge carried outward, easing into low rolling land (water stays water).
    interior = _bilinear(grid, np.clip(eu - np.sign(du) / n1, 0.0, 1.0), np.clip(ev - np.sign(dv) / n1, 0.0, 1.0))
    slope = np.clip((boundary - interior) * n1 * scale, -0.8, 0.8)
    near_slope = 0.20 * slope * np.minimum(outside, 0.16)
    descent = _smoothstep(0.04, 0.68, outside)
    bu, bv = gu / scale - x0 / cells, gv / scale - y0 / cells          # basin uv
    background = (0.12 + 0.065 * np.sin(2.7 * bu + 1.7 * bv) * np.cos(2.4 * bv - 0.8 * bu)
                  + 0.040 * np.sin(1.1 * bv - 2.3 * bu))
    rolling = np.maximum(0.025, (boundary + near_slope) * (1.0 - descent) + background * descent)
    continued = rolling * (1.0 - _smoothstep(1.1, 2.2, outside)) + 0.065 * _smoothstep(1.1, 2.2, outside)
    continued = np.where(boundary == 0.0, 0.0, continued)
    inside = outside < 1e-9
    base = np.where(inside, boundary, continued)
    edge_curve = _cubic(grid, eu, ev)
    curve = np.where(inside, edge_curve, np.maximum(0.0, edge_curve + continued - boundary))
    curve = np.where(inside, curve, curve * (1.0 - _smoothstep(1.1, 2.2, outside)) + 0.065 * _smoothstep(1.1, 2.2, outside))
    water = base == 0.0
    land = curve * _smoothstep(0.0, 0.015, base)
    # The scene's shallow convex distant world: the land falls away toward a real horizon.
    land = land - 0.38 * np.maximum(0.0, outside - 0.20) ** 2
    return np.where(water, 0.0, land), water


def surface_points(size: int, heights, basin, u, v, terrain_height: float = 1.0) -> np.ndarray:
    """World positions of grid uv points resting on the scene's surface."""
    grid = np.asarray(heights, dtype=np.float64).reshape(size, size)
    land, _water = scene_surface(grid, basin, u, v)
    return world_points(size, basin, np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64),
                        land * float(terrain_height))


def _camera(yaw: float, pitch: float, centre: np.ndarray, distance: float):
    back = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    eye = centre + back * distance
    right = np.cross(np.array([0.0, 1.0, 0.0]), back)
    right /= np.linalg.norm(right)
    up = np.cross(back, right)
    return eye, right, up, back


def dome_of(extent: float) -> tuple[np.ndarray, float]:
    return np.array([0.0, float(CELESTIAL_REFERENCE[1]), -DEPTH / 2.0]), SKY_DOME * float(extent)


def body_world(dome, x: float, y: float, z: float, size: float):
    """(dome point, world radius there, authored distance) of the body at authored X / Y / Z."""
    authored = np.array([x * NOMINAL_HALF_WIDTH, y, z])
    offset = authored - np.asarray(CELESTIAL_REFERENCE)
    distance = max(0.5, float(np.linalg.norm(offset)))
    centre, radius = dome
    return centre + offset / distance * radius, radius * float(size) / distance, distance


def project_terrain(size: int, heights, basin, rect, *, yaw=DEFAULT_YAW, pitch=DEFAULT_PITCH,
                    body=None, terrain_height: float = 1.0) -> AngledProjection:
    """The scene's surface projected and fitted into ``rect`` (left, top, width, height), whole grid in view, its
    continuation reaching on past it, with the Sun / Moon (``body``: authored x, y, z, size) when it is in front."""
    stride = preview_stride(size)
    grid = np.asarray(heights, dtype=np.float64).reshape(size, size)
    # Two samples a cell (a bank turns within one), at most MAX_PREVIEW_QUADS.
    samples = np.linspace(0.0, 1.0, min(2 * (size - 1), MAX_PREVIEW_QUADS) + 1)
    gv, gu = np.meshgrid(samples, samples, indexing="ij")
    uv = np.stack([gu, gv], axis=-1)
    surface, water = scene_surface(grid, basin, gu, gv)
    world = world_points(size, basin, gu, gv, surface * float(terrain_height))
    left_reach, right_reach, front_reach, back_reach = CONTINUATION_REACH
    bu = np.arange(-left_reach, 1.0 + right_reach + 1e-9, CONTINUATION_STEP)
    bv = np.arange(-front_reach, 1.0 + back_reach + 1e-9, CONTINUATION_STEP)
    beyond_v, beyond_u = np.meshgrid(bv, bu, indexing="ij")
    beyond_land, beyond_water = scene_surface(grid, basin, beyond_u, beyond_v)
    centres_u, centres_v = (beyond_u[:-1, :-1] + beyond_u[1:, 1:]) / 2.0, (beyond_v[:-1, :-1] + beyond_v[1:, 1:]) / 2.0
    beyond = {"uv": np.stack([beyond_u, beyond_v], axis=-1), "height": beyond_land, "water": beyond_water,
              "world": world_points(size, basin, beyond_u, beyond_v, beyond_land * float(terrain_height)),
              "inside": (centres_u > 0.0) & (centres_u < 1.0) & (centres_v > 0.0) & (centres_v < 1.0)}
    lows, highs = world.reshape(-1, 3).min(axis=0), world.reshape(-1, 3).max(axis=0)
    centre = np.array([(lows[0] + highs[0]) / 2.0, 0.0, (lows[2] + highs[2]) / 2.0])
    extent = float(np.linalg.norm(highs - lows))
    eye, right, up, back = _camera(yaw, pitch, centre, 1.6 * extent)

    def raw(points):
        relative = points - eye
        forward = -(relative @ back)
        forward = np.maximum(forward, 1e-3)
        return np.stack([_FOCAL * (relative @ right) / forward, -_FOCAL * (relative @ up) / forward], axis=-1), forward

    # Fit the whole grid's box (up to its highest land, never flatter than a tenth of full) into the rectangle,
    # below a band of sky for the Sun / Moon.
    top = max(float(highs[1]), 0.1)
    corners = np.array([[x, y, z] for x in (lows[0], highs[0]) for y in (0.0, top)
                        for z in (lows[2], highs[2])])
    dome = dome_of(extent)
    if body is not None:
        point, radius, _distance = body_world(dome, *body)
        if float(-(point - eye) @ back) > 1e-3:
            corners = np.vstack([corners, point + up * radius, point - up * radius,
                                 point + right * radius, point - right * radius])
    flat, _ = raw(corners)
    left, top, width, height = rect
    span = np.maximum(flat.max(axis=0) - flat.min(axis=0), 1e-6)
    land = 1.0 - SKY_SHARE
    scale = 0.96 * min(width / span[0], land * height / span[1])
    middle = (flat.max(axis=0) + flat.min(axis=0)) / 2.0
    offset = np.array([left + width / 2.0, top + height * (1.0 - land / 2.0)])

    def project(points):
        screen, forward = raw(points)
        return (screen - middle) * scale + offset, forward

    screen, depth = project(world)
    beyond["screen"], beyond["depth"] = project(beyond["world"])

    def direction_at(point):
        tangent = ((np.asarray(point, dtype=np.float64) - offset) / scale + middle) / _FOCAL
        direction = right * tangent[0] - up * tangent[1] - back
        return direction / np.linalg.norm(direction)

    return AngledProjection(stride, uv, world, screen, depth, project, eye, direction_at, dome, surface, water, beyond)


_BODY_LIMITS = ((-2.0, 2.0), (0.1, 3.0), (-6.0, 2.0))   # the Position X / Y / Z controls' ranges


def body_preview(projection: AngledProjection, x: float, y: float, z: float, size: float):
    """(screen centre or None behind the view, screen radius, authored distance) of the body."""
    point, radius, distance = body_world(projection.dome, x, y, z, size)
    screen, forward = projection.project(point[None, :])
    if float(forward[0]) <= 1e-3:
        return None, 0.0, distance
    edge, _ = projection.project((point + projection.direction_at(screen[0]) * 0.0
                                  + np.cross(projection.direction_at(screen[0]), [0.0, 1.0, 0.0]) * radius
                                  / max(1e-9, float(np.linalg.norm(np.cross(projection.direction_at(screen[0]),
                                                                            [0.0, 1.0, 0.0])))))[None, :])
    return screen[0], float(np.linalg.norm(edge[0] - screen[0])), distance


def place_body(projection: AngledProjection, point, distance: float):
    """Authored (x, y, z) of the body under screen ``point``: where its view ray meets the sky dome (or passes
    nearest it), at the same authored distance."""
    centre, radius = projection.dome
    ray = projection.direction_at(point)
    eye = projection.eye
    along = float((centre - eye) @ ray)
    nearest = eye + ray * along
    miss = float(np.linalg.norm(nearest - centre))
    hit = nearest + ray * math.sqrt(radius * radius - miss * miss) if miss < radius else nearest
    direction = (hit - centre) / max(float(np.linalg.norm(hit - centre)), 1e-9)
    authored = np.asarray(CELESTIAL_REFERENCE) + direction * distance
    values = (authored[0] / NOMINAL_HALF_WIDTH, authored[1], authored[2])
    return tuple(float(max(low, min(high, v))) for v, (low, high) in zip(values, _BODY_LIMITS))


def quad_order(projection: AngledProjection) -> np.ndarray:
    """(row, col) of every preview quad, farthest first (the painter's order)."""
    depth = projection.depth
    centres = (depth[:-1, :-1] + depth[1:, :-1] + depth[:-1, 1:] + depth[1:, 1:]) / 4.0
    rows, cols = np.unravel_index(np.argsort(-centres, axis=None, kind="stable"), centres.shape)
    return np.stack([rows, cols], axis=-1)


def quad_light(projection) -> np.ndarray:
    """0..1 Lambert light of each quad from the upper left front (a projection, or a world mesh)."""
    w = projection.world if isinstance(projection, AngledProjection) else np.asarray(projection)
    across = w[:-1, 1:] - w[:-1, :-1]
    along = w[1:, :-1] - w[:-1, :-1]
    normal = np.cross(along, across)
    normal /= np.maximum(np.linalg.norm(normal, axis=-1, keepdims=True), 1e-9)
    normal *= np.sign(normal[..., 1:2] + 1e-12)
    light = np.array([-0.45, 1.0, 0.55])
    light /= np.linalg.norm(light)
    return np.clip(normal @ light, 0.0, 1.0)


def pick_uv(projection: AngledProjection, point) -> tuple[float, float] | None:
    """The grid uv of the visible surface under ``point`` (pixels), or None over sky."""
    s, d, uv = projection.screen, projection.depth, projection.uv
    p = np.asarray(point, dtype=np.float64)
    best = None
    # Each quad as two triangles: (a, b, c) = (00, 01, 11) and (00, 11, 10).
    a, da, ua = s[:-1, :-1], d[:-1, :-1], uv[:-1, :-1]
    triangles = ((s[:-1, 1:], s[1:, 1:], d[:-1, 1:], d[1:, 1:], uv[:-1, 1:], uv[1:, 1:]),
                 (s[1:, 1:], s[1:, :-1], d[1:, 1:], d[1:, :-1], uv[1:, 1:], uv[1:, :-1]))
    for b_corner, c_corner, db, dc, ub, uc in triangles:
        v0, v1, v2 = b_corner - a, c_corner - a, p - a
        denominator = v0[..., 0] * v1[..., 1] - v1[..., 0] * v0[..., 1]
        safe = np.where(np.abs(denominator) < 1e-12, np.nan, denominator)
        beta = (v2[..., 0] * v1[..., 1] - v1[..., 0] * v2[..., 1]) / safe
        gamma = (v0[..., 0] * v2[..., 1] - v2[..., 0] * v0[..., 1]) / safe
        alpha = 1.0 - beta - gamma
        hit = (alpha >= -1e-9) & (beta >= -1e-9) & (gamma >= -1e-9)
        if not hit.any():
            continue
        depth = np.where(hit, alpha * da + beta * db + gamma * dc, np.inf)
        index = np.unravel_index(np.argmin(depth), depth.shape)
        if best is None or depth[index] < best[0]:
            point_uv = alpha[index] * ua[index] + beta[index] * ub[index] + gamma[index] * uc[index]
            best = (depth[index], (float(point_uv[0]), float(point_uv[1])))
    return None if best is None else best[1]


