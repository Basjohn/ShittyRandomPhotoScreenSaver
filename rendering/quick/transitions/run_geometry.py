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

from .crumble_dynamics import (
    MOTION_ATTRIBUTES,
    bake_crumble_motion,
    release_motions,
    still_motion_table,
)
from .fracture_geometry import crumble_cells, fracture_cells, fracture_vertex_array
from .glass_dynamics import EXTRA_FLOATS, piece_extras, solve_glass_pieces

logger = get_logger(__name__)

# Prism data (as Crumble), then per-piece events: life2, then two stages of
# kick4, spin4, pivot2 (a split piece can crack once more).
GLASS_ATTRIBUTES = (2, 2, 1, 3, 1, 1, 1, 1, 2, 4, 4, 2, 4, 4, 2)
# Prism data, crack coordinates, then per-chunk motion (see crumble_dynamics).
CRUMBLE_CHUNK_ATTRIBUTES = (2, 2, 1, 3, 1, 1, 1, 1, 3) + MOTION_ATTRIBUTES
# Seam point, parent centre, parent variation and size, parent release (+pad).
CRUMBLE_DEBRIS_STRIDE = 8

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
    prisms = fracture_vertex_array(
        tuple(piece.shard for piece in pieces), aspect,
        pivots=[piece.pivot_center for piece in pieces],
        radii=[piece.radius for piece in pieces],
    ).astype(np.float32)
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


def debris_instances(seed: float, shards, amount: float, *, releases) -> tuple[float, ...]:
    """Seeded chips broken off the real crack borders; ``amount`` drives count and size.

    Each run picks a grain (fine, mixed or chunky) and a hot spot, so debris
    concentrates along the cracks nearest it instead of an even sprinkle.
    Metadata: seam point, parent centre, parent variation, size, and the
    parent's release time (``releases``, aligned with ``shards``) so a chip
    breaks off exactly when its chunk falls, including a knocked-loose one.
    """
    release_of = {id(shard): float(release) for shard, release in zip(shards, releases)}

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
        values.extend((x, y, parent_x, parent_y, shard.variation, size, release_of[id(shard)], 0.0))
    return tuple(values)


def crumble_vertices(shards, aspect: float) -> np.ndarray:
    """Add crack coordinates on the real polygon borders of the shared solids.

    Each front fan triangle has exactly one external polygon edge. Distance
    from that edge and distance along it interpolate across the face; fan
    diagonals receive no crack. Shared edges use the same orientation/phase.
    The prism itself is unchanged, including its closed sides and bevels.
    Returns float64 rows of 15: the 12 prism floats, then distance, along and
    phase (vectorised over every triangle).
    """
    solid = fracture_vertex_array(shards, aspect)
    triangles = solid.reshape(-1, 3, 12)
    crack = np.zeros((len(triangles), 3, 3))
    crack[:, :, 0] = 10.0
    front = triangles[:, 0, 9] == 0.0
    if front.any():
        tri = triangles[front]
        first, second = tri[:, 1, :2], tri[:, 2, :2]
        # Order the external edge's ends (lexicographically) so a shared edge
        # gets the same orientation and phase from both of its cells.
        swap = (second[:, 0] < first[:, 0]) | ((second[:, 0] == first[:, 0]) & (second[:, 1] < first[:, 1]))
        a = np.where(swap[:, None], second, first)
        b = np.where(swap[:, None], first, second)
        dx, dy = (b[:, 0] - a[:, 0]) * aspect, b[:, 1] - a[:, 1]
        length = np.hypot(dx, dy)
        phase = (a[:, 0] + b[:, 0]) * 63.55 + (a[:, 1] + b[:, 1]) * 155.85
        # Viewport borders are not fractures between pieces.
        outer = (((a[:, 0] == b[:, 0]) & ((a[:, 0] == 0.0) | (a[:, 0] == 1.0)))
                 | ((a[:, 1] == b[:, 1]) & ((a[:, 1] == 0.0) | (a[:, 1] == 1.0))))
        x = (tri[:, :, 0] - a[:, None, 0]) * aspect
        y = tri[:, :, 1] - a[:, None, 1]
        distance = np.abs(dx[:, None] * y - dy[:, None] * x) / length[:, None]
        along = (x * dx[:, None] + y * dy[:, None]) / (length * length)[:, None]
        rows = crack[front]
        rows[:, :, 0] = np.where(outer[:, None], 10.0, distance)
        rows[:, :, 1] = along
        rows[:, :, 2] = phase[:, None]
        crack[front] = rows
    return np.concatenate((triangles, crack), axis=2).reshape(-1, 15)


