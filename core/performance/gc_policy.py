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


# How far the gen2 (full) trigger is deferred during the pre-freeze warmup window.
# The one expensive pre-freeze gen2 merely rescans the soon-to-be-frozen stable
# set (near-zero yield); deferring it past `freeze_stable_generation()` removes
# that ~100 ms stall without disabling gen2 outright.
_WARMUP_FULL_DEFERRAL = 10


def derive_warmup_thresholds(
    active: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Return startup thresholds that keep the first gen2 from racing the freeze.

    Young/middle keep the active cadence; only the gen2 (full) trigger is raised,
    so the single expensive pre-freeze gen2 — which merely rescans the
    soon-to-be-frozen long-lived set and frees almost nothing — does not fire
    before `freeze_stable_generation()`. This is contract-neutral: `gc.freeze()`
    pins the same tracked set either way, so raising the warmup trigger only skips
    a wasteful scan, it does not change what gets frozen. The trigger is left
    finite (not zero/disabled), so a run whose freeze never fires still collects
    gen2 on a bounded — if later — cadence rather than growing without limit.
    """

    young, middle, full = (max(0, int(v)) for v in active)
    if young <= 0:
        # Honour an intentionally disabled collector rather than reviving it.
        return (young, middle, full)
    return (young, middle, max(full * _WARMUP_FULL_DEFERRAL, full))


class RuntimeGCPolicy:
    """Single RUN-lifetime owner of automatic GC threshold policy/telemetry."""

    _WARN_MS = 10.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._original_thresholds = tuple(int(v) for v in gc.get_threshold())
        self._active_thresholds = derive_runtime_thresholds(self._original_thresholds)
        # Applied only until the one-shot freeze runs; keeps the pre-freeze gen2
        # from racing the freeze (see derive_warmup_thresholds).
        self._warmup_thresholds = derive_warmup_thresholds(self._active_thresholds)
        self._active = False
        self._frozen = False
        self._starts_ns = [0, 0, 0]
        self._collections = [0, 0, 0]
        self._collected = [0, 0, 0]
        self._duration_ms = [0.0, 0.0, 0.0]
        self._duration_max_ms = [0.0, 0.0, 0.0]

    @property
    def active(self) -> bool:
        return self._active

    @property
    def frozen(self) -> bool:
        return self._frozen

    def freeze_stable_generation(self) -> bool:
        """Move the current long-lived tracked set to the permanent generation.

        Called once, from a normal (non-collection) context after startup warms.
        In-situ evidence (2026-09-03): the objects that survive to gen2 are a
        stable, long-lived set that gen2 rescans for ~28-142 ms while freeing
        almost nothing (``collected=0``), and each scan stalls the pure-Python
        Visualizer cadence thread (a ~32 ms gen2 produced a ~43 ms Bubble tick
        spike). ``gc.freeze()`` splices that set into a permanent generation in
        O(1) (~0.01 ms) that future collections never scan, so recurring gen2 no
        longer causes those stalls.

        Precise lifetime semantics (this is NOT disabling GC), proven in
        `tests/test_gc_freeze_lifetime.py`:
        - objects allocated *after* the freeze remain under normal generational
          GC, so post-freeze growth — including post-freeze cyclic garbage and
          every runtime/display/Settings generation recreated after the freeze —
          is still collected on the normal cadence and stays visible;
        - ordinary refcount-zero destruction still frees frozen objects
          immediately; only *cyclic* collection of the frozen set is deferred to
          ``gc.unfreeze()`` on stop;
        - consequence: the single runtime generation live *at freeze time* has a
          cyclic Python graph, so if it later retires it stays pinned until
          unfreeze. This is a bounded one-generation offset, NOT unbounded
          accumulation (later generations are not frozen and retire normally),
          and its OS resources (threads/GL/handles) are released by explicit
          teardown regardless. Do not move runtime-owned cyclic lifetime into the
          pre-freeze set expecting it to be reclaimed before stop.
        Idempotent; a no-op once frozen or when the policy is inactive.
        """

        with self._lock:
            if not self._active or self._frozen:
                return False
            gc.freeze()
            # The stable set is now excluded from every future gen2 scan, so the
            # warmup gen2 deferral has done its job: restore the normal active
            # cadence for post-freeze objects (recreated runtime/display/Settings
            # generations still collect normally).
            gc.set_threshold(*self._active_thresholds)
            self._frozen = True
            frozen_count = gc.get_freeze_count()
        logger.info(
            "[GC_POLICY] Froze %d stable objects into the permanent generation "
            "(excluded from future gen2 scans; released on stop); restored active "
            "thresholds=%s for post-freeze collection",
            frozen_count,
            self._active_thresholds,
        )
        return True

    def start(self) -> bool:
        with self._lock:
            if self._active:
                return False
            # Warmup thresholds until the one-shot freeze: gen2 is deferred so the
            # first expensive gen2 cannot fire before the stable set is frozen.
            gc.set_threshold(*self._warmup_thresholds)
            if self._gc_callback not in gc.callbacks:
                gc.callbacks.append(self._gc_callback)
            self._active = True
        logger.info(
            "[GC_POLICY] RUN policy active original=%s warmup=%s active=%s manual_collect=disabled",
            self._original_thresholds,
            self._warmup_thresholds,
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
            unfreeze_failed = False
            if self._frozen:
                # Release the pinned startup snapshot back to normal collection
                # so the interpreter's original lifetime behavior is fully
                # restored. If this fails, keep the internal state truthful
                # (still frozen) and report loudly rather than claiming success.
                try:
                    gc.unfreeze()
                    self._frozen = False
                except Exception:
                    unfreeze_failed = True
                    logger.error(
                        "[GC_POLICY] gc.unfreeze() FAILED on stop; the frozen "
                        "startup generation remains pinned until process exit",
                        exc_info=True,
                    )
            self._active = False
        snapshot = self.snapshot()
        logger.info(
            "[GC_POLICY] RUN policy restored original=%s collections=%s "
            "duration_ms=%s max_ms=%s freeze_restored=%s",
            self._original_thresholds,
            snapshot.collections,
            tuple(round(v, 2) for v in snapshot.duration_ms),
            tuple(round(v, 2) for v in snapshot.duration_max_ms),
            not unfreeze_failed,
        )
        return not unfreeze_failed

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
