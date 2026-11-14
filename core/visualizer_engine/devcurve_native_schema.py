"""Spline Curve's fixed-layout native frame schema (native core N5.1; mode id ``devcurve``).

A generic mode's runtime schema (D12, ``native_schema._RUNTIME_SCHEMA_MODULES``): handed to the core when the route
binds its stream, never compiled into the module. The record carries exactly DevCurveDraw's per-frame members
(``rendering.quick.visualizer.implementations.devcurve.DEVCURVE_FRAME_MEMBERS``), each field named as its member, so
the core packs it by name (``packRecordField``): the four curves (96 samples each, padded past the sample count with
its last sample, as the Python renderer pads them), the three specular slots, the foreground specular alpha (the
authored alpha times the runtime's play/pause ramp) and the rainbow hue offset (the logical clock times the speed).
Every value is the Python renderer's own (``devcurve_frame_values``), stored as f64; the core rounds each to float as
the Python block packer does. Everything else in DevCurveDraw is the core's (the card) or a setting
(``devcurve_settings_values``), sent when it changes.

``encode`` is the route's writer; ``decode`` the pure-Python reference reader. ``project`` the field values of a
logical frame: ``decode(encode(frame)) == project(frame)``.

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

MODE_ID = "devcurve"
VERSION = 1
SCHEMA_ID = native_schema_id(MODE_CODES[MODE_ID], VERSION)
#: The curve members' sample count (``devcurve.frag``'s ``float u_devcurve_curve_*[96]``).
CURVE_SAMPLES = 96
_LAYERS = ("bass", "vocals", "mids", "transients")

_ENTRIES: tuple[tuple[str, str, int], ...] = (
    *((f"u_devcurve_curve_{name}", "f64", CURVE_SAMPLES) for name in _LAYERS),
    *((f"u_devcurve_specular_slot{index}", "f64x4", 1) for index in range(3)),
    ("u_devcurve_foreground_specular_alpha", "f64", 1),
    ("u_rainbow_hue_offset", "f64", 1),
)
LAYOUT = NativeLayout.build(_ENTRIES)
FIELD_NAMES = tuple(name for name, _kind, _count in _ENTRIES)
#: No u32 field, so no range rule.
FIELD_CHECKS: tuple[tuple[str, str, int], ...] = ()


def _finite(name: str, values) -> None:
    for value in values:
        if not math.isfinite(float(value)):
            raise NativeSchemaError(f"{name} is not finite")


def project(frame: Any) -> dict[str, object]:
    """The record's field values (header words excluded), from a Spline Curve ``VisualizerLogicalFrame``: the Python
    renderer's own ``devcurve_frame_values``."""
    if getattr(frame, "mode_id", None) != MODE_ID:
        raise NativeSchemaError(f"Spline Curve's native schema cannot carry a {getattr(frame, 'mode_id', None)!r} frame")
    # The renderer's module is imported only by the writer (the GUI thread's route), never by a reader of the table.
    from rendering.quick.visualizer.implementations.devcurve import devcurve_frame_values

    computed = devcurve_frame_values(frame)
    values: dict[str, object] = {}
    for name, kind, count in _ENTRIES:
        value = computed[name]
        numbers = tuple(float(v) for v in value) if (kind == "f64x4" or count > 1) else (float(value),)
        _finite(name, numbers)
        values[name] = numbers if (kind == "f64x4" or count > 1) else numbers[0]
    return values


def encode(frame: Any) -> bytes:
    """The writer: one Spline Curve logical frame as the version-1 record."""
    return LAYOUT.pack(SCHEMA_ID, project(frame))


def decode(payload: bytes) -> dict[str, object]:
    """The reference reader: the record's fields by name (header words excluded), validated by size and offsets."""
    validate_record_head(payload, SCHEMA)
    unpacked = LAYOUT.unpack(payload)
    return {name: unpacked[name] for name in FIELD_NAMES}


SCHEMA = NativeSchema(mode_id=MODE_ID, version=VERSION, layout=LAYOUT, encode=encode, decode=decode,
                      fields=FIELD_NAMES, checks=FIELD_CHECKS)
SCHEMAS = (SCHEMA,)

__all__ = ["CURVE_SAMPLES", "FIELD_CHECKS", "FIELD_NAMES", "LAYOUT", "MODE_ID", "SCHEMA", "SCHEMAS", "SCHEMA_ID",
           "VERSION", "decode", "encode", "project"]
