"""Extruded Bubble's drift portion of the native record.

Each projector belongs to one activation of one stream. It projects the simulation's published drift without
owning geometry, clocking the simulation, or copying geometry to the record. The worker's arena writer
(``geometry_arena.GeometryArenaWriter``) publishes the descriptors' bytes under the keys below before the slot naming
them; the projection names a key only once the stream's arena holds it (``project``'s ``held``), else the family keeps
its last named key and epoch.

The stream's arena is the main process's (``open_stream_arena`` at the session's configure, ``close_stream_arena`` at
its close), registered under the session's label namespace, which every drift revision of the session carries in its
high word (``engine_worker``'s revision counter). ``DriftStream`` is the native route's side: per record it finds the
arena, projects the drift fields and packs the compute streams (``pack_drift_stream``), and tells a bound native item
the arena's name once (``bound``).
"""
from __future__ import annotations

import logging
import struct
import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from core.visualizer_engine.geometry_arena import GeometryArenaOwner, key_of_words
from core.visualizer_engine.native_schema import NativeSchemaError
from widgets.spotify_visualizer.extruded_bubble_drift_log import (
    FAMILIES, KNOT_DECISION_BYTES, STEP_FLOATS, STEP_HISTORY, STEP_INDEX, DriftFamily, knot_starts, unpack_steps,
)

from widgets.spotify_visualizer.extruded_bubble_material_paths import CHAIN_PATHS

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from widgets.spotify_visualizer.render_state import ExtrudedBubbleFrame

