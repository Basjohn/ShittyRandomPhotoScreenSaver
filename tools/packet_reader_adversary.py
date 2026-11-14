"""Adversarial frame streams for the packet readers (native core N2.3; the P3.0 tests of
``Docs/Future_Work/Native_Core_P3_Decisions.md``: torn writes, stale and duplicate sequences, wrong schema, mode or
version, oversize, the refusal).

One table of cases, run against any reader behind the small adapter interface below:

- ``ReferenceReader``: the Python reference (``packet_abi.FramePacketReader`` admitting by
  ``native_schema.admit_slot_head(accept="native")``, the schema's reference decoder, the acknowledgement at the accept
  edge as ``PacketMailbox._consume`` writes it). ``naive=True`` is its negative control: a reader with no seqlock, no head
  check and no watermark, which must fail every case that has a control.
- ``NativeReader``: the C++ reader through ``rendering.native`` (``PacketReader``), with its own negative controls (each
  case names the control that must make it fail).

A case returns ``(label, observed, expected)`` checks; it passes when every check holds, and its negative control is
seen when at least one does not. The in-place writer (``inplace_writer``, a separate process) races a reader's copy
on purpose: it rewrites the slot the latest sequence names, the one a correct writer never touches.

Used by ``tests/test_native_packet_reader_sources.py`` (the reference, now) and by
``native/core/python/packet_reader_check.py`` and ``tests/test_native_core_packet_reader.py`` (the built module).
Light at import: a spawned writer process imports only this module's top level.
"""
from __future__ import annotations

import struct
import uuid
from dataclasses import dataclass, field
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Callable

#: The adversarial mappings' slot size (room for the Spectrum record and an oversize case).
SLOT_BYTES = 4096
#: The identity every case's frames carry unless a case says otherwise: (runtime generation, engine generation,
#: activation id); the mode code is Spectrum's.
IDENTITY = (3, 5, 4)
_HEADER_BYTES = 64
_LATEST, _CONSUMED = 32, 40
_SLOT_HEAD = struct.Struct("<QIIddIIIIIIQ")
_U64 = struct.Struct("<Q")


# ----------------------------------------------------------------------------------------------- records

def valid_record(variant: int = 1) -> bytes:
    """A valid Spectrum record (every range rule held), derived from the schema's own field table: every real
    ``variant`` (so two variants differ in every real field), booleans 1, counts and kept lengths their largest
    admitted value, enums their first choice."""
    from core.visualizer_engine import spectrum_native_schema as spectrum

    checks = {name: (kind, limit) for name, kind, limit in spectrum.FIELD_CHECKS}
    values: dict[str, Any] = {}
    for name in spectrum.FIELD_NAMES:
        entry = spectrum.LAYOUT.field(name)
        kind, limit = checks.get(name, (None, 0))
        if entry.kind == "f64x4":
            values[name] = (float(variant),) * 4
        elif entry.kind == "f64":
            values[name] = (float(variant),) * entry.count if entry.count > 1 else float(variant)
        elif kind == "at_most":
            values[name] = limit
        elif kind == "boolean":
            values[name] = 1
        elif kind == "enum":
            values[name] = 0
        else:
            values[name] = 7
    return spectrum.LAYOUT.pack(spectrum.SCHEMA_ID, values)


def record_is_consistent(fields: dict) -> bool:
    """Every real field of a record ``valid_record`` wrote carries one value: a copy torn across two variants does not."""
    reals = []
    for value in fields.values():
        if isinstance(value, float):
            reals.append(value)
        elif isinstance(value, tuple) and value and isinstance(value[0], float):
            reals.extend(value)
    return bool(reals) and len(set(reals)) == 1


def spectrum_schema_id() -> int:
    from core.visualizer_engine import spectrum_native_schema as spectrum

    return spectrum.SCHEMA_ID


# ---------------------------------------------------------------------------------------------- mappings

