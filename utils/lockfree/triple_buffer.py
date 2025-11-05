"""
TripleBuffer: Lock-free latest-value exchange for SPSC scenarios.

- Producer publishes values via publish(value) without blocking consumer.
- Consumer reads the most recent complete value via consume_latest().
- Uses three slots with atomic index swaps (under GIL) to avoid locks.

Assumptions:
- Exactly one producer thread and one consumer thread.
- Values are immutable or ownership is transferred (no shared mutation).
"""
from __future__ import annotations
from typing import Generic, Optional, TypeVar, List

T = TypeVar("T")


class TripleBuffer(Generic[T]):
    def __init__(self):
        # Three slots
        self._slots: List[Optional[T]] = [None, None, None]
        self._write = 0
        self._ready = -1
        self._read = -1

    def publish(self, value: T) -> None:
        i = self._write
        self._slots[i] = value
        # Mark this slot as ready
        self._ready = i
        # Advance write to a different slot
        nxt = (i + 1) % 3
        self._write = nxt

    def consume_latest(self) -> Optional[T]:
        r = self._ready
        if r < 0 or r == self._read:
            return None
        val = self._slots[r]
        self._read = r
        return val
