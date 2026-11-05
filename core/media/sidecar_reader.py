"""Blocking readers of sidecar processes (``parec``, ``pactl subscribe``) on ThreadManager workers.

A sidecar's stdout is read by one blocking loop that ends when the process exits
(its owner terminates it on stop). Each reader kind runs on its own named
ThreadManager affinity worker (a lazy single thread shut down with the manager),
so no backend creates raw threads (tests/unit/test_policy_compliance.py). Without
an app-shared ThreadManager the reader cannot start and the caller reports it.
"""
from __future__ import annotations

from typing import Any, Callable


def start_reader(worker: str, lane_id: str, reader: Callable[[], None]) -> Any:
    """Run *reader* on the named ThreadManager worker; return its lane handle."""

    from core.threading.manager import ThreadManager

    manager = ThreadManager.get_app_shared()
    if manager is None:
        raise RuntimeError(f"no app-shared ThreadManager for sidecar reader {worker}")
    lane = manager.create_affinity_lane(lane_id=lane_id, category="sidecar_reader", worker=worker)
    if not lane.submit(reader):
        lane.stop(wait=False)
        raise RuntimeError(f"sidecar reader lane {lane_id} rejected its reader")
    return lane


def stop_reader(lane: Any, timeout: float = 3.0) -> None:
    """Close the lane and wait (bounded) for a reader whose process was already ended."""

    if lane is not None:
        lane.stop(wait=True, timeout=timeout)


__all__ = ["start_reader", "stop_reader"]
