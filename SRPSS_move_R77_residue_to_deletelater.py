"""Temporary SRPSS Phase-I/R-77 cleanup helper.

Run this file from the SRPSS repository root (or place it in the repo root and
double-click/run it there). It MOVES the exact audited obsolete files into:

    ./deletelater/<original path>

Nothing is permanently deleted. Directory structure is preserved so files can
be restored manually if required.

This script is intentionally temporary and should not become production code.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys


PATHS = [
    "rendering/gl_error_handler.py",
    "rendering/gl_profiler.py",
    "rendering/gl_programs/geometry_manager.py",
    "rendering/gl_programs/gl_state_tracker.py",
    "rendering/gl_programs/program_cache.py",
    "rendering/gl_programs/texture_manager.py",
    "rendering/gl_stage_timestamps.py",
    "rendering/gl_state_manager.py",
    "rendering/gl_timer_queries.py",
    "widgets/shadow_utils.py",
    "widgets/spotify_visualizer/card_surface.py",
    "widgets/spotify_visualizer/legacy_render_snapshot_adapter.py",
    "widgets/spotify_visualizer/logical_tick_state_adapter.py",
    "widgets/spotify_visualizer/mode_transition.py",
    "widgets/spotify_visualizer/overlay_diagnostics.py",
    "widgets/spotify_visualizer/overlay_frame_shell.py",
    "widgets/spotify_visualizer/overlay_mask.py",
    "widgets/spotify_visualizer/overlay_render_dispatch.py",
    "widgets/spotify_visualizer/overlay_state.py",
    "widgets/spotify_visualizer/overlay_uniforms.py",
    "widgets/spotify_visualizer/presentation_fade.py",
    "widgets/spotify_visualizer/presentation_state_adapter.py",
    "widgets/spotify_visualizer/runtime_adapter.py",
    "widgets/spotify_visualizer/spectrum_presentation_smoothing.py",
    "widgets/spotify_visualizer/thread_affinity.py",
]


def _resolve_repo_root() -> Path:
    """Prefer the script's directory; otherwise use the current working directory."""
    script_root = Path(__file__).resolve().parent
    if (script_root / "widgets").is_dir() and (script_root / "rendering").is_dir():
        return script_root

    cwd = Path.cwd().resolve()
    if (cwd / "widgets").is_dir() and (cwd / "rendering").is_dir():
        return cwd

    raise RuntimeError(
        "Could not identify the SRPSS repository root. "
        "Place this script in the repo root or run it with the repo root as CWD."
    )


def main() -> int:
    repo_root = _resolve_repo_root()
    quarantine_root = repo_root / "deletelater"

    moved = 0
    missing = 0
    already_moved = 0

    print(f"SRPSS root: {repo_root}")
    print(f"Quarantine: {quarantine_root}")
    print()

    for relative in PATHS:
        source = repo_root / relative
        destination = quarantine_root / relative

        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)

            if destination.exists():
                print(f"[STOP] Destination already exists: {destination}")
                print("       Refusing to overwrite anything in deletelater.")
                return 2

            shutil.move(str(source), str(destination))
            print(f"[MOVED] {relative}")
            moved += 1
            continue

        if destination.exists():
            print(f"[OK]    Already in deletelater: {relative}")
            already_moved += 1
        else:
            print(f"[MISS]  Not found: {relative}")
            missing += 1

    print()
    print(
        f"Done. moved={moved} already_moved={already_moved} missing={missing} "
        f"total={len(PATHS)}"
    )
    print("Nothing was permanently deleted.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
