"""Quick overhead baseline: every showcase transition and Visualizer mode, offscreen, before/after.

Record one before and one after any major architecture addition (a shared primitive, a new
pass, a host change) and compare: an addition should leave everything that does not use it
unchanged. Transitions are drawn by the native core as the product draws them (``tools/native_transition_capture.py``, no
window): their release-showcase cases (canonical settings at High detail, fixture photographs), one wall-time figure
per frame relative to the native Crossfade control. Visualizer modes render through the production render host on one
offscreen GL 4.6 context (no window, no runtime) as their Guided Setup preview
snapshots (``tools/visualizer_cost_probe.visualizer_case``); how to run it, read it and what to expect:
``Docs/Reference/Benchmarks.md``. Per frame it records CPU submit (render
thread Python + GL calls) as wall time and as the thread's own CPU time, and GPU time
(``GL_TIME_ELAPSED``), flushing per frame as presentation does.

It is built to stay trustworthy while the machine is busy (``tools/bench_stability.py``):
transitions share one host and are measured **round-robin** (a burst of outside load spoils one
pass of many cases, not every pass of one case); every sampled frame is rendered ``REPEATS`` times, each
right after a **control** (one Crossfade frame drawn ``CONTROL_DRAWS`` times), and only the fastest repeat
of each counts. Each case is also recorded **relative to that control** (``gpu_rel``, ``cpu_rel``: the
case in Crossfade frames measured beside it): GPU clock state (an idle GPU downclocks between flushes;
Particle read 0.80 ms quiet and 0.38 ms with the GPU busy elsewhere), contention and a busy core's SMT
slowdown move case and control alike and cancel, so comparisons use the relative figures. Passes
whose control GPU time ran more than 35% over the controls' lower quartile are rejected and
re-measured in later rounds, up to ``--max-rounds``;
System usage (other processes' CPU, memory, GPU utilisation, clock and temperature) is sampled after
every pass and recorded per case and per run; a comparison prints both runs' conditions and warns
when they differ enough to mislead. CPU submit is also recorded as **thread CPU time**
(``QueryThreadCycleTime``), which other processes'
load does not inflate. Each case keeps its best admitted pass and its noise (the spread of its
admitted pass medians); a comparison flags a GPU or CPU rise only beyond its band **and** twice the
noise of either run.

    python tools/overhead_baseline.py                       # writes tools/baselines/overhead/<date>_<sha>.json
    python tools/overhead_baseline.py --compare OLD.json    # also compares against an older baseline
    python tools/overhead_baseline.py --compare-only OLD.json NEW.json
    python tools/overhead_baseline.py --match liquid_lens --compare OLD.json   # one effect, quickly

Each case also records two deterministic per-frame counts: OpenGL calls (every ``OpenGL.GL``
function, counted by wrapping the module) and Python function calls (``sys.setprofile``). They do
not drift between runs, so **any** rise is real added per-frame work (an extra pass, state change,
upload or Python step) and is flagged. GPU medians are flagged above ``max(20%, 0.05 ms)``. CPU
submit (thread CPU time when both runs have it) is flagged only above ``max(50%, 0.15 ms)`` and is a
hint, not proof. Takes about two minutes on a quiet machine, longer on a busy one.
Visualizer modes go through the same round-robin, control-relative passes (one production
Visualizer host on the shared context, each mode's Guided Setup preview snapshot) and record GL
calls through the probe's counter (its renderer modules) and Python calls like transitions.
(N5.2h: the ``surfaces`` and ``node_path`` cases measured the Python blit backdrop and background node, deleted at
the switch; the core's own costs are the reference checks' ``--cost`` rounds. A comparison against an older baseline
lists their rows as removed.)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Importing the Visualizer probe first matches production GL error checking (it switches per-call
# checking off before OpenGL.GL is first imported, as main.py does, and refuses otherwise).
import tools.visualizer_cost_probe  # noqa: E402,F401
from tools.bench_stability import (  # noqa: E402
    PairedBench, crossfade_control, environment_differs,
)

OUT = ROOT / "tools" / "baselines" / "overhead"
GPU_FLAG = (0.20, 0.05)     # ratio, ms
CPU_FLAG = (0.50, 0.15)


NATIVE_NOISE_FLAG = (0.20, 2.0)     # a transition is flagged above 20% of its control-relative cost and 2x its noise
NATIVE_CONTROL_FRAMES = 6


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def measure_transitions(bench: PairedBench, frames: int, passes: int, max_rounds: int) -> dict[str, dict[str, float]]:
    """Every showcase transition case (release-showcase settings, fixture photographs), drawn by the native core as
    the product draws it (``NativeTransitionCapture``: the native background layer in the process's hidden host).

    The figure is the frame's wall milliseconds (draw, submit and readback, ``NativeTransitionCapture.render``), not a
    GPU query: the core draws in its own context and thread. Each pass measures the native Crossfade control first and
    every case after it (round-robin, the order rotating each pass); a case's ``native_rel`` is its median over that
    pass's control median, so a busy machine moves case and control alike. The best (lowest) pass is kept and
    ``native_noise`` is the spread of the passes' relative figures. The core's own GPU cost is the reference checks'
    ``--cost`` rounds (``native/core/python/transition_route_check.py``)."""
    from tools.native_transition_capture import NativeTransitionCapture
    from tools.release_media import catalogue

    width, height = bench.capture.width, bench.capture.height
    capture = NativeTransitionCapture(width, height)
    keys = [c for c in catalogue() if c.kind == "transition" and (not bench.match or bench.match in f"{c.identity}/{c.variant}")]
    samples: dict[str, list[tuple[float, float, float, float]]] = {}
    try:
        control = capture.production_run("crossfade", 1000, {}, run_id=1)
        runs = {f"{c.identity}/{c.variant}": capture.production_run(c.identity, c.duration_ms, c.settings,
                                                                    run_id=index) for index, c in
                enumerate(keys, start=2)}
        progresses = [0.05 + 0.9 * index / max(1, frames - 1) for index in range(frames)]
        for pass_index in range(passes):
            capture.render(control, 0.5)                                     # the control's run started, untimed
            control_ms = _median([capture.render(control, 0.5)[1] for _ in range(NATIVE_CONTROL_FRAMES)])
            order = list(runs)
            offset = pass_index % max(1, len(order))
            for key in order[offset:] + order[:offset]:
                run = runs[key]
                for progress in (0.2, 0.5, 0.8):                             # the run started and its state built, untimed
                    capture.render(run, progress)
                times = [capture.render(run, progress)[1] for progress in progresses]
                ordered = sorted(times)
                median, p90 = _median(times), ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]
                samples.setdefault(key, []).append((median / control_ms if control_ms > 0 else 0.0, median, p90, control_ms))
                print(f"  transition {key:34s} pass {pass_index + 1}: {median:7.2f} ms ({median / control_ms:5.2f}x control)",
                      flush=True)
    finally:
        capture.close()
    results = {}
    for key, rows in samples.items():
        best = min(rows)
        rels = [row[0] for row in rows]
        results[key] = {"native_rel": best[0], "native_ms": best[1], "native_p90_ms": best[2], "control_ms": best[3],
                        "native_noise": (max(rels) - min(rels)) / best[0] if best[0] > 0 else 0.0, "passes": len(rows)}
    return results


def measure_visualizers(bench: PairedBench, frames: int, passes: int, max_rounds: int) -> dict[str, dict[str, float]]:
    """Every Visualizer mode as its Guided Setup preview snapshot (curated defaults, fixture music),
    drawn by one production Visualizer host on the shared context beside the same control."""
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.visualizer_cost_probe import visualizer_case

    gl, capture = bench.gl, bench.capture
    host = QuickVisualizerRenderHost()
    cases, failed = {}, {}
    for descriptor in iter_visualizer_mode_descriptors():
        mode = descriptor.mode_id
        try:
            snapshot = _build_spectrum_preview_snapshot(width=capture.width, height=capture.height, mode=mode)
        except Exception as exc:          # a broken preview fixture must not hide every other mode
            failed[mode] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"  visualizer {mode:34s} FAILED: {failed[mode]['error']}", flush=True)
            continue
        cases[mode] = visualizer_case(gl, capture, host, snapshot)
    try:
        results = bench.measure("visualizer", cases, frames, passes, max_rounds)
    finally:
        host.release_resources()
    return {**results, **failed}


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              timeout=10).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def compare(old: dict, new: dict) -> int:
    """Print per-case deltas; return how many rows are flagged."""
    flagged = 0
    print(f"\nCompare {old.get('commit')} ({old.get('date')}) -> {new.get('commit')} ({new.get('date')}), "
          f"{new.get('size')}, {new.get('renderer')}")
    if old.get("size") != new.get("size") or old.get("renderer") != new.get("renderer"):
        print("  WARNING: different size or GPU; deltas are not comparable")
    for label, run in (("old", old), ("new", new)):
        load = run.get("load", {})
        if load:
            print(f"  {label} conditions: other processes' CPU {load.get('cpu_others_median', '?')}% (max "
                  f"{load.get('cpu_others_max', '?')}%), GPU busy {load.get('gpu_util_median', '?')}%, GPU clock "
                  f"{load.get('gpu_clock_mhz_median', '?')} MHz, {load.get('admitted', '?')}/{load.get('controls', '?')} "
                  f"passes admitted")
    if any("gpu_rel" in row for row in new.get("transitions", {}).values()) and not any(
            "gpu_rel" in row for row in old.get("transitions", {}).values()):
        print("  WARNING: the old baseline predates control-relative timing (2026-10-11); its absolute GPU figures were "
              "taken with the GPU held at higher clocks, so judge transitions by how a case moved against the untouched "
              "ones, or re-record the old commit")
    differs = environment_differs(old.get("load", {}), new.get("load", {}))
    if differs:
        print(f"  WARNING: the runs were measured under different conditions ({', '.join(differs)}); "
              f"treat GPU and wall-time deltas with care (thread CPU and call counts are unaffected)")
    for section in ("transitions", "visualizers", "surfaces", "node_path"):
        rows_old, rows_new = old.get(section, {}), new.get(section, {})
        if new.get("match"):        # a partial run: only the cases it measured
            rows_old = {key: row for key, row in rows_old.items() if key in rows_new}
        for key in sorted(set(rows_old) | set(rows_new)):
            if key not in rows_old or key not in rows_new:
                print(f"  {section[:-1]:10s} {key:34s} {'added' if key in rows_new else 'removed'}")
                continue
            if "error" in rows_old[key] or "error" in rows_new[key]:
                print(f"  {section[:-1]:10s} {key:34s} not measured: {rows_new[key].get('error') or rows_old[key].get('error')}")
                continue
            notes = []
            old_row, new_row = rows_old[key], rows_new[key]
            if "native_rel" in old_row and "native_rel" in new_row:
                a, b = old_row["native_rel"], new_row["native_rel"]
                ratio, noise_factor = NATIVE_NOISE_FLAG
                noisy = noise_factor * max(old_row.get("native_noise", 0.0), new_row.get("native_noise", 0.0)) * a
                if b - a > max(ratio * a, noisy):
                    flagged += 1
                    print(f"  {section[:-1]:10s} {key:34s} SLOWER: native frame {a:.2f}x->{b:.2f}x of the control "
                          f"({old_row['native_ms']:.2f}->{new_row['native_ms']:.2f} ms)")
                continue
            relative = "gpu_rel" in old_row and "gpu_rel" in new_row
            for label, absolute, rel, noise, (ratio, floor) in (
                    ("GPU", "gpu_median", "gpu_rel", "gpu_noise", GPU_FLAG),
                    ("CPU", "cpu_thread_median" if relative else "cpu_median", "cpu_rel", "cpu_noise", CPU_FLAG)):
                a, b = old_row[absolute], new_row[absolute]
                if relative:
                    # In Crossfade frames measured beside each case; the floor in today's milliseconds.
                    unit = new_row[absolute] / new_row[rel] if new_row[rel] > 0 else 0.0
                    a, b = old_row[rel] * unit, new_row[rel] * unit
                noisy = 2.0 * max(old_row.get(noise, 0.0), new_row.get(noise, 0.0)) * a
                if b - a > max(floor, ratio * a, noisy):
                    notes.append(f"{label} {a:.3f}->{b:.3f} ms" + (" (relative)" if relative else ""))
            for metric in ("gl_calls", "py_calls"):
                a, b = rows_old[key].get(metric), rows_new[key].get(metric)
                if a is not None and b is not None and b > a:
                    notes.append(f"{metric} {a:g}->{b:g}")
            if notes:
                flagged += 1
                conditions = environment_differs(old_row.get("env", {}), new_row.get("env", {}))
                print(f"  {section[:-1]:10s} {key:34s} SLOWER: {', '.join(notes)}"
                      + (f"  (conditions differed: {', '.join(conditions)})" if conditions else ""))
    print(f"  {flagged} flagged row(s)" if flagged else "  no regressions (counts unchanged or lower; GPU and CPU within their bands)")
    return flagged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", default="1920x1080")
    parser.add_argument("--frames", type=int, default=48)
    parser.add_argument("--passes", type=int, default=3, help="admitted passes each transition needs")
    parser.add_argument("--max-rounds", type=int, default=12,
                        help="round-robin rounds before giving up on a quiet pass (busy machine)")
    parser.add_argument("--only", choices=("transitions", "visualizers"))
    parser.add_argument("--match", help="measure only cases whose key contains this text (e.g. liquid_lens); "
                                        "the file is named after it and comparisons cover only those cases")
    parser.add_argument("--compare", type=Path, help="older baseline to compare the new one against")
    parser.add_argument("--compare-only", nargs=2, type=Path, metavar=("OLD", "NEW"))
    parser.add_argument("--out", type=Path, help="write the baseline here instead of tools/baselines/overhead/ "
                                                 "(tools/preflip_pack.py reads its session control from a run of this)")
    args = parser.parse_args()
    if args.compare_only:
        old, new = (json.loads(p.read_text(encoding="utf-8")) for p in args.compare_only)
        return 1 if compare(old, new) else 0

    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication(sys.argv)
    width, height = (int(v) for v in args.size.lower().split("x"))
    size = (width, height)
    data = {"commit": _commit(), "date": _dt.datetime.now().isoformat(timespec="seconds"), "size": args.size,
            "frames": args.frames, "passes": args.passes, "match": args.match}
    from OpenGL import GL as gl
    from tools.labs.render_target import OffscreenRenderTarget

    capture = OffscreenRenderTarget(*size)
    try:
        bench = PairedBench(gl, capture, crossfade_control(capture), args.match)
        if args.only in (None, "transitions"):
            print("Transitions")
            data["transitions"] = measure_transitions(bench, args.frames, args.passes, args.max_rounds)
        if args.only in (None, "visualizers"):
            print("Visualizers")
            data["visualizers"] = measure_visualizers(bench, args.frames, args.passes, args.max_rounds)
        data["load"] = load = bench.load()
        data["renderer"] = gl.glGetString(gl.GL_RENDERER).decode()
    finally:
        capture.close()
    print(f"  load: {load.get('admitted')}/{load.get('controls')} passes admitted; control GPU quiet "
          f"{load.get('control_gpu_quiet', 0):.3f} ms, range "
          f"{load.get('control_gpu_min', 0):.3f}-{load.get('control_gpu_max', 0):.3f} ms, wall CPU "
          f"{load.get('control_cpu_min', 0):.3f}-{load.get('control_cpu_max', 0):.3f} ms")
    print(f"  conditions: other processes' CPU median {load.get('cpu_others_median', '?')}% (max "
          f"{load.get('cpu_others_max', '?')}%), memory {load.get('memory_used_median', '?')}%, GPU busy "
          f"{load.get('gpu_util_median', '?')}% (max {load.get('gpu_util_max', '?')}%), GPU clock "
          f"{load.get('gpu_clock_mhz_median', '?')} MHz, {load.get('gpu_temp_c_median', '?')} C")
    suffix = f"_{''.join(c if c.isalnum() else '-' for c in args.match)}" if args.match else ""
    from tools import artifact_paths

    path = (artifact_paths.checked_output(args.out) if args.out is not None
            else OUT / f"{_dt.date.today().isoformat()}_{data['commit']}{suffix}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    if args.compare:
        return 1 if compare(json.loads(args.compare.read_text(encoding="utf-8")), data) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
