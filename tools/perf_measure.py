"""Read-only SRPSS process resource sampler.

This tool measures *process resource shape* without pretending those counters are
presentation/reaction proof.  For Visualizer freshness, GPU telemetry, GC tails, transitions and Quick
presentation use the application's own PERF/usage instrumentation and the
focused contract/tests for the subsystem being investigated.

Safety/authority rules:
- attaching to an existing PID never terminates it;
- launching the app is explicit via ``--launch`` and only that child is stopped;
- no parser is imported/executed by production code;
- CPU/RAM/thread/handle numbers are context, not permission to reduce authored
  cadence, newest-state freshness, cache bounds or R-69 reactivity.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import psutil

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ResourceSample:
    elapsed_s: float
    cpu_pct: float
    rss_mb: float
    uss_mb: float | None
    private_mb: float | None
    threads: int
    handles: int | None
    children: int


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return float(ordered[max(0, min(len(ordered) - 1, index))])


def _process_tree(root: psutil.Process) -> list[psutil.Process]:
    processes = [root]
    try:
        processes.extend(root.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    alive: list[psutil.Process] = []
    seen: set[int] = set()
    for process in processes:
        if process.pid in seen:
            continue
        seen.add(process.pid)
        try:
            if process.is_running():
                alive.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return alive


def _memory_fields(process: psutil.Process) -> tuple[int, int | None, int | None]:
    info = process.memory_info()
    rss = int(info.rss)
    uss: int | None = None
    private: int | None = None
    try:
        full = process.memory_full_info()
        if hasattr(full, "uss"):
            uss = int(full.uss)
        # Windows exposes ``private``; some psutil builds expose ``private_bytes``.
        for name in ("private", "private_bytes"):
            if hasattr(full, name):
                private = int(getattr(full, name))
                break
    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
        pass
    return rss, uss, private


def _sample_tree(root: psutil.Process, *, started: float) -> ResourceSample:
    processes = _process_tree(root)
    cpu = 0.0
    rss = 0
    uss_total = 0
    private_total = 0
    uss_known = False
    private_known = False
    threads = 0
    handles = 0
    handles_known = False

    for process in processes:
        try:
            cpu += float(process.cpu_percent(interval=None))
            proc_rss, proc_uss, proc_private = _memory_fields(process)
            rss += proc_rss
            if proc_uss is not None:
                uss_total += proc_uss
                uss_known = True
            if proc_private is not None:
                private_total += proc_private
                private_known = True
            threads += int(process.num_threads())
            if hasattr(process, "num_handles"):
                handles += int(process.num_handles())
                handles_known = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    mib = 1024.0 * 1024.0
    return ResourceSample(
        elapsed_s=time.monotonic() - started,
        cpu_pct=cpu,
        rss_mb=rss / mib,
        uss_mb=(uss_total / mib) if uss_known else None,
        private_mb=(private_total / mib) if private_known else None,
        threads=threads,
        handles=handles if handles_known else None,
        children=max(0, len(processes) - 1),
    )


def _summarize(samples: list[ResourceSample]) -> dict[str, object]:
    def numeric(name: str) -> dict[str, float | None]:
        values = [float(getattr(sample, name)) for sample in samples if getattr(sample, name) is not None]
        if not values:
            return {"mean": None, "median": None, "p95": None, "max": None}
        return {
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "p95": _percentile(values, 0.95),
            "max": max(values),
        }

    return {
        "samples": len(samples),
        "cpu_pct": numeric("cpu_pct"),
        "rss_mb": numeric("rss_mb"),
        "uss_mb": numeric("uss_mb"),
        "private_mb": numeric("private_mb"),
        "threads": numeric("threads"),
        "handles": numeric("handles"),
        "children": numeric("children"),
        "first": asdict(samples[0]) if samples else None,
        "last": asdict(samples[-1]) if samples else None,
        "interpretation": (
            "Process CPU may exceed 100% (approximately one logical CPU per 100%). "
            "These resource counters do not replace application freshness/latency/GPU telemetry."
        ),
    }


def _prime_cpu(root: psutil.Process) -> None:
    for process in _process_tree(root):
        try:
            process.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def _stop_launched(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sample current SRPSS process resource usage safely")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pid", type=int, help="Attach to an existing SRPSS PID; never terminated by this tool")
    source.add_argument(
        "--launch",
        action="store_true",
        help="Explicitly launch this tree's main.py --perf and stop only that child when sampling ends",
    )
    parser.add_argument("--duration", type=float, default=30.0, help="Sampling duration in seconds (default: 30)")
    parser.add_argument("--interval", type=float, default=0.5, help="Sampling interval in seconds (default: 0.5)")
    parser.add_argument("--startup-wait", type=float, default=4.0, help="Wait after --launch before sampling")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    if args.duration <= 0 or args.interval <= 0:
        raise SystemExit("--duration and --interval must be positive")

    launched: subprocess.Popen[bytes] | None = None
    try:
        if args.launch:
            launched = subprocess.Popen(
                [sys.executable, str(ROOT / "main.py"), "--perf"],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(max(0.0, args.startup_wait))
            if launched.poll() is not None:
                print(f"SRPSS exited before sampling (code={launched.returncode})", file=sys.stderr)
                return 2
            root = psutil.Process(launched.pid)
        else:
            try:
                root = psutil.Process(int(args.pid))
            except (psutil.NoSuchProcess, ValueError):
                print(f"PID not found: {args.pid}", file=sys.stderr)
                return 2

        _prime_cpu(root)
        started = time.monotonic()
        samples: list[ResourceSample] = []
        next_sample = started
        while time.monotonic() - started < args.duration:
            now = time.monotonic()
            if now < next_sample:
                time.sleep(min(next_sample - now, 0.1))
                continue
            try:
                samples.append(_sample_tree(root, started=started))
            except psutil.NoSuchProcess:
                break
            next_sample += args.interval

        report = {
            "kind": "srpss_process_resource_sample",
            "pid": root.pid,
            "launched_by_tool": bool(launched),
            "duration_requested_s": args.duration,
            "interval_s": args.interval,
            "summary": _summarize(samples),
        }
        text = json.dumps(report, indent=2, sort_keys=True)
        print(text)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        return 0 if samples else 3
    finally:
        if launched is not None:
            _stop_launched(launched)


if __name__ == "__main__":
    raise SystemExit(main())
