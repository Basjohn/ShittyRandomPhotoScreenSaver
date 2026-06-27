from __future__ import annotations

from tools.transition_perf_health_parser import parse_perf_health_lines


def test_perf_health_flags_high_refresh_window_that_delivers_near_sixty():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl - INFO - [PERF] [GL ANIM] Raindrops metrics: "
            "duration=5000.0ms, frames=312, avg_fps=62.4, dt_min=2.00ms, "
            "dt_max=45.00ms, spikes=0, target_fps=165, outcome=complete"
        ]
    )

    assert len(report.high_target_near_sixty) == 1
    assert report.high_target_near_sixty[0].name == "Raindrops"
    assert "high-refresh" in report.anomalies[0]


def test_perf_health_allows_high_refresh_window_that_remains_high():
    report = parse_perf_health_lines(
        [
            "17:40:01 - rendering.gl - INFO - [PERF] [GL ANIM] Raindrops metrics: "
            "duration=5000.0ms, frames=720, avg_fps=144.0, dt_min=2.00ms, "
            "dt_max=18.00ms, spikes=0, target_fps=165, outcome=complete"
        ]
    )

    assert report.high_target_near_sixty == []
    assert report.anomalies == []


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
            "dt_min=14.62ms, dt_max=100.27ms, active_count=0, fps_target=60"
        ]
    )

    assert len(report.animation_manager_under_target) == 1
    assert report.animation_manager_under_target[0].source == "animation_manager"
    assert "animation manager" in report.anomalies[0]
