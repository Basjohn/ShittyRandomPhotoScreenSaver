"""Extruded Bubble's drift portion of the native record.

Each projector belongs to one activation of one stream. It projects the simulation's published drift without
owning geometry, clocking the simulation, or copying geometry to the record. The arena writer will publish
the descriptors' bytes under the keys below before writing a frame that names them.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.visualizer_engine.native_schema import NativeSchemaError
from widgets.spotify_visualizer.extruded_bubble_drift_log import (
    FAMILIES, KNOT_DECISION_BYTES, STEP_FLOATS, STEP_INDEX, DriftFamily, knot_starts, unpack_steps,
)

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

# These entries are composed into the runtime schema when the complete record and route are staged.
DRIFT_RECORD_ENTRIES = (
    ("drift_first_step", "u32", 1),
    ("drift_last_step", "u32", 1),
    *((f"{family}_{member}", "u32", count) for family in FAMILIES for member, count in (
        ("geometry_key", len(_NULL_GEOMETRY_KEY)), ("epoch", 1), ("rebase_from_epoch", 1), ("first_step", 1),
    )),
)


def _step_serial(value: float | int) -> int:
    serial = int(value)
    if serial != value or not 0 < serial <= _U32_MAX:
        raise NativeSchemaError(f"Extruded Bubble's drift step {value} is outside the native record's u32 serials")
    return serial


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
        self._last_serial = 0

    def _key(self, family_id: int, descriptor: DriftFamily) -> tuple[int, ...]:
        try:
            return _GEOMETRY_WORDS.unpack(_GEOMETRY_KEY.pack(*self._identity, family_id, descriptor.revision,
                                                           descriptor.capacity))
        except struct.error as exc:
            raise NativeSchemaError(f"Extruded Bubble's {descriptor.family} descriptor does not fit a D3 key") from exc

    def project(self, frame: ExtrudedBubbleFrame) -> tuple[dict[str, int | tuple[int, ...]], DriftSteps]:
        """The record's metadata and the authored steps. Geometry bytes remain in the input descriptors.

        Rebase provenance persists for the entire new epoch. A consumer rebases only if its current epoch
        is that predecessor. Same-revision capacity changes keep the epoch even as the arena key changes.
        """
        descriptors = {family.family: family for family in frame.drift_families}
        if len(descriptors) != len(frame.drift_families) or not descriptors.keys() <= _FAMILY_NAMES:
            raise NativeSchemaError("Extruded Bubble's drift frame has an unknown or repeated family")
        window = DriftSteps()
        if descriptors:
            records = unpack_steps(frame.drift_steps)
            first, last = _step_serial(records[0, _SERIAL]), _step_serial(records[-1, _SERIAL])
            if last < self._last_serial:
                raise NativeSchemaError("Extruded Bubble's drift serial went backwards within an activation")
            window = DriftSteps(frame.drift_steps, frame.drift_knots, first, last)

        fields: dict[str, int | tuple[int, ...]] = {
            "drift_first_step": window.first_serial, "drift_last_step": window.last_serial,
        }
        epochs, last_epoch = {}, self._last_epoch.copy()
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
            fields[f"{name}_geometry_key"] = self._key(family_id, descriptor)
            fields[f"{name}_epoch"] = epoch.epoch
            fields[f"{name}_rebase_from_epoch"] = epoch.rebase_from_epoch
            fields[f"{name}_first_step"] = birth
            epochs[name] = epoch

        self._epochs, self._last_epoch = epochs, last_epoch
        self._last_serial = max(self._last_serial, window.last_serial)
        return fields, window
