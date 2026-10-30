"""Extruded Bubble's free-drift step log: what the GPU drift solver integrates, published by the logical tick.

The logical tick no longer integrates the free chains, marine snow and specks. Each tick it records one step
(``STEP_FIELDS``: dt, motion phase, travel, stream speed, each family's signed drift amount, the cloud counts and
the field basis) and keeps the last ``STEP_HISTORY`` of them. Each active family carries an immutable
``DriftFamily`` descriptor: its stable seeded geometry, which changes only when its geometry is edited (a new
``revision`` that continues from the previous one) or grows. The renderer applies every step it has not applied,
in order, to persistent per-mote state (``rendering/quick/visualizer/implementations/extruded_bubble_drift_solver``);
nothing is read back. ``MaterialDriftReference`` integrates the same log on the CPU with the original
``MaterialPaths`` / ``ProceduralOffsets`` and packs the payloads the renderer reads: the reference the GPU solver
is checked against.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import itertools
import math

import numpy as np

from widgets.spotify_visualizer.extruded_bubble_drift import DRIFT_DIRECTIONS
from widgets.spotify_visualizer.extruded_bubble_material_paths import PATH_NODES

FAMILIES = ("chains", "snow", "specks")
STEP_FIELDS = ("serial", "dt", "phase", "travel", "speed", "kind",
               "amount_chains", "amount_snow", "amount_specks", "count_snow", "count_specks", "chain_rows",
               "direction_x", "direction_y", "direction_z", "across_x", "across_y", "across_z",
               "depth_x", "depth_y", "depth_z", "origin_x", "origin_y", "origin_z")
STEP_FLOATS = len(STEP_FIELDS)
STEP_INDEX = {name: index for index, name in enumerate(STEP_FIELDS)}
STEP_HISTORY = 128  # ~1.4 s of logical ticks: a render gap longer than this restarts drift (a lifecycle event)
# Geometry rows: chains as 12 float64 (start, span, end, carry, phase, 0, 0, 0) so the knot shift crosses its
# integer steps on exactly the CPU's ticks; clouds as two float32 vec4s (start, span), (seed, phase, 0, 0).
CHAIN_GEOMETRY_DOUBLES = 12
CHAIN_GEOMETRY_BYTES, CLOUD_GEOMETRY_BYTES = 8 * CHAIN_GEOMETRY_DOUBLES, 32
_REVISIONS = itertools.count(1)


@dataclass(frozen=True, eq=False)
class DriftFamily:
    """One active drift family's geometry. ``revision`` is globally unique; ``rebase_from`` names the revision
    this one continues from after a geometry edit (0: fresh history). ``first_serial`` is the step that began
    this revision. ``capacity`` is the number of geometry rows; ``source`` keeps the float64 arrays for the CPU
    reference (never mutated)."""

    family: str
    revision: int
    rebase_from: int
    first_serial: int
    capacity: int
    geometry: bytes
    carry: float = 0.0
    source: tuple = field(default=(), repr=False)


def pack_geometry(family: str, geometry) -> bytes:
    if family == "chains":
        base, spans, carry, phases = geometry
        rows = np.zeros((len(spans), CHAIN_GEOMETRY_DOUBLES), dtype=np.float64)
        rows[:, 0:3] = base[:, 0]; rows[:, 3] = spans
        rows[:, 4:7] = base[:, -1]; rows[:, 7] = carry
        rows[:, 8] = phases
    else:
        start, spans, seed, _carry, phases = geometry
        rows = np.zeros((len(spans), 2, 4), dtype=np.float32)
        rows[:, 0, :3] = start; rows[:, 0, 3] = spans
        rows[:, 1, 0] = seed; rows[:, 1, 1] = phases
    return rows.tobytes()


@dataclass
class _Live:
    descriptor: DriftFamily
    key: tuple
    lifetime: float           # travel after which every knot/mote has recycled at least once
    zero_from: float | None = None
    edited: bool = False


class DriftLog:
    """The simulation's free-drift log: descriptors and the step history (one owner per simulation)."""

    def __init__(self) -> None:
        self.serial = 0
        self._live: dict[str, _Live] = {}
        self._steps: deque[bytes] = deque(maxlen=STEP_HISTORY)
        self.families: tuple[DriftFamily, ...] = ()
        self.steps: bytes = b""

    def family(self, name: str) -> DriftFamily | None:
        live = self._live.get(name)
        return live.descriptor if live is not None else None

    def retire(self, name: str) -> None:
        self._live.pop(name, None)

    def admit(self, name: str, key: tuple, capacity: int, make_geometry, lifetime_of) -> None:
        """Make ``name`` live for this tick's step with geometry for at least ``capacity`` rows.

        ``key`` identifies the geometry apart from its row count; a different key is an edit (a new revision
        continuing from the old one), a larger capacity only extends the rows (same stable seeded prefix)."""
        live = self._live.get(name)
        serial = self.serial + 1
        if live is not None and live.key == key and live.descriptor.capacity == capacity:
            return
        geometry = make_geometry(capacity)
        carry = float(geometry[3]) if name != "chains" else 0.0
        packed = pack_geometry(name, geometry)
        if live is not None and live.key == key:
            # Only the row count changed: keep the revision (rows are a stable prefix) and its history.
            old = live.descriptor
            live.descriptor = DriftFamily(name, old.revision, old.rebase_from, old.first_serial, capacity, packed,
                                          carry, geometry)
            live.lifetime = lifetime_of(geometry)
            return
        descriptor = DriftFamily(name, next(_REVISIONS), live.descriptor.revision if live is not None else 0,
                                 serial, capacity, packed, carry, geometry)
        # An edit continues the old history with a phase offset, which never decays: such a family never retires.
        self._live[name] = _Live(descriptor, key, lifetime_of(geometry), None, live is not None)

    def record(self, *, dt, phase, travel, speed, kind, amounts, counts, chain_rows, direction, across, depth_axis,
               origin) -> None:
        """Close this tick: publish one step and the live descriptors."""
        self.serial += 1
        if not self._live:
            self.families, self.steps = (), b"".join(self._steps) if self._steps else b""
            return
        row = np.array((self.serial, dt, phase, travel, speed, float(DRIFT_DIRECTIONS.index(kind)),
                        amounts.get("chains", 0.0), amounts.get("snow", 0.0), amounts.get("specks", 0.0),
                        counts.get("snow", 0), counts.get("specks", 0), chain_rows,
                        *direction, *across, *depth_axis, *origin), dtype=np.float64)
        self._steps.append(row.tobytes())
        self.families = tuple(self._live[name].descriptor for name in FAMILIES if name in self._live)
        self.steps = b"".join(self._steps)

    def zero_gain(self, name: str, travel: float, zero: bool) -> bool:
        """Track a family whose signed drift is zero; True once it holds no displacement and can retire.

        Every knot/mote has recycled (and restarted from zero) once the stream has carried it a full lifetime
        since the drift reached zero; an edited family keeps a phase offset and never retires this way."""
        live = self._live[name]
        if not zero:
            live.zero_from = None
            return False
        if live.zero_from is None:
            live.zero_from = travel
        return not live.edited and travel - live.zero_from >= live.lifetime


