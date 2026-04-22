from __future__ import annotations

import inspect

import pytest

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.renderers.blob import get_uniform_names as blob_uniform_names
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
import widgets.spotify_bars_gl_overlay as overlay_mod


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


class _ZeroBandEngine(_StubEngine):
    def get_energy_bands(self):
        return EnergyBands(bass=0.0, mid=0.0, high=0.0, overall=0.0)


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


def test_blob_renderer_exposes_inward_liquid_uniforms():
    uniforms = set(blob_uniform_names())

    assert "u_blob_inward_liquid_color" in uniforms
    assert "u_blob_inward_liquid_enabled" in uniforms
    assert "u_blob_inward_liquid_reactivity" in uniforms
    assert "u_blob_inward_liquid_max_size" in uniforms


@pytest.mark.qt
def test_devcurve_gpu_kwargs_include_curve_payload(qt_app):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qt_app.processEvents()

    stub_engine = _StubEngine()
    widget._devcurve_sample_count = 4
    widget._devcurve_curve_bass = [0.35, 0.45, 0.4, 0.5]

    extras = build_gpu_push_extra_kwargs(widget, "devcurve", stub_engine)
    assert extras["devcurve_sample_count"] == 4
    assert extras["devcurve_curve_bass"] == [0.35, 0.45, 0.4, 0.5]
    assert "devcurve_layer_transients_enabled" in extras
    assert "devcurve_layer_bass_order" in extras
    assert "devcurve_layer_bass_outline_color" in extras
    assert "devcurve_layer_bass_outline_width" in extras
    assert "devcurve_foreground_layer_id" in extras
    assert "devcurve_foreground_shadow_enabled" in extras
    assert "devcurve_foreground_shadow_alpha" in extras
    assert "devcurve_foreground_specular_enabled" in extras
    assert "devcurve_foreground_specular_width" in extras
    assert "devcurve_specular_slot0" in extras
    assert "devcurve_specular_slot1" in extras
    assert "devcurve_specular_slot2" in extras
    assert "devcurve_outline_alpha" not in extras

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
def test_blob_gpu_kwargs_keep_cool_continuous_energy_snapshot(qt_app):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qt_app.processEvents()

    stub_engine = _StubEngine()
    widget.set_visualization_mode(VisualizerMode.BLOB)

    extras = build_gpu_push_extra_kwargs(widget, "blob", stub_engine)

    assert extras["energy_bands"] == stub_engine.get_energy_bands()
    assert extras["energy_bands"] != stub_engine.get_pre_agc_energy_bands()

    widget.deleteLater()


@pytest.mark.qt
def test_bubble_gpu_kwargs_keep_cool_continuous_energy_snapshot(qt_app):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qt_app.processEvents()

    stub_engine = _StubEngine()
    widget.set_visualization_mode(VisualizerMode.BUBBLE)

    extras = build_gpu_push_extra_kwargs(widget, "bubble", stub_engine)

    assert extras["energy_bands"] == stub_engine.get_energy_bands()
    assert extras["energy_bands"] != stub_engine.get_pre_agc_energy_bands()

    widget.deleteLater()


