"""Common deterministic workload and evidence-schema contracts."""

from __future__ import annotations

import json

import pytest

from tools.presentation_benchmark_core import (
    COMMON_SLIDE_SOURCE_SPEC,
    COMMON_TIMELINE,
    MAX_OBSERVED_PHASE_OVERRUN_NS,
    BenchmarkMetricsRecorder,
    build_common_bubble_feature_clip,
    common_logical_deadlines_ns,
    common_workload_identity,
    parse_candidate_args,
)


def test_common_timeline_has_the_exact_stage_one_markers():
    assert COMMON_TIMELINE.to_dict() == {
        "logical_hz": 90,
        "markers": [
            {"name": "first_intentional_visible_frame", "elapsed_ns": 0},
            {"name": "slide_bubble_start", "elapsed_ns": 1_000_000_000},
            {"name": "slide_end", "elapsed_ns": 6_000_000_000},
            {"name": "synthetic_pause", "elapsed_ns": 11_000_000_000},
            {"name": "synthetic_resume", "elapsed_ns": 13_000_000_000},
            {"name": "stop_report", "elapsed_ns": 15_000_000_000},
        ],
    }
    assert COMMON_TIMELINE.sha256() == (
        "957625004b1ebc0ab9123602f46501be97c4723fb5ecfd18cb99d0c030d1248c"
    )


@pytest.mark.parametrize(
    ("elapsed_ns", "phase", "slide_active", "progress", "bubble", "playing", "stopped"),
    (
        (0, "startup", False, 0.0, False, True, False),
        (1_000_000_000, "slide_bubble", True, 0.0, True, True, False),
        (3_500_000_000, "slide_bubble", True, 0.5, True, True, False),
        (6_000_000_000, "settled_bubble", False, 1.0, True, True, False),
        (11_000_000_000, "paused_hold", False, 1.0, True, False, False),
        (13_000_000_000, "resumed_bubble", False, 1.0, True, True, False),
        (15_000_000_000, "stopped", False, 1.0, False, True, True),
    ),
)
def test_common_timeline_state_is_boundary_exact(
    elapsed_ns,
    phase,
    slide_active,
    progress,
    bubble,
    playing,
    stopped,
):
    state = COMMON_TIMELINE.state_at(elapsed_ns)

    assert state.phase == phase
    assert state.slide_active is slide_active
    assert state.slide_progress == pytest.approx(progress)
    assert state.bubble_active is bubble
    assert state.playing is playing
    assert state.stopped is stopped


def test_common_logical_deadlines_are_integer_derived_and_do_not_drift():
    deadlines = common_logical_deadlines_ns()

    assert len(deadlines) == 14 * 90
    assert deadlines[0] == 1_000_000_000
    assert deadlines[-1] == 14_988_888_889
    assert 11_000_000_000 in deadlines
    assert 13_000_000_000 in deadlines
    assert all(right > left for left, right in zip(deadlines, deadlines[1:]))


def test_common_bubble_source_is_repeatable_and_has_only_the_named_playback_edges():
    first = build_common_bubble_feature_clip()
    second = build_common_bubble_feature_clip()

    assert first.sha256() == second.sha256()
    assert first.sha256() == (
        "2f6de6a911a555ec243e806bb6c76469bc9352faee691f2c83a55f892641336d"
    )
    assert len(first.frames) == 1260
    assert first.frames[0].timestamp_us == 1_000_000
    assert first.frames[-1].timestamp_us == 14_988_888
    assert {frame.mode for frame in first.frames} == {"bubble"}
    assert all(frame.visible for frame in first.frames)

    edges = [
        (right.timestamp_us, right.playing)
        for left, right in zip(first.frames, first.frames[1:])
        if right.playing != left.playing
    ]
    assert edges == [(11_000_000, False), (13_000_000, True)]

    paused = [
        frame
        for frame in first.frames
        if 11_000_000 <= frame.timestamp_us < 13_000_000
    ]
    assert paused
    assert all(frame.energy.continuous.overall == 0.0 for frame in paused)
    assert all(not any(frame.raw_bars) and not any(frame.waveform) for frame in paused)


def test_complete_common_workload_identity_freezes_slide_bubble_and_geometry():
    first = common_workload_identity()
    second = common_workload_identity()

    assert first == second
    assert first["timeline_sha256"] == COMMON_TIMELINE.sha256()
    assert first["bubble_source_sha256"] == build_common_bubble_feature_clip().sha256()
    assert len(first["slide_source_sha256"]) == 64
    assert len(first["workload_sha256"]) == 64
    assert COMMON_SLIDE_SOURCE_SPEC["duration_ms"] == 5000
    assert COMMON_SLIDE_SOURCE_SPEC["direction"] == "left"


