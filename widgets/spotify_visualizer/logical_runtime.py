"""The visualizer's authoritative logical cadence owner.

Current_Plan section 7. The logical simulation used to be driven by a recurring
GUI-thread `QTimer`, so every ordinary Qt event-loop stall became a hole in the
authored simulation itself: the installed runs show logical cadence falling to
~60-66 Hz against a ~90-100 Hz target with recurring 40-85 ms gaps, while
visualizer paint and GPU stayed in the sub-millisecond class and state->paint
stayed healthy. The renderer could not explain the holes; the owner could.

This module is deliberately Qt-free. It imports no QObject, QTimer, QWidget,
QPixmap or OpenGL, holds no reference to any of them, and must keep it that way -
a test pins it.

Two pieces:

`LatestStateMailbox`
    One slot holding the freshest current-generation render state plus a
    monotonically increasing revision. Publishing replaces whatever was there;
    superseded state is dropped rather than queued. There is no FIFO and no
    catch-up replay, so a slow consumer costs freshness, never a backlog.

`VisualizerLogicalRuntime`
    One standard Python thread owning one monotonic deadline sequence. Missed
    deadlines are skipped, never replayed. It is runtime-generation owned, is not
    a daemon, and quiesces and joins before its generation is destroyed.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from core.logging.logger import get_logger

logger = get_logger(__name__)


# A logical step that overruns this is reported once per run, bounded.
_SLOW_STEP_MS = 25.0

# How long `stop()` waits for the thread to leave its step before reporting.
_DEFAULT_JOIN_TIMEOUT_S = 2.0


@dataclass(frozen=True)
class LogicalPublication:
    """An immutable published logical frame plus its identity."""

    state: Any
    revision: int
    generation: int
    activation_id: int
    produced_ts: float


class LatestStateMailbox:
    """A single-slot latest-wins handoff from the logical runtime to the GUI.

    Deliberately not a queue. A 165-Hz display sampling a ~100-Hz producer sees
    each state at most once and never redraws an unchanged scene; a 60-Hz display
    sampling the same producer simply misses intermediate snapshots, which is
    correct because every authored event has already been integrated into the
    state before it could be replaced.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._publication: Optional[LogicalPublication] = None
        self._revision = 0
        self._dropped = 0

    def publish(
        self,
        state: Any,
        *,
        generation: int,
        activation_id: int = -1,
        now_ts: Optional[float] = None,
    ) -> int:
        """Replace the current slot. Returns the new revision."""

        with self._lock:
            if self._publication is not None:
                # Superseded before anyone sampled it. Counted, never queued.
                self._dropped += 1
            self._revision += 1
            self._publication = LogicalPublication(
                state=state,
                revision=self._revision,
                generation=int(generation),
                activation_id=int(activation_id),
                produced_ts=float(now_ts if now_ts is not None else time.monotonic()),
            )
            return self._revision

    def peek(self) -> Optional[LogicalPublication]:
        """Read the freshest publication without consuming it."""

        with self._lock:
            return self._publication

    def take(self) -> Optional[LogicalPublication]:
        """Read and clear the freshest publication."""

        with self._lock:
            publication = self._publication
            self._publication = None
            return publication

    def take_for_generation(self, generation: int) -> Optional[LogicalPublication]:
        """Take the freshest publication only if it belongs to `generation`.

        A retired generation's frame must never reach a replacement runtime.
        """

        with self._lock:
            publication = self._publication
            if publication is None:
                return None
            if int(publication.generation) != int(generation):
                self._publication = None
                return None
            self._publication = None
            return publication

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def superseded_count(self) -> int:
        """How many states were replaced before being sampled."""

        with self._lock:
            return self._dropped

    def clear(self) -> None:
        with self._lock:
            self._publication = None


