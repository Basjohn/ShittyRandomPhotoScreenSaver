"""Load-time sizing of third-party native thread pools.

numpy's bundled OpenBLAS starts one worker thread per logical CPU when numpy is
imported. On Windows each of those threads commits its own ~32 MB buffer
(``VirtualAlloc(MEM_COMMIT)``) whether or not BLAS is ever used: about 700 MB
of private commit per process on the operator's 24-thread CPU, in the main
process and again in the ImageWorker (R-99). SRPSS's only BLAS use is tiny
vector math in Glass shatter physics, which OpenBLAS never parallelizes, so one
thread costs nothing.

OpenBLAS reads its thread count once, at library load, and only from the
environment; no API releases threads it has already started. This is therefore
the one sanctioned environment write for a third-party load-time setting (the
Qt render-loop bootstrap is the other precedent). It runs before numpy is
imported, and spawned worker processes inherit it.
"""
from __future__ import annotations

import os

OPENBLAS_THREADS = "1"


def configure_native_thread_pools() -> None:
    """Size native BLAS pools before the first numpy import in this process."""

    os.environ["OPENBLAS_NUM_THREADS"] = OPENBLAS_THREADS


__all__ = ["OPENBLAS_THREADS", "configure_native_thread_pools"]
