"""Chunked pytest runner for bounded subprocess execution.

Two execution modes intentionally differ:

* The maintained ``destination`` profile is **target-isolated**.
  A single collection preflight validates the whole profile, then every selected
  profile target runs in its own fresh pytest process. ``--chunks`` only partitions those
  file processes into a small number of reporting/log groups. This prevents
  queued QQuick/QObject teardown from one target contaminating unrelated tests in
  another file.

* ``--isolated`` runs every selected test file in its own fresh pytest process,
  ``--jobs`` at a time, and runs each failed file again alone afterwards: a file
  that passes alone failed under the parallel load (reported as load-sensitive),
  one that fails again is a real failure. This is a **diagnostic** gate, not
  the normal whole-suite button. ``--changed`` selects the files a
  change can affect (``tools/impacted_tests.py``: every test importing a changed
  module through any chain of project imports, changed tests, and tests naming
  a changed non-Python file).

* On Windows, a timed-out isolated test is dumped with DbgHelp *before*
  termination; per-file text output is written continuously rather than held
  in memory. Dumps live beside the individual logs and can be opened in WinDbg.

* Ordinary whole-suite runs are the fast, complete gate: 32 duration-balanced
  batches (whole test files per batch), two subprocesses concurrently. Each
  batch gets a fresh process, progress log, timeout and optional Windows native
  minidump. GPU/Studio/QtQuick-heavy batches never overlap one another.
  Test targets are never silently skipped; only the explicitly selected profile
  is smaller than the whole suite. File isolation remains opt-in diagnostics.

Examples::

    python tests/run_chunked.py --isolated --jobs 2           # diagnostic whole suite, slow
    python tests/run_chunked.py --isolated --changed          # files the working-tree change can affect
    python tests/run_chunked.py --isolated --changed --base main~2
    python tests/run_chunked.py --profile destination --chunks 4 --log
    python tests/run_chunked.py --chunks 32 --jobs 2 --log
    python tests/run_chunked.py --chunks 8 tests/test_widgets_tab_current.py
"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

TESTS_DIR = Path(__file__).resolve().parent
LOG_DIR = TESTS_DIR.parent / "logs"

DESTINATION_PROFILE = (
    "test_qtquick_h_cutover.py",
    "test_layout_slots.py",
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
    "test_qtquick_visualizer_roundtrip_lifetime.py",
    "test_qtquick_custom_layout_overlay.py",
    "test_visualizer_geometry_profiles.py",
    "test_visualizer_custom_geometry_profiles.py",
    "test_visualizer_edit_native_input.py",
    "test_visualizer_edit_footprint.py",
    "test_visualizer_edit_content_envelope.py",
    "test_visualizer_edit_orbit_publication.py",
    "test_extruded_shadow_reach.py",
    "test_extruded_shadow_receiver_contract.py",  # E8: yaw-canonical receiver and shallow-floor projection
    "test_qtquick_edit_pointer_delivery.py",  # real QQuickWindow MouseArea click targeting
    "test_qtquick_child_mapped_geometry.py",  # thin targets + 4-corner QQuickItem mapped bounds
    "test_qtquick_child_mapped_source_contract.py",  # selected-only mapping, no new runtime owner
    "test_qtquick_child_edit_lifecycle.py",  # Edit OFF/unselected clears role delegates after rebind
    "test_qtquick_child_clip_scene.py",  # real Qt card/accessory clip ancestry through reflow and Edit
    "test_qtquick_child_edit_off_dependency_contract.py",  # edit-off observer/feedback ownership guards
    "test_qtquick_child_persist_floor_regression.py",  # real owner writer/reader + bounded child-floor fixed points
    "test_visualizer_replay_cleanup_contract.py",  # offline replay drains only its own QObject
    "test_qt_test_deferred_delete_ownership_contract.py",  # test-owned Qt deletion only
    "test_visualizer_replay.py",  # file-isolated replay floors and deterministic playback
    "test_godzip_foundry_script_runner.py",  # current in-editor command review, not old modal
    "test_qtquick_edit_pointer_source_contract.py",
    "test_qtquick_h9_uniform_resize.py",
    "test_qtquick_resize_normalization.py",
    "test_widget_auto_shrink.py",
    "test_qtquick_ordinary_widget_host.py",
    "test_qtquick_widget_glow.py",
    "test_widget_glow_settings.py",
    "test_shadow_direction.py",
    "test_qtquick_clock_presentation.py",
    "test_clock_applied_edit_transform_contract.py",  # applied Clock role paint, no edit-off observer
    "test_qtquick_weather_presentation.py",
    "test_qtquick_media_presentation.py",
    "test_qtquick_reddit_presentation.py",
    "test_reddit_spacing_contract.py",
    "test_qtquick_gmail_presentation.py",
    "test_qtquick_achievement_pulse_presentation.py",
    "test_qtquick_abandonment_issues_presentation.py",
    # Maintained retained-Quick contracts added/reconciled 2026-09-09..11.
    # Keep source-only guards in the destination profile as cheap early failures;
    # Qt-bearing files still execute in their own fresh subprocess on Windows.
    "test_about_art_theme.py",
    "test_theme_foundry_model.py",
    "test_steam_phase3_settings_descriptors.py",
    "test_defaults_schema_authority.py",
    "test_sphere_voxel_audio_contract.py",
    "test_sphere_voxel_geometry.py",
    "test_sphere_authoring_contract.py",
    "test_sphere_analysis_consumers.py",
    "test_sphere_render_authoring.py",
    "test_sphere_uniform_block.py",
    "test_3d_curated_preset_ownership.py",
    "test_visualizer_settings_body_transaction_contract.py",
    "test_visualizer_user_authored_preset_catalog.py",
    "test_visualizer_technical_profile_contract.py",
    "test_qtquick_visualizer_owner_contract.py",
    "test_qtquick_visualizer_reactivity_config_parity.py",
    "test_qtquick_visualizer_technical_sync_contract.py",
    "test_qtquick_visualizer_all_five_owner_chain.py",
    "test_qtquick_visualizer_admission.py",
    "test_qtquick_visualizer_monitor_routing.py",
    "test_visualizer_custom_route_contract.py",
    "test_visualizer_owner_retirement.py",
    "test_widget_monitor_bindings.py",
    "test_remote_visualizer_capability_admission.py",
    "test_qtquick_visualizer_double_click.py",
    "test_qtquick_visualizer_middle_click.py",
    "test_visualizer_runtime_preset_cycle.py",
    "test_settings_manager.py::TestSettingsManagerDefaults::test_visualizer_schema_migration_nests_flat_custom_cache",
    "test_settings_manager.py::TestSettingsManagerDefaults::test_runtime_preset_state_write_preserves_media_and_reloads_custom_cache",
    "test_qtquick_visualizer_logical_ownership.py",
    "test_qtquick_visualizer_owner_edge.py",
    "test_qtquick_visualizer_render_bridge.py",
    "test_qtquick_visualizer_item.py",
    "test_qtquick_visualizer_all_modes.py",
    "test_qtquick_visualizer_spectrum.py",
    "test_qtquick_visualizer_oscilloscope.py",
    "test_qtquick_visualizer_bubble.py",
    "test_qtquick_visualizer_devcurve.py",
    "test_qtquick_visualizer_geometry.py",
    "test_visualizer_presentation_orientation.py",
    "test_qtquick_visualizer_fade_authority.py",
    "test_qtquick_runtime_reality.py",
    "test_media_generation_recreation.py",
    "test_media_event_observation.py",
    "test_media_winrt_affinity_and_native_fault_contract.py",
    "test_media_runtime.py",
    # 2026-09-02 permanent retained-widget architecture regressions. These are
    # phase-neutral destination contracts, not one-off migration diagnostics.
    "test_media_external_volume_contract.py",
    "test_widget_stacking_display_plan.py",
    "test_quick_authored_layout_mode_contract.py",
    "test_widget_theme_mirror_pack.py",
    "test_widget_theme_link_and_asset_contract.py",
    "test_widget_theme_no_material_contract.py",
    "test_theme_completion_slice_contract.py",
    "test_theme_expansion_light_metal_contract.py",
    "test_settings_theme_lifetime_contract.py",
    "test_settings_theme_qobject_lifetime.py",
    "test_settings_dark_qss_retirement_contract.py",
    "test_reddit_exit_logic.py::TestContextMenuClickThroughSuppression::test_menu_action_arms_pointer_guard_and_reddit_open_is_refused",
    # Permanent Quick-runtime performance/freshness contracts. These are deliberately
    # phase-neutral: I/J must not regain green by weakening reaction cadence,
    # newest-state semantics, native-cursor ownership or viewport fidelity.
    "test_visualizer_compute_lanes.py",
    "test_visualizer_analysis_acceptance.py",
    "test_visualizer_playback_gating.py",
    "test_p2_analysis_freshness.py",
    "test_visualizer_viewport_scaling_contracts.py",
    "test_runtime_perf_policy_contracts.py",
    "test_tooling_ownership.py",
    "test_widgets_tab_current.py::TestWidgetsTab::test_widgets_tab_disables_media_size_controls_when_custom_is_active",
    "test_widgets_tab_current.py::test_clock_settings_save_preserves_runtime_display_mode_overrides",
    "test_settings_eventfilter_teardown_guards.py",
    "test_terminal_runtime_destruction.py",
    "test_qtquick_retained_model_lifetime.py",
    "test_visualizer_runtime_controller.py",
    "test_s_hotkey_workflow.py",
    "test_bubble_btf_coalescing.py",
    "test_bubble_cadence.py",
    "test_bubble_lifecycle_fades.py",
    "test_bubble_viewport_config_route.py",
    "test_bubble_viewport_reflow.py",
    "test_bubble_aspect_pixels.py",
    "test_visualizer_line_coverage.py",
    "test_visualizer_glow_footprint.py",
    "test_qtquick_phase_c_registry_parity.py",
    "test_qtquick_transition_controller.py",
    "test_qtquick_transition_implementations.py",
    "test_qtquick_crumble_transition.py",
    "test_qtquick_slide_motion.py",
    "test_qtquick_visualizer_mode_retirement.py",
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
    "test_qtquick_product_wiring_contract.py",
    "test_qtquick_startup_reveal.py",
    "test_lifecycle_display_ownership_logging.py",
    "test_qt_message_capture_contract.py",
    "test_qt_message_capture_qml_runtime.py",
    # Exactly one product context menu across all displays (real bug, independent
    # of the black-flash investigation).
    "test_qtquick_context_menu_single_owner.py",
)

PROFILES = {
    "destination": DESTINATION_PROFILE,
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


def _summary_line(output: str) -> str:
    """pytest's final count line (or the last line when a file crashed before it)."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        if any(word in line for word in ("passed", "failed", "error", "no tests ran", "skipped")):
            return line.strip("= ")
    return lines[-1] if lines else "(no output)"