@pytest.mark.qt
def test_sine_paused_gpu_kwargs_enforce_minimum_travel_floor_when_all_zero(qt_app):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qt_app.processEvents()

    engine = _ZeroBandEngine()
    widget.set_visualization_mode(VisualizerMode.SINE_WAVE)
    widget._spotify_playing = False
    widget._sine_wave_travel = 0
    widget._sine_travel_line2 = 0
    widget._sine_travel_line3 = 0
    widget._sine_travel_line4 = 0
    widget._sine_travel_line5 = 0
    widget._sine_travel_line6 = 0
    widget._sine_speed = 0.1

    extras = build_gpu_push_extra_kwargs(widget, "sine_wave", engine)
    assert int(extras.get("sine_wave_travel", 0)) == 2
    assert int(extras.get("sine_travel_line2", 0)) == 0
    assert int(extras.get("sine_travel_line3", 0)) == 0
    assert int(extras.get("sine_travel_line4", 0)) == 0
    assert int(extras.get("sine_travel_line5", 0)) == 0
    assert int(extras.get("sine_travel_line6", 0)) == 0
    assert float(extras.get("line_speed", 0.0)) >= 0.22

    # Active playback path must preserve explicit "no travel" values.
    widget._spotify_playing = True
    extras_live = build_gpu_push_extra_kwargs(widget, "sine_wave", engine)
    assert int(extras_live.get("sine_wave_travel", -1)) == 0
    assert int(extras_live.get("sine_travel_line2", -1)) == 0
    assert int(extras_live.get("sine_travel_line3", -1)) == 0
    assert int(extras_live.get("sine_travel_line4", -1)) == 0
    assert int(extras_live.get("sine_travel_line5", -1)) == 0
    assert int(extras_live.get("sine_travel_line6", -1)) == 0
    assert float(extras_live.get("line_speed", 0.0)) == pytest.approx(0.1)

    widget.deleteLater()


@pytest.mark.qt
def test_overlay_accumulated_time_advances_for_paused_sine_but_not_spectrum(qt_app, monkeypatch):
    overlay = SpotifyBarsGLOverlay(parent=None)
    qt_app.processEvents()

    clock = {"t": 100.0}
    monkeypatch.setattr(overlay_mod.time, "time", lambda: clock["t"])
    base_rect = QRect(0, 0, 320, 120)
    base_bars = [0.1] * 16
    fill = QColor(200, 200, 200, 230)
    border = QColor(255, 255, 255, 255)

    overlay.set_state(
        rect=base_rect,
        bars=base_bars,
        bar_count=16,
        segments=18,
        fill_color=fill,
        border_color=border,
        fade=1.0,
        playing=False,
        visible=True,
        vis_mode="sine_wave",
    )
    t0 = float(overlay._accumulated_time)
    clock["t"] += 0.25
    overlay.set_state(
        rect=base_rect,
        bars=base_bars,
        bar_count=16,
        segments=18,
        fill_color=fill,
        border_color=border,
        fade=1.0,
        playing=False,
        visible=True,
        vis_mode="sine_wave",
    )
    t1 = float(overlay._accumulated_time)
    assert t1 > t0

    overlay._accumulated_time = 0.0
    clock["t"] += 0.25
    overlay.set_state(
        rect=base_rect,
        bars=base_bars,
        bar_count=16,
        segments=18,
        fill_color=fill,
        border_color=border,
        fade=1.0,
        playing=False,
        visible=True,
        vis_mode="spectrum",
    )
    t2 = float(overlay._accumulated_time)
    clock["t"] += 0.25
    overlay.set_state(
        rect=base_rect,
        bars=base_bars,
        bar_count=16,
        segments=18,
        fill_color=fill,
        border_color=border,
        fade=1.0,
        playing=False,
        visible=True,
        vis_mode="spectrum",
    )
    t3 = float(overlay._accumulated_time)
    assert t3 == pytest.approx(t2)

    overlay.deleteLater()


@pytest.mark.qt
def test_devcurve_set_state_applies_curve_payload(qt_app):
    overlay = SpotifyBarsGLOverlay(parent=None)
    qt_app.processEvents()

    base_rect = QRect(0, 0, 420, 220)
    base_bars = [0.0] * 16
    fill = QColor(200, 200, 200, 230)
    border = QColor(255, 255, 255, 255)

    overlay.set_state(
        rect=base_rect,
        bars=base_bars,
        bar_count=16,
        segments=18,
        fill_color=fill,
        border_color=border,
        fade=1.0,
        playing=False,
        visible=True,
        vis_mode="devcurve",
        devcurve_sample_count=4,
        devcurve_curve_bass=[0.3, 0.4, 0.35, 0.45],
    )
    assert overlay._devcurve_sample_count == 4
    assert overlay._devcurve_curve_bass == [0.3, 0.4, 0.35, 0.45]

    overlay.deleteLater()
