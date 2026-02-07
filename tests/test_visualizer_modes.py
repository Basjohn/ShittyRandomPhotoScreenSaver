"""
Tests for Spotify Visualizer visualization modes.

These tests verify the VisualizerMode enum and the SPECTRUM mode
which is the only currently implemented visualization style.

Note: WAVEFORM and ABSTRACT modes were planned but not implemented.
Tests for those modes have been removed to match actual implementation.
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
        from widgets.spotify_visualizer_widget import VisualizerMode
        assert VisualizerMode is not None

    def test_visualizer_mode_has_spectrum(self):
        """Verify SPECTRUM mode exists."""
        from widgets.spotify_visualizer_widget import VisualizerMode
        assert hasattr(VisualizerMode, "SPECTRUM")
        assert VisualizerMode.SPECTRUM.value == 1

    def test_visualizer_mode_count(self):
        """Verify all 5 visualizer modes exist."""
        from widgets.spotify_visualizer_widget import VisualizerMode
        modes = list(VisualizerMode)
        assert len(modes) == 5
        assert modes[0] == VisualizerMode.SPECTRUM
        expected = {"SPECTRUM", "OSCILLOSCOPE", "STARFIELD", "BLOB", "HELIX"}
        assert {m.name for m in modes} == expected


class TestVisualizerWidgetModes:
    """Tests for visualization mode on SpotifyVisualizerWidget."""

    def test_widget_default_mode_is_spectrum(self, qt_app):
        """Verify default visualization mode is SPECTRUM."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        assert widget.get_visualization_mode() == VisualizerMode.SPECTRUM

    def test_widget_has_get_visualization_mode(self, qt_app):
        """Verify widget has get_visualization_mode method."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        widget = SpotifyVisualizerWidget(bar_count=15)
        assert hasattr(widget, "get_visualization_mode")
        assert callable(widget.get_visualization_mode)

    def test_widget_has_set_visualization_mode(self, qt_app):
        """Verify widget has set_visualization_mode method."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        widget = SpotifyVisualizerWidget(bar_count=15)
        assert hasattr(widget, "set_visualization_mode")
        assert callable(widget.set_visualization_mode)

    def test_set_spectrum_mode(self, qt_app):
        """Verify SPECTRUM mode can be set."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        widget.set_visualization_mode(VisualizerMode.SPECTRUM)
        assert widget.get_visualization_mode() == VisualizerMode.SPECTRUM


class TestVisualizerWidgetBasics:
    """Basic tests for SpotifyVisualizerWidget."""

    def test_widget_creation(self, qt_app):
        """Verify widget can be created."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        widget = SpotifyVisualizerWidget(bar_count=15)
        assert widget is not None

    def test_widget_bar_count_initialized(self, qt_app):
        """Verify bar count is initialized."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        widget = SpotifyVisualizerWidget(bar_count=15)
        # Bar count may be adjusted by shared engine, but should be positive
        assert widget._bar_count > 0

    def test_widget_default_bar_count(self, qt_app):
        """Verify default bar count."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        widget = SpotifyVisualizerWidget()
        # Default bar count should be reasonable (32 is the default)
        assert widget._bar_count > 0

    def test_widget_has_bar_segments(self, qt_app):
        """Verify widget has bar_segments attribute."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        widget = SpotifyVisualizerWidget(bar_count=15)
        assert hasattr(widget, "_bar_segments")
        assert widget._bar_segments > 0

    def test_widget_has_display_bars(self, qt_app):
        """Verify widget has display_bars list."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        widget = SpotifyVisualizerWidget(bar_count=15)
        assert hasattr(widget, "_display_bars")
        assert isinstance(widget._display_bars, list)

    def test_widget_has_target_bars(self, qt_app):
        """Verify widget has target_bars list."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        widget = SpotifyVisualizerWidget(bar_count=15)
        assert hasattr(widget, "_target_bars")
        assert isinstance(widget._target_bars, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
