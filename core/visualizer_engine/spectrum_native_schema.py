"""Spectrum's fixed-layout native frame schema (native core N2.3, transport rule 3).

The record carries exactly what Spectrum's renderer reads from a logical frame: the field list is
``widgets/spotify_visualizer/spectrum_frame_inputs.SPECTRUM_FRAME_INPUTS`` (the renderer reads its style and
parameters only through that declaration) less its Settings-only inputs (``record=False``: the native core takes them
by name with the other settings, N2.9), laid out by ``native_schema.NativeLayout`` (explicit offsets,
little-endian, 16-byte aligned arrays and colours, the record a multiple of 16 bytes). What the native renderer gets
from its host instead (the item matrix, viewport, device pixel ratio, content fade, visual scale) is not in it.

Values are stored as the renderer reads them, before its clamps and unit conversions, so a native renderer
reproduces the Python renderer's arithmetic exactly: every real number as f64 (all 64 bits: the bars and the
animation clock are multiplied and wrapped in double precision before they reach the shader), a colour as its four
raw channels (alpha 255 when the frame's colour has three), a boolean as a u32 0 or 1, a choice as its position in its
table (``ENUM_OUTSIDE`` for a value outside it, where the renderer's own fallback applies), a level sequence as its
first ``MAX_LEVELS`` values zero-padded with its kept length beside it.

``encode`` is the engine worker's writer; ``decode`` is the pure-Python reference reader, the oracle for the C++
reader (it validates by size and offsets, never by a tagged stream). ``project`` is the same field values taken from
a decoded ``VisualizerLogicalFrame``: ``decode(encode(frame)) == project(frame)`` bit for bit.

Version 1. A change to the declaration or the layout is a new version (the test pins the layout's fingerprint).
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from core.visualizer_engine.native_schema import (
    ENUM_OUTSIDE,
    NativeLayout,
    NativeSchema,
    NativeSchemaError,
    PayloadRefused,
    native_schema_id,
    validate_record_head,
)
from core.visualizer_engine.packet_abi import MODE_CODES
from widgets.spotify_visualizer.spectrum_frame_inputs import MAX_LEVELS, SPECTRUM_FRAME_INPUTS

MODE_ID = "spectrum"
VERSION = 1
SCHEMA_ID = native_schema_id(MODE_CODES[MODE_ID], VERSION)
_U32_MAX = 0xFFFFFFFF


def _length_field(name: str) -> str:
    return f"{name}_len"


#: The declared inputs the record carries (a Settings-only input, ``record=False``, reaches the native core by name
#: with the other settings instead).
_RECORDED = tuple(entry for entry in SPECTRUM_FRAME_INPUTS if entry.record)


def _layout_entries() -> tuple[tuple[str, str, int], ...]:
    entries = []
    for entry in _RECORDED:
        if entry.kind == "levels":
            entries.append((entry.name, "f64", MAX_LEVELS))
            entries.append((_length_field(entry.name), "u32", 1))
        elif entry.kind == "rgba":
            entries.append((entry.name, "f64x4", 1))
        elif entry.kind == "f64":
            entries.append((entry.name, "f64", 1))
        elif entry.kind in ("bool", "count", "enum"):
            entries.append((entry.name, "u32", 1))
        else:
            raise RuntimeError(f"no native field kind for frame input {entry.name} ({entry.kind})")
    return tuple(entries)


LAYOUT = NativeLayout.build(_layout_entries())
#: The record's field names in declaration order (``project``'s and ``decode``'s key order).
FIELD_NAMES = tuple(name for name, _kind, _count in _layout_entries())


def _field_checks() -> tuple[tuple[str, str, int], ...]:
    checks = []
    for entry in _RECORDED:
        if entry.kind == "levels":
            checks.append((_length_field(entry.name), "at_most", MAX_LEVELS))
        elif entry.kind == "bool":
            checks.append((entry.name, "boolean", 1))
        elif entry.kind == "enum":
            checks.append((entry.name, "enum", len(entry.table)))
    return tuple(checks)


#: The record's own range rules in the order ``decode`` applies them (``native_schema.FIELD_CHECK_KINDS``); the C++
#: reader applies the same table (``native/core/src/frame_abi_generated.h``).
FIELD_CHECKS = _field_checks()


# ------------------------------------------------------------------------------------------------- the fields

def _source(frame: Any, entry) -> object:
    if entry.source == "logical":
        return getattr(frame, entry.name)
    if entry.source == "common":
        return getattr(frame.common, entry.name)
    if entry.source == "mode_state":
        return getattr(frame.mode_state, entry.name)
    if entry.source == "style":
        style = frame.common.style
        if entry.required:
            try:
                return style[entry.name]
            except KeyError:
                raise NativeSchemaError(f"Spectrum frame style has no {entry.name}") from None
        return style.get(entry.name, entry.default)
    if entry.source == "parameters":
        try:
            return frame.mode_state.parameters[entry.name]
        except KeyError:
            raise NativeSchemaError(f"Spectrum frame has no parameter {entry.name}") from None
    raise RuntimeError(f"unknown frame input source {entry.source}")


def _real(name: str, value: object) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise NativeSchemaError(f"{name} is not finite")
    return number


def _channels(name: str, value: object) -> tuple[float, float, float, float]:
    # The shape ``implementation_values.rgba`` admits, before its normalisation and clamp.
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 3:
        raise NativeSchemaError(f"{name} is not a colour channel sequence: {value!r}")
    alpha = value[3] if len(value) > 3 else 255
    return tuple(_real(name, channel) for channel in (*value[:3], alpha))   # type: ignore[return-value]


def project(frame: Any) -> dict[str, object]:
    """The record's field values (header words excluded), taken from a ``VisualizerLogicalFrame`` of Spectrum."""
    if getattr(frame, "mode_id", None) != MODE_ID:
        raise NativeSchemaError(f"Spectrum's native schema cannot carry a {getattr(frame, 'mode_id', None)!r} frame")
    values: dict[str, object] = {}
    for entry in _RECORDED:
        value = _source(frame, entry)
        if entry.kind == "levels":
            kept = tuple(_real(entry.name, level) for level in tuple(value)[:MAX_LEVELS])
            values[entry.name] = kept + (0.0,) * (MAX_LEVELS - len(kept))
            values[_length_field(entry.name)] = len(kept)
        elif entry.kind == "rgba":
            values[entry.name] = _channels(entry.name, value)
        elif entry.kind == "f64":
            values[entry.name] = _real(entry.name, value)
        elif entry.kind == "bool":
            values[entry.name] = 1 if bool(value) else 0
        elif entry.kind == "count":
            count = int(value)
            if not 0 <= count <= _U32_MAX:
                raise NativeSchemaError(f"{entry.name} {count} does not fit a u32")
            values[entry.name] = count
        elif entry.kind == "enum":
            text = str(value)
            values[entry.name] = entry.table.index(text) if text in entry.table else ENUM_OUTSIDE
    return values


