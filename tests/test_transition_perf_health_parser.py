from __future__ import annotations

from tools.transition_perf_health_parser import parse_perf_health_lines, parse_perf_health_logs


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


def test_perf_health_flags_long_startup_first_frame_exposure():
    report = parse_perf_health_lines(
        [
            "2026-07-02 13:45:19 - rendering.display_setup - INFO - "
            "Showing on screen 1: 2560x1440 at (0, 0) DPR=1.0",
            "2026-07-02 13:45:21 - rendering.display_image_ops - INFO - "
            "[STARTUP] First frame committed on screen=1 image=C:\\wall\\one.png elapsed_ms=46.00",
        ]
    )

    assert len(report.startup_first_frame_exposures) == 1
    exposure = report.startup_first_frame_exposures[0]
    assert exposure.screen == 1
    assert exposure.exposure_ms == 2000.0
    assert exposure.first_frame_elapsed_ms == 46.0
    assert len(report.risky_startup_first_frame_exposures) == 1
    assert any("first-frame exposure" in anomaly for anomaly in report.anomalies)


def test_perf_health_allows_fast_startup_first_frame_exposure():
    report = parse_perf_health_lines(
        [
            "2026-07-02 13:45:21 - rendering.display_setup - INFO - "
            "Showing on screen 1: 2560x1440 at (0, 0) DPR=1.0",
            "2026-07-02 13:45:21 - rendering.display_image_ops - INFO - "
            "[STARTUP] First frame committed on screen=1 image=C:\\wall\\one.png elapsed_ms=46.00",
        ]
    )

    assert len(report.startup_first_frame_exposures) == 1
    assert report.risky_startup_first_frame_exposures == []
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


def test_perf_health_correlates_cross_display_spotify_visualizer_topology():
    report = parse_perf_health_lines(
        [
            "2026-07-02 14:58:22 - widgets.media_widget - INFO - "
            "[MEDIA_WIDGET] Using controller: WindowsGlobalMediaController (provider=spotify)",
            "2026-07-02 14:58:22 - rendering.spotify_widget_creators - INFO - "
            "[SPOTIFY_VIS] Created visualizer widget (screen=1, bar_count=48, "
            "monitor=2, custom_routing=True)",
            "2026-07-02 14:58:36 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=0, frames=1153, wakeups=1218, avg_fps=156.0, dt_min=3.01ms, "
            "dt_max=31.24ms, stalls=0, pending_skips=65, target=165Hz, outcome=paused",
            "2026-07-02 14:58:36 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
            "screen=0, frames=865, avg_fps=117.0, dt_min=2.53ms, dt_max=37.40ms, "
            "dur_min=0.51ms, dur_max=4.73ms, slow_frames=0, target_fps=165, outcome=complete",
        ]
    )

    assert len(report.paint_delivery_starvation_windows) == 1
    assert len(report.cross_display_spotify_paint_starvation) == 1
    topology = report.cross_display_spotify_paint_starvation[0]
    assert topology.visualizer.screen == 1
    assert topology.starvation.paint.screen == 0
    assert topology.media_seen is True
    assert any("cross-display Spotify visualizer topology" in anomaly for anomaly in report.anomalies)


def test_perf_health_does_not_blame_same_display_spotify_visualizer_topology():
    report = parse_perf_health_lines(
        [
            "2026-07-02 14:58:22 - rendering.spotify_widget_creators - INFO - "
            "[SPOTIFY_VIS] Created visualizer widget (screen=0, bar_count=48, "
            "monitor=1, custom_routing=True)",
            "2026-07-02 14:58:36 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=0, frames=1153, wakeups=1218, avg_fps=156.0, dt_min=3.01ms, "
            "dt_max=31.24ms, stalls=0, pending_skips=65, target=165Hz, outcome=paused",
            "2026-07-02 14:58:36 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
            "screen=0, frames=865, avg_fps=117.0, dt_min=2.53ms, dt_max=37.40ms, "
            "dur_min=0.51ms, dur_max=4.73ms, slow_frames=0, target_fps=165, outcome=complete",
        ]
    )

    assert len(report.paint_delivery_starvation_windows) == 1
    assert report.cross_display_spotify_paint_starvation == []


