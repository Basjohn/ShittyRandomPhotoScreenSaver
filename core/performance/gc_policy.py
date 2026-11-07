"""RUN-lifetime garbage-collection policy for the Qt Quick architecture.

The retired pre-Qt-Quick frame-owned GC controller was never wired into the
retained Qt Quick runtime.  It also tried to disable/enable collection around a
notional Python-owned frame, which no longer matches the threaded Qt Quick
scene graph.

This owner deliberately does much less:

* retain CPython's normal automatic young-generation collection;
* reduce how often the expensive deep generations are scanned;
* observe every collection without adding a timer or polling cadence;
* restore the interpreter's original policy when RUN lifetime ends.

Each display generation is frozen at its coordinated reveal and thawed before it
retires, so the live generation's long-lived heap never enters a gen2 scan and a
retiring one is judged by the strict destruction barrier exactly as an unfrozen
one would be.

The one explicit collection is ``collect_retired_generations()``: once per
replacement, after the retiring generation's destruction barrier has completed and
before the replacement is constructed (``_construct_and_start_replacement_runtime``).
Under the RUN thresholds a deep collection practically never runs on its own, so
without it every retired generation's cyclic garbage stayed for the session, and
was re-frozen at each later reveal (Settings round trips, 7 Nov 2026: ~14.5k objects
and ~20 MB a round trip, 15 Python-owned ``QQmlComponent`` and an ~11 MB buffer among
them). It never runs at frame time, during a teardown, or before the barrier has
judged the retiring owners by reference counting.
"""
from __future__ import annotations