def encode(frame: Any) -> bytes:
    """The worker's writer: one Spectrum logical frame as the version-1 record."""
    return LAYOUT.pack(SCHEMA_ID, project(frame))


def decode(payload: bytes) -> dict[str, object]:
    """The reference reader: the record's fields by name (header words excluded), validated by size and offsets and
    by each field's own range; a malformed record is refused (``PayloadRefused``), never repaired."""
    validate_record_head(payload, SCHEMA)
    unpacked = LAYOUT.unpack(payload)
    values = {name: unpacked[name] for name in FIELD_NAMES}
    for name, kind, limit in FIELD_CHECKS:
        value = values[name]
        if kind == "at_most" and value > limit:
            raise PayloadRefused("record", f"{name} is {value}, more than {limit}")
        if kind == "boolean" and value not in (0, 1):
            raise PayloadRefused("record", f"{name} is {value}, not a boolean")
        if kind == "enum" and value != ENUM_OUTSIDE and value >= limit:
            raise PayloadRefused("record", f"{name} {value} is outside its table")
    return values


SCHEMA = NativeSchema(mode_id=MODE_ID, version=VERSION, layout=LAYOUT, encode=encode, decode=decode,
                      fields=FIELD_NAMES, checks=FIELD_CHECKS)
SCHEMAS = (SCHEMA,)

__all__ = ["ENUM_OUTSIDE", "FIELD_CHECKS", "FIELD_NAMES", "LAYOUT", "MODE_ID", "SCHEMA", "SCHEMAS", "SCHEMA_ID", "VERSION", "decode", "encode",
           "project"]
