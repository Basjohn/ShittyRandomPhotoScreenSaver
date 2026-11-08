"""The engine worker's lifetime (native core P2b, work order 5 slice 5.7): the ``WorkerType.VISUALIZER`` process
exists only while a Visualizer uses it.

Imported only on the engine-worker path (the default on Windows; ``experiment_flags.visualizer_engine_worker_admitted``);
in process (Linux, ``--viz-in-process``), nothing here runs and no worker exists.

**Leases.** Every ``engine_worker_link.EngineWorkerLink`` holds one lease from its configure to its close (one
session). The worker is spawned lazily by the first link that finds it not running (``EngineWorkerLink._ensure_worker``)
and retired when the last lease goes, at the end of that GUI turn: the release queues one settle event, so a link
replaced inside one turn keeps the worker (a recovery's reconfigure retires the failed link and opens its replacement
in the same call; the owner's mode and preset activations never touch the link at all).

**Reload holds.** A display reload rebuilds the display generation with its Visualizer owner on a later event-loop
turn (the old generation's teardown, its destruction barrier, then the replacement's construction). A CUSTOM layout
commit or a monitor topology change holds the worker from the old generation's teardown until the replacement is
constructed (``engine.engine_lifecycle``: ``stop`` with a reload reason takes the hold, the replacement's construction
ends it), so the rebuilt owner adopts the running worker instead of paying a fresh spawn and session build. Nothing else
holds it: a Settings open (its dialog can stay open for minutes), the Visualizer switched off, an in-process fallback or
the app's exit retire the worker when its last owner goes. A hold that is never ended (a replacement that was never
constructed) keeps the worker only until the next hold ends or the supervisor shuts down.

**Retirement** (an IO task, never the GUI thread): ``supervisor.stop`` (the session's ``VIS_STOP``, queued by the link's
retire, ends the session first; then the worker's graceful ``SHUTDOWN`` and its reaping). Fenced: the task re-checks
under the lifetime lock that no lease or hold arrived after the settle and marks the role retiring; a link that
configures meanwhile treats the worker as not running and spawns, and its start (``serialised_start``) waits until the
retirement finished (one lock orders a retirement's stop and a link's start, both on IO threads). No timer, no poll: the
settle is a queued event and the retirement a one-off task.
"""
from __future__ import annotations

import contextlib
import itertools
import threading
from typing import Any, Iterator

from PySide6.QtCore import QObject, Qt, Signal

from core.logging.logger import get_logger

logger = get_logger(__name__)

#: The retirement's graceful bound (the session's stop, then the worker's shutdown), then termination.
RETIRE_TIMEOUT_S = 5.0

#: The engine's stop reasons that rebuild the display generation at once (``engine.engine_lifecycle.stop``): the worker
#: is held across them. Settings ("settings") is not one: its dialog holds the displays down for as long as it is open.
RELOAD_REASONS = frozenset({"custom_edit", "monitor_topology"})

_lock = threading.Lock()
_start_lock = threading.Lock()          # orders a retirement's stop and a link's start (IO threads only)
_tokens = itertools.count(1)
_leases: set[int] = set()
_holds: dict[int, str] = {}
_retiring = False
_supervisor: Any = None
_thread_manager: Any = None
_retirements = 0
_events: "_SettleEvents | None" = None


class _SettleEvents(QObject):
    """The settle, queued onto the GUI thread (one per release or hold end that left nothing holding the worker)."""

    settle = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.settle.connect(self._on_settle, Qt.ConnectionType.QueuedConnection)

    def _on_settle(self) -> None:
        _settle()


def _schedule_settle() -> None:
    global _events
    if _events is None:
        _events = _SettleEvents()          # created on the GUI thread (leases and holds are taken and ended there)
    _events.settle.emit()


def lease(supervisor: Any, thread_manager: Any) -> int:
    """A link's lease (its configure, before it looks for a running worker): the worker stays while any is held."""
    global _supervisor, _thread_manager
    with _lock:
        token = next(_tokens)
        _leases.add(token)
        _supervisor, _thread_manager = supervisor, thread_manager
    return token


def release(token: int | None) -> None:
    """The link closed (idempotent): with no lease and no hold left, the worker is retired at the end of this turn."""
    with _lock:
        if token not in _leases:
            return
        _leases.discard(token)
        idle = not _leases and not _holds
    if idle:
        _schedule_settle()


