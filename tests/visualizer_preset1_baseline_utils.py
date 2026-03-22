from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from core.settings.visualizer_presets import get_preset_settings
from utils.lockfree import TripleBuffer
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
import widgets.spotify_bars_gl_overlay as overlay_module
from widgets.spotify_visualizer.bar_computation import SpectrumShapeConfig, fft_to_bars
from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
from widgets.spotify_visualizer.config_applier import (
    apply_vis_mode_kwargs,
    build_gpu_push_extra_kwargs,
)
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.renderers import oscilloscope as osc_renderer
from widgets.spotify_visualizer.renderers import sine_wave as sine_renderer
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
from widgets.spotify_visualizer_widget import SpotifyVisualizerAudioWorker


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "tests" / "data" / "visualizer_preset1_baselines.json"
PRESET1_MODES = ("spectrum", "oscilloscope", "sine_wave", "blob", "bubble")
_QT_APP: QApplication | None = None


@dataclass(slots=True)
class _SchedulerEvent:
    strength: float


class _PeekScheduler:
    def __init__(self, events: dict[str, float] | None = None) -> None:
        self._events = dict(events or {})

    def peek_latest(self, name: str, max_age_s: float = 0.0):
        strength = float(self._events.get(name, 0.0))
        if strength <= 0.0:
            return None
        return _SchedulerEvent(strength=strength)


class _ConsumeScheduler:
    def __init__(self, events: dict[str, list[float]] | None = None) -> None:
        self._events = {key: list(values) for key, values in (events or {}).items()}

    def consume_next(self, name: str, max_age_s: float = 0.0):
        queue = self._events.get(name) or []
        if not queue:
            return None
        return _SchedulerEvent(strength=float(queue.pop(0)))


class _EngineStub:
    def __init__(
        self,
        *,
        waveform: list[float] | None = None,
        waveform_count: int | None = None,
        energy_bands: EnergyBands | None = None,
        transient_bands: TransientEnergyBands | None = None,
        scheduler: Any = None,
    ) -> None:
        self._waveform = list(waveform or [])
        self._waveform_count = int(waveform_count if waveform_count is not None else len(self._waveform))
        self._energy_bands = energy_bands or EnergyBands()
        self._transient_bands = transient_bands or TransientEnergyBands()
        self._scheduler = scheduler

    def get_waveform(self):
        return list(self._waveform)

    def get_waveform_count(self) -> int:
        return self._waveform_count

    def get_energy_bands(self):
        return self._energy_bands

    def get_pre_agc_energy_bands(self):
        return self._energy_bands

    def get_transient_energy_bands(self):
        return self._transient_bands

    def get_event_scheduler(self):
        return self._scheduler


class _UniformCaptureGL:
    def __init__(self, uniform_names: list[str]) -> None:
        self._name_to_loc = {name: index for index, name in enumerate(uniform_names)}
        self._loc_to_name = {index: name for name, index in self._name_to_loc.items()}
        self.values: dict[str, Any] = {}

    @property
    def uniform_map(self) -> dict[str, int]:
        return dict(self._name_to_loc)

    def glUniform1f(self, loc: int, value: float) -> None:
        self.values[self._loc_to_name[loc]] = float(value)

    def glUniform1i(self, loc: int, value: int) -> None:
        self.values[self._loc_to_name[loc]] = int(value)

    def glUniform4f(self, loc: int, a: float, b: float, c: float, d: float) -> None:
        self.values[self._loc_to_name[loc]] = [float(a), float(b), float(c), float(d)]

    def glUniform1fv(self, loc: int, count: int, values) -> None:
        self.values[self._loc_to_name[loc]] = [float(v) for v in list(values)[:count]]