def test_metrics_recorder_emits_the_shared_tail_first_schema():
    source_sha256 = build_common_bubble_feature_clip().sha256()
    recorder = BenchmarkMetricsRecorder(
        candidate="worker_push",
        population="P0",
        display="screen1_60hz",
        target_hz=60.0,
        completion_signal="external.presentmon.displayed",
        source_sha256=source_sha256,
        source_components={"bubble_source_sha256": source_sha256},
    )
    recorder.mark_phase("first_intentional_visible_frame", 2_000_000)
    recorder.mark_phase("slide_start", 1_004_000_000)
    recorder.record_request(accepted=True)
    recorder.record_request(accepted=False)
    recorder.record_request(accepted=True)
    recorder.record_logical_step(completed_ns=1_000_000_000, scheduled_ns=999_000_000)
    recorder.record_logical_step(completed_ns=1_011_000_000, scheduled_ns=1_010_000_000)
    recorder.record_logical_step(
        completed_ns=1_051_000_000,
        scheduled_ns=1_020_000_000,
        skipped_deadlines=2,
        failed=True,
    )
    recorder.record_gui_callback()
    recorder.record_gui_callback()
    recorder.record_completed_frame(
        consumed_ns=999_000_000,
        completed_ns=1_000_000_000,
        paint_ms=1.0,
        requested_ns=998_000_000,
        logical_published_ns=997_000_000,
    )
    recorder.record_completed_frame(
        consumed_ns=1_015_000_000,
        completed_ns=1_016_000_000,
        paint_ms=2.0,
        requested_ns=1_012_000_000,
        logical_published_ns=1_010_000_000,
    )
    recorder.record_completed_frame(
        consumed_ns=1_065_000_000,
        completed_ns=1_066_000_000,
        paint_ms=3.0,
        requested_ns=1_060_000_000,
        logical_published_ns=1_053_000_000,
    )
    recorder.record_resource_sample(
        system_cpu_pct=25.0,
        process_cpu_pct=8.0,
        gpu_busy_pct=31.0,
        gpu_frame_ms=0.9,
        memory_mb=220.0,
        vram_mb=180.0,
    )
    recorder.set_thread_identity(gui_thread_id=10, render_thread_id=20)

    report = recorder.report()

    assert report["counts"] == {
        "requested_opportunities": 3,
        "accepted_requests": 2,
        "completion_signal_frames": 3,
        "completed_physical_frames": 3,
        "logical_steps": 3,
        "skipped_deadlines": 2,
        "slow_steps": 1,
        "failures": 1,
        "gui_callbacks": 2,
    }
    assert report["rates"]["request_acceptance_pct"] == pytest.approx(200 / 3)
    assert report["rates"]["completion_signal_fps"] == pytest.approx(0.2)
    assert report["rates"]["completed_physical_fps"] == pytest.approx(0.2)
    assert report["timing_ms"]["completion_dt"] == {
        "count": 2,
        "p50": 16.0,
        "p90": 50.0,
        "p95": 50.0,
        "p99": 50.0,
        "max": 50.0,
        "counts_gte_ms": {
            "12": 2,
            "16": 2,
            "25": 1,
            "33": 1,
            "50": 1,
            "100": 0,
        },
    }
    assert report["timing_ms"]["paint"]["p95"] == 3.0
    assert report["timing_ms"]["request_age"]["max"] == 5.0
    assert report["timing_ms"][
        "logical_publication_to_render_consume_age"
    ]["max"] == 12.0
    assert report["timing_ms"]["longest_logical_hole"] == 40.0
    assert report["large_completion_gaps"] == [
        {
            "completed_ns": 1_066_000_000,
            "gap_ms": 50.0,
            "phase": "slide_bubble",
            "nearest_marker": "slide_bubble_start",
            "request_age_ms": 5.0,
            "source_age_ms": 12.0,
        }
    ]
    assert report["thread_identity"]["relationship"] == "distinct"
    assert report["timeline_sha256"] == COMMON_TIMELINE.sha256()
    assert report["source_sha256"] == source_sha256
    assert report["source_components"] == {"bubble_source_sha256": source_sha256}
    assert report["physical_evidence_valid"] is True
    assert report["missing_required_resource_metrics"] == []
    assert report["resources"]["gpu_frame_ms"]["unit"] == "milliseconds"
    json.dumps(report, allow_nan=False, sort_keys=True)


