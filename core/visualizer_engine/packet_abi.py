"""Frame packet ABI: one versioned, C-readable triple buffer of visualizer frames in shared memory.

Native core P2 (``Docs/Future_Work/Native_Core_P2_Engine_Design.md``). The engine worker writes each logical frame's
encoded payload into one of three slots; the main process (and in P3 the native render core, without Python) reads the
newest whole slot at sync. Newest state only, never a queue and never catch-up replay (the snapshot bridge's own rule):
a reader that misses frames simply takes the newest.

Layout (little-endian, every field fixed width; 16-byte aligned blocks):

header (HEADER_BYTES):
    0  4s  magic b'SRVZ'          4  u16 abi_version     6  u16 header_bytes
    8  u32 runtime_generation    12  u32 engine_generation   16 u32 activation_id
   20  u32 slot_count           24  u32 slot_bytes          28 u32 mode_code
   32  u64 latest_sequence       (written by the writer last, after the slot is whole)
   40  u64 consumed_sequence     (written by the reader: the newest sequence it accepted)
   48  u64 rejected_payload_bytes (writer: 0 until a terminal capacity violation, before wake-pipe EOF)
slot i at HEADER_BYTES + i * slot_bytes:
    0  u64 sequence_begin        (seqlock: odd while the writer fills the slot)
    8  u32 payload_bytes         12 u32 payload_schema (1: the tagged Python codec; a native fixed-layout schema:
                                    ``native_schema``; checked at the head by a reader given ``admit``)
   16  f64 logical_timestamp     24 f64 source_timestamp (NaN: none)
   32  u32 flags (FLAG_*)        36 u32 protected_edge_mask
   40  u32 runtime_generation    44 u32 engine_generation    48 u32 activation_id   52 u32 mode_code
   56  u64 publish_ns            (the writer's ``time.perf_counter_ns()`` at publish; 0: not stamped)
   64  payload ...               (at most slot_bytes - SLOT_OVERHEAD bytes)
  slot_bytes - 8  u64 sequence_end  (equal to sequence_begin, and even, once the slot is whole)

Sequences start at 2 and grow by 2 per frame; a slot whose begin is odd, or whose begin and end differ, is torn and
is never accepted. Protected edges (one bit per edge kind) survive frames the reader skipped: each slot carries the OR
of every edge published after the reader's ``consumed_sequence``, so an edge stays visible until a read acknowledges
it, within one identity: an edge is carried only into later slots of its own identity, so a new activation's slot
never carries an edge produced under the previous one. Ordering (a seqlock): the writer stores ``sequence_begin`` odd
in a store of its own (an aligned 8-byte store that precedes every other head store: the P3 C reader relies on it),
then the rest of the slot head (identity included), the payload, ``sequence_begin`` even, ``sequence_end``, then ``latest_sequence``. The reader loads in the opposite order: the word
the writer stores last first (``sequence_end``), then the head and payload, then ``sequence_begin`` again, and
accepts only if both equal ``latest`` and are even, so a write that starts while the payload is copied always shows in
the final ``sequence_begin``. CPython stores to the mapping in program order and x86 keeps store order; the P3 C
reader acquire-loads ``latest_sequence`` and ``sequence_end``, copies, then loads ``sequence_begin`` after a load
fence.

Identity (ABI 2, native core P2b slice 2; audits H5 and A3-M4): every slot carries the identity of the frame in it
(runtime generation, engine generation, activation id, ``mode_code`` from ``MODE_CODES``, 0: none) in its head, so
the slot's seqlock covers it: an in-place mode switch commits a new engine generation, activation and mode, and a
native reader validates each slot it accepts against what it expects, without Python. The header's identity fields
are the configure-time identity (written once by the session before any frame: which runtime generation and mode the
mapping was configured for); they are not updated in place and never decide a slot. Identity values are u32; -1
("none") is stored as 0xFFFFFFFF. ``flags`` carry the publication's ``FLAG_*`` bits on every slot. ABI 1 had no slot
identity (payload at 48); ABI 2 moved the payload to 64.

Publish time (native core P2 gate 3 preparation, appended to ABI 2): slot bytes 56-63, until then the zero padding
before the payload, hold ``publish_ns``, the writer's ``time.perf_counter_ns()`` at publish, under the slot's seqlock
like every head field. An append into reserved bytes, not a renumbering: no field moved, the payload stays at 64, a
reader that ignores the field is unaffected, and 0 (what ``initialise`` leaves and what an unstamped writer stores)
means "not stamped", so the ABI version stays 2. The clock is ``perf_counter`` because it is the one clock every SRPSS
process shares: on Windows it is QueryPerformanceCounter, system-wide and monotonic, with no per-process origin (the
authored clock and ``--frame-trace`` read it too), so a stamp made in the engine worker is directly comparable with the
main process's own trace timestamps (``tests/test_visualizer_engine_publish_stamp.py`` proves it across a spawn). The
engine worker stamps only while the main process's ``--frame-trace`` is admitted (``PacketMailbox``'s
``publish_stamps``); otherwise the field is written 0 in the same store as the rest of the head.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from typing import Callable

MAGIC = b"SRVZ"
ABI_VERSION = 2
HEADER_BYTES = 64
SLOT_COUNT = 3
SLOT_PAYLOAD_OFFSET = 64
SLOT_OVERHEAD = SLOT_PAYLOAD_OFFSET+8      # header fields before the payload and sequence_end after it
FRAME_MAPPING_PREFIX = "srpss_viz_"
FIRST_SEQUENCE = 2

FLAG_CHANGED, FLAG_PRESENT_FRAME, FLAG_MODE_REVEAL_READY, FLAG_PLAYING = 1, 2, 4, 8
#: The frame's reactive source is its own activation's (``render_contract.snapshot_has_current_reactive_source``):
#: with ``FLAG_PRESENT_FRAME`` and ``FLAG_PLAYING`` it is what a native renderer's admission reads (N2.5), the node's
#: ``snapshot_is_render_admissible`` without the frame. A bit appended to ``flags``: no field moved, the ABI stays 2.
FLAG_SOURCE_CURRENT = 16

#: The header's ``mode_code``: one stable number per canonical mode id, append-only (a code is never reused or
#: renumbered; a new mode takes the next one). 0 means no mode. C readers carry the same table.
MODE_CODES = {
    "spectrum": 1,
    "oscilloscope": 2,
    "bubble": 3,
    "devcurve": 4,
    "sphere": 5,
    "extruded_spectrum": 6,
    "shockwave_grid": 7,
    "extruded_bubble": 8,
    "waveform_ribbon": 9,
}


def mode_code(mode_id: str | None) -> int:
    """The header code of ``mode_id`` (0 for none); an unknown mode fails closed (``KeyError``)."""
    if not mode_id:
        return 0
    return MODE_CODES[str(mode_id)]


_HEADER = struct.Struct("<4sHHIIIIIIQQ")          # through consumed_sequence (48 bytes, padded to 64)
_SLOT_HEAD = struct.Struct("<QIIddIIIIIIQ")       # through publish_ns (64 bytes, payload at 64)
_SLOT_HEAD_REST = struct.Struct("<IIddIIIIIIQ")   # the slot head after sequence_begin (stored at offset 8)
_U64 = struct.Struct("<Q")
_IDENTITY = struct.Struct("<III")                 # runtime_generation, engine_generation, activation_id at 8
_U32 = struct.Struct("<I")
_IDENTITY_OFFSET, _MODE_CODE_OFFSET = 8, 28
_LATEST_OFFSET, _CONSUMED_OFFSET = 32, 40
_REJECTED_PAYLOAD_OFFSET = 48  # reserved ABI 2 bytes; zero-neutral append, existing offsets/layout unchanged


def _u32(value: int) -> int:
    value = int(value)
    if value < -1 or value > 0xFFFFFFFF:
        raise ValueError(f"header identity {value} does not fit a u32")
    return value & 0xFFFFFFFF
assert _HEADER.size <= HEADER_BYTES and _SLOT_HEAD.size <= SLOT_PAYLOAD_OFFSET
assert _U64.size + _SLOT_HEAD_REST.size == _SLOT_HEAD.size


class PacketAbiError(ValueError):
    """The mapping is not a frame buffer this build can read (magic, version or shape)."""


class FrameCapacityError(ValueError):
    """The published frame violated its activation-time capacity envelope; retry cannot make it fit."""


@dataclass(frozen=True)
class FramePacket:
    """One whole frame read from a slot."""

    sequence: int
    payload_schema: int
    logical_timestamp: float
    source_timestamp: float | None
    flags: int
    protected_edge_mask: int
    payload: bytes
    runtime_generation: int = 0          # the slot's identity (u32 as stored; 0xFFFFFFFF: -1)
    engine_generation: int = 0
    activation_id: int = 0
    mode_code: int = 0
    publish_ns: int = 0                  # the writer's perf_counter_ns at publish (0: not stamped)


def mapping_bytes(slot_bytes: int) -> int:
    return HEADER_BYTES+SLOT_COUNT*int(slot_bytes)


def _slot_shape(slot_bytes: int) -> int:
    slot_bytes = int(slot_bytes)
    if slot_bytes < SLOT_OVERHEAD+16 or slot_bytes % 16:
        raise ValueError("slot_bytes must be a multiple of 16 with room for a payload")
    return slot_bytes


def initialise(buffer, *, slot_bytes: int, runtime_generation: int, engine_generation: int, activation_id: int,
               mode_code: int) -> None:
    """Write a fresh header into ``buffer`` (the owner does this once, before the writer attaches)."""
    slot_bytes = _slot_shape(slot_bytes)
    view = memoryview(buffer)
    if len(view) < mapping_bytes(slot_bytes):
        raise ValueError("buffer is smaller than the frame mapping")
    view[:mapping_bytes(slot_bytes)] = bytes(mapping_bytes(slot_bytes))
    _HEADER.pack_into(view, 0, MAGIC, ABI_VERSION, HEADER_BYTES, int(runtime_generation), int(engine_generation),
                      int(activation_id), SLOT_COUNT, slot_bytes, int(mode_code), 0, 0)


def _validate(view) -> tuple[int, ...]:
    if len(view) < HEADER_BYTES:
        raise PacketAbiError("mapping is smaller than the frame header")
    fields = _HEADER.unpack_from(view, 0)
    magic, version, header_bytes, _rg, _eg, _aid, slot_count, slot_bytes, _mode, _latest, _consumed = fields
    if magic != MAGIC:
        raise PacketAbiError("not a visualizer frame mapping")
    if version != ABI_VERSION or header_bytes != HEADER_BYTES or slot_count != SLOT_COUNT:
        raise PacketAbiError(f"frame ABI {version} (header {header_bytes}, {slot_count} slots) is not this build's "
                             f"{ABI_VERSION}")
    _slot_shape(slot_bytes)
    if len(view) < mapping_bytes(slot_bytes):
        raise PacketAbiError("mapping is smaller than its declared slots")
    return fields


class FramePacketWriter:
    """The engine side: publishes whole frames, never blocking on the reader."""

    def __init__(self, buffer) -> None:
        self._view = memoryview(buffer)
        fields = _validate(self._view)
        self._slot_bytes = fields[7]
        self.capacity = self._slot_bytes-SLOT_OVERHEAD
        self._sequence = max(int(fields[9]), FIRST_SEQUENCE-2)
        # A re-attached writer continues after the newest slot (never overwrites the one a reader may be copying).
        self._latest_slot = next((slot for slot in range(SLOT_COUNT)
                                  if fields[9] and _U64.unpack_from(self._view, HEADER_BYTES+slot*self._slot_bytes)[0]
                                  == fields[9]), -1)
        # (sequence, edges, identity) published after the reader's last consume; an edge is carried only into slots
        # of its own identity (checkpoint audit 4, A4-M4: a new activation's slot never carries an old one's edge).
        self._edges: list[tuple[int, int, tuple[int, int, int, int]]] = []

    def publish(self, payload: bytes, *, payload_schema: int, logical_timestamp: float,
                source_timestamp: float | None = None, flags: int = 0, protected_edges: int = 0,
                runtime_generation: int = 0, engine_generation: int = 0, activation_id: int = 0,
                mode_code: int = 0, publish_ns: int = 0) -> int:
        """Publish one whole frame; its sequence. ``publish_ns``: the publish time on ``time.perf_counter_ns`` (the
        module docstring's shared clock), 0 when the caller does not stamp it."""
        payload = bytes(payload)
        publish_ns = int(publish_ns)
        if not 0 <= publish_ns <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"publish time {publish_ns} does not fit a u64")
        if len(payload) > self.capacity:
            # One aligned native u64 store, before EOF on the existing wake pipe; x86 store order is the ABI's
            # existing target. No slot or latest sequence changes. Zero remains neutral for older/native readers.
            _U64.pack_into(self._view, _REJECTED_PAYLOAD_OFFSET, len(payload))
            raise FrameCapacityError(f"frame payload of {len(payload)} bytes exceeds the slot's {self.capacity}")
        identity = (_u32(runtime_generation), _u32(engine_generation), _u32(activation_id), _u32(mode_code))
        consumed = _U64.unpack_from(self._view, _CONSUMED_OFFSET)[0]
        self._edges = [entry for entry in self._edges if entry[0] > consumed and entry[2] == identity]
        sequence = self._sequence+2
        mask = int(protected_edges)
        for _seq, edges, _identity in self._edges:
            mask |= edges
        slot = (self._latest_slot+1) % SLOT_COUNT      # never the newest slot a reader may be copying
        base = HEADER_BYTES+slot*self._slot_bytes
        view = self._view
        # sequence_begin odd first, in its own store (torn until sequence_end matches), then the rest of the head:
        # no head field, the identity included, can become visible before the begin change (A4-L1).
        _U64.pack_into(view, base, sequence-1)
        _SLOT_HEAD_REST.pack_into(view, base+_U64.size, len(payload), int(payload_schema), float(logical_timestamp),
                                  math.nan if source_timestamp is None else float(source_timestamp), int(flags), mask,
                                  *identity, publish_ns)
        view[base+SLOT_PAYLOAD_OFFSET:base+SLOT_PAYLOAD_OFFSET+len(payload)] = payload
        _U64.pack_into(view, base, sequence)
        _U64.pack_into(view, base+self._slot_bytes-8, sequence)
        _U64.pack_into(view, _LATEST_OFFSET, sequence)
        self._sequence, self._latest_slot = sequence, slot
        if protected_edges:
            self._edges.append((sequence, int(protected_edges), identity))
        return sequence

    def write_identity(self, *, runtime_generation: int, engine_generation: int, activation_id: int,
                       mode_code: int) -> None:
        """The header's configure-time identity (module docstring): written once, before any frame."""
        _IDENTITY.pack_into(self._view, _IDENTITY_OFFSET, _u32(runtime_generation), _u32(engine_generation),
                            _u32(activation_id))
        _U32.pack_into(self._view, _MODE_CODE_OFFSET, _u32(mode_code))

    def drop_pending_edges(self) -> None:
        """Forget every edge not yet acknowledged, so no later slot carries one (the producer cleared its unread
        frame). Slots already published are untouched: a written slot is the reader's (it never changes under it)."""
        self._edges = []

    @property
    def consumed_sequence(self) -> int:
        """The newest sequence the reader has acknowledged (0: none yet)."""
        return _U64.unpack_from(self._view, _CONSUMED_OFFSET)[0]

    def release(self) -> None:
        self._view.release()