def crumble_chunk_bytes(shards, aspect: float, motions) -> bytes:
    """``crumble_vertices`` rows, each followed by its chunk's motion constants.

    ``motions`` is aligned with ``shards``; a vertex finds its chunk by the
    chunk centre it already carries, in one vectorised gather.
    """
    rows = crumble_vertices(shards, aspect)
    unique, inverse = np.unique(rows[:, 2:4], axis=0, return_inverse=True)
    chunk_of = {shard.center: index for index, shard in enumerate(shards)}
    lookup = np.asarray([chunk_of[(float(x), float(y))] for x, y in unique], dtype=np.int64)
    motion = np.asarray([m.floats(row) for row, m in enumerate(motions)], dtype=np.float64)
    return np.hstack((rows, motion[lookup[inverse.ravel()]])).astype(np.float32).tobytes()


@dataclass(frozen=True, slots=True)
class CrumbleGeometry:
    chunks: bytes
    debris: bytes  # empty when the debris amount is zero
    # Per chunk, MOTION_FRAMES RGBA32F keyframes (offset xyz, extra tumble):
    # the baked collision response; all zero without collisions.
    motion: bytes
    chunk_count: int


def crumble_geometry_key(parameters: Mapping[str, object], aspect: float) -> tuple:
    seed, pieces, complexity, weight, depth, thickness, debris = crumble_parameters(parameters)
    collisions = bool(parameters.get("collisions", False))
    # Depth and thickness shape the contact solve only; without collisions they
    # are shader uniforms and must not force a geometry rebuild.
    return ("crumble", seed, pieces, complexity, float(aspect), debris, weight, collisions,
            depth if collisions else 0.0, thickness if collisions else 0.0)


def build_crumble_geometry(key: tuple) -> CrumbleGeometry:
    _name, seed, pieces, complexity, aspect, debris, weight, collisions, depth, thickness = key
    shards = crumble_cells(seed, pieces, aspect, complexity)
    motions = release_motions(shards, seed, weight)
    if collisions:
        motions, table = bake_crumble_motion(shards, motions, aspect, depth, thickness, seed)
    else:
        table = still_motion_table(len(shards))
    chunks = crumble_chunk_bytes(shards, aspect, motions)
    table_bytes = table.astype(np.float32).tobytes()
    if debris <= 0.0:
        return CrumbleGeometry(chunks, b"", table_bytes, len(shards))
    releases = [chunk.begin for chunk in motions]
    chips = _pack(debris_instances(seed, shards, debris, releases=releases))
    return CrumbleGeometry(chunks, chips, table_bytes, len(shards))


# --- Shared prepared-geometry store -----------------------------------------


# How long a render thread waits for the same key's in-flight preparation
# before building it itself. Waiting releases the GIL, so the preparation runs
# faster than a duplicate build would; the bound only covers a stuck worker.
IN_FLIGHT_WAIT_S = 0.25


class PreparedGeometryCache:
    """Small LRU of immutable CPU geometry keyed by its complete pure inputs.

    Keys hold every input the builder reads, so an entry can never be stale; the
    bound only limits memory. Both displays of a batch may read one entry. A
    key being prepared is tracked so a render thread that needs it meanwhile
    waits for that build instead of duplicating it under GIL contention.
    """

    def __init__(self, capacity: int = 6) -> None:
        self._capacity = max(1, int(capacity))
        self._lock = threading.Lock()
        self._entries: OrderedDict[Hashable, object] = OrderedDict()
        self._in_flight: dict[Hashable, threading.Event] = {}

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

    def claim(self, key: Hashable) -> bool:
        """Mark ``key`` as being prepared; False when it is ready or already claimed."""

        with self._lock:
            if key in self._entries or key in self._in_flight:
                return False
            self._in_flight[key] = threading.Event()
            return True

    def settle(self, key: Hashable, value: object | None) -> None:
        """Finish a claim: store ``value`` (None = the preparation failed) and wake waiters."""

        if value is not None:
            self.put(key, value)
        with self._lock:
            event = self._in_flight.pop(key, None)
        if event is not None:
            event.set()

    def get_or_build(
        self,
        key: Hashable,
        build: Callable[[Hashable], _T],
        wait_s: float = IN_FLIGHT_WAIT_S,
    ) -> _T:
        """Render-thread entry: prepared bytes; else the in-flight build; else build here."""

        value = self.get(key)
        if value is None:
            with self._lock:
                event = self._in_flight.get(key)
            if event is not None and event.wait(wait_s):
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
        except Exception:
            logger.debug("[TRANSITION] %s geometry key rejected for aspect %.6f",
                         transition_id, aspect, exc_info=True)
            continue
        if not PREPARED_GEOMETRY.claim(key):
            continue
        value = None
        try:
            value = build(key)
        except Exception:
            logger.debug(
                "[TRANSITION] %s geometry preparation skipped for aspect %.6f",
                transition_id,
                aspect,
                exc_info=True,
            )
        finally:
            PREPARED_GEOMETRY.settle(key, value)


__all__ = [
    "CRUMBLE_CHUNK_ATTRIBUTES",
    "IN_FLIGHT_WAIT_S",
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
