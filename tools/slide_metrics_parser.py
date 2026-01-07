"""Slide metrics log parser for quick GL compositor performance diagnostics.

Summarizes `[PERF] [GL COMPOSITOR] Slide metrics` entries from a single
screensaver log file, grouped by output size/resolution.

Intended for ad-hoc use during Route 3 investigations into Slide smoothness
and mixed-refresh behaviour.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class SlideSample:
    duration_ms: float
    frames: int
    avg_fps: float
    dt_min_ms: float | None
    dt_max_ms: float | None
    size: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize GLCompositor Slide metrics from a screensaver log file "
            "(duration, fps, dt_min/dt_max) grouped by resolution."
        )
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("logs") / "screensaver_perf.log",
        help="Path to the PERF log file to analyze (default: logs/screensaver_perf.log)",
    )
    return parser


def _parse_slide_metrics_line(line: str) -> SlideSample | None:
    """Parse a single `[GL COMPOSITOR] Slide metrics:` line.

    Expected payload format after the marker, for example:

        Slide metrics: duration=7621.2ms, frames=460, avg_fps=60.4,
        dt_min=0.53ms, dt_max=33.27ms, size=2560x1439
    """

    marker = "Slide metrics:"
    idx = line.find(marker)
    if idx == -1:
        return None

    payload = line[idx + len(marker) :].strip()
    if not payload:
        return None

    parts = [p.strip() for p in payload.split(",") if p.strip()]

    duration_ms: float | None = None
    frames: int | None = None
    avg_fps: float | None = None
    dt_min_ms: float | None = None
    dt_max_ms: float | None = None
    size: str | None = None

    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        try:
            if key == "duration":
                duration_ms = float(value.rstrip("ms"))
            elif key == "frames":
                frames = int(value)
            elif key == "avg_fps":
                avg_fps = float(value)
            elif key == "dt_min":
                dt_min_ms = float(value.rstrip("ms"))
            elif key == "dt_max":
                dt_max_ms = float(value.rstrip("ms"))
            elif key == "size":
                size = value
        except ValueError:
            # If any individual field fails to parse, skip it and continue.
            continue

    if duration_ms is None or frames is None or avg_fps is None or size is None:
        return None

    return SlideSample(
        duration_ms=duration_ms,
        frames=frames,
        avg_fps=avg_fps,
        dt_min_ms=dt_min_ms,
        dt_max_ms=dt_max_ms,
        size=size,
    )


def _format_stats(values: List[float]) -> str:
    if not values:
        return "n/a"
    vmin = min(values)
    vmax = max(values)
    avg = sum(values) / len(values)
    return f"mean={avg:.2f}, min={vmin:.2f}, max={vmax:.2f}"


def _summarize_slide_metrics(log_path: Path, lines: List[str]) -> None:
    samples: List[SlideSample] = []
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if "[GL COMPOSITOR]" not in line or "Slide metrics:" not in line:
            continue
        sample = _parse_slide_metrics_line(line)
        if sample is not None:
            samples.append(sample)

    print(f"Slide metrics summary for {log_path}")

    if not samples:
        print("No Slide metrics entries found.")
        return

    # Overall stats
    durations = [s.duration_ms for s in samples]
    fps_values = [s.avg_fps for s in samples]
    dt_max_values = [s.dt_max_ms for s in samples if s.dt_max_ms is not None]

    print("\nOverall:")
    print(f"  samples    : {len(samples)}")
    print(f"  duration_ms: {_format_stats(durations)}")
    print(f"  avg_fps    : {_format_stats(fps_values)}")
    print(f"  dt_max_ms  : {_format_stats(dt_max_values)}")

    # Group by size/resolution
    by_size: Dict[str, List[SlideSample]] = {}
    for s in samples:
        by_size.setdefault(s.size, []).append(s)

    print("\nBy size (resolution):")
    for size, group in sorted(by_size.items()):
        g_durations = [s.duration_ms for s in group]
        g_fps = [s.avg_fps for s in group]
        g_dt_max = [s.dt_max_ms for s in group if s.dt_max_ms is not None]

        print(f"  size={size} ({len(group)} samples)")
        print(f"    duration_ms: {_format_stats(g_durations)}")
        print(f"    avg_fps    : {_format_stats(g_fps)}")
        print(f"    dt_max_ms  : {_format_stats(g_dt_max)}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    log_path: Path = args.log

    if not log_path.exists() or not log_path.is_file():
        print(f"Log file not found: {log_path}")
        return 1

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"Failed to read log file {log_path}: {exc}")
        return 1

    lines = text.splitlines()
    _summarize_slide_metrics(log_path, lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