class FramePacketReader:
    """The main-process side: copies the newest whole frame at sync and acknowledges what it accepted.

    ``admit`` (native core N2.3, transport rule 5): ``admit(payload_schema, mode_code, payload_bytes)`` runs on the
    newest slot's head, after the head's seqlock check and before any payload byte is copied, and raises a
    ``PacketAbiError`` (``native_schema.PayloadRefused``) to refuse the slot. A refused slot is counted
    (``refused``), never accepted and never acknowledged, the refusal is raised to the caller, and the reader is
    failed from then on (``refusal``: it reads nothing more, the stream reports failed). None: no head check."""

    def __init__(self, buffer, *, admit: Callable[[int, int, int], None] | None = None,
                 expect: tuple[int, int, int, int] | None = None) -> None:
        self._view = memoryview(buffer)
        fields = _validate(self._view)
        self._slot_bytes = fields[7]
        self.identity = (fields[3], fields[4], fields[5])     # at attach: runtime/engine generation, activation id
        self.mode_code = fields[8]
        self.accepted = 0
        self.torn_reads = 0
        self._admit = admit
        self.refused = 0
        self.refusal: PacketAbiError | None = None
        # The stream's expected slot identity (runtime generation, engine generation, activation id, mode code, as
        # stored: u32) or None. A whole slot of another identity is not this stream's frame: counted foreign (once per
        # sequence), never accepted, and decided BEFORE its schema is checked, so a stale slot never fails the stream
        # (lead, 14 Nov; the C++ reader's order too).
        self._expect = None if expect is None else tuple(_u32(value) for value in expect)
        self.foreign = 0
        self._last_foreign = 0

    def read_identity(self) -> tuple[int, int, int, int]:
        """The header's configure-time identity: (runtime generation, engine generation, activation id, mode code)."""
        return (*_IDENTITY.unpack_from(self._view, _IDENTITY_OFFSET), _U32.unpack_from(self._view, _MODE_CODE_OFFSET)[0])

    @property
    def capacity_failure(self) -> dict | None:
        actual = _U64.unpack_from(self._view, _REJECTED_PAYLOAD_OFFSET)[0]
        return ({'actual_bytes': actual, 'capacity_bytes': self._slot_bytes-SLOT_OVERHEAD}
                if actual else None)

    def read_latest(self) -> FramePacket | None:
        """The newest whole frame newer than the last accepted one, or None (nothing new, or torn: keep the previous
        frame). A torn read is counted, never retried in a loop: the next sync reads again."""
        if self.refusal is not None:
            return None                       # a refused stream is failed: nothing after the refusal is read
        view = self._view
        latest = _U64.unpack_from(view, _LATEST_OFFSET)[0]
        if latest <= self.accepted:
            return None
        for slot in range(SLOT_COUNT):
            base = HEADER_BYTES+slot*self._slot_bytes
            if _U64.unpack_from(view, base)[0] != latest:
                continue
            # Seqlock read order: sequence_end (stored last) first, then head and payload, then sequence_begin
            # (stored first) again; a write begun during the copy has made sequence_begin odd or newer by then.
            end = _U64.unpack_from(view, base+self._slot_bytes-8)[0]
            if end != latest:
                break
            # ``identity_and_stamp``: the slot's four identity fields, then publish_ns (FramePacket's last fields).
            head, size, schema, logical, source, flags, edges, *identity_and_stamp = _SLOT_HEAD.unpack_from(view, base)
            if self._expect is not None:
                if head != latest or _U64.unpack_from(view, base)[0] != latest or latest % 2:
                    break
                if tuple(identity_and_stamp[:4]) != self._expect:
                    if latest != self._last_foreign:
                        self.foreign += 1
                        self._last_foreign = latest
                    return None
            if self._admit is not None:
                # The head alone, whole under its seqlock, decides admission before any payload byte is copied.
                if head != latest or _U64.unpack_from(view, base)[0] != latest or latest % 2:
                    break
                try:
                    self._admit(schema, identity_and_stamp[3], size)
                except PacketAbiError as refusal:
                    self.refused += 1
                    self.refusal = refusal
                    refusal.sequence = latest         # which slot was refused (it is never acknowledged)
                    raise
            payload =bytes(view[base+SLOT_PAYLOAD_OFFSET:base+SLOT_PAYLOAD_OFFSET+min(size, self._slot_bytes-SLOT_OVERHEAD)])
            begin = _U64.unpack_from(view, base)[0]
            if head != latest or begin != latest or latest % 2 or size > self._slot_bytes-SLOT_OVERHEAD:
                break
            self.accepted = latest
            return FramePacket(latest, schema, logical, None if math.isnan(source) else source, flags, edges, payload,
                               *identity_and_stamp)
        self.torn_reads += 1
        return None

    def has_unread(self) -> bool:
        """Whether a frame newer than the last accepted one has been published (no copy, nothing accepted); never
        after a refusal (the stream failed)."""
        return self.refusal is None and _U64.unpack_from(self._view, _LATEST_OFFSET)[0] > self.accepted

    def acknowledge(self, sequence: int) -> None:
        """Mark protected edges up to ``sequence`` as delivered (they stop being carried into later slots)."""
        _U64.pack_into(self._view, _CONSUMED_OFFSET, int(sequence))

    def release(self) -> None:
        self._view.release()


def create_frame_mapping(*, generation: int, slot_bytes: int, engine_generation: int, activation_id: int,
                         mode_code: int, token: str) -> SharedMemory:
    """The owner (main process) creates, initialises, holds and finally unlinks the generation's mapping; the worker
    opens it by name. ``token`` keeps names unique per process run."""
    slot_bytes = _slot_shape(slot_bytes)
    memory = SharedMemory(name=f"{FRAME_MAPPING_PREFIX}{token}_{int(generation)}", create=True,
                          size=mapping_bytes(slot_bytes))
    initialise(memory.buf, slot_bytes=slot_bytes, runtime_generation=generation, engine_generation=engine_generation,
               activation_id=activation_id, mode_code=mode_code)
    return memory
