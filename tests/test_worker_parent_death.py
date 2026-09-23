"""Workers exit when the UI process dies without sending SHUTDOWN.

``daemon=True`` only reaps children when the parent exits normally (atexit).
A native crash or forced termination skipped that, leaving workers polling their
request queue forever (19 such orphans were found after crashing test runs).
"""

from __future__ import annotations

import multiprocessing
import os
import time

import psutil
import pytest

from core.process.types import WorkerType
from core.process.workers.base import BaseWorker


class _IdleWorker(BaseWorker):
    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.IMAGE

    def handle_message(self, msg):
        return None


def _run_idle_worker(request_queue, response_queue) -> None:
    _IdleWorker(request_queue, response_queue).run()


def _crashing_parent(report) -> None:
    requests = multiprocessing.Queue()
    responses = multiprocessing.Queue()
    worker = multiprocessing.Process(
        target=_run_idle_worker,
        args=(requests, responses),
        daemon=True,
    )
    worker.start()
    responses.get(timeout=30)  # WORKER_READY: the message loop is running
    report.put(worker.pid)
    report.close()
    report.join_thread()  # flush the feeder thread before the abrupt exit
    os._exit(3)  # no atexit: daemon children are not reaped


def test_worker_exits_after_parent_dies_without_shutdown() -> None:
    context = multiprocessing.get_context("spawn")
    report = context.Queue()
    parent = context.Process(target=_crashing_parent, args=(report,))
    parent.start()
    worker_pid = report.get(timeout=60)
    parent.join(timeout=30)
    assert parent.exitcode == 3

    try:
        worker = psutil.Process(worker_pid)
    except psutil.NoSuchProcess:
        return  # already gone
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline and worker.is_running():
        try:
            if worker.status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        time.sleep(0.1)
    alive = worker.is_running()
    if alive:
        worker.kill()
    assert not alive, "worker outlived its crashed parent"
