"""Bounded Phase 1 event-loop-recorder hot-path benchmark.

This is deliberately a deterministic, headless *projection*, not a replacement
for the GL/runtime performance gate.  It compares the CPU time and per-frame
work-duration p99 of the same 60 Hz presentation-shaped loop with and without
the production ``EventLoopStallRecorder.record_tick`` call at its normal 20 Hz
sampling cadence.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtGui import QImage

from core.performance.event_loop_recorder import EventLoopStallRecorder
from core.performance.resource_metrics import collect_resource_accounting
from core.resources.manager import ResourceManager
from core.threading.manager import Task, ThreadManager
from rendering.gl_compositor_pkg.metrics import _PaintMetrics
from utils.image_cache import ImageCache


DEFAULT_FRAME_RATE = 60
DEFAULT_RECORDER_INTERVAL_MS = 50
DEFAULT_DURATION_SECONDS = 5.0
DEFAULT_REPEATS = 7
DEFAULT_MAX_CPU_OVERHEAD_PERCENT = 2.0
# 0.25 ms is 1.5% of a 60 Hz (16.67 ms) frame budget.
DEFAULT_MAX_P99_DELTA_MS = 0.25
FROZEN_DISPLAY_FRAME_RATES_HZ = (165.0, 60.0)
EVENT_LOOP_RECORDER_RATE_HZ = 20.0
TASK_CATEGORY_SUBMISSIONS_PER_SECOND = 171.0
RESOURCE_SNAPSHOT_RATE_HZ = 1.0 / 15.0


@dataclass(frozen=True)
class RunMeasurement:
    cpu_seconds: float
    p99_frame_work_ms: float
    recorder_samples: int




@dataclass(frozen=True)
class ComponentCalibration:
    name: str
    rate_hz: float
    invocations_per_sample: int
    method: str
    fidelity: str
    added_nanoseconds_per_call: float


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return float(ordered[index])


def _presentation_work(frame_index: int, work_items: int) -> float:
    """Fixed CPU-only stand-in for bounded per-frame presentation work."""
    value = (frame_index + 1) * 0.0001
    for offset in range(work_items):
        value = math.fmod(value * 1.000000119 + (offset + 1) * 0.000013, 1.0)
    return value


def run_once(
    *,
    frame_count: int,
    frame_rate: int,
    work_items: int,
    recorder_enabled: bool,
) -> RunMeasurement:
    """Measure a fixed number of 60 Hz-shaped frames in one process."""
    if frame_count <= 0 or frame_rate <= 0 or work_items <= 0:
        raise ValueError("frame_count, frame_rate, and work_items must be positive")

    recorder: EventLoopStallRecorder | None = None
    recorder_period_frames = max(
        1, round((DEFAULT_RECORDER_INTERVAL_MS / 1000.0) * frame_rate)
    )
    if recorder_enabled:
        recorder = EventLoopStallRecorder(interval_ms=DEFAULT_RECORDER_INTERVAL_MS)
        # ``record_tick`` is the hot path invoked by the recorder's QTimer.
        # Prime the same state that ``start`` establishes without starting a GUI
        # event loop; the benchmark must remain safe in headless CI.
        recorder._running = True
        recorder._expected_at = DEFAULT_RECORDER_INTERVAL_MS / 1000.0

    frame_durations_ms: list[float] = []
    logical_time = 0.0
    cpu_started = time.process_time()
    checksum = 0.0
    for frame_index in range(frame_count):
        frame_started = time.perf_counter_ns()
        checksum += _presentation_work(frame_index, work_items)
        logical_time += 1.0 / frame_rate
        if recorder is not None and (frame_index + 1) % recorder_period_frames == 0:
            recorder.record_tick(logical_time)
        frame_durations_ms.append((time.perf_counter_ns() - frame_started) / 1_000_000.0)
    cpu_seconds = time.process_time() - cpu_started

    # Prevent a future simplification from accidentally removing the workload.
    if not math.isfinite(checksum):  # pragma: no cover - defensive invariant
        raise RuntimeError("presentation workload produced a non-finite checksum")
    return RunMeasurement(
        cpu_seconds=cpu_seconds,
        p99_frame_work_ms=_percentile(frame_durations_ms, 0.99),
        recorder_samples=0 if recorder is None else recorder.snapshot().samples,
    )


def _time_operation_ns(operation, invocations: int) -> float:
    started = time.perf_counter_ns()
    for _ in range(invocations):
        operation()
    return (time.perf_counter_ns() - started) / invocations


def _calibrate_component(
    *,
    name: str,
    rate_hz: float,
    invocations: int,
    repeats: int,
    enabled_factory,
    disabled_factory,
    method: str,
    fidelity: str,
) -> ComponentCalibration:
    """Alternately time a direct production operation and its paired control."""
    deltas: list[float] = []
    for repeat_index in range(repeats):
        order = (False, True) if repeat_index % 2 == 0 else (True, False)
        per_condition: dict[bool, float] = {}
        for enabled in order:
            factory = enabled_factory if enabled else disabled_factory
            operation, cleanup = factory()
            try:
                per_condition[enabled] = _time_operation_ns(operation, invocations)
            finally:
                cleanup()
        deltas.append(per_condition[True] - per_condition[False])
    # Use the upper quartile rather than the median so the projected budget
    # does not quietly benefit from timer/preemption noise.
    return ComponentCalibration(
        name=name,
        rate_hz=rate_hz,
        invocations_per_sample=invocations,
        method=method,
        fidelity=fidelity,
        added_nanoseconds_per_call=max(0.0, _percentile(deltas, 0.75)),
    )


def _event_loop_factory(*, enabled: bool):
    recorder = EventLoopStallRecorder(interval_ms=DEFAULT_RECORDER_INTERVAL_MS)
    recorder._running = True
    recorder._expected_at = DEFAULT_RECORDER_INTERVAL_MS / 1000.0
    logical_time = [0.0]

    def operation() -> None:
        logical_time[0] += DEFAULT_RECORDER_INTERVAL_MS / 1000.0
        if enabled:
            recorder.record_tick(logical_time[0])

    return operation, (lambda: None)


def _paint_metrics_frame_factory(*, target_fps: int):
    """Build a bounded steady-state production paint-metrics sample operation."""
    metrics = _PaintMetrics(label="phase1-projection", slow_threshold_ms=24.0)
    frame_interval_s = 1.0 / target_fps
    request_to_paint_s = min(0.001, frame_interval_s / 4.0)
    paint_duration_ms = 0.5
    state = {"request_ts": 10_000.0, "generation": 0}

    def operation() -> None:
        request_ts = state["request_ts"]
        generation = state["generation"]
        paint_start_ts = request_ts + request_to_paint_s
        paint_end_ts = paint_start_ts + paint_duration_ms / 1000.0
        metrics.record_render_request(accepted_update=True, request_ts=request_ts)
        metrics.record_paint_start(paint_start_ts, scene_generation=generation)
        metrics.record(
            paint_duration_ms,
            paint_start_ts=paint_start_ts,
            paint_end_ts=paint_end_ts,
        )
        state["request_ts"] = request_ts + frame_interval_s
        state["generation"] = generation + 1

    # Reach the collector's bounded deque steady state before timing it.
    for _ in range(metrics.samples.maxlen):
        operation()
    return operation, (lambda: None)


def _task_category_factory():
    manager = ThreadManager()
    task = Task(lambda: None, task_id="phase1_measurement_task", category="image.decode")

    def operation() -> None:
        manager._register_active_task(task)
        manager._unregister_active_task(task.task_id, outcome="completed")

    return operation, lambda: manager.shutdown(wait=False)


class _SnapshotProbeResource:
    pass


def _resource_snapshot_factory():
    manager = ResourceManager()
    cache = ImageCache(max_items=24, owner="phase1-image-cache", generation=1)
    for index in range(24):
        cache.put(
            f"phase1-cache-{index}",
            QImage(4, 4, QImage.Format.Format_ARGB32),
        )

    # Retain a conservative mixed 64-resource registry fixture while timing the
    # real aggregate helper used by both periodic and lifecycle diagnostics.
    retained = [_SnapshotProbeResource() for _ in range(64)]
    for index, resource in enumerate(retained):
        if index < 24:
            handle_type = "texture"
            resource_format = "RGBA8"
            tracked_bytes = 4_194_304
        elif index < 32:
            handle_type = "vbo"
            resource_format = "PIXEL_UNPACK_BUFFER" if index < 28 else "float32"
            tracked_bytes = 1_048_576
        else:
            handle_type = "program"
            resource_format = "GL_PROGRAM"
            tracked_bytes = None
        manager.register(
            resource,
            description=f"phase1-snapshot-{index}",
            tracked_bytes=tracked_bytes,
            owner="display-compositor",
            generation=1,
            dimensions=(1920, 1080) if handle_type == "texture" else None,
            format=resource_format,
            gl_handle_type=handle_type,
        )
    engine = SimpleNamespace(_image_cache=cache, resource_manager=manager)

    def operation():
        # Keep weakly-registered probe objects alive for every invocation.
        _ = retained
        return collect_resource_accounting(engine)

    def cleanup() -> None:
        _ = retained
        cache.clear()
        manager.cleanup_all()

    return operation, cleanup


def _noop_factory():
    return (lambda: None), (lambda: None)


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def run_benchmark(
    *,
    duration_seconds: float = DEFAULT_DURATION_SECONDS,
    repeats: int = DEFAULT_REPEATS,
    frame_rate: int = DEFAULT_FRAME_RATE,
    work_items: int = 15_000,
) -> dict[str, object]:
    """Return machine-readable projected overhead for paired fixed workloads."""
    if not 0.5 <= duration_seconds <= 30.0:
        raise ValueError("duration_seconds must be between 0.5 and 30")
    if not 3 <= repeats <= 25:
        raise ValueError("repeats must be between 3 and 25")
    if frame_rate <= 0 or work_items <= 0:
        raise ValueError("frame_rate and work_items must be positive")

    frame_count = int(round(duration_seconds * frame_rate))
    # Warm imports/caches without including that one-off cost in either side.
    run_once(
        frame_count=min(frame_count, frame_rate),
        frame_rate=frame_rate,
        work_items=work_items,
        recorder_enabled=False,
    )
    run_once(
        frame_count=min(frame_count, frame_rate),
        frame_rate=frame_rate,
        work_items=work_items,
        recorder_enabled=True,
    )

    baseline: list[RunMeasurement] = []
    enabled: list[RunMeasurement] = []
    # Preserve the paired presentation p99 comparison from the first probe.
    for repeat_index in range(repeats):
        order = (False, True) if repeat_index % 2 == 0 else (True, False)
        for recorder_enabled in order:
            measurement = run_once(
                frame_count=frame_count,
                frame_rate=frame_rate,
                work_items=work_items,
                recorder_enabled=recorder_enabled,
            )
            (enabled if recorder_enabled else baseline).append(measurement)

    components = (
        _calibrate_component(
            name="event_loop_recorder",
            rate_hz=EVENT_LOOP_RECORDER_RATE_HZ,
            invocations=50_000,
            repeats=repeats,
            enabled_factory=lambda: _event_loop_factory(enabled=True),
            disabled_factory=lambda: _event_loop_factory(enabled=False),
            method="EventLoopStallRecorder.record_tick",
            fidelity="exact production hot path, headless primed state",
        ),
        _calibrate_component(
            name="display_0_frame_recorder",
            rate_hz=FROZEN_DISPLAY_FRAME_RATES_HZ[0],
            invocations=50_000,
            repeats=repeats,
            enabled_factory=lambda: _paint_metrics_frame_factory(target_fps=165),
            disabled_factory=_noop_factory,
            method="_PaintMetrics.record_render_request + record_paint_start + record",
            fidelity="exact Phase 1 paint-delivery collector path; excludes outer is_perf_metrics_enabled gate",
        ),
        _calibrate_component(
            name="display_1_frame_recorder",
            rate_hz=FROZEN_DISPLAY_FRAME_RATES_HZ[1],
            invocations=50_000,
            repeats=repeats,
            enabled_factory=lambda: _paint_metrics_frame_factory(target_fps=60),
            disabled_factory=_noop_factory,
            method="_PaintMetrics.record_render_request + record_paint_start + record",
            fidelity="exact Phase 1 paint-delivery collector path; excludes outer is_perf_metrics_enabled gate",
        ),
        _calibrate_component(
            name="task_category_accounting",
            rate_hz=TASK_CATEGORY_SUBMISSIONS_PER_SECOND,
            invocations=20_000,
            repeats=repeats,
            enabled_factory=_task_category_factory,
            disabled_factory=_noop_factory,
            method="ThreadManager._register_active_task + _unregister_active_task",
            fidelity="exact bookkeeping methods; excludes executor submission and callback work",
        ),
        _calibrate_component(
            name="resource_aggregate_snapshot",
            rate_hz=RESOURCE_SNAPSHOT_RATE_HZ,
            invocations=2_000,
            repeats=repeats,
            enabled_factory=_resource_snapshot_factory,
            disabled_factory=_noop_factory,
            method="collect_resource_accounting(ImageCache + ResourceManager)",
            fidelity="exact aggregate helper with retained 24-cache + 64-registry synthetic live-resource proxy",
        ),
    )

    baseline_cpu = _median([item.cpu_seconds for item in baseline])
    enabled_cpu = _median([item.cpu_seconds for item in enabled])
    baseline_p99 = _median([item.p99_frame_work_ms for item in baseline])
    enabled_p99 = _median([item.p99_frame_work_ms for item in enabled])
    component_reports = []
    aggregate_cpu_seconds = 0.0
    for component in components:
        projected_cpu_seconds = (
            component.added_nanoseconds_per_call * component.rate_hz * duration_seconds
        ) / 1_000_000_000.0
        aggregate_cpu_seconds += projected_cpu_seconds
        component_reports.append({
            **asdict(component),
            "projected_cpu_seconds": projected_cpu_seconds,
            "projected_cpu_percent_of_one_core": (
                projected_cpu_seconds / duration_seconds
            ) * 100.0,
        })
    aggregate_cpu_percent = (
        0.0 if baseline_cpu <= 0 else (aggregate_cpu_seconds / baseline_cpu) * 100.0
    )

    return {
        "kind": "phase1_composite_diagnostic_budget_projection",
        "methodology": {
            "workload": "fixed CPU-only 60 Hz presentation-shaped loop",
            "calibration": "paired, alternating, amplified direct-operation timings; upper-quartile added cost projected to frozen rates",
            "real_gl_runtime": False,
            "limitations": "Not a full Qt/GL runtime measurement: no event dispatch, actual paint/compositor work, GPU, executor submission, callbacks, or real live-resource distribution. Resource snapshot fixture is an explicit retained 24-cache plus 64-registry proxy through the exact app-owned aggregate helper; lifecycle JSON serialization is excluded.",
        },
        "configuration": {
            "duration_seconds_per_condition": duration_seconds,
            "frame_rate_hz": frame_rate,
            "frames_per_condition": frame_count,
            "repeats_per_condition": repeats,
            "work_items_per_frame": work_items,
            "alternating_condition_order": True,
            "frozen_target": {
                "display_frame_recorder_rates_hz": list(FROZEN_DISPLAY_FRAME_RATES_HZ),
                "event_loop_recorder_rate_hz": EVENT_LOOP_RECORDER_RATE_HZ,
                "task_category_submissions_per_second": TASK_CATEGORY_SUBMISSIONS_PER_SECOND,
                "resource_snapshot_rate_hz": RESOURCE_SNAPSHOT_RATE_HZ,
            },
        },
        "baseline": asdict(RunMeasurement(
            cpu_seconds=baseline_cpu,
            p99_frame_work_ms=baseline_p99,
            recorder_samples=0,
        )),
        "instrumented": asdict(RunMeasurement(
            cpu_seconds=enabled_cpu,
            p99_frame_work_ms=enabled_p99,
            recorder_samples=int(_median([item.recorder_samples for item in enabled])),
        )),
        "components": component_reports,
        "overhead": {
            "cpu_estimation": "sum of conservative upper-quartile paired direct-operation costs projected to frozen target rates",
            "cpu_seconds": aggregate_cpu_seconds,
            "cpu_percent_of_baseline_workload": aggregate_cpu_percent,
            "projected_cpu_percent_of_one_core": (
                aggregate_cpu_seconds / duration_seconds
            ) * 100.0,
            "p99_frame_work_delta_ms": enabled_p99 - baseline_p99,
        },
    }


def _add_verdict(result: dict[str, object], *, max_cpu_percent: float, max_p99_delta_ms: float) -> dict[str, object]:
    overhead = result["overhead"]
    assert isinstance(overhead, dict)
    cpu_percent = float(overhead["cpu_percent_of_baseline_workload"])
    p99_delta_ms = float(overhead["p99_frame_work_delta_ms"])
    cpu_pass = cpu_percent <= max_cpu_percent
    p99_pass = p99_delta_ms <= max_p99_delta_ms
    return {
        **result,
        "thresholds": {
            "max_cpu_percent_of_baseline_workload": max_cpu_percent,
            "max_p99_frame_work_delta_ms": max_p99_delta_ms,
        },
        "verdict": {"cpu_pass": cpu_pass, "p99_pass": p99_pass, "pass": cpu_pass and p99_pass},
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=float, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--frame-rate", type=int, default=DEFAULT_FRAME_RATE)
    parser.add_argument("--work-items", type=int, default=15_000)
    parser.add_argument("--max-cpu-overhead-percent", type=float, default=DEFAULT_MAX_CPU_OVERHEAD_PERCENT)
    parser.add_argument("--max-p99-delta-ms", type=float, default=DEFAULT_MAX_P99_DELTA_MS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run_benchmark(
            duration_seconds=args.duration_seconds,
            repeats=args.repeats,
            frame_rate=args.frame_rate,
            work_items=args.work_items,
        )
        result = _add_verdict(
            result,
            max_cpu_percent=args.max_cpu_overhead_percent,
            max_p99_delta_ms=args.max_p99_delta_ms,
        )
    except ValueError as error:
        print(json.dumps({"pass": False, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    verdict = result["verdict"]
    assert isinstance(verdict, dict)
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
