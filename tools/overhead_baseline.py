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
import ctypes
import datetime as _dt
import json
import statistics
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Importing the Visualizer probe first matches production GL error checking (it switches per-call
# checking off before OpenGL.GL is first imported, as main.py does, and refuses otherwise).
import tools.visualizer_cost_probe  # noqa: E402,F401
from tools.bench_stability import (  # noqa: E402
    LoadGate, SystemSampler, ThreadCpuClock, environment_differs, min_of_repeats, p90 as _p90, spread,
    summarise_environment,
)

OUT = ROOT / "tools" / "baselines" / "overhead"
GPU_FLAG = (0.20, 0.05)     # ratio, ms
CPU_FLAG = (0.50, 0.15)
COUNT_FRAMES = 8
REPEATS = 3                # renders per sampled frame; the fastest counts
CONTROL_DRAWS = 8          # Crossfade draws per control frame: enough GPU work to show contention
CONTROL = ("crossfade", 1000, {})


@dataclass
class _Case:
    """One measured case on the shared context: ``point(i)`` returns the render for sampled frame
    ``i``, ``warm`` runs untimed frames, ``counts`` returns its deterministic per-frame counts."""

    point: Callable[[int], Callable[[], None]]
    warm: Callable[[], None]
    counts: Callable[[], dict[str, float]]


class _Bench:
    """Round-robin passes with an interleaved control, a load gate and system conditions, shared by
    transitions and Visualizer modes on one offscreen context (``capture``)."""

    def __init__(self, gl, capture, control: Callable[[], None]) -> None:
        self.gl, self.capture, self.control = gl, capture, control
        self.clock, self.gate, self.sampler = ThreadCpuClock(), LoadGate(), SystemSampler()
        self.environment: list[dict[str, float]] = []

    def measure(self, label: str, cases: dict[str, _Case], frames: int, passes: int,
                max_rounds: int) -> dict[str, dict[str, float]]:
        pending: dict[str, list[tuple[int, dict[str, float]]]] = {key: [] for key in cases}
        admitted = lambda key: [stats for index, stats in pending[key] if self.gate.admits(index)]  # noqa: E731
        keys = list(cases)
        for round_index in range(max_rounds):
            # Judge every pass so far against the controls' quiet reference so far.
            short = [key for key in keys if len(admitted(key)) < passes]
            if not short:
                break
            # Rotate the order so no case always follows the same neighbour.
            offset = round_index % len(short)
            for key in short[offset:] + short[:offset]:
                cases[key].warm()
                self.control()
                self.gl.glFinish()
                stats = self._pass(cases[key], frames)
                index = self.gate.record(stats["control_gpu_median"], stats["control_cpu_median"])
                stats["env"] = self.sampler.sample()     # what else ran during this pass
                self.environment.append(stats["env"])
                pending[key].append((index, stats))
        results = {}
        for key in keys:
            chosen = admitted(key) or [stats for _index, stats in pending[key]]
            best = dict(min(chosen, key=lambda s: s["gpu_rel"] + s["cpu_rel"]))
            best["passes"] = len(pending[key])
            best["admitted"] = len(admitted(key))
            best["gpu_noise"] = spread([s["gpu_rel"] for s in chosen])
            best["cpu_noise"] = spread([s["cpu_rel"] for s in chosen])
            best["env"] = summarise_environment([s["env"] for s in chosen])
            best.update(cases[key].counts())
            results[key] = best
            print(f"  {label:10s} {key:34s} gpu {best['gpu_median']:6.3f} ms = {best['gpu_rel']:6.2f} cf  "
                  f"cpu {best['cpu_thread_median']:6.3f} ms = {best['cpu_rel']:5.2f} cf  noise {best['gpu_noise']:4.0%}  "
                  f"admitted {best['admitted']}/{best['passes']}  gl {best.get('gl_calls', 0):5g}  "
                  f"py {best.get('py_calls', 0):6g}", flush=True)
        return results

    def load(self) -> dict[str, float]:
        return {**self.gate.summary(), **summarise_environment(self.environment)}

    def _timed(self, render: Callable[[], None], draws: int, cpu: list, thread: list, queries: list) -> None:
        """One timed frame of ``draws`` renders: GPU over all of them (per draw), CPU over the first
        alone, so a control's CPU figure is structured exactly like a case's single render
        (back-to-back repeats run hotter and faster on the CPU than any real frame)."""
        gl = self.gl
        query = int(gl.glGenQueries(1)[0])
        queries.append(query)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.capture.fbo)
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
        start, start_thread = perf_counter(), self.clock.now()
        render()
        thread.append(self.clock.now() - start_thread)
        cpu.append((perf_counter() - start) * 1e3)
        for _draw in range(draws - 1):
            render()
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        gl.glFlush()

    def _gpu_ms(self, queries: list, draws: int) -> list[float]:
        values = []
        for query in queries:
            value = ctypes.c_uint64()
            self.gl.glGetQueryObjectui64v(query, self.gl.GL_QUERY_RESULT, ctypes.byref(value))
            values.append(value.value / 1e6 / draws)
        self.gl.glDeleteQueries(len(queries), queries)
        return values

    def _pass(self, case: _Case, frames: int) -> dict[str, float]:
        """``frames`` sampled frames, each rendered ``REPEATS`` times, every repeat right after the
        control (one Crossfade frame drawn ``CONTROL_DRAWS`` times: GPU per draw, CPU of the first);
        per frame the fastest repeat of each, then medians over frames. ``gpu_rel`` / ``cpu_rel`` are
        the case in Crossfade frames measured beside it, which cancels GPU clock state, contention
        and a busy core's slowdown (they move both alike)."""
        samples = {name: [] for name in ("cpu", "thread", "gpu", "control_cpu", "control_thread", "control_gpu")}
        for index in range(frames):
            render = case.point(index)
            point = {name: [] for name in ("cpu", "thread", "gpu", "control_cpu", "control_thread", "control_gpu")}
            for _repeat in range(REPEATS):
                self._timed(self.control, CONTROL_DRAWS, point["control_cpu"], point["control_thread"],
                            point["control_gpu"])
                self._timed(render, 1, point["cpu"], point["thread"], point["gpu"])
            for name in samples:
                samples[name].append(point[name])
        samples["gpu"] = [self._gpu_ms(queries, 1) for queries in samples["gpu"]]
        samples["control_gpu"] = [self._gpu_ms(queries, CONTROL_DRAWS) for queries in samples["control_gpu"]]
        fastest = {name: min_of_repeats(values) for name, values in samples.items()}
        ratio = lambda a, b: statistics.median(x / y for x, y in zip(fastest[a], fastest[b]) if y > 0)  # noqa: E731
        return {"cpu_median": statistics.median(fastest["cpu"]), "cpu_p90": _p90(fastest["cpu"]),
                "cpu_thread_median": statistics.median(fastest["thread"]), "cpu_thread_p90": _p90(fastest["thread"]),
                "gpu_median": statistics.median(fastest["gpu"]), "gpu_p90": _p90(fastest["gpu"]),
                "control_gpu_median": statistics.median(fastest["control_gpu"]),
                "control_cpu_median": statistics.median(fastest["control_cpu"]),
                "gpu_rel": ratio("gpu", "control_gpu"), "cpu_rel": ratio("thread", "control_thread")}