class VisualizerLogicalRuntime:
    """One non-Qt thread owning the visualizer's logical cadence.

    The step callable is invoked with the monotonic timestamp of the deadline it
    is servicing. It must not touch QWidget, QPixmap or GL state; that ownership
    stays on the GUI thread.
    """

    def __init__(
        self,
        *,
        step: Callable[[float], None],
        interval_s: float,
        generation: int,
        name: str = "srpss-visualizer-logical",
    ) -> None:
        self._step = step
        self._interval_s = max(0.001, float(interval_s))
        self._generation = int(generation)
        self._name = str(name)

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._state_lock = threading.RLock()

        self._started_ts = 0.0
        self._steps = 0
        self._skipped_deadlines = 0
        self._slow_steps = 0
        self._step_failures = 0
        self._reported_step_failure = False
        self._last_step_ts = 0.0

    # -- identity ------------------------------------------------------
    @property
    def generation(self) -> int:
        return self._generation

    @property
    def interval_s(self) -> float:
        with self._state_lock:
            return self._interval_s

    def set_interval(self, seconds: float) -> None:
        """Change the authored cadence. Never used to hide jitter."""

        with self._state_lock:
            self._interval_s = max(0.001, float(seconds))
        self.wake()

    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    # -- lifecycle -----------------------------------------------------
    def start(self) -> bool:
        if self.is_running():
            return False
        self._stop_event.clear()
        self._wake_event.clear()
        self._started_ts = time.monotonic()
        # Explicitly not a daemon: this runtime must be joined by its owning
        # generation rather than silently outliving it at interpreter exit.
        thread = threading.Thread(target=self._run, name=self._name, daemon=False)
        self._thread = thread
        thread.start()
        logger.info(
            "[SPOTIFY_VIS][LOGICAL] Runtime started (generation=%s interval_ms=%.2f)",
            self._generation,
            self._interval_s * 1000.0,
        )
        return True

    def stop(self, *, timeout_s: float = _DEFAULT_JOIN_TIMEOUT_S) -> bool:
        """Quiesce and join. Returns True when the thread actually finished."""

        thread = self._thread
        self._stop_event.set()
        self._wake_event.set()
        if thread is None:
            return True
        thread.join(timeout=max(0.0, float(timeout_s)))
        finished = not thread.is_alive()
        if finished:
            self._thread = None
        else:
            logger.error(
                "[SPOTIFY_VIS][LOGICAL] Runtime did not quiesce within %.2fs "
                "(generation=%s steps=%d)",
                timeout_s,
                self._generation,
                self._steps,
            )
        logger.info(
            "[SPOTIFY_VIS][LOGICAL] Runtime stopped (generation=%s steps=%d "
            "skipped_deadlines=%d slow_steps=%d failures=%d joined=%s)",
            self._generation,
            self._steps,
            self._skipped_deadlines,
            self._slow_steps,
            self._step_failures,
            finished,
        )
        return finished

    def wake(self) -> None:
        """Nudge the loop out of its wait without moving the deadline sequence."""

        self._wake_event.set()

    # -- loop ----------------------------------------------------------
    def _run(self) -> None:
        next_deadline = time.monotonic()
        while not self._stop_event.is_set():
            interval = self.interval_s
            now = time.monotonic()

            if now < next_deadline:
                # Wait for the deadline, but stay interruptible so stop() and
                # cadence changes take effect immediately.
                self._wake_event.wait(next_deadline - now)
                self._wake_event.clear()
                continue

            behind = now - next_deadline
            if behind >= interval:
                # The loop was held off. Advance the sequence past the deadlines
                # that can no longer be serviced instead of replaying them: this
                # is a latest-state simulation, not a backlog.
                missed = int(behind // interval)
                self._skipped_deadlines += missed
                next_deadline += interval * missed
            next_deadline += interval

            started = time.perf_counter()
            try:
                self._step(now)
            except Exception:
                self._step_failures += 1
                if not self._reported_step_failure:
                    self._reported_step_failure = True
                    logger.error(
                        "[SPOTIFY_VIS][LOGICAL] Logical step raised; cadence continues",
                        exc_info=True,
                    )
            else:
                self._reported_step_failure = False
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if elapsed_ms >= _SLOW_STEP_MS:
                self._slow_steps += 1
            self._steps += 1
            self._last_step_ts = now

    # -- accounting ----------------------------------------------------
    def describe(self) -> dict:
        return {
            "generation": self._generation,
            "running": self.is_running(),
            "interval_ms": round(self.interval_s * 1000.0, 3),
            "steps": self._steps,
            "skipped_deadlines": self._skipped_deadlines,
            "slow_steps": self._slow_steps,
            "step_failures": self._step_failures,
        }
