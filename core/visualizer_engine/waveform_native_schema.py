"""Waveform Ribbon's fixed-layout native frame schema (native core N5.4; mode id ``waveform_ribbon``).

A generic mode's runtime schema (D12, ``native_schema._RUNTIME_SCHEMA_MODULES``): handed to the core when the route
binds its stream, never compiled into the module. The record carries everything Waveform's passes draw that follows
the frame, each field named as the member it fills (``rendering.gl_programs.waveform_shader_files.member_name``:
``<pass>_<member>``) and holding the Python renderer's own value (``waveform_pass_values``, byte-exact with its
packed blocks), except the members the card decides (``SETTINGS_MEMBERS``: each pass's viewport and the floor's
pre-pass mode, the route's settings). Beside them: the composite's bloom strength and HDR exposure; the four streams
(the ribbons' knot packet, the strand cohorts' births, the event sparks' births and the Pulse Rim field, f32 each
with its used length in floats); the draws' counts (the ribbons' instances and vertices, the strays' vertices) and
the compute groups of the world field and the yielding floor.

A pass the recipe leaves out (the fog's, the yielding floor's, the strays', the sparks', the floor's pre-pass) keeps
its fields at zero; its program variant leaves them unread (``native_route.waveform_program``).

The record needs the frame's framed view (its camera, N0.4): ``project`` refuses a frame without one.

Version 1. A change to the fields or the layout is a new version.
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

MODE_ID = "waveform_ribbon"
VERSION = 1
SCHEMA_ID = native_schema_id(MODE_CODES[MODE_ID], VERSION)

def _capacities() -> dict[str, int]:
    from core.ribbon_bursts import CAPACITY, STRIDE
    from core.ribbon_frames import MAX_STRIP_STATIONS
    from core.ribbon_geometry import MAX_PATH_SAMPLES
    from core.ribbon_packet import MAX_PACKET_BYTES, MAX_RIBBONS
    from core.ribbon_strand_cohorts import COHORT_BYTES
    from core.waveform_ribbon_dynamics import PULSE_GRID

    return {
        "knot_floats": MAX_PACKET_BYTES // 4,
        "cohort_floats": MAX_RIBBONS * COHORT_BYTES // 4,
        "burst_floats": CAPACITY * STRIDE,
        "burst_instances": CAPACITY,
        "pulse_floats": int(PULSE_GRID.size),
        "ribbons": MAX_RIBBONS,
        # The culled body (8 cross strips of the longest strip) and both continuation extensions (2048 divisions).
        "ribbon_vertices": (MAX_STRIP_STATIONS - 1) * 6 * 8 + 2 * 2048 * 6 * 8,
        # Every knot's strays at the most per knot (8), 24 segments of 6 vertices each.
        "strays_vertices": MAX_PATH_SAMPLES * 8 * 24 * 6,
        "groups": 64,
    }


CAPACITIES = _capacities()


from core.visualizer_engine.waveform_native_names import SHARED_MEMBERS, member_name  # noqa: E402,F401  (the rule's owner)


#: The members the card decides: the route's settings fill them (the pass's own target size, and whether the floor
#: reads its pre-pass), never the record.
SETTINGS_MEMBERS = frozenset({
    *(member_name(pass_id, "uViewport") for pass_id in ("ribbon", "ribbon_mirror", "strays", "strays_mirror", "bursts",
                                                        "bursts_mirror", "floor", "floor_prepass")),
    member_name("floor", "uSpecMode"), member_name("floor_prepass", "uSpecMode"),
})


#: The most an int member's u32 field holds (the core fills an int only under a range rule within int32).
INT_LIMIT = 2147483647


def field_kind(glsl_type: str, numbers: int) -> tuple[str, int]:
    """A member's record field (kind, count) by its GLSL type: a vec4 (or an array of them) ``f64x4`` per vec4, an
    int or int vector ``u32`` per number (under ``INT_LIMIT``), any other float member ``f64`` per number (ABI 36: the
    core fills a vec2, vec3 or mat4 from an f64 sequence)."""
    base = glsl_type.split("[")[0]
    if base == "vec4":
        return "f64x4", numbers // 4
    if base in ("int", "ivec2", "ivec3", "ivec4", "uint", "bool"):
        return "u32", numbers
    return "f64", numbers


def _member_entries() -> tuple[tuple[str, str, int], ...]:
    from core.visualizer_engine.waveform_native_members import PASS_MEMBERS

    entries, seen = [], set()
    for pass_id, members in PASS_MEMBERS:
        for member, numbers, glsl_type in members:
            name = member_name(pass_id, member)
            if name in seen or name in SETTINGS_MEMBERS:
                continue
            seen.add(name)
            entries.append((name, *field_kind(glsl_type, numbers)))
    return tuple(entries)


MEMBER_ENTRIES = _member_entries()
STREAM_ENTRIES: tuple[tuple[str, str, int], ...] = (
    ("ribbon_knots", "f32", CAPACITIES["knot_floats"]),
    ("ribbon_cohorts", "f32", CAPACITIES["cohort_floats"]),
    ("ribbon_bursts", "f32", CAPACITIES["burst_floats"]),
    ("ribbon_pulse", "f32", CAPACITIES["pulse_floats"]),
)
COUNT_ENTRIES: tuple[tuple[str, str, int], ...] = (
    ("u_bloom_strength", "f64", 1),
    ("u_hdr_exposure", "f64", 1),
    ("ribbon_knot_floats", "u32", 1),
    ("ribbon_cohort_floats", "u32", 1),
    ("ribbon_burst_floats", "u32", 1),
    ("ribbon_pulse_floats", "u32", 1),
    ("ribbon_instances", "u32", 1),
    ("ribbon_vertices", "u32", 1),
    ("strays_vertices", "u32", 1),
    ("bursts_instances", "u32", 1),
    ("field_groups", "u32", 1),
    ("give_groups", "u32", 1),
)
_ENTRIES = MEMBER_ENTRIES + STREAM_ENTRIES + COUNT_ENTRIES
LAYOUT = NativeLayout.build(_ENTRIES)
FIELD_NAMES = tuple(name for name, _kind, _count in _ENTRIES)
FIELD_CHECKS: tuple[tuple[str, str, int], ...] = tuple(
    (name, "at_most", INT_LIMIT) for name, kind, _count in MEMBER_ENTRIES if kind == "u32") + (
    ("ribbon_knot_floats", "at_most", CAPACITIES["knot_floats"]),
    ("ribbon_cohort_floats", "at_most", CAPACITIES["cohort_floats"]),
    ("ribbon_burst_floats", "at_most", CAPACITIES["burst_floats"]),
    ("ribbon_pulse_floats", "at_most", CAPACITIES["pulse_floats"]),
    ("ribbon_instances", "at_most", CAPACITIES["ribbons"]),
    ("ribbon_vertices", "at_most", CAPACITIES["ribbon_vertices"]),
    ("strays_vertices", "at_most", CAPACITIES["strays_vertices"]),
    ("bursts_instances", "at_most", CAPACITIES["burst_instances"]),
    ("field_groups", "at_most", CAPACITIES["groups"]),
    ("give_groups", "at_most", CAPACITIES["groups"]),
)


def flat_numbers(value: Any) -> tuple[float, ...]:
    """A member's value as its numbers in order (scalars, tuples, nested tuples, numpy values)."""
    if isinstance(value, (bytes, bytearray)):
        raise NativeSchemaError("a member's value is numbers, not bytes")
    if isinstance(value, (int, float)) or hasattr(value, "__float__") and not hasattr(value, "__len__"):
        return (float(value),)
    numbers: list[float] = []
    for item in value:
        numbers.extend(flat_numbers(item))
    return tuple(numbers)


