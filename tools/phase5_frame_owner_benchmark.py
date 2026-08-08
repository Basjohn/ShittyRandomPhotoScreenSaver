"""Measure the perf-gated compositor frame-owner snapshot hot path.

This is a deterministic headless projection.  It times the exact passive
owner snapshot used by compositor paint diagnostics and projects that cost at
the dual-display 165 Hz + 60 Hz presentation ceiling.  It does not replace an
installed GL/runtime performance run.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.threading.manager import ThreadManager, ThreadPoolType
from rendering.gl_compositor_pkg.compositor_metrics import _frame_owner_snapshot


DEFAULT_INVOCATIONS = 50_000
DEFAULT_REPEATS = 7
DUAL_DISPLAY_PRESENTATION_CEILING_HZ = 225.0


def _fixture() -> tuple[SimpleNamespace, ThreadManager]:
    manager = ThreadManager(
        config={
            ThreadPoolType.IO: 1,
            ThreadPoolType.COMPUTE: 1,
        }
    )
    media = SimpleNamespace(
        _thread_manager=manager,
        _perf_media_display_total=5,
        _perf_media_emit_total=2,
        _perf_media_update_request_total=4,
    )
    visualizer = SimpleNamespace(
        _thread_manager=manager,
        _vis_mode_str="bubble",
        _mode_transition_phase=0,
        _waiting_for_fresh_engine_frame=False,
        _waiting_for_fresh_frame=False,
        _bubble_compute_pending=False,
        _bubble_pending_result=None,
        _bubble_visible_source_ts=1.0,
        _bubble_visible_simulation_ts=1.0,
        _bubble_visible_render_state_ts=1.0,
    )
    overlay = SimpleNamespace(
        _perf_set_state_total=30,
        _perf_update_request_total=30,
        _perf_paint_total=28,
    )
    parent = SimpleNamespace(
        screen_index=0,
        _thread_manager=manager,
        media_widget=media,
        spotify_visualizer_widget=visualizer,
        _spotify_bars_overlay=overlay,
    )
    widget = SimpleNamespace(parent=lambda: parent)
    return widget, manager


def _time_ns(operation, invocations: int) -> float:
    started = time.perf_counter_ns()
    for _ in range(invocations):
        operation()
    return (time.perf_counter_ns() - started) / invocations


def run_benchmark(*, invocations: int, repeats: int) -> dict[str, object]:
    if invocations <= 0 or repeats < 3:
        raise ValueError("invocations must be positive and repeats must be at least 3")
    widget, manager = _fixture()
    try:
        for _ in range(1_000):
            _frame_owner_snapshot(widget)
        costs: list[float] = []
        controls: list[float] = []
        noop = lambda: None
        for repeat in range(repeats):
            operations = (
                (_frame_owner_snapshot, widget, costs),
                (lambda _widget: noop(), widget, controls),
            )
            if repeat % 2:
                operations = tuple(reversed(operations))
            for operation, argument, destination in operations:
                destination.append(
                    _time_ns(lambda op=operation, arg=argument: op(arg), invocations)
                )
        snapshot_ns = statistics.median(costs)
        control_ns = statistics.median(controls)
        added_ns = max(0.0, snapshot_ns - control_ns)
        projected_core_pct = (
            added_ns * DUAL_DISPLAY_PRESENTATION_CEILING_HZ / 1_000_000_000.0
        ) * 100.0
        return {
            "kind": "phase5_frame_owner_snapshot_projection",
            "production_operation": "compositor_metrics._frame_owner_snapshot",
            "fidelity": (
                "exact passive snapshot with a real ThreadManager and production "
                "locks/queue-depth reads; headless synthetic widget ownership graph"
            ),
            "invocations_per_repeat": invocations,
            "repeats": repeats,
            "dual_display_presentation_ceiling_hz": DUAL_DISPLAY_PRESENTATION_CEILING_HZ,
            "snapshot_median_ns_per_call": snapshot_ns,
            "control_median_ns_per_call": control_ns,
            "added_median_ns_per_call": added_ns,
            "projected_cpu_percent_of_one_core": projected_core_pct,
            "limitations": (
                "No Qt event dispatch, real QObject graph, GL paint, contention, "
                "logging, or frame-gap serialization."
            ),
        }
    finally:
        manager.shutdown(wait=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--invocations", type=int, default=DEFAULT_INVOCATIONS)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    args = parser.parse_args()
    print(json.dumps(run_benchmark(invocations=args.invocations, repeats=args.repeats), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
