#!/usr/bin/env python
"""Compare two synthetic benchmark suite summaries and flag regressions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ScenarioRuns = Dict[str, Dict[str, Any]]
WidgetKey = Tuple[str, str]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare synthetic suite summaries produced by run_synthetic_benchmark_suite.py",
    )
    parser.add_argument("baseline", type=Path, help="Path to baseline suite_summary.json")
    parser.add_argument("candidate", type=Path, help="Path to candidate suite_summary.json")
    parser.add_argument(
        "--max-late-frames-delta",
        type=int,
        default=0,
        help="Allowed increase in late frame count (per scenario). Default: 0",
    )
    parser.add_argument(
        "--max-thread-saturation-delta",
        type=int,
        default=0,
        help="Allowed increase in thread pool saturated frames (per pool.) Default: 0",
    )
    parser.add_argument(
        "--max-widget-avg-delta",
        type=float,
        default=0.25,
        help="Allowed increase in widget avg_ms (per widget/kind). Default: 0.25ms",
    )
    return parser.parse_args()


def _load_summary(path: Path) -> ScenarioRuns:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    runs: ScenarioRuns = {}
    for entry in payload.get("scenarios", []):
        name = entry.get("name")
        if not name:
            continue
        runs[name] = entry
    if not runs:
        raise RuntimeError(f"No scenarios in summary {path}")
    return runs


def _build_widget_map(summary_rows: List[Dict[str, Any]]) -> Dict[WidgetKey, Dict[str, Any]]:
    return {(row.get("widget"), row.get("kind")): row for row in summary_rows}


def _build_thread_map(stats: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {item.get("pool", ""): item for item in stats}


def _compare_timer(
    scenario: str,
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    max_delta: int,
    failures: List[str],
) -> None:
    base_timer = baseline.get("run", {}).get("frame_driver_timer", {})
    cand_timer = candidate.get("run", {}).get("frame_driver_timer", {})
    base_late = int(base_timer.get("late_frames", 0))
    cand_late = int(cand_timer.get("late_frames", 0))
    delta = cand_late - base_late
    if delta > max_delta:
        failures.append(
            f"[{scenario}] Late frames increased by {delta} (baseline={base_late}, candidate={cand_late}, allowed={max_delta})"
        )


def _compare_threads(
    scenario: str,
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    max_delta: int,
    failures: List[str],
) -> None:
    base_map = _build_thread_map(baseline.get("run", {}).get("thread_pool_stats", []))
    cand_map = _build_thread_map(candidate.get("run", {}).get("thread_pool_stats", []))
    for pool, base_stats in base_map.items():
        cand_stats = cand_map.get(pool)
        if not cand_stats:
            continue
        base_sat = int(base_stats.get("saturated_frames", 0))
        cand_sat = int(cand_stats.get("saturated_frames", 0))
        delta = cand_sat - base_sat
        if delta > max_delta:
            failures.append(
                f"[{scenario}] Thread pool '{pool}' saturation increased by {delta} (baseline={base_sat}, candidate={cand_sat}, allowed={max_delta})"
            )


def _compare_widgets(
    scenario: str,
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    max_delta: float,
    failures: List[str],
) -> None:
    base_widgets = _build_widget_map(baseline.get("summaries", []))
    cand_widgets = _build_widget_map(candidate.get("summaries", []))
    for key, base_row in base_widgets.items():
        cand_row = cand_widgets.get(key)
        if not cand_row:
            continue
        base_avg = float(base_row.get("avg_ms", 0.0))
        cand_avg = float(cand_row.get("avg_ms", 0.0))
        delta = cand_avg - base_avg
        if delta > max_delta:
            failures.append(
                f"[{scenario}] Widget {key} avg_ms increased by {delta:.3f}ms (baseline={base_avg:.3f}, candidate={cand_avg:.3f}, allowed={max_delta:.3f})"
            )


def main() -> int:
    args = _parse_args()
    baseline = _load_summary(args.baseline)
    candidate = _load_summary(args.candidate)

    failures: List[str] = []
    for name, base_entry in baseline.items():
        cand_entry = candidate.get(name)
        if not cand_entry:
            failures.append(f"Scenario '{name}' missing in candidate summary")
            continue
        _compare_timer(name, base_entry, cand_entry, args.max_late_frames_delta, failures)
        _compare_threads(name, base_entry, cand_entry, args.max_thread_saturation_delta, failures)
        _compare_widgets(name, base_entry, cand_entry, args.max_widget_avg_delta, failures)

    if failures:
        print("[COMPARE] Regressions detected:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("[COMPARE] Candidate metrics are within allowed deltas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
