"""Generation-owned, event-driven admission between image batches and refresh work.

The gate decides *when* a widget's already-due work may start. It does not own
source cadence, worker execution, cancellation or image presentation. A claim
lasts through GUI publication. One refresh runs at a time across participating
families, so releasing a dual-display transition cannot create a refresh storm.
"""
from __future__ import annotations

from collections import OrderedDict
from threading import RLock
import logging
import time
from typing import Callable
import weakref

_logger = logging.getLogger(__name__)


def _family_name(key: object) -> str:
    """Diagnostic family only. Do not log authored feed URLs/cache keys."""
    if isinstance(key, tuple) and key:
        if key[0] in ("gmail", "reddit"):
            return str(key[0])
        if isinstance(key[0], int):
            return "feeds"
    return "other"


class RefreshTransitionGate:
    def __init__(self, generation: object) -> None:
        self.generation = generation
        self._lock = RLock()
        self._closed = False
        self._transition = False
        self._refresh_tokens: set[object] = set()
        self._waiting_transition: Callable[[], None] | None = None
        self._waiting_refresh: OrderedDict[object, Callable[[], None]] = OrderedDict()
        self._draining = False
        self._draining_key = None
        # Edge-only latency attribution. Never sample, tick or poll the gate.
        self._refresh_queued_at: dict[object, float] = {}
        self._refresh_claims_at: dict[object, tuple[float, str]] = {}
        self._transition_queued_at: float | None = None

    def begin_transition(self, resume: Callable[[], None] | None = None) -> str:
        """Reserve one whole multi-display batch; a waiting batch outranks refresh."""
        with self._lock:
            if self._closed or self._transition:
                return "busy"
            if self._refresh_tokens:
                if resume is not None:
                    if self._waiting_transition is None:
                        self._transition_queued_at = time.monotonic()
                    self._waiting_transition = resume  # latest wins
                    _logger.info("[REFRESH_GATE] transition_waits active_refreshes=%d", len(self._refresh_tokens))
                    return "deferred"
                return "busy"
            self._transition = True
            return "started"

    def begin_refresh(self, key: object, resume: Callable[[], None]) -> object | None:
        """Claim through GUI publication, or coalesce one wake per source key.

        Waiting work is resumed by an event, then rechecks its own dormancy,
        freshness and cancellation before requesting a claim again.
        """
        should_drain = False
        with self._lock:
            if self._closed:
                return None
            if (self._transition or self._waiting_transition is not None
                    or self._refresh_tokens
                    or (self._waiting_refresh and key != self._draining_key)):
                was_waiting = key in self._waiting_refresh
                self._waiting_refresh[key] = resume
                if not was_waiting:
                    self._refresh_queued_at[key] = time.monotonic()
                    _logger.info("[REFRESH_GATE] refresh_waits family=%s contention=1",
                                 _family_name(key))
                should_drain = not (self._transition or self._refresh_tokens or self._waiting_transition)
            else:
                token = object()
                self._refresh_tokens.add(token)
                self._refresh_claims_at[token] = (time.monotonic(), _family_name(key))
                return token
        if should_drain:
            self._drain_refreshes()
        return None

    def cancel_refresh(self, key: object) -> None:
        """Discard a dormant/retired source's deferred intent, never its active claim."""
        with self._lock:
            self._waiting_refresh.pop(key, None)
            self._refresh_queued_at.pop(key, None)

    def finish_refresh(self, token: object) -> None:
        resume = None
        should_drain = False
        with self._lock:
            if token not in self._refresh_tokens:
                return
            self._refresh_tokens.remove(token)
            started = self._refresh_claims_at.pop(token, None)
            if started is not None:
                _logger.info("[REFRESH_GATE] refresh_finished family=%s held_ms=%.2f",
                             started[1], (time.monotonic() - started[0]) * 1000.0)
            if self._closed:
                return
            if (not self._refresh_tokens and self._waiting_transition is not None
                    and not self._transition):
                resume, self._waiting_transition = self._waiting_transition, None
                self._transition = True  # reserve before invoking the contender
                queued_at, self._transition_queued_at = self._transition_queued_at, None
                _logger.info("[REFRESH_GATE] transition_resumes after_refresh=1 wait_ms=%.2f",
                             (time.monotonic() - queued_at) * 1000.0 if queued_at is not None else 0.0)
            elif not self._refresh_tokens and not self._transition:
                should_drain = True
        if resume is not None:
            try:
                resume()
            except Exception:
                self.end_transition()
                raise
        elif should_drain:
            self._drain_refreshes()

    def end_transition(self) -> None:
        with self._lock:
            if not self._transition or self._closed:
                return
            self._transition = False
        self._drain_refreshes()

    def _drain_refreshes(self) -> None:
        """Iteratively wake one deferred owner, stopping when it claims work.

        A stale/dormant owner may decline the wake without obtaining a token;
        keep draining rather than stranding the next source. Reentrant finish()
        never recursively replays the backlog. No timers or polling are used.
        """
        with self._lock:
            if self._draining or self._closed:
                return
            self._draining = True
        try:
            while True:
                with self._lock:
                    if (self._closed or self._transition or self._refresh_tokens
                            or self._waiting_transition is not None or not self._waiting_refresh):
                        return
                    key, resume = self._waiting_refresh.popitem(last=False)
                    queued_at = self._refresh_queued_at.pop(key, None)
                    self._draining_key = key
                _logger.info("[REFRESH_GATE] refresh_resumes family=%s wait_ms=%.2f one=1",
                             _family_name(key),
                             (time.monotonic() - queued_at) * 1000.0 if queued_at is not None else 0.0)
                try:
                    resume()
                except Exception:
                    _logger.exception("[REFRESH_GATE] deferred refresh resume failed")
        finally:
            with self._lock:
                self._draining_key = None
                self._draining = False

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._transition = False
            self._waiting_transition = None
            self._waiting_refresh.clear()
            self._refresh_tokens.clear()
            self._refresh_queued_at.clear()
            self._refresh_claims_at.clear()
            self._transition_queued_at = None

    @property
    def snapshot(self) -> tuple[bool, int, int, bool]:
        with self._lock:
            return (self._transition, len(self._refresh_tokens),
                    len(self._waiting_refresh), self._waiting_transition is not None)


_active_gate: weakref.ReferenceType[RefreshTransitionGate] | None = None


def install_gate(gate: RefreshTransitionGate | None) -> None:
    global _active_gate
    _active_gate = weakref.ref(gate) if gate is not None else None


def current_gate(generation: object = None) -> RefreshTransitionGate | None:
    gate = _active_gate() if _active_gate is not None else None
    if gate is None or gate._closed:
        return None
    if generation is not None and gate.generation != generation:
        return None
    return gate