def _write_windows_timeout_dump(process: subprocess.Popen, path: Path) -> str:
    """Best-effort native thread/stack minidump of a *still-running* pytest child.

    This deliberately does not touch Qt or the native engine. The parent invokes
    Windows DbgHelp on the child before termination; WinDbg can inspect the dump.
    A failed dump must never prevent terminating a timed-out test process.
    """
    if sys.platform != "win32":
        return "Native minidump unavailable on this platform"
    import ctypes
    import msvcrt
    from ctypes import wintypes

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    PROCESS_DUP_HANDLE = 0x0040
    # Thread info, unloaded modules, process/thread data: useful for Qt/C++
    # deadlocks without copying all GPU/system memory into a massive dump.
    MINIDUMP_FLAGS = 0x00001000 | 0x00000020 | 0x00000100
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    dbghelp.MiniDumpWriteDump.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                          wintypes.HANDLE, wintypes.DWORD,
                                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    dbghelp.MiniDumpWriteDump.restype = wintypes.BOOL
    handle = kernel.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_DUP_HANDLE,
                                False, process.pid)
    if not handle:
        return f"Native minidump OpenProcess failed: Win32 {ctypes.get_last_error()}"
    try:
        with path.open("wb") as output:
            ok = dbghelp.MiniDumpWriteDump(handle, process.pid,
                                            wintypes.HANDLE(msvcrt.get_osfhandle(output.fileno())),
                                            MINIDUMP_FLAGS, None, None, None)
            failure = ctypes.get_last_error() if not ok else 0
        if not ok:
            path.unlink(missing_ok=True)
            return f"Native minidump MiniDumpWriteDump failed: Win32 {failure}"
        return f"Native minidump saved: {path} ({path.stat().st_size} bytes)"
    except (OSError, ValueError) as exc:
        path.unlink(missing_ok=True)
        return f"Native minidump unavailable: {type(exc).__name__}: {exc}"
    finally:
        kernel.CloseHandle(handle)


