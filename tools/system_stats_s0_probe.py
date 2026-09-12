"""Run the non-product System Stats S0 source measurement.

This script creates no SRPSS runtime service and has no recurring scheduler. It
samples sources directly as the preserved bounded admission/diagnostic harness;
running it never activates the product card.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.system_stats.source import (  # noqa: E402
    PersistentWindowsGpuAdapterSource,
    WholeSystemCpuRamSource,
)


def _burn_cpu(seconds: float) -> int:
    deadline = time.perf_counter() + max(0.0, seconds)
    value = 0
    while time.perf_counter() < deadline:
        value = (value * 1664525 + 1013904223) & 0xFFFFFFFF
    return value


def _summary(values_ms: list[float]) -> dict[str, float | int]:
    ordered = sorted(values_ms)

    def percentile(fraction: float) -> float:
        if not ordered:
            return 0.0
        return ordered[round((len(ordered) - 1) * fraction)]

    return {
        "samples": len(ordered),
        "p50_ms": percentile(0.50),
        "p95_ms": percentile(0.95),
        "max_ms": max(ordered, default=0.0),
    }


def _measure(condition: str, samples: int, interval_seconds: float) -> dict[str, Any]:
    cpu_ram = WholeSystemCpuRamSource()
    gpu = PersistentWindowsGpuAdapterSource() if condition == "gpu" else None
    durations: list[float] = []
    statuses: list[dict[str, Any]] = []
    for index in range(samples):
        started = time.perf_counter()
        if condition != "baseline":
            cpu_sample = cpu_ram.sample()
        else:
            cpu_sample = None
        gpu_sample = gpu.sample() if gpu is not None else None
        durations.append((time.perf_counter() - started) * 1000.0)
        statuses.append(
            {
                "index": index,
                "cpu_status": None if cpu_sample is None else cpu_sample.cpu_status,
                "ram_status": None if cpu_sample is None else cpu_sample.ram_status,
                "gpu_status": None if gpu_sample is None else gpu_sample.status,
                "gpu_cardinality": None if gpu is None else gpu.cardinality(),
            }
        )
        if index + 1 < samples:
            time.sleep(max(0.0, interval_seconds))
    if gpu is not None:
        gpu.close()
    return {
        "condition": condition,
        "timing": _summary(durations),
        "observations": statuses,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded System Stats S0 source probe")
    parser.add_argument(
        "--condition", choices=("baseline", "cpu-ram", "gpu", "all"), default="all"
    )
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    parser.add_argument("--contention-workers", type=int, default=0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    samples = max(2, int(args.samples))
    interval = max(0.0, float(args.interval_seconds))
    conditions = (
        ("baseline", "cpu-ram", "gpu") if args.condition == "all" else (args.condition,)
    )
    total_seconds = len(conditions) * max(0, samples - 1) * interval + 5.0
    workers = max(0, int(args.contention_workers))
    result: dict[str, Any] = {
        "samples": samples,
        "interval_seconds": interval,
        "contention_workers": workers,
        "conditions": [],
    }
    with (
        ProcessPoolExecutor(max_workers=workers)
        if workers
        else _NullExecutor() as executor
    ):
        futures = [executor.submit(_burn_cpu, total_seconds) for _ in range(workers)]
        for condition in conditions:
            result["conditions"].append(_measure(condition, samples, interval))
        for future in futures:
            future.result()
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


class _NullExecutor:
    def __enter__(self) -> "_NullExecutor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def submit(self, *_args: object, **_kwargs: object) -> Any:
        raise AssertionError("no workers should be submitted")


if __name__ == "__main__":
    raise SystemExit(main())
