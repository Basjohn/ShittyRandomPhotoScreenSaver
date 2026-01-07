"""Spotify VIS and Slide metrics parser for quick PERF diagnostics.

Summarises `[PERF] [SPOTIFY_VIS] Tick/Paint metrics` and
`[PERF] [GL COMPOSITOR] Slide metrics` from a single PERF log file.

Intended for ad-hoc use when `SRPSS_PERF_METRICS=1` is enabled.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Tuple


@dataclass
class PerfSample:
    duration_ms: float
    frames: int
    avg_fps: float
    dt_min_ms: Optional[float]
    dt_max_ms: Optional[float]


@dataclass
class SpotifySummary:
    tick: List[PerfSample]
    paint: List[PerfSample]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize Spotify VIS Tick/Paint metrics and GL Slide metrics from "
            "a PERF log file (screensaver_perf.log)."
        )
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("logs") / "screensaver_perf.log",
        help="Path to the PERF log file to analyze (default: logs/screensaver_perf.log)",
    )
    return parser


def _parse_perf_payload(line: str, marker: str) -> Optional[PerfSample]:
    idx = line.find(marker)
    if idx == -1:
        return None

    payload = line[idx + len(marker) :].strip()
    if not payload:
        return None

    parts = [p.strip() for p in payload.split(",") if p.strip()]

    duration_ms: Optional[float] = None
    frames: Optional[int] = None
    avg_fps: Optional[float] = None
    dt_min_ms: Optional[float] = None
    dt_max_ms: Optional[float] = None

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
        except ValueError:
            continue

    if duration_ms is None or frames is None or avg_fps is None:
        return None

    return PerfSample(
        duration_ms=duration_ms,
        frames=frames,
        avg_fps=avg_fps,
        dt_min_ms=dt_min_ms,
        dt_max_ms=dt_max_ms,
    )


def _collect_spotify_samples(lines: List[str]) -> SpotifySummary:
    tick: List[PerfSample] = []
    paint: List[PerfSample] = []

    for raw in lines:
        line = raw.rstrip("\n")
        if "[PERF] [SPOTIFY_VIS]" not in line:
            continue

        if "Tick metrics:" in line:
            sample = _parse_perf_payload(line, "Tick metrics:")
            if sample is not None:
                tick.append(sample)
        elif "Paint metrics:" in line:
            sample = _parse_perf_payload(line, "Paint metrics:")
            if sample is not None:
                paint.append(sample)

    return SpotifySummary(tick=tick, paint=paint)


def _collect_slide_samples(lines: List[str]) -> List[Tuple[str, PerfSample]]:
    from scripts.slide_metrics_parser import _parse_slide_metrics_line  # type: ignore[import]

    result: List[Tuple[str, PerfSample]] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if "[GL COMPOSITOR]" not in line or "Slide metrics:" not in line:
            continue
        sample = _parse_slide_metrics_line(line)
        if sample is None:
            continue
        perf = PerfSample(
            duration_ms=sample.duration_ms,
            frames=sample.frames,
            avg_fps=sample.avg_fps,
            dt_min_ms=sample.dt_min_ms,
            dt_max_ms=sample.dt_max_ms,
        )
        result.append((sample.size, perf))
    return result


def _format_stats(values: List[float]) -> str:
    if not values:
        return "n/a"
    vmin = min(values)
    vmax = max(values)
    avg = sum(values) / len(values)
    return f"mean={avg:.2f}, min={vmin:.2f}, max={vmax:.2f}"


def _summarize_spotify(summary: SpotifySummary) -> None:
    print("Spotify VIS metrics (Tick)")
    if not summary.tick:
        print("  No Tick metrics found.")
    else:
        dur = [s.duration_ms for s in summary.tick]
        fps = [s.avg_fps for s in summary.tick]
        dt_min = [s.dt_min_ms for s in summary.tick if s.dt_min_ms is not None]
        dt_max = [s.dt_max_ms for s in summary.tick if s.dt_max_ms is not None]
        print(f"  windows   : {len(summary.tick)}")
        print(f"  duration  : {_format_stats(dur)}")
        print(f"  avg_fps   : {_format_stats(fps)}")
        print(f"  dt_min_ms : {_format_stats(dt_min)}")
        print(f"  dt_max_ms : {_format_stats(dt_max)}")

    print("\nSpotify VIS metrics (Paint)")
    if not summary.paint:
        print("  No Paint metrics found.")
    else:
        dur = [s.duration_ms for s in summary.paint]
        fps = [s.avg_fps for s in summary.paint]
        dt_min = [s.dt_min_ms for s in summary.paint if s.dt_min_ms is not None]
        dt_max = [s.dt_max_ms for s in summary.paint if s.dt_max_ms is not None]
        print(f"  windows   : {len(summary.paint)}")
        print(f"  duration  : {_format_stats(dur)}")
        print(f"  avg_fps   : {_format_stats(fps)}")
        print(f"  dt_min_ms : {_format_stats(dt_min)}")
        print(f"  dt_max_ms : {_format_stats(dt_max)}")

        # Highlight clearly bad windows for quick scanning.
        bad = [s for s in summary.paint if (s.dt_max_ms or 0.0) > 250.0 or s.avg_fps < 25.0]
        if bad:
            worst = max((s.dt_max_ms or 0.0) for s in bad)
            print(f"\n  WARN: {len(bad)} paint windows have dt_max>250ms or avg_fps<25.0 (worst dt_max={worst:.2f}ms)")


def _summarize_slide(slide: List[Tuple[str, PerfSample]]) -> None:
    print("\nGL Slide metrics (from PERF log)")
    if not slide:
        print("  No Slide metrics found.")
        return

    by_size: Dict[str, List[PerfSample]] = {}
    for size, sample in slide:
        by_size.setdefault(size, []).append(sample)

    for size, samples in sorted(by_size.items()):
        dur = [s.duration_ms for s in samples]
        fps = [s.avg_fps for s in samples]
        dt_max = [s.dt_max_ms for s in samples if s.dt_max_ms is not None]
        print(f"  size={size} ({len(samples)} samples)")
        print(f"    duration  : {_format_stats(dur)}")
        print(f"    avg_fps   : {_format_stats(fps)}")
        print(f"    dt_max_ms : {_format_stats(dt_max)}")


def main() -> int:
    # Only run when PERF metrics were enabled for the session.
    perf_env = os.environ.get("SRPSS_PERF_METRICS", "0").strip().lower()
    if perf_env not in {"1", "true", "yes"}:
        print("SRPSS_PERF_METRICS is not enabled; this script is intended for PERF runs only.")
        return 1

    parser = _build_parser()
    # When invoked from main.py, additional flags such as --debug may be
    # present in sys.argv. Treat them as opaque and ignore them here so
    # PERF summaries still run without interfering with the main
    # application argument handling.
    args, _unknown = parser.parse_known_args()

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

    spotify = _collect_spotify_samples(lines)
    slide = _collect_slide_samples(lines)

    print(f"Perf summary for {log_path}\n")
    _summarize_spotify(spotify)
    _summarize_slide(slide)

    return 0


if __name__ == "__main__":  # pragma: no cover - ad-hoc tool
    raise SystemExit(main())
