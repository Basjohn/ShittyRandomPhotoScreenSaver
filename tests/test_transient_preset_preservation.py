"""Preset preservation tests for Approach A transient bus controls.

Verifies:
  1. New transient keys (kick_lane_gain, transient_pulse_gain, transient_clamp)
     persist through preset repair when each mode declares their ownership.
  2. Default settings include per-mode transient control entries.
  3. Settings model resolve methods return correct defaults.
  4. Technical config cache includes transient keys.
"""
from __future__ import annotations


from core.settings.defaults import get_default_settings
from core.settings.models import PER_MODE_TECHNICAL_MODES, SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
from tools import visualizer_preset_repair as repair


# Transient controls are mode-owned only when their capability descriptors
# include the corresponding key. Sphere owns transient_clamp but deliberately
# does not persist kick_lane_gain or transient_pulse_gain.
_TRANSIENT_KEYS = ("kick_lane_gain", "transient_pulse_gain", "transient_clamp")
_MODES = PER_MODE_TECHNICAL_MODES


def _owned_transients(mode):
    owned = get_owned_mode_setting_keys(mode, "technical")
    return {key: owned[key] for key in _TRANSIENT_KEYS if key in owned}


class TestDefaultSettingsContainTransientKeys:
    """Verify canonical defaults keep transient controls mode-owned."""

    def test_per_mode_defaults_present(self):
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for mode in _MODES:
            owned = _owned_transients(mode)
            for suffix in _TRANSIENT_KEYS:
                full_key = f"{mode}_{suffix}"
                assert (full_key in viz) == (suffix in owned), (
                    f"Incorrect canonical ownership: {full_key}"
                )

    def test_global_defaults_not_present_in_canonical_defaults(self):
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for key in _TRANSIENT_KEYS:
            assert key not in viz, f"Unexpected legacy global default: {key}"

    def test_default_values_sane(self):
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for mode in _MODES:
            for suffix, full_key in _owned_transients(mode).items():
                value = viz[full_key]
                assert isinstance(value, (int, float))
                assert value > 0.0 if suffix == "transient_clamp" else value >= 0.0


class TestSettingsModelResolvers:
    """Verify SpotifyVisualizerSettings resolve methods for transient keys."""

    def _make_model(self, **overrides) -> SpotifyVisualizerSettings:
        return SpotifyVisualizerSettings(**overrides)

    def test_resolve_kick_lane_gain_default(self):
        # A default model resolves each mode's canonical per-mode value (these
        # legitimately differ per mode; there is no uniform gain default).
        model = self._make_model()
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for mode in _MODES:
            key = _owned_transients(mode).get("kick_lane_gain")
            expected = viz[key] if key is not None else viz["spectrum_kick_lane_gain"]
            assert model.resolve_kick_lane_gain(mode) == expected, mode

    def test_resolve_transient_pulse_gain_default(self):
        model = self._make_model()
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for mode in _MODES:
            key = _owned_transients(mode).get("transient_pulse_gain")
            expected = viz[key] if key is not None else viz["spectrum_transient_pulse_gain"]
            assert model.resolve_transient_pulse_gain(mode) == expected, mode

    def test_resolve_transient_clamp_default(self):
        model = self._make_model()
        viz = get_default_settings()["widgets"]["spotify_visualizer"]
        for mode in _MODES:
            key = _owned_transients(mode).get("transient_clamp")
            if key is not None:
                val = model.resolve_transient_clamp(mode)
                assert val == viz[key], f"{mode}: got {val}"

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

            for suffix in _TRANSIENT_KEYS:
                full_key = f"{mode}_{suffix}"
                assert (full_key in sanitized) == (suffix in _owned_transients(mode)), (
                    f"Repair produced incorrect transient ownership for {full_key}"
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