class _VisualizerPresetState:
    def __init__(self) -> None:
        self._rainbow_enabled = False
        self._rainbow_speed = 0.5
        self._rainbow_per_bar = False
        self._spectrum_ghosting_enabled = True
        self._spectrum_ghost_alpha = 0.4
        self._spectrum_ghost_decay = 0.4
        self._osc_ghosting_enabled = False
        self._osc_ghost_intensity = 0.4
        self._blob_ghosting_enabled = False
        self._blob_ghost_alpha = 0.4
        self._blob_ghost_decay = 0.3
        self._sine_ghosting_enabled = True
        self._sine_ghost_alpha = 0.45
        self._sine_ghost_decay = 0.3
        self._bubble_ghosting_enabled = False
        self._bubble_ghost_alpha = 0.0
        self._bubble_ghost_decay = 0.4
        self._sine_heartbeat = 0.0
        self._heartbeat_intensity = 0.0
        self._sine_density = 1.0
        self._sine_displacement = 0.0
        self._use_raw_energy = False

        self._sine_glow_enabled = True
        self._sine_glow_intensity = 0.5
        self._sine_glow_size = 1.0
        self._sine_glow_reactivity = 1.0
        self._sine_glow_color = QColor(255, 255, 255, 255)
        self._sine_reactive_glow = True
        self._sine_sensitivity = 1.0
        self._sine_speed = 1.0
        self._sine_line_dim = False
        self._sine_line_offset_bias = 0.0
        self._sine_wave_travel = 0
        self._sine_card_adaptation = 0.30
        self._sine_travel_line2 = 0
        self._sine_travel_line3 = 0
        self._sine_line1_shift = 0.0
        self._sine_line2_shift = 0.0
        self._sine_line3_shift = 0.0
        self._sine_wave_effect = 0.0
        self._sine_micro_wobble = 0.0
        self._sine_crawl_amount = 0.0
        self._sine_width_reaction = 0.0
        self._sine_vertical_shift = 0
        self._sine_line_color = QColor(255, 255, 255, 255)
        self._sine_line_count = 1
        self._sine_line2_color = QColor(255, 255, 255, 180)
        self._sine_line2_glow_color = QColor(255, 255, 255, 180)
        self._sine_line3_color = QColor(255, 255, 255, 160)
        self._sine_line3_glow_color = QColor(255, 255, 255, 160)

        self._osc_glow_enabled = True
        self._osc_glow_intensity = 0.5
        self._osc_glow_size = 1.0
        self._osc_glow_reactivity = 1.0
        self._osc_glow_color = QColor(255, 255, 255, 255)
        self._osc_reactive_glow = True
        self._osc_line_amplitude = 3.0
        self._osc_smoothing = 0.7
        self._osc_speed = 1.0
        self._osc_line_dim = False
        self._osc_line_offset_bias = 0.0
        self._osc_vertical_shift = 0
        self._osc_line_color = QColor(255, 255, 255, 255)
        self._osc_line_count = 1
        self._osc_line2_color = QColor(255, 255, 255, 180)
        self._osc_line2_glow_color = QColor(255, 255, 255, 180)
        self._osc_line3_color = QColor(255, 255, 255, 160)
        self._osc_line3_glow_color = QColor(255, 255, 255, 160)

        self._blob_color = QColor(0, 180, 255, 230)
        self._blob_glow_color = QColor(0, 140, 255, 180)
        self._blob_edge_color = QColor(100, 220, 255, 230)
        self._blob_outline_color = QColor(0, 0, 0, 0)
        self._blob_pulse = 1.0
        self._blob_width = 1.0
        self._blob_size = 1.0
        self._blob_glow_intensity = 0.5
        self._blob_glow_reactivity = 1.0
        self._blob_glow_max_size = 1.0
        self._blob_reactive_glow = True
        self._blob_reactive_deformation = 1.0
        self._blob_pulse_cap = 1.0
        self._blob_pulse_release_ms = 220.0
        self._blob_stage_gain = 1.0
        self._blob_core_scale = 1.0
        self._blob_core_floor_bias = 0.35
        self._blob_stage_bias = 0.0
        self._blob_stage2_release_ms = 900.0
        self._blob_stage3_release_ms = 1200.0
        self._blob_constant_wobble = 1.0
        self._blob_reactive_wobble = 1.0
        self._blob_stretch_tendency = 0.35
        self._blob_stretch_inner = 0.5
        self._blob_stretch_outer = 0.5

        self._bubble_outline_color = QColor(255, 255, 255, 230)
        self._bubble_specular_color = QColor(255, 255, 255, 255)
        self._bubble_gradient_light = QColor(255, 255, 255, 255)
        self._bubble_gradient_dark = QColor(0, 0, 0, 255)
        self._bubble_pop_color = QColor(255, 255, 255, 255)
        self._bubble_specular_direction = "top_left"
        self._bubble_gradient_direction = "top"
        self._bubble_pos_data = []
        self._bubble_extra_data = []
        self._bubble_trail_data = []
        self._bubble_trail_strength = 0.0
        self._bubble_tail_opacity = 0.0
        self._bubble_count = 0