def _run_isolated_file(target: Path, *, timeout_seconds: float | None, extra: list[str],
                       log_dir: Path) -> tuple[Path, int, float, str]:
    cmd = [sys.executable, "-u", "-m", "pytest", str(target), "--tb=short", "-q", "-p", "no:cacheprovider", *extra]
    log_path = log_dir / f"{target.stem}.log"
    dump_path = log_dir / f"{target.stem}.dmp"
    t0 = time.monotonic()
    rc = 124
    # Streaming to disk avoids losing traceback output when a Qt/native hang
    # prevents pytest from exiting, and bounds the parent's memory use.
    with log_path.open("wb") as log:
        process = subprocess.Popen(cmd, cwd=str(TESTS_DIR.parent), stdout=log, stderr=subprocess.STDOUT)
        try:
            rc = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Capture native C++/Qt thread stacks before killing the child.
            # Python's pytest faulthandler logs are already streamed to this file.
            try:
                diagnostic = _write_windows_timeout_dump(process, dump_path)
            except Exception as exc:
                diagnostic = f"Native minidump failed: {type(exc).__name__}: {exc}"
            log.write((f"\nTIMEOUT after {timeout_seconds}s (pid {process.pid})\n"
                       f"{diagnostic}\n").encode("utf-8", "replace"))
            log.flush()
            process.kill()
            process.wait()
    elapsed = time.monotonic() - t0
    output = log_path.read_text(encoding="utf-8", errors="replace")
    # 5 = no tests collected (a file whose tests are all deselected or skipped by marker).
    return target, (0 if rc == 5 else rc), elapsed, _summary_line(output)


