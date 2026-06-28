from __future__ import annotations

from tools.transition_perf_health_parser import parse_perf_health_lines


def test_perf_health_flags_high_refresh_window_that_delivers_near_sixty():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
            "screen=0, frames=312, avg_fps=62.4, dt_min=2.00ms, dt_max=45.00ms, "
            "dur_min=0.50ms, dur_max=5.00ms, slow_frames=0, target_fps=165, outcome=complete"
        ]
    )

    assert len(report.high_target_near_sixty) == 1
    assert report.high_target_near_sixty[0].name == "Raindrops"
    assert report.high_target_near_sixty[0].screen == 0
    assert "high-refresh" in report.anomalies[0]


def test_perf_health_allows_high_refresh_window_that_remains_high():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
            "frames=720, avg_fps=144.0, dt_min=2.00ms, dt_max=18.00ms, "
            "dur_min=0.50ms, dur_max=5.00ms, slow_frames=0, target_fps=165, outcome=complete"
        ]
    )

    assert report.high_target_near_sixty == []
    assert report.high_target_under_delivered == []
    assert report.anomalies == []


def test_perf_health_flags_high_refresh_window_that_is_not_near_sixty_but_far_under_target():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
            "frames=795, avg_fps=108.0, dt_min=2.00ms, dt_max=45.00ms, "
            "dur_min=0.50ms, dur_max=5.00ms, slow_frames=0, target_fps=165, outcome=complete"
        ]
    )

    assert report.high_target_near_sixty == []
    assert len(report.high_target_under_delivered) == 1
    assert any(
        "far under target" in anomaly or "render/paint cadence split" in anomaly
        for anomaly in report.anomalies
    )


def test_perf_health_flags_high_refresh_stable_divisor_cadence():
    report = parse_perf_health_lines(
        [
            "2026-06-27 17:40:01 - rendering.gl - INFO - [PERF] [GL PAINT] Slide metrics: "
            "frames=425, avg_fps=82.1, dt_min=4.00ms, dt_max=45.00ms, "
            "dur_min=0.50ms, dur_max=5.00ms, slow_frames=0, target_fps=165, outcome=complete"
        ]
    )

    assert len(report.high_target_stable_divisor_windows) == 1
    assert report.high_target_stable_divisor_windows[0].timestamp == "2026-06-27 17:40:01"
    assert "divisor/cadence locked" in report.anomalies[0]


def test_perf_health_flags_render_paint_split_without_calling_it_timer_mutation():
    report = parse_perf_health_lines(
        [
            "2026-06-27 17:40:01 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "frames=850, avg_fps=164.8, dt_min=5.50ms, dt_max=12.00ms, "
            "stalls=0, target=165Hz, outcome=paused",
            "2026-06-27 17:40:01 - rendering.gl - INFO - [PERF] [GL PAINT] Slide metrics: "
            "frames=570, avg_fps=110.1, dt_min=1.00ms, dt_max=57.01ms, "
            "dur_min=1.00ms, dur_max=7.53ms, slow_frames=0, target_fps=165, outcome=complete",
        ]
    )

    assert len(report.high_target_render_paint_split_windows) == 1
    assert report.high_target_render_paint_split_windows[0].source == "gl_paint"
    assert report.high_target_near_sixty == []
    assert any("render/paint cadence split" in anomaly for anomaly in report.anomalies)


def test_perf_health_flags_paired_paint_delivery_starvation_on_high_refresh_display():
    report = parse_perf_health_lines(
        [
            "2026-06-27 21:21:45 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=0, frames=822, avg_fps=164.8, dt_min=5.50ms, dt_max=12.00ms, "
            "stalls=0, target=165Hz, outcome=running",
            "2026-06-27 21:21:45 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
            "screen=0, frames=292, avg_fps=58.4, dt_min=3.00ms, dt_max=57.01ms, "
            "dur_min=0.50ms, dur_max=6.20ms, slow_frames=0, target_fps=165, outcome=complete",
        ]
    )

    assert len(report.paint_delivery_starvation_windows) == 1
    starvation = report.paint_delivery_starvation_windows[0]
    assert starvation.render.avg_fps == 164.8
    assert starvation.paint.avg_fps == 58.4
    assert "paint delivery starvation" in report.anomalies[0]


def test_perf_health_flags_paired_paint_delivery_starvation_on_sixty_hz_display():
    report = parse_perf_health_lines(
        [
            "2026-06-27 21:21:45 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=1, frames=299, avg_fps=59.9, dt_min=14.50ms, dt_max=28.00ms, "
            "stalls=0, target=60Hz, outcome=running",
            "2026-06-27 21:21:45 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
            "screen=1, frames=191, avg_fps=38.2, dt_min=7.00ms, dt_max=82.01ms, "
            "dur_min=0.50ms, dur_max=7.20ms, slow_frames=0, target_fps=60, outcome=complete",
        ]
    )

    assert len(report.paint_delivery_starvation_windows) == 1
    assert len(report.low_refresh_under_target) == 1
    assert any("paint delivery starvation" in anomaly for anomaly in report.anomalies)