def _color_or_default(value: Any, fallback: tuple[int, int, int, int]) -> QColor:
    if isinstance(value, QColor):
        return QColor(value)
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        rgba = list(value[:4])
        while len(rgba) < 4:
            rgba.append(fallback[len(rgba)])
        return QColor(*rgba)
    return QColor(*fallback)


def _resolve_bar_count(mode: str, settings: dict[str, Any]) -> int:
    per_mode_key = {
        "spectrum": "spectrum_bar_count",
        "oscilloscope": "oscilloscope_bar_count",
        "sine_wave": "sine_wave_bar_count",
        "blob": "blob_bar_count",
        "bubble": "bubble_bar_count",
    }.get(mode, "bar_count")
    return int(settings.get(per_mode_key, settings.get("bar_count", 32)))


def _resolve_fill_color(settings: dict[str, Any]) -> QColor:
    return _color_or_default(settings.get("bar_fill_color"), (255, 255, 255, 230))


def _resolve_border_color(settings: dict[str, Any]) -> QColor:
    color = _color_or_default(settings.get("bar_border_color"), (255, 255, 255, 255))
    opacity = settings.get("bar_border_opacity")
    if opacity is not None:
        try:
            color.setAlphaF(max(0.0, min(1.0, float(opacity))))
        except Exception:
            pass
    return color


def _apply_shared_preset_keys(state: _VisualizerPresetState, settings: dict[str, Any]) -> None:
    color_mappings = {
        "_blob_color": "blob_color",
        "_blob_glow_color": "blob_glow_color",
        "_blob_edge_color": "blob_edge_color",
        "_blob_outline_color": "blob_outline_color",
        "_sine_glow_color": "sine_glow_color",
        "_sine_line_color": "sine_line_color",
        "_sine_line2_color": "sine_line2_color",
        "_sine_line2_glow_color": "sine_line2_glow_color",
        "_sine_line3_color": "sine_line3_color",
        "_sine_line3_glow_color": "sine_line3_glow_color",
        "_osc_glow_color": "osc_glow_color",
        "_osc_line_color": "osc_line_color",
        "_osc_line2_color": "osc_line2_color",
        "_osc_line2_glow_color": "osc_line2_glow_color",
        "_osc_line3_color": "osc_line3_color",
        "_osc_line3_glow_color": "osc_line3_glow_color",
        "_bubble_outline_color": "bubble_outline_color",
        "_bubble_specular_color": "bubble_specular_color",
        "_bubble_gradient_light": "bubble_gradient_light",
        "_bubble_gradient_dark": "bubble_gradient_dark",
        "_bubble_pop_color": "bubble_pop_color",
    }
    for attr, key in color_mappings.items():
        if key in settings:
            setattr(state, attr, _color_or_default(settings[key], (255, 255, 255, 255)))

    scalar_mappings = {
        "_rainbow_enabled": "rainbow_enabled",
        "_rainbow_speed": "rainbow_speed",
        "_rainbow_per_bar": "spectrum_rainbow_per_bar",
        "_spectrum_ghosting_enabled": "spectrum_ghosting_enabled",
        "_spectrum_ghost_alpha": "spectrum_ghost_alpha",
        "_spectrum_ghost_decay": "spectrum_ghost_decay",
        "_osc_ghosting_enabled": "osc_ghosting_enabled",
        "_osc_ghost_intensity": "osc_ghost_intensity",
        "_blob_ghosting_enabled": "blob_ghosting_enabled",
        "_blob_ghost_alpha": "blob_ghost_alpha",
        "_blob_ghost_decay": "blob_ghost_decay",
        "_sine_ghosting_enabled": "sine_ghosting_enabled",
        "_sine_ghost_alpha": "sine_ghost_alpha",
        "_sine_ghost_decay": "sine_ghost_decay",
        "_bubble_ghosting_enabled": "bubble_ghosting_enabled",
        "_bubble_ghost_alpha": "bubble_ghost_alpha",
        "_bubble_ghost_decay": "bubble_ghost_decay",
        "_sine_heartbeat": "sine_heartbeat",
        "_heartbeat_intensity": "heartbeat_intensity",
        "_sine_density": "sine_density",
        "_sine_displacement": "sine_displacement",
        "_use_raw_energy": "use_raw_energy",
        "_bubble_specular_direction": "bubble_specular_direction",
        "_bubble_gradient_direction": "bubble_gradient_direction",
    }
    for attr, key in scalar_mappings.items():
        if key in settings:
            setattr(state, attr, settings[key])