_DURATIONS = LOG_DIR / "pytest_isolated_durations.json"
_BASELINE_DURATIONS = TESTS_DIR / "chunk_duration_baseline.json"


def _load_durations() -> dict[str, float]:
    """Use shareable 19-Nov baseline, overridden by newer local measurements.

    Separate worktrees often start without /logs: keeping a small source-owned
    timing snapshot avoids wildly unbalanced first batches in those worktrees.
    The running test suite never rewrites the tracked baseline.
    """
    combined: dict[str, float] = {}
    for path in (_BASELINE_DURATIONS, _DURATIONS):
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(values, dict):
                combined.update({name: float(duration) for name, duration in values.items()
                                 if isinstance(name, str) and isinstance(duration, (int, float))
                                 and 0 < duration < 1e6})
        except (OSError, ValueError, TypeError):
            pass
    return combined


def _run_isolated(targets: list[Path], *, jobs: int, timeout_seconds: float | None, extra: list[str]) -> int:
    """Every target in a fresh pytest process, ``jobs`` at a time; failures rerun alone."""

    log_dir = LOG_DIR / "pytest_isolated"
    log_dir.mkdir(parents=True, exist_ok=True)
    for stale in (*log_dir.glob("*.log"), *log_dir.glob("*.dmp")):
        stale.unlink()
    durations = _load_durations()
    print(f"=== Isolated: {len(targets)} files, {jobs} at a time; logs in {log_dir} ===", flush=True)
    t0 = time.time()
    failed: list[tuple[Path, str]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(_run_isolated_file, target, timeout_seconds=timeout_seconds, extra=extra,
                               log_dir=log_dir) for target in targets]
        for future in as_completed(futures):
            target, rc, elapsed, summary = future.result()
            done += 1
            durations[target.name] = round(elapsed, 2)
            if rc != 0:
                failed.append((target, summary))
                print(f"  [{done}/{len(targets)}] FAIL {target.name} [{elapsed:.1f}s] {summary}", flush=True)
    wall = time.time() - t0
    _DURATIONS.write_text(json.dumps(durations, indent=0, sort_keys=True), encoding="utf-8")

    real: list[tuple[Path, str]] = []
    load_sensitive: list[tuple[Path, str]] = []
    if failed:
        print(f"\n=== Rerunning {len(failed)} failed files alone ===", flush=True)
        for target, first in sorted(failed):
            # Keep the parallel-run failure: the rerun rewrites <stem>.log, and a load-sensitive file's only
            # evidence is the run that failed.
            first_log = log_dir / f"{target.stem}.log"
            if first_log.exists():
                first_log.replace(log_dir / f"{target.stem}.under_load.log")
            first_dump = log_dir / f"{target.stem}.dmp"
            if first_dump.exists():
                first_dump.replace(log_dir / f"{target.stem}.under_load.dmp")
            _target, rc, elapsed, summary = _run_isolated_file(target, timeout_seconds=timeout_seconds,
                                                               extra=extra, log_dir=log_dir)
            (load_sensitive if rc == 0 else real).append((target, first if rc == 0 else summary))
            print(f"  {'passes alone' if rc == 0 else 'FAILS again'}: {target.name} [{elapsed:.1f}s] {summary}",
                  flush=True)

    print("\n" + "=" * 64)
    print("ISOLATED SUMMARY")
    print("=" * 64)
    print(f"  Files: {len(targets)}   passed: {len(targets) - len(real) - len(load_sensitive)}   "
          f"load-sensitive: {len(load_sensitive)}   failed: {len(real)}   wall {wall:.0f}s")
    for target, summary in load_sensitive:
        print(f"    load-sensitive (passed alone): {target.name}: {summary}   "
              f"(failing log: {log_dir / (target.stem + '.under_load.log')})")
    for target, summary in real:
        print(f"    FAILED: {target.name}: {summary}   (log: {log_dir / (target.stem + '.log')})")
    print(f"  Result: {'ALL PASSED' if not real else 'FAILURES'}"
          f"{' (load-sensitive files listed above)' if load_sensitive else ''}")
    return 1 if real else 0



