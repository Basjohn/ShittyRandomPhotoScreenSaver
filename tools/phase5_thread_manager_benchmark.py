"""Measure steady high-rate ThreadManager bookkeeping overhead.

This headless benchmark deliberately uses tiny general-COMPUTE tasks because
Phase 5 evidence identified task accounting and GUI delivery as possible owners.
It does not model or alter visualizer cadence, equations, or presentation.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import QCoreApplication

from core.threading.manager import ThreadManager, ThreadPoolType
from core.resources.manager import ResourceManager


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark high-rate ThreadManager task bookkeeping."
    )
    parser.add_argument("--duration-seconds", type=float, default=5.0)
    parser.add_argument("--tasks-per-second", type=float, default=165.0)
    parser.add_argument("--compute-workers", type=int, default=4)
    parser.add_argument("--resource-manager", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    duration = max(0.5, float(args.duration_seconds))
    rate = max(1.0, float(args.tasks_per_second))
    app = QCoreApplication.instance() or QCoreApplication([])
    resource_manager = ResourceManager() if args.resource_manager else None
    manager = ThreadManager(
        config={
            ThreadPoolType.IO: 1,
            ThreadPoolType.COMPUTE: max(1, int(args.compute_workers)),
        },
        resource_manager=resource_manager,
    )
    before_ui = manager.get_diagnostic_snapshot()["ui"]
    completed = 0
    completed_lock = threading.Lock()
    producer_done = threading.Event()

    def _complete(_result) -> None:
        nonlocal completed
        with completed_lock:
            completed += 1

    def _produce() -> None:
        interval = 1.0 / rate
        deadline = time.perf_counter()
        stop_at = deadline + duration
        while deadline < stop_at:
            manager.submit_compute_task(
                lambda: None,
                callback=_complete,
                category="benchmark.tiny_compute",
            )
            deadline += interval
            remaining = deadline - time.perf_counter()
            if remaining > 0.0:
                time.sleep(remaining)
        producer_done.set()

    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    producer = threading.Thread(target=_produce, name="phase5_benchmark_producer")
    producer.start()
    while not producer_done.is_set():
        app.processEvents()
        time.sleep(0.0005)
    producer.join()

    expected = manager.get_task_category_stats()["benchmark.tiny_compute"]["submitted"]
    deadline = time.perf_counter() + 5.0
    while completed < expected and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.0005)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.001)

    wall_s = time.perf_counter() - wall_start
    cpu_s = time.process_time() - cpu_start
    after_ui = manager.get_diagnostic_snapshot()["ui"]
    result = {
        "duration_seconds": duration,
        "target_tasks_per_second": rate,
        "submitted": expected,
        "completed": completed,
        "wall_seconds": wall_s,
        "process_cpu_seconds": cpu_s,
        "process_cpu_percent_of_one_core": 100.0 * cpu_s / max(wall_s, 1e-9),
        "ui_callbacks_delivered_delta": int(after_ui["delivered"])
        - int(before_ui["delivered"]),
        "ui_callbacks_queued_delta": int(after_ui["queued"])
        - int(before_ui["queued"]),
        "scheduled_single_shots_at_end": int(after_ui["scheduled_single_shots"]),
        "pool_stats": manager.get_pool_stats(),
        "resource_manager_enabled": bool(resource_manager is not None),
        "resource_manager_live_resources": (
            int(resource_manager.get_stats().get("total_resources", 0))
            if resource_manager is not None
            else 0
        ),
    }
    manager.shutdown(wait=True, timeout=2.0)
    if resource_manager is not None:
        resource_manager.cleanup_all()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if completed == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
