from __future__ import annotations

import inspect

import pytest

from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay


class _StubEngine:
    def get_waveform(self):
        return [0.0] * 256

    def get_energy_bands(self):
        return EnergyBands(bass=0.11, mid=0.22, high=0.33, overall=0.44)

    def get_raw_energy_bands(self):
        return EnergyBands()

    def get_pre_agc_energy_bands(self):
        return EnergyBands(bass=0.71, mid=0.72, high=0.73, overall=0.74)

    def get_transient_energy_bands(self):
        return TransientEnergyBands()


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
        ("blob", VisualizerMode.BLOB),
        ("bubble", VisualizerMode.BUBBLE),
    ]

    for mode_name, enum_value in modes:
        widget.set_visualization_mode(enum_value)
        extras = build_gpu_push_extra_kwargs(widget, mode_name, stub_engine)
        unexpected = set(extras.keys()) - overlay_params
        assert not unexpected, f"Overlay missing params for {mode_name}: {sorted(unexpected)}"

    widget.deleteLater()


@pytest.mark.qt
def test_spectrum_gpu_kwargs_include_shared_engine_signal_snapshot(qt_app):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qt_app.processEvents()

    stub_engine = _StubEngine()
    widget.set_visualization_mode(VisualizerMode.SPECTRUM)

    extras = build_gpu_push_extra_kwargs(widget, "spectrum", stub_engine)

    assert "energy_bands" in extras
    assert isinstance(extras["energy_bands"], EnergyBands)
    assert "transient_energy" in extras
    assert isinstance(extras["transient_energy"], TransientEnergyBands)
    assert "waveform" in extras
    assert "waveform_count" in extras

    widget.deleteLater()


@pytest.mark.qt
def test_blob_gpu_kwargs_use_pre_agc_energy_snapshot(qt_app):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qt_app.processEvents()

    stub_engine = _StubEngine()
    widget.set_visualization_mode(VisualizerMode.BLOB)

    extras = build_gpu_push_extra_kwargs(widget, "blob", stub_engine)

    assert extras["energy_bands"] == stub_engine.get_pre_agc_energy_bands()

    widget.deleteLater()


@pytest.mark.qt
def test_bubble_gpu_kwargs_use_pre_agc_energy_snapshot(qt_app):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qt_app.processEvents()

    stub_engine = _StubEngine()
    widget.set_visualization_mode(VisualizerMode.BUBBLE)

    extras = build_gpu_push_extra_kwargs(widget, "bubble", stub_engine)

    assert extras["energy_bands"] == stub_engine.get_pre_agc_energy_bands()

    widget.deleteLater()