from dataclasses import dataclass
import gc
import threading
import time
from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GCPolicySnapshot:
    active: bool
    original_thresholds: tuple[int, int, int]
    active_thresholds: tuple[int, int, int]
    collections: tuple[int, int, int]
    collected: tuple[int, int, int]
    uncollectable: tuple[int, int, int]
    slow_collections: tuple[int, int, int]
    duration_ms: tuple[float, float, float]
    duration_max_ms: tuple[float, float, float]
    freeze_duration_ms: float | None
    frozen_object_count: int


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
        self._freeze_duration_ms: float | None = None
        self._frozen_object_count = 0
        self._starts_ns = [0, 0, 0]
        self._collections = [0, 0, 0]
        self._collected = [0, 0, 0]
        self._uncollectable = [0, 0, 0]
        self._slow_collections = [0, 0, 0]
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

        Called at every display generation's coordinated reveal (its warm-up end), from a normal context.
        In-situ evidence (2026-09-03): the objects that survive to gen2 are a
        stable, long-lived set that gen2 rescans for ~28-142 ms while freeing
        almost nothing (``collected=0``), and each scan stalls the pure-Python
        Visualizer cadence thread (a ~32 ms gen2 produced a ~43 ms Bubble tick
        spike). ``gc.freeze()`` moves that set into a permanent generation that
        future collections never scan. The one-shot boundary records its actual
        cost (freeze, threshold restoration and count observation) in this RUN;
        historical measurements are not a bound on a current runtime.

        Precise lifetime semantics (this is NOT disabling GC), proven in
        `tests/test_gc_freeze_lifetime.py`:
        - objects allocated *after* the freeze remain under normal generational
          GC, so post-freeze growth — including post-freeze cyclic garbage and
          every runtime/display/Settings generation recreated after the freeze —
          is still collected on the normal cadence and stays visible;
        - ordinary refcount-zero destruction still frees frozen objects
          immediately; only *cyclic* collection of the frozen set is deferred to
          ``gc.unfreeze()`` at that generation's teardown or RUN stop;
        - consequence: every teardown thaws first (``thaw_for_runtime_retirement``,
          from ``teardown_display_runtime``). The thaw sweeps nothing: the destruction
          barrier judges the retiring owners by reference counting alone, exactly
          as for a generation that was never frozen (R-53/R-154). Once that barrier
          has completed, the replacement's construction collects the thawed cycles
          once (``collect_retired_generations``). The next generation is frozen
          at its own reveal. (Before that collection, 7 Nov, each reveal re-froze
          every earlier generation's uncollected cycles as well.)
          (Until 7 Nov the freeze was a one-shot 45 s timer and the first Settings
          visit thawed the RUN for good: every later gen2 scanned the whole heap.)
        Idempotent; a no-op once frozen or when the policy is inactive.
        """

        with self._lock:
            if not self._active or self._frozen:
                return False
            started_ns = time.perf_counter_ns()
            gc.freeze()
            # The stable set is now excluded from every future gen2 scan, so the
            # warmup gen2 deferral has done its job: restore the normal active
            # cadence for post-freeze objects (recreated runtime/display/Settings
            # generations still collect normally).
            gc.set_threshold(*self._active_thresholds)
            self._frozen = True
            frozen_count = gc.get_freeze_count()
            self._frozen_object_count = frozen_count
            self._freeze_duration_ms = max(
                0.0, (time.perf_counter_ns() - started_ns) / 1_000_000.0
            )
        logger.info(
            "[GC_POLICY] Froze %d stable objects into the permanent generation "
            "(excluded from future gen2 scans; released on stop); restored active "
            "thresholds=%s for post-freeze collection freeze_boundary_ms=%.3f",
            frozen_count,
            self._active_thresholds,
            self._freeze_duration_ms,
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

    def thaw_for_runtime_retirement(self) -> bool:
        """Return the revealed generation's frozen heap to the collector before it retires.

        Called on every display teardown (``teardown_display_runtime``; ``stop`` too). Thawing only makes the
        retiring generation's objects ordinary again; it schedules no sweep. The destruction barrier stays the
        project's cycle detector (R-53/R-154): a retiring owner must be released by reference counting alone, and a
        cyclic one fails closed exactly as it would had it never been frozen. (Until 7 Nov the first retirement after
        the one-shot freeze, and only that one, got a stop-boundary gen2 sweep; the 25 Oct assessment recorded that
        inconsistency, and the 7 Nov operator session's retirement needed no sweep.) The next generation is frozen at
        its own coordinated reveal, never while it is still being built or edited.
        """
        with self._lock:
            if not self._active or not self._frozen:
                return False
            gc.unfreeze()
            self._frozen = False
        logger.info("[GC_POLICY] Thawed the revealed generation before its retirement")
        return True

    def collect_retired_generations(self, *, event: str = "replacement") -> int | None:
        """Reclaim the cyclic garbage of generations the destruction barrier has already judged.

        Called once per replacement, after the retiring generation's barrier (and the Settings dialog's) completed
        and before the replacement is constructed. The barrier has already proven its watched owners released by
        reference counting alone (R-53/R-154) or failed closed, so this collection hides nothing from it; it only
        reclaims what that generation left in reference cycles: Python wrappers of destroyed QObjects, their
        dicts and closures, and the Python-owned native objects and buffers they keep (Python-owned
        ``QQmlComponent``s, arrays, images). Under the RUN thresholds a deep collection practically never runs on
        its own (none in a 10-minute Settings round-trip run), and each later reveal re-froze that garbage, so
        every round trip added ~20 MB for the session.

        Never at frame time and never inside a teardown: no display generation exists at this point (the
        retiring one is gone, the replacement not yet built). A no-op (``None``) while the policy is inactive or
        a generation is still frozen.
        """
        with self._lock:
            if not self._active or self._frozen:
                return None
        started_ns = time.perf_counter_ns()
        unreachable = gc.collect()
        elapsed_ms = max(0.0, (time.perf_counter_ns() - started_ns) / 1_000_000.0)
        logger.info(
            "[GC_POLICY] Collected %d unreachable objects of retired generations after the destruction barrier "
            "event=%s ms=%.1f",
            unreachable,
            event,
            elapsed_ms,
        )
        return unreachable

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
            "collected=%s uncollectable=%s slow_ge_%.1fms=%s "
            "duration_ms=%s max_ms=%s freeze_restored=%s",
            self._original_thresholds,
            snapshot.collections,
            snapshot.collected,
            snapshot.uncollectable,
            self._WARN_MS,
            snapshot.slow_collections,
            tuple(round(v, 2) for v in snapshot.duration_ms),
            tuple(round(v, 2) for v in snapshot.duration_max_ms),
            not unfreeze_failed,
        )
        if any(snapshot.slow_collections):
            # GC callbacks are forbidden from logging.  Emit their aggregate
            # warning only after the callback has been removed and ordinary
            # logging is once again a safe operation.
            logger.warning(
                "[PERF][GC_POLICY] deferred slow-collection summary "
                "slow_ge_%.1fms=%s max_ms=%s collected=%s uncollectable=%s",
                self._WARN_MS,
                snapshot.slow_collections,
                tuple(round(v, 2) for v in snapshot.duration_max_ms),
                snapshot.collected,
                snapshot.uncollectable,
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
                uncollectable=tuple(self._uncollectable),
                slow_collections=tuple(self._slow_collections),
                duration_ms=tuple(self._duration_ms),
                duration_max_ms=tuple(self._duration_max_ms),
                freeze_duration_ms=self._freeze_duration_ms,
                frozen_object_count=self._frozen_object_count,
            )

    def _gc_callback(self, phase: str, info: dict[str, Any]) -> None:
        """Capture collection telemetry without locks, logging, I/O or Qt work.

        CPython can invoke this callback from an arbitrary allocation point.
        That includes code already holding the logging ingress locks or this
        policy's own lifecycle lock.  The callback is therefore deliberately
        leaf-like: mutate only small in-memory counters while the GIL is held.
        Reporting happens later from stop(), after this callback is removed.
        """

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

        # No lock here by design.  gc.callbacks execute as Python callbacks
        # under the GIL, and this path must remain safe even if collection
        # interrupts code that already owns self._lock or a logging lock.
        self._collections[generation] += 1
        self._collected[generation] += collected
        self._uncollectable[generation] += uncollectable
        self._duration_ms[generation] += elapsed_ms
        self._duration_max_ms[generation] = max(
            self._duration_max_ms[generation], elapsed_ms
        )
        if elapsed_ms >= self._WARN_MS:
            self._slow_collections[generation] += 1


def heap_census(top: int = 25) -> tuple[int, int, list[tuple[str, int]]]:
    """(tracked, frozen, the ``top`` most numerous tracked types): what a gen2 scan would walk.

    Diagnostic only (``--frame-trace``): one full walk of the tracked heap, at a lifecycle edge, never per frame.
    """
    from collections import Counter

    counts = Counter(
        f"{getattr(type(obj), '__module__', '?')}.{type(obj).__qualname__}" for obj in gc.get_objects()
    )
    return sum(counts.values()), gc.get_freeze_count(), counts.most_common(top)


__all__ = [
    "GCPolicySnapshot",
    "heap_census",
    "RuntimeGCPolicy",
    "derive_runtime_thresholds",
]