def _build_overlay_frame_kwargs(
    mode: str,
    settings: dict[str, Any],
    *,
    waveform: list[float] | None,
    waveform_count: int | None,
    energy: EnergyBands,
    transient: TransientEnergyBands,
    scheduler_events: dict[str, float] | None = None,
) -> tuple[dict[str, Any], _VisualizerPresetState]:
    state = _VisualizerPresetState()
    _apply_shared_preset_keys(state, settings)
    apply_vis_mode_kwargs(state, settings)
    engine = _EngineStub(
        waveform=waveform,
        waveform_count=waveform_count,
        energy_bands=energy,
        transient_bands=transient,
        scheduler=_PeekScheduler(scheduler_events),
    )
    extra = build_gpu_push_extra_kwargs(state, mode, engine)
    kwargs = {
        "rect": QRect(0, 0, 420, 220),
        "bars": [0.0] * max(1, _resolve_bar_count(mode, settings)),
        "bar_count": max(1, _resolve_bar_count(mode, settings)),
        "segments": 1,
        "fill_color": _resolve_fill_color(settings),
        "border_color": _resolve_border_color(settings),
        "fade": 1.0,
        "playing": True,
        "visible": True,
        "ghosting_enabled": bool(settings.get("ghosting_enabled", True)),
        "ghost_alpha": float(settings.get("ghost_alpha", 0.4)),
        "ghost_decay": float(settings.get("ghost_decay", 0.4)),
        "vis_mode": mode,
    }
    kwargs.update(extra)
    return kwargs, state


def _push_overlay_frame(
    overlay: SpotifyBarsGLOverlay,
    mode: str,
    settings: dict[str, Any],
    *,
    now_ts: float,
    dt: float,
    waveform: list[float] | None,
    waveform_count: int | None,
    energy: EnergyBands,
    transient: TransientEnergyBands,
    scheduler_events: dict[str, float] | None = None,
) -> SpotifyBarsGLOverlay:
    kwargs, _state = _build_overlay_frame_kwargs(
        mode,
        settings,
        waveform=waveform,
        waveform_count=waveform_count,
        energy=energy,
        transient=transient,
        scheduler_events=scheduler_events,
    )
    overlay._last_time_ts = now_ts - dt
    with patch.object(overlay_module.time, "time", return_value=now_ts):
        overlay.set_state(**kwargs)
    return overlay


def _capture_uniforms(upload_fn, uniform_names: list[str], state) -> dict[str, Any]:
    gl = _UniformCaptureGL(uniform_names)
    upload_fn(gl, gl.uniform_map, state)
    return gl.values