@dataclass(frozen=True)
class BalancedBatch:
    number: int
    files: tuple[Path, ...]
    estimated_seconds: float
    gpu_exclusive: bool


def _gpu_exclusive(path: Path) -> bool:
    """Conservative single-lane admission for actual Quick/GL/Studio workloads.

    A lightweight source-only file may also land here. A false positive slows
    only that batch; a false negative could make two real render tests compete.
    This is local to the runner: no feature flag enters production code.
    """
    name = path.stem.lower()
    return any(word in name for word in (
        "studio", "qtquick", "_gpu", "scene3d", "visualizer_card_clip",
        "visualizer_owner_render", "native_scene", "_render_node", "_shader_compile",
    ))


def _duration_estimate(path: Path, known: dict[str, float]) -> float:
    candidate = known.get(path.name)
    if isinstance(candidate, (float, int)) and 0 < float(candidate) < 1e6:
        return float(candidate)
    name = path.stem.lower()
    if "studio" in name:
        return 45.0
    if _gpu_exclusive(path):
        return 12.0
    return 4.0


def _make_balanced_batches(files: list[Path], count: int,
                           durations: dict[str, float]) -> list[BalancedBatch]:
    """Longest-processing-time-first across whole files, not mutable test nodes.

    The GPU/Qt-heavy lane and ordinary lane are each balanced independently.
    Ordinary batches can overlap GPU batches; two GPU batches never overlap.
    """
    count = max(1, min(int(count), len(files)))
    gpu = [f for f in files if _gpu_exclusive(f)]
    ordinary = [f for f in files if not _gpu_exclusive(f)]
    gpu_count = 0
    if gpu and ordinary and count >= 2:
        total_gpu = sum(_duration_estimate(f, durations) for f in gpu)
        total = total_gpu + sum(_duration_estimate(f, durations) for f in ordinary)
        gpu_count = max(1, min(count - 1, round(count * total_gpu / total)))
        gpu_count = min(gpu_count, len(gpu))
    elif gpu:
        gpu_count = count
    ordinary_count = count - gpu_count
    if ordinary and ordinary_count == 0:
        ordinary_count, gpu_count = 1, count - 1
    if gpu and gpu_count == 0:
        gpu_count, ordinary_count = 1, count - 1

    bins: list[tuple[bool, list[Path], float]] = []
    for exclusive, candidates, slots in ((True, gpu, gpu_count), (False, ordinary, ordinary_count)):
        if not candidates or slots <= 0:
            continue
        groups = [[] for _ in range(slots)]
        weights = [0.0] * slots
        for candidate in sorted(candidates, key=lambda f: (-_duration_estimate(f, durations), str(f))):
            index = min(range(slots), key=lambda i: (weights[i], len(groups[i]), i))
            groups[index].append(candidate)
            weights[index] += _duration_estimate(candidate, durations)
        bins.extend((exclusive, group, weight) for group, weight in zip(groups, weights) if group)
    # Schedule longest likely batches first, but allow the runner to interleave lanes.
    bins.sort(key=lambda item: (-item[2], not item[0]))
    return [BalancedBatch(i, tuple(group), round(weight, 2), exclusive)
            for i, (exclusive, group, weight) in enumerate(bins, 1)]


