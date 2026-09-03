"""Headless attribution harness for the P0 Visualizer hitch (GIL contention).

Purpose
-------
Prove/quantify, WITHOUT hijacking a display, why `Tick dt spike` warnings appear
on the Visualizer's authored cadence. The cadence runs on a dedicated pure-Python
thread (`VisualizerLogicalRuntime`, a high-resolution `time.sleep` deadline loop),
so its `dt` only spikes when some OTHER thread holds the GIL uninterruptibly.

Findings this harness reproduces (2026-09-03):

* CPython preempts the GIL every ~5 ms (`sys.getswitchinterval`), so pure-Python
  busy work and GIL-releasing psutil syscalls do NOT stall the logical thread.
* `Process.children(recursive=True)` and `Process.num_threads()` are Windows
  system-wide `NtQuerySystemInformation` enumerations that hold the GIL for the
  whole call. Back-to-back they reproduce the operator's 42-100 ms spikes.
* The partitioned `ProcessUsageCollector` (heavy sub-cadence) keeps light samples
  at ~1-3 ms with no system-wide enumeration.

See `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`.

Run: `python tools/viz_logical_gil_contention_harness.py`
"""
from __future__ import annotations

import gc
import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil  # noqa: E402

from core.performance.usage_sampler import ProcessUsageCollector  # noqa: E402
from widgets.spotify_visualizer.logical_runtime import (  # noqa: E402
    VisualizerLogicalRuntime,
)

SPIKE_MS = 42.0  # matches state._dt_spike_threshold_ms


def _time_ms(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000.0


def breakdown_collect(samples: int = 6) -> None:
    print("=" * 70)
    print("collect() cost breakdown (real ProcessUsageCollector, heavy every sample)")
    print("=" * 70)
    collector = ProcessUsageCollector(heavy_refresh_samples=1)
    main = psutil.Process(os.getpid())
    full = [(_time_ms(collector.collect), time.sleep(0.2))[0] for _ in range(samples)]
    print(f"collect() total_ms: first={full[0]:.1f} warm_mean={statistics.mean(full[1:]):.1f} "
          f"warm_max={max(full[1:]):.1f}")

    procs = [main] + main.children(recursive=True)
    parts = {
        "children(recursive)": lambda: main.children(recursive=True),
        "memory_info xN": lambda: [p.memory_info() for p in procs],
        "memory_full_info(USS) xN": lambda: [p.memory_full_info() for p in procs],
        "num_threads xN": lambda: [p.num_threads() for p in procs],
        "num_handles xN": lambda: [p.num_handles() for p in procs],
        "io_counters xN": lambda: [p.io_counters() for p in procs],
    }
    print(f"process tree size: {len(procs)}")
    for name, fn in parts.items():
        vals = [(_time_ms(fn), time.sleep(0.02))[0] for _ in range(5)]
        print(f"  {name:28s} mean={statistics.mean(vals):7.2f}ms max={max(vals):7.2f}ms")


def _logical_vs_background(background_fn, *, duration_s, logical_hz, period_s):
    dt_samples: list[tuple[float, float]] = []
    last = {"t": -1.0}

    def step(_deadline):
        now = time.perf_counter()
        if last["t"] >= 0.0:
            dt_samples.append((now, (now - last["t"]) * 1000.0))
        last["t"] = now

    runtime = VisualizerLogicalRuntime(
        step=step, interval_s=1.0 / logical_hz, generation=0, name="harness-logical"
    )
    windows: list[tuple[float, float]] = []
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            t0 = time.perf_counter()
            try:
                background_fn()
            except Exception:
                pass
            t1 = time.perf_counter()
            windows.append((t0, t1))
            stop.wait(max(0.0, period_s - (t1 - t0)))

    runtime.start()
    time.sleep(0.5)
    th = threading.Thread(target=loop, name="harness-bg", daemon=True)
    th.start()
    time.sleep(duration_s)
    stop.set()
    th.join(timeout=2.0)
    runtime.stop()
    return dt_samples, windows


def _report(label, dt_samples, windows, logical_hz):
    dts = [d for _, d in dt_samples]
    target = 1000.0 / logical_hz
    spikes = [(ts, d) for ts, d in dt_samples if d >= SPIKE_MS]

    def near(ts):
        return any(s - target / 1000.0 <= ts <= e + 2 * target / 1000.0
                   for (s, e) in windows)

    coin = sum(1 for ts, _ in spikes if near(ts))
    win_ms = [(e - s) * 1000.0 for s, e in windows]
    print(f"\n[{label}]  steps={len(dts)} target={target:.2f}ms "
          f"median={statistics.median(dts):.2f} max={max(dts):.2f}")
    if win_ms:
        print(f"  bg calls={len(windows)} self_ms mean={statistics.mean(win_ms):.1f} "
              f"max={max(win_ms):.1f}")
    print(f"  spikes>={SPIKE_MS:.0f}ms: {len(spikes)}  coincident_with_bg: {coin}/{len(spikes)}")


def contention_experiment(duration_s=10.0, logical_hz=90.0) -> None:
    print("\n" + "=" * 70)
    print("GIL contention vs real VisualizerLogicalRuntime")
    print("=" * 70)

    def busy_100ms():
        end = time.perf_counter() + 0.100
        x = 0
        while time.perf_counter() < end:
            x += 1

    _report("pure-python 100ms every 2s (preemptible - expect ~0 spikes)",
            *_logical_vs_background(busy_100ms, duration_s=duration_s,
                                    logical_hz=logical_hz, period_s=2.0), logical_hz=logical_hz)

    main = psutil.Process(os.getpid())

    def hammer_sysinfo():
        try:
            main.children(recursive=True)
            main.num_threads()
        except psutil.Error:
            pass

    _report("children(recursive)+num_threads back-to-back (expect spikes)",
            *_logical_vs_background(hammer_sysinfo, duration_s=duration_s,
                                    logical_hz=logical_hz, period_s=0.0), logical_hz=logical_hz)

    _report("gc.collect(2) every 1s (stop-the-world, scales with heap)",
            *_logical_vs_background(lambda: gc.collect(2), duration_s=duration_s,
                                    logical_hz=logical_hz, period_s=1.0), logical_hz=logical_hz)


def after_fix_measurement() -> None:
    print("\n" + "=" * 70)
    print("after-fix: partitioned collector keeps light samples cheap")
    print("=" * 70)
    calls = {"children": 0, "num_threads": 0}
    real = psutil.Process(os.getpid())

    class _Counting:
        pid = real.pid

        def children(self, recursive=False):
            calls["children"] += 1
            return real.children(recursive=recursive)

        def num_threads(self):
            calls["num_threads"] += 1
            return real.num_threads()

        def __getattr__(self, name):
            return getattr(real, name)

    collector = ProcessUsageCollector(_Counting(), heavy_refresh_samples=8)
    per = [_time_ms(collector.collect) for _ in range(17)]
    heavy = [i for i, ms in enumerate(per) if ms > 8.0]
    light = [ms for i, ms in enumerate(per) if i not in heavy and i > 0]
    print(f"per-sample collect_ms: {[round(x, 1) for x in per]}")
    print(f"heavy indices: {heavy} (expect 0, 8, 16)")
    print(f"light mean={statistics.mean(light):.2f}ms max={max(light):.2f}ms  "
          f"children={calls['children']} num_threads={calls['num_threads']} (expect 3 each)")


if __name__ == "__main__":
    print(f"python switch interval = {sys.getswitchinterval() * 1000:.1f}ms")
    breakdown_collect()
    contention_experiment()
    after_fix_measurement()
