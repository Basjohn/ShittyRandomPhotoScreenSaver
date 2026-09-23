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
    return _cells_from_sites(sites, aspect, rng)


def _cells_from_sites(sites, aspect: float, rng: random.Random) -> tuple[GlassShard, ...]:
    """Clip every site's Voronoi cell to the wall; the cells tile it without gaps."""

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


CRUMBLE_PATTERNS = ("impact", "clusters", "warp")


def crumble_cells(seed: int | float, count: int, aspect: float, complexity: float) -> tuple[GlassShard, ...]:
    """Crumble's seeded fracture: a new crack layout every run, mutated by complexity.

    Glass keeps ``fracture_cells``. Crumble starts from the same jittered wall
    grid, then each seed picks a pattern family -- an impact point (small shards
    near it, large slabs far away), a few stress clusters, or an organic domain
    warp -- plus a mild warp for every family. ``complexity`` (0.5-2.0) sets how
    far the layout departs from the grid, over its whole range. Cells stay
    convex Voronoi cells of the wall, so seams remain gap-free and the crack
    stage keeps drawing on real shared borders; a minimum site spacing prevents
    degenerate slivers.
    """

    count = max(4, min(180, int(count)))
    aspect = max(0.1, min(10.0, float(aspect)))
    strength = max(0.0, min(1.0, (float(complexity) - 0.5) / 1.5))
    rng = random.Random(seed)
    columns = max(2, min(count, round(math.sqrt(count * aspect))))
    rows = math.ceil(count / columns)
    spread = .30 + .18 * strength
    sites = [((index % columns + rng.uniform(.5-spread, .5+spread)) / columns * aspect,
              (index // columns + rng.uniform(.5-spread, .5+spread)) / rows)
             for index in range(count)]
    cell = math.sqrt(aspect / count)
    pattern = CRUMBLE_PATTERNS[rng.randrange(len(CRUMBLE_PATTERNS))]

    if pattern == "impact":
        ix, iy = rng.uniform(.18, .82) * aspect, rng.uniform(.15, .85)
        reach = max(math.hypot(max(ix, aspect - ix), max(iy, 1.0 - iy)), 1e-6)
        power = 1.0 + 1.7 * strength
        sites = [(ix + (x - ix) * (math.hypot(x - ix, y - iy) / reach) ** (power - 1.0),
                  iy + (y - iy) * (math.hypot(x - ix, y - iy) / reach) ** (power - 1.0))
                 for x, y in sites]
    elif pattern == "clusters":
        centres = [(rng.uniform(.12, .88) * aspect, rng.uniform(.12, .88))
                   for _ in range(rng.randint(2, 4))]
        pulled = []
        for x, y in sites:
            if rng.random() < .25 + .55 * strength:
                cx, cy = min(centres, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)
                pull = (.30 + .50 * strength) * rng.random()
                x, y = x + (cx - x) * pull, y + (cy - y) * pull
            pulled.append((x, y))
        sites = pulled

    # Every family gets an organic warp; the "warp" family gets a strong one.
    amplitude = cell * strength * (1.25 if pattern == "warp" else .35)
    waves = []
    for _ in range(3):
        angle = rng.uniform(0.0, math.tau)
        frequency = rng.uniform(.8, 2.6) * math.tau
        waves.append((math.cos(angle), math.sin(angle), frequency, rng.uniform(0.0, math.tau)))
    warped = []
    for x, y in sites:
        dx = dy = 0.0
        for ux, uy, frequency, phase in waves:
            wave = math.sin((x * ux + y * uy) * frequency + phase)
            dx += -uy * wave
            dy += ux * wave
        warped.append((x + dx * amplitude / 3.0, y + dy * amplitude / 3.0))

    # Keep sites inside the wall and apart: clusters/impacts may crowd sites,
    # but coincident sites would give overlapping cells and slivers.
    margin = 1e-4
    minimum = cell * (.30 - .14 * strength)
    spaced = []
    for x, y in warped:
        x = min(aspect - margin, max(margin, x))
        y = min(1.0 - margin, max(margin, y))
        for _ in range(4):
            crowded = [(ox, oy) for ox, oy in spaced if (ox - x) ** 2 + (oy - y) ** 2 < minimum * minimum]
            if not crowded:
                break
            ox, oy = crowded[0]
            distance = math.hypot(x - ox, y - oy)
            if distance < 1e-9:
                angle = rng.uniform(0.0, math.tau)
                ux, uy = math.cos(angle), math.sin(angle)
            else:
                ux, uy = (x - ox) / distance, (y - oy) / distance
            x = min(aspect - margin, max(margin, ox + ux * minimum))
            y = min(1.0 - margin, max(margin, oy + uy * minimum))
        spaced.append((x, y))
    return _cells_from_sites(spaced, aspect, rng)


def fracture_vertices(shards: tuple[GlassShard, ...], aspect: float, *,
                      pivots=None, radii=None) -> tuple[float, ...]:
    """Closed beveled prisms, with UV continuity when their release is zero.

    UV2, centre2, depth fraction, normal3, inset flag, face, variation, radius.
    Geometry is uploaded once; thickness and bevel emerge during release. Each
    prism fans from its own centre; ``pivots``/``radii`` let a piece split off
    a Glass shard keep that shard's motion pivot and thickness.
    """
    vertices = []
    for index, shard in enumerate(shards):
        cx, cy = shard.center
        px, py = pivots[index] if pivots is not None else shard.center
        radius = (radii[index] if radii is not None
                  else max(math.hypot((x-cx)*aspect, y-cy) for x, y in shard.polygon))

        def vertex(point, z, normal, inset, face):
            vertices.extend((*point, px, py, z, *normal, inset, face, shard.variation, radius))

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
