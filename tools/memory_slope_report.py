"""Warm-plateau memory slopes and per-rebuild steps from existing `--usage` logs.

Reads the rotated ``screensaver_usage.log*`` files written by ``--usage`` (and,
when present, the ``--life`` lifecycle log for runtime-generation boundaries)
and reports, per runtime generation:

* the warm plateau window (samples after ``--warmup-minutes``);
* least-squares slopes of main private commit, USS, RSS and handles per hour;
* the step each runtime replacement added (settled value after vs. before).

It adds no sampling of its own. Typical use on the operator machine::

    python tools/memory_slope_report.py <log dir> --warmup-minutes 20

A bounded steady state shows slopes near zero once the image cache is warm;
steady growth that persists hour after hour is retention. Rebuild steps compare
equivalent settled points, so a step that repeats on every replacement is
per-generation retention, while one bounded step is first-use initialisation.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_SAMPLE_RX = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[USAGE\] sample (.*)$")
_GEN_RX = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Runtime generation advanced generation=(\d+) reason=(\S+)"
)
_FIELDS = (
    "private_main_mb",
    "uss_main_mb",
    "rss_main_mb",
    "handles_main",
    # Separates bounded image-cache fill and GPU/driver memory from commit growth.
    "cpu_cache_mb",
    "vram_dedicated_mb",
    "vram_shared_mb",
)


@dataclass
class Sample:
    ts: datetime
    values: dict[str, float]
    seq: int = -1


@dataclass
class Segment:
    generation: int
    reason: str
    started: datetime
    samples: list[Sample] = field(default_factory=list)
    process: int = 0


def _rotated(log_dir: Path, stem: str) -> list[Path]:
    paths = [p for p in log_dir.glob(f"{stem}*") if re.fullmatch(rf"{re.escape(stem)}(\.\d+)?", p.name)]

    def _order(path: Path) -> int:
        suffix = path.name[len(stem):]
        return -int(suffix[1:]) if suffix else 0

    return sorted(paths, key=_order)


def _parse_samples(log_dir: Path) -> list[Sample]:
    samples: list[Sample] = []
    for path in _rotated(log_dir, "screensaver_usage.log"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _SAMPLE_RX.match(line)
            if not match:
                continue
            pairs = dict(re.findall(r"(\w+)=([^ ]+)", match.group(2)))
            if "cpu_cache_bytes" in pairs:
                try:
                    pairs["cpu_cache_mb"] = str(float(pairs["cpu_cache_bytes"]) / (1024.0 * 1024.0))
                except ValueError:
                    pass
            values: dict[str, float] = {}
            for name in _FIELDS:
                try:
                    values[name] = float(pairs[name])
                except (KeyError, ValueError):
                    pass
            if values:
                try:
                    seq = int(pairs.get("seq", -1))
                except ValueError:
                    seq = -1
                samples.append(Sample(datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"), values, seq))
    samples.sort(key=lambda s: s.ts)
    return samples


def _parse_generations(log_dir: Path) -> list[tuple[datetime, int, str]]:
    edges: list[tuple[datetime, int, str]] = []
    for stem in ("screensaver_lifecycle.log", "screensaver.log"):
        for path in _rotated(log_dir, stem):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                match = _GEN_RX.match(line)
                if match:
                    edges.append(
                        (datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"), int(match.group(2)), match.group(3))
                    )
        if edges:
            break
    return sorted(set(edges))


def _slope_per_hour(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    n = float(len(points))
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    den = sum((x - mx) ** 2 for x, _ in points)
    if den <= 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in points) / den * 3600.0


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def build_segments(samples: list[Sample], edges: list[tuple[datetime, int, str]]) -> list[Segment]:
    if not samples:
        return []
    process = 0
    segments = [Segment(generation=0, reason="process_start", started=samples[0].ts)]
    # Only in-process replacements start a generation segment; terminal exits
    # and edges older than the first sample belong to other processes.
    edge_iter = iter(
        [edge for edge in edges if edge[2] != "application_exit" and edge[0] >= samples[0].ts]
    )
    pending = next(edge_iter, None)
    previous_seq = None
    for sample in samples:
        # The sampler sequence restarts with each process; a restart is a cold
        # start, never a replacement step of the previous process.
        if previous_seq is not None and 0 <= sample.seq < previous_seq:
            process += 1
            segments.append(
                Segment(generation=0, reason="process_start", started=sample.ts, process=process)
            )
            while pending is not None and pending[0] <= sample.ts:
                pending = next(edge_iter, None)
        previous_seq = sample.seq
        while pending is not None and sample.ts >= pending[0]:
            segments.append(
                Segment(generation=pending[1], reason=pending[2], started=pending[0], process=process)
            )
            pending = next(edge_iter, None)
        segments[-1].samples.append(sample)
    return [segment for segment in segments if segment.samples]


def report(log_dir: Path, *, warmup_minutes: float, settle_minutes: float) -> str:
    samples = _parse_samples(log_dir)
    if not samples:
        return f"no [USAGE] samples under {log_dir} (run with --usage)"
    segments = build_segments(samples, _parse_generations(log_dir))
    lines = [f"samples={len(samples)} first={samples[0].ts} last={samples[-1].ts} generations={len(segments)}"]
    previous_settled: dict[str, float] | None = None
    for index, segment in enumerate(segments):
        cold = segment.reason == "process_start"
        skip = warmup_minutes if cold else settle_minutes
        warm = [s for s in segment.samples if (s.ts - segment.started).total_seconds() >= skip * 60.0]
        head = warm[: max(1, min(8, len(warm)))] if warm else []
        tail = warm[-max(1, min(8, len(warm))):] if warm else []
        lines.append(
            f"process={segment.process} generation={segment.generation} reason={segment.reason} start={segment.started} "
            f"samples={len(segment.samples)} warm_samples={len(warm)}"
        )
        if len(warm) >= 2:
            span_h = (warm[-1].ts - warm[0].ts).total_seconds() / 3600.0
            for name in _FIELDS:
                points = [((s.ts - warm[0].ts).total_seconds(), s.values[name]) for s in warm if name in s.values]
                if not points:
                    continue
                first = _median([s.values[name] for s in head if name in s.values])
                last = _median([s.values[name] for s in tail if name in s.values])
                lines.append(
                    f"  {name:16s} warm_start={first:9.1f} warm_end={last:9.1f} "
                    f"slope_per_hour={_slope_per_hour(points):+8.1f} span_h={span_h:5.2f}"
                )
        settled = {
            name: _median([s.values[name] for s in head if name in s.values]) for name in _FIELDS
        } if head else None
        if cold:
            previous_settled = None
        if previous_settled is not None and settled is not None:
            steps = " ".join(
                f"{name}={settled[name] - previous_settled[name]:+.1f}"
                for name in _FIELDS
                if name in settled and name in previous_settled
            )
            lines.append(f"  replacement_step_vs_previous_settled: {steps}")
        if tail:
            previous_settled = {
                name: _median([s.values[name] for s in tail if name in s.values]) for name in _FIELDS
            }
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log_dir", type=Path)
    parser.add_argument("--warmup-minutes", type=float, default=20.0, help="cold-start cache warm-up excluded from slopes")
    parser.add_argument("--settle-minutes", type=float, default=1.0, help="post-replacement settle excluded per generation")
    args = parser.parse_args()
    print(report(args.log_dir, warmup_minutes=args.warmup_minutes, settle_minutes=args.settle_minutes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