def test_perf_health_flags_spotify_overlay_overpaint_against_owner_display_target():
    report = parse_perf_health_lines(
        [
            "2026-07-02 19:19:49 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=1, frames=600, avg_fps=60.0, dt_min=15.50ms, dt_max=20.00ms, "
            "stalls=0, target=60Hz, outcome=running",
            "2026-07-02 19:19:49 - widgets.spotify_bars_gl_overlay - INFO - "
            "[PERF][SPOTIFY_VIS][OVERLAY] reason=paintGL screen=1 mode=bubble "
            "elapsed_ms=10000.0 set_state=889 paint=2754 update_requests=3643 "
            "geometry_changes=0 visible=True enabled=True",
        ]
    )

    assert len(report.spotify_overlay_perf_windows) == 1
    overpaint = report.spotify_overlay_overpaint_windows[0]
    assert overpaint.screen == 1
    assert overpaint.paint_fps > 250.0
    assert overpaint.update_request_fps > 350.0
    assert any("overlay overpainted" in anomaly for anomaly in report.anomalies)


def test_perf_health_allows_spotify_overlay_near_owner_display_target():
    report = parse_perf_health_lines(
        [
            "2026-07-02 19:19:49 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=1, frames=600, avg_fps=60.0, dt_min=15.50ms, dt_max=20.00ms, "
            "stalls=0, target=60Hz, outcome=running",
            "2026-07-02 19:19:49 - widgets.spotify_bars_gl_overlay - INFO - "
            "[PERF][SPOTIFY_VIS][OVERLAY] reason=set_state screen=1 mode=bubble "
            "elapsed_ms=10000.0 set_state=590 paint=598 update_requests=600 "
            "geometry_changes=0 visible=True enabled=True",
        ]
    )

    assert len(report.spotify_overlay_perf_windows) == 1
    assert report.spotify_overlay_overpaint_windows == []
    assert report.anomalies == []


def test_perf_health_allows_restored_smooth_overlay_feed_above_low_refresh_target():
    report = parse_perf_health_lines(
        [
            "2026-07-03 00:00:17 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=1, frames=438, wakeups=443, avg_fps=59.3, dt_min=12.58ms, "
            "dt_max=33.81ms, stalls=0, target=60Hz, outcome=paused",
            "2026-07-03 00:00:13 - widgets.spotify_bars_gl_overlay - INFO - "
            "[PERF][SPOTIFY_VIS][OVERLAY] reason=set_state screen=1 mode=bubble "
            "elapsed_ms=10000.0 set_state=953 paint=946 update_requests=953 "
            "geometry_changes=0 visible=True enabled=True",
        ]
    )

    assert len(report.spotify_overlay_perf_windows) == 1
    assert report.spotify_overlay_overpaint_windows == []
    assert report.spotify_overlay_under_delivery_windows == []
    assert report.anomalies == []


def test_perf_health_flags_spotify_overlay_under_delivery_despite_healthy_feed():
    report = parse_perf_health_lines(
        [
            "2026-07-02 20:19:16 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=1, frames=428, wakeups=431, avg_fps=59.4, dt_min=13.60ms, "
            "dt_max=33.51ms, stalls=0, pending_skips=3, target=60Hz, outcome=paused",
            "2026-07-02 20:19:14 - widgets.spotify_bars_gl_overlay - INFO - "
            "[PERF][SPOTIFY_VIS][OVERLAY] reason=set_state screen=1 mode=bubble "
            "elapsed_ms=10000.0 set_state=997 paint=400 update_requests=400 "
            "geometry_changes=0 visible=True enabled=True",
        ]
    )

    assert len(report.spotify_overlay_perf_windows) == 1
    under_delivered = report.spotify_overlay_under_delivery_windows[0]
    assert under_delivered.screen == 1
    assert under_delivered.set_state_fps > 90.0
    assert under_delivered.paint_fps < 45.0
    assert under_delivered.update_request_fps < 45.0
    assert report.spotify_overlay_overpaint_windows == []
    assert any("overlay under-delivered" in anomaly for anomaly in report.anomalies)


