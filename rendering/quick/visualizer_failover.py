"""Presentation-neutral Visualizer CUSTOM failover state (E2.7).

Process-scoped, runtime-only record of the single Visualizer's CUSTOM
failover/reclaim lifecycle. This is the durable state authority that must
outlive individual Quick runtime generations: a configured CUSTOM monitor can
be momentarily unavailable across a wake/topology cycle that rebuilds the whole
Quick display generation, and the outage's grace generation / temporary-owner
record must survive that rebuild so the next generation's admission can reclaim
the configured monitor or honour an in-flight grace.

It is deliberately presentation-neutral: it holds only the intended (configured)
screen index, opaque references to the temporary host and origin owner, the
pending-grace flag, and the global outage generation. It constructs, renders,
and retires nothing itself; ``rendering/quick/visualizer_failover_lifecycle.py``
owns the policy and drives an injected topology over this state.

Never persisted — a temporary fallback must not become configuration authority;
the record is cleared on runtime teardown. Recovered/re-homed from the legacy
``rendering/multi_monitor_coordinator.py`` E2.7 failover authority deleted with
the physical presentation host; the generation/grace/reclaim contract is
unchanged.
"""

from __future__ import annotations

import threading
import weakref
from typing import Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)


def _weak_or_none(obj: object) -> Optional["weakref.ref"]:
    if obj is None:
        return None
    try:
        return weakref.ref(obj)
    except TypeError:
        # Test doubles / immutable sentinels may not support weakrefs; hold none
        # rather than a strong reference so the failover record never keeps a
        # retiring owner alive.
        return None


class VisualizerFailoverState:
    """Single-Visualizer CUSTOM failover record + global outage generation.

    Either a pending 30 s grace (no temporary owner yet) or a live temporary
    fallback owner. Holds the configured/intended screen index, an opaque weakref
    to the temporary host (if any), an opaque weakref to the origin owner (to read
    live settings and fence its pending delayed callback), and the pending flag.

    The generation is the GLOBAL authority for one outage: ``_seq`` only ever
    increments (unique per outage); ``_gen`` is the currently-active outage
    generation (0 = none). Every delayed grace callback validates ``_gen`` so a
    straggler from an older outage cannot act after reclaim or a new outage.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._intended: Optional[int] = None
        self._host_ref: Optional[weakref.ref] = None
        self._origin_ref: Optional[weakref.ref] = None
        self._pending: bool = False
        self._seq: int = 0
        self._gen: int = 0

    def arm_visualizer_grace(
        self,
        *,
        intended_index: int,
        origin_manager: object = None,
    ) -> Optional[int]:
        """Arm ONE global grace for the single Visualizer outage.

        Returns a fresh generation to schedule the deadline with, or ``None`` when
        a failover (grace or live fallback) is already active for the current
        outage — in which case the caller must NOT schedule another 30 s deadline.
        This makes the grace authority global: repeated reconcile during one
        outage cannot start or reset a second grace.
        """
        with self._lock:
            if self._intended is not None:
                return None  # a grace/fallback is already active for this outage
            try:
                idx = int(intended_index)
            except Exception:
                return None
            self._seq += 1
            gen = self._seq
            self._gen = gen
            self._intended = idx
            self._host_ref = None
            self._origin_ref = _weak_or_none(origin_manager)
            self._pending = True
        logger.debug(
            "[VIS_FAILOVER] grace armed gen=%s intended_index=%s", gen, idx
        )
        return gen

    def set_visualizer_fallback_owner(
        self,
        *,
        intended_index: int,
        host: object,
        origin_manager: object = None,
    ) -> None:
        """Record a live temporary fallback owner for the CURRENT outage.

        Keeps the current failover generation (the fallback is the same outage as
        the grace). Allocates a generation if somehow none is active.
        """
        with self._lock:
            try:
                idx = int(intended_index)
            except Exception:
                return
            if self._gen == 0:
                self._seq += 1
                self._gen = self._seq
            self._intended = idx
            self._host_ref = _weak_or_none(host)
            self._origin_ref = _weak_or_none(origin_manager)
            self._pending = False
        logger.debug(
            "[VIS_FAILOVER] fallback owner recorded gen=%s intended_index=%s host=%s",
            self._gen, idx, getattr(host, "screen_index", None),
        )

    def repend_visualizer_failover(
        self,
        *,
        intended_index: int,
        origin_manager: object = None,
    ) -> None:
        """Return the CURRENT outage record to the pending-grace state (no owner).

        Used when a reclaim create fails after the temporary owner was already
        retired: keep the same generation so a later event can retry without a
        dangling fallback host.
        """
        with self._lock:
            try:
                idx = int(intended_index)
            except Exception:
                return
            if self._gen == 0:
                self._seq += 1
                self._gen = self._seq
            self._intended = idx
            self._host_ref = None
            self._origin_ref = _weak_or_none(origin_manager)
            self._pending = True

    def update_visualizer_failover_intended(self, intended_index: int) -> None:
        """Update the recorded intended index (a live Settings monitor change)."""
        with self._lock:
            if self._intended is None:
                return
            try:
                self._intended = int(intended_index)
            except Exception:
                pass

    def clear_visualizer_failover(self) -> None:
        """Clear the failover record and INVALIDATE its generation.

        Setting the active generation to 0 makes every outstanding delayed grace
        callback (this outage or older) fail its generation check, so
        reclaim/target-return retires the whole old generation at once. A later
        outage arms a fresh, strictly-greater generation.
        """
        with self._lock:
            had = self._intended is not None
            self._intended = None
            self._host_ref = None
            self._origin_ref = None
            self._pending = False
            self._gen = 0
        if had:
            logger.debug("[VIS_FAILOVER] failover record cleared (generation invalidated)")

    def is_visualizer_failover_generation_current(self, generation: int) -> bool:
        """Return whether ``generation`` is the currently-active outage generation."""
        with self._lock:
            return generation != 0 and generation == self._gen

    def get_visualizer_failover(self) -> Optional[dict]:
        """Return the current failover record, or None if there is none.

        Shape: ``{"intended_index": int, "host": obj|None,
        "origin_manager": obj|None, "pending": bool, "generation": int}``.
        """
        with self._lock:
            if self._intended is None:
                return None
            host = self._host_ref() if self._host_ref else None
            origin = self._origin_ref() if self._origin_ref else None
            return {
                "intended_index": self._intended,
                "host": host,
                "origin_manager": origin,
                "pending": self._pending,
                "generation": self._gen,
            }


_STATE_LOCK = threading.Lock()
_STATE: Optional[VisualizerFailoverState] = None


def get_visualizer_failover_state() -> VisualizerFailoverState:
    """Return the process-scoped single-Visualizer failover state authority."""
    global _STATE
    with _STATE_LOCK:
        if _STATE is None:
            _STATE = VisualizerFailoverState()
        return _STATE


__all__ = [
    "VisualizerFailoverState",
    "get_visualizer_failover_state",
]
