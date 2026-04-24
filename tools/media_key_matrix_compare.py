"""Run media-key matrix harness across focus policies and summarize results.

One-command automation wrapper for U-05 investigations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "media_key_matrix_harness.py"


def _run_policy(
    policy: str,
    launch: str,
    profile_mode: str,
    scenarios: str,
    launch_timeout_s: float,
    output_root: Path,
) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        str(HARNESS),
        "--launch",
        launch,
        "--profile-mode",
        profile_mode,
        "--focus-policy",
        policy,
        "--scenarios",
        scenarios,
        "--launch-timeout-s",
        str(launch_timeout_s),
        "--output-dir",
        str(output_root / policy),
    ]
    start = time.time()
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
    duration_s = round(time.time() - start, 2)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Policy '{policy}' run failed (code={proc.returncode}).\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )

    json_line = ""
    for line in (proc.stdout or "").splitlines():
        if "Report JSON:" in line:
            json_line = line
            break
    if not json_line:
        raise RuntimeError(f"Policy '{policy}' run did not print report JSON path.")
    report_path = Path(json_line.split("Report JSON:", 1)[1].strip())
    if not report_path.exists():
        raise RuntimeError(f"Policy '{policy}' report JSON missing: {report_path}")

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        "policy": policy,
        "duration_s": duration_s,
        "report_json": str(report_path),
        "report_md": str(report_path.with_name("matrix_report.md")),
        "payload": payload,
    }


def _scenario_row(policy_result: Dict[str, Any], scenario_name: str) -> Dict[str, Any]:
    payload = policy_result["payload"]
    for row in payload.get("scenarios", []):
        if row.get("scenario") == scenario_name:
            return row
    return {}


def _write_summary(path: Path, run_rows: List[Dict[str, Any]], scenarios: List[str]) -> None:
    lines: List[str] = []
    lines.append("# Media Matrix Compare Summary")
    lines.append("")
    lines.append(f"- Generated: `{time.strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append("")
    lines.append("## Runs")
    lines.append("")
    for row in run_rows:
        lines.append(
            f"- Policy `{row['policy']}` | duration `{row['duration_s']}s` | "
            f"[json]({row['report_json']}) | [md]({row['report_md']})"
        )
    lines.append("")
    lines.append("## Scenario Matrix")
    lines.append("")
    header = "| Scenario | " + " | ".join(
        f"{r['policy']} Valid | {r['policy']} Qt | {r['policy']} AppCmd | {r['policy']} C"
        for r in run_rows
    ) + " |"
    sep = "|---|" + "|".join("---:|---:|---:|---:" for _ in run_rows) + "|"
    lines.append(header)
    lines.append(sep)
    for sc in scenarios:
        cols: List[str] = []
        for r in run_rows:
            srow = _scenario_row(r, sc)
            cols.extend(
                [
                    "no" if srow.get("blocked_no_focus") else "yes",
                    "pass" if srow.get("media_probe", {}).get("passed") else "fail",
                    "pass" if srow.get("native_appcommand_probe", {}).get("passed") else "fail",
                    "pass" if srow.get("transition_probe", {}).get("passed") else "fail",
                ]
            )
        lines.append(f"| `{sc}` | " + " | ".join(cols) + " |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Valid = scenario setup preserved intended focus contract (not blocked as contaminated).")
    lines.append("- Qt = synthetic key route (`SendInput`).")
    lines.append("- AppCmd = injected native `WM_APPCOMMAND` route.")
    lines.append("- C = transition hotkey path.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compare media-key matrix runs across focus policies.")
    p.add_argument("--launch", choices=("mc", "run"), default="mc")
    p.add_argument("--profile-mode", choices=("isolated", "live", "mirrored"), default="mirrored")
    p.add_argument("--policies", default="strict,realistic")
    p.add_argument("--scenarios", default="focused_idle,focused_clicked")
    p.add_argument("--launch-timeout-s", type=float, default=40.0)
    p.add_argument("--output-dir", default=str(ROOT / "logs" / "media_matrix_compare"))
    return p


def main() -> int:
    args = build_parser().parse_args()
    policies = [x.strip() for x in args.policies.split(",") if x.strip()]
    scenarios = [x.strip() for x in args.scenarios.split(",") if x.strip()]
    if not policies:
        raise SystemExit("No policies supplied.")
    output_root = Path(args.output_dir).resolve() / time.strftime("%Y%m%d_%H%M%S")
    output_root.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    for policy in policies:
        rows.append(
            _run_policy(
                policy=policy,
                launch=args.launch,
                profile_mode=args.profile_mode,
                scenarios=",".join(scenarios),
                launch_timeout_s=float(args.launch_timeout_s),
                output_root=output_root,
            )
        )

    summary_path = output_root / "compare_summary.md"
    json_path = output_root / "compare_summary.json"
    _write_summary(summary_path, rows, scenarios)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("[COMPARE] Completed")
    print(f"[COMPARE] Summary MD:   {summary_path}")
    print(f"[COMPARE] Summary JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