def test_perf_health_merges_perf_and_viz_sidecars_for_spotify_topology(tmp_path):
    perf_log = tmp_path / "screensaver_perf.log"
    viz_log = tmp_path / "screensaver_spotify_vis.log"
    perf_log.write_text(
        "\n".join(
            [
                "2026-07-02 14:58:36 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
                "screen=0, frames=1153, wakeups=1218, avg_fps=156.0, dt_min=3.01ms, "
                "dt_max=31.24ms, stalls=0, pending_skips=65, target=165Hz, outcome=paused",
                "2026-07-02 14:58:36 - rendering.gl - INFO - [PERF] [GL PAINT] Raindrops metrics: "
                "screen=0, frames=865, avg_fps=117.0, dt_min=2.53ms, dt_max=37.40ms, "
                "dur_min=0.51ms, dur_max=4.73ms, slow_frames=0, target_fps=165, outcome=complete",
            ]
        ),
        encoding="utf-8",
    )
    viz_log.write_text(
        "2026-07-02 14:58:22 - rendering.spotify_widget_creators - INFO - "
        "[SPOTIFY_VIS] Created visualizer widget (screen=1, bar_count=48, "
        "monitor=2, custom_routing=True)\n",
        encoding="utf-8",
    )

    report = parse_perf_health_logs([perf_log, viz_log])

    assert len(report.cross_display_spotify_paint_starvation) == 1


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


def test_perf_health_flags_swap_interval_constrained_context():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl_compositor_pkg.gl_lifecycle - WARNING - "
            "[PERF][GL COMPOSITOR][WARNING] GL context may still be swap-interval constrained "
            "format_interval=1 requested_interval=0 wgl_disable=False wgl_current=1 source=wglSwapIntervalEXT"
        ]
    )

    assert len(report.gl_swap_interval_warnings) == 1
    assert any("swap-interval constrained" in anomaly for anomaly in report.anomalies)


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


def test_perf_health_flags_long_completed_animation_manager_run_under_target():
    report = parse_perf_health_lines(
        [
            "17:40:01 - core.animation.animator - INFO - [PERF] [ANIM] "
            "AnimationManager metrics: duration=9174.0ms, frames=366, avg_fps=40.0, "
            "dt_min=7.32ms, dt_max=40.95ms, active_count=0, listeners=1, "
            "max_active=1, max_listeners=1, fps_target=60, owner=display:1"
        ]
    )

    assert len(report.animation_manager_under_target) == 1
    window = report.animation_manager_under_target[0]
    assert window.duration_ms == 9174.0
    assert window.listener_count == 1
    assert window.max_active_count == 1
    assert window.max_listener_count == 1
    assert window.owner == "display:1"
    assert report.idle_animation_manager_under_target == []
    assert "animation manager" in report.anomalies[0]


def test_perf_health_flags_under_target_animation_manager_without_owner():
    report = parse_perf_health_lines(
        [
            "17:40:01 - core.animation.animator - INFO - [PERF] [ANIM] "
            "AnimationManager metrics: duration=9174.0ms, frames=366, avg_fps=40.0, "
            "dt_min=7.32ms, dt_max=40.95ms, active_count=0, listeners=1, fps_target=60"
        ]
    )

    assert len(report.animation_manager_under_target) == 1
    assert len(report.animation_manager_under_target_unknown_owner) == 1
    assert any("lack concrete owner" in anomaly for anomaly in report.anomalies)


def test_perf_health_flags_idle_animation_manager_under_target_when_peak_counts_are_zero():
    report = parse_perf_health_lines(
        [
            "17:40:01 - core.animation.animator - INFO - [PERF] [ANIM] "
            "AnimationManager metrics: duration=3200.0ms, frames=96, avg_fps=30.0, "
            "dt_min=16.00ms, dt_max=70.00ms, active_count=0, listeners=0, "
            "max_active=0, max_listeners=0, fps_target=60, owner=display:1"
        ]
    )

    assert len(report.animation_manager_under_target) == 1
    assert len(report.idle_animation_manager_under_target) == 1
    assert any("no active work" in anomaly for anomaly in report.anomalies)


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


def test_perf_health_flags_slow_media_widget_async_refresh_with_dominant_phase():
    report = parse_perf_health_lines(
        [
            "17:40:01 - widgets.media_widget - WARNING - "
            "[PERF][MEDIA_WIDGET][REFRESH] slow async refresh total_ms=1302.4 "
            "worker_ms=1040.5 callback_ms=12.0 ui_delay_ms=249.9 in_flight=True state=playing"
        ]
    )

    assert len(report.media_refresh_warnings) == 1
    warning = report.media_refresh_warnings[0]
    assert warning.total_ms == 1302.4
    assert warning.dominant_phase == ("worker", 1040.5)
    assert report.timeline_markers[0].kind == "media_refresh_slow"
    assert "media widget async refresh slow paths" in report.anomalies[0]


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