def create_mapping(slot_bytes: int = SLOT_BYTES) -> SharedMemory:
    """A fresh frame mapping (the owner's: closed and unlinked by the caller)."""
    from core.visualizer_engine.packet_abi import MODE_CODES, create_frame_mapping

    return create_frame_mapping(generation=IDENTITY[0], slot_bytes=slot_bytes, engine_generation=IDENTITY[1],
                                activation_id=IDENTITY[2], mode_code=MODE_CODES["spectrum"],
                                token=uuid.uuid4().hex[:12])


class Adversary:
    """Raw access to one mapping: publishes as the ABI's writer does, and writes the states a writer that died, raced or
    misbehaved leaves behind."""

    def __init__(self, name: str) -> None:
        self.memory = SharedMemory(name=name)
        self.view = self.memory.buf
        self.slot_bytes = struct.unpack_from("<I", self.view, 24)[0]

    def publish(self, payload: bytes, *, schema: int | None = None, mode: int = 1,
                identity: tuple[int, int, int] = IDENTITY, edges: int = 0, logical: float = 1.0) -> int:
        """Publish whole, as ``FramePacketWriter`` does (a fresh writer continues after the newest slot)."""
        from core.visualizer_engine.packet_abi import FramePacketWriter

        writer = FramePacketWriter(self.view)
        try:
            return writer.publish(payload, payload_schema=spectrum_schema_id() if schema is None else schema,
                                  logical_timestamp=logical, mode_code=mode, runtime_generation=identity[0],
                                  engine_generation=identity[1], activation_id=identity[2], protected_edges=edges)
        finally:
            writer.release()

    def base(self, slot: int) -> int:
        return _HEADER_BYTES + slot * self.slot_bytes

    def slot_of(self, sequence: int) -> int:
        for slot in range(3):
            if _U64.unpack_from(self.view, self.base(slot))[0] == sequence:
                return slot
        raise LookupError(f"no slot holds sequence {sequence}")

    def other_slot(self, sequence: int) -> int:
        """A slot that is not the one holding ``sequence`` (the next a writer would use)."""
        return (self.slot_of(sequence) + 1) % 3

    def write_slot(self, slot: int, *, sequence: int, payload: bytes, schema: int | None = None, mode: int = 1,
                   identity: tuple[int, int, int] = IDENTITY, begin: int | None = None, end: int | None = None,
                   payload_bytes: int | None = None) -> None:
        """Write one slot raw: its head, its payload, then ``begin`` and ``end`` as given (default: ``sequence``)."""
        base = self.base(slot)
        _SLOT_HEAD.pack_into(self.view, base, sequence, len(payload) if payload_bytes is None else payload_bytes,
                             spectrum_schema_id() if schema is None else schema, 1.0, float("nan"), 0, 0,
                             *identity, mode, 0)
        self.view[base + 64:base + 64 + len(payload)] = payload
        _U64.pack_into(self.view, base, sequence if begin is None else begin)
        _U64.pack_into(self.view, base + self.slot_bytes - 8, sequence if end is None else end)

    def set_payload_bytes(self, sequence: int, payload_bytes: int) -> None:
        struct.pack_into("<I", self.view, self.base(self.slot_of(sequence)) + 8, payload_bytes)

    def set_latest(self, sequence: int) -> None:
        _U64.pack_into(self.view, _LATEST, sequence)

    def latest(self) -> int:
        return _U64.unpack_from(self.view, _LATEST)[0]

    def consumed(self) -> int:
        return _U64.unpack_from(self.view, _CONSUMED)[0]

    def close(self) -> None:
        self.view = None
        self.memory.close()


# ----------------------------------------------------------------------------------------------- readers

