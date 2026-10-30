"""Extruded Bubble logical-capture CPU cost by phase, from a real recording, headless (no window, no GL).

    .venv/Scripts/python tools/eb_logical_cost_probe.py --clip logs/visualizer_recordings/anything_mixed2.jsonl --preset 1
    .venv/Scripts/python tools/eb_logical_cost_probe.py --clip <clip> --preset 1 --set extruded_bubble_drift_specks=[0,0]
    .venv/Scripts/python tools/eb_logical_cost_probe.py --clip <clip> --preset 1 --alloc
    .venv/Scripts/python tools/eb_logical_cost_probe.py --clip <clip> --preset 1 --profile 30

The clip's recorded feature frames drive the production logical tick through ``replay_clip`` (the real authored
tick, EB capture, mailbox and Quick snapshot sync; deterministic logical clock at the recording's ~90 Hz). While it
runs, this tool wraps the phases of that path with ``perf_counter`` timers (tool-only patches, restored after) so the
coarse ``publish`` tick phase of ``--perf`` splits into: Settings read, controls, the simulation (collisions, free
drift per family and its packing, wakes, snapshot records), frame validation, render-parameter freezing, mailbox
insertion, plus the presentation sync the GUI side runs afterwards. Every figure is inclusive wall time per logical
tick; ``*_self`` rows subtract the nested rows. Payload sizes and populations are reported per tick.

``--alloc`` instead traces Python/NumPy allocations (tracemalloc; slows every phase, so timings are omitted) and
reports the peak bytes each tick allocates. ``--profile N`` prints the top N functions by cumulative time under
cProfile (also slowed; use it to localise, not to rank). ``--set KEY=JSON`` overrides the preset like
``extruded_bubble_capture.py``. Presets are operator-authored workloads: record which one was used, never pin values.

Scope: CPU work of the logical side only, on one thread, with no render thread competing for the GIL. It cannot show
GL/driver cost or cross-thread contention; ``tools/extruded_bubble_capture.py --passes`` times the GPU passes.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODE = "extruded_bubble"
WARMUP_SECONDS = 2.0


class _PhaseClock:
    """Inclusive wall time per labelled call, summed per logical tick."""

    def __init__(self) -> None:
        self.ticks: list[dict[str, float]] = []
        self.current: dict[str, float] | None = None

    def begin_tick(self) -> None:
        self.current = {}
        self.ticks.append(self.current)

    def add(self, label: str, ms: float) -> None:
        if self.current is not None:
            self.current[label] = self.current.get(label, 0.0) + ms

    def wrap(self, label, function):
        clock = self

        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                clock.add(label, (time.perf_counter() - start) * 1000.0)

        timed.__wrapped__ = function
        return timed


def _load_clip(path: Path, start: float, duration: float):
    from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame

    frames = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            frame = FeatureFrame.from_dict(json.loads(line))
            origin = frames[0].timestamp_us if frames else frame.timestamp_us
            if (frame.timestamp_us - origin) / 1e6 > start + duration:
                break
            frames.append(frame)
    if not frames:
        raise ValueError("the clip holds no frames")
    return FeatureClip("eb_logical_cost_probe", tuple(frames))


def _patches(clock: _PhaseClock, counts: list[dict[str, float]]):
    """Tool-only timing wrappers around the production EB logical path (all restored on exit)."""
    from tools.visualizer_replay import driver
    from widgets.spotify_visualizer import config_applier, logical_frame_capture as capture
    from widgets.spotify_visualizer import extruded_bubble_frame_runtime as frame_runtime
    from widgets.spotify_visualizer import extruded_bubble_material_paths as material
    from widgets.spotify_visualizer import extruded_bubble_simulation as simulation
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.extruded_bubble_wake import WakeField
    from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox
    from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync
    from widgets.spotify_visualizer.render_state import ExtrudedBubbleFrame

    families: dict[int, str] = {}

    def cloud_geometry(controls, direction, across, depth_axis, weights, family, count):
        start = time.perf_counter()
        geometry = material_cloud(controls, direction, across, depth_axis, weights, family, count)
        clock.add(f"drift.{family}.geometry", (time.perf_counter() - start) * 1000.0)
        families[id(geometry)] = family
        return geometry

    def offsets_advance(self, geometry, *args, **kwargs):
        start = time.perf_counter()
        try:
            return offsets_original(self, geometry, *args, **kwargs)
        finally:
            clock.add(f"drift.{families.get(id(geometry), 'cloud')}.advance", (time.perf_counter() - start) * 1000.0)

    def logical_tick(state):
        clock.begin_tick()
        start = time.perf_counter()
        try:
            return tick_original(state)
        finally:
            clock.add("logical_tick", (time.perf_counter() - start) * 1000.0)

    def snapshot(self, *args, **kwargs):
        start = time.perf_counter()
        result = snapshot_original(self, *args, **kwargs)
        clock.add("sim.snapshot", (time.perf_counter() - start) * 1000.0)
        counts.append({
            "bubbles": len(result.bubbles) // 8, "clusters": len(result.clusters) // 4,
            "wake_floats": len(result.wakes),
            "chain_bytes": len(result.drift_paths), "snow_bytes": len(result.snow_drift_offsets),
            "speck_bytes": len(result.speck_drift_offsets),
        })
        return result

    material_cloud = material.cloud_geometry
    offsets_original = material.ProceduralOffsets.advance
    tick_original = driver.logical_tick
    snapshot_original = simulation.ExtrudedBubbleSimulation._snapshot
    table = dict(capture._BUILTIN_MODE_CAPTURE)
    table[MODE] = clock.wrap("capture", capture._BUILTIN_MODE_CAPTURE[MODE])
    return [
        patch.object(driver, "logical_tick", logical_tick),
        patch.dict(capture._BUILTIN_MODE_CAPTURE, table),
        patch.object(tick_pipeline, "_publish_logical_state",
                     clock.wrap("publish", tick_pipeline._publish_logical_state)),
        patch.object(config_applier, "extruded_bubble_parameters",
                     clock.wrap("capture.settings_read", config_applier.extruded_bubble_parameters)),
        patch.object(frame_runtime, "controls_from_parameters",
                     clock.wrap("capture.controls", frame_runtime.controls_from_parameters)),
        patch.object(capture, "_render_parameters", clock.wrap("capture.render_parameters", capture._render_parameters)),
        patch.object(ExtrudedBubbleFrame, "__post_init__",
                     clock.wrap("capture.frame_validation", ExtrudedBubbleFrame.__post_init__)),
        patch.object(simulation.ExtrudedBubbleSimulation, "advance",
                     clock.wrap("sim", simulation.ExtrudedBubbleSimulation.advance)),
        patch.object(simulation.ExtrudedBubbleSimulation, "_collide",
                     clock.wrap("sim.collide", simulation.ExtrudedBubbleSimulation._collide)),
        patch.object(simulation.ExtrudedBubbleSimulation, "_advance_free_drift",
                     clock.wrap("sim.free_drift", simulation.ExtrudedBubbleSimulation._advance_free_drift)),
        patch.object(simulation.ExtrudedBubbleSimulation, "_snapshot", snapshot),
        patch.object(simulation.ExtrudedBubbleSimulation, "_wakes",
                     clock.wrap("sim.snapshot.wakes", simulation.ExtrudedBubbleSimulation._wakes)),
        patch.object(WakeField, "flow", clock.wrap("sim.snapshot.wakes.flow", WakeField.flow)),
        patch.object(material, "chain_geometry", clock.wrap("drift.chains.geometry", material.chain_geometry)),
        patch.object(material, "cloud_geometry", cloud_geometry),
        patch.object(material.MaterialPaths, "advance",
                     clock.wrap("drift.chains.advance", material.MaterialPaths.advance)),
        patch.object(material.ProceduralOffsets, "advance", offsets_advance),
        patch.object(LatestStateMailbox, "publish", clock.wrap("publish.mailbox", LatestStateMailbox.publish)),
        patch.object(QuickVisualizerPresentationSync, "sync_latest",
                     clock.wrap("gui.quick_sync", QuickVisualizerPresentationSync.sync_latest)),
    ]


# Rows whose own (exclusive) time is the row minus these nested rows.
_SELF = {
    "logical_tick": ("publish",),
    "publish": ("capture", "publish.mailbox"),
    "capture": ("capture.settings_read", "capture.controls", "sim", "capture.render_parameters",
                "capture.frame_validation"),
    "sim": ("sim.collide", "sim.free_drift", "sim.snapshot"),
    "sim.free_drift": ("drift.chains.geometry", "drift.chains.advance", "drift.snow.geometry", "drift.snow.advance",
                       "drift.specks.geometry", "drift.specks.advance"),
    "sim.snapshot": ("sim.snapshot.wakes",),
}


def _stats(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]
    return {"median": statistics.median(ordered), "p90": pick(0.90), "p99": pick(0.99), "max": ordered[-1],
            "mean": statistics.fmean(ordered)}


def _report(ticks: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    labels = sorted({label for tick in ticks for label in tick})
    rows = {label: _stats([tick.get(label, 0.0) for tick in ticks]) for label in labels}
    for parent, children in _SELF.items():
        if parent in labels:
            rows[f"{parent}_self"] = _stats([tick.get(parent, 0.0) - sum(tick.get(c, 0.0) for c in children)
                                             for tick in ticks])
    return rows


def _gc_recorder():
    events: list[tuple[int, float]] = []
    started: dict[str, float] = {}

    def callback(phase, info):
        if phase == "start":
            started["t"] = time.perf_counter()
        elif "t" in started:
            events.append((info["generation"], (time.perf_counter() - started.pop("t")) * 1000.0))

    return events, callback


def run(clip_path: Path, *, preset: int, overrides: dict, start: float, duration: float, alloc: bool,
        profile: int) -> dict:
    from PySide6.QtCore import QCoreApplication
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from tools.bench_stability import SystemSampler, summarise_environment
    from tools.visualizer_replay.driver import replay_clip

    app = QCoreApplication.instance() or QCoreApplication([])
    clip = _load_clip(clip_path, start, duration)
    activation = resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": preset - 1}, mode=MODE)
    settings = {**activation.resolved_config, **overrides}
    clock = _PhaseClock()
    counts: list[dict[str, float]] = []
    peaks: list[int] = []
    sampler = SystemSampler()
    conditions = [sampler.sample()]
    gc_events, gc_callback = _gc_recorder()
    patches = _patches(clock, counts)
    if alloc:
        import tracemalloc
        from tools.visualizer_replay import driver
        inner = driver.logical_tick

        def traced(state):
            tracemalloc.reset_peak()
            before = tracemalloc.get_traced_memory()[0]
            try:
                return inner(state)
            finally:
                peaks.append(tracemalloc.get_traced_memory()[1] - before)
    profiler = None
    for item in patches:
        item.start()
    gc.callbacks.append(gc_callback)
    try:
        if alloc:
            patch_alloc = patch.object(driver, "logical_tick", traced)
            patch_alloc.start()
            tracemalloc.start()
        if profile:
            import cProfile
            profiler = cProfile.Profile()
            profiler.enable()
        wall = time.perf_counter()
        replay_clip(clip, MODE, settings=settings)
        wall = time.perf_counter() - wall
    finally:
        if profiler is not None:
            profiler.disable()
        if alloc:
            tracemalloc.stop()
            patch_alloc.stop()
        gc.callbacks.remove(gc_callback)
        for item in reversed(patches):
            item.stop()
    conditions.append(sampler.sample())
    del app
    times = [(frame.timestamp_us - clip.frames[0].timestamp_us) / 1e6 for frame in clip.frames]
    skip = next((i for i, t in enumerate(times) if t >= start + WARMUP_SECONDS), 0)
    skip = max(skip, next((i for i, t in enumerate(times) if t >= start), 0))
    steady = clock.ticks[skip:]
    steady_counts = counts[skip:] if len(counts) == len(clock.ticks) else counts
    ticks_per_s = len(clip.frames) / max(times[-1] - times[0], 1e-9)
    document = {
        "source": str(clip_path.resolve()), "start_s": start, "duration_s": times[-1] - times[0],
        "ticks": len(clock.ticks), "steady_ticks": len(steady), "logical_hz": round(ticks_per_s, 1),
        "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "preset": preset, "preset_path": activation.preset_path, "overrides": overrides,
        "drift_settings": {name: settings.get(name) for name in sorted(settings)
                           if name.startswith("extruded_bubble_") and ("drift" in name or name in (
                               "extruded_bubble_particles", "extruded_bubble_bead_chains",
                               "extruded_bubble_emission_geometry", "extruded_bubble_wake_trails"))},
        "wall_s": round(wall, 2), "conditions": summarise_environment(conditions),
        "gc": {f"gen{g}": {"count": sum(1 for gen, _ in gc_events if gen == g),
                           "max_ms": round(max((ms for gen, ms in gc_events if gen == g), default=0.0), 2)}
               for g in (0, 1, 2)},
        "populations_median": {name: statistics.median(row[name] for row in steady_counts)
                               for name in (steady_counts[0] if steady_counts else {})},
        "populations_max": {name: max(row[name] for row in steady_counts)
                            for name in (steady_counts[0] if steady_counts else {})},
    }
    if alloc:
        document["alloc_peak_bytes_per_tick"] = _stats([float(v) for v in peaks[skip:]])
    elif not profile:
        document["phases_ms"] = _report(steady)
        budget = 1000.0 / ticks_per_s
        document["tick_budget_ms"] = round(budget, 2)
    if profile:
        import io
        import pstats
        text = io.StringIO()
        pstats.Stats(profiler, stream=text).sort_stats("cumulative").print_stats(profile)
        document["profile"] = text.getvalue()
    return document


def _print(document: dict) -> None:
    print(f"{document['preset_path']}  overrides={document['overrides']}")
    print(f"ticks {document['ticks']} ({document['steady_ticks']} steady) at {document['logical_hz']} Hz, "
          f"wall {document['wall_s']} s; conditions {document['conditions']}")
    print(f"gc {document['gc']}")
    print(f"populations median {document['populations_median']}")
    print(f"populations max    {document['populations_max']}")
    if "phases_ms" in document:
        print(f"{'phase (ms per tick)':38s} {'median':>8s} {'p90':>8s} {'p99':>8s} {'max':>8s} {'mean':>8s}")
        for label, row in sorted(document["phases_ms"].items()):
            print(f"{label:38s} " + " ".join(f"{row[k]:8.3f}" for k in ("median", "p90", "p99", "max", "mean")))
    if "alloc_peak_bytes_per_tick" in document:
        row = document["alloc_peak_bytes_per_tick"]
        print("alloc peak per tick (bytes): " + ", ".join(f"{k} {v / 1e6:.2f} MB" for k, v in row.items()))
    if "profile" in document:
        print(document["profile"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clip", type=Path, required=True, help="recorded feature JSONL (real-music recording)")
    parser.add_argument("--preset", type=int, default=1, help="the curated preset (1-based) used as the workload")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON", help="in-memory settings override")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--alloc", action="store_true", help="trace allocation peaks per tick instead of timing")
    parser.add_argument("--profile", type=int, default=0, metavar="N", help="cProfile: top N by cumulative time")
    parser.add_argument("--json", type=Path, help="also write the full result here")
    args = parser.parse_args()
    overrides = {}
    for item in args.set:
        key, _, value = item.partition("=")
        try:
            overrides[key] = json.loads(value)
        except json.JSONDecodeError:
            overrides[key] = value
    document = run(args.clip, preset=args.preset, overrides=overrides, start=args.start, duration=args.duration,
                   alloc=args.alloc, profile=args.profile)
    _print(document)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
