"""Compatibility entrypoint for the derived defaults JSON artifact.

Kept to preserve existing operator/test references.  All generation is owned
by ``tools/regenerate_defaults_artifacts.py``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.regenerate_defaults_artifacts import DEFAULTS_JSON_PATH  # noqa: E402


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate canonical defaults JSON safely")
    parser.add_argument("--output", default=str(DEFAULTS_JSON_PATH))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    forwarded = ["--json-only", "--defaults-json", str(Path(args.output))]
    if args.check:
        forwarded.append("--check")
    elif args.dry_run:
        forwarded.append("--dry-run")
    from tools.regenerate_defaults_artifacts import main as unified_main

    return unified_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