class ReferenceReader:
    """The Python reference reader behind the adapter interface (``naive``: its negative control)."""

    name = "reference"

    def __init__(self, mapping_name: str, *, naive: bool = False, expect: Any = None, controls: tuple = ()) -> None:
        from functools import partial

        from core.visualizer_engine.native_schema import admit_slot_head
        from core.visualizer_engine.packet_abi import FramePacketReader

        self.memory = SharedMemory(name=mapping_name)
        self._reader = FramePacketReader(self.memory.buf, admit=partial(admit_slot_head, accept="native"))
        self.naive = naive
        self._retained: tuple[int, bytes, dict | None] | None = None
        self._cause: str | None = None

    def read(self) -> str:
        from core.visualizer_engine.native_schema import PayloadRefused, decode_native_payload

        if self.naive:
            return self._naive_read()
        if self._cause is not None:
            return "failed"
        view = self.memory.buf
        latest = _U64.unpack_from(view, _LATEST)[0]
        torn = self._reader.torn_reads
        try:
            packet = self._reader.read_latest()
            if packet is None:
                if self._reader.torn_reads > torn:
                    return "torn"
                return "stale" if latest < self._reader.accepted else "nothing"
            fields = decode_native_payload(packet.payload_schema, packet.payload)
        except PayloadRefused as refusal:
            self._cause = refusal.cause
            return "refused"
        self._reader.acknowledge(packet.sequence)
        self._retained = (packet.sequence, packet.payload, fields)
        return "accepted"

    def _naive_read(self) -> str:
        """No seqlock, no head check, no watermark: the slot the latest sequence names, whatever it holds."""
        view = self.memory.buf
        latest = _U64.unpack_from(view, _LATEST)[0]
        slot_bytes = self._reader._slot_bytes
        for slot in range(3):
            base = _HEADER_BYTES + slot * slot_bytes
            if _U64.unpack_from(view, base)[0] != latest:
                continue
            size = min(struct.unpack_from("<I", view, base + 8)[0], slot_bytes - 72)
            payload = bytes(view[base + 64:base + 64 + size])
            fields = None
            try:
                from core.visualizer_engine import spectrum_native_schema as spectrum

                fields = spectrum.LAYOUT.unpack(payload) if len(payload) == spectrum.LAYOUT.size else None
                if fields is not None:
                    fields = {name: fields[name] for name in spectrum.FIELD_NAMES}
            except struct.error:
                fields = None
            _U64.pack_into(view, _CONSUMED, latest)
            self._retained = (latest, payload, fields)
            return "accepted"
        return "nothing"

    def head(self) -> None:
        """The reference's non-consuming check (``has_unread``): reads the header only."""
        self._reader.has_unread()

    def retained_sequence(self) -> int | None:
        return None if self._retained is None else self._retained[0]

    def retained_payload(self) -> bytes | None:
        return None if self._retained is None else self._retained[1]

    def retained_fields(self) -> dict | None:
        return None if self._retained is None else self._retained[2]

    def refusal_cause(self) -> str | None:
        return self._cause

    def torn_reads(self) -> int:
        return self._reader.torn_reads

    def close(self) -> None:
        self._reader.release()
        self.memory.close()


class NativeReader:
    """The C++ reader (``rendering.native.PacketReader``) behind the adapter interface."""

    name = "native"

    def __init__(self, core: Any, mapping_name: str, *, expect: dict | None = None, controls: tuple = ()) -> None:
        self.reader = core.packet_reader(mapping_name, expect=expect, controls=tuple(controls))

    def read(self) -> str:
        return self.reader.read()

    def head(self) -> dict | None:
        return self.reader.head()

    def _frame(self):
        return self.reader.frame()

    def retained_sequence(self) -> int | None:
        frame = self._frame()
        return None if frame is None else frame.sequence

    def retained_payload(self) -> bytes | None:
        frame = self._frame()
        return None if frame is None else frame.payload

    def retained_fields(self) -> dict | None:
        frame = self._frame()
        return None if frame is None else frame.fields

    def refusal_cause(self) -> str | None:
        refusal = self.reader.state().get("refusal")
        return None if refusal is None else refusal["cause"]

    def torn_reads(self) -> int:
        return int(self.reader.state()["torn_reads"])

    def close(self) -> dict:
        return self.reader.close()


# ------------------------------------------------------------------------------------------------- cases

Check = tuple[str, Any, Any]


@dataclass(frozen=True)
class Case:
    name: str
    run: Callable[[Adversary, Any], list[Check]]
    #: The native reader's negative controls, each of which must make the case fail (empty: none applies).
    controls: tuple[str, ...] = ()
    #: The case applies to the Python reference (False: a native-only contract, D1's or D2's).
    reference: bool = True
    #: The stream's expected identity the native reader is opened with.
    expect: dict | None = None
    #: The naive reader (the reference's negative control) makes the case fail.
    naive_fails: bool = True


