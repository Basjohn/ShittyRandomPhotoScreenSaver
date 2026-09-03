"""
Tests for Spotify Visualizer visualization modes.

These tests verify the VisualizerMode enum and the five active registry modes.
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
        assert len(modes) == 5
        assert modes[0] == VisualizerMode.SPECTRUM
        assert {m.name.lower() for m in modes} == set(VISUALIZER_MODE_IDS)

    def test_registry_default_mode_id_matches_canonical_default(self):
        """Verify the shared default-mode helper stays aligned with product defaults."""
        from core.settings.default_settings import DEFAULT_SETTINGS
        from core.settings.visualizer_mode_registry import get_default_visualizer_mode_id
        assert get_default_visualizer_mode_id() == DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]["mode"]


# NOTE: TestVisualizerWidgetModes and TestVisualizerWidgetBasics were removed
# here. They exercised the removed pre-cutover `SpotifyVisualizerWidget`
# monolith (mode get/set, bar_segments/display_bars/target_bars). The retained
# Quick visualizer owns mode selection through `VisualizerRuntimeController` /
# `quick_display_visualizer_owner`; that behavior is covered by
# `tests/test_qtquick_visualizer_all_modes.py`,
# `tests/test_visualizer_runtime_controller.py` and the per-mode
# `tests/test_qtquick_visualizer_*` suite.
