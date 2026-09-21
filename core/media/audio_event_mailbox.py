"""Bounded callback-thread -> UI admission for system-audio notifications.

No Qt or COM is imported here. The caller owns a pre-created queued UI wake;
``post_wake`` MUST only queue that wake, never run ``drain`` synchronously.
An endpoint handover has priority over late volume notifications from the old
endpoint. No polling, per-event timer or callback-thread endpoint access.
"""
from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Callable


@dataclass(frozen=True, slots=True)
class AudioNotification:
    kind: str  # volume | device
    endpoint_token: int
    volume: float | None = None
    muted: bool | None = None


class AudioEventMailbox:
    """One pending wake and one latest immutable payload per active endpoint."""

    def __init__(
        self,
        *,
        post_wake: Callable[[], bool],
        deliver: Callable[[AudioNotification], None],
        ui_thread_id: int | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._post_wake = post_wake
        self._deliver = deliver
        self._ui_thread_id = threading.get_ident() if ui_thread_id is None else ui_thread_id
        self._endpoint_token = 0
        self._retired = False
        self._handover_pending = False
        self._pending: AudioNotification | None = None
        # A callback may repeat an already-consumed state after the GUI has
        # drained its wake. Keep the last consumed *endpoint-scoped* value so
        # those repeats do not schedule another GUI wake for no effective work.
        self._last_delivered: AudioNotification | None = None
        self._wake_queued = False

    @property
    def endpoint_token(self) -> int:
        with self._lock:
            return self._endpoint_token

    def accepts_endpoint_actions(self, token: int) -> bool:
        """Reject UI-side commands once retirement or device handover was admitted."""
        with self._lock:
            return (not self._retired and not self._handover_pending
                    and token == self._endpoint_token)

    def _post(self) -> bool:
        post_wake = self._post_wake
        if post_wake is None:
            return False
        try:
            admitted = post_wake()
        except Exception:
            admitted = False
        if admitted:
            return True
        with self._lock:
            # The caller must stop/reconcile the source if its UI bridge dies.
            # Do not silently build an unbounded retry or poll chain.
            self._pending = None
            self._wake_queued = False
        return False

    def push_volume(self, token: int, volume: float, muted: bool) -> bool:
        """Called from COM callback thread: copy scalar values only."""
        scalar = float(volume)
        if not 0.0 <= scalar <= 1.0:
            return False
        # Ignore sub-microfraction COM floating-point jitter without changing
        # any human-visible volume step or the authoritative endpoint value.
        scalar = round(scalar, 6)
        next_wake = False
        with self._lock:
            if self._retired or self._handover_pending or token != self._endpoint_token:
                return False
            notification = AudioNotification("volume", token, scalar, bool(muted))
            if self._pending == notification or (
                self._pending is None and self._last_delivered == notification
            ):
                return True
            self._pending = notification
            if not self._wake_queued:
                self._wake_queued = True
                next_wake = True
        return self._post() if next_wake else True

    def push_device_change(self) -> bool:
        """Fence the old endpoint immediately; rebind only after UI delivery."""
        next_wake = False
        with self._lock:
            if self._retired:
                return False
            if self._handover_pending:
                return True
            self._handover_pending = True
            self._endpoint_token += 1
            self._last_delivered = None
            self._pending = AudioNotification("device", self._endpoint_token)
            if not self._wake_queued:
                self._wake_queued = True
                next_wake = True
        return self._post() if next_wake else True

    def finish_handover(self, token: int) -> bool:
        self._require_ui_thread()
        with self._lock:
            if self._retired or token != self._endpoint_token or not self._handover_pending:
                return False
            self._handover_pending = False
            return True

    def drain(self) -> bool:
        """Run only on UI thread; at most one delivery per queued wake."""
        self._require_ui_thread()
        with self._lock:
            if self._retired:
                self._pending = None
                self._wake_queued = False
                return False
            item = self._pending
            self._pending = None
            self._wake_queued = False
            if item is not None:
                # Update before delivery: the GUI consumer can synchronously
                # trigger a callback for the same effective audio state.
                self._last_delivered = item if item.kind == "volume" else None
        if item is None:
            return False
        deliver = self._deliver
        if deliver is None:
            return False
        deliver(item)
        return True

    def retire(self) -> None:
        self._require_ui_thread()
        with self._lock:
            self._retired = True
            self._endpoint_token += 1
            self._pending = None
            self._last_delivered = None
            self._handover_pending = False
            # Break retained bound-method cycles deterministically. In particular,
            # the Qt bridge's post callback points back to the bridge and session
            # listeners deliver through bound methods that can otherwise retain
            # COM session wrappers until an unrelated later GC pass. A queued wake
            # may still run; ``drain`` observes retired state and discards it.
            self._post_wake = None
            self._deliver = None

    def _require_ui_thread(self) -> None:
        if threading.get_ident() != self._ui_thread_id:
            raise RuntimeError("audio event lifecycle and delivery require the owning UI thread")
