"""
Lock-free primitives for high-frequency cross-thread communication.

Provided primitives (single producer/consumer assumptions):
- SPSCQueue: bounded ring buffer with non-blocking try_push/try_pop.
- TripleBuffer: latest-value exchange without locks.

Note: In CPython, basic integer and reference assignments are atomic under the GIL.
These structures rely on strict SPSC usage to avoid data races without locks.
"""
from .spsc_queue import SPSCQueue
from .triple_buffer import TripleBuffer