def _round_value(value: Any, digits: int = 6) -> Any:
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {key: _round_value(val, digits) for key, val in value.items()}
    if isinstance(value, list):
        return [_round_value(item, digits) for item in value]
    return value


def _make_waveform(samples: int = 64, amplitude: float = 0.82) -> list[float]:
    return [
        math.sin((index / max(1, samples)) * math.tau * 1.25) * amplitude
        for index in range(samples)
    ]


def _ensure_qt_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is not None:
        return app
    if _QT_APP is None:
        _QT_APP = QApplication([])
    return _QT_APP


def _make_spectrum_worker(settings: dict[str, Any], *, bar_count: int) -> SpotifyVisualizerAudioWorker:
    worker = SpotifyVisualizerAudioWorker(bar_count=bar_count, buffer=TripleBuffer())
    worker._np = np
    worker._spectrum_mirrored = bool(settings.get("spectrum_mirrored", True))
    worker._spectrum_shape_nodes = settings.get(
        "spectrum_shape_nodes",
        [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]],
    )
    worker._spectrum_notch_positions_mirrored = settings.get(
        "spectrum_notch_positions_mirrored",
        [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]],
    )
    worker._spectrum_notch_positions_linear = settings.get(
        "spectrum_notch_positions_linear",
        [[0.0, "Bass"], [0.25, "Low"], [0.50, "Mid"], [0.75, "Hi-Mid"], [1.0, "Treble"]],
    )
    worker._spectrum_notch_positions = (
        worker._spectrum_notch_positions_mirrored
        if worker._spectrum_mirrored
        else worker._spectrum_notch_positions_linear
    )
    worker._spectrum_shape_config = SpectrumShapeConfig(
        bass_emphasis=float(settings.get("spectrum_bass_emphasis", 0.50)),
        vocal_peak_position=float(settings.get("spectrum_vocal_position", 0.40)),
        mid_suppression=float(settings.get("spectrum_mid_suppression", 0.50)),
        wave_amplitude=float(settings.get("spectrum_wave_amplitude", 0.50)),
        profile_floor=float(settings.get("spectrum_profile_floor", 0.12)),
    )
    worker._use_recommended = False
    worker._user_sensitivity = float(settings.get("spectrum_sensitivity", settings.get("sensitivity", 1.0)))
    worker._use_dynamic_floor = bool(settings.get("spectrum_dynamic_floor", settings.get("dynamic_floor", False)))
    worker._manual_floor = float(settings.get("spectrum_manual_floor", settings.get("manual_floor", 0.12)))
    worker._applied_noise_floor = worker._manual_floor
    worker._raw_bass_avg = worker._manual_floor
    worker._kick_lane_gain = float(settings.get("spectrum_kick_lane_gain", 1.0))
    worker._transient_clamp = float(settings.get("spectrum_transient_clamp", 1.5))
    worker._transient_bass = 0.0
    worker._transient_mid = 0.0
    worker._transient_high = 0.0
    return worker


def _make_lane_fft(low: float, mid: float, high: float, size: int = 2048):
    fft = np.zeros(size, dtype="float32")
    fft[2:24] = low
    fft[48:180] = mid
    fft[260:640] = high
    return fft


def _mean(values: Any) -> float:
    arr = np.asarray(values, dtype="float64")
    return float(np.mean(arr)) if arr.size else 0.0


def _max_value(values: Any) -> float:
    arr = np.asarray(values, dtype="float64")
    return float(np.max(arr)) if arr.size else 0.0


