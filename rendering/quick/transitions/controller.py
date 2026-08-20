"""GUI-side monotonic lifecycle owner for Qt Quick transitions."""

from __future__ import annotations

from collections.abc import Callable
import math
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from core.logging.logger import get_logger
from ..frame_pacer import QuickFramePacer
from .state import (
    TransitionCompletion,
    TransitionOutcome,
    TransitionRequest,
    TransitionRun,
)


logger = get_logger(__name__)


class QuickTransitionController(QObject):
    """Own deadlines/completion; render code only samples immutable runs."""

    run_started = Signal(object)
    run_changed = Signal(object)
    run_finalized = Signal(object)

    def __init__(
        self,
        *,
        runtime_generation: int,
        frame_pacer: QuickFramePacer,
        clock_ns: Callable[[], int] = time.monotonic_ns,
        timer: QTimer | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        generation = int(runtime_generation)
        if generation < 0:
            raise ValueError("runtime generation must be non-negative")
        self._runtime_generation = generation
        self._frame_pacer = frame_pacer
        self._clock_ns = clock_ns
        self._timer = timer or QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_deadline)
        self._next_run_id = 1
        self._active_run: TransitionRun | None = None
        self._on_finalized: Callable[[TransitionCompletion], None] | None = None
        self._last_completion: TransitionCompletion | None = None
        self._completion_count = 0
        self._closed = False
        self._closing = False
        self._finalizing = False

    @property
    def active_run(self) -> TransitionRun | None:
        return self._active_run

    @property
    def last_completion(self) -> TransitionCompletion | None:
        return self._last_completion

    @property
    def is_active(self) -> bool:
        return self._active_run is not None

    def start(
        self,
        request: TransitionRequest,
        *,
        on_finalized: Callable[[TransitionCompletion], None] | None = None,
    ) -> TransitionRun:
        """Start one request; interruption requires an explicit cancel first."""

        if self._closed or self._closing:
            raise RuntimeError("Quick transition controller is closed")
        if self._finalizing:
            raise RuntimeError("cannot start a transition from finalization dispatch")
        if self._active_run is not None:
            raise RuntimeError("a Quick transition run is already active")
        if request.runtime_generation != self._runtime_generation:
            raise ValueError(
                "transition request generation does not match its display runtime"
            )

        run = TransitionRun.start(
            run_id=self._next_run_id,
            request=request,
            start_ns=self._clock_ns(),
        )
        self._next_run_id += 1
        self._active_run = run
        self._on_finalized = on_finalized
        try:
            self._frame_pacer.set_transition_active(True)
            self._schedule_deadline(run)
        except Exception:
            self._timer.stop()
            self._active_run = None
            self._on_finalized = None
            try:
                self._frame_pacer.set_transition_active(False)
            except Exception as release_exc:
                logger.exception(
                    "[QUICK] Failed to roll back transition pacing: %s",
                    release_exc,
                )
            raise
        self.run_changed.emit(run)
        self.run_started.emit(run)
        return run

    def finish_if_current(
        self,
        *,
        run_id: int,
        runtime_generation: int,
        now_ns: int | None = None,
    ) -> bool:
        """Finalize only the current expired run; reject stale callbacks."""

        run = self._active_run
        if (
            run is None
            or run.run_id != int(run_id)
            or run.request.runtime_generation != int(runtime_generation)
        ):
            return False
        now = self._clock_ns() if now_ns is None else int(now_ns)
        if now < run.end_ns:
            self._schedule_deadline(run, now_ns=now)
            return False
        self._finalize(
            run,
            outcome=TransitionOutcome.COMPLETED,
            reason="deadline",
            finalized_at_ns=now,
        )
        return True

    def cancel_current(self, *, reason: str) -> bool:
        """Snap the active run to its authored destination exactly once."""

        run = self._active_run
        if run is None:
            return False
        self._finalize(
            run,
            outcome=TransitionOutcome.CANCELLED_TO_DESTINATION,
            reason=str(reason or "cancelled"),
            finalized_at_ns=self._clock_ns(),
        )
        return True

    def close(self) -> None:
        if self._closed:
            return
        self._closing = True
        try:
            self.cancel_current(reason="runtime-retirement")
            self._timer.stop()
        finally:
            self._closing = False
            self._closed = True

    def describe(self) -> dict[str, object]:
        run = self._active_run
        completion = self._last_completion
        return {
            "runtime_generation": self._runtime_generation,
            "active": run is not None,
            "closed": self._closed,
            "next_run_id": self._next_run_id,
            "completion_count": self._completion_count,
            "active_run_id": None if run is None else run.run_id,
            "active_transition_id": (
                None if run is None else run.request.transition_id
            ),
            "active_source_identity": (
                None if run is None else run.request.source_image_identity
            ),
            "active_destination_identity": (
                None if run is None else run.request.destination_image_identity
            ),
            "last_completion": (
                None
                if completion is None
                else {
                    "run_id": completion.run_id,
                    "runtime_generation": completion.runtime_generation,
                    "outcome": completion.outcome.value,
                    "destination_image_identity": (
                        completion.destination_image_identity
                    ),
                    "finalized_at_ns": completion.finalized_at_ns,
                    "reason": completion.reason,
                }
            ),
        }

    def _on_deadline(self) -> None:
        run = self._active_run
        if run is None:
            return
        self.finish_if_current(
            run_id=run.run_id,
            runtime_generation=run.request.runtime_generation,
        )

    def _schedule_deadline(
        self,
        run: TransitionRun,
        *,
        now_ns: int | None = None,
    ) -> None:
        now = self._clock_ns() if now_ns is None else int(now_ns)
        remaining_ns = max(0, run.end_ns - now)
        self._timer.start(max(1, math.ceil(remaining_ns / 1_000_000.0)))

    def _finalize(
        self,
        run: TransitionRun,
        *,
        outcome: TransitionOutcome,
        reason: str,
        finalized_at_ns: int,
    ) -> None:
        if self._active_run is not run:
            return
        self._finalizing = True
        callback = self._on_finalized
        self._active_run = None
        self._on_finalized = None
        self._timer.stop()
        try:
            self._frame_pacer.set_transition_active(False)
        except Exception as exc:
            logger.exception("[QUICK] Transition pacing release failed: %s", exc)
        completion = TransitionCompletion(
            run_id=run.run_id,
            runtime_generation=run.request.runtime_generation,
            outcome=outcome,
            destination_image_identity=run.request.destination_image_identity,
            finalized_at_ns=int(finalized_at_ns),
            reason=str(reason),
        )
        self._last_completion = completion
        self._completion_count += 1
        try:
            self.run_changed.emit(None)
            self.run_finalized.emit(completion)
            if callback is not None:
                callback(completion)
        except Exception as exc:
            logger.exception("[QUICK] Transition finalization callback failed: %s", exc)
        finally:
            self._finalizing = False