def measure_transitions(bench: _Bench, frames: int, passes: int, max_rounds: int) -> dict[str, dict[str, float]]:
    """Every showcase transition case (release-showcase settings, fixture photographs)."""
    from tools.release_media import _transition_run, catalogue

    gl, capture = bench.gl, bench.capture
    cases = {}
    for run_id, case in enumerate((c for c in catalogue() if c.kind == "transition"), start=2):
        run = _transition_run(capture, case.identity, case.duration_ms, case.settings, run_id=run_id)

        def point(index, run=run):
            frame = capture.frame(run, 0.05 + 0.9 * index / max(1, frames - 1))
            return lambda: capture.host.render(frame)

        def warm(run=run):
            # A renderer switching runs on the shared host rebuilds per-run state here, untimed.
            for progress in (0.2, 0.5, 0.8):
                capture.render(run, progress)

        cases[f"{case.identity}/{case.variant}"] = _Case(point, warm, lambda run=run: _transition_counts(gl, capture, run))
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


def measure_visualizers(bench: _Bench, frames: int, passes: int, max_rounds: int) -> dict[str, dict[str, float]]:
    """Every Visualizer mode as its Guided Setup preview snapshot (curated defaults, fixture music),
    drawn by one production Visualizer host on the shared context beside the same control."""
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.visualizer_cost_probe import _CallCounter

    gl, capture = bench.gl, bench.capture
    width, height = capture.width, capture.height
    matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    host = QuickVisualizerRenderHost()
    cases, failed = {}, {}
    for descriptor in iter_visualizer_mode_descriptors():
        mode = descriptor.mode_id
        try:
            snapshot = _build_spectrum_preview_snapshot(width=width, height=height, mode=mode)
        except Exception as exc:          # a broken preview fixture must not hide every other mode
            failed[mode] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"  visualizer {mode:34s} FAILED: {failed[mode]['error']}", flush=True)
            continue

        def render(snapshot=snapshot):
            gl.glViewport(0, 0, width, height)
            gl.glClearColor(0.1, 0.12, 0.16, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                        logical_size=(float(width), float(height)), matrix_values=matrix)

        def warm(render=render):
            for _ in range(10):
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                render()

        def counts(render=render):
            counter, gl_counts, py_counts = _CallCounter(gl), [], []
            for _ in range(COUNT_FRAMES):
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                calls = [0]

                def profile(_frame, event, _arg, calls=calls):
                    if event in ("call", "c_call"):
                        calls[0] += 1

                counter.count = 0
                counter.install()
                sys.setprofile(profile)
                try:
                    render()
                finally:
                    sys.setprofile(None)
                    counter.uninstall()
                gl_counts.append(counter.count)
                py_counts.append(calls[0])
            gl.glFinish()
            return {"gl_calls": statistics.median(gl_counts), "py_calls": statistics.median(py_counts)}

        cases[mode] = _Case(lambda _index, render=render: render, warm, counts)
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
    from OpenGL import GL as gl
    from tools.release_media import _transition_run
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(*size)
    try:
        control_frame = capture.frame(_transition_run(capture, CONTROL[0], CONTROL[1], CONTROL[2], run_id=1), 0.5)
        bench = _Bench(gl, capture, lambda: capture.host.render(control_frame))
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
    path = OUT / f"{_dt.date.today().isoformat()}_{data['commit']}.json"
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {path.relative_to(ROOT)}")
    if args.compare:
        return 1 if compare(json.loads(args.compare.read_text(encoding="utf-8")), data) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
