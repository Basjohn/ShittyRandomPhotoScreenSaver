"""RUN-lifetime garbage-collection policy for the Qt Quick architecture.

The legacy ``GCController`` in ``frame_budget.py`` was never wired into the
retained Qt Quick runtime.  It also tried to disable/enable collection around a
notional Python-owned frame, which no longer matches the threaded Qt Quick
scene graph.

This owner deliberately does much less:

* retain CPython's normal automatic young-generation collection;
* reduce how often the expensive deep generations are scanned;
* observe every collection without adding a timer or polling cadence;
* restore the interpreter's original policy when RUN lifetime ends.

No manual ``gc.collect()`` is performed here.  The current evidence shows
40ms-class generation-2 scans frequently collecting zero objects; forcing
those scans at another arbitrary scene boundary would merely move the hitch.
"""
from __future__ import annotations

from dataclasses import dataclass
import gc
import threading
import time
from typing import Any

from core.logging.logger import get_logger, is_perf_metrics_enabled

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GCPolicySnapshot:
    active: bool
    original_thresholds: tuple[int, int, int]
    active_thresholds: tuple[int, int, int]
    collections: tuple[int, int, int]
    collected: tuple[int, int, int]
    duration_ms: tuple[float, float, float]
    duration_max_ms: tuple[float, float, float]


def derive_runtime_thresholds(
    original: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Return a conservative deep-scan policy from the interpreter defaults.

    Reference-counted objects are still reclaimed immediately.  Generation-0
    keeps the interpreter's own cadence; only promotion/deep-scan frequency is
    relaxed.  This specifically targets the observed 30-45ms generation-2
    scans without turning the screensaver into a manual-GC runtime.
    """

    young, middle, full = (max(0, int(v)) for v in original)
    if young <= 0:
        # Preserve a caller that intentionally disabled automatic GC through a
        # zero threshold rather than silently re-enabling it.
        return (young, middle, full)
    return (
        young,
        max(middle, 20),
        max(full, 50),
    )


class RuntimeGCPolicy:
    """Single RUN-lifetime owner of automatic GC threshold policy/telemetry."""

    _WARN_MS = 10.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._original_thresholds = tuple(int(v) for v in gc.get_threshold())
        self._active_thresholds = derive_runtime_thresholds(self._original_thresholds)
        self._active = False
        self._starts_ns = [0, 0, 0]
        self._collections = [0, 0, 0]
        self._collected = [0, 0, 0]
        self._duration_ms = [0.0, 0.0, 0.0]
        self._duration_max_ms = [0.0, 0.0, 0.0]

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> bool:
        with self._lock:
            if self._active:
                return False
            gc.set_threshold(*self._active_thresholds)
            if self._gc_callback not in gc.callbacks:
                gc.callbacks.append(self._gc_callback)
            self._active = True
        logger.info(
            "[GC_POLICY] RUN policy active original=%s active=%s manual_collect=disabled",
            self._original_thresholds,
            self._active_thresholds,
        )
        return True

    def stop(self) -> bool:
        with self._lock:
            if not self._active:
                return False
            try:
                while self._gc_callback in gc.callbacks:
                    gc.callbacks.remove(self._gc_callback)
            except (ValueError, RuntimeError):
                pass
            gc.set_threshold(*self._original_thresholds)
            self._active = False
        snapshot = self.snapshot()
        logger.info(
            "[GC_POLICY] RUN policy restored original=%s collections=%s "
            "duration_ms=%s max_ms=%s",
            self._original_thresholds,
            snapshot.collections,
            tuple(round(v, 2) for v in snapshot.duration_ms),
            tuple(round(v, 2) for v in snapshot.duration_max_ms),
        )
        return True

    def snapshot(self) -> GCPolicySnapshot:
        with self._lock:
            return GCPolicySnapshot(
                active=self._active,
                original_thresholds=self._original_thresholds,
                active_thresholds=self._active_thresholds,
                collections=tuple(self._collections),
                collected=tuple(self._collected),
                duration_ms=tuple(self._duration_ms),
                duration_max_ms=tuple(self._duration_max_ms),
            )

    def _gc_callback(self, phase: str, info: dict[str, Any]) -> None:
        generation = int(info.get("generation", -1) or 0)
        if generation < 0 or generation >= len(self._starts_ns):
            return
        now_ns = time.perf_counter_ns()
        if phase == "start":
            self._starts_ns[generation] = now_ns
            return
        if phase != "stop":
            return

        started_ns = self._starts_ns[generation]
        elapsed_ms = (
            max(0.0, (now_ns - started_ns) / 1_000_000.0)
            if started_ns > 0
            else 0.0
        )
        collected = max(0, int(info.get("collected", 0) or 0))
        uncollectable = max(0, int(info.get("uncollectable", 0) or 0))
        with self._lock:
            self._collections[generation] += 1
            self._collected[generation] += collected
            self._duration_ms[generation] += elapsed_ms
            self._duration_max_ms[generation] = max(
                self._duration_max_ms[generation], elapsed_ms
            )

        if elapsed_ms >= self._WARN_MS:
            logger.warning(
                "[PERF][GC_POLICY] generation=%d duration_ms=%.2f collected=%d "
                "uncollectable=%d counts=%s thresholds=%s",
                generation,
                elapsed_ms,
                collected,
                uncollectable,
                gc.get_count(),
                gc.get_threshold(),
            )
        elif is_perf_metrics_enabled() and generation >= 1:
            logger.debug(
                "[PERF][GC_POLICY] generation=%d duration_ms=%.2f collected=%d",
                generation,
                elapsed_ms,
                collected,
            )


__all__ = [
    "GCPolicySnapshot",
    "RuntimeGCPolicy",
    "derive_runtime_thresholds",
]
