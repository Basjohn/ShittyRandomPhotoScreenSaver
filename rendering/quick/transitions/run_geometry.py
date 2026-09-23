"""Per-run CPU geometry for the fracture transitions (pure Python; no GL).

Glass Shatter and Crumble build seeded fracture geometry for every run: tens of
milliseconds of pure Python. It used to run on the Qt render thread at the
first transition frame, stalling that display's whole scene. The batch owner
now prepares it on COMPUTE as soon as the batch transition resolves (image
processing runs meanwhile), and the renderer uploads the prepared bytes. When
preparation has not finished, the renderer builds the identical bytes itself:
the builders below are the one reference implementation for both paths.

Only CPU bytes are shared. GL buffers stay with each render context (R-51).
"""

from __future__ import annotations

from array import array
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import math
import random
import threading
from typing import Callable, Hashable, TypeVar

import numpy as np

from core.logging.logger import get_logger

from .fracture_geometry import crumble_cells, fracture_cells, fracture_vertices
from .glass_dynamics import EXTRA_FLOATS, piece_extras, solve_glass_pieces

logger = get_logger(__name__)

# Prism data (as Crumble), then per-piece events: life2, then two stages of
# kick4, spin4, pivot2 (a split piece can crack once more).
GLASS_ATTRIBUTES = (2, 2, 1, 3, 1, 1, 1, 1, 2, 4, 4, 2, 4, 4, 2)
CRUMBLE_CHUNK_ATTRIBUTES = (2, 2, 1, 3, 1, 1, 1, 1, 3)
CRUMBLE_DEBRIS_STRIDE = 6

_T = TypeVar("_T")


def _pack(values: Iterable[float]) -> bytes:
    return array("f", values).tobytes()


# --- Glass Shatter ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GlassGeometry:
    vertices: bytes


def glass_geometry_key(
    parameters: Mapping[str, object], aspect: float, direction: object = None
) -> tuple:
    collisions = bool(parameters.get("collisions", False))
    reshatter = bool(parameters.get("reshatter", False))
    dynamic = collisions or reshatter
    # Collisions and splits follow the shards' paths, which depend on the
    # resolved direction and depth; without them the geometry does not.
    return ("glass_shatter", int(parameters["seed"]), int(parameters["shards"]), float(aspect),
            str(direction) if dynamic else None,
            float(parameters["depth"]) if dynamic else None,
            collisions, reshatter)


def build_glass_geometry(key: tuple) -> GlassGeometry:
    _name, seed, shards, aspect, direction, depth, collisions, reshatter = key
    pieces = solve_glass_pieces(
        fracture_cells(seed, shards, aspect), aspect, direction, depth or 0.0, seed,
        collisions=collisions, reshatter=reshatter,
    )
    prisms = np.asarray(fracture_vertices(
        tuple(piece.shard for piece in pieces), aspect,
        pivots=[piece.pivot_center for piece in pieces],
        radii=[piece.radius for piece in pieces],
    ), dtype=np.float32).reshape(-1, 12)
    per_piece = np.asarray([piece_extras(piece) for piece in pieces], dtype=np.float32).reshape(-1, EXTRA_FLOATS)
    counts = [24 * len(piece.shard.polygon) for piece in pieces]
    extras = np.repeat(per_piece, counts, axis=0)
    return GlassGeometry(np.hstack((prisms, extras)).tobytes())


# --- Crumble ----------------------------------------------------------------


