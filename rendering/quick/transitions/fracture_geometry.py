"""Pure shared fracture prisms for the admitted Glass Shatter and Crumble renderers."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True, slots=True)
class GlassShard:
    center: tuple[float, float]
    polygon: tuple[tuple[float, float], ...]
    variation: float


def _clip_cell(polygon, nx: float, ny: float, limit: float):
    result = []
    previous = polygon[-1]
    previous_distance = previous[0] * nx + previous[1] * ny - limit
    for current in polygon:
        distance = current[0] * nx + current[1] * ny - limit
        if (distance <= 0.0) != (previous_distance <= 0.0):
            fraction = previous_distance / (previous_distance - distance)
            result.append((previous[0] + fraction * (current[0] - previous[0]),
                           previous[1] + fraction * (current[1] - previous[1])))
        if distance <= 0.0:
            result.append(current)
        previous, previous_distance = current, distance
    return result


def fracture_cells(seed: int | float, count: int, aspect: float, complexity: float = 1.0) -> tuple[GlassShard, ...]:
    """Clip a jittered site set into gap-free convex cells in physical aspect.

    A hard 180-site ceiling bounds quadratic work at admission. No scipy,
    triangulation dependency, process-global random state or per-frame physics.
    """
    count = max(4, min(180, int(count)))
    aspect = max(0.1, min(10.0, float(aspect)))
    rng = random.Random(seed)
    columns = max(2, min(count, round(math.sqrt(count * aspect))))
    rows = math.ceil(count / columns)
    spread = max(.08, min(.48, .38 * float(complexity)))
    # Every site is retained (including the last partial row), with independent
    # offsets so the fracture has irregular cells instead of grid diagonals.
    sites = [((index % columns + rng.uniform(.5-spread, .5+spread)) / columns * aspect,
              (index // columns + rng.uniform(.5-spread, .5+spread)) / rows)
             for index in range(count)]
    shards = []
    for index, (sx, sy) in enumerate(sites):
        polygon = [(0.0, 0.0), (aspect, 0.0), (aspect, 1.0), (0.0, 1.0)]
        # Nearest planes first reduce the polygon quickly; distance ordering
        # is stable and changes no topology or seeded result.
        others = sorted((point for i, point in enumerate(sites) if i != index),
                        key=lambda point: (point[0] - sx)**2 + (point[1] - sy)**2)
        radius_squared = max((x-sx)**2 + (y-sy)**2 for x, y in polygon)
        for ox, oy in others:
            nx, ny = ox - sx, oy - sy
            # A farther bisector cannot intersect this cell's enclosing circle.
            # Ordered distances make all remaining planes provably irrelevant.
            if nx*nx + ny*ny > 4.0*radius_squared:
                break
            limit = (ox * ox + oy * oy - sx * sx - sy * sy) * 0.5
            if all(x * nx + y * ny <= limit for x, y in polygon):
                continue
            polygon = _clip_cell(polygon, nx, ny, limit)
            radius_squared = max((x-sx)**2 + (y-sy)**2 for x, y in polygon)
        # Arithmetic mean lies strictly inside this convex cell and produces
        # valid fan triangles even on clipped display boundaries.
        cx = sum(x for x, _ in polygon) / len(polygon)
        cy = sum(y for _, y in polygon) / len(polygon)
        shards.append(GlassShard((cx / aspect, cy),
                                tuple((x / aspect, y) for x, y in polygon), rng.random()))
    return tuple(shards)


def fracture_vertices(shards: tuple[GlassShard, ...], aspect: float) -> tuple[float, ...]:
    """Closed beveled prisms, with UV continuity when their release is zero.

    UV2, centre2, depth fraction, normal3, inset flag, face, variation, radius.
    Geometry is uploaded once; thickness and bevel emerge during release.
    """
    vertices = []
    for shard in shards:
        cx, cy = shard.center
        radius = max(math.hypot((x-cx)*aspect, y-cy) for x, y in shard.polygon)

        def vertex(point, z, normal, inset, face):
            vertices.extend((*point, cx, cy, z, *normal, inset, face, shard.variation, radius))

        for index, a in enumerate(shard.polygon):
            b = shard.polygon[(index+1) % len(shard.polygon)]
            dx, dy = (b[0]-a[0])*aspect, b[1]-a[1]
            length = math.hypot(dx, dy)
            outward = (dy/length, dx/length, 0.)
            for point in (shard.center, b, a):
                vertex(point, 0., (0., 0., 1.), 1., 0.)
            for point in (shard.center, a, b):
                vertex(point, -1., (0., 0., -1.), 1., 3.)
            # Upper bevel, vertical wall, lower bevel. The clockwise world
            # contour produces outward-facing closed side geometry.
            for z0, z1, inset0, inset1, nz, face in (
                (0., -.22, 1., 0., .8, 1.),
                (-.22, -.78, 0., 0., 0., 2.),
                (-.78, -1., 0., 1., -.8, 1.),
            ):
                normal = (outward[0], outward[1], nz)
                for point, z, inset in ((a,z0,inset0),(b,z0,inset0),(b,z1,inset1),
                                        (a,z0,inset0),(b,z1,inset1),(a,z1,inset1)):
                    vertex(point, z, normal, inset, face)
    return tuple(vertices)
