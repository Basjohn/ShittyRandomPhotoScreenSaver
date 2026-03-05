"""Regression tests for the Visualizer Architecture Split (Phase 2).

Verifies that:
1. Extracted modules exist and export expected functions.
2. Widget delegate methods route to the extracted modules.
3. Widget line count stays below the target threshold.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest  # noqa: F401 – test framework


# ------------------------------------------------------------------
# Module existence & export checks
# ------------------------------------------------------------------

class TestTickPipelineExports:
    """Verify tick_pipeline.py exports all expected functions."""

    def test_module_importable(self):
        from widgets.spotify_visualizer import tick_pipeline
        assert tick_pipeline is not None

    def test_on_tick_exists(self):
        from widgets.spotify_visualizer.tick_pipeline import on_tick
        assert callable(on_tick)

    def test_process_heartbeat_exists(self):
        from widgets.spotify_visualizer.tick_pipeline import process_heartbeat
        assert callable(process_heartbeat)

    def test_dispatch_bubble_simulation_exists(self):
        from widgets.spotify_visualizer.tick_pipeline import dispatch_bubble_simulation
        assert callable(dispatch_bubble_simulation)

    def test_consume_engine_bars_exists(self):
        from widgets.spotify_visualizer.tick_pipeline import consume_engine_bars
        assert callable(consume_engine_bars)

    def test_push_gpu_frame_exists(self):
        from widgets.spotify_visualizer.tick_pipeline import push_gpu_frame
        assert callable(push_gpu_frame)

    def test_record_tick_perf_exists(self):
        from widgets.spotify_visualizer.tick_pipeline import record_tick_perf
        assert callable(record_tick_perf)

    def test_log_audio_latency_metrics_exists(self):
        from widgets.spotify_visualizer.tick_pipeline import log_audio_latency_metrics
        assert callable(log_audio_latency_metrics)


class TestModeTransitionExports:
    """Verify mode_transition.py exports all Phase 1 + Phase 2 functions."""

    def test_module_importable(self):
        from widgets.spotify_visualizer import mode_transition
        assert mode_transition is not None

    # Phase 1 exports
    def test_cycle_mode_exists(self):
        from widgets.spotify_visualizer.mode_transition import cycle_mode
        assert callable(cycle_mode)

    def test_mode_transition_fade_factor_exists(self):
        from widgets.spotify_visualizer.mode_transition import mode_transition_fade_factor
        assert callable(mode_transition_fade_factor)

    def test_persist_vis_mode_exists(self):
        from widgets.spotify_visualizer.mode_transition import persist_vis_mode
        assert callable(persist_vis_mode)

    # Phase 2 exports
    def test_reset_visualizer_state_exists(self):
        from widgets.spotify_visualizer.mode_transition import reset_visualizer_state
        assert callable(reset_visualizer_state)

    def test_start_widget_fade_in_exists(self):
        from widgets.spotify_visualizer.mode_transition import start_widget_fade_in
        assert callable(start_widget_fade_in)

    def test_start_widget_fade_out_exists(self):
        from widgets.spotify_visualizer.mode_transition import start_widget_fade_out
        assert callable(start_widget_fade_out)

    def test_reset_teardown_bookkeeping_exists(self):
        from widgets.spotify_visualizer.mode_transition import reset_teardown_bookkeeping
        assert callable(reset_teardown_bookkeeping)

    def test_on_mode_cycle_requested_exists(self):
        from widgets.spotify_visualizer.mode_transition import on_mode_cycle_requested
        assert callable(on_mode_cycle_requested)

    def test_on_mode_fade_out_complete_exists(self):
        from widgets.spotify_visualizer.mode_transition import on_mode_fade_out_complete
        assert callable(on_mode_fade_out_complete)

    def test_prepare_engine_for_mode_reset_exists(self):
        from widgets.spotify_visualizer.mode_transition import prepare_engine_for_mode_reset
        assert callable(prepare_engine_for_mode_reset)

    def test_begin_mode_fade_in_exists(self):
        from widgets.spotify_visualizer.mode_transition import begin_mode_fade_in
        assert callable(begin_mode_fade_in)

    def test_check_mode_teardown_ready_exists(self):
        from widgets.spotify_visualizer.mode_transition import check_mode_teardown_ready
        assert callable(check_mode_teardown_ready)

    def test_invalidate_shadow_cache_if_needed_exists(self):
        from widgets.spotify_visualizer.mode_transition import invalidate_shadow_cache_if_needed
        assert callable(invalidate_shadow_cache_if_needed)

    def test_on_first_frame_after_cold_start_exists(self):
        from widgets.spotify_visualizer.mode_transition import on_first_frame_after_cold_start
        assert callable(on_first_frame_after_cold_start)

    def test_get_gpu_fade_factor_exists(self):
        from widgets.spotify_visualizer.mode_transition import get_gpu_fade_factor
        assert callable(get_gpu_fade_factor)


class TestTickHelpersExports:
    """Verify tick_helpers.py still exports its Phase 1 functions."""

    def test_get_transition_context(self):
        from widgets.spotify_visualizer.tick_helpers import get_transition_context
        assert callable(get_transition_context)

    def test_resolve_max_fps(self):
        from widgets.spotify_visualizer.tick_helpers import resolve_max_fps
        assert callable(resolve_max_fps)

    def test_rebuild_geometry_cache(self):
        from widgets.spotify_visualizer.tick_helpers import rebuild_geometry_cache
        assert callable(rebuild_geometry_cache)

    def test_apply_visual_smoothing(self):
        from widgets.spotify_visualizer.tick_helpers import apply_visual_smoothing
        assert callable(apply_visual_smoothing)

    def test_log_perf_snapshot(self):
        from widgets.spotify_visualizer.tick_helpers import log_perf_snapshot
        assert callable(log_perf_snapshot)


# ------------------------------------------------------------------
# Widget delegation wiring
# ------------------------------------------------------------------

class TestWidgetDelegation:
    """Verify the widget's delegate methods exist and are thin wrappers."""

    def test_on_tick_is_delegate(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        src = inspect.getsource(SpotifyVisualizerWidget._on_tick)
        assert "tick_pipeline" in src, "_on_tick should delegate to tick_pipeline"

    def test_log_audio_latency_is_delegate(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        src = inspect.getsource(SpotifyVisualizerWidget._log_audio_latency_metrics)
        assert "tick_pipeline" in src, "_log_audio_latency_metrics should delegate to tick_pipeline"

    def test_reset_visualizer_state_is_delegate(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        src = inspect.getsource(SpotifyVisualizerWidget._reset_visualizer_state)
        assert "mode_transition" in src

    def test_start_widget_fade_in_is_delegate(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        src = inspect.getsource(SpotifyVisualizerWidget._start_widget_fade_in)
        assert "mode_transition" in src

    def test_check_mode_teardown_ready_is_delegate(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        src = inspect.getsource(SpotifyVisualizerWidget._check_mode_teardown_ready)
        assert "mode_transition" in src

    def test_get_gpu_fade_factor_is_delegate(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        src = inspect.getsource(SpotifyVisualizerWidget._get_gpu_fade_factor)
        assert "mode_transition" in src


# ------------------------------------------------------------------
# Monolith size guard
# ------------------------------------------------------------------

class TestWidgetSize:
    """Ensure the widget stays below the monolith threshold."""

    def test_widget_below_1700_lines(self):
        widget_path = Path(__file__).resolve().parent.parent / "widgets" / "spotify_visualizer_widget.py"
        line_count = len(widget_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 1700, (
            f"spotify_visualizer_widget.py has {line_count} lines, "
            f"exceeding the 1700-line monolith threshold"
        )
