"""Compatibility wrapper around the canonical chunked pytest runner.

The maintained test authority lives in ``tests/run_chunked.py``.  This tool is
kept only as a short operator convenience so old habits do not fork a second
suite manifest.

Examples::

    python tools/run_tests.py --suite destination
    python tools/run_tests.py --suite all
    python tools/run_tests.py --test tests/test_qtquick_window.py

``destination`` is the maintained post-H authority.  ``all`` is the broad
whole-tree Phase-I reconciliation diagnostic.  Explicit tests use the same
chunked runner rather than a separate pytest wrapper.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "run_chunked.py"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run SRPSS tests through the canonical tests/run_chunked.py authority."
    )
    parser.add_argument(
        "--suite",
        choices=("destination", "all"),
        default="destination",
        help=(
            "destination = maintained post-H authority (default); "
            "all = broad whole-tree reconciliation diagnostic"
        ),
    )
    parser.add_argument(
        "--test",
        dest="test_spec",
        help="Optional pytest path/nodeid; overrides --suite.",
    )
    parser.add_argument("--chunks", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Do not ask the canonical runner to write logs/pytest_*.log files.",
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip the canonical collection preflight (normally keep it enabled).",
    )
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        help="Additional arguments forwarded to pytest after tests/run_chunked.py --extra.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the canonical runner command without executing it.",
    )
    return parser


def build_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--chunks",
        str(max(1, int(args.chunks))),
        "--timeout-seconds",
        str(float(args.timeout_seconds)),
    ]
    if not args.no_log:
        command.append("--log")
    if args.no_preflight:
        command.append("--no-preflight")

    if args.test_spec:
        command.append(str(args.test_spec))
    elif args.suite == "destination":
        command.extend(("--profile", "destination"))
    # ``all`` intentionally relies on run_chunked.py's no-target whole-tree mode.

    extra: Iterable[str] = args.pytest_args or ()
    extra = list(extra)
    if extra:
        command.append("--extra")
        command.extend(extra)
    return command


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    command = build_command(args)
    print("→ Canonical test runner:", " ".join(command))
    if args.dry_run:
        return 0
    completed = subprocess.run(command, cwd=str(ROOT))
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
