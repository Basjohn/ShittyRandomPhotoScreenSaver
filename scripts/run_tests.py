"""Utility script to run pytest with logging-first policy.

Provides a consistent CLI for the project's preferred PowerShell workflow by
collecting pytest output into timestamped log files and optionally targeting
common test suites.
"""
from __future__ import annotations

import argparse
import locale
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

DEFAULT_LOG_ROOT = Path("logs") / "tests"
MAX_LOG_FILES = 10
_CACHE_PURGE_EXCLUDES = {".git", ".venv", "venv", "env", "node_modules", ".mypy_cache", ".ruff_cache"}


def _purge_pycache(root: Path) -> None:
    """Remove __pycache__ directories under the project tree."""

    if not root.exists() or not root.is_dir():
        return

    for cache_dir in root.rglob("__pycache__"):
        try:
            if not cache_dir.is_dir():
                continue
            if any(part in _CACHE_PURGE_EXCLUDES for part in cache_dir.parts):
                continue
            shutil.rmtree(cache_dir, ignore_errors=True)
        except Exception:
            # Best-effort cleanup; ignore failures so tests can proceed.
            pass


# Canonical suite definitions. Keys are CLI values accepted by --suite.
# Values are the pytest arguments appended after base flags.
SUITES: dict[str, list[str]] = {
    "all": ["tests"],
    "core": [
        "tests/test_events.py",
        "tests/test_resources.py",
        "tests/test_settings.py",
        "tests/test_threading.py",
    ],
    "transitions": [
        "tests/test_transitions.py",
        "tests/test_transition_integration.py",
        "tests/test_gl_prewarm.py",
    ],
    "flicker": [
        "tests/test_flicker_fix_integration.py",
        "tests/test_gl_prewarm.py",
        "tests/test_transition_telemetry.py",
    ],
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the ShittyRandomPhotoScreenSaver test suites with project-"
            "specific logging behaviour."
        )
    )
    parser.add_argument(
        "--suite",
        choices=sorted(SUITES.keys()),
        default="all",
        help=(
            "Named test suite to run. Defaults to 'all'. Use 'core' for fast "
            "CI checks, 'transitions' for GL overlay coverage, and 'flicker' "
            "for readiness diagnostics."
        ),
    )
    parser.add_argument(
        "--test",
        dest="test_spec",
        help=(
            "Optional pytest nodeid to run a single test or test class. "
            "Overrides --suite if supplied (e.g. "
            "'tests/test_events.py::test_subscribe_and_publish')."
        ),
    )
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        help="Additional arguments to forward to pytest after the suite args.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_ROOT,
        help="Directory where timestamped logs should be written.",
    )
    parser.add_argument(
        "--max-logs",
        type=int,
        default=MAX_LOG_FILES,
        help="Maximum number of log files to retain (default: 10).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the pytest command without executing it.",
    )
    return parser


def _resolve_pytest_args(args: argparse.Namespace) -> List[str]:
    if args.test_spec:
        suite_args = [args.test_spec]
    else:
        suite_args = SUITES.get(args.suite, ["tests"])

    extra: Iterable[str] = args.pytest_args or []
    return ["-vv", "--maxfail=5", *suite_args, *extra]


def _ensure_log_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = root / f"pytest_{timestamp}.log"
    return log_file


def _rotate_logs(root: Path, keep: int) -> None:
    if keep <= 0:
        return
    log_files = sorted(
        (p for p in root.glob("pytest_*.log") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for stale in log_files[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    pytest_args = _resolve_pytest_args(args)
    log_file = _ensure_log_dir(args.log_dir)

    command = [sys.executable, "-m", "pytest", *pytest_args]

    print("→ Running:", " ".join(command))
    print(f"→ Logging to: {log_file}")

    project_root = Path.cwd()

    if args.dry_run:
        _purge_pycache(project_root)
        return 0

    _purge_pycache(project_root)

    with log_file.open("w", encoding="utf-8") as fh:
        process = subprocess.run(command, stdout=fh, stderr=subprocess.STDOUT)

    _purge_pycache(project_root)

    _rotate_logs(args.log_dir, args.max_logs)

    tail_hint = "powershell" if "powershell" in os.environ.get("SHELL", "").lower() else ""  # noqa: SIM108
    print("→ pytest exit code:", process.returncode)
    print("→ Last log lines:")
    try:
        try:
            tail_contents = log_file.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            fallback_encoding = locale.getpreferredencoding(False) or "utf-8"
            tail_contents = log_file.read_text(
                encoding=fallback_encoding,
                errors="replace",
            ).splitlines()
        for line in tail_contents[-20:]:
            print(line)
    except OSError:
        print("  <unable to read log>")

    if tail_hint:
        print(f"→ Tip: Get-Content '{log_file}' -Tail 100")
    else:
        print(f"→ View full log: {log_file}")

    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