def retiring() -> bool:
    """Whether a retirement is stopping the worker now (a link that needs it spawns a fresh one instead)."""
    with _lock:
        return _retiring


def hold_for_reload(reason: str) -> int:
    """Hold the worker across a display reload (``RELOAD_REASONS``): a lease-free span that does not retire it."""
    with _lock:
        token = next(_tokens)
        _holds[token] = str(reason)
    return token


def end_hold(token: int | None) -> None:
    """The reload's replacement was constructed (or abandoned); idempotent. With no lease left (the replacement has no
    owner on the worker), the worker is retired at the end of this turn."""
    with _lock:
        if _holds.pop(token, None) is None:
            return
        idle = not _leases and not _holds
    if idle:
        _schedule_settle()


@contextlib.contextmanager
def serialised_start() -> Iterator[None]:
    """A link's start of the worker (an IO task): after any retirement in flight has stopped it."""
    with _start_lock:
        yield


def retire_if_unused(supervisor: Any) -> None:
    """IO thread: a spawn whose link closed while it ran (checkpoint audit 9, A9-L2) retires the worker it may have
    started when no lease or hold claims it (re-checked under the lock: a link that leased meanwhile keeps it). Never
    on the GUI thread: the stop waits for the worker."""
    from core.process.types import WorkerType

    if callable(getattr(supervisor, "stop", None)) and supervisor.is_running(WorkerType.VISUALIZER):
        _retire(supervisor)


def _settle() -> None:
    """GUI thread, at the end of the turn that released the last lease or hold: retire the worker if nothing took one
    meanwhile."""
    with _lock:
        if _leases or _holds or _supervisor is None:
            return
        supervisor, manager = _supervisor, _thread_manager
    from core.process.types import WorkerType

    if not callable(getattr(supervisor, "stop", None)) or not supervisor.is_running(WorkerType.VISUALIZER):
        return
    if manager is None:
        _retire(supervisor)                          # a bare rig without an IO lane
        return
    try:
        manager.submit_io_task(_retire, supervisor, category="engine_worker_retire")
    except Exception:                                # the lane is shutting down: the supervisor's shutdown reaps it
        logger.debug("[SPOTIFY_VIS][ENGINE_WORKER] Retirement not submitted (IO lane unavailable)", exc_info=True)


def _retire(supervisor: Any) -> None:
    """IO task: stop the worker unless a lease or hold arrived since the settle (re-checked under the lock)."""
    global _retiring, _retirements
    from core.process.types import WorkerType

    with _start_lock:
        with _lock:
            if _leases or _holds:
                return
            _retiring = True
        try:
            pid = (supervisor.get_visualizer_worker_usage_snapshot().get("visualizer_worker_pid")
                   if callable(getattr(supervisor, "get_visualizer_worker_usage_snapshot", None)) else None)
            supervisor.stop(WorkerType.VISUALIZER, timeout=RETIRE_TIMEOUT_S)
            with _lock:
                _retirements += 1
            logger.info("[SPOTIFY_VIS][ENGINE_WORKER] Engine worker retired: no Visualizer uses it (pid=%s)", pid)
        except Exception:
            logger.exception("[SPOTIFY_VIS][ENGINE_WORKER] Engine worker retirement failed")
        finally:
            with _lock:
                _retiring = False


def describe() -> dict:
    """Leases, holds, whether a retirement is in flight, and retirements so far (tests and diagnostics)."""
    with _lock:
        return {"leases": len(_leases), "holds": sorted(_holds.values()), "retiring": _retiring,
                "retirements": _retirements}


def reset_for_testing() -> None:
    """Tests only: forget every lease and hold (a test's links are closed or abandoned with it)."""
    global _supervisor, _thread_manager, _retiring, _retirements
    with _lock:
        _leases.clear()
        _holds.clear()
        _supervisor = _thread_manager = None
        _retiring = False
        _retirements = 0


__all__ = [
    "RELOAD_REASONS",
    "RETIRE_TIMEOUT_S",
    "describe",
    "end_hold",
    "hold_for_reload",
    "lease",
    "release",
    "reset_for_testing",
    "retire_if_unused",
    "retiring",
    "serialised_start",
]