def _fields_repr(reader) -> str:
    fields = reader.retained_fields()
    return repr(None if fields is None else dict(fields))


def _whole(adv: Adversary, reader) -> list[Check]:
    from core.visualizer_engine import spectrum_native_schema as spectrum

    record = valid_record(1)
    sequence = adv.publish(record)
    return [("result", reader.read(), "accepted"), ("consumed", adv.consumed(), sequence),
            ("retained", reader.retained_sequence(), sequence),
            ("fields", _fields_repr(reader), repr(spectrum.decode(record)))]


def _accepted_baseline(adv: Adversary, reader) -> int:
    sequence = adv.publish(valid_record(1))
    if reader.read() != "accepted":
        raise AssertionError("the baseline frame was not accepted")
    return sequence


def _latest_odd(adv: Adversary, reader) -> list[Check]:
    # The header names a slot that is mid-write (its begin and end odd): torn, the previous frame kept.
    accepted = _accepted_baseline(adv, reader)
    adv.write_slot(adv.other_slot(accepted), sequence=accepted + 1, payload=valid_record(2))
    adv.set_latest(accepted + 1)
    return [("result", reader.read(), "torn"), ("consumed", adv.consumed(), accepted),
            ("retained", reader.retained_sequence(), accepted)]


def _end_behind(adv: Adversary, reader) -> list[Check]:
    # The slot's begin is the new sequence but its end is still the old one (the payload not yet whole).
    accepted = _accepted_baseline(adv, reader)
    adv.write_slot(adv.other_slot(accepted), sequence=accepted + 2, payload=valid_record(2), end=accepted - 2)
    adv.set_latest(accepted + 2)
    return [("result", reader.read(), "torn"), ("consumed", adv.consumed(), accepted),
            ("retained", reader.retained_sequence(), accepted)]


def _writer_died_mid_publish(adv: Adversary, reader) -> list[Check]:
    # D1's worker replacement: the writer stopped with a slot's begin odd and the latest sequence not yet moved; the
    # torn slot is never accepted; a replacement writer continues after the newest whole slot and is accepted.
    accepted = _accepted_baseline(adv, reader)
    adv.write_slot(adv.other_slot(accepted), sequence=accepted + 2, payload=valid_record(2), begin=accepted + 1,
                   end=0)
    first = reader.read()
    replacement = adv.publish(valid_record(3))
    return [("result", first, "nothing"), ("consumed", adv.consumed(), accepted),
            ("replacement", replacement, accepted + 2), ("after", reader.read(), "accepted"),
            ("retained", reader.retained_sequence(), replacement)]


def _duplicate(adv: Adversary, reader) -> list[Check]:
    # The accepted sequence republished with other content: never accepted twice (a head read in between changes
    # nothing; the head_resets_watermark control is the reader that lets it back in).
    accepted = _accepted_baseline(adv, reader)
    adv.write_slot(adv.slot_of(accepted), sequence=accepted, payload=valid_record(2))
    reader.head()
    return [("result", reader.read(), "nothing"), ("payload", reader.retained_payload() == valid_record(1), True),
            ("consumed", adv.consumed(), accepted)]


def _stale(adv: Adversary, reader) -> list[Check]:
    # The latest sequence rewound to an older whole slot: stale, the newer frame kept.
    older = adv.publish(valid_record(1))
    newer = adv.publish(valid_record(2))
    if reader.read() != "accepted":
        raise AssertionError("the newer frame was not accepted")
    adv.set_latest(older)
    return [("result", reader.read(), "stale"), ("consumed", adv.consumed(), newer),
            ("retained", reader.retained_sequence(), newer)]


