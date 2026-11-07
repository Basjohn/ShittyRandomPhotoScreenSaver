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
slot i at HEADER_BYTES + i * slot_bytes:
    0  u64 sequence_begin        (seqlock: odd while the writer fills the slot)
    8  u32 payload_bytes         12 u32 payload_schema (the mode codec's own version)
   16  f64 logical_timestamp     24 f64 source_timestamp (NaN: none)
   32  u32 flags                 36 u32 protected_edge_mask
   48  payload ...               (at most slot_bytes - SLOT_OVERHEAD bytes)
  slot_bytes - 8  u64 sequence_end  (equal to sequence_begin, and even, once the slot is whole)

Sequences start at 2 and grow by 2 per frame; a slot whose begin is odd, or whose begin and end differ, is torn and
is never accepted. Protected edges (one bit per edge kind) survive frames the reader skipped: each slot carries the OR
of every edge published after the reader's ``consumed_sequence``, so an edge stays visible until a read acknowledges
it. Ordering: CPython stores to the mapping in program order and x86 keeps store order; the P3 C reader uses acquire
loads of ``sequence_end``/``latest_sequence`` and the writer's release order (begin, payload, end, latest).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory

MAGIC = b"SRVZ"
ABI_VERSION = 1
HEADER_BYTES = 64
SLOT_COUNT = 3
SLOT_PAYLOAD_OFFSET = 48
SLOT_OVERHEAD = SLOT_PAYLOAD_OFFSET+8      # header fields before the payload and sequence_end after it
FRAME_MAPPING_PREFIX = "srpss_viz_"
FIRST_SEQUENCE = 2

FLAG_CHANGED, FLAG_PRESENT_FRAME, FLAG_MODE_REVEAL_READY, FLAG_PLAYING = 1, 2, 4, 8

_HEADER = struct.Struct("<4sHHIIIIIIQQ")          # through consumed_sequence (48 bytes, padded to 64)
_SLOT_HEAD = struct.Struct("<QIIddII")            # through protected_edge_mask (40 bytes, payload at 48)
_U64 = struct.Struct("<Q")
_LATEST_OFFSET, _CONSUMED_OFFSET = 32, 40
assert _HEADER.size <= HEADER_BYTES and _SLOT_HEAD.size <= SLOT_PAYLOAD_OFFSET


class PacketAbiError(ValueError):
    """The mapping is not a frame buffer this build can read (magic, version or shape)."""


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
        self._edges: list[tuple[int, int]] = []    # (sequence, edges) published after the reader's last consume

    def publish(self, payload: bytes, *, payload_schema: int, logical_timestamp: float,
                source_timestamp: float | None = None, flags: int = 0, protected_edges: int = 0) -> int:
        payload = bytes(payload)
        if len(payload) > self.capacity:
            raise ValueError(f"frame payload of {len(payload)} bytes exceeds the slot's {self.capacity}")
        consumed = _U64.unpack_from(self._view, _CONSUMED_OFFSET)[0]
        self._edges = [(seq, edges) for seq, edges in self._edges if seq > consumed]
        sequence = self._sequence+2
        mask = int(protected_edges)
        for _seq, edges in self._edges:
            mask |= edges
        slot = (self._latest_slot+1) % SLOT_COUNT      # never the newest slot a reader may be copying
        base = HEADER_BYTES+slot*self._slot_bytes
        view = self._view
        # sequence_begin odd first (in the same store as the slot head): torn until sequence_end matches.
        _SLOT_HEAD.pack_into(view, base, sequence-1, len(payload), int(payload_schema), float(logical_timestamp),
                             math.nan if source_timestamp is None else float(source_timestamp), int(flags), mask)
        view[base+SLOT_PAYLOAD_OFFSET:base+SLOT_PAYLOAD_OFFSET+len(payload)] = payload
        _U64.pack_into(view, base, sequence)
        _U64.pack_into(view, base+self._slot_bytes-8, sequence)
        _U64.pack_into(view, _LATEST_OFFSET, sequence)
        self._sequence, self._latest_slot = sequence, slot
        if protected_edges:
            self._edges.append((sequence, int(protected_edges)))
        return sequence

    def release(self) -> None:
        self._view.release()


class FramePacketReader:
    """The main-process side: copies the newest whole frame at sync and acknowledges what it accepted."""

    def __init__(self, buffer) -> None:
        self._view = memoryview(buffer)
        fields = _validate(self._view)
        self._slot_bytes = fields[7]
        self.identity = (fields[3], fields[4], fields[5])     # runtime/engine generation, activation id
        self.mode_code = fields[8]
        self.accepted = 0
        self.torn_reads = 0

    def read_latest(self) -> FramePacket | None:
        """The newest whole frame newer than the last accepted one, or None (nothing new, or torn: keep the previous
        frame). A torn read is counted, never retried in a loop: the next sync reads again."""
        view = self._view
        latest = _U64.unpack_from(view, _LATEST_OFFSET)[0]
        if latest <= self.accepted:
            return None
        for slot in range(SLOT_COUNT):
            base = HEADER_BYTES+slot*self._slot_bytes
            if _U64.unpack_from(view, base)[0] != latest:
                continue
            begin, size, schema, logical, source, flags, edges = _SLOT_HEAD.unpack_from(view, base)
            payload = bytes(view[base+SLOT_PAYLOAD_OFFSET:base+SLOT_PAYLOAD_OFFSET+min(size, self._slot_bytes-SLOT_OVERHEAD)])
            end = _U64.unpack_from(view, base+self._slot_bytes-8)[0]
            if begin != latest or end != latest or begin % 2 or size > self._slot_bytes-SLOT_OVERHEAD:
                break
            self.accepted = latest
            return FramePacket(latest, schema, logical, None if math.isnan(source) else source, flags, edges, payload)
        self.torn_reads += 1
        return None

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
