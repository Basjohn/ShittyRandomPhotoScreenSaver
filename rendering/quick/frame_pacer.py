"""Qt-Quick-owned continuous-frame demand for retained scene animations.

Visualizer presentation is intentionally *not* paced here. Fresh visualizer
publications wake their retained QQuickItem directly with latest-wins/coalesced
semantics. This owner exists only for scene content whose pixels continue to
change as a function of wall time after state admission (wallpaper transitions
and admitted QML widget animations).

The driver is chained from ``QQuickWindow.frameSwapped`` instead of a Python
``QTimer``. One initial ``QWindow.requestUpdate()`` enters Qt's coalesced update path;
each completed swap requests at most one successor while continuous-frame demand
remains active. There is no second display-refresh clock, deadline debt,
or timer polling layer competing with Qt Quick's animation/render scheduling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, auto
import math

from PySide6.QtCore import QObject
from PySide6.QtQuick import QQuickWindow


class QuickFrameDemand(IntFlag):
    """Independent reasons that require continuously changing scene frames."""

    NONE = 0
    TRANSITION = auto()
    WIDGET_ANIMATION = auto()


@dataclass
class QuickPacerState:
    """Diagnostics for one Qt-Quick-owned continuous frame chain.

    ``target_hz`` is the bound screen's nominal refresh and remains useful in
    PERF output. It is *not* a Python pacing clock. ``skipped_deadlines`` stays
    at zero for log/schema compatibility because this driver owns no deadlines.
    """

    target_hz: float
    requested_opportunities: int = 0
    paced_requests: int = 0
    skipped_deadlines: int = 0
    frame_swaps: int = 0

    def __post_init__(self) -> None:
        rate = float(self.target_hz)
        if not math.isfinite(rate) or rate <= 0.0:
            raise ValueError("target_hz must be finite and greater than zero")
        self.target_hz = rate
        self.interval_ns = max(1, int(round(1_000_000_000.0 / rate)))


class QuickFramePacer(QObject):
    """Drive continuous retained-scene animation from Qt Quick frame completion.

    This class deliberately does not know about the visualizer. Visualizer
    logical state is event-driven and calls ``QQuickItem.update()`` only when a
    fresh latest-wins publication exists.
    """

    def __init__(self, window: QQuickWindow, target_hz: float) -> None:
        super().__init__(window)
        self._window = window
        self._state = QuickPacerState(float(target_hz))
        self._demands = QuickFrameDemand.NONE
        self._paused = False
        # A hidden/retired window may discard an already queued update without
        # emitting frameSwapped.  Never carry that stale admission across a
        # later reuse of this runtime.
        self._update_pending = False
        self._closed = False
        window.frameSwapped.connect(self._on_frame_swapped)

    @property
    def target_hz(self) -> float:
        return self._state.target_hz

    @property
    def demands(self) -> QuickFrameDemand:
        return self._demands

    def is_active(self) -> bool:
        return bool(self._demands) and not self._paused and not self._closed

    def set_demand(self, reason: QuickFrameDemand, active: bool) -> None:
        """Add/remove one continuous-frame reason and seed Qt Quick once."""

        if self._closed:
            raise RuntimeError("Quick frame pacer is closed")
        allowed = int(QuickFrameDemand.TRANSITION | QuickFrameDemand.WIDGET_ANIMATION)
        reason_value = int(reason)
        if reason_value == 0 or reason_value & ~allowed:
            raise ValueError(f"unsupported Quick frame demand: {reason!r}")
        reason = QuickFrameDemand(reason_value)

        previous = self._demands
        if active:
            self._demands |= reason
        else:
            self._demands &= ~reason
        if self._demands == previous:
            return

        if previous == QuickFrameDemand.NONE and self.is_active():
            self._request_next_frame()

    def set_transition_active(self, active: bool) -> None:
        self.set_demand(QuickFrameDemand.TRANSITION, active)

    def set_widget_animation_active(self, active: bool) -> None:
        self.set_demand(QuickFrameDemand.WIDGET_ANIMATION, active)

    def set_target_hz(self, target_hz: float) -> None:
        """Update nominal display refresh metadata after QScreen retargeting."""

        if self._closed:
            raise RuntimeError("Quick frame pacer is closed")
        replacement = QuickPacerState(float(target_hz))
        if math.isclose(
            replacement.target_hz,
            self._state.target_hz,
            rel_tol=0.0,
            abs_tol=0.001,
        ):
            return
        replacement.requested_opportunities = self._state.requested_opportunities
        replacement.paced_requests = self._state.paced_requests
        replacement.frame_swaps = self._state.frame_swaps
        self._state = replacement

    def stop(self) -> None:
        """Clear all continuous demand; an already queued frame may finish once."""

        if self._closed:
            return
        self._demands = QuickFrameDemand.NONE
        self._paused = False
        # A queued update can be discarded when a transition/animation owner is
        # retired. Do not let that stale admission suppress a later demand.
        self._update_pending = False

    def pause(self) -> bool:
        """Suspend continuation while preserving active reasons."""

        if self._closed or self._paused:
            return False
        self._paused = True
        # Visibility changes can discard a queued QQuickWindow update without a
        # frameSwapped acknowledgement.  Clear only our admission bit; Qt owns
        # whatever work was already accepted.  resume() will seed one fresh
        # update from the current demand set.
        self._update_pending = False
        return True

    def resume(self) -> bool:
        """Resume from now with one Qt Quick update; there is no hidden debt."""

        if self._closed or not self._paused:
            return False
        self._paused = False
        if self._demands:
            self._request_next_frame()
        return True

    def close(self) -> None:
        """Permanently close demand admission for display-runtime teardown."""

        if self._closed:
            return
        self.stop()
        try:
            self._window.frameSwapped.disconnect(self._on_frame_swapped)
        except (RuntimeError, TypeError):
            pass
        self._closed = True
        self._update_pending = False

    def describe(self) -> dict[str, object]:
        return {
            "driver": "qt_frame_swapped",
            "target_hz": self._state.target_hz,
            "interval_ns": self._state.interval_ns,
            "active": self.is_active(),
            "paused": self._paused,
            "closed": self._closed,
            "demands": [
                demand.name.lower()
                for demand in (
                    QuickFrameDemand.TRANSITION,
                    QuickFrameDemand.WIDGET_ANIMATION,
                )
                if self._demands & demand
            ],
            # Keep the existing PERF schema stable. These now mean Qt-owned
            # continuation opportunities/requests, not Python timer deadlines.
            "requested_opportunities": self._state.requested_opportunities,
            "issued_update_requests": self._state.paced_requests,
            "skipped_deadlines": 0,
            "frame_swaps": self._state.frame_swaps,
            "update_pending": self._update_pending,
        }

    def _request_next_frame(self) -> bool:
        if not self.is_active() or self._update_pending:
            return False
        self._update_pending = True
        self._state.requested_opportunities += 1
        self._state.paced_requests += 1
        self._window.requestUpdate()
        return True

    def _on_frame_swapped(self) -> None:
        """Continue only after Qt Quick confirms the previous frame boundary."""

        if self._closed:
            return
        self._state.frame_swaps += 1
        self._update_pending = False
        if self.is_active():
            self._request_next_frame()


__all__ = [
    "QuickFrameDemand",
    "QuickFramePacer",
    "QuickPacerState",
]
