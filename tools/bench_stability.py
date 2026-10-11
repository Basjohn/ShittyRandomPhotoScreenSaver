"""Benchmark measurements that stay trustworthy on a busy machine (headless tools only).

Three pieces shared by the offscreen benchmarks (``tools/overhead_baseline.py`` first):

* ``ThreadCpuClock``: this thread's own CPU time in milliseconds. Wall time (``perf_counter``)
  grows whenever other processes preempt the render thread; thread CPU time is charged only
  while the thread runs. On Windows it reads ``QueryThreadCycleTime`` (cycle-exact, unlike the
  15.6 ms ``GetThreadTimes`` tick) and converts with a rate calibrated by busy spins at start;
  elsewhere ``time.thread_time``.
* ``LoadGate``: each measured pass is paired with a short **control** pass of a fixed, trivial
  workload measured right before it. The lower quartile of the controls is the machine's quiet
  reference (the single quietest is an outlier: a tiny workload's GPU time spreads 3x on an idle
  machine); a pass whose control ran slower than that by more than the tolerance shared the GPU
  with something else and is rejected. Only GPU time is gated: CPU submit is judged by thread CPU
  time, which outside load does not inflate (wall time spread 2x on an idle machine and 1000x under
  full CPU load). Decisions are made at the end against the final reference, so early passes are
  judged as strictly as late ones.
* ``min_of_repeats``: render each sampled frame a few times and keep its fastest repeat before
  taking the median over frames: a repeat that lost the GPU or the core to another process is
  discarded, while the median over frames still reflects the whole run, not its cheapest moment.
* ``spread``: the relative spread of a case's admitted pass medians, its own noise estimate, so a
  comparison can demand more than the noise before it calls a change real.
* ``PairedBench`` / ``BenchCase``: the measurement itself, shared by ``tools/overhead_baseline.py``
  (every transition and Visualizer mode) and ``tools/visualizer_cost_probe.py`` (one mode): cases
  measured round-robin on one offscreen context, every sampled frame rendered ``REPEATS`` times
  right after the control (``crossfade_control``) with the fastest repeat kept, figures relative to
  that control, passes gated on it, and system conditions sampled after every pass.
* ``SystemSampler``: what else the machine was doing, sampled between passes (never inside a timed
  frame): CPU used by other processes (system minus this process, in per cent of the whole
  machine), memory in use, and, where ``nvidia-smi`` exists, GPU utilisation, graphics clock and
  temperature. Recorded with every pass and summarised per run, so two runs measured under
  different conditions are reported as such instead of silently disagreeing.
"""
from __future__ import annotations

import ctypes
import shutil
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter


class ThreadCpuClock:
    """Milliseconds of CPU time charged to the calling thread (create and read it on one thread)."""

    def __init__(self) -> None:
        self._query = None
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            kernel32.GetCurrentThread.restype = ctypes.c_void_p
            kernel32.QueryThreadCycleTime.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64))
            kernel32.QueryThreadCycleTime.restype = ctypes.c_int
            self._handle = kernel32.GetCurrentThread()
            self._query = kernel32.QueryThreadCycleTime
            self._value = ctypes.c_uint64()
            self.cycles_per_ms = self._calibrate()

    def _cycles(self) -> int:
        self._query(self._handle, ctypes.byref(self._value))
        return self._value.value

    def _calibrate(self) -> float:
        # Cycles charged per wall millisecond while spinning; a preempted spin charges fewer, so
        # the largest of a few spins is the running rate.
        best = 0.0
        for _ in range(5):
            start_wall, start_cycles = perf_counter(), self._cycles()
            while perf_counter() - start_wall < 0.02:
                pass
            best = max(best, (self._cycles() - start_cycles) / ((perf_counter() - start_wall) * 1e3))
        return best

    def now(self) -> float:
        if self._query is None:
            return time.thread_time() * 1e3
        return self._cycles() / self.cycles_per_ms


@dataclass
class LoadGate:
    """Admits passes whose paired control ran within ``tolerance`` of the quietest control."""

    gpu_tolerance: tuple[float, float] = (0.35, 0.005)     # ratio, ms
    controls: list[tuple[float, float]] = field(default_factory=list)

    def record(self, control_gpu: float, control_cpu: float) -> int:
        """Remember one control (GPU and wall CPU medians); returns its index."""
        self.controls.append((float(control_gpu), float(control_cpu)))
        return len(self.controls) - 1

    def quiet_gpu(self) -> float:
        return lower_quartile([c[0] for c in self.controls])

    def admits(self, index: int) -> bool:
        return self.controls[index][0] <= self.quiet_gpu() * (1 + self.gpu_tolerance[0]) + self.gpu_tolerance[1]

    def summary(self) -> dict[str, float]:
        if not self.controls:
            return {}
        gpus, cpus = [c[0] for c in self.controls], [c[1] for c in self.controls]
        return {"controls": len(self.controls), "admitted": sum(self.admits(i) for i in range(len(self.controls))),
                "control_gpu_quiet": self.quiet_gpu(), "control_gpu_min": min(gpus), "control_gpu_max": max(gpus),
                "control_cpu_min": min(cpus), "control_cpu_max": max(cpus)}


