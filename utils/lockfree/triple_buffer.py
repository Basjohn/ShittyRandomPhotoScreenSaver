"""
TripleBuffer: Lock-free latest-value exchange for SPSC scenarios.

- Producer publishes values via publish(value) without blocking consumer.
- Consumer reads the most recent complete value via consume_latest().
- One atomic reference store (under the GIL) carries the newest value together
  with its publication sequence, so no lock is needed.

Freshness is the publication sequence, never a slot identity. The former
three-slot round-robin compared the ready slot index with the last-read index,
so exactly 3 (or 6, ...) publishes between two consumes wrapped back to the
same index and a brand-new value was reported as "nothing new" (R-171: 128-sample
WASAPI callbacks arrive 3-4 per 10 ms burst, which hid ~23% of Spectrum ticks'
fresh audio and made bars stutter).

Assumptions:
- Exactly one producer thread and one consumer thread.
- Values are immutable or ownership is transferred (no shared mutation).
"""
from __future__ import annotations
from typing import Generic, Optional, Tuple, TypeVar

T = TypeVar("T")


class TripleBuffer(Generic[T]):
    def __init__(self):
        # (sequence, value) of the newest publication; replaced as one reference.
        self._latest: Optional[Tuple[int, T]] = None
        # Sequence of the publication the consumer last took (0: none yet).
        self._consumed = 0

    def publish(self, value: T) -> None:
        latest = self._latest
        sequence = 1 if latest is None else latest[0] + 1
        self._latest = (sequence, value)

    @property
    def published(self) -> int:
        """How many values have been published (the newest publication's sequence; 0: none). A read for rigs and
        gates; nothing reads it per frame."""
        latest = self._latest
        return 0 if latest is None else latest[0]

    def consume_latest(self) -> Optional[T]:
        latest = self._latest
        if latest is None or latest[0] == self._consumed:
            return None
        self._consumed = latest[0]
        return latest[1]

    def has_pending(self) -> bool:
        """Check if there's new data that hasn't been consumed yet."""
        latest = self._latest
        return latest is not None and latest[0] != self._consumed
