"""The packet reader's Python face (Current_Plan.md item 8b, N2.3; ``native/core/src/packet_reader.h``).

The native core's one consuming reader of a Visualizer frame stream, on its own view of the named mapping (D1), the
accept-edge acknowledgement and the non-consuming head read (D2), the drop edge, and the transport rule's refusal at
the slot head. In the product its frame edge will be the render thread's (N2.5); here every call runs on the caller's
thread, and the harnesses drive it (``native/core/python/packet_reader_check.py``).

``NativeCore.packet_reader`` creates one after comparing the module's compiled-in schema table with this build's
(``core.visualizer_engine.native_schema``): a module built from another layout is refused here, with the schema that
differs, never read.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Mapping

#: What ``read`` returns (``readResultName`` in ``packet_reader.cpp``).
READ_RESULTS = ("nothing", "accepted", "torn", "stale", "foreign", "refused", "failed", "retiring", "retired")
#: The negative controls a harness may switch on (``PacketReaderConfig`` in ``packet_reader.h``); the product never does.
#: ``pause_in_copy`` is not a negative control but D1's test hook "close during copy": each read pauses inside its copy
#: until another thread resumes it (``wait_paused``, ``resume``). ``accept_after_retire`` is that test's negative control
#: (a copy finished after the stream began retiring is accepted), ``copy_while_retiring`` the "no copy starts once
#: retiring" check's. The seqlock has two: ``skip_head_seqlock`` (an odd latest, the end check, the head's begin) and
#: ``skip_copy_reread`` (the begin re-read after the payload copy, alone).
READER_CONTROLS = ("skip_head_check", "skip_head_seqlock", "skip_copy_reread", "accept_unordered", "acknowledge_refused",
                   "head_resets_watermark", "skip_identity", "pause_in_copy", "accept_after_retire",
                   "copy_while_retiring")
_IDENTITY_KEYS = ("runtime_generation", "engine_generation", "activation_id", "mode_code")


class SchemaTableMismatch(RuntimeError):
    """The module's compiled-in frame schemas are not this build's (it was built from another layout)."""


@dataclass(frozen=True)
class NativeFrame:
    """The reader's retained frame: the slot head as stored, the record's bytes and its fields as the C++ table decodes
    them (None only under the ``skip_head_check`` control)."""

    head: Mapping[str, Any]
    payload: bytes = field(repr=False)
    fields: Mapping[str, Any] | None = field(repr=False)

    @property
    def sequence(self) -> int:
        return int(self.head["sequence"])


def python_schema_table() -> dict:
    """This build's frame ABI version, mode codes and native schemas, in the shape ``frame_schemas()`` reports them."""
    from core.visualizer_engine import native_schema, packet_abi

    schemas = []
    for schema in sorted(native_schema.native_schemas().values(), key=lambda s: s.schema_id):
        checks = {name: (kind, limit) for name, kind, limit in schema.checks}
        rows = []
        for name in schema.fields:
            entry = schema.layout.field(name)
            kind, limit = checks.get(name, ("", 0))
            rows.append([name, entry.kind, entry.count, entry.offset, kind, limit])
        schemas.append({
            "schema_id": schema.schema_id, "mode_id": schema.mode_id, "mode_code": schema.mode_code,
            "version": schema.version, "record_bytes": schema.layout.size,
            "fingerprint": schema.layout.fingerprint(), "fields": rows,
            "check_order": [schema.fields.index(name) for name, _kind, _limit in schema.checks],
        })
    return {"abi_version": packet_abi.ABI_VERSION, "mapping_prefix": packet_abi.FRAME_MAPPING_PREFIX,
            "mode_codes": dict(packet_abi.MODE_CODES), "schemas": schemas}