def bad_slot(cause: str) -> tuple[int, int, bytes]:
    """(payload_schema, slot mode code, payload) of one head refusal on a native stream (the Python half's table,
    ``tests/test_visualizer_engine_native_schema.py``)."""
    from core.visualizer_engine import frame_codec, native_schema
    from core.visualizer_engine import spectrum_native_schema as spectrum
    from core.visualizer_engine.packet_abi import MODE_CODES

    good, size = spectrum.SCHEMA_ID, spectrum.LAYOUT.size
    return {
        "reserved schema": (2, 1, bytes(size)),
        "malformed schema": (good | 0x01000000, 1, bytes(size)),
        "unknown mode code": (good, 200, bytes(size)),
        "mode disagrees": (good, MODE_CODES["oscilloscope"], bytes(size)),
        "mode without a schema": (native_schema.native_schema_id(MODE_CODES["oscilloscope"], 1),
                                  MODE_CODES["oscilloscope"], bytes(size)),
        "newer version": (native_schema.native_schema_id(1, spectrum.VERSION + 1), 1, bytes(size)),
        "short record": (good, 1, bytes(size - 16)),
        "record plus 16 bytes": (good, 1, valid_record(1) + bytes(16)),
        "codec payload": (frame_codec.CODEC_SCHEMA, 1, frame_codec.encode((1, 1, 0.0, None))),
    }[cause]


HEAD_REFUSALS = {
    "reserved schema": "schema", "malformed schema": "schema", "unknown mode code": "mode", "mode disagrees": "mode",
    "mode without a schema": "schema", "newer version": "version", "short record": "size",
    "record plus 16 bytes": "size", "codec payload": "schema",
}


def _refusal_checks(adv: Adversary, reader, result: str, cause: str) -> list[Check]:
    # A refusal: counted with its cause, never acknowledged, and the stream stays failed whatever follows.
    consumed = adv.consumed()
    adv.publish(valid_record(1))
    after = reader.read()
    return [("result", result, "refused"), ("cause", reader.refusal_cause(), cause), ("consumed", consumed, 0),
            ("after", after, "failed"), ("consumed after", adv.consumed(), 0),
            ("retained", reader.retained_sequence(), None)]


def _head_refusal(name: str) -> Callable[[Adversary, Any], list[Check]]:
    def run(adv: Adversary, reader) -> list[Check]:
        schema, mode, payload = bad_slot(name)
        adv.publish(payload, schema=schema, mode=mode)
        return _refusal_checks(adv, reader, reader.read(), HEAD_REFUSALS[name])
    return run


def _oversize(adv: Adversary, reader) -> list[Check]:
    # The slot's payload_bytes beyond the slot (the seqlock whole): refused by its head before any copy.
    sequence = adv.publish(valid_record(1))
    adv.set_payload_bytes(sequence, 1 << 20)
    return _refusal_checks(adv, reader, reader.read(), "size")


def record_breaks() -> dict[str, tuple[int, int, str]]:
    """name -> (offset, u32 written, cause): one break per kind of the record's own rule, derived from its table."""
    from core.visualizer_engine import native_schema
    from core.visualizer_engine import spectrum_native_schema as spectrum

    breaks: dict[str, tuple[int, int, str]] = {}
    for name, kind, limit in spectrum.FIELD_CHECKS:
        label = f"{kind} rule ({name})"
        if any(key.startswith(kind) for key in breaks):
            continue
        offset = spectrum.LAYOUT.field(name).offset
        breaks[label] = (offset, {"at_most": limit + 1, "boolean": 2, "enum": limit}[kind], "record")
    breaks["record names another schema"] = (0, native_schema.native_schema_id(1, spectrum.VERSION + 1), "schema")
    return breaks


def _record_break(name: str) -> Callable[[Adversary, Any], list[Check]]:
    def run(adv: Adversary, reader) -> list[Check]:
        offset, value, cause = record_breaks()[name]
        record = bytearray(valid_record(1))
        struct.pack_into("<I", record, offset, value)
        adv.publish(bytes(record))
        return _refusal_checks(adv, reader, reader.read(), cause)
    return run


EXPECTED_IDENTITY = {"runtime_generation": IDENTITY[0], "engine_generation": IDENTITY[1],
                     "activation_id": IDENTITY[2], "mode_code": 1}


def _foreign(adv: Adversary, reader) -> list[Check]:
    # D2's accept edge: a slot of another engine generation is not this stream's frame (not accepted, not
    # acknowledged); the stream's own next frame is.
    adv.publish(valid_record(1), identity=(IDENTITY[0], IDENTITY[1] + 1, IDENTITY[2]))
    first = reader.read()
    consumed = adv.consumed()
    own = adv.publish(valid_record(2))
    return [("result", first, "foreign"), ("consumed", consumed, 0), ("after", reader.read(), "accepted"),
            ("retained", reader.retained_sequence(), own)]