def chain_lifetime(geometry) -> float:
    _base, spans, carry, _phases = geometry
    # A knot retires after its progress passes the outlet ghost: one span plus two knot spacings.
    return float(np.max(spans / carry)) * (1.0 + 2.0 / (PATH_NODES - 3)) if len(spans) else 0.0


def cloud_lifetime(geometry) -> float:
    _start, spans, _seed, carry, _phases = geometry
    return float(np.max(spans)) / float(carry) if len(spans) else 0.0


def unpack_steps(steps: bytes) -> np.ndarray:
    if len(steps) % (8 * STEP_FLOATS):
        raise ValueError("Extruded Bubble drift steps must be whole float64 records")
    return np.frombuffer(steps, dtype=np.float64).reshape(-1, STEP_FLOATS)


class MaterialDriftReference:
    """CPU reference for the GPU drift solver: integrates the published log with the original
    ``MaterialPaths`` / ``ProceduralOffsets`` and packs the payloads (chain rows, snow, specks) the renderer
    reads. Consumes snapshots in order, applying each step once, exactly as the solver does."""

    def __init__(self) -> None:
        self.serial = 0
        self._state: dict[str, tuple] = {}   # name -> (revision, integrator, its descriptor)
        self.payload: dict[str, bytes] = {}

    def apply(self, families, steps: bytes) -> dict[str, bytes]:
        from widgets.spotify_visualizer.extruded_bubble_material_paths import MaterialPaths, ProceduralOffsets
        rows = unpack_steps(steps)
        live = {f.family: f for f in families}
        for name in tuple(self._state):
            if name not in live:
                del self._state[name]
                self.payload.pop(name, None)
        for record in rows:
            serial = int(record[STEP_INDEX["serial"]])
            if serial <= self.serial:
                continue
            self.serial = serial
            for name, family in live.items():
                revision, paths, applied = self._state.get(name, (0, None, None))
                if serial < family.first_serial:
                    # A step of the revision this one continues from, not yet applied: on the old geometry.
                    if paths is not None and revision == family.rebase_from:
                        self.payload[name] = _reference_step(name, applied, paths, record)
                    continue
                if paths is None or (revision != family.revision and family.rebase_from != revision):
                    paths = MaterialPaths() if name == "chains" else ProceduralOffsets()
                self._state[name] = (family.revision, paths, family)
                self.payload[name] = _reference_step(name, family, paths, record)
        return {name: self.payload[name] for name in FAMILIES if name in self.payload and name in live}