def schema_table_differences(compiled: Mapping[str, Any], expected: Mapping[str, Any]) -> list[str]:
    """What differs between the module's table and this build's (empty: the same layout)."""
    problems = []
    for key in ("abi_version", "mapping_prefix", "mode_codes"):
        if compiled.get(key) != expected.get(key):
            problems.append(f"{key}: module {compiled.get(key)!r}, this build {expected.get(key)!r}")
    by_id = {int(s["schema_id"]): s for s in compiled.get("schemas", ())}
    wanted = {int(s["schema_id"]): s for s in expected.get("schemas", ())}
    for schema_id in sorted(set(by_id) | set(wanted)):
        mine, theirs = wanted.get(schema_id), by_id.get(schema_id)
        if mine is None or theirs is None:
            problems.append(f"schema {schema_id:#x}: {'only the module' if mine is None else 'not in the module'}")
            continue
        for key in mine:
            if json.loads(json.dumps(theirs.get(key))) != json.loads(json.dumps(mine[key])):
                problems.append(f"schema {schema_id:#x} {key} differs")
    return problems


def reader_config(expect: Mapping[str, int] | None = None, controls: tuple[str, ...] = ()) -> str:
    """The reader's configuration JSON: the stream's expected identity (u32 as stored) and any negative controls."""
    unknown = [name for name in controls if name not in READER_CONTROLS]
    if unknown:
        raise ValueError(f"unknown packet reader controls {unknown} (the controls are {', '.join(READER_CONTROLS)})")
    config: dict[str, Any] = {"controls": list(controls)}
    if expect is not None:
        if set(expect) != set(_IDENTITY_KEYS):
            raise ValueError(f"an expected identity names exactly {', '.join(_IDENTITY_KEYS)}")
        config["expect"] = {key: int(expect[key]) & 0xFFFFFFFF for key in _IDENTITY_KEYS}
    return json.dumps(config)


class PacketReader:
    """One packet reader on the native core's side; closed explicitly (:meth:`close`)."""

    def __init__(self, module: ModuleType, handle: int) -> None:
        self._module = module
        self._handle = int(handle)
        self._closed: dict | None = None

    @property
    def handle(self) -> int:
        return self._handle

    def _live(self) -> int:
        if self._closed is not None:
            raise RuntimeError(f"packet reader {self._handle} is closed")
        return self._handle

    def read(self) -> str:
        """The consuming read at the frame edge; one of ``READ_RESULTS``."""
        return str(self._module.packet_reader_read(self._live()))

    def head(self) -> dict | None:
        """The newest whole slot's head; consumes nothing."""
        return self._module.packet_reader_head(self._live())

    def frame(self) -> NativeFrame | None:
        """The retained frame, or None (nothing accepted yet, dropped, or released)."""
        record = self._module.packet_reader_frame(self._live())
        if record is None:
            return None
        payload, fields = record.pop("payload"), record.pop("fields")
        return NativeFrame(head=record, payload=payload, fields=fields)

    def drop_retained_frame(self) -> None:
        self._module.packet_reader_drop(self._live())

    def wait_paused(self, timeout_ms: int) -> bool:
        """The ``pause_in_copy`` hook (another thread than the reading one): a read is paused inside its copy."""
        return bool(self._module.packet_reader_wait_paused(self._live(), int(timeout_ms)))

    def resume(self) -> None:
        """The ``pause_in_copy`` hook: the paused read goes on."""
        self._module.packet_reader_resume(self._live())

    def retire(self) -> None:
        self._module.packet_reader_retire(self._live())

    def release(self) -> None:
        self._module.packet_reader_release(self._live())

    def state(self) -> dict:
        return json.loads(self._module.packet_reader_state(self._live()))

    def close(self) -> dict:
        """Retire, release and forget (idempotent); the reader's last state."""
        if self._closed is None:
            self._closed = json.loads(self._module.packet_reader_close(self._handle))
        return self._closed


__all__ = ["NativeFrame", "PacketReader", "READER_CONTROLS", "READ_RESULTS", "SchemaTableMismatch", "python_schema_table",
           "reader_config", "schema_table_differences"]
