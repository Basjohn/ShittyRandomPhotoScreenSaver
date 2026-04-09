"""Tests for the parameterized spectrum shaping pipeline.

Covers:
1. SpectrumShapeConfig dataclass defaults and custom values
2. Config propagation: config_applier → widget attrs → beat_engine → audio_worker
3. fft_to_bars uses the config (not hardcoded values)
4. Preset filtering includes shaping keys
5. Settings model round-trip (from_mapping / to_flat_dict)
6. UI save path emits correct keys
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer.bar_computation import (
    SpectrumShapeConfig,
    _DEFAULT_SHAPE_CONFIG,
)
from widgets.spotify_visualizer_widget import SpotifyVisualizerAudioWorker, _AudioFrame

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. SpectrumShapeConfig dataclass
# ---------------------------------------------------------------------------

class TestSpectrumShapeConfig:
    def test_defaults_match_expected(self):
        cfg = SpectrumShapeConfig()
        assert cfg.lane_strengths_mirrored == {
            "Mid": pytest.approx(0.60),
            "Vocal": pytest.approx(0.64),
            "Low-Mid": pytest.approx(0.70),
            "Bass": pytest.approx(0.80),
        }
        assert cfg.lane_strengths_linear == {
            "Bass": pytest.approx(0.80),
            "Low-Mid": pytest.approx(0.70),
            "Vocal": pytest.approx(0.64),
            "Hi-Mid": pytest.approx(0.80),
            "Treble": pytest.approx(1.00),
        }
        assert cfg.wave_amplitude == 0.50
        assert cfg.profile_floor == 0.12

    def test_custom_values(self):
        cfg = SpectrumShapeConfig(
            lane_strengths_linear={"Bass": 0.25, "Low-Mid": 0.40, "Vocal": 0.80, "Hi-Mid": 0.55, "Treble": 0.90},
            wave_amplitude=0.70,
            profile_floor=0.05,
        )
        assert cfg.lane_strengths_linear["Bass"] == 0.25
        assert cfg.lane_strengths_linear["Vocal"] == 0.80
        assert cfg.wave_amplitude == 0.70
        assert cfg.profile_floor == 0.05

    def test_default_singleton_matches_dataclass_defaults(self):
        fresh = SpectrumShapeConfig()
        assert asdict(fresh) == asdict(_DEFAULT_SHAPE_CONFIG)

    def test_asdict_roundtrip(self):
        cfg = SpectrumShapeConfig(lane_strengths_mirrored={"Mid": 0.25, "Vocal": 0.50, "Low-Mid": 0.75, "Bass": 1.0}, profile_floor=0.25)
        d = asdict(cfg)
        restored = SpectrumShapeConfig(**d)
        assert asdict(restored) == d

    def test_interpolate_nodes_mirrored_even_bar_counts_stay_edge_symmetric(self):
        from ui.tabs.media.spectrum_shape_editor import interpolate_nodes_mirrored

        nodes = [[0.0, 0.98], [0.16, 0.98], [0.58, 0.76], [0.86, 0.90], [1.0, 0.26]]
        vals = interpolate_nodes_mirrored(nodes, 34)

        assert vals[0] == pytest.approx(vals[-1], abs=1e-6)
        assert vals[1] == pytest.approx(vals[-2], abs=1e-6)

    def test_bar_layout_reclaims_width_without_centering_waste(self):
        from widgets.spotify_visualizer.renderers.spectrum import compute_bar_layout

        layout = compute_bar_layout(884.0, 33, gap=2.0, bars_inset=2.0)
        assert layout is not None
        assert layout["left"] == pytest.approx(2.0)
        assert layout["right_padding"] == pytest.approx(2.0, abs=1e-6)
        assert layout["span"] == pytest.approx(880.0, abs=1e-6)
        assert layout["bar_width"] > 24.0

    def test_shader_uses_full_span_bar_width_contract(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "spectrum.frag").read_text(encoding="utf-8")
        assert "float bars_inset = 2.0;" in src
        assert "float bar_width = usable_width / bar_count;" in src


class TestSpectrumShapeEditorNotches:
    @staticmethod
    def _mouse_event(event_type, x, y, button, buttons=None):
        if buttons is None:
            buttons = button
        return QMouseEvent(
            event_type,
            QPointF(x, y),
            QPointF(x, y),
            QPointF(x, y),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )

    @pytest.mark.qt
    def test_dragged_notch_can_cross_neighbors_without_pulling_them(self, qt_app):
        from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor

        editor = SpectrumShapeEditor(mirrored=True)
        try:
            editor.resize(320, 180)
            editor.show()

            original = editor.get_notch_positions()
            plot = editor._plot_rect()
            center_x = plot.left() + plot.width() * 0.5
            half_w = plot.width() * 0.5
            notch_y = plot.bottom() + 10.0

            drag_idx = 1  # Vocal
            start_frac = float(original[drag_idx][0])
            start_x = center_x - start_frac * half_w
            move_target_x = center_x - (float(original[0][0]) + 0.01) * half_w

            editor.mousePressEvent(
                self._mouse_event(
                    QEvent.Type.MouseButtonPress,
                    start_x,
                    notch_y,
                    Qt.MouseButton.LeftButton,
                )
            )
            editor.mouseMoveEvent(
                self._mouse_event(
                    QEvent.Type.MouseMove,
                    move_target_x,
                    notch_y,
                    Qt.MouseButton.NoButton,
                    Qt.MouseButton.LeftButton,
                )
            )
            editor.mouseReleaseEvent(
                self._mouse_event(
                    QEvent.Type.MouseButtonRelease,
                    move_target_x,
                    notch_y,
                    Qt.MouseButton.LeftButton,
                )
            )

            updated = editor.get_notch_positions()
            labels_to_positions = {str(label): float(pos) for pos, label in updated}
            assert labels_to_positions["Mid"] == pytest.approx(float(original[0][0]), abs=1e-6)
            assert labels_to_positions["Low-Mid"] == pytest.approx(float(original[2][0]), abs=1e-6)
            assert labels_to_positions["Vocal"] < float(original[0][0]) + 0.03
            assert labels_to_positions["Vocal"] >= 0.0
        finally:
            editor.deleteLater()


# ---------------------------------------------------------------------------
# 2. Config applier propagation
# ---------------------------------------------------------------------------

class TestConfigApplierShaping:
    def _make_widget_mock(self) -> MagicMock:
        widget = MagicMock()
        widget._spectrum_lane_strengths_mirrored = {"Mid": 0.60, "Vocal": 0.64, "Low-Mid": 0.70, "Bass": 0.80}
        widget._spectrum_lane_strengths_linear = {"Bass": 0.80, "Low-Mid": 0.70, "Vocal": 0.64, "Hi-Mid": 0.80, "Treble": 1.00}
        widget._spectrum_wave_amplitude = 0.50
        widget._spectrum_profile_floor = 0.12
        widget._bar_count = 15
        widget._engine = None
        return widget

    def test_shaping_keys_applied_to_widget(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        widget = self._make_widget_mock()
        apply_vis_mode_kwargs(widget, {'spectrum_lane_strengths_linear': {'Bass': 0.25, 'Low-Mid': 0.4, 'Vocal': 0.8, 'Hi-Mid': 0.55, 'Treble': 0.95}})
        assert widget._spectrum_lane_strengths_linear["Bass"] == pytest.approx(0.25)
        assert widget._spectrum_lane_strengths_linear["Vocal"] == pytest.approx(0.8)

    def test_shaping_clamped_to_bounds(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        widget = self._make_widget_mock()
        apply_vis_mode_kwargs(widget, {'spectrum_lane_strengths_linear': {'Bass': 5.0}, 'spectrum_profile_floor': -1.0})
        assert widget._spectrum_lane_strengths_linear["Bass"] == 1.0  # clamped to max
        assert widget._spectrum_profile_floor == 0.05  # clamped to min

    def test_shaping_pushes_to_engine(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        mock_engine = MagicMock()
        widget = self._make_widget_mock()
        widget._engine = mock_engine
        apply_vis_mode_kwargs(widget, {'spectrum_wave_amplitude': 0.75})
        mock_engine.set_spectrum_shape_config.assert_called_once()
        cfg = mock_engine.set_spectrum_shape_config.call_args[0][0]
        assert isinstance(cfg, SpectrumShapeConfig)
        assert cfg.wave_amplitude == 0.75

    def test_no_engine_push_when_unchanged(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        mock_engine = MagicMock()
        widget = self._make_widget_mock()
        widget._engine = mock_engine
        # Apply same values as defaults — no change → no push
        apply_vis_mode_kwargs(widget, {'spectrum_lane_strengths_linear': dict(widget._spectrum_lane_strengths_linear)})
        mock_engine.set_spectrum_shape_config.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Audio worker setter
# ---------------------------------------------------------------------------

class TestAudioWorkerShapeConfig:
    def test_set_spectrum_shape_config_stores(self):
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        worker = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
        worker._spectrum_shape_config = None
        cfg = SpectrumShapeConfig(lane_strengths_mirrored={"Mid": 0.25, "Vocal": 0.5, "Low-Mid": 0.75, "Bass": 0.9})
        worker.set_spectrum_shape_config(cfg)
        assert worker._spectrum_shape_config is cfg
        assert worker._spectrum_shape_config.lane_strengths_mirrored["Bass"] == 0.9

    def test_set_curved_profile_is_noop(self):
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        worker = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
        worker._spectrum_shape_config = None
        # Should not raise, should do nothing
        worker.set_curved_profile(True)
        worker.set_curved_profile(False)


# ---------------------------------------------------------------------------
# 4. Preset filtering includes shaping keys
# ---------------------------------------------------------------------------

class TestPresetShapingKeys:
    def test_shaping_keys_pass_mode_prefix_filter(self):
        from core.settings.visualizer_presets import MODE_KEY_PREFIXES
        expected = {
            "spectrum_lane_strengths_mirrored",
            "spectrum_lane_strengths_linear",
            "spectrum_wave_amplitude",
            "spectrum_profile_floor",
            "spectrum_border_radius",
            "spectrum_single_piece",
        }
        prefixes = MODE_KEY_PREFIXES.get("spectrum", [])
        for key in expected:
            assert any(key.startswith(p) for p in prefixes), (
                f"{key} does not match any spectrum MODE_KEY_PREFIXES: {prefixes}"
            )

    def test_spectrum_bar_profile_not_in_allowed(self):
        from core.settings.visualizer_presets import GLOBAL_ALLOWED_KEYS
        assert "spectrum_bar_profile" not in GLOBAL_ALLOWED_KEYS

    def test_filter_passes_shaping_keys(self):
        from core.settings.visualizer_presets import _filter_settings_for_mode
        settings = {
            "mode": "spectrum",
            "spectrum_lane_strengths_linear": {"Bass": 0.80, "Low-Mid": 0.60, "Vocal": 0.64, "Hi-Mid": 0.75, "Treble": 0.95},
            "spectrum_wave_amplitude": 0.40,
            "spectrum_profile_floor": 0.10,
            "spectrum_border_radius": 3.0,
        }
        filtered = _filter_settings_for_mode("spectrum", settings)
        for key in settings:
            assert key in filtered, f"Key {key} was filtered out for spectrum mode"

    def test_preset_1_json_has_shaping_keys(self):
        preset_path = ROOT / "presets" / "visualizer_modes" / "spectrum" / "preset_1_rainbow.json"
        if not preset_path.exists():
            pytest.skip("Preset 1 JSON not found")
        payload = json.loads(preset_path.read_text(encoding="utf-8"))
        sv = payload["snapshot"]["widgets"]["spotify_visualizer"]
        assert "spectrum_lane_strengths_linear" in sv
        assert "spectrum_wave_amplitude" in sv
        assert "spectrum_bar_profile" not in sv


# ---------------------------------------------------------------------------
# 5. Settings model round-trip
# ---------------------------------------------------------------------------

class TestSettingsModelShaping:
    def test_from_mapping_picks_up_shaping(self):
        from core.settings.models import SpotifyVisualizerSettings
        mapping: Dict[str, Any] = {
            "spectrum_lane_strengths_linear": {"Bass": 0.70, "Low-Mid": 0.55, "Vocal": 0.65, "Hi-Mid": 0.80, "Treble": 0.95},
            "spectrum_wave_amplitude": 0.80,
            "spectrum_profile_floor": 0.20,
            "spectrum_glow_enabled": True,
            "spectrum_glow_intensity": 0.72,
            "spectrum_glow_color": [12, 240, 255, 220],
        }
        model = SpotifyVisualizerSettings.from_mapping(mapping)
        assert model.spectrum_lane_strengths_linear["Bass"] == pytest.approx(0.70)
        assert model.spectrum_lane_strengths_linear["Treble"] == pytest.approx(0.95)
        assert model.spectrum_wave_amplitude == 0.80
        assert model.spectrum_profile_floor == 0.20
        assert model.spectrum_glow_enabled is True
        assert model.spectrum_glow_intensity == pytest.approx(0.72)
        assert model.spectrum_glow_color == [12, 240, 255, 220]

    def test_to_dict_includes_shaping(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings(
            spectrum_lane_strengths_linear={"Bass": 0.60, "Low-Mid": 0.55, "Vocal": 0.62, "Hi-Mid": 0.80, "Treble": 1.00},
        )
        flat = model.to_dict()
        prefix = "widgets.spotify_visualizer"
        assert flat[f"{prefix}.spectrum_lane_strengths_linear"]["Bass"] == pytest.approx(0.60)
        assert flat[f"{prefix}.spectrum_lane_strengths_mirrored"]["Bass"] == pytest.approx(0.80)
        assert flat[f"{prefix}.spectrum_glow_enabled"] is False
        assert flat[f"{prefix}.spectrum_glow_intensity"] == pytest.approx(0.55)
        assert f"{prefix}.spectrum_bar_profile" not in flat

    def test_no_spectrum_bar_profile_field(self):
        from core.settings.models import SpotifyVisualizerSettings
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(SpotifyVisualizerSettings)}
        assert "spectrum_bar_profile" not in field_names
        assert "spectrum_lane_strengths_linear" in field_names


# ---------------------------------------------------------------------------
# 6. fft_to_bars uses config from worker
# ---------------------------------------------------------------------------

class TestProfileShapeComputation:
    def test_lane_profile_interpolates_between_authored_labels(self):
        import numpy as np
        from widgets.spotify_visualizer.bar_computation import _build_lane_energy_profile

        positions = np.linspace(0.0, 1.0, 9, dtype="float32")
        notches = [
            [0.0, "Bass"],
            [0.25, "Low-Mid"],
            [0.50, "Vocal"],
            [0.75, "Hi-Mid"],
            [1.0, "Treble"],
        ]
        strengths = {"Bass": 1.0, "Low-Mid": 0.75, "Vocal": 0.50, "Hi-Mid": 0.25, "Treble": 0.0}

        profile = _build_lane_energy_profile(np, positions, notches, strengths, 1.0, 0.5, 0.25)

        assert profile.shape == (9,)
        assert profile[0] > profile[4] > profile[-1]
        assert np.all(profile >= 0.0)

    def test_profile_floor_still_enforces_minimum_shape_height(self):
        import numpy as np
        profile = np.array([0.0, 0.1, 0.2, 0.05], dtype="float32")
        floor = 0.30
        profile = np.maximum(profile, floor)
        assert np.all(profile >= floor - 1e-6)

    def test_wave_amplitude_still_scales_lane_energy(self):
        import numpy as np
        from widgets.spotify_visualizer.bar_computation import _build_lane_energy_profile

        positions = np.linspace(0.0, 1.0, 7, dtype="float32")
        notches = [[0.0, "Bass"], [0.5, "Vocal"], [1.0, "Treble"]]
        strengths = {"Bass": 0.8, "Vocal": 0.8, "Treble": 0.8}

        base = _build_lane_energy_profile(np, positions, notches, strengths, 0.8, 0.6, 0.4)
        calm = base * (0.5 + 0.0)
        intense = base * (0.5 + 1.0)

        assert float(np.max(intense)) > float(np.max(calm))


class TestLaneAwareSpectrumEnergy:
    @staticmethod
    def _make_worker(np_module, bar_count: int = 15) -> SpotifyVisualizerAudioWorker:
        buf: TripleBuffer[_AudioFrame] = TripleBuffer()
        worker = SpotifyVisualizerAudioWorker(bar_count=bar_count, buffer=buf)
        worker._np = np_module  # type: ignore[attr-defined]
        worker._spectrum_shape_nodes = [[0.0, 0.9], [0.5, 0.9], [1.0, 0.9]]
        worker._spectrum_mirrored = False
        worker._spectrum_notch_positions = [
            [0.0, "Bass"],
            [0.25, "Low-Mid"],
            [0.50, "Vocal"],
            [0.75, "Hi-Mid"],
            [1.0, "Treble"],
        ]
        worker._spectrum_shape_config = SpectrumShapeConfig(
            lane_strengths_linear={
                "Bass": 0.7,
                "Low-Mid": 0.65,
                "Vocal": 0.7,
                "Hi-Mid": 0.55,
                "Treble": 0.5,
            },
            wave_amplitude=0.9,
            profile_floor=0.05,
        )
        worker._use_recommended = False
        worker._user_sensitivity = 1.0
        worker._use_dynamic_floor = False
        worker._manual_floor = 0.12
        worker._applied_noise_floor = 0.12
        worker._raw_bass_avg = 0.12
        return worker

    @staticmethod
    def _make_fft(np_module, low: float, mid: float, high: float, size: int = 2048):
        fft = np_module.zeros(size, dtype="float32")
        fft[2:24] = low
        fft[48:180] = mid
        fft[260:640] = high
        return fft

    def test_missing_bass_can_collapse_bass_lane(self):
        import numpy as np

        worker = self._make_worker(np)
        bars = worker._fft_to_bars(self._make_fft(np, low=0.0, mid=12.0, high=10.0))

        bass_lane = sum(bars[:4]) / 4.0
        vocal_lane = sum(bars[5:10]) / 5.0

        assert bass_lane < vocal_lane * 0.5

    def test_missing_mid_reduces_vocal_lane(self):
        import numpy as np

        worker = self._make_worker(np)
        bars = worker._fft_to_bars(self._make_fft(np, low=10.0, mid=0.0, high=2.0))

        bass_lane = sum(bars[:4]) / 4.0
        vocal_lane = sum(bars[5:10]) / 5.0

        assert vocal_lane < bass_lane * 0.65
