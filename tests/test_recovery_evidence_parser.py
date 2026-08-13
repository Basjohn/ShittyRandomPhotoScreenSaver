from __future__ import annotations

import hashlib
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
            "private_app_mb=700.0 private_main_mb=620.0 private_children_mb=80.0 "
            "uss_app_mb=480.0 uss_main_mb=420.0 uss_children_mb=60.0 "
            "vram_dedicated_mb=250.0 "
            "gpu_busy_pct=5.0 tracked_resources=5 tracked_known_bytes=1248 "
            "cpu_cache_resources=1 cpu_cache_bytes=800 cpu_display_resources=1 cpu_display_bytes=64 rm_resources=3 rm_known_bytes=384 "
            "rm_unknown_resources=1 gl_resources=3 gl_known_bytes=384 gl_unknown_resources=1 "
            "gl_texture_resources=1 gl_texture_bytes=128 gl_framebuffer_resources=0 "
            "gl_framebuffer_bytes=0 gl_renderbuffer_resources=0 gl_renderbuffer_bytes=0 "
            "gl_pbo_resources=1 gl_pbo_bytes=256 qt_default_fbo=qt_owned_untracked "
            "tm_compute_submitted=100 tm_io_submitted=10 "
            'tm_categories={"diagnostics.usage":{"submitted":1},'
            '"uncategorized":{"submitted":19},'
            '"visualizer.audio_analysis":{"submitted":90}} '
            'tm_delivery={"pools":{"compute":{"callbacks_delivered":90}}}',
            "2026-07-23 19:38:00 - usage - INFO - [USAGE] sample "
            "seq=2 cpu_app_pct=20.0 cpu_main_pct=15.0 cpu_system_pct=7.0 "
            "rss_app_mb=550.0 rss_main_mb=465.0 rss_children_mb=85.0 "
            "image_worker_pid=123 image_worker_rss_mb=85.0 image_worker_vms_mb=165.0 "
            "shm_segments_created=5 shm_segments_live=0 shm_live_bytes=0 "
            "shm_segments_consumed=4 shm_segments_reclaimed_late=1 shm_unlink_failures=0 "
            "private_app_mb=760.0 private_main_mb=675.0 private_children_mb=85.0 "
            "uss_app_mb=525.0 uss_main_mb=465.0 uss_children_mb=60.0 "
            "vram_dedicated_mb=275.0 "
            "gpu_busy_pct=8.0 tracked_resources=5 tracked_known_bytes=1248 "
            "cpu_cache_resources=1 cpu_cache_bytes=800 cpu_display_resources=1 cpu_display_bytes=64 rm_resources=3 rm_known_bytes=384 "
            "rm_unknown_resources=1 gl_resources=3 gl_known_bytes=384 gl_unknown_resources=1 "
            "gl_texture_resources=1 gl_texture_bytes=128 gl_framebuffer_resources=0 "
            "gl_framebuffer_bytes=0 gl_renderbuffer_resources=0 gl_renderbuffer_bytes=0 "
            "gl_pbo_resources=1 gl_pbo_bytes=256 qt_default_fbo=qt_owned_untracked "
            "tm_compute_submitted=1600 tm_io_submitted=25 "
            'tm_categories={"diagnostics.usage":{"submitted":2},'
            '"uncategorized":{"submitted":43},'
            '"visualizer.audio_analysis":{"submitted":1580}} '
            'tm_delivery={"pools":{"compute":{"callbacks_delivered":1580}}}',
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
            "2026-07-23 19:38:04 - metrics - WARNING - "
            "[PERF][FRAME_GAP_OWNER] severity=over_50 screen=0 gap_ms=52.00 "
            "paint_ms=4.00 request_age_ms=8.00 source_age_ms=12.00 "
            "simulation_age_ms=9.00 render_state_age_ms=7.00 target_hz=60 "
            "transition_active=1 transition=fade vis_mode=bubble",
            "2026-07-23 19:38:05 - metrics - INFO - "
            "[ADAPTIVE_TIMER] Metrics: frames=120, transitions=4, "
            "time_idle=10.0ms, time_paused=20.0ms, time_running=2000.0ms, "
            "idle_waits=2 paused_waits=1 total_runtime=2.1s",
            "2026-07-23 19:38:06 - metrics - INFO - "
            "[PERF] [SPOTIFY_VIS][BUBBLE_LANE] lane_registrations=1 "
            "executor_tasks=3 logical_steps=12 completed=12 published=11 "
            "rejected_busy=1 rejected_stopped=0 cancelled=0 handoff_ms_mean=1.000 "
            "handoff_ms_max=2.000 execution_ms_mean=3.000 execution_ms_max=4.000 "
            "callback_ms_mean=0.500 callback_ms_max=1.000",
            "2026-07-23 19:38:07 - metrics - INFO - "
            "[PERF] [SPOTIFY_VIS][AUDIO_LANE] lane_registrations=1 "
            "executor_tasks=2 logical_steps=10 completed=10 published=10 "
            "rejected_busy=0 rejected_stopped=0 cancelled=0 handoff_ms_mean=2.000 "
            "handoff_ms_max=3.000 execution_ms_mean=4.000 execution_ms_max=5.000 "
            "callback_ms_mean=1.000 callback_ms_max=2.000",
            "2026-07-23 19:38:08 - metrics - INFO - "
            "[PERF][MEDIA_PRESENTATION] event=unchanged_refresh_suppressed "
            "deferred_for_transition=False update_requested=False layout_mutations=0",
            "2026-07-23 19:38:08 - metrics - INFO - "
            "[PERF][SPOTIFY_VIS][OVERLAY] reason=set_state screen=1 mode=bubble "
            "elapsed_ms=10000.0 set_state=950 paint=910 update_requests=950 "
            "geometry_changes=0 refresh_hz=60.0 dpr=1.5 "
            "paint_cpu_samples=910 paint_cpu_p50_ms=0.2 paint_cpu_p95_ms=0.4 "
            "paint_cpu_max_ms=1.2 state_to_paint_samples=910 "
            "state_to_paint_p50_ms=1.0 state_to_paint_p95_ms=3.0 "
            "state_to_paint_max_ms=8.0 gpu_supported=True "
            "gpu_reason=supported gpu_pending=2 gpu_errors=0 "
            "visible=True enabled=True playing=True",
            "2026-07-23 19:38:08 - metrics - INFO - "
            "[PERF][SPOTIFY_VIS][OVERLAY_GPU] screen=1 mode=bubble "
            "elapsed_ms=10000.0 gpu_supported=True gpu_reason=supported "
            "gpu_submitted=908 gpu_collected=906 gpu_pending=2 "
            "gpu_dropped_pending=2 gpu_discarded=0 gpu_samples=906 "
            "gpu_errors=0 "
            "gpu_p50_ms=0.11 gpu_p95_ms=0.23 gpu_max_ms=0.71",
            "2026-07-23 19:38:08 - metrics - INFO - "
            "[PERF][GL COMPOSITOR][GPU] screen=0 transition=burn "
            "elapsed_ms=10000.0 gpu_supported=True gpu_reason=supported "
            "gpu_submitted=1200 gpu_collected=1199 gpu_pending=1 "
            "gpu_dropped_pending=0 gpu_discarded=0 gpu_errors=0 "
            "gpu_samples=1199 gpu_p50_ms=0.50 gpu_p95_ms=0.90 gpu_max_ms=1.50",
            "2026-07-23 19:38:09 - metrics - INFO - "
            "[PERF][MEDIA_PRESENTATION] event=published metadata_changed=True "
            "presentation_changed=True deferred_for_transition=False transition_active=False "
            "layout_mutations=1 update_requested=True layout_ms=2.00 emit_ms=1.00 "
            "subscriber_count=3 generation=4",
            "2026-07-23 19:38:10 - metrics - INFO - "
            "[PERF] [CACHE] ImageCacheRepresentations: raw_items=2 raw_mb=4.0 "
            "scaled_items=3 scaled_mb=6.0 raw_evictions=1 scaled_evictions=2 "
            "raw_evicted_mb=1.0 scaled_evicted_mb=2.0 replacements=1 "
            "idempotent_puts_avoided=2",
            "2026-07-23 19:38:11 - metrics - INFO - "
            "[PERF] [CACHE] ImageCacheFlow: raw_hits=8 raw_misses=2 scaled_hits=6 "
            "scaled_misses=3 worker_requests=4 worker_fallbacks=1 "
            "scaled_prefetch_requests=4 "
            "scaled_prefetch_completed=3 scaled_derivations=2 raw_released_after_scaled=1 "
            "scaled_reuses_without_put=5 prefetch_resume_scheduled=1 prefetch_resume_runs=1",
            "2026-07-23 19:38:14 - metrics - INFO - "
            "[PERF] [IMAGE_UI_DELAY] reason=transition_display_stagger display=1 "
            "callable=display_image_apply generation=4 delay_ms=200 "
            "queue_late_ms=3.50 guard_ms=0.25 callback_ms=24.75 "
            "total_age_ms=228.25 scheduled_mono_ms=1000.000 due_mono_ms=1200.000 "
            "start_mono_ms=1203.500 end_mono_ms=1228.250 outcome=completed",
            "2026-07-23 19:38:14 - metrics - INFO - "
            "[PERF] [IMAGE_UI_SEGMENT] reason=transition_display_stagger display=1 "
            "stage=set_processed_image duration_ms=23.50 size=3840x2160",
            "2026-07-23 19:38:14 - metrics - INFO - "
            "[PERF] [IMAGE_UI_SEGMENT] reason=display_setter_detail display=1 "
            "stage=generic_pair_warm duration_ms=18.25 transition=GLCompositorSlideTransition "
            "outcome=completed size=3840x2160 cold_compositor=false "
            "manager_before=true manager_after=true cache_size_before=1 cache_size_after=2 "
            "retained_key_before=111 old_key=111 new_key=222 old_cached_before=true "
            "new_cached_before=false old_texture_before=7 new_texture_before=0 "
            "cache_hits_delta=1 texture_allocations_delta=1 texture_uploads_delta=1",
            "2026-07-23 19:38:15 - metrics - INFO - "
            "[PERF] [GL RETENTION] owner=display:1 terminal=2 retain_active=new "
            "retained_texture=7 retained_cache_key=111 texture_count=1 "
            "texture_cache_hits=4 texture_allocations=2 texture_uploads=2 "
            "texture_deletions=2 pbo_count=1 pbo_creations=0 pbo_reuses=2 "
            "upload_total_ms=24.25 interval_scope=terminal_to_terminal "
            "interval_texture_uploads=2 interval_texture_allocations=2 "
            "interval_pbo_creations=0 interval_pbo_reuses=2 "
            "interval_upload_total_ms=24.25",
            "2026-07-23 19:38:15 - metrics - INFO - "
            "[PERF][GL TEXTURE][UPLOAD] owner=compositor:1 size=3840x2160 "
            "upload_bytes=33177600 path=pbo image_format=rgb32 bits_path=direct_const_view "
            "total_ms=18.250 image_prepare_ms=0.750 "
            "bits_copy_ms=4.000 texture_alloc_ms=0.100 pbo_stage_ms=10.000 "
            "texture_submit_ms=3.300 unattributed_ms=0.100",
        ]
    )
    visualizer = "\n".join(
        [
            "2026-07-23 19:38:02 - visualizer - INFO - "
            "[PERF][SPOTIFY_VIS][MICROGAP] screen=0 mode=bubble "
            "context=steady_idle gap_samples=30 gap_p95_ms=33.0 "
            "gap_max_ms=80.0 wait_p95_ms=20.0 wait_max_ms=40.0",
            "2026-07-23 19:38:03 - visualizer - WARNING - "
            "[PERF] [SPOTIFY_VIS] Tick dt spike_ms=72.0 mode=bubble "
            "transition_running=True transition_name=GLCompositorSlideTransition "
            "transition_elapsed=0.41 idle_age=<n/a>",
            "2026-07-23 19:38:04 - visualizer - WARNING - "
            "[PERF] [SPOTIFY_VIS] Tick dt spike_ms=55.0 mode=bubble "
            "transition_running=True transition_name=GLCompositorSlideTransition "
            "transition_elapsed=2.00 idle_age=<n/a>",
            "2026-07-23 19:38:05 - visualizer - WARNING - "
            "[PERF] [SPOTIFY_VIS] Tick dt spike_ms=80.0 mode=bubble "
            "transition_running=False transition_name=<none> "
            "transition_elapsed=<n/a> idle_age=0.08",
            "2026-07-23 19:38:05 - visualizer - WARNING - "
            "[SPOTIFY_VIS][LATENCY] lag_ms=84.0 mode=bubble trigger=transition_end",
        ]
    )
    lifecycle = "\n".join(
        [
            "2026-07-23 19:38:03 - runtime - WARNING - "
            "Settings cleanup started context_generation=2",
            "2026-07-23 19:38:12 - runtime - INFO - "
            "[LIFECYCLE_BARRIER] armed reason=settings retiring_generation=4 "
            "qobjects=3 python_owners=2 python_owner_classes={'WidgetManager': 1}",
            "2026-07-23 19:38:13 - runtime - INFO - "
            "[LIFECYCLE_BARRIER] complete reason=settings retiring_generation=4 elapsed_ms=15.5",
        ]
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
    assert analysis.memory_rows[0]["private_main_mb"] == 620.0
    assert analysis.memory_rows[0]["private_children_mb"] == 80.0
    assert analysis.memory_rows[0]["uss_app_mb"] == 480.0
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
    assert analysis.visualizer_rows[1]["boundary"] == "transition_start"
    assert analysis.visualizer_rows[1]["transition_elapsed"] == 0.41
    assert analysis.visualizer_rows[2]["boundary"] == "active_transition"
    assert analysis.visualizer_rows[3]["boundary"] == "transition_end"
    assert analysis.summary["visualizer"]["tick_spikes_by_boundary"] == {
        "active_transition": {
            "count": 1,
            "dt_ms": {"minimum": 55.0, "median": 55.0, "maximum": 55.0},
        },
        "transition_end": {
            "count": 1,
            "dt_ms": {"minimum": 80.0, "median": 80.0, "maximum": 80.0},
        },
        "transition_start": {
            "count": 1,
            "dt_ms": {"minimum": 72.0, "median": 72.0, "maximum": 72.0},
        },
    }
    assert analysis.summary["visualizer"]["latency_by_trigger"] == {
        "transition_end": {
            "count": 1,
            "lag_ms": {"minimum": 84.0, "median": 84.0, "maximum": 84.0},
        }
    }
    assert analysis.summary["phase5"]["frame_gap_owner"]["severity_counts"] == {"over_50": 1}
    assert analysis.summary["phase5"]["adaptive_timer"]["frames"]["maximum"] == 120.0
    assert analysis.summary["phase5"]["visualizer_lanes"]["bubble_lane"]["published"]["maximum"] == 11.0
    assert analysis.summary["phase5"]["media_presentation"] == {
        "applied": 1,
        "unchanged_refresh_suppressed": 1,
    }
    assert analysis.summary["phase5"]["visualizer_overlay"] == {
        "records": 1,
        "by_mode": {
            "bubble": {
                "records": 1,
                "set_state_per_sec": {
                    "minimum": 95.0,
                    "median": 95.0,
                    "maximum": 95.0,
                },
                "update_requests_per_sec": {
                    "minimum": 95.0,
                    "median": 95.0,
                    "maximum": 95.0,
                },
                "paint_per_sec": {
                    "minimum": 91.0,
                    "median": 91.0,
                    "maximum": 91.0,
                },
                "geometry_changes": {
                    "minimum": 0.0,
                    "median": 0.0,
                    "maximum": 0.0,
                },
                "refresh_hz": {
                    "minimum": 60.0,
                    "median": 60.0,
                    "maximum": 60.0,
                },
                "paint_cpu_p95_ms": {
                    "minimum": 0.4,
                    "median": 0.4,
                    "maximum": 0.4,
                },
                "state_to_paint_p95_ms": {
                    "minimum": 3.0,
                    "median": 3.0,
                    "maximum": 3.0,
                },
            }
        },
    }
    assert analysis.summary["phase5"]["visualizer_overlay_gpu"] == {
        "records": 1,
        "by_mode": {
            "bubble": {
                "records": 1,
                "supported_records": 1,
                "unsupported_records": 0,
                "submitted": {
                    "minimum": 908.0,
                    "median": 908.0,
                    "maximum": 908.0,
                },
                "collected": {
                    "minimum": 906.0,
                    "median": 906.0,
                    "maximum": 906.0,
                },
                "pending": {
                    "minimum": 2.0,
                    "median": 2.0,
                    "maximum": 2.0,
                },
                "dropped_pending": {
                    "minimum": 2.0,
                    "median": 2.0,
                    "maximum": 2.0,
                },
                "discarded": {
                    "minimum": 0.0,
                    "median": 0.0,
                    "maximum": 0.0,
                },
                "errors": {
                    "minimum": 0.0,
                    "median": 0.0,
                    "maximum": 0.0,
                },
                "samples": {
                    "minimum": 906.0,
                    "median": 906.0,
                    "maximum": 906.0,
                },
                "p50_ms": {
                    "minimum": 0.11,
                    "median": 0.11,
                    "maximum": 0.11,
                },
                "p95_ms": {
                    "minimum": 0.23,
                    "median": 0.23,
                    "maximum": 0.23,
                },
                "max_ms": {
                    "minimum": 0.71,
                    "median": 0.71,
                    "maximum": 0.71,
                },
            }
        },
    }
    compositor_gpu = analysis.summary["phase5"]["compositor_gpu"]
    assert compositor_gpu["records"] == 1
    assert compositor_gpu["by_transition"]["burn"]["supported_records"] == 1
    assert compositor_gpu["by_transition"]["burn"]["samples"]["median"] == 1199.0
    assert compositor_gpu["by_transition"]["burn"]["p95_ms"]["median"] == 0.9
    overlay = next(
        row for row in analysis.phase5_rows
        if row["kind"] == "visualizer_overlay"
    )
    assert overlay["screen"] == 1
    assert overlay["mode"] == "bubble"
    assert overlay["elapsed_ms"] == 10000.0
    assert overlay["set_state"] == 950
    assert overlay["paint"] == 910
    assert overlay["update_requests"] == 950
    assert overlay["geometry_changes"] == 0
    assert overlay["refresh_hz"] == 60.0
    assert overlay["paint_cpu_p95_ms"] == 0.4
    assert overlay["state_to_paint_p95_ms"] == 3.0
    overlay_gpu = next(
        row for row in analysis.phase5_rows
        if row["kind"] == "visualizer_overlay_gpu"
    )
    assert overlay_gpu["gpu_supported"] == "True"
    assert overlay_gpu["gpu_submitted"] == 908
    assert overlay_gpu["gpu_collected"] == 906
    assert overlay_gpu["gpu_dropped_pending"] == 2
    assert overlay_gpu["gpu_p95_ms"] == 0.23
    compositor_gpu_row = next(
        row for row in analysis.phase5_rows
        if row["kind"] == "compositor_gpu"
    )
    assert compositor_gpu_row["screen"] == 0
    assert compositor_gpu_row["transition"] == "burn"
    assert compositor_gpu_row["gpu_collected"] == 1199
    assert compositor_gpu_row["gpu_p95_ms"] == 0.9
    assert analysis.summary["phase5"]["cache"]["raw_hits"]["maximum"] == 8.0
    assert analysis.summary["phase5"]["cache"]["worker_requests"]["maximum"] == 4.0
    assert analysis.summary["phase5"]["cache"]["worker_fallbacks"]["maximum"] == 1.0
    assert analysis.summary["phase5"]["lifecycle_barrier"]["complete"] == 1
    assert analysis.summary["phase5"]["lifecycle_barrier"]["by_reason"] == {
        "settings": {
            "armed": 1,
            "complete": 1,
            "elapsed_ms": {
                "minimum": 15.5,
                "median": 15.5,
                "maximum": 15.5,
            },
        }
    }
    assert analysis.summary["resources"]["by_stage"]["after_restart"] == {
        "records": 1,
        "tracked_known_bytes": {
            "minimum": 1248.0,
            "median": 1248.0,
            "maximum": 1248.0,
        },
        "cpu_cache_bytes": {
            "minimum": 800.0,
            "median": 800.0,
            "maximum": 800.0,
        },
        "gl_known_bytes": {
            "minimum": 384.0,
            "median": 384.0,
            "maximum": 384.0,
        },
        "gl_resources": {
            "minimum": 3.0,
            "median": 3.0,
            "maximum": 3.0,
        },
        "gl_unknown_resources": {
            "minimum": 1.0,
            "median": 1.0,
            "maximum": 1.0,
        },
    }
    image_delay = next(row for row in analysis.phase5_rows if row["kind"] == "image_ui_delay")
    assert image_delay["reason"] == "transition_display_stagger"
    assert image_delay["display"] == "1"
    assert image_delay["callable"] == "display_image_apply"
    assert image_delay["generation"] == 4
    assert image_delay["queue_late_ms"] == 3.5
    assert image_delay["guard_ms"] == 0.25
    assert image_delay["callback_ms"] == 24.75
    assert image_delay["scheduled_mono_ms"] == 1000.0
    assert image_delay["due_mono_ms"] == 1200.0
    assert image_delay["start_mono_ms"] == 1203.5
    assert image_delay["end_mono_ms"] == 1228.25
    image_segment = next(
        row for row in analysis.phase5_rows
        if row["kind"] == "image_ui_segment" and row["stage"] == "set_processed_image"
    )
    assert image_segment["stage"] == "set_processed_image"
    assert image_segment["duration_ms"] == 23.5
    assert image_segment["size"] == "3840x2160"
    assert analysis.summary["phase5"]["image_ui"]["delay_records"] == 1
    detailed_segment = next(
        row for row in analysis.phase5_rows
        if row["kind"] == "image_ui_segment" and row["stage"] == "generic_pair_warm"
    )
    assert detailed_segment["old_key"] == 111
    assert detailed_segment["retained_key_before"] == 111
    assert detailed_segment["old_cached_before"] == "true"
    assert detailed_segment["texture_allocations_delta"] == 1
    assert detailed_segment["texture_uploads_delta"] == 1
    assert analysis.summary["phase5"]["image_ui"]["segment_records"] == 2
    assert analysis.summary["phase5"]["image_ui"]["guard_ms"]["maximum"] == 0.25
    assert analysis.summary["phase5"]["image_ui"]["callback_ms"]["maximum"] == 24.75
    assert analysis.summary["phase5"]["image_ui"]["segment_duration_ms"]["maximum"] == 23.5
    pair_warm = analysis.summary["phase5"]["image_ui"]["segments_by_stage"]["generic_pair_warm"]
    assert pair_warm["count"] == 1
    assert pair_warm["duration_ms"]["maximum"] == 18.25
    assert pair_warm["texture_uploads_delta"]["maximum"] == 1.0
    assert analysis.summary["phase5"]["image_ui"]["outcomes"] == {"completed": 1}
    texture_upload = analysis.summary["phase5"]["texture_upload"]
    assert texture_upload["records"] == 1
    assert texture_upload["image_formats"] == {"rgb32": 1}
    assert texture_upload["bits_paths"] == {"direct_const_view": 1}
    assert texture_upload["by_path"]["pbo"]["total_ms"] == {
        "minimum": 18.25,
        "median": 18.25,
        "maximum": 18.25,
    }
    assert texture_upload["by_path"]["pbo"]["pbo_stage_ms"]["maximum"] == 10.0
    upload_row = next(
        row for row in analysis.phase5_rows if row["kind"] == "texture_upload"
    )
    assert upload_row["owner"] == "compositor:1"
    assert upload_row["upload_bytes"] == 33177600
    assert upload_row["upload_image_format"] == "rgb32"
    assert upload_row["upload_bits_path"] == "direct_const_view"
    assert upload_row["texture_submit_ms"] == 3.3
    gl_retention = next(
        row for row in analysis.phase5_rows if row["kind"] == "gl_retention"
    )
    assert gl_retention["owner"] == "display:1"
    assert gl_retention["terminal"] == 2
    assert gl_retention["retain_active"] == "new"
    assert gl_retention["retained_texture"] == 7
    assert gl_retention["retained_cache_key"] == 111
    assert gl_retention["interval_scope"] == "terminal_to_terminal"
    assert gl_retention["interval_texture_uploads"] == 2
    retention_summary = analysis.summary["phase5"]["gl_retention"]
    assert retention_summary["records"] == 1
    assert retention_summary["retained_cache_keys"] == [111]
    assert retention_summary["interval_texture_uploads"]["maximum"] == 2.0
    assert retention_summary["interval_pbo_creations"]["maximum"] == 0.0
    assert len(analysis.errors_and_warnings) == 6


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
        "phase5_telemetry.csv",
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
    assert summary["usage"]["private_main_mb"]["maximum"] == 675.0
    assert summary["usage"]["private_children_mb"]["maximum"] == 85.0
    assert summary["usage"]["uss_app_mb"]["maximum"] == 525.0
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


def test_plain_evidence_parser_includes_rotated_sidecars_in_chronological_order(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "rotated_evidence"
    evidence_dir.mkdir()
    (evidence_dir / "screensaver_perf.log.1").write_text(
        "2026-08-08 21:50:00 - metrics - INFO - "
        "[PERF] [GL PAINT] Slide metrics: screen=0, frames=10, "
        "avg_fps=20.0, dt_max=80.0ms, target_fps=60, outcome=completed\n",
        encoding="utf-8",
    )
    (evidence_dir / "screensaver_perf.log").write_text(
        "2026-08-08 22:05:00 - metrics - INFO - "
        "[PERF] [GL PAINT] Slide metrics: screen=0, frames=60, "
        "avg_fps=60.0, dt_max=20.0ms, target_fps=60, outcome=completed\n",
        encoding="utf-8",
    )

    analysis = analyze_evidence_source(evidence_dir)

    assert [row["timestamp"] for row in analysis.frame_rows] == [
        "2026-08-08 21:50:00",
        "2026-08-08 22:05:00",
    ]
    assert analysis.summary["time_range"] == {
        "first": "2026-08-08 21:50:00",
        "last": "2026-08-08 22:05:00",
    }
    assert analysis.summary["source_files"] == {
        "screensaver_perf.log": (
            evidence_dir / "screensaver_perf.log"
        ).stat().st_size,
        "screensaver_perf.log.1": (
            evidence_dir / "screensaver_perf.log.1"
        ).stat().st_size,
    }


def test_live_logs_root_ignores_nested_archives_and_hashes_only_live_sidecars(
    tmp_path: Path,
) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    rotated = logs_dir / "screensaver_perf.log.1"
    active = logs_dir / "screensaver_perf.log"
    rotated.write_text(
        "2026-08-11 03:00:00 - metrics - INFO - "
        "[PERF] [GL PAINT] Slide metrics: screen=0, frames=10, "
        "avg_fps=20.0, dt_max=80.0ms, target_fps=60, outcome=completed\n",
        encoding="utf-8",
    )
    active.write_text(
        "2026-08-11 03:30:00 - metrics - INFO - "
        "[PERF] [GL PAINT] Slide metrics: screen=0, frames=60, "
        "avg_fps=60.0, dt_max=20.0ms, target_fps=60, outcome=completed\n",
        encoding="utf-8",
    )
    archived_dir = logs_dir / "evidence_chest" / "historical_run"
    archived_dir.mkdir(parents=True)
    archived = archived_dir / "screensaver_perf.log"
    archived.write_text(
        "2026-08-09 14:59:00 - historical - INFO - "
        "[PERF] [GL PAINT] Slide metrics: screen=0, frames=1, "
        "avg_fps=1.0, dt_max=1000.0ms, target_fps=60, outcome=completed\n",
        encoding="utf-8",
    )

    analysis = analyze_evidence_source(logs_dir)
    original_hash = analysis.summary["source_sha256"]

    assert [row["timestamp"] for row in analysis.frame_rows] == [
        "2026-08-11 03:00:00",
        "2026-08-11 03:30:00",
    ]
    assert analysis.summary["time_range"] == {
        "first": "2026-08-11 03:00:00",
        "last": "2026-08-11 03:30:00",
    }
    assert analysis.summary["source_files"] == {
        active.name: active.stat().st_size,
        rotated.name: rotated.stat().st_size,
    }

    archived.write_text("changed historical content\n", encoding="utf-8")
    assert analyze_evidence_source(logs_dir).summary["source_sha256"] == original_hash


def test_live_source_hash_and_size_describe_exact_bytes_consumed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    active = logs_dir / "screensaver_perf.log"
    parsed_payload = (
        "2026-08-13 15:38:23 - metrics - INFO - "
        "[PERF] [GL PAINT] Slide metrics: screen=0, frames=60, "
        "avg_fps=60.0, dt_max=20.0ms, target_fps=60, outcome=completed\n"
    ).encode("utf-8")
    appended_payload = b"2026-08-13 15:38:24 - still writing\n"
    active.write_bytes(parsed_payload)

    original_read_bytes = Path.read_bytes
    mutated = False

    def read_bytes_then_append(path: Path) -> bytes:
        nonlocal mutated
        payload = original_read_bytes(path)
        if path == active and not mutated:
            mutated = True
            active.write_bytes(payload + appended_payload)
        return payload

    monkeypatch.setattr(Path, "read_bytes", read_bytes_then_append)

    analysis = analyze_evidence_source(logs_dir)
    expected_digest = hashlib.sha256()
    expected_digest.update(active.name.encode("utf-8"))
    expected_digest.update(b"\0")
    expected_digest.update(parsed_payload)

    assert analysis.summary["source_sha256"] == expected_digest.hexdigest().upper()
    assert analysis.summary["source_archive_sha256"] == expected_digest.hexdigest().upper()
    assert analysis.summary["source_files"] == {active.name: len(parsed_payload)}
    assert active.stat().st_size == len(parsed_payload + appended_payload)
    assert analysis.summary["time_range"] == {
        "first": "2026-08-13 15:38:23",
        "last": "2026-08-13 15:38:23",
    }


def test_explicit_evidence_directory_retains_recursive_log_discovery(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "selected_evidence"
    nested_dir = evidence_dir / "copied_sidecars"
    nested_dir.mkdir(parents=True)
    (nested_dir / "screensaver_perf.log").write_text(
        "2026-08-10 12:00:00 - metrics - INFO - "
        "[PERF] [GL PAINT] Slide metrics: screen=0, frames=60, "
        "avg_fps=60.0, dt_max=20.0ms, target_fps=60, outcome=completed\n",
        encoding="utf-8",
    )

    analysis = analyze_evidence_source(evidence_dir)

    assert [row["timestamp"] for row in analysis.frame_rows] == [
        "2026-08-10 12:00:00"
    ]
    assert analysis.summary["source_files"] == {
        "screensaver_perf.log": (
            nested_dir / "screensaver_perf.log"
        ).stat().st_size,
    }


def test_texture_upload_parser_keeps_pre_1_16_records(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "selected_evidence"
    evidence_dir.mkdir()
    (evidence_dir / "screensaver_perf.log").write_text(
        "2026-08-13 17:42:45 - metrics - INFO - "
        "[PERF][GL TEXTURE][UPLOAD] owner=compositor:0 size=2560x1440 "
        "upload_bytes=14745600 path=pbo total_ms=10.000 "
        "image_prepare_ms=4.000 bits_copy_ms=2.000 texture_alloc_ms=0.100 "
        "pbo_stage_ms=3.500 texture_submit_ms=0.400 unattributed_ms=0.000\n",
        encoding="utf-8",
    )

    analysis = analyze_evidence_source(evidence_dir)
    upload_summary = analysis.summary["phase5"]["texture_upload"]
    upload_row = next(
        row for row in analysis.phase5_rows if row["kind"] == "texture_upload"
    )

    assert upload_summary["records"] == 1
    assert upload_summary["image_formats"] == {}
    assert upload_summary["bits_paths"] == {}
    assert upload_summary["by_path"]["pbo"]["total_ms"]["maximum"] == 10.0
    assert upload_row["upload_image_format"] == ""
    assert upload_row["upload_bits_path"] == ""
