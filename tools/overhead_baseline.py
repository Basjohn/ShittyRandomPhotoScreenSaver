"""Quick overhead baseline: every showcase transition and Visualizer mode, offscreen, before/after.

Record one before and one after any major architecture addition (a shared primitive, a new
pass, a host change) and compare: an addition should leave everything that does not use it
unchanged. Each case renders through the production render host on one offscreen GL 4.6
context (no window, no runtime): transitions as their release-showcase cases (canonical
settings at High detail, fixture photographs), Visualizer modes as their Guided Setup preview
snapshots (``tools/visualizer_cost_probe.measure``). Per frame it records CPU submit (render
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
    BenchCase, PairedBench, crossfade_control, environment_differs,
)

OUT = ROOT / "tools" / "baselines" / "overhead"
GPU_FLAG = (0.20, 0.05)     # ratio, ms
CPU_FLAG = (0.50, 0.15)
COUNT_FRAMES = 8


def measure_transitions(bench: PairedBench, frames: int, passes: int, max_rounds: int) -> dict[str, dict[str, float]]:
    """Every showcase transition case (release-showcase settings, fixture photographs)."""
    from tools.release_media import catalogue

    gl, capture = bench.gl, bench.capture
    cases = {}
    for run_id, case in enumerate((c for c in catalogue() if c.kind == "transition"), start=2):
        run = capture.production_run(case.identity, case.duration_ms, case.settings, run_id=run_id)

        def point(index, run=run):
            frame = capture.frame(run, 0.05 + 0.9 * index / max(1, frames - 1))
            return lambda: capture.host.render(frame)

        def warm(run=run):
            # A renderer switching runs on the shared host rebuilds per-run state here, untimed.
            for progress in (0.2, 0.5, 0.8):
                capture.render(run, progress)

        cases[f"{case.identity}/{case.variant}"] = BenchCase(point, warm, lambda run=run: _transition_counts(gl, capture, run))
    return bench.measure("transition", cases, frames, passes, max_rounds)


class _GLCounter:
    """Counts every call to an ``OpenGL.GL`` function while installed (renderers call through
    the module object, so wrapping its attributes sees them all)."""

    def __init__(self, gl) -> None:
        self.gl, self.count, self._saved = gl, 0, {}

    def __enter__(self):
        for name in dir(self.gl):
            value = getattr(self.gl, name)
            if name.startswith("gl") and callable(value):
                self._saved[name] = value
                setattr(self.gl, name, self._wrap(value))
        return self

    def _wrap(self, function):
        def call(*args, **kwargs):
            self.count += 1
            return function(*args, **kwargs)
        return call

    def __exit__(self, *_exc):
        for name, value in self._saved.items():
            setattr(self.gl, name, value)
        self._saved.clear()


def _transition_counts(gl, capture, run) -> dict[str, float]:
    """Median GL and Python calls per frame over ``COUNT_FRAMES`` frames (deterministic)."""
    gl_counts, py_counts = [], []
    for index in range(COUNT_FRAMES):
        progress = 0.05 + 0.9 * index / max(1, COUNT_FRAMES - 1)
        frame = capture.frame(run, progress)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        calls = [0]

        def profile(_frame, event, _arg):
            if event in ("call", "c_call"):
                calls[0] += 1

        with _GLCounter(gl) as counter:
            sys.setprofile(profile)
            try:
                capture.host.render(frame)
            finally:
                sys.setprofile(None)
        gl_counts.append(counter.count)
        py_counts.append(calls[0])
    gl.glFinish()
    return {"gl_calls": statistics.median(gl_counts), "py_calls": statistics.median(py_counts)}


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
    for section in ("transitions", "visualizers"):
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
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(*size)
    try:
        bench = PairedBench(gl, capture, crossfade_control(capture), args.match)
        if args.only != "visualizers":
            print("Transitions")
            data["transitions"] = measure_transitions(bench, args.frames, args.passes, args.max_rounds)
        if args.only != "transitions":
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
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = f"_{''.join(c if c.isalnum() else '-' for c in args.match)}" if args.match else ""
    path = OUT / f"{_dt.date.today().isoformat()}_{data['commit']}{suffix}.json"
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {path.relative_to(ROOT)}")
    if args.compare:
        return 1 if compare(json.loads(args.compare.read_text(encoding="utf-8")), data) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
