"""Focused H5c bars for historical preset/source semantics under Quick ownership."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from rendering.quick.visualizer.implementations.spectrum import (
    prepare_spectrum_shader_levels,
)
from widgets.spotify_visualizer.bar_computation import _apply_adaptive_normalization
from widgets.spotify_visualizer.quick_display_visualizer_owner import (
    QuickDisplayVisualizerOwner,
)
from widgets.spotify_visualizer.quick_technical_config import (
    apply_controller_technical_config,
)
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    SPECTRUM_SHADER_INPUT_SCALE,
)


class _SpectrumConfigEngine:
    def __init__(self) -> None:
        self.mirrored = None
        self.shape_nodes = None
        self.notches = None
        self.shape_config = None
        self.drop_speed = None

    def set_spectrum_mirrored(self, value: bool) -> None:
        self.mirrored = bool(value)

    def set_spectrum_shape_nodes(self, value: list) -> None:
        self.shape_nodes = list(value)

    def set_notch_positions(self, value: list) -> None:
        self.notches = list(value)

    def set_spectrum_shape_config(self, value) -> None:
        self.shape_config = value

    def set_drop_speed(self, value: float) -> None:
        self.drop_speed = float(value)


_SPECTRUM_CANONICAL_CONFIG = {
    "spectrum_render_mode": "bars",
    "spectrum_unique_colors": True,
    "spectrum_mirrored": False,
    "spectrum_shape_nodes": [[0.0, 0.21], [0.5, 0.88], [1.0, 0.44]],
    "spectrum_notch_positions_mirrored": [
        [0.0, "Mid"],
        [0.4, "Vocal"],
        [1.0, "Bass"],
    ],
    "spectrum_notch_positions_linear": [
        [0.0, "Bass"],
        [0.3, "Low-Mid"],
        [0.6, "Vocal"],
        [1.0, "Treble"],
    ],
    "spectrum_lane_strengths_mirrored": {
        "Mid": 0.11,
        "Vocal": 0.22,
        "Low-Mid": 0.33,
        "Bass": 0.44,
    },
    "spectrum_lane_strengths_linear": {
        "Bass": 0.15,
        "Low-Mid": 0.25,
        "Vocal": 0.35,
        "Hi-Mid": 0.45,
        "Treble": 0.55,
    },
    "spectrum_wave_amplitude": 0.73,
    "spectrum_profile_floor": 0.19,
    "spectrum_drop_speed": 2.4,
}


def _owner(engine: _SpectrumConfigEngine, *, mode: str = "spectrum"):
    runtime = SimpleNamespace(runtime_generation=17)
    return QuickDisplayVisualizerOwner(
        runtime,
        bar_count=33,
        initial_mode=mode,
        engine_factory=lambda _bar_count: engine,
    )


def test_quick_owner_routes_canonical_spectrum_preset_to_all_three_owners() -> None:
    """Historical creator translations + engine side effects survive sans QWidget."""

    engine = _SpectrumConfigEngine()
    owner = _owner(engine)
    owner.configure(
        logical_kwargs=_SPECTRUM_CANONICAL_CONFIG,
        presentation_kwargs=_SPECTRUM_CANONICAL_CONFIG,
        playing=True,
    )

    state = owner.controller.logical_tick_state
    presentation = owner.controller.presentation_state

    # Historical creator: spectrum_render_mode="bars" -> single-piece runtime.
    assert state._spectrum_single_piece is True
    # Historical creator: spectrum_unique_colors -> per-bar rainbow topology.
    assert presentation._rainbow_per_bar is True

    # Historical mixed applier's source-owned side effects now reach the one
    # controller-owned BeatEngine directly.
    assert engine.mirrored is False
    assert engine.shape_nodes == _SPECTRUM_CANONICAL_CONFIG["spectrum_shape_nodes"]
    assert engine.notches == _SPECTRUM_CANONICAL_CONFIG["spectrum_notch_positions_linear"]
    assert engine.drop_speed == pytest.approx(2.4)
    assert engine.shape_config.wave_amplitude == pytest.approx(0.73)
    assert engine.shape_config.profile_floor == pytest.approx(0.19)
    assert dict(engine.shape_config.lane_strengths_mirrored) == {
        "Mid": pytest.approx(0.11),
        "Vocal": pytest.approx(0.22),
        "Low-Mid": pytest.approx(0.33),
        "Bass": pytest.approx(0.44),
    }
    assert dict(engine.shape_config.lane_strengths_linear) == {
        "Bass": pytest.approx(0.15),
        "Low-Mid": pytest.approx(0.25),
        "Vocal": pytest.approx(0.35),
        "Hi-Mid": pytest.approx(0.45),
        "Treble": pytest.approx(0.55),
    }


def test_spectrum_source_contract_is_applied_even_when_active_mode_is_bubble() -> None:
    """Historical full-model apply configured the shared FFT worker for every mode."""

    engine = _SpectrumConfigEngine()
    owner = _owner(engine, mode="bubble")
    owner.configure(
        logical_kwargs=_SPECTRUM_CANONICAL_CONFIG,
        playing=True,
    )

    # These notches feed the shared pre-mode bass/mid/high split in fft_to_bars,
    # so losing them can alter Bubble/Oscillo/Sine/DevCurve reactivity too.
    assert engine.mirrored is False
    assert engine.notches == _SPECTRUM_CANONICAL_CONFIG["spectrum_notch_positions_linear"]
    assert engine.shape_config.wave_amplitude == pytest.approx(0.73)


def test_quick_logical_owner_restores_stranded_bubble_preset_controls() -> None:
    engine = _SpectrumConfigEngine()
    owner = _owner(engine, mode="bubble")
    owner.configure(
        logical_kwargs={
            "bubble_group_drift": True,
            "bubble_collision_pop_mode": "one",
            "bubble_big_visual_smoothing": 0.93,
        },
        playing=True,
    )

    state = owner.controller.logical_tick_state
    assert state._bubble_group_drift is True
    assert state._bubble_collision_pop_mode == "one"
    assert state._bubble_big_visual_smoothing == pytest.approx(0.93)


def test_canonical_spectrum_render_mode_has_priority_over_legacy_boolean() -> None:
    engine = _SpectrumConfigEngine()
    owner = _owner(engine)
    owner.configure(
        logical_kwargs={
            "spectrum_render_mode": "segment",
            "spectrum_single_piece": True,
        },
        playing=False,
    )
    assert owner.controller.logical_tick_state._spectrum_single_piece is False


def test_quick_spectrum_shader_upload_preserves_historical_055_transfer() -> None:
    bars, peaks = prepare_spectrum_shader_levels(
        [1.0, 0.5, 0.25],
        [0.8],
        bar_count=3,
    )

    assert SPECTRUM_SHADER_INPUT_SCALE == pytest.approx(0.55)
    assert bars[:3] == pytest.approx([0.55, 0.275, 0.1375])
    # Missing peak entries inherit the authored bar before the historical scale.
    assert peaks[:3] == pytest.approx([0.44, 0.275, 0.1375])
    assert len(bars) == 64
    assert len(peaks) == 64
    assert bars[3:] == pytest.approx([0.0] * 61)
    assert peaks[3:] == pytest.approx([0.0] * 61)


def test_agc_zero_preserves_raw_output_contract() -> None:
    """BeatEngine AGC zero must remain a real bypass, not a default/falsy alias."""

    worker = SimpleNamespace(_agc_strength=0.0)
    bars = [0.12, 0.54, 0.91]
    before = list(bars)

    _apply_adaptive_normalization(
        worker,
        bars,
        drop_signal=0.0,
        low_resolution=False,
        np=None,
    )

    assert bars == before
    assert not hasattr(worker, "_env_bass_short")
    assert not hasattr(worker, "_env_mix_short")


class _TechnicalWorker:
    def __init__(self) -> None:
        self.block_size = None
        self._kick_lane_gain = None
        self._spectrum_lane_transient_mix = None

    def set_audio_block_size(self, value: int) -> None:
        self.block_size = int(value)


class _TechnicalEngine:
    def __init__(self) -> None:
        self._audio_worker = _TechnicalWorker()
        self.reconfigured_bar_count = None
        self.floor = None
        self.sensitivity = None
        self.energy_boost = None
        self.agc_strength = None
        self.input_gain = None

    def reconfigure_bar_count(self, value: int) -> None:
        self.reconfigured_bar_count = int(value)

    def set_floor_config(self, dynamic: bool, manual: float) -> None:
        self.floor = (bool(dynamic), float(manual))

    def set_sensitivity_config(self, adaptive: bool, value: float) -> None:
        self.sensitivity = (bool(adaptive), float(value))

    def set_energy_boost(self, value: float) -> None:
        self.energy_boost = float(value)

    def set_agc_strength(self, value: float) -> None:
        self.agc_strength = float(value)

    def set_input_gain(self, value: float) -> None:
        self.input_gain = float(value)


class _TechnicalController:
    def __init__(self) -> None:
        self.bar_count = 32
        self.logical_tick_state = SimpleNamespace()
        self.engine = _TechnicalEngine()

    def ensure_engine(self):
        return self.engine


def test_quick_technical_config_preserves_reactivity_critical_zero_and_false_values() -> None:
    """The migrated technical subset must preserve preset semantics exactly.

    In particular, ``agc_strength=0.0`` is an intentional "no AGC" setting;
    treating it as missing/default would radically alter several curated
    presets.  Dynamic-floor False, explicit capture block size and per-mode bar
    count are similarly behavior-defining rather than cosmetic.
    """

    controller = _TechnicalController()
    apply_controller_technical_config(
        controller,
        {
            "bar_count": 48,
            "dynamic_floor": False,
            "manual_floor": 0.30,
            "adaptive_sensitivity": False,
            "sensitivity": 0.55,
            "audio_block_size": 128,
            "dynamic_range_enabled": False,
            "agc_strength": 0.0,
            "input_gain": 0.75,
            "kick_lane_gain": 1.0,
            "transient_pulse_gain": 0.05,
            "transient_clamp": 1.15,
            "bubble_transient_mix_bass": 0.20,
            "bubble_transient_mix_vocal": 0.15,
        },
        reason="test_bubble_preset_contract",
    )

    engine = controller.engine
    state = controller.logical_tick_state
    assert controller.bar_count == 48
    assert engine.reconfigured_bar_count == 48
    assert engine.floor is not None
    assert engine.floor[0] is False
    assert engine.floor[1] == pytest.approx(0.30)
    assert engine.sensitivity is not None
    assert engine.sensitivity[0] is False
    assert engine.sensitivity[1] == pytest.approx(0.55)
    assert engine._audio_worker.block_size == 128
    assert engine.energy_boost == pytest.approx(0.85)
    assert engine.agc_strength == pytest.approx(0.0)
    assert engine.input_gain == pytest.approx(0.75)
    assert engine._audio_worker._kick_lane_gain == pytest.approx(1.0)
    assert state._transient_pulse_gain == pytest.approx(0.05)
    assert state._transient_clamp == pytest.approx(1.15)
    assert state._bubble_transient_mix_bass == pytest.approx(0.20)
    assert state._bubble_transient_mix_vocal == pytest.approx(0.15)

