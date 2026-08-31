"""Summarize SRPSS image-change admission, cache, GC, and HUD telemetry.

Read-only checkpoint tool for the Qt Quick performance investigation.  It is
purposefully dependency-free so captured Windows logs can be inspected on any
machine without importing PySide6 or project runtime modules.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable


_IMAGE_CHANGE_RE = re.compile(r"\[PERF\]\[IMAGE_CHANGE\]\s+(?P<payload>.*)")
_GC_RE = re.compile(r"\[PERF\]\[GC_POLICY\]\s+(?P<payload>.*)")
_PREFETCH_RE = re.compile(r"\[PERF\]\s+\[PREFETCH\]\s+(?P<payload>.*)")
_HUD_RE = re.compile(r"\[PERF\]\s+\[PERF_HUD\]\s+(?P<payload>.*)")
_KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)")


def _kv(payload: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in _KV_RE.finditer(payload)}


def _float(fields: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(fields.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _int(fields: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(fields.get(key, default)))
    except (TypeError, ValueError):
        return int(default)


@dataclass
class TraceSummary:
    trace_id: str
    origin: str = "unknown"
    max_delta_ms: float = 0.0
    max_delta_stage: str = ""
    finished_ms: float | None = None
    outcome: str = ""
    process_sources: Counter[str] = field(default_factory=Counter)
    stages: list[tuple[str, float, float]] = field(default_factory=list)

    def add(self, fields: dict[str, str]) -> None:
        self.origin = fields.get("origin", self.origin)
        stage = fields.get("stage", "unknown")
        delta = _float(fields, "delta_ms")
        elapsed = _float(fields, "elapsed_ms")
        self.stages.append((stage, elapsed, delta))
        if delta > self.max_delta_ms:
            self.max_delta_ms = delta
            self.max_delta_stage = stage
        if stage == "display_processed":
            self.process_sources[fields.get("source", "unknown")] += 1
        if stage == "finished":
            self.finished_ms = elapsed
            self.outcome = fields.get("outcome", "")


@dataclass
class PerfReport:
    traces: dict[str, TraceSummary] = field(default_factory=dict)
    gc_events: list[tuple[int, float, int]] = field(default_factory=list)
    prefetch_protected_counts: list[int] = field(default_factory=list)
    hud_dt_max_ms: list[float] = field(default_factory=list)

    def ingest(self, line: str) -> None:
        match = _IMAGE_CHANGE_RE.search(line)
        if match:
            fields = _kv(match.group("payload"))
            trace_id = fields.get("id", "unknown")
            trace = self.traces.setdefault(trace_id, TraceSummary(trace_id))
            trace.add(fields)
            return
        match = _GC_RE.search(line)
        if match:
            fields = _kv(match.group("payload"))
            self.gc_events.append(
                (
                    _int(fields, "generation", -1),
                    _float(fields, "duration_ms"),
                    _int(fields, "collected"),
                )
            )
            return
        match = _PREFETCH_RE.search(line)
        if match:
            fields = _kv(match.group("payload"))
            if "protected_immediate" in fields:
                self.prefetch_protected_counts.append(_int(fields, "protected_immediate"))
            return
        match = _HUD_RE.search(line)
        if match:
            fields = _kv(match.group("payload"))
            # Accept both the scene HUD's intended dt_max_ms spelling and a
            # future shorter spelling without coupling this parser to QML text.
            if "dt_max_ms" in fields:
                self.hud_dt_max_ms.append(_float(fields, "dt_max_ms"))
            elif "dt_max" in fields:
                self.hud_dt_max_ms.append(_float(fields, "dt_max"))

    def render(self) -> str:
        lines: list[str] = []
        traces = list(self.traces.values())
        lines.append(f"image_change_traces={len(traces)}")
        by_origin: dict[str, list[TraceSummary]] = defaultdict(list)
        for trace in traces:
            by_origin[trace.origin].append(trace)

        for origin in sorted(by_origin):
            group = by_origin[origin]
            completed = [t for t in group if t.finished_ms is not None]
            durations = [float(t.finished_ms) for t in completed if t.finished_ms is not None]
            source_counts: Counter[str] = Counter()
            for trace in group:
                source_counts.update(trace.process_sources)
            worst = max(group, key=lambda t: t.max_delta_ms)
            mean_ms = sum(durations) / len(durations) if durations else 0.0
            max_ms = max(durations, default=0.0)
            lines.append(
                f"origin={origin} traces={len(group)} completed={len(completed)} "
                f"mean_admission_ms={mean_ms:.2f} max_admission_ms={max_ms:.2f} "
                f"worst_stage={worst.max_delta_stage or 'none'} "
                f"worst_stage_delta_ms={worst.max_delta_ms:.2f} "
                f"sources={dict(source_counts)}"
            )

        timer = by_origin.get("timer", [])
        manual = by_origin.get("manual_next", [])
        if timer or manual:
            timer_worker = sum(t.process_sources.get("image_worker", 0) for t in timer)
            manual_worker = sum(t.process_sources.get("image_worker", 0) for t in manual)
            lines.append(
                "natural_vs_manual "
                f"timer_image_worker={timer_worker} manual_image_worker={manual_worker} "
                f"timer_traces={len(timer)} manual_traces={len(manual)}"
            )

        if self.gc_events:
            durations = [duration for _generation, duration, _collected in self.gc_events]
            zero_collect = sum(1 for _generation, _duration, collected in self.gc_events if collected == 0)
            gen_counts = Counter(generation for generation, _duration, _collected in self.gc_events)
            lines.append(
                f"gc_events={len(self.gc_events)} max_ms={max(durations):.2f} "
                f"mean_ms={sum(durations)/len(durations):.2f} "
                f"zero_collect={zero_collect} generations={dict(gen_counts)}"
            )
        else:
            lines.append("gc_events=0")

        if self.prefetch_protected_counts:
            lines.append(
                f"prefetch_protected_samples={len(self.prefetch_protected_counts)} "
                f"min={min(self.prefetch_protected_counts)} "
                f"max={max(self.prefetch_protected_counts)}"
            )
        else:
            lines.append("prefetch_protected_samples=0")

        if self.hud_dt_max_ms:
            lines.append(
                f"hud_samples={len(self.hud_dt_max_ms)} "
                f"dt_max_observed_ms={max(self.hud_dt_max_ms):.2f}"
            )
        return "\n".join(lines)


def parse_lines(lines: Iterable[str]) -> PerfReport:
    report = PerfReport()
    for line in lines:
        report.ingest(line)
    return report


def parse_paths(paths: Iterable[Path]) -> PerfReport:
    report = PerfReport()
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                report.ingest(line)
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path, help="SRPSS log files")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    report = parse_paths(args.logs)
    print(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