def _number(parameters: Mapping[str, object], name: str, low: float, high: float) -> float:
    value = parameters.get(name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ValueError(f"Crumble requires resolved finite numeric parameter {name!r}")
    value = float(value)
    if not low <= value <= high:
        raise ValueError(f"Crumble {name} must be between {low} and {high}")
    return value


def crumble_parameters(
    parameters: Mapping[str, object],
) -> tuple[float, int, float, float, float, float, float]:
    seed = _number(parameters, "seed", 0.0, 1000.0)
    pieces = parameters.get("piece_count")
    if (
        isinstance(pieces, bool)
        or not isinstance(pieces, int)
        or not 4 <= pieces <= 128
    ):
        raise ValueError("Crumble piece_count must be an integer between 4 and 128")
    complexity = _number(parameters, "crack_complexity", 0.5, 2.0)
    weight = _number(parameters, "weight_mode", 0.0, 4.0)
    if weight not in {0.0, 1.0, 2.0, 3.0, 4.0}:
        raise ValueError("Crumble weight_mode must be one of 0, 1, 2, 3, 4")
    return (
        seed,
        pieces,
        complexity,
        weight,
        _number(parameters, "depth", 0.2, 1.5),
        _number(parameters, "thickness", 0.0, 1.0),
        _number(parameters, "debris", 0.0, 1.0),
    )


# Per-run debris grain: (smallest size, largest size, density multiplier).
_DEBRIS_GRAINS = {
    "fine": (0.30, 0.85, 1.35),
    "mixed": (0.35, 1.45, 1.00),
    "chunky": (0.85, 2.10, 0.70),
}


def debris_instances(seed: float, shards, amount: float) -> tuple[float, ...]:
    """Seeded chips broken off the real crack borders; ``amount`` drives count and size.

    Each run picks a grain (fine, mixed or chunky) and a hot spot, so debris
    concentrates along the cracks nearest it instead of an even sprinkle.
    Metadata: seam point, parent centre, parent variation, size.
    """

    rng = random.Random(seed)
    grain = sorted(_DEBRIS_GRAINS)[rng.randrange(len(_DEBRIS_GRAINS))]
    smallest, largest, density = _DEBRIS_GRAINS[grain]
    hot_x, hot_y = rng.random(), rng.random()
    count = max(12, min(512, round(len(shards) * (2 + 16 * amount) * density)))
    edges = []
    weights = []
    for shard in shards:
        polygon = shard.polygon
        for index, first in enumerate(polygon):
            second = polygon[(index + 1) % len(polygon)]
            length = math.hypot(second[0] - first[0], second[1] - first[1])
            if length <= 0.0:
                continue
            mid_x, mid_y = (first[0] + second[0]) * 0.5, (first[1] + second[1]) * 0.5
            near = math.exp(-math.hypot(mid_x - hot_x, mid_y - hot_y) / 0.30)
            edges.append((shard, first, second))
            weights.append(length * (0.25 + near))
    chosen = rng.choices(edges, weights=weights, k=count)
    growth = 0.75 + 0.5 * amount
    values = []
    for shard, first, second in chosen:
        fraction = rng.random()
        x = first[0] + (second[0] - first[0]) * fraction
        y = first[1] + (second[1] - first[1]) * fraction
        parent_x, parent_y = shard.center
        size = (smallest + (largest - smallest) * rng.random() ** 1.4) * growth
        values.extend((x, y, parent_x, parent_y, shard.variation, size))
    return tuple(values)


def crumble_vertices(shards, aspect: float) -> tuple[float, ...]:
    """Add crack coordinates on the real polygon borders of the shared solids.

    Each front fan triangle has exactly one external polygon edge. Distance
    from that edge and distance along it interpolate across the face; fan
    diagonals receive no crack. Shared edges use the same orientation/phase.
    The prism itself is unchanged, including its closed sides and bevels.
    """
    solid = fracture_vertices(shards, aspect)
    result = []
    for start in range(0, len(solid), 36):
        triangle = [solid[start + offset:start + offset + 12] for offset in (0, 12, 24)]
        if triangle[0][9] == 0.0:
            a, b = sorted((triangle[1][:2], triangle[2][:2]))
            dx, dy = (b[0] - a[0]) * aspect, b[1] - a[1]
            length = math.hypot(dx, dy)
            phase = (a[0] + b[0]) * 63.55 + (a[1] + b[1]) * 155.85
            # Viewport borders are not fractures between pieces.
            outer = ((a[0] == b[0] and a[0] in (0.0, 1.0)) or
                     (a[1] == b[1] and a[1] in (0.0, 1.0)))
            for vertex in triangle:
                x, y = (vertex[0] - a[0]) * aspect, vertex[1] - a[1]
                distance = abs(dx * y - dy * x) / length
                along = (x * dx + y * dy) / (length * length)
                result.extend((*vertex, 10.0 if outer else distance, along, phase))
        else:
            for vertex in triangle:
                result.extend((*vertex, 10.0, 0.0, 0.0))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class CrumbleGeometry:
    chunks: bytes
    debris: bytes  # empty when the debris amount is zero


def crumble_geometry_key(parameters: Mapping[str, object], aspect: float) -> tuple:
    seed, pieces, complexity, _weight, _depth, _thickness, debris = crumble_parameters(parameters)
    return ("crumble", seed, pieces, complexity, float(aspect), debris)


def build_crumble_geometry(key: tuple) -> CrumbleGeometry:
    _name, seed, pieces, complexity, aspect, debris = key
    shards = crumble_cells(seed, pieces, aspect, complexity)
    chunks = _pack(crumble_vertices(shards, aspect))
    if debris <= 0.0:
        return CrumbleGeometry(chunks, b"")
    return CrumbleGeometry(chunks, _pack(debris_instances(seed, shards, debris)))


# --- Shared prepared-geometry store -----------------------------------------


class PreparedGeometryCache:
    """Small LRU of immutable CPU geometry keyed by its complete pure inputs.

    Keys hold every input the builder reads, so an entry can never be stale; the
    bound only limits memory. Both displays of a batch may read one entry.
    """

    def __init__(self, capacity: int = 6) -> None:
        self._capacity = max(1, int(capacity))
        self._lock = threading.Lock()
        self._entries: OrderedDict[Hashable, object] = OrderedDict()

    def get(self, key: Hashable) -> object | None:
        with self._lock:
            value = self._entries.get(key)
            if value is not None:
                self._entries.move_to_end(key)
            return value

    def put(self, key: Hashable, value: object) -> None:
        with self._lock:
            self._entries[key] = value
            self._entries.move_to_end(key)
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)

    def get_or_build(self, key: Hashable, build: Callable[[Hashable], _T]) -> _T:
        """Render-thread entry: prepared bytes, else build synchronously (never waits)."""

        value = self.get(key)
        if value is None:
            value = build(key)
            self.put(key, value)
        return value  # type: ignore[return-value]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