def test_perf_health_does_not_call_bad_render_timer_paint_delivery_starvation():
    report = parse_perf_health_lines(
        [
            "2026-06-27 21:21:45 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=0, frames=280, avg_fps=56.0, dt_min=14.50ms, dt_max=120.00ms, "
            "stalls=5, target=165Hz, outcome=running",
            "2026-06-27 21:21:45 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
            "screen=0, frames=250, avg_fps=50.0, dt_min=7.00ms, dt_max=82.01ms, "
            "dur_min=0.50ms, dur_max=7.20ms, slow_frames=0, target_fps=165, outcome=complete",
        ]
    )

    assert report.paint_delivery_starvation_windows == []
    assert any("near-60" in anomaly for anomaly in report.anomalies)


def test_perf_health_flags_sixty_hz_window_far_under_target():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl - INFO - [PERF] [GL ANIM] Slide metrics: "
            "duration=5000.0ms, frames=199, avg_fps=39.8, dt_min=2.00ms, "
            "dt_max=85.00ms, spikes=0, target_fps=60, outcome=complete"
        ]
    )

    assert len(report.low_refresh_under_target) == 1
    assert "60Hz transition" in report.anomalies[0]


def test_perf_health_separates_high_refresh_animation_callback_collapse_from_paint_delivery():
    report = parse_perf_health_lines(
        [
            "2026-06-28 02:59:25 - rendering.gl - INFO - [PERF] [GL ANIM] Blinds metrics: "
            "screen=0, duration=4178.3ms, frames=247, avg_fps=59.1, "
            "dt_min=6.31ms, dt_max=55.67ms, spikes=0, target_fps=165, outcome=complete",
            "2026-06-28 02:59:25 - rendering.gl - INFO - [PERF] [GL PAINT] Blinds metrics: "
            "screen=0, frames=510, avg_fps=119.4, dt_min=2.00ms, dt_max=61.50ms, "
            "dur_min=0.50ms, dur_max=6.00ms, slow_frames=0, target_fps=165, outcome=complete",
        ]
    )

    assert len(report.high_target_animation_callback_collapse) == 1
    assert report.high_target_animation_callback_collapse[0].name == "Blinds"
    assert report.paint_delivery_starvation_windows == []
    assert any("animation/control callback cadence" in anomaly for anomaly in report.anomalies)


def test_perf_health_flags_cache_worker_fallback_with_no_registered_producer():
    report = parse_perf_health_lines(
        [
            "17:40:01 - engine.image_pipeline - WARNING - [CACHE] [FALLBACK] "
            "Worker fallback display=1 reason=scaled_miss raw_state=raw_missing "
            "prefetch_state=raw_inflight:0,raw_pending:0,scaled_inflight:0,scaled_pending:0 "
            "path=C:\\wall\\one.jpg target=2560x1440 mode=fill"
        ]
    )

    assert len(report.cache_fallbacks) == 1
    assert len(report.zero_producer_cache_fallbacks) == 1
    assert report.zero_producer_cache_fallbacks[0].display == 1
    assert "cache worker fallbacks" in report.anomalies[0]


def test_perf_health_does_not_flag_cache_fallback_when_prefetch_has_producers():
    report = parse_perf_health_lines(
        [
            "17:40:01 - engine.image_pipeline - WARNING - [CACHE] [FALLBACK] "
            "Worker fallback display=0 reason=scaled_miss raw_state=raw_missing "
            "prefetch_state=raw_inflight:1,raw_pending:2,scaled_inflight:0,scaled_pending:1 "
            "path=C:\\wall\\one.jpg target=2560x1440 mode=fill"
        ]
    )

    assert len(report.cache_fallbacks) == 1
    assert report.zero_producer_cache_fallbacks == []
    assert report.anomalies == []


def test_perf_health_keeps_shader_fallback_loud_in_summary():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl_compositor_pkg.paint - WARNING - "
            "[GL PAINT][FALLBACK] All active shader paths failed; rendering base image only "
            "active=diffuse use_shaders=False last_failure=diffuse:capability_unavailable"
        ]
    )

    assert len(report.shader_fallbacks) == 1
    assert report.anomalies == ["shader fallbacks present: 1"]


def test_perf_health_flags_animation_manager_windows_under_target():
    report = parse_perf_health_lines(
        [
            "17:40:01 - core.animation.animator - INFO - [PERF] [ANIM] "
            "AnimationManager metrics: duration=604.3ms, frames=15, avg_fps=24.8, "
            "dt_min=14.62ms, dt_max=100.27ms, active_count=2, fps_target=60"
        ]
    )

    assert len(report.animation_manager_under_target) == 1
    assert report.animation_manager_under_target[0].source == "animation_manager"
    assert report.animation_manager_under_target[0].active_count == 2
    assert "animation manager" in report.anomalies[0]


