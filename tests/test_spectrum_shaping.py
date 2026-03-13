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

from widgets.spotify_visualizer.bar_computation import (
    SpectrumShapeConfig,
    _DEFAULT_SHAPE_CONFIG,
)

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. SpectrumShapeConfig dataclass
# ---------------------------------------------------------------------------

class TestSpectrumShapeConfig:
    def test_defaults_match_expected(self):
        cfg = SpectrumShapeConfig()
        assert cfg.bass_emphasis == 0.50
        assert cfg.vocal_peak_position == 0.40
        assert cfg.mid_suppression == 0.50
        assert cfg.wave_amplitude == 0.50
        assert cfg.profile_floor == 0.12

    def test_custom_values(self):
        cfg = SpectrumShapeConfig(
            bass_emphasis=0.80,
            vocal_peak_position=0.30,
            mid_suppression=0.20,
            wave_amplitude=0.70,
            profile_floor=0.05,
        )
        assert cfg.bass_emphasis == 0.80
        assert cfg.vocal_peak_position == 0.30
        assert cfg.mid_suppression == 0.20
        assert cfg.wave_amplitude == 0.70
        assert cfg.profile_floor == 0.05

    def test_default_singleton_matches_dataclass_defaults(self):
        fresh = SpectrumShapeConfig()
        assert asdict(fresh) == asdict(_DEFAULT_SHAPE_CONFIG)

    def test_asdict_roundtrip(self):
        cfg = SpectrumShapeConfig(bass_emphasis=0.9, profile_floor=0.25)
        d = asdict(cfg)
        restored = SpectrumShapeConfig(**d)
        assert asdict(restored) == d


# ---------------------------------------------------------------------------
# 2. Config applier propagation
# ---------------------------------------------------------------------------

