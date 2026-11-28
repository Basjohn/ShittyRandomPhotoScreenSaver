"""The D3 geometry arena's Python side (``native/core/src/geometry_arena.h`` owns the layout; decision D3 in
``Docs/Future_Work/Native_Core_P3_Decisions.md``).

Extruded Bubble's drift geometry travels once per key, never in the native record. Three parties share one arena:

- ``GeometryArenaOwner`` (the main process): creates the named mapping beside the stream's frame mapping
  (``engine_worker_link.configure``), keeps it for the stream's life and unlinks it at the stream's close. It hands
  the name to the worker (``transfer``) and to the core (``NativeMode.geometry_arena``), and answers ``holds`` for the
  native record's projection (``extruded_bubble_native_schema``): a key is named only once its bank is whole.
- ``GeometryArenaWriter`` (the engine worker): attaches by name, stamps its own key namespace into the header (a
  replacement worker is another namespace, so no key of a dead writer ever matches a new one), and from inside
  ``PacketMailbox.publish`` writes a family's new key into a free bank under the bank's seqlock before the slot that
  names it is written. A bank is free once ``consumed_sequence`` acknowledges a frame after the last frame naming its
  key (the successor names another key or none). The bank holding the family's current key is never free, so a rebase's
  predecessor stays whole. When both banks are live the key is not written: the projection keeps the family's last
  named key and epoch (the lineage at its last published revision) until a bank frees.
- The core (``GeometryArena`` in C++) maps it read-only and copies a bank under its sequence.

Layout (little-endian; geometry_arena.h): a 64-byte header (u32 magic 'SRGA', u32 version 1, u32 families, u32 banks
(2), u64 bank bytes, u32 header bytes 64, u32 bank header bytes 64, u64 the writer's key namespace (0: none attached;
the C++ reader ignores it), 24 reserved), then for family f, bank b at ``bank_offset(f, b, bank_bytes)`` a 64-byte bank
header (u32 sequence (odd while written), u32 payload bytes, u64 namespace, u32 engine, u32 activation, u32 family,
u32 capacity, u64 revision, 24 reserved) and ``bank bytes`` of payload.

A key here is the tuple ``(namespace, engine, activation, family, revision, capacity)``, the order the record's eight
u32 words are packed in (``key_words``).
"""
from __future__ import annotations

import logging
import secrets
import struct
import uuid
from collections.abc import Sequence
from multiprocessing.shared_memory import SharedMemory
from typing import Any

logger = logging.getLogger(__name__)

MAGIC = 0x41475253          # "SRGA" little-endian
VERSION = 1
HEADER_BYTES = 64
BANK_HEADER_BYTES = 64
BANKS = 2
MAX_FAMILIES = 8
MAX_BANK_BYTES = 64 << 20

_HEADER = struct.Struct("<IIIIQII")
_WRITER_NAMESPACE = struct.Struct("<Q")
_WRITER_NAMESPACE_AT = 32
_SEQUENCE = struct.Struct("<I")
_BANK_HEAD = struct.Struct("<IIQIIIIQ")      # sequence, payload bytes, ns, engine, activation, family, capacity, rev
_KEY = struct.Struct("<QIIIQI")              # the record's order: ns, engine, activation, family, revision, capacity
_WORDS = struct.Struct("<8I")
_NO_ACK = -1
_U32_MAX = (1 << 32) - 1

Key = tuple[int, int, int, int, int, int]


class GeometryArenaError(RuntimeError):
    """An arena that cannot be made or attached (sizes past the layout's limits, a name that does not open)."""


def bank_offset(family: int, bank: int, bank_bytes: int) -> int:
    return HEADER_BYTES + (family * BANKS + bank) * (BANK_HEADER_BYTES + bank_bytes)


def arena_bytes(families: int, bank_bytes: int) -> int:
    return bank_offset(families, 0, bank_bytes)


def key_words(key: Key) -> tuple[int, ...]:
    """The record's eight u32 words of ``key`` (GeometryKey::fromWords' order)."""
    return _WORDS.unpack(_KEY.pack(*key))


def key_of_words(words: Sequence[int]) -> Key:
    return _KEY.unpack(_WORDS.pack(*words))


def _bank_key(view: memoryview, at: int) -> tuple[int, Key]:
    """(sequence, key) of the bank header at ``at``."""
    sequence, _size, ns, engine, activation, family, capacity, revision = _BANK_HEAD.unpack_from(view, at)
    return sequence, (ns, engine, activation, family, revision, capacity)


def _attach(name: str) -> SharedMemory:
    try:
        return SharedMemory(name=name)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise GeometryArenaError(f"geometry arena {name!r} does not open ({exc})") from exc


