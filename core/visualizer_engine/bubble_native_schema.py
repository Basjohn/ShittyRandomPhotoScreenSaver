"""Bubble's fixed-layout native frame schema (native core N5.1; mode id ``bubble``).

A generic mode's runtime schema (D12, ``native_schema._RUNTIME_SCHEMA_MODULES``): handed to the core when the route
binds its stream, never compiled into the module. The record carries BubbleDraw's per-frame members
(``rendering.quick.visualizer.implementations.bubble.BUBBLE_FRAME_MEMBERS``), each named as its member so the core packs
it by name: the 192 positions and extras and the 576 trail samples (four-number elements, zero past the count and on a
frame without trail samples), the count (at most 192), the eight big-class words (two uvec4), the wake's strength and opacity, the
rainbow hue and the ambient layer's two switches; and the ambient layer's two instance streams (D15 point 4), the points
(six floats each, at most 192) and the hero occluders (four floats each, at most 192), each with its used length in
floats. Every value is the Python renderer's own (``bubble_frame_values``); the core rounds each f64 to float as the
Python block packer does. Everything else is the core's (the card) or a setting (``bubble_settings_values``,
``bubble_ambient_settings_values``).

``encode`` is the route's writer; ``decode`` the pure-Python reference reader; ``project`` the field values of a logical
frame: ``decode(encode(frame)) == project(frame)``.

Version 2 (22 Nov: 192 heroes for the display-wide card, was 110). A change to the fields or the layout is a new version (the test pins the layout's fingerprint).
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

MODE_ID = "bubble"
VERSION = 2
SCHEMA_ID = native_schema_id(MODE_CODES[MODE_ID], VERSION)
#: The shader's capacities (``bubble.frag``: ``vec4 u_bubbles_pos[192]``, ``u_bubbles_trail[576]``) and the ambient
#: layer's (``bubble_ambient``: 96 microbubbles and 96 particles of six floats; one occluder of four per hero).
#: ``bubble_viewport_profile.BUBBLE_RENDER_CAPACITY`` (a test holds the two equal; this table imports no widget).
BUBBLES = 192
TRAIL_SAMPLES = 3 * BUBBLES
AMBIENT_POINT_FLOATS = 6 * 192
AMBIENT_OCCLUDER_FLOATS = 4 * BUBBLES

_ENTRIES: tuple[tuple[str, str, int], ...] = (
    ("u_bubbles_pos", "f64x4", BUBBLES),
    ("u_bubbles_extra", "f64x4", BUBBLES),
    ("u_bubbles_trail", "f64x4", TRAIL_SAMPLES),
    ("ambient_points", "f32", AMBIENT_POINT_FLOATS),
    ("ambient_occluders", "f32", AMBIENT_OCCLUDER_FLOATS),
    ("u_big_class_bits", "u32", 4),
    ("u_big_class_bits_hi", "u32", 4),
    ("u_trail_strength", "f64", 1),
    ("u_tail_opacity", "f64", 1),
    ("u_rainbow_hue_offset", "f64", 1),
    ("u_bubble_count", "u32", 1),
    ("u_ambient_enabled", "u32", 1),
    ("u_ambient_light_enabled", "u32", 1),
    ("ambient_point_floats", "u32", 1),
    ("ambient_occluder_floats", "u32", 1),
)
LAYOUT = NativeLayout.build(_ENTRIES)
FIELD_NAMES = tuple(name for name, _kind, _count in _ENTRIES)
FIELD_CHECKS: tuple[tuple[str, str, int], ...] = (
    ("u_bubble_count", "at_most", BUBBLES),
    ("u_ambient_enabled", "boolean", 1),
    ("u_ambient_light_enabled", "boolean", 1),
    ("ambient_point_floats", "at_most", AMBIENT_POINT_FLOATS),
    ("ambient_occluder_floats", "at_most", AMBIENT_OCCLUDER_FLOATS),
)


def project(frame: Any) -> dict[str, object]:
    """The record's field values (header words excluded), from a Bubble ``VisualizerLogicalFrame``: the Python
    renderer's own ``bubble_frame_values``."""
    if getattr(frame, "mode_id", None) != MODE_ID:
        raise NativeSchemaError(f"Bubble's native schema cannot carry a {getattr(frame, 'mode_id', None)!r} frame")
    # The renderer's module is imported only by the writer (the GUI thread's route), never by a reader of the table.
    from rendering.quick.visualizer.implementations.bubble import bubble_frame_values

    computed = bubble_frame_values(frame)
    values: dict[str, object] = {}
    for name, kind, count in _ENTRIES:
        value = computed[name]
        if kind == "f64x4":
            rows = tuple(tuple(float(v) for v in row) for row in value)
            if len(rows) != count or not all(math.isfinite(v) for row in rows for v in row):
                raise NativeSchemaError(f"{name} is not {count} finite four-number elements")
            values[name] = rows
        elif kind == "f32":
            values[name] = bytes(value).ljust(LAYOUT.field(name).size, b"\0")   # zero past the used length
        elif count > 1:
            values[name] = tuple(int(v) for v in value)
        elif kind == "f64":
            number = float(value)
            if not math.isfinite(number):
                raise NativeSchemaError(f"{name} is not finite")
            values[name] = number
        else:
            values[name] = int(value)
    return values


def encode(frame: Any) -> bytes:
    """The writer: one Bubble logical frame as the version-2 record."""
    return LAYOUT.pack(SCHEMA_ID, project(frame))


def decode(payload: bytes) -> dict[str, object]:
    """The reference reader: the record's fields by name (header words excluded), validated by size and offsets; the
    f32 streams as their bytes."""
    validate_record_head(payload, SCHEMA)
    unpacked = LAYOUT.unpack(payload)
    values = {name: unpacked[name] for name in FIELD_NAMES}
    for name in ("ambient_points", "ambient_occluders"):
        field = LAYOUT.field(name)
        values[name] = bytes(payload[field.offset:field.offset + field.size])
    return values


SCHEMA = NativeSchema(mode_id=MODE_ID, version=VERSION, layout=LAYOUT, encode=encode, decode=decode,
                      fields=FIELD_NAMES, checks=FIELD_CHECKS)
SCHEMAS = (SCHEMA,)

__all__ = ["AMBIENT_OCCLUDER_FLOATS", "AMBIENT_POINT_FLOATS", "BUBBLES", "FIELD_CHECKS", "FIELD_NAMES", "LAYOUT",
           "MODE_ID", "SCHEMA", "SCHEMAS", "SCHEMA_ID", "TRAIL_SAMPLES", "VERSION", "decode", "encode", "project"]
