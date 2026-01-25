#!/usr/bin/env python
"""
Automation helper that runs the synthetic widget benchmark across predefined
scenarios (steady baseline vs. stress) and captures JSONL artefacts for CI use.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_PATH = REPO_ROOT / "tools" / "synthetic_widget_benchmark.py"


ScenarioDef = Dict[str, Any]


SCENARIOS: Dict[str, ScenarioDef] = {
    "steady-baseline": {
        "description": "2 displays, single widget copies, steady cadence (baseline parity check).",
        "args": [
            "--display-count",
            "2",
            "--frames",
            "600",
            "--cadence-mode",
            "steady",
            "--weather-per-display",
            "1",
            "--reddit-per-display",
            "1",
            "--clock-per-display",
            "1",
            "--media-per-display",
            "1",
            "--transitions",
            "--transition-speed-scale",
            "1.0",
        ],
    },
    "stress-stack": {
        "description": "2 displays, duplicated widgets, stress cadence (forces timer + thread saturation).",
        "args": [
            "--display-count",
            "2",
            "--frames",
            "600",
            "--cadence-mode",
            "stress",
            "--weather-per-display",
            "2",
            "--reddit-per-display",
            "2",
            "--clock-per-display",
            "1",
            "--media-per-display",
            "2",
            "--transitions",
            "--transition-speed-scale",
            "1.5",
            "--weather-updates-per-frame",
            "3",
        ],
    },
    "weather-anim-dual": {
        "description": "2 displays, weather animation enabled independently on both widgets.",
        "args": [
            "--display-count",
            "2",
            "--frames",
            "600",
            "--cadence-mode",
            "steady",
            "--weather-per-display",
            "1",
            "--reddit",
            "--no-reddit",
            "--clock",
            "--no-clock",
            "--media",
            "--no-media",
            "--weather-animated-icon",
            "right",
            "--weather-animate",
            "--weather-animated-displays",
            "all",
        ],
    },
    "weather-anim-shared": {
        "description": "2 displays, weather animation shared via single driver (baseline for fix).",
        "args": [
            "--display-count",
            "2",
            "--frames",
            "600",
            "--cadence-mode",
            "steady",
            "--weather-per-display",
            "1",
            "--reddit",
            "--no-reddit",
            "--clock",
            "--no-clock",
            "--media",
            "--no-media",
            "--weather-animated-icon",
            "right",
            "--weather-animate",
            "--weather-animated-displays",
            "all",
            "--weather-shared-animation-driver",
        ],
    },
    "clock-dual-raw": {
        "description": "2 displays, two clocks per display with independent timers (duplicates real regression).",
        "args": [
            "--display-count",
            "2",
            "--frames",
            "600",
            "--cadence-mode",
            "steady",
            "--clock-per-display",
            "2",
            "--no-weather",
            "--no-reddit",
            "--no-media",
            "--no-transitions",
            "--no-clock-shared-tick",
        ],
    },
    "clock-dual-shared": {
        "description": "Same layout as clock-dual-raw but drives all clocks from the shared tick hub.",
        "args": [
            "--display-count",
            "2",
            "--frames",
            "600",
            "--cadence-mode",
            "steady",
            "--clock-per-display",
            "2",
            "--no-weather",
            "--no-reddit",
            "--no-media",
            "--no-transitions",
            "--clock-shared-tick",
        ],
    },
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run synthetic_widget_benchmark across predefined scenarios."
    )
    parser.add_argument(
        "--scenario",
        dest="scenarios",
        action="append",
        choices=sorted(SCENARIOS.keys()),
        help="Scenario(s) to execute (default: all). Can be passed multiple times.",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="Print scenario definitions and exit.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / ".cache" / "synthetic_suite",
        help="Directory where JSONL artefacts and the suite summary will be written.",
    )
    parser.add_argument(
        "--harness-arg",
        action="append",
        dest="extra_args",
        default=[],
        help="Additional argument appended to every harness invocation (can repeat).",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Python interpreter to use when launching the benchmark harness.",
    )
    return parser.parse_args()


def _print_scenarios() -> None:
    rows = []
    for name, data in SCENARIOS.items():
        block = textwrap.dedent(
            f"""
            {name}
              Description: {data['description']}
              Args: {' '.join(data['args'])}
            """
        ).strip()
        rows.append(block)
    print("\n\n".join(rows))


def _run_harness(
    python_exe: Path,
    scenario_name: str,
    scenario: ScenarioDef,
    output_dir: Path,
    extra_args: List[str],
) -> Dict[str, Any]:
    scenario_dir = output_dir / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = scenario_dir / "run.jsonl"
    cmd = [str(python_exe), str(HARNESS_PATH), *scenario["args"], *extra_args, "--json-output", str(jsonl_path)]
    print(f"[SUITE] Running {scenario_name}: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    run_meta, summaries = _load_jsonl(jsonl_path)
    return {
        "name": scenario_name,
        "description": scenario["description"],
        "command": cmd,
        "jsonl": str(jsonl_path),
        "run": run_meta,
        "summaries": summaries,
    }


def _load_jsonl(path: Path) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    run_entry: Dict[str, Any] = {}
    summaries: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            entry = json.loads(line)
            entry_type = entry.get("type")
            if entry_type == "run":
                run_entry = entry
            elif entry_type == "summary":
                summaries.append(entry)
    if not run_entry:
        raise RuntimeError(f"No run metadata found in {path}")
    return run_entry, summaries


def main() -> int:
    args = _parse_args()
    if args.list_scenarios:
        _print_scenarios()
        return 0

    scenarios = args.scenarios or list(SCENARIOS.keys())
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for name in scenarios:
        scenario = SCENARIOS[name]
        result = _run_harness(args.python, name, scenario, output_dir, args.extra_args)
        run_meta = result["run"]
        timer = run_meta.get("frame_driver_timer", {})
        print(
            textwrap.dedent(
                f"""
                [SUITE] Scenario {name} complete
                  Frames: {run_meta.get('frames')}
                  Interval(ms): {run_meta.get('interval_ms')}
                  Late frames: {timer.get('late_frames', 0)} (threshold {timer.get('warn_threshold_ms', 'n/a')}ms)
                  Thread pools: {run_meta.get('thread_pool_stats', [])}
                """
            ).strip()
        )
        results.append(result)

    summary_path = output_dir / "suite_summary.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "scenarios": results,
            },
            fh,
            indent=2,
        )
    print(f"[SUITE] Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