def _layout(view: memoryview) -> tuple[int, int]:
    """(families, bank bytes) of a whole arena header, else GeometryArenaError."""
    if len(view) < HEADER_BYTES:
        raise GeometryArenaError("a geometry arena is at least its header")
    magic, version, families, banks, bank_bytes, header, bank_header = _HEADER.unpack_from(view, 0)
    if (magic != MAGIC or version != VERSION or not 0 < families <= MAX_FAMILIES or banks != BANKS
            or not 0 < bank_bytes <= MAX_BANK_BYTES or header != HEADER_BYTES or bank_header != BANK_HEADER_BYTES
            or arena_bytes(families, bank_bytes) > len(view)):
        raise GeometryArenaError(f"not a version {VERSION} geometry arena of its own size")
    return families, bank_bytes


class GeometryArenaOwner:
    """The main process's arena: created whole (every bank empty, sequence 0), kept until ``close`` unlinks it."""

    def __init__(self, *, families: int, bank_bytes: int) -> None:
        bank_bytes = (int(bank_bytes) + 15) // 16 * 16
        if not 0 < families <= MAX_FAMILIES or not 0 < bank_bytes <= MAX_BANK_BYTES:
            raise GeometryArenaError(f"a geometry arena of {families} families and {bank_bytes} bytes a bank is "
                                     f"past the layout's {MAX_FAMILIES} families and {MAX_BANK_BYTES} bytes")
        self._memory: SharedMemory | None = SharedMemory(
            create=True, size=arena_bytes(families, bank_bytes), name=f"srpss_ga_{uuid.uuid4().hex[:16]}")
        _HEADER.pack_into(self._memory.buf, 0, MAGIC, VERSION, families, BANKS, bank_bytes, HEADER_BYTES,
                          BANK_HEADER_BYTES)
        self.name = self._memory.name
        self.families = int(families)
        self.bank_bytes = bank_bytes

    def transfer(self) -> dict:
        """What the worker's configure carries (plain data)."""
        return {"name": self.name}

    @property
    def closed(self) -> bool:
        return self._memory is None

    def writer_namespace(self) -> int:
        """The attached writer's key namespace (0: none yet, or the stream retired)."""
        memory = self._memory
        return 0 if memory is None else _WRITER_NAMESPACE.unpack_from(memory.buf, _WRITER_NAMESPACE_AT)[0]

    def holds(self, key: Key) -> bool:
        """Whether a bank of ``key``'s family holds ``key`` whole (its sequence even and unchanged across the read)."""
        memory = self._memory
        family = int(key[3])
        if memory is None or not 0 <= family < self.families:
            return False
        view = memory.buf
        for bank in range(BANKS):
            at = bank_offset(family, bank, self.bank_bytes)
            before, held = _bank_key(view, at)
            if before & 1 or before == 0 or held != tuple(key):
                continue
            if _SEQUENCE.unpack_from(view, at)[0] == before:
                return True
        return False

    def close(self) -> None:
        """The stream retired: the mapping is closed and unlinked (a writer or core still attached keeps its view)."""
        memory, self._memory = self._memory, None
        if memory is None:
            return
        try:
            memory.close()
        finally:
            try:
                memory.unlink()
            except FileNotFoundError:
                pass


class _Bank:
    __slots__ = ("key", "sequence", "last_named")

    def __init__(self) -> None:
        self.key: Key | None = None
        self.sequence = 0
        self.last_named = _NO_ACK            # the newest published sequence whose frame named this bank's key


