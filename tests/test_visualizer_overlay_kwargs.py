from __future__ import annotations

import inspect

import pytest

from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay


class _StubEngine:
    def get_waveform(self):
        return [0.0] * 256

    def get_energy_bands(self):
        return EnergyBands()


@pytest.mark.qt
def test_overlay_accepts_all_gpu_kwargs(qt_app):
    """Ensure every GPU extra kwarg has a matching overlay parameter."""

    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qt_app.processEvents()

    signature = inspect.signature(SpotifyBarsGLOverlay.set_state)
    overlay_params = set(signature.parameters.keys()) - {"self"}

    base_keys = {
        "rect",
        "bars",
        "bar_count",
        "segments",
        "fill_color",
        "border_color",
        "fade",
        "playing",
        "visible",
        "ghosting_enabled",
        "ghost_alpha",
        "ghost_decay",
        "vis_mode",
        "sine_density",
        "sine_displacement",
    }
    assert base_keys <= overlay_params

    stub_engine = _StubEngine()
    modes = [
        ("spectrum", VisualizerMode.SPECTRUM),
        ("oscilloscope", VisualizerMode.OSCILLOSCOPE),
        ("sine_wave", VisualizerMode.SINE_WAVE),
        ("starfield", VisualizerMode.STARFIELD),
        ("blob", VisualizerMode.BLOB),
        ("helix", VisualizerMode.HELIX),
        ("bubble", VisualizerMode.BUBBLE),
    ]

    for mode_name, enum_value in modes:
        widget.set_visualization_mode(enum_value)
        extras = build_gpu_push_extra_kwargs(widget, mode_name, stub_engine)
        unexpected = set(extras.keys()) - overlay_params
        assert not unexpected, f"Overlay missing params for {mode_name}: {sorted(unexpected)}"

    widget.deleteLater()