def test_perf_health_collects_spotify_tick_phase_breakdown_without_new_anomaly():
    report = parse_perf_health_lines(
        [
            "17:40:02 - widgets.spotify_visualizer.tick_pipeline - WARNING - "
            "[PERF] [SPOTIFY_VIS] Tick phase breakdown total_ms=61.20 mode=bubble "
            "transition_active=True changed=True first_frame=False used_gpu=True "
            "fresh_state_ms=0.02 validity_ms=0.01 context_ms=0.08 "
            "engine_consume_ms=1.20 bubble_consume_ms=0.55 bubble_dispatch_ms=0.40 "
            "devcurve_dispatch_ms=0.01 gpu_push_ms=58.91",
        ]
    )

    assert report.anomalies == []
    assert len(report.visualizer_tick_phase_breakdowns) == 1
    breakdown = report.visualizer_tick_phase_breakdowns[0]
    assert breakdown.mode == "bubble"
    assert breakdown.transition_active is True
    assert breakdown.used_gpu is True
    assert breakdown.dominant_phase == ("gpu_push", 58.91)
    assert report.timeline_markers[0].kind == "spotify_tick_phase_breakdown"


def test_perf_health_flags_significant_settings_stalls():
    report = parse_perf_health_lines(
        [
            "2026-06-30 01:54:56 - ui.tabs.widgets_tab - INFO - "
            "[PERF][SETTINGS][WidgetsTab] lazy_build_subtab_3 in 1368.1 ms",
            "2026-06-30 01:54:57 - ui.settings_dialog - INFO - "
            "[PERF][SETTINGS] SettingsDialog._setup_ui in 2444.0 ms",
        ]
    )

    assert len(report.settings_stalls) == 2
    assert len(report.significant_settings_stalls) == 2
    assert report.significant_settings_stalls[0].name == "[WidgetsTab] lazy_build_subtab_3"
    assert any("settings UI stalls" in anomaly for anomaly in report.anomalies)


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


def test_perf_health_flags_render_pending_skips_from_coalesced_updates():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=0, frames=540, wakeups=900, avg_fps=82.0, dt_min=6.00ms, dt_max=25.00ms, "
            "stalls=0, pending_skips=360, target=165Hz, outcome=paused"
        ]
    )

    assert len(report.render_timer_pending_skip_windows) == 1
    assert report.render_timer_pending_skip_windows[0].pending_skip_count == 360
    assert report.render_timer_pending_skip_windows[0].wakeup_count == 900
    assert "render timer wakeups skipped because paint was already pending: 1" in report.anomalies


def test_perf_health_allows_low_ratio_render_pending_skips_near_target():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl - INFO - [PERF] [GL RENDER] Timer metrics: "
            "screen=0, frames=1219, wakeups=1219, avg_fps=157.1, dt_min=6.00ms, dt_max=20.00ms, "
            "stalls=0, pending_skips=57, target=165Hz, outcome=paused"
        ]
    )

    assert report.render_timer_pending_skip_windows == []
    assert not any("render timer wakeups skipped" in item for item in report.anomalies)


def test_perf_health_flags_visualizer_custom_creation_suppression():
    report = parse_perf_health_lines(
        [
            "04:14:59 - rendering.spotify_widget_creators - WARNING - "
            "[SPOTIFY_VIS][FALLBACK] Suppressing CUSTOM visualizer creation because no exact local custom rect is available"
        ]
    )

    assert len(report.visualizer_custom_suppressions) == 1
    assert report.timeline_markers[0].kind == "visualizer_custom_suppression"
    assert report.anomalies == ["spotify visualizer CUSTOM creation suppressions present: 1"]


def test_perf_health_flags_visualizer_custom_bucket_repair_as_watch_marker():
    report = parse_perf_health_lines(
        [
            "04:14:59 - rendering.spotify_widget_creators - WARNING - "
            "[SPOTIFY_VIS][FALLBACK] Repaired spotify_visualizer CUSTOM rect bucket from single foreign saved rect "
            "source_bucket=screen:stale target_bucket=screen:live monitor=2"
        ]
    )

    assert len(report.visualizer_custom_bucket_repairs) == 1
    assert report.timeline_markers[0].kind == "visualizer_custom_bucket_repair"
    assert report.anomalies == ["spotify visualizer CUSTOM rect bucket repairs present: 1"]


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