def test_completion_signal_and_observed_phase_semantics_are_strict():
    source_sha256 = build_common_bubble_feature_clip().sha256()

    with pytest.raises(ValueError, match="unsupported completion signal"):
        BenchmarkMetricsRecorder(
            candidate="worker_push",
            population="P0",
            display="screen0",
            target_hz=165.0,
            completion_signal="beforeRendering",
            source_sha256=source_sha256,
        )

    recorder = BenchmarkMetricsRecorder(
        candidate="worker_push",
        population="P0",
        display="screen0",
        target_hz=165.0,
        completion_signal="qrhiwidget.frameSubmitted",
        source_sha256=source_sha256,
    )
    recorder.mark_phase("first_intentional_visible_frame", 1)
    with pytest.raises(ValueError, match="unsupported observed phase"):
        recorder.mark_phase("made_up", 2)
    recorder.mark_phase("slide_end", 6_000_000_000)
    with pytest.raises(ValueError, match="canonical order"):
        recorder.mark_phase("bubble_first_logical_frame", 7_000_000_000)
    with pytest.raises(ValueError, match="bounded observation window"):
        recorder.mark_phase(
            "slide_start",
            COMMON_TIMELINE.duration_ns + MAX_OBSERVED_PHASE_OVERRUN_NS + 1,
        )

    report = recorder.report()
    assert report["physical_evidence_valid"] is False
    assert report["counts"]["completed_physical_frames"] is None
    assert report["rates"]["completed_physical_fps"] is None
    assert report["completion_semantics"]["stage"] == "graphics_submission"
    assert set(report["missing_required_resource_metrics"]) == {
        "system_cpu_pct",
        "process_cpu_pct",
        "gpu_busy_pct",
        "gpu_frame_ms",
        "memory_mb",
        "vram_mb",
    }

    quick_recorder = BenchmarkMetricsRecorder(
        candidate="quick",
        population="P0",
        display="screen0",
        target_hz=165.0,
        completion_signal="qquickwindow.frameSwapped",
        source_sha256=source_sha256,
    )
    quick_recorder.record_completed_frame(consumed_ns=1, completed_ns=2)
    quick_report = quick_recorder.report()
    assert quick_report["completion_semantics"] == {
        "stage": "queued_for_presentation",
        "physical_presentation_evidence": False,
    }
    assert quick_report["physical_evidence_valid"] is False
    assert quick_report["counts"]["completed_physical_frames"] is None
    assert quick_report["rates"]["completed_physical_fps"] is None


def test_consume_and_completion_boundaries_cannot_be_conflated():
    recorder = BenchmarkMetricsRecorder(
        candidate="quick",
        population="P0",
        display="screen1",
        target_hz=60.0,
        completion_signal="qquickwindow.frameSwapped",
        source_sha256=build_common_bubble_feature_clip().sha256(),
    )

    with pytest.raises(ValueError, match="consume timestamp cannot follow completion"):
        recorder.record_completed_frame(consumed_ns=20, completed_ns=10)
    with pytest.raises(ValueError, match="request timestamp cannot follow consume"):
        recorder.record_completed_frame(
            consumed_ns=20,
            completed_ns=30,
            requested_ns=21,
        )
    with pytest.raises(ValueError, match="publication timestamp cannot follow consume"):
        recorder.record_completed_frame(
            consumed_ns=20,
            completed_ns=30,
            logical_published_ns=21,
        )


def test_candidate_cli_requires_unique_output_and_exact_two_display_rates(tmp_path):
    output = tmp_path / "run.json"
    args = parse_candidate_args(
        (
            "--output",
            str(output),
            "--run-id",
            "p0-light-01",
            "--target-hz",
            "165,60",
        ),
        description="test",
    )

    assert args.population == "P0"
    assert args.target_hz == (165.0, 60.0)
    assert args.output == output.resolve()

    output.write_text("occupied", encoding="utf-8")
    with pytest.raises(SystemExit):
        parse_candidate_args(
            ("--output", str(output), "--run-id", "duplicate"),
            description="test",
        )

    with pytest.raises(SystemExit):
        parse_candidate_args(
            (
                "--output",
                str(tmp_path / "other.json"),
                "--run-id",
                "bad-rates",
                "--target-hz",
                "165,60,90",
            ),
            description="test",
        )