def test_perf_health_allows_idle_animation_manager_under_target_window():
    report = parse_perf_health_lines(
        [
            "17:40:01 - core.animation.animator - INFO - [PERF] [ANIM] "
            "AnimationManager metrics: duration=604.3ms, frames=15, avg_fps=24.8, "
            "dt_min=14.62ms, dt_max=100.27ms, active_count=0, fps_target=60"
        ]
    )

    assert report.animation_manager_under_target == []
    assert report.anomalies == []


def test_perf_health_flags_media_widget_timer_starvation_gap():
    report = parse_perf_health_lines(
        [
            "17:40:01 - core.threading.manager - WARNING - [PERF] [TIMER] "
            "Large gap for MediaWidget smart poll: 2502.80ms "
            "(interval=1000ms likely=compositor_cadence_starvation context={})"
        ]
    )

    assert len(report.media_timer_starvation_gaps) == 1
    assert report.media_timer_starvation_gaps[0].owner == "MediaWidget smart poll"
    assert "media widget timer gaps" in report.anomalies[0]


def test_perf_health_flags_spotify_visualizer_latency_and_tick_spikes():
    report = parse_perf_health_lines(
        [
            "17:40:01 - widgets.spotify_visualizer.tick_pipeline - WARNING - "
            "[SPOTIFY_VIS][LATENCY] lag_ms=84.6 mode=spectrum transition_phase=0",
            "17:40:02 - widgets.spotify_visualizer.tick_helpers - WARNING - "
            "[PERF] [SPOTIFY_VIS] Tick dt spike_ms=52.38 mode=spectrum",
        ]
    )

    assert len(report.significant_visualizer_timing_warnings) == 2
    assert {w.kind for w in report.significant_visualizer_timing_warnings} == {
        "latency",
        "tick_spike",
    }
    assert "spotify visualizer timing warnings" in report.anomalies[0]


def test_perf_health_flags_severe_spotify_visualizer_latency_as_own_anomaly():
    report = parse_perf_health_lines(
        [
            "21:03:24 - widgets.spotify_visualizer.tick_pipeline - ERROR - "
            "[!!!!][SPOTIFY_VIS][LATENCY] lag_ms=1805.4 mode=bubble "
            "transition_phase=0 pending=<none> trigger=transition_end",
        ]
    )

    assert len(report.severe_visualizer_latency_warnings) == 1
    assert report.severe_visualizer_latency_warnings[0].kind == "severe_latency"
    assert any("severe latency" in anomaly for anomaly in report.anomalies)


def test_perf_health_flags_slow_texture_uploads_as_own_anomaly():
    report = parse_perf_health_lines(
        [
            "21:02:44 - rendering.gl_programs.texture_manager - WARNING - "
            "[PERF] [GL TEXTURE] Slow upload: 20.58ms (3840x2160, pbo=True)"
        ]
    )

    assert len(report.slow_texture_uploads) == 1
    assert report.slow_texture_uploads[0].width == 3840
    assert report.slow_texture_uploads[0].height == 2160
    assert report.slow_texture_uploads[0].pbo is True
    assert any("slow GL texture uploads" in anomaly for anomaly in report.anomalies)


def test_perf_health_flags_pending_paint_requeue_rescues():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.adaptive_timer - WARNING - "
            "[PERF] [GL RENDER] Pending paint update exceeded coalescing window; "
            "requesting another transition frame age_ms=18.10 stale_after_ms=15.15 target_fps=165"
        ]
    )

    assert len(report.pending_paint_requeues) == 1
    assert report.anomalies == ["transition paint request coalescing rescues fired: 1"]


def test_perf_health_flags_pending_paint_stalls_without_requeue():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.adaptive_timer - WARNING - "
            "[PERF] [GL RENDER] Paint update still pending without delivery "
            "age_ms=301.12 target_fps=165 screen=0 no_requeue=True"
        ]
    )

    assert len(report.pending_paint_stalls) == 1
    assert report.timeline_markers[0].kind == "pending_paint_stall"
    assert report.anomalies == ["paint update delivery stalls observed without requeue: 1"]


def test_perf_health_collects_timeline_markers_for_collapse_correlation():
    report = parse_perf_health_lines(
        [
            "21:24:24 - ui.settings_dialog - WARNING - [PERF][SETTINGS] "
            "SettingsDialog._setup_ui took 2810.1ms",
            "21:24:29 - rendering.display_manager - INFO - [PERF][DISPLAY] "
            "shutdown_render_pipeline display=0 reason=settings_apply",
            "21:24:30 - rendering.custom_layout_manager - INFO - [GEO_AUDIT] "
            "phase=save_scene widget=clock",
            "21:24:31 - rendering.gl - WARNING - [PERF] [FRAME] "
            "frame-budget spike display=0 duration_ms=77.4",
        ]
    )

    assert [marker.kind for marker in report.timeline_markers] == [
        "settings_stall",
        "display_lifecycle",
        "geometry_save",
        "frame_budget_spike",
    ]
