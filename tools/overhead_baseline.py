"""Quick overhead baseline: every showcase transition and Visualizer mode, offscreen, before/after.

Record one before and one after any major architecture addition (a shared primitive, a new
pass, a host change) and compare: an addition should leave everything that does not use it
unchanged. Each case renders through the production render host on one offscreen GL 4.6
context (no window, no runtime): transitions as their release-showcase cases (canonical
settings at High detail, fixture photographs), Visualizer modes as their Guided Setup preview
snapshots (``tools/visualizer_cost_probe.measure``). Per frame it records CPU submit (render
thread Python + GL calls) and GPU time (``GL_TIME_ELAPSED``), flushing per frame as presentation
does. Each case runs ``--passes`` passes after a warm-up and keeps the pass with the lowest median
(the best of several medians is far steadier than one: single passes of sub-millisecond work
moved up to 30% between identical runs).

    python tools/overhead_baseline.py                       # writes tools/baselines/overhead/<date>_<sha>.json
    python tools/overhead_baseline.py --compare OLD.json    # also compares against an older baseline
    python tools/overhead_baseline.py --compare-only OLD.json NEW.json

Each case also records two deterministic per-frame counts: OpenGL calls (every ``OpenGL.GL``
function, counted by wrapping the module) and Python function calls (``sys.setprofile``). They do
not drift between runs, so **any** rise is real added per-frame work (an extra pass, state change,
upload or Python step) and is flagged. GPU medians are flagged above ``max(20%, 0.05 ms)``. CPU
submit of sub-millisecond Python drifts ~0.1 ms between identical runs (power states, scheduler),
so it is flagged only above ``max(50%, 0.15 ms)`` and is a hint, not proof. Takes about a minute.
Visualizer modes record GL calls through the probe's counter (its renderer modules) but no Python
count.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as _dt
import json
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Importing the Visualizer probe first matches production GL error checking (it switches per-call
# checking off before OpenGL.GL is first imported, as main.py does, and refuses otherwise).
from tools.visualizer_cost_probe import measure as measure_visualizer  # noqa: E402

OUT = ROOT / "tools" / "baselines" / "overhead"
GPU_FLAG = (0.20, 0.05)     # ratio, ms
CPU_FLAG = (0.50, 0.15)
COUNT_FRAMES = 8


def _p90(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]


def measure_transitions(size: tuple[int, int], frames: int, passes: int) -> dict[str, dict[str, float]]:
    from OpenGL import GL as gl

    from tools.release_media import _transition_run, catalogue
    from tools.transition_contact_sheet import TransitionCapture

    results = {}
    for case in (c for c in catalogue() if c.kind == "transition"):
        capture = TransitionCapture(*size)
        try:
            run = _transition_run(capture, case.identity, case.duration_ms, case.settings)
            for progress in (0.2, 0.5, 0.8):                     # compile and allocate first
                capture.render(run, progress)
            gl.glFinish()
            best = None
            for _pass in range(passes):
                stats = _transition_pass(gl, capture, run, frames)
                if best is None or stats["cpu_median"] + stats["gpu_median"] < best["cpu_median"] + best["gpu_median"]:
                    best = stats
            best.update(_transition_counts(gl, capture, run))
        finally:
            capture.close()
        key = f"{case.identity}/{case.variant}"
        results[key] = best
        print(f"  transition {key:34s} cpu {best['cpu_median']:6.3f} ms  gpu {best['gpu_median']:6.3f} ms  "
              f"gl {best['gl_calls']:5g}  py {best['py_calls']:6g}", flush=True)
    return results


def _transition_pass(gl, capture, run, frames: int) -> dict[str, float]:
    cpu, queries = [], []
    for index in range(frames):
        progress = 0.05 + 0.9 * index / max(1, frames - 1)
        query = int(gl.glGenQueries(1)[0])
        queries.append(query)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
        start = perf_counter()
        capture.host.render(capture.frame(run, progress))
        cpu.append((perf_counter() - start) * 1e3)
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        gl.glFlush()
    gpu = []
    for query in queries:
        value = ctypes.c_uint64()
        gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
        gpu.append(value.value / 1e6)
    gl.glDeleteQueries(len(queries), queries)
    return {"cpu_median": statistics.median(cpu), "cpu_p90": _p90(cpu),
            "gpu_median": statistics.median(gpu), "gpu_p90": _p90(gpu)}


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


def measure_visualizers(size: tuple[int, int], frames: int, passes: int) -> dict[str, dict[str, float]]:
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors

    results = {}
    for descriptor in iter_visualizer_mode_descriptors():
        mode = descriptor.mode_id
        try:
            runs = [measure_visualizer(mode, {}, size, frames=frames) for _ in range(passes)]
            results[mode] = min(runs, key=lambda r: r["cpu_median"] + r["gpu_median"])
            results[mode]["gl_calls"] = measure_visualizer(mode, {}, size, frames=COUNT_FRAMES, calls=True)["gl_calls"]
        except Exception as exc:          # a broken preview fixture must not hide every other mode
            results[mode] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"  visualizer {mode:34s} FAILED: {results[mode]['error']}", flush=True)
            continue
        print(f"  visualizer {mode:34s} cpu {results[mode]['cpu_median']:6.3f} ms  gpu {results[mode]['gpu_median']:6.3f} ms",
              flush=True)
    return results


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
    for section in ("transitions", "visualizers"):
        rows_old, rows_new = old.get(section, {}), new.get(section, {})
        for key in sorted(set(rows_old) | set(rows_new)):
            if key not in rows_old or key not in rows_new:
                print(f"  {section[:-1]:10s} {key:34s} {'added' if key in rows_new else 'removed'}")
                continue
            if "error" in rows_old[key] or "error" in rows_new[key]:
                print(f"  {section[:-1]:10s} {key:34s} not measured: {rows_new[key].get('error') or rows_old[key].get('error')}")
                continue
            notes = []
            for metric, (ratio, floor) in (("gpu_median", GPU_FLAG), ("cpu_median", CPU_FLAG)):
                a, b = rows_old[key][metric], rows_new[key][metric]
                if b - a > max(floor, ratio * a):
                    notes.append(f"{metric.split('_')[0].upper()} {a:.3f}->{b:.3f} ms")
            for metric in ("gl_calls", "py_calls"):
                a, b = rows_old[key].get(metric), rows_new[key].get(metric)
                if a is not None and b is not None and b > a:
                    notes.append(f"{metric} {a:g}->{b:g}")
            if notes:
                flagged += 1
                print(f"  {section[:-1]:10s} {key:34s} SLOWER: {', '.join(notes)}")
    print(f"  {flagged} flagged row(s)" if flagged else "  no regressions (counts unchanged or lower; GPU and CPU within their bands)")
    return flagged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", default="1920x1080")
    parser.add_argument("--frames", type=int, default=48)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--only", choices=("transitions", "visualizers"))
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
            "frames": args.frames, "passes": args.passes}
    if args.only != "visualizers":
        print("Transitions")
        data["transitions"] = measure_transitions(size, args.frames, args.passes)
    if args.only != "transitions":
        print("Visualizers")
        data["visualizers"] = measure_visualizers(size, args.frames, args.passes)
    from OpenGL import GL as gl
    from tools.transition_contact_sheet import TransitionCapture

    probe = TransitionCapture(16, 16)
    try:
        data["renderer"] = gl.glGetString(gl.GL_RENDERER).decode()
    finally:
        probe.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{_dt.date.today().isoformat()}_{data['commit']}.json"
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {path.relative_to(ROOT)}")
    if args.compare:
        return 1 if compare(json.loads(args.compare.read_text(encoding="utf-8")), data) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