PREPARED_GEOMETRY = PreparedGeometryCache()

_BUILDERS: dict[str, tuple[Callable[[Mapping[str, object], float, object], tuple], Callable[[tuple], object]]] = {
    "glass_shatter": (glass_geometry_key, build_glass_geometry),
    "crumble": (lambda parameters, aspect, _direction: crumble_geometry_key(parameters, aspect),
                build_crumble_geometry),
}


def has_run_geometry(transition_id: str) -> bool:
    return transition_id in _BUILDERS


def prepare_run_geometry(
    transition_id: str,
    parameters: Mapping[str, object],
    aspects: Iterable[float],
    direction: object = None,
) -> None:
    """Build and store geometry for each distinct display aspect (COMPUTE side).

    Best effort by design: a failure here only means the renderer builds the
    same bytes itself (and reports any real parameter error there).
    """

    builders = _BUILDERS.get(transition_id)
    if builders is None:
        return
    make_key, build = builders
    for aspect in dict.fromkeys(float(value) for value in aspects):
        try:
            key = make_key(parameters, aspect, direction)
            if PREPARED_GEOMETRY.get(key) is None:
                PREPARED_GEOMETRY.put(key, build(key))
        except Exception:
            logger.debug(
                "[TRANSITION] %s geometry preparation skipped for aspect %.6f",
                transition_id,
                aspect,
                exc_info=True,
            )


__all__ = [
    "CRUMBLE_CHUNK_ATTRIBUTES",
    "CRUMBLE_DEBRIS_STRIDE",
    "CrumbleGeometry",
    "GLASS_ATTRIBUTES",
    "GlassGeometry",
    "PREPARED_GEOMETRY",
    "PreparedGeometryCache",
    "build_crumble_geometry",
    "build_glass_geometry",
    "crumble_geometry_key",
    "crumble_parameters",
    "crumble_vertices",
    "debris_instances",
    "glass_geometry_key",
    "has_run_geometry",
    "prepare_run_geometry",
]
