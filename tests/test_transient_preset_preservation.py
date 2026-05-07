"""Preset preservation tests for Approach A transient bus controls.

Verifies:
  1. New transient keys (kick_lane_gain, transient_pulse_gain, transient_clamp)
     persist through the preset repair tool for all modes.
  2. Default settings include per-mode transient control entries.
  3. Settings model resolve methods return correct defaults.
  4. Technical config cache includes transient keys.
"""
from __future__ import annotations


from core.settings import default_settings
from core.settings.defaults import get_default_settings
from core.settings.models import SpotifyVisualizerSettings
from tools import visualizer_preset_repair as repair


# The three new transient bus keys that must appear per-mode
_TRANSIENT_KEYS = ("kick_lane_gain", "transient_pulse_gain", "transient_clamp")
_MODES = ("spectrum", "bubble", "blob", "sine_wave", "oscilloscope")


class TestDefaultSettingsContainTransientKeys:
    """Verify canonical defaults keep transient controls mode-owned."""

    def test_per_mode_defaults_present(self):
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for mode in _MODES:
            for key in _TRANSIENT_KEYS:
                full_key = f"{mode}_{key}"
                assert full_key in viz, f"Missing default: {full_key}"

    def test_global_defaults_not_present_in_canonical_defaults(self):
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for key in _TRANSIENT_KEYS:
            assert key not in viz, f"Unexpected legacy global default: {key}"

    def test_default_values_sane(self):
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for mode in _MODES:
            assert viz[f"{mode}_kick_lane_gain"] == 1.0
            assert viz[f"{mode}_transient_pulse_gain"] == 1.0
            assert viz[f"{mode}_transient_clamp"] == 1.5


class TestSettingsModelResolvers:
    """Verify SpotifyVisualizerSettings resolve methods for transient keys."""

    def _make_model(self, **overrides) -> SpotifyVisualizerSettings:
        return SpotifyVisualizerSettings(**overrides)

    def test_resolve_kick_lane_gain_default(self):
        model = self._make_model()
        for mode in _MODES:
            val = model.resolve_kick_lane_gain(mode)
            assert val == 1.0, f"{mode}: expected 1.0, got {val}"

    def test_resolve_transient_pulse_gain_default(self):
        model = self._make_model()
        for mode in _MODES:
            val = model.resolve_transient_pulse_gain(mode)
            assert val == 1.0, f"{mode}: expected 1.0, got {val}"

    def test_resolve_transient_clamp_default(self):
        model = self._make_model()
        for mode in _MODES:
            val = model.resolve_transient_clamp(mode)
            assert val == 1.5, f"{mode}: expected 1.5, got {val}"

    def test_resolve_custom_value(self):
        model = self._make_model(spectrum_kick_lane_gain=1.8)
        assert model.resolve_kick_lane_gain("spectrum") == 1.8


class TestPresetRepairAddsTransientKeys:
    """Verify the repair tool injects transient keys into presets."""

    def test_repair_injects_missing_transient_keys(self):
        for mode in _MODES:
            minimal = {
                "snapshot": {
                    "widgets": {
                        "spotify_visualizer": {
                            "mode": mode,
                            f"{mode}_agc_strength": 0.5,
                        }
                    }
                }
            }

            sanitized, _stats = repair._sanitize_settings(mode, minimal)

            for key in _TRANSIENT_KEYS:
                full_key = f"{mode}_{key}"
                assert full_key in sanitized, (
                    f"Repair did not inject {full_key} for mode {mode}"
                )

    def test_repair_preserves_existing_transient_values(self):
        mode = "bubble"
        custom = {
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": {
                        "mode": mode,
                        f"{mode}_kick_lane_gain": 1.5,
                        f"{mode}_transient_pulse_gain": 2.0,
                        f"{mode}_transient_clamp": 2.5,
                    }
                }
            }
        }

        sanitized, _stats = repair._sanitize_settings(mode, custom)

        assert sanitized[f"{mode}_kick_lane_gain"] == 1.5
        assert sanitized[f"{mode}_transient_pulse_gain"] == 2.0
        assert sanitized[f"{mode}_transient_clamp"] == 2.5


class TestMandatoryTechSuffixes:
    """Verify the repair tool's _MANDATORY_TECH_SUFFIXES includes transient keys."""

    def test_transient_keys_in_mandatory_suffixes(self):
        for key in _TRANSIENT_KEYS:
            assert key in repair._MANDATORY_TECH_SUFFIXES, (
                f"{key} not in _MANDATORY_TECH_SUFFIXES"
            )