def lower_quartile(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[int(0.25 * (len(ordered) - 1))]


def min_of_repeats(samples: list[list[float]]) -> list[float]:
    """Each frame's fastest repeat (``samples[frame][repeat]``)."""
    return [min(repeats) for repeats in samples]


def p90(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]


def spread(medians: list[float]) -> float:
    """Relative spread (max - min) / min of pass medians; 0 for fewer than two."""
    if len(medians) < 2:
        return 0.0
    low = min(medians)
    return (max(medians) - low) / low if low > 0 else 0.0


def median(values: list[float]) -> float:
    return statistics.median(values)


class SystemSampler:
    """Rough system usage since the previous sample (call between passes, on the measuring thread)."""

    _GPU_FIELDS = ("gpu_util", "gpu_clock_mhz", "gpu_temp_c")

    def __init__(self) -> None:
        import psutil

        self._psutil = psutil
        self._process = psutil.Process()
        self._cores = psutil.cpu_count() or 1
        psutil.cpu_percent(None)                 # prime both counters: the next call covers since now
        self._process.cpu_percent(None)
        self._smi = shutil.which("nvidia-smi")

    def sample(self) -> dict[str, float]:
        system = self._psutil.cpu_percent(None)
        own = self._process.cpu_percent(None) / self._cores      # per cent of one core -> of the machine
        values = {"cpu_others": max(0.0, system - own), "cpu_system": system,
                  "memory_used": self._psutil.virtual_memory().percent}
        if self._smi:
            try:
                out = subprocess.run(
                    [self._smi, "--query-gpu=utilization.gpu,clocks.gr,temperature.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                ).stdout.splitlines()[0]
                values.update(zip(self._GPU_FIELDS, (float(v) for v in out.split(","))))
            except (OSError, subprocess.SubprocessError, ValueError, IndexError):
                self._smi = None                 # unavailable: stop asking, keep the CPU figures
        return values


def summarise_environment(samples: list[dict[str, float]]) -> dict[str, float]:
    """Median and max of each sampled figure (``cpu_others_median``, ``gpu_util_max``, ...)."""
    summary: dict[str, float] = {}
    for name in sorted({key for sample in samples for key in sample}):
        values = [sample[name] for sample in samples if name in sample]
        summary[f"{name}_median"] = round(statistics.median(values), 1)
        summary[f"{name}_max"] = round(max(values), 1)
    return summary


def environment_differs(old: dict[str, float], new: dict[str, float]) -> list[str]:
    """Plain-language notes where two runs' conditions differ enough to mislead a comparison."""
    notes = []
    for name, label, limit in (("cpu_others_median", "other processes' CPU", 15.0),
                               ("gpu_util_median", "GPU busy", 15.0),
                               ("gpu_clock_mhz_median", "GPU clock", 150.0),
                               ("gpu_temp_c_median", "GPU temperature", 10.0)):
        a, b = old.get(name), new.get(name)
        if a is not None and b is not None and abs(b - a) > limit:
            notes.append(f"{label} {a:g} -> {b:g}")
    return notes


REPEATS = 3                # renders per sampled frame; the fastest counts
CONTROL_DRAWS = 8          # Crossfade draws per control frame: enough GPU work to show contention
CONTROL = ("crossfade", 1000, {})


def crossfade_control(capture) -> Callable[[], None]:
    """The control: one fixed Crossfade frame on ``capture``'s host (the same workload in every run)."""
    frame = capture.frame(capture.production_run(CONTROL[0], CONTROL[1], CONTROL[2], run_id=1), 0.5)
    return lambda: capture.host.render(frame)


@dataclass
class BenchCase:
    """One measured case on the shared context: ``point(i)`` returns the render for sampled frame
    ``i``, ``warm`` runs untimed frames, ``counts`` returns its deterministic per-frame counts."""

    point: Callable[[int], Callable[[], None]]
    warm: Callable[[], None]
    counts: Callable[[], dict[str, float]]


class PairedBench:
    """Round-robin passes with an interleaved control, a load gate and system conditions, shared by
    transitions and Visualizer modes on one offscreen context (``capture``)."""

    def __init__(self, gl, capture, control: Callable[[], None], match: str | None = None) -> None:
        self.gl, self.capture, self.control, self.match = gl, capture, control, match
        self.clock, self.gate, self.sampler = ThreadCpuClock(), LoadGate(), SystemSampler()
        self.environment: list[dict[str, float]] = []

    def measure(self, label: str, cases: dict[str, BenchCase], frames: int, passes: int,
                max_rounds: int) -> dict[str, dict[str, float]]:
        pending: dict[str, list[tuple[int, dict[str, float]]]] = {key: [] for key in cases}
        admitted = lambda key: [stats for index, stats in pending[key] if self.gate.admits(index)]  # noqa: E731
        keys = [key for key in cases if not self.match or self.match in key]
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

    def _pass(self, case: BenchCase, frames: int) -> dict[str, float]:
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
        return {"cpu_median": statistics.median(fastest["cpu"]), "cpu_p90": p90(fastest["cpu"]),
                "cpu_thread_median": statistics.median(fastest["thread"]), "cpu_thread_p90": p90(fastest["thread"]),
                "gpu_median": statistics.median(fastest["gpu"]), "gpu_p90": p90(fastest["gpu"]),
                "control_gpu_median": statistics.median(fastest["control_gpu"]),
                "control_cpu_median": statistics.median(fastest["control_cpu"]),
                "gpu_rel": ratio("gpu", "control_gpu"), "cpu_rel": ratio("thread", "control_thread")}
