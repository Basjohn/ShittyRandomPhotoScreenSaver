"""The Oscilloscope's fixed-layout native frame schema (native core N5.1; mode id ``oscilloscope``).

A generic mode's runtime schema (D12, ``native_schema._RUNTIME_SCHEMA_MODULES``): handed to the core when the route
binds its stream, never compiled into the module. The record carries what follows the music each frame, from the
logical frame alone (``rendering.quick.visualizer.implementations.oscilloscope.oscilloscope_frame_values``), each field
named as what it fills: the beam block's per-frame members (``OSCILLOSCOPE_FRAME_MEMBERS``: each trace's alpha, the
points per trace, the flare's widening, the brightness, the white-hot centre, the beam colour) and the composite's
bloom strength; the traces' points as a storage stream (D15 point 4; float32 x, y, at most 16 traces of 384 points,
zero past the used length) with its used length in floats; the beam's instance count (a quad a segment) and the
graticule's vertex count. Every value is the Python renderer's own; the core rounds each f64 to float as the Python
block packer does. Everything else is the core's (the card) or a setting (``oscilloscope_settings_values``).

``encode`` is the route's writer; ``decode`` the pure-Python reference reader; ``project`` the field values of a logical
frame: ``decode(encode(frame)) == project(frame)``.

Version 1. A change to the fields or the layout is a new version (the test pins the layout's fingerprint).
"""
from __future__ import annotations

import math
from typing import Any

from core.visualizer_engine.native_schema import (
    NativeLayout,
    NativeSchema,
    NativeSchemaError,
    native_schema_id,
    validate_record_head,
)
from core.visualizer_engine.packet_abi import MODE_CODES

MODE_ID = "oscilloscope"
VERSION = 1
SCHEMA_ID = native_schema_id(MODE_CODES[MODE_ID], VERSION)
#: The beam's capacities (``oscilloscope_program``: 16 traces, the afterglow's 15 and the live one, of at most 384
#: points; the beam block's ``float u_alpha[16]``).
TRACES = 16
TRACE_POINTS = 384
POINT_FLOATS = 2 * TRACES * TRACE_POINTS
SEGMENTS = TRACES * (TRACE_POINTS - 1)
GRATICULE_VERTICES = 4

_ENTRIES: tuple[tuple[str, str, int], ...] = (
    ("u_beam", "f64x4", 1),
    ("u_alpha", "f64", TRACES),
    ("osc_points", "f32", POINT_FLOATS),
    ("u_widen", "f64", 1),
    ("u_bright", "f64", 1),
    ("u_hot", "f64", 1),
    ("u_bloom_strength", "f64", 1),
    ("u_points", "u32", 1),
    ("osc_point_floats", "u32", 1),
    ("osc_segments", "u32", 1),
    ("osc_graticule_vertices", "u32", 1),
)
LAYOUT = NativeLayout.build(_ENTRIES)
FIELD_NAMES = tuple(name for name, _kind, _count in _ENTRIES)
FIELD_CHECKS: tuple[tuple[str, str, int], ...] = (
    ("u_points", "at_most", TRACE_POINTS),
    ("osc_point_floats", "at_most", POINT_FLOATS),
    ("osc_segments", "at_most", SEGMENTS),
    ("osc_graticule_vertices", "at_most", GRATICULE_VERTICES),
)


def project(frame: Any) -> dict[str, object]:
    """The record's field values (header words excluded), from an Oscilloscope ``VisualizerLogicalFrame``: the Python
    renderer's own ``oscilloscope_frame_values``."""
    if getattr(frame, "mode_id", None) != MODE_ID:
        raise NativeSchemaError(f"the Oscilloscope's native schema cannot carry a {getattr(frame, 'mode_id', None)!r} "
                                "frame")
    # The renderer's module is imported only by the writer (the GUI thread's route), never by a reader of the table.
    from rendering.quick.visualizer.implementations.oscilloscope import oscilloscope_frame_values

    computed = oscilloscope_frame_values(frame)
    values: dict[str, object] = {}
    for name, kind, count in _ENTRIES:
        value = computed[name]
        if kind == "f64x4":
            row = tuple(float(v) for v in value)
            if len(row) != 4 or not all(math.isfinite(v) for v in row):
                raise NativeSchemaError(f"{name} is not four finite numbers")
            values[name] = row
        elif kind == "f32":
            data = bytes(value)
            if len(data) > LAYOUT.field(name).size:
                raise NativeSchemaError(f"{name} holds {len(data)} bytes, past its {LAYOUT.field(name).size}")
            values[name] = data.ljust(LAYOUT.field(name).size, b"\0")   # zero past the used length
        elif kind == "f64" and count > 1:
            numbers = tuple(float(v) for v in value)
            if len(numbers) != count or not all(math.isfinite(v) for v in numbers):
                raise NativeSchemaError(f"{name} is not {count} finite numbers")
            values[name] = numbers
        elif kind == "f64":
            number = float(value)
            if not math.isfinite(number):
                raise NativeSchemaError(f"{name} is not finite")
            values[name] = number
        else:
            values[name] = int(value)
    return values


def encode(frame: Any) -> bytes:
    """The writer: one Oscilloscope logical frame as the version-1 record."""
    return LAYOUT.pack(SCHEMA_ID, project(frame))


def decode(payload: bytes) -> dict[str, object]:
    """The reference reader: the record's fields by name (header words excluded), validated by size and offsets; the
    points stream as its bytes."""
    validate_record_head(payload, SCHEMA)
    unpacked = LAYOUT.unpack(payload)
    values = {name: unpacked[name] for name in FIELD_NAMES}
    field = LAYOUT.field("osc_points")
    values["osc_points"] = bytes(payload[field.offset:field.offset + field.size])
    return values


SCHEMA = NativeSchema(mode_id=MODE_ID, version=VERSION, layout=LAYOUT, encode=encode, decode=decode,
                      fields=FIELD_NAMES, checks=FIELD_CHECKS)
SCHEMAS = (SCHEMA,)

__all__ = ["FIELD_CHECKS", "FIELD_NAMES", "GRATICULE_VERTICES", "LAYOUT", "MODE_ID", "POINT_FLOATS", "SCHEMA",
           "SCHEMAS", "SCHEMA_ID", "SEGMENTS", "TRACES", "TRACE_POINTS", "VERSION", "decode", "encode", "project"]
