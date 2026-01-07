"""Overlay log parser for quick overlay-related diagnostics.

Summarizes overlay-related warnings and diagnostics from a single log file.
Intended for ad-hoc use during Route 3 investigations.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize overlay-related warnings and diagnostics from a "
            "screensaver log file."
        )
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("logs") / "screensaver.log",
        help="Path to the log file to analyze (default: logs/screensaver.log)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=5,
        help="Maximum number of sample lines to show per category (default: 5)",
    )
    return parser


def _summarize_overlay_entries(
    log_path: Path, lines: List[str], max_samples: int
) -> None:
    categories: Dict[str, Dict[str, object]] = {
        "watchdog": {"label": "Watchdog events", "count": 0, "samples": []},
        "overlay_readiness": {
            "label": "Overlay readiness diagnostics",
            "count": 0,
            "samples": [],
        },
        "swap_downgrade": {
            "label": "Swap downgrade warnings",
            "count": 0,
            "samples": [],
        },
        "fallback_overlay": {
            "label": "Fallback overlay warnings",
            "count": 0,
            "samples": [],
        },
        "other_overlay": {
            "label": "Other overlay-related entries",
            "count": 0,
            "samples": [],
        },
    }

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        lower = line.lower()
        key: str | None = None

        if "[watchdog]" in line:
            key = "watchdog"
        elif "overlay readiness" in lower:
            key = "overlay_readiness"
        elif "swap downgrade" in lower:
            key = "swap_downgrade"
        elif "[fallback]" in lower and "overlay" in lower:
            key = "fallback_overlay"
        elif "overlay" in lower:
            key = "other_overlay"

        if key is None:
            continue

        cat = categories[key]
        cat["count"] = int(cat["count"]) + 1  # type: ignore[assignment]
        samples: List[str] = cat["samples"]  # type: ignore[assignment]
        if len(samples) < max_samples:
            samples.append(line)

    print(f"Overlay log summary for {log_path}")

    any_entries = any(int(cat["count"]) > 0 for cat in categories.values())
    if not any_entries:
        print("No overlay-related entries found.")
        return

    for key in ("watchdog", "overlay_readiness", "swap_downgrade", "fallback_overlay", "other_overlay"):
        cat = categories[key]
        count = int(cat["count"])
        label = str(cat["label"])
        print(f"\n{label}: {count}")
        samples = cat["samples"]  # type: ignore[assignment]
        for sample in samples:
            print("  ", sample)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    log_path: Path = args.log
    max_samples: int = max(1, int(args.max_samples))

    if not log_path.exists() or not log_path.is_file():
        print(f"Log file not found: {log_path}")
        return 1

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"Failed to read log file {log_path}: {exc}")
        return 1

    lines = text.splitlines()
    _summarize_overlay_entries(log_path, lines, max_samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
