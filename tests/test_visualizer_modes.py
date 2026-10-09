"""
Tests for Spotify Visualizer visualization modes.

These tests verify the permanent audio-worker enum without collapsing isolated Sphere into it.
"""
# ruff: noqa: E402
from __future__ import annotations

import os
import sys

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import pytest


class TestVisualizerModeEnum:
    """Tests for the VisualizerMode enum."""

    def test_visualizer_mode_enum_exists(self):
        """Verify VisualizerMode enum can be imported."""
        from widgets.spotify_visualizer.audio_worker import VisualizerMode
        assert VisualizerMode is not None

    def test_visualizer_mode_has_spectrum(self):
        """Verify SPECTRUM mode exists."""
        from widgets.spotify_visualizer.audio_worker import VisualizerMode
        assert hasattr(VisualizerMode, "SPECTRUM")
        assert VisualizerMode.SPECTRUM.value == 1

    def test_visualizer_mode_count(self):
        """Verify the current visualizer mode set exists."""
        from widgets.spotify_visualizer.audio_worker import VisualizerMode
        from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
        modes = list(VisualizerMode)
        # This enum is the original audio-worker protocol, *not* the extensible
        # product catalogue: newer Scene3D modes are registered with separate
        # frame runtimes without adding legacy worker enum members.
        worker_ids = tuple(mode.name.lower() for mode in modes)
        # EXACT-VALUE INVARIANT: frozen five-member audio-worker protocol, not
        # the extensible Visualizer catalogue (Scene3D modes do not join it).
        assert worker_ids == (
            "spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve"
        )
        assert all(mode_id in VISUALIZER_MODE_IDS for mode_id in worker_ids)
        assert modes[0] == VisualizerMode.SPECTRUM
        assert tuple(mode.value for mode in modes) == tuple(range(1, len(modes) + 1))

    def test_registry_default_mode_id_matches_canonical_default(self):
        """Verify the shared default-mode helper stays aligned with product defaults."""
        from core.settings.default_contract import require_canonical_default
        from core.settings.visualizer_mode_registry import get_default_visualizer_mode_id

        assert get_default_visualizer_mode_id() == require_canonical_default(
            "widgets.spotify_visualizer.mode"
        )


# NOTE: TestVisualizerWidgetModes and TestVisualizerWidgetBasics were removed
# here. They exercised the removed pre-cutover `SpotifyVisualizerWidget`
# monolith (mode get/set, bar_segments/display_bars/target_bars). The retained
# Quick visualizer owns mode selection through `VisualizerRuntimeController` /
# `quick_display_visualizer_owner`; that behavior is covered by
# `tests/test_qtquick_visualizer_all_modes.py`,
# `tests/test_visualizer_runtime_controller.py` and the per-mode
# `tests/test_qtquick_visualizer_*` suite.