def cases() -> list[Case]:
    table = [
        Case("a whole slot is accepted and acknowledged", _whole, naive_fails=False),
        Case("torn: the latest sequence is odd", _latest_odd, ("skip_seqlock",)),
        Case("torn: the slot's end is behind its begin", _end_behind, ("skip_seqlock",)),
        Case("torn: the writer died mid-publish, then a replacement", _writer_died_mid_publish),
        Case("duplicate: the accepted sequence republished", _duplicate, ("head_resets_watermark",)),
        Case("stale: the latest sequence rewound", _stale, ("accept_unordered",)),
        Case("oversize: payload_bytes beyond the slot", _oversize, ("skip_head_check", "acknowledge_refused")),
        Case("identity: another engine generation's slot", _foreign, ("skip_identity",), reference=False,
             expect=EXPECTED_IDENTITY),
    ]
    for name in HEAD_REFUSALS:
        table.append(Case(f"refused at the head: {name}", _head_refusal(name),
                          ("skip_head_check", "acknowledge_refused")))
    for name in record_breaks():
        table.append(Case(f"refused record: {name}", _record_break(name), ("skip_head_check", "acknowledge_refused")))
    return table


@dataclass
class CaseResult:
    case: str
    reader: str
    control: str | None
    checks: list = field(default_factory=list)

    @property
    def held(self) -> bool:
        return all(observed == expected for _label, observed, expected in self.checks)

    def failures(self) -> list[str]:
        return [f"{label}: {observed!r} != {expected!r}" for label, observed, expected in self.checks
                if observed != expected]


def run_case(case: Case, make_reader: Callable[[str, Case], Any], *, reader_name: str,
             control: str | None = None) -> CaseResult:
    """One case on a fresh mapping: ``make_reader(mapping_name, case)`` gives the reader (closed here)."""
    memory = create_mapping()
    adv = Adversary(memory.name)
    reader = make_reader(memory.name, case)
    result = CaseResult(case.name, reader_name, control)
    try:
        result.checks = [(label, observed, expected) for label, observed, expected in case.run(adv, reader)]
    except AssertionError as exc:
        result.checks = [("setup", str(exc), "ok")]
    finally:
        reader.close()
        adv.close()
        memory.close()
        memory.unlink()
    return result


def run_reference_table() -> dict:
    """Every case the reference applies to, on the reference reader and on its naive negative control."""
    rows = []
    for case in cases():
        if not case.reference:
            continue
        held = run_case(case, lambda name, _case: ReferenceReader(name), reader_name="reference")
        naive = run_case(case, lambda name, _case: ReferenceReader(name, naive=True), reader_name="naive",
                         control="naive")
        rows.append({"case": case.name, "held": held.held, "failures": held.failures(),
                     "naive_fails": case.naive_fails, "naive_failed": not naive.held})
    passed = all(row["held"] and (row["naive_failed"] or not row["naive_fails"]) for row in rows)
    return {"reader": "reference", "pass": passed, "cases": rows}


def run_native_table(core: Any) -> dict:
    """Every case on the C++ reader, and each case again under each of its negative controls (which must fail it)."""
    rows = []
    for case in cases():
        def make(name: str, case_: Case, controls: tuple = ()) -> NativeReader:
            return NativeReader(core, name, expect=case_.expect, controls=controls)

        held = run_case(case, make, reader_name="native")
        controls = {}
        for control in case.controls:
            seen = run_case(case, lambda name, case_, c=control: make(name, case_, (c,)), reader_name="native",
                            control=control)
            controls[control] = {"failed": not seen.held, "failures": seen.failures()}
        rows.append({"case": case.name, "held": held.held, "failures": held.failures(), "controls": controls})
    passed = all(row["held"] and all(c["failed"] for c in row["controls"].values()) for row in rows)
    return {"reader": "native", "pass": passed, "cases": rows,
            "live_after": core.packet_reader_live()}


