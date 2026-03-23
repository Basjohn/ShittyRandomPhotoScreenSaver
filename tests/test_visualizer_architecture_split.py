"""Focused regression guards for the visualizer architecture split.

These tests intentionally stay small:
- required extracted modules still export the main entrypoints we depend on
- widget delegate methods still forward into the extracted modules
- the main visualizer widget does not quietly bloat back into a monolith
"""
from __future__ import annotations

import os
from importlib import import_module
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
TEST_APPDATA = ROOT / "tests_tmp_appdata"
TEST_APPDATA.mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(TEST_APPDATA)


@pytest.mark.parametrize(
    "module_name, expected_exports",
    [
        (
            "widgets.spotify_visualizer.tick_pipeline",
            {
                "on_tick",
                "consume_engine_bars",
                "push_gpu_frame",
                "log_audio_latency_metrics",
            },
        ),
        (
            "widgets.spotify_visualizer.mode_transition",
            {
                "cycle_mode",
                "reset_visualizer_state",
                "check_mode_teardown_ready",
                "get_gpu_fade_factor",
            },
        ),
        (
            "widgets.spotify_visualizer.tick_helpers",
            {
                "get_transition_context",
                "resolve_max_fps",
                "apply_visual_smoothing",
            },
        ),
    ],
)
def test_visualizer_split_modules_export_required_entrypoints(module_name: str, expected_exports: set[str]) -> None:
    module = import_module(module_name)
    missing = {
        name for name in expected_exports
        if not callable(getattr(module, name, None))
    }
    assert not missing, f"{module_name} missing required exports: {sorted(missing)}"


class TestWidgetDelegation:
    """Ensure the widget still delegates to the extracted modules."""

    def test_on_tick_delegates_to_tick_pipeline(self, monkeypatch):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from widgets.spotify_visualizer import tick_pipeline

        calls = []
        monkeypatch.setattr(tick_pipeline, "on_tick", lambda widget: calls.append(widget))

        sentinel = object()
        SpotifyVisualizerWidget._on_tick(sentinel)

        assert calls == [sentinel]

    def test_reset_visualizer_state_delegates_to_mode_transition(self, monkeypatch):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from widgets.spotify_visualizer import mode_transition

        calls = []

        def _fake(widget, *, clear_overlay=False, replay_cached=False):
            calls.append((widget, clear_overlay, replay_cached))

        monkeypatch.setattr(mode_transition, "reset_visualizer_state", _fake)

        sentinel = object()
        SpotifyVisualizerWidget._reset_visualizer_state(
            sentinel,
            clear_overlay=True,
            replay_cached=False,
        )

        assert calls == [(sentinel, True, False)]

    def test_get_gpu_fade_factor_delegates_to_mode_transition(self, monkeypatch):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from widgets.spotify_visualizer import mode_transition

        monkeypatch.setattr(mode_transition, "get_gpu_fade_factor", lambda widget, now_ts: (id(widget), now_ts))

        sentinel = object()
        result = SpotifyVisualizerWidget._get_gpu_fade_factor(sentinel, 4.25)

        assert result == (id(sentinel), 4.25)


def test_visualizer_widget_stays_below_monolith_threshold():
    widget_path = ROOT / "widgets" / "spotify_visualizer_widget.py"
    line_count = len(widget_path.read_text(encoding="utf-8").splitlines())
    assert line_count < 2200, (
        f"spotify_visualizer_widget.py has {line_count} lines, "
        "exceeding the current monolith threshold"
    )
