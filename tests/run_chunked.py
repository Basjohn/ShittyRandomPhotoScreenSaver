"""Chunked pytest runner for bounded subprocess execution.

Two execution modes intentionally differ:

* Maintained profiles (currently ``h-destination``) are **target-isolated**.
  A single collection preflight validates the whole profile, then every selected
  profile target runs in its own fresh pytest process. ``--chunks`` only partitions those
  file processes into a small number of reporting/log groups. This prevents
  queued QQuick/QObject teardown from one target contaminating unrelated tests in
  another file.

* Whole-tree or explicit-target runs retain pytest-chunk's test-level chunking.
  They are broad reconciliation diagnostics during H/I, not the current H
  destination authority.

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
from typing import TextIO

TESTS_DIR = Path(__file__).resolve().parent
LOG_DIR = TESTS_DIR.parent / "logs"

H_DESTINATION_PROFILE = (
    "test_qtquick_h_cutover.py",
    "test_qtquick_ctrl_coordinator.py",
    "test_qtquick_display_image_route.py",
    "test_qtquick_display_presenter.py",
    "test_qtquick_display_unit.py",
    "test_qtquick_family_binder.py",
    "test_qtquick_family_binder_two_phase.py",
    "test_qtquick_family_size_policy.py",
    "test_qtquick_geometry_resolver.py",
    "test_qtquick_overlay_preferred_size.py",
    "test_qtquick_frame_pacer.py",
    "test_qtquick_runtime.py::test_runtime_is_a_narrow_qobject_owner_with_queued_window_retirement",
    "test_qtquick_runtime.py::test_threaded_runtime_teardown_recreates_generation_zero_to_one",
    "test_qtquick_runtime.py::test_threaded_runtime_input_exit_retires_complete_display_set",
    "test_qtquick_window.py",
    "test_qtquick_scene_controller.py",
    "test_qtquick_input_controller.py",
    "test_qtquick_auxiliary.py",
    "test_qtquick_context_menu.py",
    "test_qtquick_custom_layout_owner.py",
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
    "test_qtquick_visualizer_monitor_routing.py",
    "test_visualizer_failover_reclaim.py",
    "test_remote_visualizer_capability_admission.py",
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
    "test_qtquick_runtime_reality.py",
    "test_media_generation_recreation.py",
    "test_settings_eventfilter_teardown_guards.py",
    "test_terminal_runtime_destruction.py",
    "test_qtquick_retained_model_lifetime.py",
    "test_visualizer_runtime_controller.py",
    "test_s_hotkey_workflow.py",
    "test_bubble_btf_coalescing.py",
    "test_bubble_cadence.py",
    "test_bubble_viewport_config_route.py",
    "test_bubble_viewport_reflow.py",
    "test_qtquick_phase_c_registry_parity.py",
    "test_qtquick_transition_controller.py",
    "test_qtquick_transition_implementations.py",
    "test_qtquick_transition_parameter_defaults.py",
    "test_qtquick_transition_parameter_resolution.py",
    "test_qtquick_transition_request_resolution.py",
    "test_qtquick_transition_state.py",
    "test_qtquick_transition_state_fence.py",
    "test_qtquick_transition_uniform_wiring.py",
    # H3/H3b product actions + Clock variant geometry, startup reveal/lifecycle,
    # and the permanent always-on Qt/QML capture baseline. Each runs in its own
    # isolated pytest process (per-target isolation), so their PySide/QML engine
    # setup cannot cross-contaminate the rest of the profile.
    "test_qtquick_family_product_actions.py",
    "test_qtquick_clock_custom_variant_geometry.py",
    "test_qtquick_postcutover_wiring.py",
    "test_qtquick_startup_reveal.py",
    "test_lifecycle_display_ownership_logging.py",
    "test_qt_message_capture_contract.py",
    "test_qt_message_capture_qml_runtime.py",
    # Black-flash / native surface-continuity contract and the global
    # single-context-menu owner (Display-1 flash investigation).
    "test_qtquick_black_flash_contract.py",
    "test_qtquick_context_menu_single_owner.py",
    "test_quick_window_activation_experiment.py",
)

PROFILES = {
    "h-destination": H_DESTINATION_PROFILE,
}


def _run_subprocess(
    cmd: list[str],
    *,
    cwd: str,
    timeout_seconds: float | None,
    log_path: Path | None = None,
) -> tuple[int, bool]:
    try:
        if log_path is not None:
            with log_path.open("w", encoding="utf-8") as handle:
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


def _run_profile_file(
    cmd: list[str],
    *,
    cwd: str,
    timeout_seconds: float | None,
    log_handle: TextIO | None,
) -> tuple[int, bool]:
    """Run one profile target in a fresh pytest process."""

    if log_handle is not None:
        log_handle.write("\n" + "=" * 88 + "\n")
        log_handle.write(f"COMMAND: {' '.join(cmd)}\n")
        log_handle.write("=" * 88 + "\n")
        log_handle.flush()

    try:
        proc = subprocess.run(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT if log_handle is not None else None,
            cwd=cwd,
            timeout=timeout_seconds,
        )
        return proc.returncode, False
    except subprocess.TimeoutExpired:
        if log_handle is not None:
            log_handle.write(
                f"\nTIMEOUT after {timeout_seconds}s while running {' '.join(cmd)}\n"
            )
            log_handle.flush()
        return 124, True


def _profile_groups(targets: list[str], total: int) -> list[list[str]]:
    groups: list[list[str]] = [[] for _ in range(max(1, total))]
    for index, target in enumerate(targets):
        groups[index % len(groups)].append(target)
    return groups


def _run_profile(
    *,
    profile_name: str,
    targets: list[str],
    chunks: int,
    verbose: bool,
    extra: list[str],
    timeout_seconds: float | None,
    log: bool,
) -> int:
    """Run a maintained profile with one fresh pytest process per target."""

    groups = _profile_groups(targets, chunks)
    file_results: list[tuple[str, float, int]] = []
    any_fail = False

    for group_index, group in enumerate(groups, start=1):
        if not group:
            continue

        group_log = (
            LOG_DIR / f"pytest_{profile_name.replace('-', '_')}_group_{group_index}.log"
            if log
            else None
        )
        handle: TextIO | None = None
        if group_log is not None:
            handle = group_log.open("w", encoding="utf-8")
            handle.write(
                f"{profile_name} target-isolated group {group_index}/{len(groups)}\n"
            )
            handle.write(
                "Each target below executes in a fresh pytest subprocess. "
                "Failures cannot contaminate later files through queued Qt state.\n"
            )
            handle.flush()

        try:
            print(
                f"\n=== {profile_name}: group {group_index}/{len(groups)} "
                f"({len(group)} files; target-isolated) ===",
                flush=True,
            )
            if group_log is not None:
                print(f"  Log: {group_log}", flush=True)

            for target in group:
                cmd = [
                    sys.executable,
                    "-m",
                    "pytest",
                    target,
                    "--tb=short",
                    "-q",
                ]
                if verbose:
                    cmd.append("-v")
                cmd.extend(extra)

                label = Path(target).name
                print(f"  -> {label}", flush=True)
                t0 = time.time()
                rc, timed_out = _run_profile_file(
                    cmd,
                    cwd=str(TESTS_DIR.parent),
                    timeout_seconds=timeout_seconds,
                    log_handle=handle,
                )
                elapsed = time.time() - t0
                file_results.append((label, elapsed, rc))

                if rc == 0:
                    print(f"     PASS [{elapsed:.1f}s]", flush=True)
                else:
                    any_fail = True
                    status = "TIMEOUT (exit 124)" if timed_out else f"FAIL (exit {rc})"
                    print(f"     {status} [{elapsed:.1f}s]", flush=True)
        finally:
            if handle is not None:
                handle.close()

    print("\n" + "=" * 64)
    print(f"{profile_name.upper()} TARGET-ISOLATED SUMMARY")
    print("=" * 64)
    failures = [(name, elapsed, rc) for name, elapsed, rc in file_results if rc != 0]
    total_time = sum(elapsed for _, elapsed, _ in file_results)

    print(f"  Targets run: {len(file_results)}")
    print(f"  Targets passed: {len(file_results) - len(failures)}")
    print(f"  Targets failed: {len(failures)}")
    print(f"  Aggregate subprocess time: {total_time:.1f}s")

    if failures:
        print("  Failed targets:")
        for name, elapsed, rc in failures:
            status = "TIMEOUT" if rc == 124 else f"exit {rc}"
            print(f"    - {name}: {status} [{elapsed:.1f}s]")
    else:
        print("  Result: ALL PROFILE FILES PASSED")

    return 1 if any_fail else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pytest suite in bounded chunks")
    parser.add_argument(
        "--chunks",
        type=int,
        default=4,
        help=(
            "Number of reporting groups for maintained profiles, or pytest-chunk "
            "partitions for ordinary runs (default: 4)"
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Pass -v to pytest")
    parser.add_argument(
        "--log",
        action="store_true",
        help="Write collection/chunk or profile-group output under logs/",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=900.0,
        help=(
            "Maximum runtime for collection and for each subprocess; "
            "use 0 to disable (default: 900)"
        ),
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        help=(
            "Use a maintained phase-specific profile. Profile files run in "
            "fresh pytest subprocesses to isolate Qt lifecycle state."
        ),
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip the one-time collection preflight (normally keep it enabled)",
    )
    parser.add_argument(
        "--extra",
        nargs=argparse.REMAINDER,
        default=[],
        help="Extra args forwarded to pytest (after --extra)",
    )
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

    missing = [
        target
        for target in targets
        if not Path(target.split("::", 1)[0]).exists()
    ]
    if missing:
        print("Selected test targets are missing:", file=sys.stderr)
        for target in missing:
            print(f"  {target}", file=sys.stderr)
        return 2

    total = max(1, args.chunks)
    timeout_seconds = args.timeout_seconds if args.timeout_seconds > 0 else None
    LOG_DIR.mkdir(exist_ok=True)

    if not args.no_preflight:
        collect_cmd = [
            sys.executable,
            "-m",
            "pytest",
            *targets,
            "--collect-only",
            "--tb=short",
            "-q",
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
                print(
                    f"  Collection TIMED OUT after {elapsed:.1f}s (exit 124)",
                    flush=True,
                )
            else:
                print(f"  Collection FAILED (exit {rc}) [{elapsed:.1f}s]", flush=True)
            if collect_log is not None:
                print(f"    Log: {collect_log}", flush=True)
            print("  No tests were started because collection is not clean.", flush=True)
            return rc if rc != 0 else 1
        print(f"  Collection passed [{elapsed:.1f}s]", flush=True)

    if args.profile:
        return _run_profile(
            profile_name=args.profile,
            targets=targets,
            chunks=total,
            verbose=args.verbose,
            extra=args.extra,
            timeout_seconds=timeout_seconds,
            log=args.log,
        )

    # Ordinary whole-tree / explicit-target mode retains pytest-chunk's
    # test-level partitioning. This is intentionally separate from the
    # target-isolated maintained-profile path above.
    results: list[tuple[int, float, int]] = []
    any_fail = False

    for chunk in range(1, total + 1):
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            *targets,
            f"--chunk={chunk}",
            f"--total-chunks={total}",
            "--tb=short",
            "-q",
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
                print(
                    f"  Chunk {chunk} TIMED OUT after {elapsed:.1f}s (exit 124)",
                    flush=True,
                )
                print(
                    "  Re-run the focused target with --verbose to isolate the stall.",
                    flush=True,
                )
            else:
                print(
                    f"  Chunk {chunk} FAILED (exit {returncode}) [{elapsed:.1f}s]",
                    flush=True,
                )
            if log_path is not None:
                print(f"    Log: {log_path}", flush=True)
        else:
            print(f"  Chunk {chunk} passed [{elapsed:.1f}s]", flush=True)

    print("\n" + "=" * 50)
    print("CHUNKED TEST SUMMARY")
    print("=" * 50)
    total_time = sum(elapsed for _, elapsed, _ in results)
    for chunk, elapsed, rc in results:
        status = (
            "PASS"
            if rc == 0
            else ("TIMEOUT (exit 124)" if rc == 124 else f"FAIL (exit {rc})")
        )
        print(f"  Chunk {chunk}: {status}  [{elapsed:.1f}s]")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Result: {'ALL PASSED' if not any_fail else 'SOME CHUNKS FAILED'}")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
