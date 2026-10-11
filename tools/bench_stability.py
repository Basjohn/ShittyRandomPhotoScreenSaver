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
