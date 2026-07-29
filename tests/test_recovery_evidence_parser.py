from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from tools.recovery_evidence_parser import (
    analyze_archive,
    analyze_evidence_source,
    write_analysis,
)


def _write_archive(path: Path) -> None:
    usage = "\n".join(
        [
            "2026-07-23 19:37:45 - usage - INFO - [USAGE] sample "
            "seq=1 cpu_app_pct=10.0 cpu_main_pct=8.0 cpu_system_pct=5.0 "
            "rss_app_mb=500.0 rss_main_mb=420.0 rss_children_mb=80.0 "
            "image_worker_pid=123 image_worker_rss_mb=80.0 image_worker_vms_mb=160.0 "
            "shm_segments_created=4 shm_segments_live=0 shm_live_bytes=0 "
            "shm_segments_consumed=3 shm_segments_reclaimed_late=1 shm_unlink_failures=0 "
            "private_app_mb=700.0 vram_dedicated_mb=250.0 "
            "gpu_busy_pct=5.0 tracked_resources=5 tracked_known_bytes=1248 "
            "cpu_cache_resources=1 cpu_cache_bytes=800 cpu_display_resources=1 cpu_display_bytes=64 rm_resources=3 rm_known_bytes=384 "
            "rm_unknown_resources=1 gl_resources=3 gl_known_bytes=384 gl_unknown_resources=1 "
            "gl_texture_resources=1 gl_texture_bytes=128 gl_framebuffer_resources=0 "
            "gl_framebuffer_bytes=0 gl_renderbuffer_resources=0 gl_renderbuffer_bytes=0 "
            "gl_pbo_resources=1 gl_pbo_bytes=256 qt_default_fbo=qt_owned_untracked "
            "tm_compute_submitted=100 tm_io_submitted=10 "
            'tm_categories={"diagnostics.usage":{"submitted":1},'
            '"uncategorized":{"submitted":19},'
            '"visualizer.audio_analysis":{"submitted":90}}',
            "2026-07-23 19:38:00 - usage - INFO - [USAGE] sample "
            "seq=2 cpu_app_pct=20.0 cpu_main_pct=15.0 cpu_system_pct=7.0 "
            "rss_app_mb=550.0 rss_main_mb=465.0 rss_children_mb=85.0 "
            "image_worker_pid=123 image_worker_rss_mb=85.0 image_worker_vms_mb=165.0 "
            "shm_segments_created=5 shm_segments_live=0 shm_live_bytes=0 "
            "shm_segments_consumed=4 shm_segments_reclaimed_late=1 shm_unlink_failures=0 "
            "private_app_mb=760.0 vram_dedicated_mb=275.0 "
            "gpu_busy_pct=8.0 tracked_resources=5 tracked_known_bytes=1248 "
            "cpu_cache_resources=1 cpu_cache_bytes=800 cpu_display_resources=1 cpu_display_bytes=64 rm_resources=3 rm_known_bytes=384 "
            "rm_unknown_resources=1 gl_resources=3 gl_known_bytes=384 gl_unknown_resources=1 "
            "gl_texture_resources=1 gl_texture_bytes=128 gl_framebuffer_resources=0 "
            "gl_framebuffer_bytes=0 gl_renderbuffer_resources=0 gl_renderbuffer_bytes=0 "
            "gl_pbo_resources=1 gl_pbo_bytes=256 qt_default_fbo=qt_owned_untracked "
            "tm_compute_submitted=1600 tm_io_submitted=25 "
            'tm_categories={"diagnostics.usage":{"submitted":2},'
            '"uncategorized":{"submitted":43},'
            '"visualizer.audio_analysis":{"submitted":1580}}',
        ]
    )
    perf = "\n".join(
        [
            "2026-07-23 19:38:01 - metrics - INFO - "
            "[PERF] [GL PAINT] Slide metrics: screen=0, frames=100, "
            "avg_fps=60.0, dt_min=2.0ms, dt_max=45.0ms, target_fps=60, "
            "window_frames=100, render_requests=102, skipped_requests=2, "
            "request_acceptance_pct=98.08, last_presented_frame=100, scene_generation=4, "
            "dt_p50_ms=16.6, dt_p90_ms=17.0, dt_p95_ms=18.0, dt_p99_ms=24.0, "
            "dt_max_ms=45.0, dt_over_25_ms=2, dt_over_33_ms=1, dt_over_50_ms=0, "
            "dt_over_100_ms=0, paint_p50_ms=1.0, paint_p90_ms=2.0, paint_p95_ms=2.5, "
            "paint_p99_ms=4.0, paint_max_ms=6.0, request_age_p50_ms=2.0, "
            "request_age_p90_ms=3.0, request_age_p95_ms=4.0, request_age_p99_ms=7.0, "
            "request_age_max_ms=9.0, outcome=completed",
            "2026-07-23 19:38:02 - metrics - INFO - "
            "[PERF] [EVENT LOOP] summary samples=300 retained=300 interval_ms=50 "
            "late_p50_ms=0.5 late_p90_ms=2.0 late_p95_ms=3.0 late_p99_ms=8.0 "
            "late_max_ms=55.0 over_25_ms=2 over_50_ms=1 over_100_ms=0 outcome=sampled",
            "2026-07-23 19:38:03 - metrics - INFO - "
            "[PERF] [RESOURCE] snapshot event=settings stage=after_restart "
            "tracked_resources=5 tracked_known_bytes=1248 cpu_cache_resources=1 "
            "cpu_cache_bytes=800 cpu_display_resources=1 cpu_display_bytes=64 rm_resources=3 rm_known_bytes=384 rm_unknown_resources=1 "
            "gl_resources=3 gl_known_bytes=384 gl_unknown_resources=1 "
            "gl_texture_resources=1 gl_texture_bytes=128 gl_framebuffer_resources=0 "
            "gl_framebuffer_bytes=0 gl_renderbuffer_resources=0 gl_renderbuffer_bytes=0 "
            "gl_pbo_resources=1 gl_pbo_bytes=256 qt_default_fbo=qt_owned_untracked "
            'resources_json=[{"dimensions":[4,8],"format":"RGBA8","generation":9,'
            '"lease_count":null,"owner":"compositor:1","resource_id":"texture-1",'
            '"resource_kind":"texture","source":"resource_manager","tracked_bytes":128}]',
        ]
    )
    visualizer = (
        "2026-07-23 19:38:02 - visualizer - INFO - "
        "[PERF][SPOTIFY_VIS][MICROGAP] screen=0 mode=bubble "
        "context=steady_idle gap_samples=30 gap_p95_ms=33.0 "
        "gap_max_ms=80.0 wait_p95_ms=20.0 wait_max_ms=40.0"
    )
    lifecycle = (
        "2026-07-23 19:38:03 - runtime - WARNING - "
        "Settings cleanup started context_generation=2"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("screensaver_usage.log", usage)
        archive.writestr("screensaver_perf.log", perf)
        archive.writestr("screensaver_spotify_vis.log", visualizer)
        archive.writestr("screensaver_lifecycle.log", lifecycle)
        archive.writestr("screensaver_verbose.log", lifecycle)


def test_analyze_archive_derives_rates_and_deduplicates_warnings(tmp_path: Path) -> None:
    archive = tmp_path / "evidence.zip"
    _write_archive(archive)

    analysis = analyze_archive(archive)

    assert analysis.summary["visualizer_modes_observed"] == ["bubble"]
    assert analysis.task_rows[0]["compute_submitted_per_sec"] == 100.0
    assert analysis.task_rows[0]["io_submitted_per_sec"] == 1.0
    category_rates = json.loads(analysis.task_rows[0]["category_submitted_per_sec"])
    assert category_rates["visualizer.audio_analysis"] == pytest.approx(1490 / 15)
    assert analysis.task_rows[0]["category_coverage_pct"] == pytest.approx(1491 / 1515 * 100)
    assert analysis.frame_rows[0]["dt_p99_ms"] == 24.0
    assert analysis.frame_rows[0]["dt_max_ms"] == 45.0
    assert analysis.frame_rows[0]["request_age_p99_ms"] == 7.0
    assert analysis.memory_rows[0]["tracked_known_bytes"] == 1248
    assert analysis.memory_rows[0]["rss_children_mb"] == 80.0
    assert analysis.memory_rows[0]["image_worker_rss_mb"] == 80.0
    assert analysis.memory_rows[0]["shm_segments_created"] == 4
    assert analysis.memory_rows[0]["shm_segments_reclaimed_late"] == 1
    assert analysis.memory_rows[0]["display_image_tracked_bytes"] == 64
    assert analysis.memory_rows[0]["resource_gl_pbo_bytes"] == 256
    assert analysis.event_loop_rows[0]["late_p99_ms"] == 8.0
    assert analysis.resource_rows[0]["stage"] == "after_restart"
    assert analysis.resource_rows[0]["gl_texture_bytes"] == 128
    assert analysis.resource_rows[0]["cpu_display_bytes"] == 64
    assert analysis.resource_rows[0]["resource_detail_count"] == 1
    assert analysis.visualizer_rows[0]["p95_ms"] == 33.0
    assert len(analysis.errors_and_warnings) == 1


def test_write_analysis_emits_required_recovery_artifacts(tmp_path: Path) -> None:
    archive = tmp_path / "evidence.zip"
    output_dir = tmp_path / "derived"
    _write_archive(archive)

    write_analysis(analyze_archive(archive), output_dir)

    expected = {
        "summary.json",
        "frame_intervals.csv",
        "task_rates.csv",
        "memory_usage.csv",
        "gpu_usage.csv",
        "event_loop_stalls.csv",
        "resource_snapshots.csv",
        "lifecycle_events.csv",
        "visualizer_gaps.csv",
        "errors_and_warnings.txt",
        "unknown_lines.txt",
    }
    assert expected == {path.name for path in output_dir.iterdir()}
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["source_archive_sha256"]
    assert summary["counts"]["usage_samples"] == 2
    assert summary["counts"]["event_loop_windows"] == 1
    assert summary["counts"]["resource_snapshots"] == 1
    assert summary["resources"]["tracked_known_bytes"]["maximum"] == 1248.0
    assert summary["usage"]["image_worker_rss_mb"]["maximum"] == 85.0
    assert summary["usage"]["shm_live_bytes"]["maximum"] == 0.0


def test_analyze_plain_evidence_subfolder_without_archive(tmp_path: Path) -> None:
    archive = tmp_path / "legacy.zip"
    evidence_dir = tmp_path / "phase4plus_folder"
    _write_archive(archive)
    with zipfile.ZipFile(archive) as source:
        source.extractall(evidence_dir)

    analysis = analyze_evidence_source(evidence_dir)

    assert analysis.summary["source_kind"] == "folder"
    assert analysis.summary["source_path"] == str(evidence_dir.resolve())
    assert analysis.summary["source_sha256"]
    assert analysis.summary["counts"]["usage_samples"] == 2