def _generate_spectrum_metrics(settings: dict[str, Any]) -> dict[str, Any]:
    bar_count = _resolve_bar_count("spectrum", settings)
    calm_worker = _make_spectrum_worker(settings, bar_count=bar_count)
    bass_worker = _make_spectrum_worker(settings, bar_count=bar_count)
    vocal_worker = _make_spectrum_worker(settings, bar_count=bar_count)

    calm_fft = _make_lane_fft(0.10, 0.12, 0.08)
    bass_fft = _make_lane_fft(0.88, 0.16, 0.05)
    vocal_fft = _make_lane_fft(0.08, 0.86, 0.18)

    calm_bars = bass_bars = vocal_bars = None
    for _ in range(8):
        calm_bars = fft_to_bars(calm_worker, calm_fft)
        bass_bars = fft_to_bars(bass_worker, bass_fft)
        vocal_bars = fft_to_bars(vocal_worker, vocal_fft)

    calm_arr = np.asarray(calm_bars, dtype="float64")
    bass_arr = np.asarray(bass_bars, dtype="float64")
    vocal_arr = np.asarray(vocal_bars, dtype="float64")
    edge_slice = 4 if bar_count >= 12 else max(2, bar_count // 5)
    center = bar_count // 2
    center_slice = slice(max(0, center - 1), min(bar_count, center + 2))

    return {
        "preset_name": "Preset 1",
        "bar_count": bar_count,
        "calm_mean": _mean(calm_arr),
        "bass_outer_mean": _mean(np.concatenate([bass_arr[:edge_slice], bass_arr[-edge_slice:]])),
        "bass_center_mean": _mean(bass_arr[center_slice]),
        "vocal_outer_mean": _mean(np.concatenate([vocal_arr[:edge_slice], vocal_arr[-edge_slice:]])),
        "vocal_center_mean": _mean(vocal_arr[center_slice]),
    }


def _generate_osc_metrics(settings: dict[str, Any]) -> dict[str, Any]:
    overlay = SpotifyBarsGLOverlay(None)
    waveform = _make_waveform(samples=24, amplitude=0.72)
    calm = EnergyBands(bass=0.10, mid=0.08, high=0.04, overall=0.09)
    hit = EnergyBands(bass=0.42, mid=0.21, high=0.10, overall=0.26)
    calm_t = TransientEnergyBands()
    hit_t = TransientEnergyBands(bass_transient=0.35, mid_transient=0.07, high_transient=0.03)

    _push_overlay_frame(
        overlay,
        "oscilloscope",
        settings,
        now_ts=1.000,
        dt=0.016,
        waveform=waveform,
        waveform_count=24,
        energy=calm,
        transient=calm_t,
    )
    calm_uniforms = _capture_uniforms(osc_renderer.upload_uniforms, osc_renderer.get_uniform_names(), overlay)

    _push_overlay_frame(
        overlay,
        "oscilloscope",
        settings,
        now_ts=1.016,
        dt=0.016,
        waveform=waveform,
        waveform_count=24,
        energy=hit,
        transient=hit_t,
        scheduler_events={"kick": 1.0, "snare": 0.35},
    )
    hit_uniforms = _capture_uniforms(osc_renderer.upload_uniforms, osc_renderer.get_uniform_names(), overlay)

    return {
        "preset_name": "Preset 1",
        "waveform_count": hit_uniforms["u_waveform_count"],
        "calm_sensitivity": float(calm_uniforms["u_sensitivity"]),
        "hit_sensitivity": float(hit_uniforms["u_sensitivity"]),
        "hit_bass_energy": float(hit_uniforms["u_bass_energy"]),
        "hit_overall_energy": float(hit_uniforms["u_overall_energy"]),
    }


def _generate_sine_metrics(settings: dict[str, Any]) -> dict[str, Any]:
    overlay = SpotifyBarsGLOverlay(None)
    waveform = _make_waveform(samples=64, amplitude=0.78)
    calm = EnergyBands(bass=0.08, mid=0.08, high=0.04, overall=0.07)
    hit = EnergyBands(bass=0.34, mid=0.24, high=0.11, overall=0.24)
    calm_t = TransientEnergyBands()
    hit_t = TransientEnergyBands(bass_transient=0.30, mid_transient=0.06, high_transient=0.02)

    _push_overlay_frame(
        overlay,
        "sine_wave",
        settings,
        now_ts=1.000,
        dt=0.016,
        waveform=waveform,
        waveform_count=64,
        energy=calm,
        transient=calm_t,
    )
    calm_state = sine_renderer._compute_sine_reactivity_state(overlay, now_ts=1.000)

    _push_overlay_frame(
        overlay,
        "sine_wave",
        settings,
        now_ts=1.016,
        dt=0.016,
        waveform=waveform,
        waveform_count=64,
        energy=hit,
        transient=hit_t,
        scheduler_events={"kick": 1.0, "snare": 0.30},
    )
    hit_state = sine_renderer._compute_sine_reactivity_state(overlay, now_ts=1.016)

    _push_overlay_frame(
        overlay,
        "sine_wave",
        settings,
        now_ts=1.032,
        dt=0.016,
        waveform=waveform,
        waveform_count=64,
        energy=calm,
        transient=calm_t,
    )
    release_state = sine_renderer._compute_sine_reactivity_state(overlay, now_ts=1.032)

    return {
        "preset_name": "Preset 1",
        "calm_width_reaction": float(calm_state["width_reaction"]),
        "hit_width_reaction": float(hit_state["width_reaction"]),
        "release_width_reaction": float(release_state["width_reaction"]),
        "calm_wave_effect_gate": float(calm_state["wave_effect_gate"]),
        "hit_wave_effect_gate": float(hit_state["wave_effect_gate"]),
        "hit_sensitivity": float(hit_state["sensitivity"]),
    }


def _generate_blob_metrics(settings: dict[str, Any]) -> dict[str, Any]:
    overlay = SpotifyBarsGLOverlay(None)
    calm = EnergyBands(bass=0.10, mid=0.12, high=0.04, overall=0.09)
    kick = EnergyBands(bass=0.24, mid=0.07, high=0.03, overall=0.15)
    vocal = EnergyBands(bass=0.05, mid=0.24, high=0.14, overall=0.11)
    calm_t = TransientEnergyBands()
    kick_t = TransientEnergyBands(bass_transient=0.34, mid_transient=0.05, high_transient=0.02)
    vocal_t = TransientEnergyBands(bass_transient=0.02, mid_transient=0.24, high_transient=0.12)

    _push_overlay_frame(
        overlay,
        "blob",
        settings,
        now_ts=1.000,
        dt=0.016,
        waveform=None,
        waveform_count=None,
        energy=calm,
        transient=calm_t,
    )
    calm_live_overall = overlay._blob_live_overall_energy

    _push_overlay_frame(
        overlay,
        "blob",
        settings,
        now_ts=1.016,
        dt=0.016,
        waveform=None,
        waveform_count=None,
        energy=kick,
        transient=kick_t,
        scheduler_events={"kick": 1.0},
    )
    kick_live_overall = overlay._blob_live_overall_energy
    kick_stage_primary = overlay._blob_stage_progress_filtered[0]

    _push_overlay_frame(
        overlay,
        "blob",
        settings,
        now_ts=1.032,
        dt=0.016,
        waveform=None,
        waveform_count=None,
        energy=calm,
        transient=calm_t,
    )
    release_stage_primary = overlay._blob_stage_progress_filtered[0]

    _push_overlay_frame(
        overlay,
        "blob",
        settings,
        now_ts=1.048,
        dt=0.016,
        waveform=None,
        waveform_count=None,
        energy=vocal,
        transient=vocal_t,
        scheduler_events={"snare": 1.0},
    )
    vocal_stage_overall = float(getattr(overlay, "_blob_stage_input_overall", 0.0))

    return {
        "preset_name": "Preset 1",
        "calm_live_overall": float(calm_live_overall),
        "kick_live_overall": float(kick_live_overall),
        "kick_stage_primary": float(kick_stage_primary),
        "release_stage_primary": float(release_stage_primary),
        "vocal_stage_overall": vocal_stage_overall,
    }


def _generate_bubble_metrics(settings: dict[str, Any]) -> dict[str, Any]:
    random_state = random.getstate()
    random.seed(1337)
    try:
        sim = BubbleSimulation()
        calm = {"bass": 0.08, "mid": 0.09, "high": 0.05, "overall": 0.08}
        vocal = {"bass": 0.10, "mid": 0.56, "high": 0.36, "overall": 0.39}
        kick = {"bass": 0.82, "mid": 0.10, "high": 0.04, "overall": 0.44}

        calm_settings = dict(settings)
        calm_settings["_event_scheduler"] = _ConsumeScheduler({})
        for _ in range(24):
            sim.tick(0.016, calm, calm_settings)
        calm_speed_energy = sim._smoothed_speed_energy
        calm_burst = sim._stream_burst_envelope

        for _ in range(20):
            sim.tick(0.016, vocal, calm_settings)
        vocal_speed_energy = sim._smoothed_speed_energy
        vocal_burst = sim._stream_burst_envelope
        pos_data, _extra_data, _trail_data = sim.snapshot(
            bass=vocal["bass"],
            mid_high=vocal["mid"] + vocal["high"],
            big_bass_pulse=float(settings.get("bubble_big_bass_pulse", 0.5)),
            small_freq_pulse=float(settings.get("bubble_small_freq_pulse", 0.5)),
            big_specular_max_size=float(settings.get("bubble_big_specular_max_size", 2.5)),
            big_contraction_bias=float(settings.get("bubble_big_contraction_bias", 1.0)),
            big_size_clamp=float(settings.get("bubble_big_size_clamp", 4.0)),
        )
        vocal_max_radius = _max_value(pos_data[2::4])

        beat_sim = BubbleSimulation()
        random.seed(1337)
        beat_settings = dict(settings)
        beat_settings["_event_scheduler"] = _ConsumeScheduler({"kick": [1.0]})
        for _ in range(24):
            beat_sim.tick(0.016, calm, beat_settings)
        beat_sim.tick(0.016, kick, beat_settings)
        beat_pos, _beat_extra, _beat_trail = beat_sim.snapshot(
            bass=kick["bass"],
            mid_high=kick["mid"] + kick["high"],
            big_bass_pulse=float(settings.get("bubble_big_bass_pulse", 0.5)),
            small_freq_pulse=float(settings.get("bubble_small_freq_pulse", 0.5)),
            big_specular_max_size=float(settings.get("bubble_big_specular_max_size", 2.5)),
            big_contraction_bias=float(settings.get("bubble_big_contraction_bias", 1.0)),
            big_size_clamp=float(settings.get("bubble_big_size_clamp", 4.0)),
        )
        kick_max_radius = _max_value(beat_pos[2::4])

        return {
            "preset_name": "Preset 1",
            "calm_speed_energy": float(calm_speed_energy),
            "calm_burst": float(calm_burst),
            "vocal_speed_energy": float(vocal_speed_energy),
            "vocal_burst": float(vocal_burst),
            "vocal_max_radius": float(vocal_max_radius),
            "kick_max_radius": float(kick_max_radius),
        }
    finally:
        random.setstate(random_state)


def generate_preset1_baseline_snapshot() -> dict[str, Any]:
    _ensure_qt_app()
    settings = {mode: get_preset_settings(mode, 0) for mode in PRESET1_MODES}
    snapshot = {
        "schema_version": 1,
        "description": (
            "Deterministic synthetic preset-1 metrics captured before further visualizer refactors. "
            "Use these as a migration guard for preset plumbing and per-mode runtime feel."
        ),
        "modes": {
            "spectrum": _generate_spectrum_metrics(settings["spectrum"]),
            "oscilloscope": _generate_osc_metrics(settings["oscilloscope"]),
            "sine_wave": _generate_sine_metrics(settings["sine_wave"]),
            "blob": _generate_blob_metrics(settings["blob"]),
            "bubble": _generate_bubble_metrics(settings["bubble"]),
        },
    }
    return _round_value(snapshot)


def load_recorded_preset1_baseline() -> dict[str, Any]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def main() -> None:
    print(json.dumps(generate_preset1_baseline_snapshot(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
