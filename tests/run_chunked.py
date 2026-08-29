"""Chunked pytest runner for bounded, isolated subprocesses.

The runner performs a single collection preflight before starting chunks.  This
prevents one stale import/collection error from being reported four times as
four independent chunk failures.

During the pre-cutover H checkpoint, ``--profile h-destination`` is the focused
architecture gate for the retained Quick destination.  A whole-tree run remains
available for test-debt/reconciliation work, but it intentionally still contains
legacy physical-host tests until H/I retire those owners.

Examples::

    python tests/run_chunked.py --profile h-destination --chunks 4 --log
    python tests/run_chunked.py --chunks 4 --log
    python tests/run_chunked.py --chunks 4 tests/test_widgets_tab.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
LOG_DIR = TESTS_DIR.parent / "logs"

H_DESTINATION_PROFILE = (
    "test_qtquick_h_cutover.py",
    "test_qtquick_ctrl_coordinator.py",
    "test_qtquick_display_image_route.py",
    "test_qtquick_display_presenter.py",
    "test_qtquick_display_unit.py",
    "test_qtquick_family_binder.py",
    "test_qtquick_family_size_policy.py",
    "test_qtquick_geometry_resolver.py",
    "test_qtquick_overlay_preferred_size.py",
    "test_qtquick_runtime.py",
    "test_qtquick_window.py",
    "test_qtquick_scene_controller.py",
    "test_qtquick_input_controller.py",
    "test_qtquick_auxiliary.py",
    "test_qtquick_context_menu.py",
    "test_qtquick_custom_layout_overlay.py",
    "test_qtquick_ordinary_widget_host.py",
    "test_qtquick_clock_presentation.py",
    "test_qtquick_weather_presentation.py",
    "test_qtquick_media_presentation.py",
    "test_qtquick_reddit_presentation.py",
    "test_qtquick_gmail_presentation.py",
    "test_qtquick_achievement_pulse_presentation.py",
    "test_qtquick_abandonment_issues_presentation.py",
    "test_qtquick_visualizer_pre_cutover_audit.py",
    "test_qtquick_visualizer_true_f_gate.py",
    "test_qtquick_visualizer_all_five_owner_chain.py",
    "test_qtquick_visualizer_admission.py",
    "test_qtquick_visualizer_double_click.py",
    "test_qtquick_visualizer_logical_ownership.py",
    "test_qtquick_visualizer_owner_edge.py",
    "test_qtquick_visualizer_render_bridge.py",
    "test_qtquick_visualizer_item.py",
    "test_qtquick_visualizer_all_modes.py",
    "test_qtquick_visualizer_spectrum.py",
    "test_qtquick_visualizer_oscilloscope.py",
    "test_qtquick_visualizer_sine.py",
    "test_qtquick_visualizer_bubble.py",
    "test_qtquick_visualizer_devcurve.py",
    "test_qtquick_visualizer_geometry.py",
    "test_qtquick_visualizer_fade_authority.py",
    "test_visualizer_runtime_controller.py",
    "test_visualizer_replay.py",
    "test_bubble_btf_coalescing.py",
    "test_bubble_cadence.py",
    "test_bubble_viewport_config_route.py",
    "test_bubble_viewport_reflow.py",
    "test_qtquick_phase_c_registry_parity.py",
    "test_qtquick_transition_controller.py",
    "test_qtquick_transition_implementations.py",
    "test_qtquick_transition_parameter_defaults.py",
    "test_qtquick_transition_parameter_resolution.py",
    "test_qtquick_transition_state.py",
    "test_qtquick_transition_state_fence.py",
    "test_qtquick_transition_uniform_wiring.py",
)

PROFILES = {
    "h-destination": H_DESTINATION_PROFILE,
}


def _run_subprocess(cmd, *, cwd, timeout_seconds, log_path=None):
    try:
        if log_path is not None:
            with open(log_path, "w", encoding="utf-8") as handle:
                proc = subprocess.run(
                    cmd,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    cwd=cwd,
                    timeout=timeout_seconds,
                )
        else:
            proc = subprocess.run(cmd, cwd=cwd, timeout=timeout_seconds)
        return proc.returncode, False
    except subprocess.TimeoutExpired:
        return 124, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pytest suite in bounded chunks")
    parser.add_argument("--chunks", type=int, default=4,
                        help="Number of chunks to split the selected tests into (default: 4)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Pass -v to pytest")
    parser.add_argument("--log", action="store_true",
                        help="Write collection/chunk output under logs/")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=900.0,
        help="Maximum runtime for collection and each chunk; use 0 to disable (default: 900)",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        help="Use a maintained phase-specific test target profile",
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip the one-time collection preflight (normally keep it enabled)",
    )
    parser.add_argument("--extra", nargs=argparse.REMAINDER, default=[],
                        help="Extra args forwarded to pytest (after --extra)")
    parser.add_argument(
        "targets",
        nargs="*",
        help="Optional pytest paths/nodeids (default: complete tests directory)",
    )
    args = parser.parse_args()

    if args.profile and args.targets:
        parser.error("--profile cannot be combined with explicit pytest targets")

    if args.profile:
        targets = [str(TESTS_DIR / name) for name in PROFILES[args.profile]]
    else:
        targets = args.targets or [str(TESTS_DIR)]

    missing = [target for target in targets if not Path(target.split("::", 1)[0]).exists()]
    if missing:
        print("Selected test targets are missing:", file=sys.stderr)
        for target in missing:
            print(f"  {target}", file=sys.stderr)
        return 2

    total = max(1, args.chunks)
    timeout_seconds = args.timeout_seconds if args.timeout_seconds > 0 else None
    results = []
    any_fail = False
    LOG_DIR.mkdir(exist_ok=True)

    if not args.no_preflight:
        collect_cmd = [
            sys.executable, "-m", "pytest", *targets,
            "--collect-only", "--tb=short", "-q",
        ]
        collect_cmd.extend(args.extra)
        collect_log = LOG_DIR / "pytest_collection_preflight.log" if args.log else None
        print("=== Collection preflight ===", flush=True)
        print(f"  Command: {' '.join(collect_cmd)}", flush=True)
        t0 = time.time()
        rc, timed_out = _run_subprocess(
            collect_cmd,
            cwd=str(TESTS_DIR.parent),
            timeout_seconds=timeout_seconds,
            log_path=collect_log,
        )
        elapsed = time.time() - t0
        if rc != 0:
            if timed_out:
                print(f"  Collection TIMED OUT after {elapsed:.1f}s (exit 124)", flush=True)
            else:
                print(f"  Collection FAILED (exit {rc}) [{elapsed:.1f}s]", flush=True)
            if collect_log is not None:
                print(f"    Log: {collect_log}", flush=True)
            print("  No chunks were started because collection is not clean.", flush=True)
            return rc if rc != 0 else 1
        print(f"  Collection passed [{elapsed:.1f}s]", flush=True)

    for chunk in range(1, total + 1):
        cmd = [
            sys.executable, "-m", "pytest", *targets,
            f"--chunk={chunk}", f"--total-chunks={total}",
            "--tb=short", "-q",
        ]
        if args.verbose:
            cmd.append("-v")
        cmd.extend(args.extra)

        print(f"\n=== Chunk {chunk}/{total} ===", flush=True)
        print(f"  Command: {' '.join(cmd)}", flush=True)
        t0 = time.time()
        log_path = LOG_DIR / f"pytest_chunk_{chunk}.log" if args.log else None
        returncode, timed_out = _run_subprocess(
            cmd,
            cwd=str(TESTS_DIR.parent),
            timeout_seconds=timeout_seconds,
            log_path=log_path,
        )
        elapsed = time.time() - t0
        results.append((chunk, elapsed, returncode))
        if returncode != 0:
            any_fail = True
            if timed_out:
                print(f"  Chunk {chunk} TIMED OUT after {elapsed:.1f}s (exit 124)", flush=True)
                print("  Re-run the focused target with --verbose to isolate the stall.", flush=True)
            else:
                print(f"  Chunk {chunk} FAILED (exit {returncode}) [{elapsed:.1f}s]", flush=True)
            if log_path is not None:
                print(f"    Log: {log_path}", flush=True)
        else:
            print(f"  Chunk {chunk} passed [{elapsed:.1f}s]", flush=True)

    print("\n" + "=" * 50)
    print("CHUNKED TEST SUMMARY")
    print("=" * 50)
    total_time = sum(elapsed for _, elapsed, _ in results)
    for chunk, elapsed, rc in results:
        status = "PASS" if rc == 0 else ("TIMEOUT (exit 124)" if rc == 124 else f"FAIL (exit {rc})")
        print(f"  Chunk {chunk}: {status}  [{elapsed:.1f}s]")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Result: {'ALL PASSED' if not any_fail else 'SOME CHUNKS FAILED'}")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
