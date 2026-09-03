"""Headless GC attribution for the P0 lead-B Gen2 hitch.

Gen2 is stop-the-world: its wall time = its scan cost, which is O(tracked
container objects). This harness attributes:

1. gen2 cost vs tracked-object count (the cost model);
2. the real Bubble tick's per-frame container churn (what feeds gen0->gen1->gen2);
3. how often the Bubble cadence triggers a gen2 at the runtime thresholds;
4. the effect of gc.freeze() on gen2 cost.
"""
from __future__ import annotations

import gc
import os
import sys
import time
import tracemalloc

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime  # noqa: E402


def _time_gc2() -> float:
    t0 = time.perf_counter()
    gc.collect(2)
    return (time.perf_counter() - t0) * 1000.0


def cost_model():
    print("=" * 70)
    print("1. gen2 scan cost vs tracked-object count")
    print("=" * 70)
    gc.collect(2)
    retained = []
    for target in (0, 50_000, 100_000, 200_000, 400_000, 800_000):
        while len(retained) < target:
            # Nested tracked containers, like real retained app state.
            retained.append({"a": [1, 2, 3], "b": (retained and retained[-1]) or None})
        ms = _time_gc2()
        print(f"  tracked~{len(retained):>8,}  gen2_scan={ms:7.2f} ms  "
              f"gc_objects={len(gc.get_objects()):,}")
    del retained
    gc.collect(2)


def _payloads():
    energy = {
        "bass": 0.4, "mid": 0.3, "high": 0.2, "overall": 0.3,
        "smooth_mid": 0.3, "smooth_high": 0.2, "crest": 0.1,
        "pulse_bass": 0.4, "pulse_mid": 0.3, "pulse_high": 0.2, "pulse_overall": 0.3,
    }
    settings = {
        "bubble_big_count": 8, "bubble_small_count": 25,
        "bubble_surface_reach": 0.6, "bubble_stream_direction": "up",
        "bubble_stream_constant_speed": 0.5, "bubble_stream_speed_cap": 2.0,
        "bubble_stream_reactivity": 0.5, "bubble_rotation_amount": 0.5,
        "bubble_drift_amount": 0.5, "bubble_group_drift": False,
        "bubble_drift_speed": 0.5, "bubble_drift_frequency": 0.5,
        "bubble_drift_direction": "random", "bubble_big_size_max": 0.038,
        "bubble_small_size_max": 0.018, "bubble_trail_strength": 0.0,
        "bubble_ghosting_enabled": False, "bubble_bounce_big_pct": 70,
        "bubble_bounce_small_pct": 30, "bubble_bounce_big_speed": 0.8,
        "bubble_bounce_small_speed": 0.5, "bubble_bounce_same_only": False,
        "bubble_collision_pop_mode": "off", "_event_scheduler": None,
    }
    pulse = {
        "bass": 0.4, "mid_high": 0.25, "big_bass_pulse": 0.5,
        "small_freq_pulse": 0.5, "big_specular_max_size": 2.5,
        "big_visual_smoothing": 0.5, "big_contraction_bias": 1.0,
        "big_size_clamp": 4.0,
    }
    return energy, settings, pulse


def churn(ticks: int = 900, hz: float = 90.0):
    print("\n" + "=" * 70)
    print(f"2/3. real Bubble tick churn over {ticks} ticks (~{ticks/hz:.0f}s @ {hz:.0f}Hz)")
    print("=" * 70)
    runtime = BubbleFrameRuntime()
    energy, settings, pulse = _payloads()

    # Warm up (first-frame construction) then reset counters.
    now = 1000.0
    dt = 1.0 / hz
    for _ in range(5):
        now += dt
        runtime.advance(
            dt=dt, energy=dict(energy), settings=dict(settings), pulse=dict(pulse),
            source_timestamp=now, authored_timestamp=now, runtime_generation=0,
            engine_generation=0, activation_id=0, playing=True, source_ready=True,
            source_generation=0, source_activation_id=0, edge_token=1,
        )
    gc.collect()

    gc.disable()  # count triggers manually via thresholds we emulate
    obj_before = len(gc.get_objects())
    stats_before = [dict(s) for s in gc.get_stats()]
    tracemalloc.start()
    snap0 = tracemalloc.take_snapshot()

    t0 = time.perf_counter()
    for i in range(ticks):
        now += dt
        runtime.advance(
            dt=dt, energy=dict(energy), settings=dict(settings), pulse=dict(pulse),
            source_timestamp=now, authored_timestamp=now, runtime_generation=0,
            engine_generation=0, activation_id=0, playing=True, source_ready=True,
            source_generation=0, source_activation_id=0, edge_token=(i % 7) + 1,
        )
    wall = (time.perf_counter() - t0) * 1000.0

    snap1 = tracemalloc.take_snapshot()
    obj_after = len(gc.get_objects())
    gc.enable()

    print(f"  wall={wall:.1f}ms  mean_tick={wall/ticks:.3f}ms")
    print(f"  live gc objects: before={obj_before:,} after={obj_after:,} "
          f"delta={obj_after-obj_before:+,}  (retention, not churn)")

    top = snap1.compare_to(snap0, "lineno")[:8]
    print("  top allocation sites (net over the run):")
    for stat in top:
        frame = stat.traceback[0]
        loc = f"{os.path.basename(frame.filename)}:{frame.lineno}"
        print(f"    {stat.size_diff/1024:+8.1f} KiB  count {stat.count_diff:+7d}  {loc}")
    tracemalloc.stop()

    # Estimate allocations/tick by counting objects created per tick with gc off.
    gc.collect()
    base = len(gc.get_objects())
    runtime.advance(
        dt=dt, energy=dict(energy), settings=dict(settings), pulse=dict(pulse),
        source_timestamp=now + dt, authored_timestamp=now + dt, runtime_generation=0,
        engine_generation=0, activation_id=0, playing=True, source_ready=True,
        source_generation=0, source_activation_id=0, edge_token=2,
    )
    per_tick_live = len(gc.get_objects()) - base
    print(f"  net tracked-object delta for ONE tick (post-warm): {per_tick_live:+d}")


def freeze_effect():
    print("\n" + "=" * 70)
    print("4. gc.freeze() effect on gen2 cost")
    print("=" * 70)
    # Build a realistic retained set, then compare gen2 cost with/without freeze.
    retained = [{"a": [1, 2, 3], "b": None} for _ in range(300_000)]
    gc.collect(2)
    before = _time_gc2()
    gc.freeze()
    frozen = gc.get_freeze_count()
    after = _time_gc2()
    print(f"  retained~{len(retained):,} tracked objects")
    print(f"  gen2 scan BEFORE freeze: {before:.2f} ms")
    print(f"  gc.freeze() moved {frozen:,} objects to the permanent generation")
    print(f"  gen2 scan AFTER  freeze: {after:.2f} ms  "
          f"({(1 - after/before)*100:.0f}% cheaper)")
    gc.unfreeze()
    del retained
    gc.collect(2)


if __name__ == "__main__":
    print(f"gc thresholds: {gc.get_threshold()}  gc enabled: {gc.isenabled()}")
    cost_model()
    churn()
    freeze_effect()
