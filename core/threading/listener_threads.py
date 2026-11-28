"""Blocking listeners: one thread per listener, living exactly as long as the blocking call it waits on.

A listener is a loop blocked on one source (a pipe's ``recv_bytes``) that ends by itself when that source closes:
its owner closes the source, never the thread. ThreadManager's pools and lanes cannot hold one: an IO-pool task
would occupy a FIFO worker for the source's whole life, and a named affinity worker outlives its listener (an idle
thread per closed source until the manager's shutdown) or, shared, queues a second listener behind the first,
which never returns while its source is open. So each listener gets its own daemon thread here, registered while it
runs (``snapshot()``, read by ``ThreadManager.get_diagnostic_snapshot``) and forgotten when it returns. Daemon, so
a source left open never holds the process's exit. No cadence, no poll, no per-message thread.

Users: the visualizer engine's wake pipe (``PacketMailbox.listen_for_wakes``).
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from core.logging.logger import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_running: dict[int, dict[str, Any]] = {}


class ListenerHandle:
    """A started listener: whether it still runs, and a bounded join for owners that wait for its end."""

    __slots__ = ("_thread", "name", "category")

    def __init__(self, thread: threading.Thread, name: str, category: str) -> None:
        self._thread = thread
        self.name = name
        self.category = category

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def join(self, timeout: float | None = None) -> bool:
        """Wait (bounded) for the listener to return; True when it has. Close its source first."""
        if threading.current_thread() is self._thread:
            return False
        self._thread.join(timeout)
        return not self._thread.is_alive()


def start_listener(target: Callable[[], None], *, name: str, category: str) -> ListenerHandle:
    """Run ``target`` (a loop that returns when its source closes) on its own daemon thread named ``name``."""
    if not callable(target):
        raise TypeError("a listener's target must be callable")
    label, kind = str(name or "srpss-listener"), str(category or "listener")

    def run() -> None:
        ident = threading.get_ident()
        with _lock:
            _running[ident] = {"name": label, "category": kind}
        try:
            target()
        except Exception:
            logger.exception("[THREADS] Listener %s ended with an error", label)
        finally:
            with _lock:
                _running.pop(ident, None)

    thread = threading.Thread(target=run, name=label, daemon=True)
    thread.start()
    return ListenerHandle(thread, label, kind)


def snapshot() -> dict[str, Any]:
    """The listeners running now (diagnostics)."""
    with _lock:
        rows = sorted(_running.values(), key=lambda row: (row["category"], row["name"]))
    return {"running": len(rows), "listeners": rows}


__all__ = ["ListenerHandle", "snapshot", "start_listener"]