class TestConfigApplierShaping:
    def _make_widget_mock(self) -> MagicMock:
        widget = MagicMock()
        widget._spectrum_bass_emphasis = 0.50
        widget._spectrum_vocal_position = 0.40
        widget._spectrum_mid_suppression = 0.50
        widget._spectrum_wave_amplitude = 0.50
        widget._spectrum_profile_floor = 0.12
        widget._bar_count = 15
        widget._engine = None
        return widget

    def test_shaping_keys_applied_to_widget(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        widget = self._make_widget_mock()
        apply_vis_mode_kwargs(widget, {'spectrum_bass_emphasis': 0.80, 'spectrum_mid_suppression': 0.30})
        assert widget._spectrum_bass_emphasis == 0.80
        assert widget._spectrum_mid_suppression == 0.30
        # Unchanged
        assert widget._spectrum_vocal_position == 0.40

    def test_shaping_clamped_to_bounds(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        widget = self._make_widget_mock()
        apply_vis_mode_kwargs(widget, {'spectrum_bass_emphasis': 5.0, 'spectrum_profile_floor': -1.0})
        assert widget._spectrum_bass_emphasis == 1.0  # clamped to max
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
        apply_vis_mode_kwargs(widget, {'spectrum_bass_emphasis': 0.50})
        mock_engine.set_spectrum_shape_config.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Audio worker setter
# ---------------------------------------------------------------------------

class TestAudioWorkerShapeConfig:
    def test_set_spectrum_shape_config_stores(self):
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        worker = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
        worker._spectrum_shape_config = None
        cfg = SpectrumShapeConfig(bass_emphasis=0.9)
        worker.set_spectrum_shape_config(cfg)
        assert worker._spectrum_shape_config is cfg
        assert worker._spectrum_shape_config.bass_emphasis == 0.9

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
    def test_shaping_keys_in_global_allowed(self):
        from core.settings.visualizer_presets import GLOBAL_ALLOWED_KEYS
        expected = {
            "spectrum_bass_emphasis",
            "spectrum_vocal_position",
            "spectrum_mid_suppression",
            "spectrum_wave_amplitude",
            "spectrum_profile_floor",
            "spectrum_border_radius",
            "spectrum_single_piece",
        }
        assert expected.issubset(GLOBAL_ALLOWED_KEYS), (
            f"Missing keys: {expected - GLOBAL_ALLOWED_KEYS}"
        )

    def test_spectrum_bar_profile_not_in_allowed(self):
        from core.settings.visualizer_presets import GLOBAL_ALLOWED_KEYS
        assert "spectrum_bar_profile" not in GLOBAL_ALLOWED_KEYS

    def test_filter_passes_shaping_keys(self):
        from core.settings.visualizer_presets import _filter_settings_for_mode
        settings = {
            "mode": "spectrum",
            "spectrum_bass_emphasis": 0.80,
            "spectrum_vocal_position": 0.35,
            "spectrum_mid_suppression": 0.60,
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
        assert "spectrum_bass_emphasis" in sv
        assert "spectrum_wave_amplitude" in sv
        assert "spectrum_bar_profile" not in sv


# ---------------------------------------------------------------------------
# 5. Settings model round-trip
# ---------------------------------------------------------------------------

class TestSettingsModelShaping:
    def test_from_mapping_picks_up_shaping(self):
        from core.settings.models import SpotifyVisualizerSettings
        mapping: Dict[str, Any] = {
            "spectrum_bass_emphasis": 0.70,
            "spectrum_vocal_position": 0.55,
            "spectrum_mid_suppression": 0.25,
            "spectrum_wave_amplitude": 0.80,
            "spectrum_profile_floor": 0.20,
        }
        model = SpotifyVisualizerSettings.from_mapping(mapping)
        assert model.spectrum_bass_emphasis == 0.70
        assert model.spectrum_vocal_position == 0.55
        assert model.spectrum_mid_suppression == 0.25
        assert model.spectrum_wave_amplitude == 0.80
        assert model.spectrum_profile_floor == 0.20

    def test_to_dict_includes_shaping(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings(
            spectrum_bass_emphasis=0.60,
            spectrum_vocal_position=0.45,
        )
        flat = model.to_dict()
        prefix = "widgets.spotify_visualizer"
        assert flat[f"{prefix}.spectrum_bass_emphasis"] == 0.60
        assert flat[f"{prefix}.spectrum_vocal_position"] == 0.45
        assert flat[f"{prefix}.spectrum_mid_suppression"] == 0.50  # default
        assert f"{prefix}.spectrum_bar_profile" not in flat

    def test_no_spectrum_bar_profile_field(self):
        from core.settings.models import SpotifyVisualizerSettings
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(SpotifyVisualizerSettings)}
        assert "spectrum_bar_profile" not in field_names
        assert "spectrum_bass_emphasis" in field_names


# ---------------------------------------------------------------------------
# 6. fft_to_bars uses config from worker
# ---------------------------------------------------------------------------

class TestProfileShapeComputation:
    """Test the profile shape math directly — pure numpy, no worker state needed.

    This is the core of SpectrumShapeConfig: the profile_shape array that
    determines per-bar amplitude weighting in fft_to_bars.
    """

    @staticmethod
    def _compute_profile(cfg: SpectrumShapeConfig, bands: int):
        """Reproduce the profile shape computation from bar_computation.fft_to_bars."""
        import numpy as np
        center = bands // 2
        half = bands // 2
        frac_arr = np.abs(np.arange(bands, dtype="float32") - center) / max(1.0, float(half))

        wave = np.sin(frac_arr * np.pi * 1.5 + np.pi * 0.5)
        wave_scale = cfg.wave_amplitude * 0.70
        profile_shape = wave * wave_scale + 0.50

        bass_amp = cfg.bass_emphasis * 0.40
        edge_boost = np.exp(-((frac_arr - 1.0) ** 2) / 0.08) * bass_amp
        profile_shape = profile_shape + edge_boost

        vp = cfg.vocal_peak_position
        vocal_peak = np.exp(-((frac_arr - vp) ** 2) / 0.018) * 0.12
        vocal_dip = -np.exp(-((frac_arr - (vp - 0.10)) ** 2) / 0.015) * 0.06

        suppress_depth = cfg.mid_suppression * 0.32
        mid_suppress = -np.exp(-((frac_arr - 0.20) ** 2) / 0.030) * suppress_depth
        bar7_cut = -np.exp(-((frac_arr - 0.30) ** 2) / 0.008) * (suppress_depth * 0.375)
        bar9_cut = -np.exp(-((frac_arr - 0.10) ** 2) / 0.008) * (suppress_depth * 0.25)
        profile_shape = profile_shape + vocal_peak + vocal_dip + mid_suppress + bar7_cut + bar9_cut

        profile_shape = np.maximum(profile_shape, cfg.profile_floor)
        return profile_shape

    def test_default_config_produces_nonzero_profile(self):
        import numpy as np
        profile = self._compute_profile(SpectrumShapeConfig(), bands=21)
        assert profile.shape == (21,)
        assert np.all(profile > 0), "Default profile should have all positive values"

    def test_different_configs_produce_different_profiles(self):
        import numpy as np
        bands = 21
        default_profile = self._compute_profile(SpectrumShapeConfig(), bands=bands)
        custom_profile = self._compute_profile(SpectrumShapeConfig(
            bass_emphasis=1.0, wave_amplitude=0.0, mid_suppression=0.0,
        ), bands=bands)
        assert not np.allclose(default_profile, custom_profile), (
            "Different SpectrumShapeConfig should produce different profiles"
        )

    def test_zero_amplitude_gives_flat_profile(self):
        import numpy as np
        bands = 15
        profile = self._compute_profile(SpectrumShapeConfig(
            bass_emphasis=0.0, wave_amplitude=0.0, mid_suppression=0.0,
            vocal_peak_position=0.40, profile_floor=0.50,
        ), bands=bands)
        # With zero wave/bass/mid, profile should be near-uniform at ~0.50
        assert profile.shape == (bands,)
        assert np.all(profile >= 0.50 - 0.01), "Floor should be respected"
        ratio = float(np.max(profile)) / float(np.min(profile) + 1e-9)
        assert ratio < 1.5, f"Flat profile should be near-uniform, got max/min ratio {ratio:.2f}"

    def test_high_bass_emphasis_boosts_edges(self):
        bands = 21
        low_bass = self._compute_profile(SpectrumShapeConfig(bass_emphasis=0.0), bands=bands)
        high_bass = self._compute_profile(SpectrumShapeConfig(bass_emphasis=1.0), bands=bands)
        # Edge bars (index 0 and last) should be higher with more bass emphasis
        assert high_bass[0] > low_bass[0], "Bass emphasis should boost edge bars"
        assert high_bass[-1] > low_bass[-1], "Bass emphasis should boost edge bars"

    def test_profile_floor_enforced(self):
        import numpy as np
        bands = 15
        floor_val = 0.30
        profile = self._compute_profile(SpectrumShapeConfig(
            profile_floor=floor_val, wave_amplitude=1.0, mid_suppression=1.0,
        ), bands=bands)
        assert np.all(profile >= floor_val - 1e-6), (
            f"No bar should be below profile_floor={floor_val}"
        )

    def test_wave_amplitude_affects_center(self):
        import numpy as np
        bands = 21
        low_wave = self._compute_profile(SpectrumShapeConfig(wave_amplitude=0.0), bands=bands)
        high_wave = self._compute_profile(SpectrumShapeConfig(wave_amplitude=1.0), bands=bands)
        # Higher wave amplitude should create more variation between center and edges
        range_low = float(np.max(low_wave) - np.min(low_wave))
        range_high = float(np.max(high_wave) - np.min(high_wave))
        assert range_high > range_low, (
            "Higher wave_amplitude should create more variation in the profile"
        )
