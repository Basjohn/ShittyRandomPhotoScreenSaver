"""Benchmark stability helpers (``tools/bench_stability.py``): thread CPU time is charged only while
the thread runs, the load gate judges passes against the controls' quiet reference, fastest-repeat
sampling discards contended repeats, and system conditions are summarised and compared."""
from __future__ import annotations

import time
from time import perf_counter

from tools.bench_stability import (
    LoadGate,
    SystemSampler,
    ThreadCpuClock,
    environment_differs,
    lower_quartile,
    min_of_repeats,
    spread,
    summarise_environment,
)


def test_thread_cpu_time_ignores_time_spent_off_the_cpu():
    clock = ThreadCpuClock()
    start = clock.now()
    time.sleep(0.12)                      # off the CPU, as when another process holds the core
    slept = clock.now() - start
    start, wall = clock.now(), perf_counter()
    while perf_counter() - wall < 0.06:
        pass
    spun, wall = clock.now() - start, (perf_counter() - wall) * 1e3
    assert slept < 20.0
    assert 0.5 * wall < spun < 1.5 * wall


def test_the_gate_rejects_passes_whose_control_was_slowed():
    gate = LoadGate()
    quiet = [gate.record(gpu, 0.5) for gpu in (0.20, 0.21, 0.19, 0.22, 0.20, 0.20)]
    loaded = gate.record(0.40, 0.5)
    outlier = gate.record(0.05, 0.5)      # one freak-fast control must not become the reference
    assert all(gate.admits(i) for i in quiet) and not gate.admits(loaded) and gate.admits(outlier)
    assert gate.quiet_gpu() == lower_quartile([c[0] for c in gate.controls])
    assert gate.admits(gate.record(0.20, 900.0))     # wall CPU never gates: thread CPU answers CPU
    summary = gate.summary()
    assert summary["controls"] == 9 and summary["admitted"] == 8


def test_fastest_repeats_and_spread():
    assert min_of_repeats([[3.0, 1.0, 2.0], [5.0, 9.0, 4.0]]) == [1.0, 4.0]
    assert spread([1.0]) == 0.0 and spread([1.0, 1.5]) == 0.5


def test_conditions_are_summarised_and_differences_named():
    summary = summarise_environment([{"cpu_others": 4.0, "gpu_util": 10.0}, {"cpu_others": 40.0, "gpu_util": 12.0}])
    assert summary["cpu_others_median"] == 22.0 and summary["cpu_others_max"] == 40.0
    assert environment_differs({"cpu_others_median": 3.0}, {"cpu_others_median": 60.0}) == \
        ["other processes' CPU 3 -> 60"]
    assert environment_differs({"gpu_util_median": 5.0}, {"gpu_util_median": 9.0}) == []
    assert environment_differs({}, {"cpu_others_median": 60.0}) == []      # an old baseline without figures


def test_the_sampler_reports_rough_cpu_and_memory():
    sample = SystemSampler().sample()
    assert 0.0 <= sample["cpu_others"] <= 100.0 and 0.0 < sample["memory_used"] <= 100.0