def _stream(name: str, data: bytes) -> tuple[bytes, int]:
    size = LAYOUT.field(name).size
    if len(data) > size or len(data) % 4:
        raise NativeSchemaError(f"{name} holds {len(data)} bytes, past its {size} or not whole floats")
    return bytes(data).ljust(size, b"\0"), len(data) // 4


def project(frame: Any) -> dict[str, object]:
    """The record's field values (header words excluded) of a Waveform ``VisualizerLogicalFrame``: the Python
    renderer's own pass values (``waveform_pass_values``) for its framed view."""
    if getattr(frame, "mode_id", None) != MODE_ID:
        raise NativeSchemaError(f"Waveform Ribbon's native schema cannot carry a {getattr(frame, 'mode_id', None)!r} "
                                "frame")
    state = frame.mode_state
    if not state.framed_view:
        raise NativeSchemaError("a Waveform frame without its card's framed view has no camera")
    # The renderer's module is imported only by the writer (the GUI thread's route), never by a reader of the table.
    from rendering.quick.visualizer.implementations.waveform_ribbon import waveform_pass_values

    passes, counts = waveform_pass_values(state, (1, 1))
    values: dict[str, object] = {}
    filled = {member_name(pass_id, member): value for pass_id, members in passes.items()
              for member, value in members.items()}
    for name, kind, count in MEMBER_ENTRIES:
        value = filled.get(name)
        expected = 4 * count if kind == "f64x4" else count
        numbers = (0.0,) * expected if value is None else flat_numbers(value)
        if len(numbers) != expected or not all(math.isfinite(v) for v in numbers):
            raise NativeSchemaError(f"{name} is not {expected} finite numbers")
        if kind == "u32":
            if not all(0 <= v <= INT_LIMIT and v == int(v) for v in numbers):
                raise NativeSchemaError(f"{name} is not {expected} whole numbers from 0 to {INT_LIMIT}")
            numbers = tuple(int(v) for v in numbers)
        values[name] = numbers if expected > 1 else numbers[0]
    recipe = state.scene
    values["u_bloom_strength"] = float(recipe.bloom)
    values["u_hdr_exposure"] = float(recipe.exposure)
    for stream, used, data in (("ribbon_knots", "ribbon_knot_floats", state.packet.payload),
                               ("ribbon_cohorts", "ribbon_cohort_floats", state.strands),
                               ("ribbon_bursts", "ribbon_burst_floats", state.particles),
                               ("ribbon_pulse", "ribbon_pulse_floats", state.pulse)):
        values[stream], values[used] = _stream(stream, data)
    values["ribbon_instances"] = int(counts.get("ribbon_instances", 0))
    values["ribbon_vertices"] = int(counts.get("ribbon_vertices", 0))
    values["strays_vertices"] = int(counts.get("strays_vertices", 0)) if "strays" in passes else 0
    values["bursts_instances"] = CAPACITIES["burst_instances"] if "bursts" in passes else 0
    values["field_groups"] = -(-int(counts.get("field_samples", 0)) // 64)
    values["give_groups"] = -(-int(counts.get("give_samples", 0)) // 64)
    return values


def encode(frame: Any) -> bytes:
    """The writer: one Waveform logical frame as the version-1 record."""
    return LAYOUT.pack(SCHEMA_ID, project(frame))


def decode(payload: bytes) -> dict[str, object]:
    """The reference reader: the record's fields by name (header words excluded); the streams as their bytes."""
    validate_record_head(payload, SCHEMA)
    unpacked = LAYOUT.unpack(payload)
    values = {name: unpacked[name] for name in FIELD_NAMES}
    for stream, _kind, _count in STREAM_ENTRIES:
        field = LAYOUT.field(stream)
        values[stream] = bytes(payload[field.offset:field.offset + field.size])
    return values


SCHEMA = NativeSchema(mode_id=MODE_ID, version=VERSION, layout=LAYOUT, encode=encode, decode=decode,
                      fields=FIELD_NAMES, checks=FIELD_CHECKS)
SCHEMAS = (SCHEMA,)

__all__ = ["CAPACITIES", "COUNT_ENTRIES", "FIELD_CHECKS", "FIELD_NAMES", "LAYOUT", "MEMBER_ENTRIES", "MODE_ID",
           "SCHEMA", "SCHEMAS", "SCHEMA_ID", "SETTINGS_MEMBERS", "STREAM_ENTRIES", "VERSION", "decode", "encode",
           "flat_numbers", "project"]