def _field(record) -> dict:
    r = STEP_INDEX
    return dict(kind=DRIFT_DIRECTIONS[int(record[r["kind"]])], phase=float(record[r["phase"]]),
                direction=tuple(float(v) for v in record[r["direction_x"]:r["direction_z"] + 1]),
                across=tuple(float(v) for v in record[r["across_x"]:r["across_z"] + 1]),
                depth_axis=tuple(float(v) for v in record[r["depth_x"]:r["depth_z"] + 1]),
                origin=tuple(float(v) for v in record[r["origin_x"]:r["origin_z"] + 1]))


def _reference_step(name, family, paths, record) -> bytes:
    r = STEP_INDEX
    dt, travel, speed = float(record[r["dt"]]), float(record[r["travel"]]), float(record[r["speed"]])
    amount = float(record[r[f"amount_{name}"]])
    if name == "chains":
        rows = int(record[r["chain_rows"]])
        base, spans, carry, phases = family.source
        base, spans, carry, phases = base[:rows], spans[:rows], carry[:rows], phases[:rows]
        displacement = paths.advance(base, spans, travel * carry, speed * carry, phases, dt, amount=amount,
                                     **_field(record))
        if displacement is None:
            return b""
        packed = np.zeros((*displacement.shape[:2], 4), dtype=np.float32)
        packed[..., :3] = displacement
        packed[:, 0, 3] = paths.shift; packed[:, 1, 3] = paths.phase_offset
        return packed.tobytes()
    count = int(record[r[f"count_{name}"]])
    start, spans, seed, carry, phases = family.source
    geometry = (start[:count], spans[:count], seed[:count], carry, phases[:count])
    key = (family.revision, count)
    return paths.advance(geometry, key, travel, speed, dt, amount=amount, **_field(record)).tobytes()


__all__ = ["CHAIN_GEOMETRY_BYTES", "CHAIN_GEOMETRY_DOUBLES", "CLOUD_GEOMETRY_BYTES", "DriftFamily", "DriftLog", "FAMILIES",
           "MaterialDriftReference", "STEP_FIELDS", "STEP_FLOATS", "STEP_HISTORY", "STEP_INDEX", "chain_lifetime",
           "cloud_lifetime", "pack_geometry", "unpack_steps"]