def _kill_test_tree(process: subprocess.Popen) -> None:
    """Kill *only* the timed-out child tree, not other agents or worktrees."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run_balanced_batch(batch: BalancedBatch, *, run_dir: Path,
                        timeout_seconds: float | None, extra: list[str],
                        verbose: bool) -> tuple[BalancedBatch, int, float, bool]:
    logfile = run_dir / f"batch_{batch.number:02d}.log"
    dumpfile = run_dir / f"batch_{batch.number:02d}.dmp"
    cmd = [sys.executable, "-u", "-m", "pytest", *(str(p) for p in batch.files),
           "--tb=short", "-q", "-vv", "-p", "no:cacheprovider",
           "-o", "faulthandler_timeout=60", *extra]
    # -vv gives the precise last test name on a stall. Logs are run-local and
    # continuously flushed, so no global 'pytest_chunk_N.log' overwrites.
    t0 = time.monotonic()
    timed_out = False
    with logfile.open("wb") as log:
        log.write((f"BATCH {batch.number}: {len(batch.files)} files; "
                   f"estimated {batch.estimated_seconds:.1f}s; GPU-exclusive={batch.gpu_exclusive}\n"
                   f"FILES: {', '.join(p.name for p in batch.files)}\n\n").encode("utf-8"))
        log.flush()
        process = subprocess.Popen(cmd, cwd=str(TESTS_DIR.parent), stdout=log,
                                   stderr=subprocess.STDOUT,
                                   **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                                      if sys.platform == "win32" else {"start_new_session": True}))
        try:
            rc = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = 124
            try:
                diagnosis = _write_windows_timeout_dump(process, dumpfile)
            except Exception as exc:
                diagnosis = f"Native minidump failed: {type(exc).__name__}: {exc}"
            log.write((f"\nTIMEOUT after {timeout_seconds}s; PID={process.pid}\n{diagnosis}\n").encode("utf-8", "replace"))
            log.flush()
            _kill_test_tree(process)
    return batch, rc, time.monotonic() - t0, timed_out


def _run_balanced(targets: list[str], *, chunks: int, jobs: int, extra: list[str],
                  timeout_seconds: float | None, verbose: bool) -> int:
    """Full-suite/file-target batches; resource-aware scheduling, no hidden skips."""
    root = TESTS_DIR.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tools.impacted_tests import all_test_files, runs_on_this_platform
    if len(targets) == 1 and Path(targets[0]).resolve() == TESTS_DIR.resolve():
        files = all_test_files()
    else:
        files = []
        for raw in targets:
            path = Path(raw.split("::", 1)[0]).resolve()
            if "::" in raw:
                raise ValueError("Balanced batches accept whole-file or folder targets; use --isolated for pytest nodeids")
            if path.is_dir():
                files.extend(f for f in path.rglob("test_*.py") if runs_on_this_platform(f))
            elif runs_on_this_platform(path):
                files.append(path)
    files = sorted(set(files))
    if not files:
        print("No test files selected", flush=True)
        return 0
    batches = _make_balanced_batches(files, chunks, _load_durations())
    run_dir = LOG_DIR / "pytest_chunked" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8])
    run_dir.mkdir(parents=True, exist_ok=False)
    plan = {"mode": "balanced", "jobs": jobs, "requested_batches": chunks,
            "selected_files": len(files), "batches": [
        {"number": b.number, "gpu_exclusive": b.gpu_exclusive,
         "estimated_seconds": b.estimated_seconds,
         "files": [str(f.relative_to(root)).replace("\\", "/") for f in b.files]}
        for b in batches]}
    (run_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"\n=== Balanced full suite: {len(files)} files, {len(batches)} batches, "
          f"{jobs} concurrent subprocesses (one GPU-heavy batch max) ===", flush=True)
    print(f"  Evidence: {run_dir}", flush=True)
    pending_gpu = deque(b for b in batches if b.gpu_exclusive)
    pending_other = deque(b for b in batches if not b.gpu_exclusive)
    inflight = {}
    running_gpu = False
    results = []
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        while pending_gpu or pending_other or inflight:
            while len(inflight) < jobs:
                batch = None
                if pending_gpu and not running_gpu:
                    batch = pending_gpu.popleft()
                elif pending_other:
                    batch = pending_other.popleft()
                if batch is None:
                    break
                if batch.gpu_exclusive:
                    running_gpu = True
                print(f"  START batch {batch.number:02d}/{len(batches)} "
                      f"({len(batch.files)} files; estimate {batch.estimated_seconds:.0f}s; "
                      f"{'GPU-exclusive' if batch.gpu_exclusive else 'ordinary'})", flush=True)
                future = pool.submit(_run_balanced_batch, batch, run_dir=run_dir,
                                     timeout_seconds=timeout_seconds, extra=extra, verbose=verbose)
                inflight[future] = batch
            if not inflight:
                break
            completed, _ = wait(inflight, return_when=FIRST_COMPLETED)
            for future in completed:
                batch = inflight.pop(future)
                if batch.gpu_exclusive:
                    running_gpu = False
                try:
                    _, rc, elapsed, timed_out = future.result()
                except Exception as exc:
                    rc, elapsed, timed_out = 1, 0.0, False
                    with (run_dir / f"batch_{batch.number:02d}.log").open("ab") as log:
                        log.write(f"\nRUNNER ERROR: {type(exc).__name__}: {exc}\n".encode())
                results.append((batch, rc, round(elapsed, 2), timed_out))
                status = 'PASS' if rc == 0 else ('TIMEOUT' if timed_out else f'FAIL exit {rc}')
                print(f"  END   batch {batch.number:02d}/{len(batches)}: {status} "
                      f"[{elapsed:.1f}s] (batch_{batch.number:02d}.log)", flush=True)
    summary = {"wall_seconds": round(time.monotonic() - t0, 2),
               "results": [{"batch": b.number, "exit_code": rc, "elapsed": elapsed,
                            "timeout": timed_out, "log": f"batch_{b.number:02d}.log"}
                           for b, rc, elapsed, timed_out in sorted(results, key=lambda item: item[0].number)]}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    failed = [item for item in results if item[1] != 0]
    print(f"\nBALANCED CHUNK SUMMARY: {len(results)} batches; "
          f"{len(results) - len(failed)} passed, {len(failed)} failed/timeouts; "
          f"wall {summary['wall_seconds']:.1f}s", flush=True)
    for batch, rc, elapsed, timed_out in sorted(failed, key=lambda item: item[0].number):
        print(f"    batch {batch.number:02d}: {'TIMEOUT' if timed_out else f'exit {rc}'} "
              f"[{elapsed:.1f}s] ({run_dir / f'batch_{batch.number:02d}.log'})", flush=True)
    print(f"  Complete evidence: {run_dir}", flush=True)
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pytest suite in bounded chunks")
    parser.add_argument(
        "--chunks",
        type=int,
        default=None,
        help=(
            "Number of file-balanced batches (normal default: 32), or "
            "reporting groups for --profile destination (default: 4)"
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Pass -v to pytest")
    parser.add_argument(
        "--log",
        action="store_true",
        help="Write collection/profile logs (balanced batches always keep run-scoped evidence)",
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
        "--isolated",
        action="store_true",
        help="Run every selected test file in its own pytest process, --jobs at a time, rerunning failures alone",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=2,
        help="Maximum concurrent test subprocesses (default: 2); GPU-heavy batches never overlap",
    )
    parser.add_argument(
        "--changed",
        action="store_true",
        help="With --isolated: only the test files the change against --base can affect",
    )
    parser.add_argument("--base", default="HEAD", help="Revision --changed diffs against (default: HEAD)")
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
    if args.changed and not args.isolated:
        parser.error("--changed needs --isolated")

    if args.isolated:
        sys.path.insert(0, str(TESTS_DIR.parent))
        from tools.impacted_tests import all_test_files, changed_files, impacted_tests

        if args.changed:
            selected = impacted_tests(changed_files(args.base))
            for target, reason in selected.items():
                print(f"  {target.name}: {reason}")
            files = list(selected)
        elif args.targets:
            files = [Path(target).resolve() for target in args.targets]
        else:
            files = all_test_files()
        if not files:
            print("No test files selected.")
            return 0
        timeout_seconds = args.timeout_seconds if args.timeout_seconds > 0 else None
        # Longest files first keeps the parallel tail short (unknown ones first of all).
        durations = _load_durations()
        files.sort(key=lambda f: -durations.get(f.name, 1e9))
        return _run_isolated(files, jobs=max(1, args.jobs), timeout_seconds=timeout_seconds, extra=args.extra)

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

    total = max(1, args.chunks if args.chunks is not None else (4 if args.profile else 32))
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

    # Ordinary whole-tree / explicit-target mode uses historical file timings
    # and bounded parallelism rather than four enormous sequential pytest chunks.
    return _run_balanced(targets, chunks=total, jobs=max(1, args.jobs),
                         extra=args.extra, timeout_seconds=timeout_seconds,
                         verbose=args.verbose)



if __name__ == "__main__":
    sys.exit(main())