class GeometryArenaWriter:
    """The engine worker's side: ``before_publish`` (inside ``PacketMailbox.publish``, before the slot) writes each
    family's new key into a free bank; ``published`` records the sequence of the slot that named them. One producer
    thread (the mailbox's publish), so no lock beyond the mailbox's own."""

    def __init__(self, name: str, *, families: Sequence[str]) -> None:
        self._memory: SharedMemory | None = _attach(name)
        try:
            self._families, self._bank_bytes = _layout(self._memory.buf)
        except BaseException:
            self._memory.close()
            raise
        self._names = {family: index for index, family in enumerate(families)}
        if len(self._names) > self._families:
            self._memory.close()
            raise GeometryArenaError(f"{len(self._names)} families in an arena of {self._families}")
        self.name = name
        # This writer's own key namespace (never 0, never a dead writer's): stamped once, read by the owner's projection.
        self.namespace = secrets.randbits(63) | 1
        _WRITER_NAMESPACE.pack_into(self._memory.buf, _WRITER_NAMESPACE_AT, self.namespace)
        self._banks = {index: (_Bank(), _Bank()) for index in self._names.values()}
        self._named: dict[int, Key] = {}           # family -> the key the newest frame names (its lineage)
        self._pending: dict[int, Key] | None = None
        self._refused: set[Key] = set()            # keys past a bank (logged once)
        self.deferred = 0                          # new keys left unwritten because both banks were live
        self.writes = 0

    def key_for(self, family: str, descriptor: Any, engine_generation: int, activation_id: int) -> Key:
        return (self.namespace, int(engine_generation), int(activation_id), self._names[family],
                int(descriptor.revision), int(descriptor.capacity))

    def before_publish(self, state: Any, consumed_sequence: int) -> None:
        """Write the frame's new keys (seqlock: odd, key and payload, even) before its slot names them. A family with
        no free bank keeps naming its previous key; nothing of this frame raises for a deferral."""
        memory = self._memory
        frame = getattr(state, "mode_state", None)
        families = getattr(frame, "drift_families", None)
        if memory is None or families is None:
            self._pending = None
            return
        engine = int(getattr(state, "engine_generation", 0) or 0)
        activation = int(getattr(state, "activation_id", 0) or 0)
        if not (0 <= engine <= _U32_MAX and 0 <= activation <= _U32_MAX):
            self._pending = None          # an unactivated frame (-1): no key fits; the projection names none either
            return
        named: dict[int, Key] = {}
        for descriptor in families:
            index = self._names.get(descriptor.family)
            if index is None:
                continue
            key = self.key_for(descriptor.family, descriptor, engine, activation)
            banks = self._banks[index]
            if any(bank.key == key and bank.sequence for bank in banks):
                named[index] = key
                continue
            free = self._free_bank(banks, self._named.get(index), consumed_sequence)
            if free is None or key in self._refused:
                self.deferred += free is None
                if index in self._named:
                    named[index] = self._named[index]   # the lineage at its last published key
                continue
            if not self._write(index, free, key, descriptor.geometry):
                continue
            named[index] = key
        self._pending = named

    def published(self, sequence: int) -> None:
        """The slot ``sequence`` named the keys ``before_publish`` chose: each one's bank is live through it."""
        named, self._pending = self._pending, None
        if named is None:
            return
        for index, key in named.items():
            for bank in self._banks[index]:
                if bank.key == key:
                    bank.last_named = int(sequence)
        self._named = named

    def _free_bank(self, banks: tuple[_Bank, _Bank], current: Key | None, consumed: int) -> int | None:
        for number, bank in enumerate(banks):
            if bank.key is None:
                return number
        for number, bank in enumerate(banks):
            # Never the bank of the key the newest frame names (a rebase's predecessor); another is free once the
            # consumer took a frame after the last one naming it.
            if bank.key != current and int(consumed) > bank.last_named:
                return number
        return None

    def _write(self, index: int, number: int, key: Key, payload: bytes) -> bool:
        if len(payload) > self._bank_bytes or len(payload) % 4:
            if key not in self._refused:
                self._refused.add(key)
                logger.warning("[SPOTIFY_VIS][GEOMETRY_ARENA] key %s: %d geometry bytes past the arena's %d a bank; "
                               "the family keeps its previous key", key, len(payload), self._bank_bytes)
            return False
        view = self._memory.buf
        at = bank_offset(index, number, self._bank_bytes)
        bank = self._banks[index][number]
        sequence = _SEQUENCE.unpack_from(view, at)[0]
        _SEQUENCE.pack_into(view, at, (sequence + 1) | 1)            # odd: being written
        start = at + BANK_HEADER_BYTES
        view[start:start + len(payload)] = payload
        ns, engine, activation, family, revision, capacity = key
        _BANK_HEAD.pack_into(view, at, (sequence + 1) | 1, len(payload), ns, engine, activation, family, capacity,
                             revision)
        even = ((sequence + 1) | 1) + 1
        _SEQUENCE.pack_into(view, at, even & 0xFFFFFFFF or 2)       # even, advanced: whole
        bank.key, bank.sequence, bank.last_named = key, even, _NO_ACK
        self.writes += 1
        return True

    def close(self) -> None:
        """The stream retired on the worker's side: the view goes (the owner unlinks the mapping)."""
        memory, self._memory = self._memory, None
        if memory is not None:
            memory.close()


__all__ = ["BANKS", "BANK_HEADER_BYTES", "GeometryArenaError", "GeometryArenaOwner", "GeometryArenaWriter",
           "HEADER_BYTES", "MAGIC", "VERSION", "arena_bytes", "bank_offset", "key_of_words", "key_words"]