# D3 (geometry_arena.h): namespace (u64), engine, activation, family, revision (u64), capacity.
_GEOMETRY_KEY = struct.Struct("<QIIIQI")
_GEOMETRY_WORDS = struct.Struct("<8I")
_NULL_GEOMETRY_KEY = (0,) * (_GEOMETRY_WORDS.size // 4)
_U32_MAX = (1 << 32) - 1
_STEP_BYTES = STEP_FLOATS * 8
_SERIAL = STEP_INDEX["serial"]
_FAMILY_NAMES = frozenset(FAMILIES)
# The drift stream (``pack_drift_stream``) at its largest: a full window, every drawable chain's knots each step, and
# the steps' serials (chain_rows is drawable_chains: CHAIN_PATHS at most; 384,512 bytes).
DRIFT_STREAM_FLOATS = STEP_HISTORY * (STEP_FLOATS + CHAIN_PATHS * KNOT_DECISION_BYTES // 4 + 1)

# These entries are composed into the runtime schema when the complete record and route are staged.
DRIFT_RECORD_ENTRIES = (
    ("drift_first_step", "u32", 1),
    ("drift_last_step", "u32", 1),
    ("drift_step_count", "u32", 1),
    ("drift_stream", "f32", DRIFT_STREAM_FLOATS),
    ("drift_stream_used", "u32", 1),
    ("drift_serial_base", "u32", 1),
    *((f"{family}_{member}", "u32", count) for family in FAMILIES for member, count in (
        ("geometry_key", len(_NULL_GEOMETRY_KEY)), ("epoch", 1), ("rebase_from_epoch", 1), ("first_step", 1),
    )),
)


def _step_serial(value: float | int) -> int:
    if not 0 < value <= _U32_MAX or int(value) != value:
        raise NativeSchemaError(f"Extruded Bubble's drift step {value} is outside the native record's u32 serials")
    return int(value)


def _step_bounds(steps: bytes) -> tuple[int, int]:
    try:
        serials = unpack_steps(steps)[:, _SERIAL]
    except ValueError as exc:
        raise NativeSchemaError(str(exc)) from exc
    if not len(serials):
        raise NativeSchemaError("Extruded Bubble's live drift families need at least one drift step")
    valid = (serials >= 1) & (serials <= _U32_MAX) & (serials == np.trunc(serials))
    if not valid.all():
        raise NativeSchemaError("Extruded Bubble's drift step serials must be positive u32 integers")
    if not (serials[1:] > serials[:-1]).all():
        raise NativeSchemaError("Extruded Bubble's drift step serials must be strictly increasing")
    return int(serials[0]), int(serials[-1])


@dataclass(frozen=True, slots=True)
class DriftSteps:
    """The author's window and knot decisions, still in the logical owner's precision.

    A consumer with an applied-step watermark uses ``after`` to pick its unapplied steps. A publication or
    mailbox acknowledgement alone does not indicate what the solver dispatched.
    """

    steps: bytes = b""
    knots: bytes = b""
    first_serial: int = 0
    last_serial: int = 0

    def after(self, last_applied: int) -> tuple[DriftSteps, bool]:
        """The unapplied suffix and whether its first step follows a gap (a fresh solve).

        This plans work for one accepted record. A replay that shows a late window must still submit every
        preceding input from cold start to keep the integrated history.
        """
        if not self.steps or last_applied >= self.last_serial:
            return DriftSteps(), False
        if last_applied < self.first_serial:
            return self, self.first_serial != last_applied + 1
        records = unpack_steps(self.steps)
        start = int(records[:, _SERIAL].searchsorted(last_applied, side="right"))
        first = _step_serial(records[start, _SERIAL])
        knot_offset = int(knot_starts(records[:start])[-1]) * KNOT_DECISION_BYTES
        suffix = DriftSteps(self.steps[start * _STEP_BYTES:], self.knots[knot_offset:], first, self.last_serial)
        return suffix, first != last_applied + 1


@dataclass(frozen=True, slots=True)
class _FamilyEpoch:
    revision: int
    epoch: int
    rebase_from_epoch: int


class DriftRecordProjector:
    """Project canonical drift families into a stream's geometry keys and wrapping-free u32 epochs."""

    def __init__(self, namespace: int, engine_generation: int, activation: int) -> None:
        if not 0 < namespace < 1 << 64 or not (0 <= engine_generation <= _U32_MAX and 0 <= activation <= _U32_MAX):
            raise NativeSchemaError("Extruded Bubble's drift stream identity does not fit a D3 geometry key")
        self._identity = (namespace, engine_generation, activation)
        self._epochs: dict[str, _FamilyEpoch] = {}
        self._last_epoch: dict[str, int] = {}
        self._named: dict[str, tuple[tuple[int, ...], _FamilyEpoch, int]] = {}   # family -> its last named lineage
        self._last_serial = 0

    def _key(self, family_id: int, descriptor: DriftFamily) -> tuple[int, ...]:
        try:
            return _GEOMETRY_WORDS.unpack(_GEOMETRY_KEY.pack(*self._identity, family_id, descriptor.revision,
                                                           descriptor.capacity))
        except struct.error as exc:
            raise NativeSchemaError(f"Extruded Bubble's {descriptor.family} descriptor does not fit a D3 key") from exc

    def project(self, frame: ExtrudedBubbleFrame, held: Callable[[tuple], bool] | None = None,
                ) -> tuple[dict[str, int | tuple[int, ...]], DriftSteps]:
        """The record's metadata and the authored steps. Geometry bytes remain in the input descriptors.

        Rebase provenance persists for the entire new epoch. A consumer rebases only if its current epoch
        is that predecessor. Same-revision capacity changes keep the epoch even as the arena key changes.

        ``held(key)``: whether the stream's arena holds a key whole (D3: the worker writes a bank before the slot naming
        it, and defers a key while both of its family's banks are live). A key not held is never named: the family
        keeps the key, epoch and first step it was last projected with (its lineage at the last published revision),
        or is absent if it has none yet. None names every key (the metadata fixture's form).
        """
        descriptors = {family.family: family for family in frame.drift_families}
        if len(descriptors) != len(frame.drift_families) or not descriptors.keys() <= _FAMILY_NAMES:
            raise NativeSchemaError("Extruded Bubble's drift frame has an unknown or repeated family")
        window = DriftSteps()
        if descriptors:
            first, last = _step_bounds(frame.drift_steps)
            if last < self._last_serial:
                raise NativeSchemaError("Extruded Bubble's drift serial went backwards within an activation")
            window = DriftSteps(frame.drift_steps, frame.drift_knots, first, last)

        fields: dict[str, int | tuple[int, ...] | bytes] = {
            "drift_first_step": window.first_serial, "drift_last_step": window.last_serial,
            "drift_step_count": drift_step_serials(window)[0],
        }
        stream = pack_drift_stream(window)
        if len(stream) > DRIFT_STREAM_FLOATS * 4:
            raise NativeSchemaError(f"Extruded Bubble's drift stream is {len(stream)} bytes, past the record's "
                                    f"{DRIFT_STREAM_FLOATS * 4}")
        fields["drift_stream"], fields["drift_stream_used"] = stream, len(stream) // 4
        fields["drift_serial_base"] = len(stream) // 4 - fields["drift_step_count"]
        epochs, last_epoch, named = {}, self._last_epoch.copy(), {}
        for family_id, name in enumerate(FAMILIES):
            descriptor = descriptors.get(name)
            if descriptor is None:
                fields[f"{name}_geometry_key"] = _NULL_GEOMETRY_KEY
                fields[f"{name}_epoch"] = fields[f"{name}_rebase_from_epoch"] = fields[f"{name}_first_step"] = 0
                continue
            if descriptor.source or descriptor.revision <= 0 or descriptor.capacity <= 0:
                raise NativeSchemaError(f"Extruded Bubble's {name} needs a live, source-free drift descriptor")
            birth = _step_serial(descriptor.first_serial)
            if birth > window.last_serial:
                raise NativeSchemaError(f"Extruded Bubble's {name} was published before its first drift step")
            key = self._key(family_id, descriptor)
            if held is not None and not held(key_of_words(key)):
                kept = self._named.get(name)
                if kept is None:
                    fields[f"{name}_geometry_key"] = _NULL_GEOMETRY_KEY
                    fields[f"{name}_epoch"] = fields[f"{name}_rebase_from_epoch"] = fields[f"{name}_first_step"] = 0
                    continue
                fields[f"{name}_geometry_key"], kept_epoch, fields[f"{name}_first_step"] = kept
                fields[f"{name}_epoch"] = kept_epoch.epoch
                fields[f"{name}_rebase_from_epoch"] = kept_epoch.rebase_from_epoch
                epochs[name], named[name] = kept_epoch, kept
                continue
            previous = self._epochs.get(name)
            if previous is not None and previous.revision == descriptor.revision:
                epoch = previous
            else:
                number = last_epoch.get(name, 0) + 1
                if number > _U32_MAX:
                    raise NativeSchemaError(f"Extruded Bubble's {name} epoch is outside the native record's u32")
                predecessor = previous.epoch if previous and previous.revision == descriptor.rebase_from else 0
                epoch = _FamilyEpoch(descriptor.revision, number, predecessor)
                last_epoch[name] = number
            fields[f"{name}_geometry_key"] = key
            fields[f"{name}_epoch"] = epoch.epoch
            fields[f"{name}_rebase_from_epoch"] = epoch.rebase_from_epoch
            fields[f"{name}_first_step"] = birth
            epochs[name], named[name] = epoch, (key, epoch, birth)

        self._epochs, self._last_epoch, self._named = epochs, last_epoch, named
        self._last_serial = max(self._last_serial, window.last_serial)
        return fields, window


# ------------------------------------------------------------------------------- the compute streams (N5.6)

_KNOT_START = STEP_INDEX["serial"]


def drift_step_serials(window: DriftSteps) -> tuple[int, tuple[int, ...]]:
    """(the window's step count, its serials as u32, zero past the count): the native solver's cursor reads them (the
    stream's last words, ``pack_drift_stream``), since a window's serials need not be consecutive (a tick with no live
    family records no step)."""
    if not window.steps:
        return 0, (0,) * STEP_HISTORY
    serials = unpack_steps(window.steps)[:, _SERIAL]
    if len(serials) > STEP_HISTORY:
        raise NativeSchemaError(f"Extruded Bubble's drift window holds {len(serials)} steps, past {STEP_HISTORY}")
    return len(serials), tuple(int(s) for s in serials) + (0,) * (STEP_HISTORY - len(serials))


def pack_drift_stream(window: DriftSteps) -> bytes:
    """The whole retained window as the drift solver's one storage stream: each step as float32 with its serial slot
    carrying where its knot decisions begin (relative to the window's first step), then those decisions, as the Python
    solver uploads a suffix (``extruded_bubble_drift_solver._upload``), and last the steps' serials as whole u32 words
    (``drift_step_serials``: a float's 24 bits cannot hold them; the core fills no uint array of a uniform block, so
    the cursor reads them here, from ``drift_serial_base``: the used words less the step count). The core's cursor
    picks the unapplied suffix (``u_srpss_compute``: the trigger ``drift_last_step`` and its value at the entry's last
    dispatch): a repeated record dispatches nothing, a short gap applies the steps after the last applied one, and a
    gap past the window restarts from its first step, as the Python solver restarts. Empty when no family is live."""
    if not window.steps:
        return b""
    records = unpack_steps(window.steps)
    starts = knot_starts(records)
    gpu = records.astype(np.float32)
    gpu[:, _KNOT_START] = starts[:-1]
    knots = window.knots[:int(starts[-1]) * KNOT_DECISION_BYTES]
    if len(knots) != int(starts[-1]) * KNOT_DECISION_BYTES:
        raise NativeSchemaError("Extruded Bubble's drift knots are shorter than their steps' chain rows")
    count, serials = drift_step_serials(window)
    return gpu.tobytes() + knots + np.asarray(serials[:count], dtype="<u4").tobytes()


def drift_stream_bytes(chain_rows: int) -> int:
    """The stream's bytes at a full window of ``chain_rows`` drawable chains (each step and its knot decisions)."""
    return STEP_HISTORY * (STEP_FLOATS * 4 + int(chain_rows) * KNOT_DECISION_BYTES)


# --------------------------------------------------------------------- the stream's arena (main process, D3)

_ARENAS_LOCK = threading.Lock()
_ARENAS: dict[int, GeometryArenaOwner] = {}     # label namespace -> the session's arena


def open_stream_arena(label_namespace: int, bank_bytes: int) -> GeometryArenaOwner:
    """The session's arena (``engine_worker_link.configure``), registered under its label namespace."""
    owner = GeometryArenaOwner(families=len(FAMILIES), bank_bytes=bank_bytes)
    with _ARENAS_LOCK:
        if int(label_namespace) in _ARENAS:
            owner.close()
            raise NativeSchemaError(f"label namespace {label_namespace} already owns a geometry arena")
        _ARENAS[int(label_namespace)] = owner
    return owner


def close_stream_arena(owner: GeometryArenaOwner) -> None:
    """The session closed: its arena unregistered, closed and unlinked."""
    with _ARENAS_LOCK:
        for namespace, held in list(_ARENAS.items()):
            if held is owner:
                del _ARENAS[namespace]
    owner.close()


def stage_stream_arena(bank_bytes: int) -> GeometryArenaOwner:
    """A larger arena for a hidden activation (``engine_worker_link.set_mode``): unregistered until its commit."""
    return GeometryArenaOwner(families=len(FAMILIES), bank_bytes=bank_bytes)


def replace_stream_arena(label_namespace: int, owner: GeometryArenaOwner) -> None:
    """The activation committed: ``owner`` is the session's arena from now on, and the previous one is closed and
    unlinked (the core keeps its own view of it until the route names the new one; the worker already let it go)."""
    with _ARENAS_LOCK:
        previous = _ARENAS.get(int(label_namespace))
        _ARENAS[int(label_namespace)] = owner
    if previous is not None and previous is not owner:
        previous.close()


def stream_arena(label_namespace: int) -> GeometryArenaOwner | None:
    with _ARENAS_LOCK:
        return _ARENAS.get(int(label_namespace))


class DriftStream:
    """The native route's drift side (GUI thread): per record, the stream's arena by the frame's label namespace, a
    projector per (writer namespace, engine generation, activation), the drift fields and the packed stream. A bound
    item (``bound``) is told its stream's arena name when it first differs (the core opens it once per name)."""

    def __init__(self) -> None:
        self._projectors: dict[tuple[int, int, int], DriftRecordProjector] = {}
        self._items: list[tuple[weakref.ref, tuple[int, int, int], list[str]]] = []
        self._missing: set[int] = set()

    def bound(self, item: Any, expect: dict) -> None:
        """``item`` (a ``NativeMode``) draws the stream of ``expect``'s identity: its arena name is sent with the first
        record that has one, and the previous stream's is dropped now."""
        identity = tuple(int(expect.get(k, -1)) & _U32_MAX
                         for k in ("runtime_generation", "engine_generation", "activation_id"))
        self._items = [entry for entry in self._items if entry[0]() is not None and entry[0]() is not item]
        self._items.append((weakref.ref(item), identity, [""]))
        item.geometry_arena("")

    def project(self, logical: Any) -> dict:
        """The record's drift fields of ``logical`` (a logical publication), its packed stream among them."""
        frame = logical.mode_state
        families = frame.drift_families
        engine, activation = int(logical.engine_generation), int(logical.activation_id)
        arena = None
        if families:
            namespace = int(families[0].revision) >> 32
            arena = stream_arena(namespace)
            if arena is None and namespace not in self._missing:
                self._missing.add(namespace)
                logger.warning("[SPOTIFY_VIS][NATIVE] Extruded Bubble's stream (label namespace %d) has no geometry "
                               "arena: its drift families are not named", namespace)
        writer = arena.writer_namespace() if arena is not None else 0
        if writer == 0 or not (0 <= engine <= _U32_MAX and 0 <= activation <= _U32_MAX):
            # No writer attached, no arena, or an unactivated frame: every family absent; the steps still travel.
            fields, _window = DriftRecordProjector(1, 0, 0).project(frame, held=lambda _key: False)
            return fields
        identity = (writer, engine, activation)
        projector = self._projectors.get(identity)
        if projector is None:
            # One stream a route: a new writer (a replacement worker) or activation starts its own epochs.
            self._projectors = {identity: DriftRecordProjector(writer, engine, activation)}
            projector = self._projectors[identity]
        fields, _window = projector.project(frame, held=arena.holds)
        self._tell(logical, arena.name)
        return fields

    def _tell(self, logical: Any, name: str) -> None:
        identity = tuple(int(v) & _U32_MAX for v in (logical.runtime_generation, logical.engine_generation,
                                                     logical.activation_id))
        for ref, bound, told in self._items:
            item = ref()
            if item is not None and bound == identity and told[0] != name:
                item.geometry_arena(name)
                told[0] = name


# ------------------------------------------------------------------------------- the record (N5.6, version 1)
#
# A generic mode's runtime schema (D12, ``native_schema._RUNTIME_SCHEMA_MODULES``). The record carries what follows
# the frame: each program's state members (``rendering.native.extruded_bubble_values.STATE_MEMBERS``, named for their
# program, ``extruded_bubble_shaders.member_name``), the draws' instance streams (the shells, clusters, glint proxies
# and wakes as the renderer uploads them, f32 each with its used length in floats), the draws' counts and the near
# layer's gate, each drift family's capacity, output offset, carry and groups, and the drift portion above
# (``DriftStream``: the steps, their stream and each family's geometry key and lineage). The Settings and the card
# decide everything else (the route's settings: ``extruded_bubble_values.settings``).
#
# Version 1. A change to the fields or the layout is a new version.

from core.visualizer_engine.native_schema import (  # noqa: E402
    NativeLayout, NativeSchema, native_schema_id, validate_record_head)
from core.visualizer_engine.packet_abi import MODE_CODES  # noqa: E402

MODE_ID = "extruded_bubble"
VERSION = 1
SCHEMA_ID = native_schema_id(MODE_CODES[MODE_ID], VERSION)
#: The most an int member's u32 field holds (the core fills an int only under a range rule within int32).
INT_LIMIT = 2147483647


def _capacities() -> dict[str, int]:
    from core.constants.extruded_bubble_world import WAKE_STRIDE
    from rendering.gl_programs.extruded_bubble_scene import CLUSTER_FLOATS, PROXY_FLOATS, SHELL_FLOATS
    from widgets.spotify_visualizer.extruded_bubble_simulation import MAX_BUBBLES

    return {"shells": MAX_BUBBLES * SHELL_FLOATS, "clusters": MAX_BUBBLES // 2 * CLUSTER_FLOATS,
            "proxies": MAX_BUBBLES * PROXY_FLOATS, "wakes": MAX_BUBBLES * 2 * WAKE_STRIDE}


CAPACITIES = _capacities()
#: The instance streams, in the program's order (``extruded_bubble_program.INSTANCE_STREAMS`` and ``wakes``).
INSTANCE_STREAM_NAMES = ("shells", "clusters", "proxies", "wakes")


def field_kind(glsl_type: str, numbers: int) -> tuple[str, int]:
    """A member's record field (kind, count) by its GLSL type (``waveform_native_schema.field_kind``'s rule)."""
    if glsl_type == "vec4":
        return "f64x4", 1
    if glsl_type in ("int", "uint", "bool"):
        return "u32", numbers
    return "f64", numbers


def _member_entries() -> tuple[tuple[str, str, int], ...]:
    from rendering.native.extruded_bubble_values import block_members, state_fields

    numbers = {"float": 1, "int": 1, "uint": 1, "bool": 1, "vec2": 2, "vec3": 3, "vec4": 4}
    entries = []
    for name, program, member in state_fields():
        glsl_type = block_members(program)[member]
        entries.append((name, *field_kind(glsl_type, numbers[glsl_type])))
    return tuple(entries)


MEMBER_ENTRIES = _member_entries()
STREAM_ENTRIES: tuple[tuple[str, str, int], ...] = tuple(
    (name, "f32", CAPACITIES[name]) for name in INSTANCE_STREAM_NAMES)
COUNT_ENTRIES: tuple[tuple[str, str, int], ...] = (
    *((f"{name}_floats", "u32", 1) for name in INSTANCE_STREAM_NAMES),
    ("speck_count", "u32", 1), ("bead_instances", "u32", 1), ("trail_instances", "u32", 1), ("near_layer", "u32", 1),
    *((f"{family}_{member}", kind, 1) for family in FAMILIES
      for member, kind in (("capacity", "u32"), ("out_offset", "u32"), ("carry", "f64"), ("groups", "u32"))),
)
_ENTRIES = MEMBER_ENTRIES + STREAM_ENTRIES + COUNT_ENTRIES + DRIFT_RECORD_ENTRIES
LAYOUT = NativeLayout.build(_ENTRIES)
FIELD_NAMES = tuple(name for name, _kind, _count in _ENTRIES)


def _drift_limits() -> dict[str, int]:
    from core.constants.extruded_bubble_world import SNOW_FULL, SPECKS_FULL
    from rendering.native.extruded_bubble_program import buffer_bytes

    return {"chains": CHAIN_PATHS, "snow": SNOW_FULL, "specks": SPECKS_FULL,
            "out_rows": buffer_bytes()["drift_out"] // 16}


_LIMITS = _drift_limits()
FIELD_CHECKS: tuple[tuple[str, str, int], ...] = (
    *((name, "at_most", INT_LIMIT) for name, kind, _count in MEMBER_ENTRIES if kind == "u32"),
    *((f"{name}_floats", "at_most", CAPACITIES[name]) for name in INSTANCE_STREAM_NAMES),
    ("drift_stream_used", "at_most", DRIFT_STREAM_FLOATS),
    ("drift_serial_base", "at_most", DRIFT_STREAM_FLOATS),
    ("drift_step_count", "at_most", STEP_HISTORY),
    *((f"{family}_capacity", "at_most", _LIMITS[family]) for family in FAMILIES),
    *((f"{family}_out_offset", "at_most", _LIMITS["out_rows"]) for family in FAMILIES),
    # A chain's group is one path; a cloud's one of 256 rows (``extruded_bubble_values.state_values``).
    *((f"{family}_groups", "at_most", _LIMITS[family] if family == "chains" else -(-_LIMITS[family] // 256))
      for family in FAMILIES),
)


def _numbers(name: str, kind: str, count: int, value: Any) -> object:
    from core.visualizer_engine.waveform_native_schema import flat_numbers

    expected = 4 * count if kind == "f64x4" else count
    numbers = flat_numbers(value)
    if len(numbers) != expected or not all(np.isfinite(numbers)):
        raise NativeSchemaError(f"{name} is not {expected} finite numbers")
    if kind == "u32":
        if not all(0 <= v <= INT_LIMIT and v == int(v) for v in numbers):
            raise NativeSchemaError(f"{name} is not {expected} whole numbers from 0 to {INT_LIMIT}")
        numbers = tuple(int(v) for v in numbers)
    return numbers if expected > 1 else numbers[0]


#: The route's drift side (one per process: the route's records and the reference encoder name the same lineage).
DRIFT = DriftStream()


def project(frame: Any) -> dict[str, object]:
    """The record's field values (header words excluded) of an Extruded Bubble ``VisualizerLogicalFrame``."""
    if getattr(frame, "mode_id", None) != MODE_ID:
        raise NativeSchemaError(f"Extruded Bubble's native schema cannot carry a {getattr(frame, 'mode_id', None)!r} "
                                "frame")
    from rendering.native.extruded_bubble_shaders import member_name
    from rendering.native.extruded_bubble_values import state_values

    members, counts, streams = state_values(frame.mode_state)
    filled = {member_name(program, member): value
              for program, values in members.items() for member, value in values.items()}
    values: dict[str, object] = {}
    for name, kind, count in MEMBER_ENTRIES:
        if name not in filled:
            raise NativeSchemaError(f"Extruded Bubble's frame has no value for {name}")
        values[name] = _numbers(name, kind, count, filled[name])
    for name in INSTANCE_STREAM_NAMES:
        data = streams[name]
        size = LAYOUT.field(name).size
        if len(data) > size or len(data) % 4:
            raise NativeSchemaError(f"{name} holds {len(data)} bytes, past its {size} or not whole floats")
        values[name], values[f"{name}_floats"] = data, len(data) // 4
    values.update(counts)
    values.update(DRIFT.project(frame))
    return values


def encode(frame: Any) -> bytes:
    """The writer: one Extruded Bubble logical frame as the version-1 record."""
    return LAYOUT.pack(SCHEMA_ID, project(frame))


def decode(payload: bytes) -> dict[str, object]:
    """The reference reader: the record's fields by name (header words excluded); the streams as their bytes."""
    validate_record_head(payload, SCHEMA)
    unpacked = LAYOUT.unpack(payload)
    values = {name: unpacked[name] for name in FIELD_NAMES}
    for stream in (*INSTANCE_STREAM_NAMES, "drift_stream"):
        field_ = LAYOUT.field(stream)
        values[stream] = bytes(payload[field_.offset:field_.offset + field_.size])
    return values


class _ArenaSchema(NativeSchema):
    """The schema a bound native item is told its stream's arena through (``NativeMode.bind``'s ``bound``)."""

    __slots__ = ()

    def bound(self, item: Any, expect: dict) -> None:
        DRIFT.bound(item, expect)


SCHEMA = _ArenaSchema(mode_id=MODE_ID, version=VERSION, layout=LAYOUT, encode=encode, decode=decode,
                      fields=FIELD_NAMES, checks=FIELD_CHECKS)
SCHEMAS = (SCHEMA,)
