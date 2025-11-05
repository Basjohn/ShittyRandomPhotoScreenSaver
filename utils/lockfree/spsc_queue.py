"""
SPSCQueue: A bounded Single-Producer/Single-Consumer ring buffer.

Design notes:
- Strict SPSC usage: exactly one producer thread and one consumer thread.
- No locks: relies on CPython GIL for atomic pointer updates and ref assignments.
- Bounded capacity: try_push returns False when full; try_pop returns (False, None) when empty.
"""
from __future__ import annotations
from typing import Generic, Optional, Tuple, TypeVar, List

T = TypeVar("T")


class SPSCQueue(Generic[T]):
    def __init__(self, capacity: int):
        if capacity <= 1:
            raise ValueError("capacity must be > 1")
        self._cap = int(capacity)
        self._buf: List[Optional[T]] = [None] * self._cap
        self._head = 0  # next slot to read
        self._tail = 0  # next slot to write

    def _next(self, idx: int) -> int:
        n = idx + 1
        if n == self._cap:
            n = 0
        return n

    def clear(self) -> None:
        # Safe under SPSC: only producer should clear when consumer quiesced.
        self._buf = [None] * self._cap
        self._head = 0
        self._tail = 0

    def is_empty(self) -> bool:
        return self._head == self._tail

    def is_full(self) -> bool:
        return self._next(self._tail) == self._head

    def size(self) -> int:
        t = self._tail
        h = self._head
        if t >= h:
            return t - h
        return self._cap - (h - t)

    def try_push(self, item: T) -> bool:
        nxt = self._next(self._tail)
        if nxt == self._head:
            return False  # full
        self._buf[self._tail] = item
        self._tail = nxt
        return True

    def try_pop(self) -> Tuple[bool, Optional[T]]:
        if self._head == self._tail:
            return False, None
        item = self._buf[self._head]
        self._buf[self._head] = None  # help GC
        self._head = self._next(self._head)
        return True, item

    def push_drop_oldest(self, item: T) -> None:
        """Push with drop-oldest policy if full (coalescing use-cases)."""
        if not self.try_push(item):
            # drop one
            _ok, _ = self.try_pop()
            # retry once; if still full, overwrite current tail slot
            if not self.try_push(item):
                self._buf[self._tail] = item
                self._tail = self._next(self._tail)
