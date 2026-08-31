"""Compatibility entrypoint for canonical SST defaults regeneration.

The authoritative implementation is ``tools/regenerate_defaults_artifacts.py``.
This wrapper remains so existing tests/docs/operator habits do not fork a
second regeneration architecture.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.regenerate_defaults_artifacts import (  # noqa: E402
    DOCS_DIR,
    EXPORT_TARGETS,
    GENERATED_METADATA,
    _build_sst_payload,
    _validate_sst_payload,
    build_artifact_bytes,
)
from tools.defaults_foundry_core import atomic_write_many  # noqa: E402


def _build_payload(application: str) -> dict[str, Any]:
    return _build_sst_payload(application)


def _validate_payload(payload: Mapping[str, Any], application: str) -> None:
    _validate_sst_payload(payload, application)


def regenerate_sst_defaults(docs_dir: Path) -> tuple[Path, ...]:
    payloads = build_artifact_bytes(
        docs_dir=Path(docs_dir),
        include_json=False,
        include_sst=True,
    )
    result = atomic_write_many(payloads)
    # Historical API returns all target paths, not only files whose bytes changed.
    return tuple(Path(docs_dir) / filename for _app, filename in EXPORT_TARGETS)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate canonical SST snapshots safely")
    parser.add_argument("--docs-dir", default=str(DOCS_DIR))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    forwarded: list[str] = ["--sst-only", "--docs-dir", str(args.docs_dir)]
    if args.check:
        forwarded.append("--check")
    elif args.dry_run:
        forwarded.append("--dry-run")
    from tools.regenerate_defaults_artifacts import main as unified_main

    return unified_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
