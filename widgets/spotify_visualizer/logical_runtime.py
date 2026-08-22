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
    Bounded protected results are merged into the newest unread state.

`VisualizerLogicalRuntime`
    One standard Python thread owning one monotonic deadline sequence. Missed
    deadlines are skipped, never replayed. It is runtime-generation owned, is not
    a daemon, and quiesces and joins before its generation is destroyed.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)


# A logical step that overruns this is reported once per run, bounded.
_SLOW_STEP_MS = 25.0

# How long `stop()` waits for the thread to leave its step before reporting.
_DEFAULT_JOIN_TIMEOUT_S = 2.0

# The deadline clock. `time.monotonic()` is `GetTickCount64()` on this Windows
# build - measured resolution 15.625 ms - so a deadline sequence built on it can
# only ever observe time advancing in ~16 ms steps. That is precisely why the
# first wiring attempt locked at ~63.9-64.0 Hz against an 11.11 ms request with
# ~29% of deadlines reported missed while every callback was fast and no step
# failed. `perf_counter()` is `QueryPerformanceCounter()`, measured resolution
# 0.0001 ms, and is monotonic on every platform SRPSS targets.
_clock = time.perf_counter

# Longest single sleep inside a wait. Bounded so `stop()` stays prompt without
# busy-spinning: the thread really sleeps, it just re-checks the stop flag
# between slices.
_MAX_SLEEP_SLICE_S = 0.004


# The sentinel for an unassigned generation/activation identity.
UNASSIGNED_IDENTITY = -1


def coerce_identity(value: Any, *, missing: int = UNASSIGNED_IDENTITY) -> int:
    """Coerce a generation/activation identity, preserving a valid integer 0.

    Runtime and engine identity counters both start at `0` (see
    `ScreensaverEngine._runtime_generation` and `_SpotifyBeatEngine._generation_id`
    / `_activation_id`), so `0` is a real, fenceable identity - not "unassigned."
    The old `int(value or -1)` coercion collapsed that valid zero into the
    invalid sentinel through truthiness: the first installed run started its
    logical runtime as `generation=-1`, which disabled the presentation fence
    (`generation >= 0`) for the entire first generation. Only `None`, a missing
    attribute, or a non-integer maps to the sentinel here; `0` stays `0`.
    """

    if value is None:
        return missing
    try:
        return int(value)
    except (TypeError, ValueError):
        return missing


@dataclass(frozen=True)
class LogicalPublication:
    """An immutable published logical frame plus its identity."""

    state: Any
    revision: int
    generation: int
    activation_id: int
    produced_ts: float


_MAX_PROTECTED_EDGE_KINDS = 8


def _coalesce_protected_state(previous: Any, incoming: Any) -> Any:
    """Carry bounded short-lived results into the newest unread state."""

    previous_edges = getattr(previous, "protected_edges", ())
    incoming_edges = getattr(incoming, "protected_edges", ())
    if not isinstance(previous_edges, tuple) or not previous_edges:
        return incoming
    if not isinstance(incoming_edges, tuple):
        return incoming
    if getattr(previous, "mode_id", None) != getattr(incoming, "mode_id", None):
        return incoming
    if getattr(previous, "engine_generation", None) != getattr(
        incoming,
        "engine_generation",
        None,
    ):
        return incoming

    merged: dict[str, Any] = {}
    for edge in previous_edges + incoming_edges:
        kind = getattr(edge, "kind", None)
        token = getattr(edge, "token", None)
        if not isinstance(kind, str) or not isinstance(token, int):
            return incoming
        current = merged.get(kind)
        if current is None or token >= current.token:
            merged[kind] = edge
    if len(merged) > _MAX_PROTECTED_EDGE_KINDS:
        raise RuntimeError(
            "visualizer protected-edge kinds exceeded the bounded mailbox contract"
        )
    protected_edges = tuple(merged[kind] for kind in sorted(merged))
    if protected_edges == incoming_edges:
        return incoming
    try:
        return replace(incoming, protected_edges=protected_edges)
    except TypeError:
        return incoming


class LatestStateMailbox:
    """A single-slot latest-wins handoff from the logical runtime to the GUI.

    Deliberately not a queue. A 165-Hz display sampling a ~100-Hz producer sees
    each state at most once and never redraws an unchanged scene; a 60-Hz display
    sampling the same producer simply misses intermediate snapshots, which is
    correct because every authored event has already been integrated into the
    state before it could be replaced. Short-lived protected results coalesce
    into that newest unread state rather than creating a second slot.
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
            previous = self._publication
            if previous is not None:
                # Superseded before anyone sampled it. Counted, never queued.
                self._dropped += 1
                if (
                    previous.generation == int(generation)
                    and previous.activation_id == int(activation_id)
                ):
                    state = _coalesce_protected_state(previous.state, state)
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
        self._started_ts = _clock()
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
        """Nudge the loop out of its wait without moving the deadline sequence.

        `_wait_until` observes `_wake_event`, so this truthfully interrupts the
        current bounded sleep rather than waiting out the remaining slice: a
        `set_interval()` or `wake()` takes effect within one loop turn, and the
        loop re-reads the interval before waiting again. It does not restore the
        old `Event.wait(timeout)` deadline wait - the deadline is still a
        high-resolution `time.sleep()`, so the Windows ~15.6 ms quantisation
        cannot come back.
        """

        self._wake_event.set()

    # -- loop ----------------------------------------------------------
    def _wait_until(self, deadline: float) -> None:
        """Sleep until `deadline`, interruptibly, without a coarse wait.

        `threading.Event.wait(timeout)` is independently quantised to the same
        ~15.6 ms Windows tick as `time.monotonic()`; measured against a
        high-resolution clock it still delivers ~64 Hz with ~29% of an 11.11 ms
        deadline sequence missed. `time.sleep()` uses a high-resolution waitable
        timer on this platform and delivers the requested cadence, so the wait
        is a bounded sleep with a stop check between slices. That is a real
        sleep, not a spin.

        A `stop()` or `wake()` returns promptly: both are checked between
        slices, so the maximum a wake waits is one `_MAX_SLEEP_SLICE_S`. The
        wake flag is checked but not cleared here - the run loop clears it after
        this returns so it can re-read the interval before waiting again.
        """

        while not self._stop_event.is_set():
            if self._wake_event.is_set():
                return
            remaining = deadline - _clock()
            if remaining <= 0.0:
                return
            time.sleep(min(remaining, _MAX_SLEEP_SLICE_S))

    def _run(self) -> None:
        next_deadline = _clock()
        while not self._stop_event.is_set():
            interval = self.interval_s
            now = _clock()

            if now < next_deadline:
                self._wait_until(next_deadline)
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

            started = _clock()
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
            elapsed_ms = (_clock() - started) * 1000.0
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
