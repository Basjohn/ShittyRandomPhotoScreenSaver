"""Display-local presentation pacing for dynamic Quick render-node content."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, auto
import math
import time
from typing import Callable

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtQuick import QQuickWindow

from core.logging.logger import get_logger

logger = get_logger(__name__)


class QuickFrameDemand(IntFlag):
    """Independent reasons that require continuous custom-node presentation."""

    NONE = 0
    TRANSITION = auto()
    VISUALIZER = auto()
    # A widget QML opacity/crossfade animation is running. Without this the
    # threaded scene is only driven while a wallpaper transition or the
    # visualizer demands frames, so a track-change/rotation fade with neither
    # active renders only its first/last frame and reads as a hard flash.
    WIDGET_ANIMATION = auto()


@dataclass(frozen=True)
class QuickPacingDecision:
    due_opportunities: int
    next_delay_ms: int


@dataclass
class QuickPacerState:
    """Monotonic latest-opportunity pacing with no catch-up request burst."""

    target_hz: float
    requested_opportunities: int = 0
    paced_requests: int = 0
    skipped_deadlines: int = 0
    next_deadline_ns: int | None = None

    def __post_init__(self) -> None:
        rate = float(self.target_hz)
        if not math.isfinite(rate) or rate <= 0.0:
            raise ValueError("target_hz must be finite and greater than zero")
        self.target_hz = rate
        self.interval_ns = max(1, int(round(1_000_000_000.0 / rate)))

    def start(self, now_ns: int) -> None:
        self.next_deadline_ns = int(now_ns)

    def stop(self) -> None:
        self.next_deadline_ns = None

    def consume(self, now_ns: int) -> QuickPacingDecision:
        now_ns = int(now_ns)
        if self.next_deadline_ns is None:
            self.start(now_ns)

        deadline = int(self.next_deadline_ns)
        if now_ns < deadline:
            return QuickPacingDecision(
                due_opportunities=0,
                next_delay_ms=max(
                    1,
                    math.ceil((deadline - now_ns) / 1_000_000.0),
                ),
            )

        due = 1 + ((now_ns - deadline) // self.interval_ns)
        self.requested_opportunities += int(due)
        self.paced_requests += 1
        self.skipped_deadlines += max(0, int(due) - 1)
        self.next_deadline_ns = deadline + int(due) * self.interval_ns
        delay_ns = max(0, int(self.next_deadline_ns) - now_ns)
        return QuickPacingDecision(
            due_opportunities=int(due),
            next_delay_ms=max(1, math.ceil(delay_ns / 1_000_000.0)),
        )


class QuickFramePacer(QObject):
    """One demand-driven target pacer for one standalone Quick window."""

    def __init__(
        self,
        window: QQuickWindow,
        target_hz: float,
        *,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
        timer: QTimer | None = None,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._clock_ns = clock_ns
        self._timer = timer or QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._service_deadline)
        self._state = QuickPacerState(float(target_hz))
        self._demands = QuickFrameDemand.NONE
        self._visualizer_sync: Callable[[], bool] | None = None
        self._paused = False
        self._closed = False

    @property
    def target_hz(self) -> float:
        return self._state.target_hz

    @property
    def demands(self) -> QuickFrameDemand:
        return self._demands

    def is_active(self) -> bool:
        return bool(self._demands) and not self._paused and not self._closed

    def set_demand(self, reason: QuickFrameDemand, active: bool) -> None:
        """Add or remove one continuous-frame reason.

        Adding the first reason starts with one immediate opportunity. Removing
        the last reason stops the timer and discards its old deadline so an
        eventual resume cannot replay idle-time debt.
        """

        if self._closed:
            raise RuntimeError("Quick frame pacer is closed")
        allowed = int(
            QuickFrameDemand.TRANSITION
            | QuickFrameDemand.VISUALIZER
            | QuickFrameDemand.WIDGET_ANIMATION
        )
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

        if previous == QuickFrameDemand.NONE and self._demands and not self._paused:
            self._state.start(self._clock_ns())
            self._service_deadline()
        elif previous and self._demands == QuickFrameDemand.NONE:
            self._timer.stop()
            self._state.stop()

    def set_transition_active(self, active: bool) -> None:
        self.set_demand(QuickFrameDemand.TRANSITION, active)

    def set_visualizer_active(self, active: bool) -> None:
        self.set_demand(QuickFrameDemand.VISUALIZER, active)

    def set_widget_animation_active(self, active: bool) -> None:
        self.set_demand(QuickFrameDemand.WIDGET_ANIMATION, active)

    def set_visualizer_sync(
        self,
        synchronize: Callable[[], bool] | None,
    ) -> None:
        """Bind the one GUI-side visualizer publication edge.

        The visualizer's logical owner owns authored evolution. This callback
        only drains its latest immutable state on the existing display-local
        presentation opportunity; it never introduces another timer or clock.
        """

        if self._closed:
            raise RuntimeError("Quick frame pacer is closed")
        if synchronize is not None and not callable(synchronize):
            raise TypeError("visualizer synchronization edge must be callable")
        self._visualizer_sync = synchronize

    def set_target_hz(self, target_hz: float) -> None:
        """Retarget this display after its bound QScreen refresh changes."""

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
        replacement.skipped_deadlines = self._state.skipped_deadlines
        was_active = self.is_active()
        self._timer.stop()
        self._state = replacement
        if was_active:
            self._state.start(self._clock_ns())
            self._service_deadline()

    def stop(self) -> None:
        """Stop current presentation demand without permanently closing."""

        if self._closed:
            return
        self._demands = QuickFrameDemand.NONE
        self._paused = False
        self._timer.stop()
        self._state.stop()

    def pause(self) -> bool:
        """Suspend delivery while preserving active presentation reasons."""

        if self._closed or self._paused:
            return False
        self._paused = True
        self._timer.stop()
        self._state.stop()
        return True

    def resume(self) -> bool:
        """Resume preserved demand from now without replaying hidden-time debt."""

        if self._closed or not self._paused:
            return False
        self._paused = False
        if self._demands:
            self._state.start(self._clock_ns())
            self._service_deadline()
        return True

    def close(self) -> None:
        """Permanently close demand admission for display-runtime teardown."""

        if self._closed:
            return
        self.stop()
        self._visualizer_sync = None
        self._closed = True

    def describe(self) -> dict[str, object]:
        return {
            "target_hz": self._state.target_hz,
            "interval_ns": self._state.interval_ns,
            "active": self.is_active(),
            "paused": self._paused,
            "closed": self._closed,
            "demands": [
                demand.name.lower()
                for demand in (
                    QuickFrameDemand.TRANSITION,
                    QuickFrameDemand.VISUALIZER,
                )
                if self._demands & demand
            ],
            "requested_opportunities": self._state.requested_opportunities,
            "issued_update_requests": self._state.paced_requests,
            "skipped_deadlines": self._state.skipped_deadlines,
            "next_deadline_ns": self._state.next_deadline_ns,
        }

    def _service_deadline(self) -> None:
        if not self.is_active():
            return
        decision = self._state.consume(self._clock_ns())
        if decision.due_opportunities:
            visualizer_requested_present = False
            if self._demands & QuickFrameDemand.VISUALIZER:
                synchronize = self._visualizer_sync
                if synchronize is None:
                    raise RuntimeError(
                        "visualizer frame demand has no presentation synchronization owner"
                    )
                try:
                    # A successful visualizer sync is contractually complete only
                    # after VisualizerRenderItem.update() accepted the retained
                    # presentation request. That is already a scene
                    # presentation request. Issuing QQuickWindow.update() as well
                    # produced two swaps from the same pacer opportunity (observed
                    # ~120 fps on a 60 Hz display and ~250 on 165 Hz) without a
                    # second authored revision. Preserve the item update and only
                    # request the window when no fresh visualizer publication did.
                    visualizer_requested_present = bool(synchronize())
                except Exception:
                    logger.error(
                        "[QUICK_PACER] Visualizer presentation synchronization failed",
                        exc_info=True,
                    )
                    raise
            # Qt may coalesce update requests. One service callback issues at
            # most one presentation request for all deadlines already missed. A
            # visualizer item update also services transition/widget animation
            # state because the complete Quick window renders that opportunity.
            if not visualizer_requested_present:
                self._window.update()
        if self.is_active():
            self._timer.start(decision.next_delay_ms)