# ----------------------------------------------------------------------------------- the in-place writer

def inplace_writer(name: str, records: tuple[bytes, bytes], schema: int, started: Any, stop: Any, written: Any,
                   chunks: int = 8) -> None:
    """A separate process: rewrites the slot the latest sequence names, in place, with the next sequence, the payload
    in ``chunks`` pieces (the window in which a copy sees half of each variant), until ``stop`` is set (``started`` is
    set after its first rewrite). The torn-copy adversary: a correct writer never writes the newest slot, so only a
    reader's seqlock stands between a copy and a mixed record."""
    memory = SharedMemory(name=name)
    view = memory.buf
    try:
        slot_bytes = struct.unpack_from("<I", view, 24)[0]
        sequence = _U64.unpack_from(view, _LATEST)[0]
        slot = 0
        for candidate in range(3):
            if _U64.unpack_from(view, _HEADER_BYTES + candidate * slot_bytes)[0] == sequence:
                slot = candidate
        base = _HEADER_BYTES + slot * slot_bytes
        size = len(records[0])
        step = -(-size // chunks)
        count = 0
        while not stop.is_set():
            record = records[count % 2]
            sequence += 2
            _U64.pack_into(view, base, sequence - 1)
            _SLOT_HEAD.pack_into(view, base, sequence - 1, size, schema, 1.0, float("nan"), 0, 0, *IDENTITY, 1, 0)
            for start in range(0, size, step):
                view[base + 64 + start:base + 64 + min(size, start + step)] = record[start:start + step]
            _U64.pack_into(view, base, sequence)
            _U64.pack_into(view, base + slot_bytes - 8, sequence)
            _U64.pack_into(view, _LATEST, sequence)
            count += 1
            if count == 1:
                started.set()
        written.value = count
    finally:
        view = None
        memory.close()


def stress(make_reader: Callable[[str], Any], *, reads: int = 200_000, stop_on_mixed: bool = False) -> dict:
    """The in-place writer races ``reads`` reads of one reader; every accepted record must be one variant whole.
    ``stop_on_mixed`` (a negative control's run): stop at the first mixed record, ``reads`` then being the cap (a C++
    copy is short, so a reader without its seqlock is caught mixing only a few times in 10^5 reads: build round 1 saw
    4 in 200,000)."""
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    memory = create_mapping()
    adv = Adversary(memory.name)
    records = (valid_record(1), valid_record(2))
    adv.publish(records[0])
    reader = make_reader(memory.name)
    started, stop, written = context.Event(), context.Event(), context.Value("q", 0)
    process = context.Process(target=inplace_writer,
                              args=(memory.name, records, spectrum_schema_id(), started, stop, written), daemon=True)
    accepted = mixed = done = 0
    results: dict[str, int] = {}
    try:
        process.start()
        # The writer's first rewrite is the edge the race starts at (a blocking wait on its event, bounded).
        if not started.wait(60):
            raise RuntimeError("the in-place writer never started")
        for _ in range(reads):
            done += 1
            result = reader.read()
            results[result] = results.get(result, 0) + 1
            if result == "accepted":
                accepted += 1
                fields = reader.retained_fields()
                if fields is None or not record_is_consistent(dict(fields)):
                    mixed += 1
                    if stop_on_mixed:
                        break
            elif result in ("refused", "failed"):
                break
    finally:
        stop.set()
        process.join(30)
        torn = reader.torn_reads()
        reader.close()
        adv.close()
        memory.close()
        memory.unlink()
    return {"reads": done, "read_cap": reads, "results": results, "accepted": accepted, "mixed": mixed, "torn_reads": torn,
            "writes": int(written.value), "writer_exit": process.exitcode}


__all__ = ["Adversary", "Case", "CaseResult", "EXPECTED_IDENTITY", "HEAD_REFUSALS", "IDENTITY", "NativeReader",
           "ReferenceReader", "SLOT_BYTES", "bad_slot", "cases", "create_mapping", "inplace_writer", "record_breaks",
           "record_is_consistent", "run_case", "run_native_table", "run_reference_table", "stress", "valid_record"]
