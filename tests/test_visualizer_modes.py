"""
Tests for Spotify Visualizer visualization modes (Spectrum, Waveform, Abstract).

These tests verify the VisualizerMode enum and mode switching functionality
added to support multiple visualization styles.
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

    def test_visualizer_mode_has_waveform(self):
        """Verify WAVEFORM mode exists."""
        from widgets.spotify_visualizer_widget import VisualizerMode
        assert hasattr(VisualizerMode, "WAVEFORM")
        assert VisualizerMode.WAVEFORM.value == 2

    def test_visualizer_mode_has_abstract(self):
        """Verify ABSTRACT mode exists."""
        from widgets.spotify_visualizer_widget import VisualizerMode
        assert hasattr(VisualizerMode, "ABSTRACT")
        assert VisualizerMode.ABSTRACT.value == 3

    def test_visualizer_mode_count(self):
        """Verify exactly 3 modes exist."""
        from widgets.spotify_visualizer_widget import VisualizerMode
        modes = list(VisualizerMode)
        assert len(modes) == 3


class TestVisualizerWidgetModes:
    """Tests for visualization mode switching on SpotifyVisualizerWidget."""

    def test_widget_default_mode_is_spectrum(self, qt_app):
        """Verify default visualization mode is SPECTRUM."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        assert widget.get_visualization_mode() == VisualizerMode.SPECTRUM

    def test_set_visualization_mode_to_waveform(self, qt_app):
        """Verify mode can be changed to WAVEFORM."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        widget.set_visualization_mode(VisualizerMode.WAVEFORM)
        assert widget.get_visualization_mode() == VisualizerMode.WAVEFORM

    def test_set_visualization_mode_to_abstract(self, qt_app):
        """Verify mode can be changed to ABSTRACT."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        widget.set_visualization_mode(VisualizerMode.ABSTRACT)
        assert widget.get_visualization_mode() == VisualizerMode.ABSTRACT

    def test_set_visualization_mode_clears_waveform_history(self, qt_app):
        """Verify waveform history is cleared on mode change."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        # Add some fake history
        widget._waveform_history = [0.5, 0.6, 0.7]
        # Change mode
        widget.set_visualization_mode(VisualizerMode.ABSTRACT)
        assert len(widget._waveform_history) == 0

    def test_set_visualization_mode_clears_particles(self, qt_app):
        """Verify abstract particles are cleared on mode change."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        # Add some fake particles
        widget._abstract_particles = [{"x": 0, "y": 0}]
        # Change mode
        widget.set_visualization_mode(VisualizerMode.SPECTRUM)
        assert len(widget._abstract_particles) == 0

    def test_cycle_visualization_mode(self, qt_app):
        """Verify cycle_visualization_mode cycles through all modes."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        
        # Start at SPECTRUM
        assert widget.get_visualization_mode() == VisualizerMode.SPECTRUM
        
        # Cycle to WAVEFORM
        next_mode = widget.cycle_visualization_mode()
        assert next_mode == VisualizerMode.WAVEFORM
        assert widget.get_visualization_mode() == VisualizerMode.WAVEFORM
        
        # Cycle to ABSTRACT
        next_mode = widget.cycle_visualization_mode()
        assert next_mode == VisualizerMode.ABSTRACT
        assert widget.get_visualization_mode() == VisualizerMode.ABSTRACT
        
        # Cycle back to SPECTRUM
        next_mode = widget.cycle_visualization_mode()
        assert next_mode == VisualizerMode.SPECTRUM
        assert widget.get_visualization_mode() == VisualizerMode.SPECTRUM

    def test_set_same_mode_is_noop(self, qt_app):
        """Verify setting the same mode doesn't clear state."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget, VisualizerMode
        widget = SpotifyVisualizerWidget(bar_count=15)
        
        # Add some history
        widget._waveform_history = [0.5, 0.6, 0.7]
        
        # Set same mode (SPECTRUM)
        widget.set_visualization_mode(VisualizerMode.SPECTRUM)
        
        # History should NOT be cleared (same mode)
        assert len(widget._waveform_history) == 3


class TestWaveformModeState:
    """Tests for waveform mode state management."""

    @pytest.fixture
    def widget(self, qt_app):
        """Create a SpotifyVisualizerWidget for testing."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        w = SpotifyVisualizerWidget(bar_count=15)
        yield w
        try:
            w.deleteLater()
        except Exception:
            pass

    def test_waveform_history_initialized_empty(self, widget):
        """Verify waveform history starts empty."""
        assert widget._waveform_history == []

    def test_waveform_max_samples_default(self, widget):
        """Verify waveform max samples has reasonable default."""
        assert widget._waveform_max_samples == 128


class TestAbstractModeState:
    """Tests for abstract mode state management."""

    @pytest.fixture
    def widget(self, qt_app):
        """Create a SpotifyVisualizerWidget for testing."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        w = SpotifyVisualizerWidget(bar_count=15)
        yield w
        try:
            w.deleteLater()
        except Exception:
            pass

    def test_abstract_particles_initialized_empty(self, widget):
        """Verify abstract particles list starts empty."""
        assert widget._abstract_particles == []

    def test_abstract_max_particles_default(self, widget):
        """Verify abstract max particles has reasonable default."""
        assert widget._abstract_max_particles == 50

    def test_abstract_spawn_timestamp_initialized(self, widget):
        """Verify abstract spawn timestamp is initialized."""
        assert widget._abstract_last_spawn_ts == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
