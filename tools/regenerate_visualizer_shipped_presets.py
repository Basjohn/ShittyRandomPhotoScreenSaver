"""Validate or regenerate repo-local shipped visualizer preset artifacts.

Source of truth is ``presets/visualizer_modes``.  Generated artifacts are the
the Media Center release mirror.  ``--check`` and
``--dry-run`` are deliberately read-only so operators/CI can prove parity
without mutating curated preset files or release artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.visualizer_preset_tree import (  # noqa: E402
    refresh_shipped_visualizer_presets,
    scan_curated_visualizer_preset_tree,
    snapshot_curated_visualizer_preset_tree,
)


def audit_repo_shipped_visualizer_preset_artifacts(
    repo_root: Path | None = None,
) -> tuple[str, ...]:
    """Return deterministic drift descriptions without writing anything."""

    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    source_root = root / "presets" / "visualizer_modes"
    release_root = root / "release" / "media_center" / "presets" / "visualizer_modes"

    if not source_root.exists() or not source_root.is_dir():
        return (f"missing authoritative source tree: {source_root}",)

    source_entries = scan_curated_visualizer_preset_tree(source_root)
    if not source_entries:
        return (f"no curated visualizer presets found under {source_root}",)

    try:
        snapshot_curated_visualizer_preset_tree(source_root)
    except Exception as exc:
        return (f"invalid authoritative source tree: {exc}",)
    drifts: list[str] = []

    release_entries = scan_curated_visualizer_preset_tree(release_root)
    missing = sorted(source_entries - release_entries)
    stale = sorted(release_entries - source_entries)
    if missing:
        drifts.append("release mirror missing: " + ", ".join(missing[:8]))
    if stale:
        drifts.append("release mirror stale: " + ", ".join(stale[:8]))

    for entry in sorted(source_entries & release_entries):
        source_path = source_root / entry
        release_path = release_root / entry
        try:
            if source_path.read_bytes() != release_path.read_bytes():
                drifts.append(f"release content drift: {entry}")
        except OSError as exc:
            drifts.append(f"release compare failed: {entry}: {exc}")

    return tuple(drifts)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate or regenerate shipped visualizer preset artifacts"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Read-only: return non-zero if source/release directory drift.",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Read-only: report drift but always return success.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check or args.dry_run:
        drifts = audit_repo_shipped_visualizer_preset_artifacts(REPO_ROOT)
        if not drifts:
            print("[VIS_PRESET_ARTIFACTS] GREEN writes=0")
            return 0
        for drift in drifts:
            print(f"[VIS_PRESET_ARTIFACTS] DRIFT {drift}")
        print(f"[VIS_PRESET_ARTIFACTS] drift_count={len(drifts)} writes=0")
        return 0 if args.dry_run else 1

    artifacts = refresh_shipped_visualizer_presets(REPO_ROOT)
    print(
        "Regenerated shipped visualizer preset artifacts: "
        f"{artifacts['entry_count']} curated files mirrored into "
        f"{artifacts['release_root']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
