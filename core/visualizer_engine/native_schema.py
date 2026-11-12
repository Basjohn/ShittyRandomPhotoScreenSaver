"""The frame packet's ``payload_schema`` namespace and the fixed-layout native schemas (native core N2.3).

Transport rule 3 to 5 (``Docs/Future_Work/Native_Core_P3_Decisions.md``, "The transport rule", numbering decided by
the lead on 12 Nov 2026):

- ``payload_schema`` 1 is the tagged Python codec (``frame_codec.CODEC_SCHEMA``); values 0 and 2 to 0xFF are
  reserved and never valid.
- A native schema is ``(version << 16) | 0x100 | mode_code``: the mode code (``packet_abi.MODE_CODES``, append-only)
  in the low byte, bit 8 set, bits 9 to 15 and 24 to 31 zero, the version (1 to 255) in bits 16 to 23. Its low 16
  bits are therefore at least 0x101, so the codec's own u16 prefix (1) can never match a native payload's first u32.
- A native schema is a fixed-layout record: explicit offsets, little-endian, every array and four-component value
  16-byte aligned, the record's size a multiple of 16, the record's first two u32 words its own schema id and size.
  A reader validates it by size and offsets; it never decodes a tagged stream.
- A reader admits a slot at its head, before any payload copy (``admit_slot_head``): an unknown schema, an unknown
  mode code, a version newer than (or other than) the reader knows, or a size that disagrees with the layout is
  refused (``PayloadRefused``), counted, not acknowledged, and the stream is reported failed. It never guesses, skips
  silently or falls back to the other decoder.

The per-mode schemas live in their own modules (``_SCHEMA_MODULES``), imported on first use.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, Literal

from core.visualizer_engine.frame_codec import CODEC_SCHEMA
from core.visualizer_engine.packet_abi import MODE_CODES, PacketAbiError

NATIVE_BASE = 0x100
NATIVE_ALIGNMENT = 16
#: The native schema's mode id -> the module that defines it (``SCHEMA``: a ``NativeSchema``).
_SCHEMA_MODULES = {
    "spectrum": "core.visualizer_engine.spectrum_native_schema",
}

PayloadKind = Literal["codec", "native"]


class PayloadRefused(PacketAbiError):
    """A slot whose payload this reader does not admit (refused at the slot head, before any payload copy).

    ``cause``: ``schema`` (unknown or not this reader's kind), ``mode`` (an unknown mode code, or one disagreeing with
    the schema's), ``version`` (newer than, or other than, the versions this build knows), ``size`` (disagreeing with
    the layout) or ``record`` (an admitted record whose own field is out of its range: the reference decoder's)."""

    def __init__(self, cause: str, message: str) -> None:
        super().__init__(message)
        self.cause = cause


class NativeSchemaError(ValueError):
    """A frame the native encoder cannot carry (wrong mode, a value outside its field's shape)."""


def native_schema_id(mode_code: int, version: int) -> int:
    mode_code, version = int(mode_code), int(version)
    if not 1 <= mode_code <= 0xFF or not 1 <= version <= 0xFF:
        raise ValueError(f"no native schema id for mode code {mode_code}, version {version}")
    return (version << 16) | NATIVE_BASE | mode_code


def parse_native_schema_id(schema: int) -> tuple[int, int] | None:
    """(mode code, version) of a well-formed native id, else None (the codec's 1, a reserved value, stray bits)."""
    schema = int(schema)
    if schema & ~0x00FF01FF or not schema & NATIVE_BASE:
        return None
    mode_code, version = schema & 0xFF, (schema >> 16) & 0xFF
    if not mode_code or not version:
        return None
    return mode_code, version


# --------------------------------------------------------------------------------------------- record layouts

#: kind -> (struct format of one element, element bytes, alignment)
_KINDS = {
    "u32": ("I", 4, 4),
    "f64": ("d", 8, 8),
    "f64x4": ("4d", 32, NATIVE_ALIGNMENT),
}


@dataclass(frozen=True, slots=True)
class NativeField:
    name: str
    kind: str          # "u32", "f64" or "f64x4"
    count: int         # 1, or the array length
    offset: int

    @property
    def size(self) -> int:
        return _KINDS[self.kind][1] * self.count

    @property
    def is_array(self) -> bool:
        return self.count > 1


@dataclass(frozen=True, slots=True)
class NativeLayout:
    fields: tuple[NativeField, ...]
    size: int

    @classmethod
    def build(cls, fields: tuple[tuple[str, str, int], ...]) -> "NativeLayout":
        """Lay out ``(name, kind, count)`` entries: the header words (``payload_schema``, ``record_bytes``) first,
        then every 16-byte aligned entry (arrays and four-component values), then f64 scalars, then u32 scalars, each
        group in the given order; each entry at its alignment, the record padded to 16 bytes."""
        names = [name for name, _kind, _count in fields]
        if len(set(names)) != len(names) or {"payload_schema", "record_bytes"} & set(names):
            raise ValueError("native layout field names must be unique and not the header's")

        def alignment(entry) -> int:
            _name, kind, count = entry
            return NATIVE_ALIGNMENT if count > 1 else _KINDS[kind][2]
        ordered = ([("payload_schema", "u32", 1), ("record_bytes", "u32", 1)]
                   + [e for e in fields if alignment(e) == NATIVE_ALIGNMENT]
                   + [e for e in fields if alignment(e) == 8]
                   + [e for e in fields if alignment(e) == 4])
        placed, offset = [], 0
        for entry in ordered:
            name, kind, count = entry
            align = alignment(entry) if name not in ("payload_schema", "record_bytes") else 4
            offset = -(-offset // align) * align
            placed.append(NativeField(name, kind, int(count), offset))
            offset += _KINDS[kind][1] * int(count)
        size = -(-offset // NATIVE_ALIGNMENT) * NATIVE_ALIGNMENT
        return cls(tuple(placed), size)

    def field(self, name: str) -> NativeField:
        for entry in self.fields:
            if entry.name == name:
                return entry
        raise KeyError(name)

    def fingerprint(self) -> str:
        """A digest of the layout table (names, kinds, counts, offsets, size): a change without a version bump shows."""
        text = ";".join(f"{f.name}:{f.kind}:{f.count}:{f.offset}" for f in self.fields) + f";size={self.size}"
        return hashlib.sha256(text.encode("ascii")).hexdigest()[:16]

    def table(self) -> str:
        """The layout as a Markdown table (offset, size, type, name)."""
        rows = ["| offset | bytes | type | field |", "|---:|---:|---|---|"]
        for f in self.fields:
            kind = f.kind if f.count == 1 else f"{f.kind}[{f.count}]"
            rows.append(f"| {f.offset} | {f.size} | {kind} | {f.name} |")
        rows.append(f"| {self.size} | | | (record size) |")
        return "\n".join(rows)

    def pack(self, schema: int, values: dict[str, Any]) -> bytes:
        out = bytearray(self.size)
        struct.pack_into("<II", out, 0, int(schema), self.size)
        for f in self.fields[2:]:
            value = values[f.name]
            element = _KINDS[f.kind][0]
            if f.kind == "f64x4":
                struct.pack_into("<4d", out, f.offset, *value)
            elif f.count > 1:
                struct.pack_into(f"<{f.count}{element}", out, f.offset, *value)
            else:
                struct.pack_into(f"<{element}", out, f.offset, value)
        return bytes(out)

    def unpack(self, payload) -> dict[str, Any]:
        """Every field by name (the header words included), read at its offset; the caller validated the size."""
        view = memoryview(payload)
        values: dict[str, Any] = {}
        for f in self.fields:
            element = _KINDS[f.kind][0]
            if f.kind == "f64x4":
                values[f.name] = struct.unpack_from("<4d", view, f.offset)
            elif f.count > 1:
                values[f.name] = struct.unpack_from(f"<{f.count}{element}", view, f.offset)
            else:
                values[f.name] = struct.unpack_from(f"<{element}", view, f.offset)[0]
        return values


@dataclass(frozen=True, slots=True)
class NativeSchema:
    """One mode's fixed-layout record at one version: the worker's encoder and the pure-Python reference decoder."""
    mode_id: str
    version: int
    layout: NativeLayout
    encode: Callable[[Any], bytes]          # a VisualizerLogicalFrame of ``mode_id`` -> the record
    decode: Callable[[bytes], dict]         # the record -> its fields by name (validated by size and offsets)

    @property
    def mode_code(self) -> int:
        return MODE_CODES[self.mode_id]

    @property
    def schema_id(self) -> int:
        return native_schema_id(self.mode_code, self.version)


_schemas: dict[int, NativeSchema] | None = None


def native_schemas() -> dict[int, NativeSchema]:
    """Every native schema this build knows, by schema id."""
    global _schemas
    if _schemas is None:
        table = {}
        for mode_id, module in _SCHEMA_MODULES.items():
            for schema in import_module(module).SCHEMAS:
                if schema.mode_id != mode_id:
                    raise RuntimeError(f"{module} defines a schema for {schema.mode_id}, not {mode_id}")
                table[schema.schema_id] = schema
        _schemas = table
    return _schemas


def schema_for_mode(mode_id: str | None) -> NativeSchema:
    """The newest native schema of ``mode_id``; a mode without one fails explicitly."""
    candidates = [s for s in native_schemas().values() if s.mode_id == mode_id]
    if not candidates:
        raise NativeSchemaError(f"mode {mode_id!r} has no native schema")
    return max(candidates, key=lambda schema: schema.version)


def validate_record_head(payload, schema: NativeSchema) -> None:
    """The record's own header words agree with ``schema`` and its layout (size first: nothing read past the end)."""
    if len(payload) != schema.layout.size:
        raise PayloadRefused("size", f"a {len(payload)}-byte payload is not the {schema.layout.size}-byte "
                                     f"record of schema {schema.schema_id:#x}")
    head, size = struct.unpack_from("<II", payload, 0)
    if head != schema.schema_id or size != schema.layout.size:
        raise PayloadRefused("schema", f"the record names schema {head:#x} ({size} bytes), not "
                                       f"{schema.schema_id:#x} ({schema.layout.size} bytes)")


# ------------------------------------------------------------------------------------------- head admission

_KNOWN_MODE_CODES = frozenset(MODE_CODES.values())


def admit_slot_head(payload_schema: int, mode_code: int, payload_bytes: int, *, accept: PayloadKind) -> None:
    """Admit a slot by its head alone (no payload read), or raise ``PayloadRefused``.

    ``accept``: what this reader consumes. ``codec``: the tagged Python codec only (a native payload on a stream the
    Python codec consumes is refused: D2's one consumer per stream). ``native``: the native schemas this build knows."""
    schema, mode_code, payload_bytes = int(payload_schema), int(mode_code), int(payload_bytes)
    if mode_code and mode_code not in _KNOWN_MODE_CODES:
        raise PayloadRefused("mode", f"unknown mode code {mode_code} in the slot head")
    if schema == CODEC_SCHEMA:
        if accept != "codec":
            raise PayloadRefused("schema", "a tagged-codec payload on a native stream")
        return
    parsed = parse_native_schema_id(schema)
    if parsed is None:
        raise PayloadRefused("schema", f"unknown payload schema {schema:#x}")
    if accept != "native":
        raise PayloadRefused("schema", f"a native payload (schema {schema:#x}) on a stream the Python codec consumes")
    schema_mode, version = parsed
    if schema_mode not in _KNOWN_MODE_CODES:
        raise PayloadRefused("mode", f"schema {schema:#x} names unknown mode code {schema_mode}")
    if schema_mode != mode_code:
        raise PayloadRefused("mode", f"schema {schema:#x} is for mode code {schema_mode}, the slot's is {mode_code}")
    known = native_schemas()
    found = known.get(schema)
    if found is None:
        versions = [s.version for s in known.values() if s.mode_code == schema_mode]
        if not versions:
            raise PayloadRefused("schema", f"mode code {schema_mode} has no native schema in this build")
        newest = max(versions)
        relation = "newer than" if version > newest else "not one of"
        raise PayloadRefused("version", f"schema {schema:#x}: version {version} is {relation} this build's "
                                        f"{sorted(versions)}")
    if payload_bytes != found.layout.size:
        raise PayloadRefused("size", f"schema {schema:#x}: a {payload_bytes}-byte payload disagrees with its "
                                     f"{found.layout.size}-byte layout")


def decode_native_payload(payload_schema: int, payload: bytes) -> dict:
    """The reference reader's decode of an admitted slot's payload (the record's own head validated again)."""
    schema = native_schemas()[int(payload_schema)]
    return schema.decode(payload)


__all__ = [
    "NATIVE_ALIGNMENT",
    "NATIVE_BASE",
    "NativeField",
    "NativeLayout",
    "NativeSchema",
    "NativeSchemaError",
    "PayloadRefused",
    "admit_slot_head",
    "decode_native_payload",
    "native_schema_id",
    "native_schemas",
    "parse_native_schema_id",
    "schema_for_mode",
    "validate_record_head",
]
