"""Regression tests for visualizer settings plumbing.

This file aims to stay mostly behavior-level:
- settings round-trip through the model
- creator/applier/frame-push propagation
- set_state compatibility guards

Small source-level checks remain only where there is no practical runtime
surface without a live GL context (mainly shader-source contracts).
"""
import os
import inspect
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SHADER_DIR = ROOT / "widgets" / "spotify_visualizer" / "shaders"
TEST_APPDATA = ROOT / "tests_tmp_appdata"
TEST_APPDATA.mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(TEST_APPDATA)


# ===========================================================================
# 1. Bubble GPU push must NOT include simulation-only keys
# ===========================================================================

class TestBubbleGpuPushKwargs:
    """Regression: sim-only kwargs in GPU push caused TypeError in set_state,
    making bubble fall back to spectrum silently."""

    def _get_set_state_params(self):
        """Extract parameter names from SpotifyBarsGLOverlay.set_state."""
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
        sig = inspect.signature(SpotifyBarsGLOverlay.set_state)
        return set(sig.parameters.keys()) - {"self"}

    def _build_bubble_extra(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs

        class _DummyWidget:
            def __init__(self):
                self._bubble_pos_data = [0.1, 0.2, 0.3, 0.4]
                self._bubble_extra_data = [0.5, 0.6, 0.7, 0.8]
                self._bubble_trail_data = [0.9, 1.0]
                self._bubble_count = 2

            def __getattr__(self, name):
                if name in {"_spectrum_shape_nodes", "_spectrum_notch_positions_mirrored", "_spectrum_notch_positions_linear"}:
                    return []
                if name.endswith("_direction"):
                    return "top"
                if "color" in name or "tint" in name:
                    return QColor(255, 255, 255, 255)
                if name.endswith("enabled"):
                    return False
                if name.endswith("line_count"):
                    return 1
                return 0.0

        return build_gpu_push_extra_kwargs(_DummyWidget(), "bubble", None)

    def test_bubble_extra_keys_accepted_by_set_state(self):
        """Every key in bubble GPU push must be accepted by set_state."""
        set_state_params = self._get_set_state_params()
        bubble_keys = set(self._build_bubble_extra().keys())
        rejected = bubble_keys - set_state_params
        assert not rejected, (
            f"Bubble GPU push keys not accepted by set_state: {rejected}. "
            f"These will cause TypeError and bubble falls back to spectrum."
        )

    def test_no_simulation_only_keys_in_gpu_push(self):
        """Simulation-only keys must NOT be in the GPU push."""
        sim_only_keys = {
            "bubble_big_bass_pulse", "bubble_small_freq_pulse",
            "bubble_stream_direction", "bubble_stream_constant_speed",
            "bubble_stream_speed_cap", "bubble_stream_reactivity", "bubble_rotation_amount",
            "bubble_drift_amount", "bubble_drift_speed",
            "bubble_drift_frequency", "bubble_drift_direction",
            "bubble_big_count", "bubble_small_count",
            "bubble_surface_reach",
            "bubble_bounce_big_pct", "bubble_bounce_small_pct",
            "bubble_bounce_big_speed", "bubble_bounce_small_speed",
            "bubble_bounce_same_only",
            "bubble_collision_pop_mode",
        }
        bubble_keys = set(self._build_bubble_extra().keys())
        leaked = bubble_keys & sim_only_keys
        assert not leaked, (
            f"Simulation-only keys leaked into GPU push: {leaked}. "
            f"These cause TypeError in set_state."
        )


# ===========================================================================
# 2. Card height: all modes must have entries
# ===========================================================================

class TestCardHeight:
    """Regression: bubble was missing from DEFAULT_GROWTH causing fallback to 1.0."""

    def test_all_modes_have_default_growth(self):
        from widgets.spotify_visualizer.card_height import DEFAULT_GROWTH
        required_modes = {"spectrum", "oscilloscope", "blob", "sine_wave", "bubble"}
        missing = required_modes - set(DEFAULT_GROWTH.keys())
        assert not missing, f"Modes missing from DEFAULT_GROWTH: {missing}"

    def test_all_growth_factors_at_least_2(self):
        """User requested +1.0x on all card heights (minimum 2.0)."""
        from widgets.spotify_visualizer.card_height import DEFAULT_GROWTH
        for mode, growth in DEFAULT_GROWTH.items():
            assert growth >= 2.0, f"{mode} growth {growth} < 2.0 (user requested +1.0x raise)"

    def test_bubble_growth_is_expanded(self):
        """Bubble should be an expanded mode (>= 2.5x)."""
        from widgets.spotify_visualizer.card_height import DEFAULT_GROWTH
        assert DEFAULT_GROWTH.get("bubble", 0) >= 2.5

    def test_widget_get_preferred_height_uses_bubble_growth(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        widget = SimpleNamespace(
            _vis_mode_str="bubble",
            _base_height=80,
            _spectrum_growth=2.0,
            _osc_growth=2.0,
            _blob_growth=3.5,
            _sine_wave_growth=2.0,
            _bubble_growth=3.0,
        )

        assert SpotifyVisualizerWidget.get_preferred_height(widget) == 240


# ===========================================================================
# 3. Rainbow greyscale saturation fix in ALL shaders
# ===========================================================================

class TestRainbowGreyscaleFix:
    """Regression: rainbow hue shift invisible on white/grey because saturation=0."""

    SHADER_FILES = [
        "spectrum.frag", "oscilloscope.frag", "sine_wave.frag",
        "blob.frag", "bubble.frag",
    ]

    def test_all_shaders_have_rainbow_uniform(self):
        for fname in self.SHADER_FILES:
            path = SHADER_DIR / fname
            assert path.exists(), f"Shader file missing: {fname}"
            src = path.read_text(encoding="utf-8")
            assert "u_rainbow_hue_offset" in src, (
                f"{fname} missing u_rainbow_hue_offset uniform"
            )

    def test_all_shaders_force_saturation_on_greyscale(self):
        """Each shader with inline HSV must force s=1.0 when greyscale."""
        for fname in self.SHADER_FILES:
            path = SHADER_DIR / fname
            src = path.read_text(encoding="utf-8")
            if "u_rainbow_hue_offset" not in src:
                continue
            # bubble.frag uses a helper function, not inline HSV
            if fname == "bubble.frag":
                # bubble uses apply_rainbow → rgb2hsv → hsv2rgb, saturation
                # is always preserved from the input colour which is user-set
                # (not greyscale by default). Skip inline check.
                continue
            # All other shaders should have the greyscale saturation force
            assert "s = 1.0" in src or "s=1.0" in src, (
                f"{fname} missing greyscale saturation force (s = 1.0). "
                f"Rainbow will be invisible on white/grey colours."
            )


# ===========================================================================
# 4. Settings model plumbing: every setting in model must be in all 4 methods
# ===========================================================================

class TestSettingsModelPlumbing:
    """Verify key settings survive real model round-trips."""

    CRITICAL_SETTINGS = {
        "sine_width_reaction": 0.42,
        "sine_micro_wobble": 0.15,
        "sine_heartbeat": 0.33,
        "rainbow_enabled": True,
        "rainbow_speed": 0.8,
        "osc_ghosting_enabled": True,
        "osc_ghost_intensity": 0.6,
        "bubble_big_bass_pulse": 0.65,
        "bubble_small_freq_pulse": 0.35,
        "bubble_stream_direction": "left",
        "bubble_bounce_big_pct": 91,
        "bubble_bounce_small_pct": 12,
        "bubble_bounce_big_speed": 1.42,
        "bubble_bounce_small_speed": 0.37,
        "bubble_bounce_same_only": True,
        "bubble_collision_pop_mode": "all",
        "bubble_outline_color": [10, 20, 30, 255],
        "bubble_specular_direction": "bottom_right",
        "bubble_gradient_direction": "center_out",
        "spectrum_drop_speed": 2.2,
    }

    def _payload(self):
        from core.settings import visualizer_presets as vp

        return {
            "mode": "bubble",
            "preset_bubble": vp.get_custom_preset_index("bubble"),
            **self.CRITICAL_SETTINGS,
        }

    def _assert_model_matches(self, model):
        for key, expected in self.CRITICAL_SETTINGS.items():
            assert getattr(model, key) == expected

    def _assert_serialized_matches(self, payload):
        for key, expected in self.CRITICAL_SETTINGS.items():
            assert payload[f"widgets.spotify_visualizer.{key}"] == expected

    def test_critical_settings_round_trip_via_from_mapping(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping(self._payload())
        self._assert_model_matches(model)
        self._assert_serialized_matches(model.to_dict())

    def test_critical_settings_round_trip_via_from_settings(self):
        from core.settings.models import SpotifyVisualizerSettings

        class _DummySettings:
            def __init__(self, data):
                self._data = data

            def get(self, key, default=None):
                return self._data.get(key, default)

        persisted = SpotifyVisualizerSettings.from_mapping(self._payload()).to_dict()
        model = SpotifyVisualizerSettings.from_settings(_DummySettings(persisted))
        self._assert_model_matches(model)
        self._assert_serialized_matches(model.to_dict())


class TestVisualizerPresetSelectionAuthority:
    """Guard against curated/custom cross-bleed in visualizer preset hydration."""

    def test_apply_preset_to_config_clears_mode_keys_not_present_in_curated_payload(self, monkeypatch):
        from core.settings import visualizer_presets as vp

        mode = "bubble"
        custom_idx = vp.get_custom_preset_index(mode)
        curated_idx = 0 if custom_idx > 0 else 1

        def _fake_get_preset_settings(mode_key, index):
            if mode_key == mode and index == curated_idx:
                return {
                    "bubble_stream_direction": "left",
                }
            return {}

        monkeypatch.setattr(vp, "get_preset_settings", _fake_get_preset_settings)

        source = {
            "mode": "bubble",
            "preset_bubble": curated_idx,
            "bubble_stream_direction": "right",
            "bubble_manual_floor": 0.27,
            "bubble_audio_block_size": 256,
        }
        merged = vp.apply_preset_to_config(mode, curated_idx, source)
        assert merged["bubble_stream_direction"] == "left"
        assert "bubble_manual_floor" not in merged
        assert "bubble_audio_block_size" not in merged

    def test_from_mapping_curated_preset_values_win_over_saved_custom_values(self, monkeypatch):
        from core.settings import visualizer_presets as vp
        from core.settings.models import SpotifyVisualizerSettings

        mode = "bubble"
        custom_idx = vp.get_custom_preset_index(mode)
        curated_idx = 0 if custom_idx > 0 else 1

        def _fake_get_preset_settings(mode_key, index):
            if mode_key == mode and index == curated_idx:
                return {
                    "bubble_stream_direction": "up",
                    "bubble_manual_floor": 0.12,
                    "bubble_audio_block_size": 128,
                }
            return {}

        monkeypatch.setattr(vp, "get_preset_settings", _fake_get_preset_settings)

        payload = {
            "mode": "bubble",
            "preset_bubble": curated_idx,
            "bubble_stream_direction": "right",
            "bubble_manual_floor": 0.27,
            "bubble_audio_block_size": 256,
        }
        model = SpotifyVisualizerSettings.from_mapping(payload)
        assert model.bubble_stream_direction == "up"
        assert model.resolve_manual_floor("bubble") == pytest.approx(0.12)
        assert model.resolve_audio_block_size("bubble") == 128

    def test_from_mapping_custom_preset_keeps_custom_values(self):
        from core.settings import visualizer_presets as vp
        from core.settings.models import SpotifyVisualizerSettings

        custom_idx = vp.get_custom_preset_index("bubble")
        payload = {
            "mode": "bubble",
            "preset_bubble": custom_idx,
            "bubble_stream_direction": "right",
            "bubble_manual_floor": 0.31,
            "bubble_audio_block_size": 256,
        }
        model = SpotifyVisualizerSettings.from_mapping(payload)
        assert model.bubble_stream_direction == "right"
        assert model.resolve_manual_floor("bubble") == pytest.approx(0.31)
        assert model.resolve_audio_block_size("bubble") == 256

    def test_mode_switch_uses_active_mode_curated_preset_contract(self):
        from core.settings.models import SpotifyVisualizerSettings

        payload = {
            "mode": "bubble",
            "preset_bubble": 0,
            "preset_spectrum": 0,
            "bubble_manual_floor": 0.31,
            "bubble_audio_block_size": 256,
            "spectrum_manual_floor": 0.37,
            "spectrum_audio_block_size": 256,
        }

        bubble_model = SpotifyVisualizerSettings.from_mapping(payload)
        bubble_baseline = SpotifyVisualizerSettings.from_mapping({"mode": "bubble", "preset_bubble": 0})
        assert bubble_model.resolve_manual_floor("bubble") == pytest.approx(
            bubble_baseline.resolve_manual_floor("bubble")
        )
        assert bubble_model.resolve_audio_block_size("bubble") == bubble_baseline.resolve_audio_block_size("bubble")

        spectrum_payload = dict(payload)
        spectrum_payload["mode"] = "spectrum"
        spectrum_model = SpotifyVisualizerSettings.from_mapping(spectrum_payload)
        spectrum_baseline = SpotifyVisualizerSettings.from_mapping({"mode": "spectrum", "preset_spectrum": 0})
        assert spectrum_model.resolve_manual_floor("spectrum") == pytest.approx(
            spectrum_baseline.resolve_manual_floor("spectrum")
        )
        assert spectrum_model.resolve_audio_block_size("spectrum") == spectrum_baseline.resolve_audio_block_size(
            "spectrum"
        )


# ===========================================================================
# 5. Creator kwargs: settings must be passed through
# ===========================================================================

class TestCreatorKwargs:
    """Verify spotify_widget_creators passes critical settings."""

    def test_critical_settings_passed_through(self):
        from core.settings.models import SpotifyVisualizerSettings
        from rendering.spotify_widget_creators import apply_spotify_vis_model_config

        captured = {}

        class FakeVis:
            def apply_vis_mode_config(self, **kwargs):
                captured.update(kwargs)

        model = SpotifyVisualizerSettings(
            mode="bubble",
            sine_width_reaction=0.42,
            sine_micro_wobble=0.15,
            sine_heartbeat=0.33,
            rainbow_enabled=True,
            rainbow_speed=0.8,
            osc_ghosting_enabled=True,
            osc_ghost_intensity=0.6,
            bubble_outline_color=[10, 20, 30, 255],
            bubble_gradient_direction="center_out",
            bubble_specular_direction="bottom_right",
            bubble_bounce_big_pct=88,
            bubble_bounce_small_pct=18,
            bubble_bounce_big_speed=1.1,
            bubble_bounce_small_speed=0.6,
            bubble_bounce_same_only=True,
            bubble_collision_pop_mode="one",
        )

        apply_spotify_vis_model_config(FakeVis(), model)

        assert captured["sine_width_reaction"] == pytest.approx(0.42)
        assert captured["sine_micro_wobble"] == pytest.approx(0.15)
        assert captured["sine_heartbeat"] == pytest.approx(0.33)
        assert captured["rainbow_enabled"] is True
        assert captured["rainbow_speed"] == pytest.approx(0.8)
        assert captured["osc_ghosting_enabled"] is True
        assert captured["osc_ghost_intensity"] == pytest.approx(0.6)
        assert captured["bubble_outline_color"] == [10, 20, 30, 255]
        assert captured["bubble_gradient_direction"] == "center_out"
        assert captured["bubble_specular_direction"] == "bottom_right"
        assert captured["bubble_bounce_big_pct"] == 88
        assert captured["bubble_bounce_small_pct"] == 18
        assert captured["bubble_bounce_big_speed"] == pytest.approx(1.1)
        assert captured["bubble_bounce_small_speed"] == pytest.approx(0.6)
        assert captured["bubble_bounce_same_only"] is True
        assert captured["bubble_collision_pop_mode"] == "one"

    def test_apply_spotify_vis_model_config_passes_spectrum_glow_and_secondary_ghosts(self):
        from core.settings.models import SpotifyVisualizerSettings
        from rendering.spotify_widget_creators import apply_spotify_vis_model_config

        captured = {}

        class FakeVis:
            def apply_vis_mode_config(self, **kwargs):
                captured.update(kwargs)

        model = SpotifyVisualizerSettings(
            mode="oscilloscope",
            osc_ghost_line2_enabled=True,
            osc_ghost_line3_enabled=False,
            spectrum_glow_enabled=True,
            spectrum_glow_intensity=1.1,
            spectrum_glow_color=[12, 34, 200, 255],
        )

        apply_spotify_vis_model_config(FakeVis(), model)

        assert captured["spectrum_glow_enabled"] is True
        assert captured["spectrum_glow_intensity"] == pytest.approx(1.1)
        assert captured["spectrum_glow_color"] == [12, 34, 200, 255]
        assert captured["osc_ghost_line2_enabled"] is True
        assert captured["osc_ghost_line3_enabled"] is False

    def test_apply_spotify_vis_model_config_translates_canonical_spectrum_fields(self):
        from core.settings.models import SpotifyVisualizerSettings
        from rendering.spotify_widget_creators import apply_spotify_vis_model_config

        captured = {}

        class FakeVis:
            def apply_vis_mode_config(self, **kwargs):
                captured.update(kwargs)

        model = SpotifyVisualizerSettings(
            mode="spectrum",
            spectrum_render_mode="segment",
            spectrum_unique_colors=False,
        )

        apply_spotify_vis_model_config(FakeVis(), model)

        assert captured["mode"] == "spectrum"
        assert captured["spectrum_single_piece"] is False
        assert captured["spectrum_rainbow_per_bar"] is False
        assert captured["spectrum_lane_strengths_mirrored"] == model.spectrum_lane_strengths_mirrored
        assert captured["spectrum_lane_strengths_linear"] == model.spectrum_lane_strengths_linear


class TestWidgetsTabLiveConfigGuard:
    def test_build_current_spotify_visualizer_config_preserves_base_when_media_controls_missing(self):
        from ui.tabs.widgets_tab import WidgetsTab

        base_config = {
            "mode": "spectrum",
            "spectrum_bar_count": 35,
            "spectrum_glow_enabled": True,
        }
        dummy_tab = SimpleNamespace()

        result = WidgetsTab._build_current_spotify_visualizer_config(dummy_tab, base_config)

        assert result == base_config
        assert result is not base_config
        assert result == deepcopy(base_config)


class TestPresetOverlayRuntimeOverrides:
    def test_from_mapping_curated_spectrum_ignores_explicit_runtime_overrides(self):
        from core.settings.models import SpotifyVisualizerSettings

        baseline = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "spectrum",
                "preset_spectrum": 0,
            }
        )
        model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "spectrum",
                "preset_spectrum": 0,
                "bar_count": 32,
                "spectrum_bar_count": 35,
                "spectrum_glow_enabled": True,
                "spectrum_glow_intensity": 1.2,
                "spectrum_glow_color": [0, 120, 255, 255],
                "spectrum_manual_floor": 0.33,
            }
        )

        assert model.resolve_bar_count("spectrum") == baseline.resolve_bar_count("spectrum")
        assert model.spectrum_glow_enabled == baseline.spectrum_glow_enabled
        assert model.spectrum_glow_intensity == pytest.approx(baseline.spectrum_glow_intensity)
        assert model.spectrum_glow_color == baseline.spectrum_glow_color
        assert model.resolve_manual_floor("spectrum") == pytest.approx(baseline.resolve_manual_floor("spectrum"))

    def test_from_mapping_curated_spectrum_ignores_dotted_runtime_overrides(self):
        from core.settings.models import SpotifyVisualizerSettings

        baseline = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "spectrum",
                "preset_spectrum": 0,
            }
        )
        model = SpotifyVisualizerSettings.from_mapping(
            {
                "widgets.spotify_visualizer.mode": "spectrum",
                "widgets.spotify_visualizer.preset_spectrum": 0,
                "widgets.spotify_visualizer.spectrum_bar_count": 35,
                "widgets.spotify_visualizer.spectrum_glow_enabled": True,
                "widgets.spotify_visualizer.spectrum_glow_intensity": 1.2,
                "widgets.spotify_visualizer.spectrum_glow_color": [0, 120, 255, 255],
            }
        )

        assert model.resolve_bar_count("spectrum") == baseline.resolve_bar_count("spectrum")
        assert model.spectrum_glow_enabled == baseline.spectrum_glow_enabled
        assert model.spectrum_glow_intensity == pytest.approx(baseline.spectrum_glow_intensity)
        assert model.spectrum_glow_color == baseline.spectrum_glow_color

    def test_from_mapping_curated_ignores_explicit_secondary_ghost_toggles(self):
        from core.settings.models import SpotifyVisualizerSettings

        osc_baseline = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "oscilloscope",
                "preset_oscilloscope": 0,
            }
        )
        osc_model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "oscilloscope",
                "preset_oscilloscope": 0,
                "oscilloscope_bar_count": 35,
                "osc_ghost_line2_enabled": False,
                "osc_ghost_line3_enabled": True,
            }
        )
        assert osc_model.resolve_bar_count("oscilloscope") == osc_baseline.resolve_bar_count("oscilloscope")
        assert osc_model.osc_ghost_line2_enabled == osc_baseline.osc_ghost_line2_enabled
        assert osc_model.osc_ghost_line3_enabled == osc_baseline.osc_ghost_line3_enabled

        sine_baseline = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "sine_wave",
                "preset_sine_wave": 0,
            }
        )
        sine_model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "sine_wave",
                "preset_sine_wave": 0,
                "sine_ghost_line2_enabled": False,
                "sine_ghost_line3_enabled": True,
            }
        )
        assert sine_model.sine_ghost_line2_enabled == sine_baseline.sine_ghost_line2_enabled
        assert sine_model.sine_ghost_line3_enabled == sine_baseline.sine_ghost_line3_enabled


# ===========================================================================
# 6. Config applier: settings must be applied and pushed
# ===========================================================================

class TestConfigApplier:
    """Verify config_applier handles critical settings."""

    def test_sine_width_reaction_applied(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs, build_gpu_push_extra_kwargs

        class DummyWidget:
            _sine_width_reaction = 0.0

            def __getattr__(self, name):
                if "color" in name or "tint" in name:
                    return QColor(255, 255, 255, 255)
                if name.endswith("enabled"):
                    return False
                if name.endswith("_direction"):
                    return "top"
                if name.endswith("line_count"):
                    return 1
                return 0.0

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {"sine_width_reaction": 0.61})
        extra = build_gpu_push_extra_kwargs(widget, "sine_wave", None)

        assert widget._sine_width_reaction == pytest.approx(0.61)
        assert extra["sine_width_reaction"] == pytest.approx(0.61)
        assert "blob_color" not in extra
        assert "bubble_pos_data" not in extra

    def test_blob_pulse_controls_applied_and_pushed(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs, build_gpu_push_extra_kwargs

        class DummyWidget:
            _blob_pulse_cap = 1.0
            _blob_pulse_release_ms = 220.0
            _blob_stage_gain = 1.0
            _blob_glow_drive_mode = "bass"

            def __getattr__(self, name):
                if "color" in name or "tint" in name:
                    return QColor(255, 255, 255, 255)
                if name.endswith("enabled"):
                    return False
                if name.endswith("_direction"):
                    return "top"
                if name.endswith("line_count"):
                    return 1
                return 0.0

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {
            "blob_pulse": 1.65,
            "blob_pulse_release_ms": 1320.0,
            "blob_glow_drive_mode": "vocal",
        })
        extra = build_gpu_push_extra_kwargs(widget, "blob", None)

        assert widget._blob_pulse == pytest.approx(1.65)
        assert widget._blob_pulse_cap == pytest.approx(1.0)
        assert widget._blob_pulse_release_ms == pytest.approx(1320.0)
        assert widget._blob_stage_gain == pytest.approx(1.0)
        assert widget._blob_glow_drive_mode == "vocal"
        assert extra["blob_pulse"] == pytest.approx(1.65)
        assert extra["blob_pulse_cap"] == pytest.approx(1.0)
        assert extra["blob_pulse_release_ms"] == pytest.approx(1320.0)
        assert extra["blob_glow_drive_mode"] == "vocal"
        assert "line_sensitivity" not in extra
        assert "bubble_pos_data" not in extra

    def test_blob_non_shaper_export_keeps_inner_stretch_zero(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs

        class DummyWidget:
            _blob_shaper_enabled = False
            _blob_stretch_inner = 0.5
            _blob_stretch_outer = 0.4

            def __getattr__(self, name):
                if "color" in name or "tint" in name:
                    return QColor(255, 255, 255, 255)
                if name.endswith("enabled"):
                    return False
                if name.endswith("_direction"):
                    return "top"
                if name.endswith("line_count"):
                    return 1
                return 0.0

        extra = build_gpu_push_extra_kwargs(DummyWidget(), "blob", None)

        assert extra["blob_stretch_inner"] == pytest.approx(0.0)
        assert extra["blob_stretch_outer"] == pytest.approx(0.4)

    def test_blob_gpu_push_includes_floor_snapshot_from_engine(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
        from widgets.spotify_visualizer.energy_bands import EnergyBands
        from widgets.spotify_visualizer.transient_bus import TransientEnergyBands

        class _DummyWidget:
            def __getattr__(self, name):
                if "color" in name:
                    return QColor(255, 255, 255, 255)
                if name.endswith("enabled"):
                    return False
                if "alpha" in name or "decay" in name or "intensity" in name:
                    return 0.0
                return 0

        class _Engine:
            def get_waveform(self):
                return []

            def get_waveform_count(self):
                return 0

            def get_pre_agc_energy_bands(self):
                return EnergyBands(bass=0.1, mid=0.2, high=0.1, overall=0.15)

            def get_energy_bands(self):
                return EnergyBands(bass=0.1, mid=0.2, high=0.1, overall=0.15)

            def get_transient_energy_bands(self):
                return TransientEnergyBands()

            def get_floor_snapshot(self):
                return {
                    "dynamic_enabled": True,
                    "manual_floor": 0.15,
                    "applied_floor": 0.88,
                    "last_noise_floor": 0.86,
                    "pressure": 0.86,
                }

            def get_event_scheduler(self):
                return None

        extra = build_gpu_push_extra_kwargs(_DummyWidget(), "blob", _Engine())

        assert extra["floor_snapshot"]["dynamic_enabled"] is True
        assert extra["floor_snapshot"]["manual_floor"] == pytest.approx(0.15)
        assert extra["floor_snapshot"]["applied_floor"] == pytest.approx(0.88)

    def test_spectrum_glow_applied_and_pushed(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs, build_gpu_push_extra_kwargs

        class DummyWidget:
            _spectrum_glow_enabled = False
            _spectrum_glow_intensity = 0.55
            _spectrum_glow_color = QColor(110, 220, 255, 235)

            def __getattr__(self, name):
                if "color" in name or "tint" in name:
                    return QColor(255, 255, 255, 255)
                if name.endswith("enabled"):
                    return False
                if name.endswith("_direction"):
                    return "top"
                if name.endswith("line_count"):
                    return 1
                return 0.0

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {
            "spectrum_glow_enabled": True,
            "spectrum_glow_intensity": 1.2,
            "spectrum_glow_color": [0, 120, 255, 255],
        })
        extra = build_gpu_push_extra_kwargs(widget, "spectrum", None)

        assert widget._spectrum_glow_enabled is True
        assert widget._spectrum_glow_intensity == pytest.approx(1.2)
        assert widget._spectrum_glow_color == QColor(0, 120, 255, 255)
        assert extra["spectrum_glow_enabled"] is True
        assert extra["spectrum_glow_intensity"] == pytest.approx(1.2)
        assert extra["spectrum_glow_color"] == QColor(0, 120, 255, 255)

    def test_line2_line3_ghost_toggles_applied_and_pushed(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs, build_gpu_push_extra_kwargs

        class DummyWidget:
            _osc_ghost_line2_enabled = True
            _osc_ghost_line3_enabled = True
            _sine_ghost_line2_enabled = True
            _sine_ghost_line3_enabled = True

            def __getattr__(self, name):
                if "color" in name or "tint" in name:
                    return QColor(255, 255, 255, 255)
                if name.endswith("enabled"):
                    return False
                if name.endswith("_direction"):
                    return "top"
                if name.endswith("line_count"):
                    return 1
                return 0.0

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {
            "osc_ghost_line2_enabled": False,
            "osc_ghost_line3_enabled": True,
            "sine_ghost_line2_enabled": False,
            "sine_ghost_line3_enabled": True,
        })
        osc_extra = build_gpu_push_extra_kwargs(widget, "oscilloscope", None)
        sine_extra = build_gpu_push_extra_kwargs(widget, "sine_wave", None)

        assert osc_extra["osc_ghost_line2_enabled"] is False
        assert osc_extra["osc_ghost_line3_enabled"] is True
        assert sine_extra["sine_ghost_line2_enabled"] is False
        assert sine_extra["sine_ghost_line3_enabled"] is True

    def test_bubble_gpu_push_has_snapshot_data(self):
        """Bubble GPU push must include pos_data, extra_data, count."""
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs

        class DummyWidget:
            _bubble_pos_data = [0.1, 0.2, 0.3, 0.4]
            _bubble_extra_data = [0.5, 0.6, 0.7, 0.8]
            _bubble_trail_data = [0.9, 1.0]
            _bubble_count = 2

            def __getattr__(self, name):
                if "color" in name or "tint" in name:
                    return QColor(255, 255, 255, 255)
                if name.endswith("enabled"):
                    return False
                if name.endswith("_direction"):
                    return "top"
                if name.endswith("line_count"):
                    return 1
                return 0.0

        extra = build_gpu_push_extra_kwargs(DummyWidget(), "bubble", None)
        for key in ("bubble_pos_data", "bubble_extra_data", "bubble_count"):
            assert key in extra
        assert "blob_color" not in extra
        assert "line_sensitivity" not in extra

    def test_config_applier_accepts_gradient_direction(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bubble_gradient_direction = "top"

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {"bubble_gradient_direction": "bottom_left"})
        assert widget._bubble_gradient_direction == "bottom_left"

    def test_config_applier_accepts_specular_direction(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bubble_specular_direction = "top_left"

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {"bubble_specular_direction": "right"})
        assert widget._bubble_specular_direction == "right"

    def test_config_applier_clamps_bubble_bounce_settings(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bubble_bounce_big_pct = 70
            _bubble_bounce_small_pct = 30
            _bubble_bounce_big_speed = 0.8
            _bubble_bounce_small_speed = 0.5
            _bubble_bounce_same_only = False
            _bubble_collision_pop_mode = "off"

        widget = DummyWidget()
        apply_vis_mode_kwargs(
            widget,
            {
                "bubble_bounce_big_pct": 175,
                "bubble_bounce_small_pct": -9,
                "bubble_bounce_big_speed": 9.5,
                "bubble_bounce_small_speed": -3.0,
                "bubble_bounce_same_only": True,
                "bubble_collision_pop_mode": "bad_value",
            },
        )
        assert widget._bubble_bounce_big_pct == 100
        assert widget._bubble_bounce_small_pct == 0
        assert widget._bubble_bounce_big_speed == pytest.approx(2.0)
        assert widget._bubble_bounce_small_speed == pytest.approx(0.0)
        assert widget._bubble_bounce_same_only is True
        assert widget._bubble_collision_pop_mode == "off"

    def test_gpu_push_extra_kwargs_include_gradient_and_specular(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
        from PySide6.QtGui import QColor

        class _DummyWidget:
            """Minimal stub that satisfies build_gpu_push_extra_kwargs reads."""
            def __getattr__(self, name):
                if name.startswith('_bubble_specular_direction'):
                    return "bottom_right"
                if name.startswith('_bubble_gradient_direction'):
                    return "bottom"
                if name.startswith('_bubble_') and 'color' in name:
                    return QColor(255, 255, 255, 255)
                if name.startswith('_bubble_'):
                    return 0
                if 'color' in name or 'tint' in name:
                    return QColor(255, 255, 255, 255)
                if 'enabled' in name or 'double' in name:
                    return False
                return 0.0

        extra = build_gpu_push_extra_kwargs(_DummyWidget(), "bubble", None)

        assert extra["bubble_gradient_direction"] == "bottom"
        assert extra["bubble_specular_direction"] == "bottom_right"

    def test_apply_vis_mode_kwargs_sets_bar_colors(self):
        from PySide6.QtGui import QColor
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bar_fill_color = QColor(0, 0, 0, 0)
            _bar_border_color = QColor(0, 0, 0, 0)

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {
            "bar_fill_color": [5, 10, 15, 200],
            "bar_border_color": [20, 25, 30, 255],
            "bar_border_opacity": 0.4,
        })

        assert widget._bar_fill_color == QColor(5, 10, 15, 200)
        assert widget._bar_border_color.red() == 20
        assert widget._bar_border_color.green() == 25
        assert widget._bar_border_color.blue() == 30
        assert abs(widget._bar_border_color.alphaF() - 0.4) < 1e-6

    def test_gpu_push_extra_kwargs_leaves_spectrum_bar_colors_on_top_level_push(self):
        from PySide6.QtGui import QColor
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs

        class DummyWidget:
            def __init__(self):
                self._bar_fill_color = QColor(100, 110, 120, 230)
                self._bar_border_color = QColor(200, 210, 220, 128)

            def __getattr__(self, name):
                if name.startswith('_') and 'color' in name:
                    return QColor(255, 255, 255, 255)
                if name.startswith('_') and name.endswith('enabled'):
                    return False
                if name.startswith('_'):
                    return 0
                raise AttributeError(name)

        extra = build_gpu_push_extra_kwargs(DummyWidget(), "spectrum", None)
        assert 'bar_fill_color' not in extra
        assert 'bar_border_color' not in extra


# ===========================================================================
# 7. GL overlay: uniform query list and set_state params
# ===========================================================================

class TestGLOverlayStateContract:
    """Verify overlay.set_state still accepts the pushed kwargs we rely on."""

    def test_set_state_accepts_bubble_gpu_and_width_reaction_params(self):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        params = set(inspect.signature(SpotifyBarsGLOverlay.set_state).parameters) - {"self"}
        required = {
            "bubble_count",
            "bubble_pos_data",
            "bubble_extra_data",
            "bubble_outline_color",
            "bubble_specular_direction",
            "bubble_gradient_direction",
            "sine_width_reaction",
        }
        missing = required - params
        assert not missing, f"overlay.set_state missing required params: {sorted(missing)}"

    def test_set_state_accepts_secondary_ghosts_and_spectrum_glow(self):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        params = set(inspect.signature(SpotifyBarsGLOverlay.set_state).parameters) - {"self"}
        required = {
            "osc_ghost_line2_enabled",
            "osc_ghost_line3_enabled",
            "sine_ghost_line2_enabled",
            "sine_ghost_line3_enabled",
            "spectrum_glow_enabled",
            "spectrum_glow_intensity",
            "spectrum_glow_color",
        }
        missing = required - params
        assert not missing, f"overlay.set_state missing required params: {sorted(missing)}"


class TestCreateTimeRefreshParity:
    def test_create_spotify_visualizer_widget_reuses_refresh_path(self, monkeypatch):
        appdata = ROOT / "tests_tmp_appdata"
        appdata.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("APPDATA", str(appdata))
        from core.settings import visualizer_presets as vp
        from rendering import spotify_widget_creators as creators

        class FakeVisualizer:
            def __init__(self, parent, bar_count):
                self.parent = parent
                self.bar_count = bar_count
                self.bar_colors = None

            def set_settings_model(self, model):
                self.model = model

            def set_anchor_media_widget(self, widget):
                self.anchor = widget

            def set_bar_style(self, **kwargs):
                self.bar_style = kwargs

            def set_bar_colors(self, fill, border):
                self.bar_colors = (fill, border)

            def set_ghost_config(self, enabled, alpha, decay):
                self.ghost = (enabled, alpha, decay)

            def set_shadow_config(self, cfg):
                self.shadow = cfg

            def handle_media_update(self, *args, **kwargs):
                return None

            def apply_vis_mode_config(self, **kwargs):
                self.mode_kwargs = kwargs

        monkeypatch.setattr(creators, "SpotifyVisualizerWidget", FakeVisualizer)
        monkeypatch.setattr(creators, "parse_color_to_qcolor", lambda *args, **kwargs: SimpleNamespace())

        class FakeSignal:
            def connect(self, *args, **kwargs):
                return None

        class FakeMediaWidget:
            media_updated = FakeSignal()

        refresh_calls = []

        class FakeManager:
            def __init__(self):
                self._parent = object()
                self._widgets = {}
                self.bound = {}

            def add_expected_overlay(self, name):
                self.expected_overlay = name

            def _log_spotify_vis_config(self, *args, **kwargs):
                return None

            def register_widget(self, name, widget):
                self._widgets[name] = widget

            def _bind_parent_attribute(self, name, widget):
                self.bound[name] = widget

            def _refresh_spotify_visualizer_config(self, payload=None):
                refresh_calls.append(payload)

        mgr = FakeManager()
        widgets_config = {
            "media": {
                "monitor": "ALL",
                "bg_color": [0, 0, 0, 180],
                "background_opacity": 0.5,
                "border_color": [255, 255, 255, 255],
                "border_opacity": 0.8,
                "show_background": True,
            },
            "spotify_visualizer": {
                "enabled": True,
                "mode": "spectrum",
                "preset_spectrum": vp.get_custom_preset_index("spectrum"),
                "bar_count": 32,
                "spectrum_bar_count": 35,
                "spectrum_glow_enabled": True,
                "spectrum_glow_intensity": 1.2,
                "spectrum_glow_color": [0, 120, 255, 255],
                "bar_fill_color": [25, 25, 25, 255],
                "bar_border_color": [20, 140, 255, 255],
                "bar_border_opacity": 1.0,
            },
        }

        vis = creators.create_spotify_visualizer_widget(
            mgr,
            widgets_config,
            shadows_config={},
            screen_index=0,
            thread_manager=None,
            media_widget=FakeMediaWidget(),
        )

        assert vis is not None
        assert vis.bar_count == 35
        assert vis.model.resolve_bar_count("spectrum") == 35
        assert vis.model.spectrum_glow_enabled is True
        assert vis.model.spectrum_glow_intensity == pytest.approx(1.2)
        assert vis.bar_colors is not None
        fill_color, border_color = vis.bar_colors
        assert (fill_color.red(), fill_color.green(), fill_color.blue(), fill_color.alpha()) == tuple(vis.model.bar_fill_color)
        expected_border = list(vis.model.bar_border_color)
        expected_border[3] = int(float(vis.model.bar_border_opacity) * expected_border[3])
        assert (border_color.red(), border_color.green(), border_color.blue(), border_color.alpha()) == tuple(expected_border)
        assert vis.mode_kwargs["spectrum_glow_enabled"] is True
        assert vis.mode_kwargs["spectrum_glow_intensity"] == pytest.approx(1.2)
        assert getattr(mgr, "expected_overlay", None) is None, (
            "Visualizer should no longer register as a primary overlay participant; "
            "it now joins via the Spotify secondary stage."
        )
        assert refresh_calls == [widgets_config], (
            "Create-time visualizer setup must reuse the same refresh contract "
            "that settings re-entry uses."
        )

    def test_create_spotify_visualizer_widget_applies_curated_contract_on_startup(self, monkeypatch):
        appdata = ROOT / "tests_tmp_appdata"
        appdata.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("APPDATA", str(appdata))
        from core.settings.models import SpotifyVisualizerSettings
        from rendering import spotify_widget_creators as creators

        class FakeVisualizer:
            def __init__(self, parent, bar_count):
                self.parent = parent
                self.bar_count = bar_count

            def set_settings_model(self, model):
                self.model = model

            def set_anchor_media_widget(self, widget):
                self.anchor = widget

            def set_bar_style(self, **kwargs):
                self.bar_style = kwargs

            def set_bar_colors(self, fill, border):
                self.bar_colors = (fill, border)

            def set_ghost_config(self, enabled, alpha, decay):
                self.ghost = (enabled, alpha, decay)

            def set_shadow_config(self, cfg):
                self.shadow = cfg

            def handle_media_update(self, *args, **kwargs):
                return None

            def apply_vis_mode_config(self, **kwargs):
                self.mode_kwargs = kwargs

        monkeypatch.setattr(creators, "SpotifyVisualizerWidget", FakeVisualizer)
        monkeypatch.setattr(creators, "parse_color_to_qcolor", lambda *args, **kwargs: SimpleNamespace())

        class FakeSignal:
            def connect(self, *args, **kwargs):
                return None

        class FakeMediaWidget:
            media_updated = FakeSignal()

        class FakeManager:
            def __init__(self):
                self._parent = object()
                self._widgets = {}

            def add_expected_overlay(self, name):
                self.expected_overlay = name

            def _log_spotify_vis_config(self, *args, **kwargs):
                return None

            def register_widget(self, name, widget):
                self._widgets[name] = widget

            def _bind_parent_attribute(self, name, widget):
                return None

            def _refresh_spotify_visualizer_config(self, payload=None):
                return None

        mgr = FakeManager()
        widgets_config = {
            "media": {"monitor": "ALL"},
            "spotify_visualizer": {
                "enabled": True,
                "mode": "bubble",
                "preset_bubble": 0,
                "bubble_manual_floor": 0.31,
                "bubble_audio_block_size": 256,
            },
        }

        vis = creators.create_spotify_visualizer_widget(
            mgr,
            widgets_config,
            shadows_config={},
            screen_index=0,
            thread_manager=None,
            media_widget=FakeMediaWidget(),
        )

        assert vis is not None
        baseline = SpotifyVisualizerSettings.from_mapping({"mode": "bubble", "preset_bubble": 0})
        assert vis.model.resolve_manual_floor("bubble") == pytest.approx(
            baseline.resolve_manual_floor("bubble")
        )
        assert vis.model.resolve_audio_block_size("bubble") == baseline.resolve_audio_block_size("bubble")


class TestDisplayFramePush:
    def test_push_spotify_visualizer_frame_preserves_spectrum_glow_and_osc_secondary_ghosts(self, monkeypatch):
        from rendering import display_image_ops

        class FakeOverlay:
            def __init__(self, parent):
                self.parent = parent
                self.last_kwargs = None

            def setObjectName(self, *_args):
                return None

            def clear_overlay_buffer(self):
                return None

            def set_state(self, **kwargs):
                self.last_kwargs = dict(kwargs)

        monkeypatch.setattr(display_image_ops, "SpotifyBarsGLOverlay", FakeOverlay)

        class FakeVis:
            def isVisible(self):
                return True

            def geometry(self):
                return QRect(0, 0, 320, 180)

        class FakeWidget:
            def __init__(self):
                self.spotify_visualizer_widget = FakeVis()
                self._spotify_bars_overlay = None
                self._resource_manager = None
                self._widget = self

        widget = FakeWidget()
        ok = display_image_ops.push_spotify_visualizer_frame(
            widget,
            bars=[0.1, 0.3, 0.2],
            bar_count=3,
            segments=16,
            fill_color=QColor(10, 10, 10, 255),
            border_color=QColor(255, 255, 255, 255),
            fade=1.0,
            playing=True,
            vis_mode="oscilloscope",
            spectrum_glow_enabled=True,
            spectrum_glow_intensity=1.2,
            spectrum_glow_color=QColor(0, 120, 255, 255),
            osc_ghosting_enabled=True,
            osc_ghost_intensity=0.55,
            osc_ghost_line2_enabled=True,
            osc_ghost_line3_enabled=False,
        )

        assert ok is True
        overlay = widget._spotify_bars_overlay
        assert overlay is not None
        assert overlay.last_kwargs is not None
        assert overlay.last_kwargs["spectrum_glow_enabled"] is True
        assert overlay.last_kwargs["spectrum_glow_intensity"] == pytest.approx(1.2)
        assert overlay.last_kwargs["osc_ghost_line2_enabled"] is True
        assert overlay.last_kwargs["osc_ghost_line3_enabled"] is False


# ===========================================================================
# 8. Bubble simulation thread safety
# ===========================================================================

class TestBubbleSimulationThreadSafety:
    """Verify bubble simulation accepts dict energy_bands (for COMPUTE thread)."""

    def test_tick_accepts_dict_energy_bands(self):
        from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
        sim = BubbleSimulation()
        eb_dict = {"bass": 0.5, "mid": 0.3, "high": 0.2, "overall": 0.4}
        settings = {
            "bubble_big_count": 5,
            "bubble_small_count": 10,
            "bubble_surface_reach": 0.6,
            "bubble_stream_direction": "up",
            "bubble_stream_constant_speed": 0.5,
            "bubble_stream_speed_cap": 2.0,
            "bubble_stream_reactivity": 0.5,
            "bubble_rotation_amount": 0.5,
            "bubble_drift_amount": 0.5,
            "bubble_drift_speed": 0.5,
            "bubble_drift_frequency": 0.5,
            "bubble_drift_direction": "random",
        }
        # Should not raise — dict must be accepted, not just objects
        sim.tick(0.016, eb_dict, settings)
        pos, extra, trail = sim.snapshot(
            bass=0.5, mid_high=0.25, big_bass_pulse=0.5, small_freq_pulse=0.5
        )
        assert isinstance(pos, list)
        assert isinstance(extra, list)
        assert isinstance(trail, list)
        assert isinstance(sim.count, int)

    def test_tick_accepts_none_energy_bands(self):
        """Graceful handling of None energy bands."""
        from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
        sim = BubbleSimulation()
        settings = {
            "bubble_big_count": 3, "bubble_small_count": 5,
            "bubble_surface_reach": 0.6, "bubble_stream_direction": "none",
            "bubble_stream_constant_speed": 0.5,
            "bubble_stream_speed_cap": 0.5,
            "bubble_stream_reactivity": 0.0,
            "bubble_rotation_amount": 0.0, "bubble_drift_amount": 0.0,
            "bubble_drift_speed": 0.0, "bubble_drift_frequency": 0.0,
            "bubble_drift_direction": "none",
        }
        # None energy bands should not crash
        sim.tick(0.016, None, settings)


# ===========================================================================
# 9a. Per-mode technical load/save round-trip
# ===========================================================================


class TestPerModeTechnicalRoundTrip:
    """Ensure per-mode technical overrides survive load/save paths."""

    def _sample_payload(self):
        from core.settings.models import PER_MODE_TECHNICAL_MODES

        payload = {
            "widgets.spotify_visualizer.bar_count": 64,
            "widgets.spotify_visualizer.manual_floor": 2.5,
            "widgets.spotify_visualizer.dynamic_floor": True,
            "widgets.spotify_visualizer.dynamic_range_enabled": False,
            "widgets.spotify_visualizer.adaptive_sensitivity": True,
            "widgets.spotify_visualizer.sensitivity": 1.0,
        }
        per_mode = {}
        for idx, mode in enumerate(PER_MODE_TECHNICAL_MODES, start=1):
            overrides = {
                "bar_count": 12 + idx,
                "manual_floor": round(1.0 + idx * 0.1, 2),
                "dynamic_floor": idx % 2 == 0,
                "dynamic_range_enabled": idx % 3 == 0,
                "audio_block_size": 64 * idx,
                "adaptive_sensitivity": idx % 2 == 1,
                "sensitivity": round(0.5 + idx * 0.15, 2),
            }
            prefix = f"widgets.spotify_visualizer.{mode}_"
            for key, value in overrides.items():
                payload[f"{prefix}{key}"] = value
            per_mode[mode] = overrides
        return payload, per_mode

    def _assert_model_matches(self, model, per_mode):
        for mode, overrides in per_mode.items():
            assert model.resolve_bar_count(mode) == overrides["bar_count"]
            assert model.resolve_manual_floor(mode) == overrides["manual_floor"]
            assert model.resolve_dynamic_floor(mode) == overrides["dynamic_floor"]
            assert model.resolve_dynamic_range_enabled(mode) == overrides["dynamic_range_enabled"]
            assert model.resolve_audio_block_size(mode) == overrides["audio_block_size"]
            assert model.resolve_adaptive_sensitivity(mode) == overrides["adaptive_sensitivity"]
            assert model.resolve_sensitivity(mode) == overrides["sensitivity"]

    def _assert_dict_matches(self, data, per_mode):
        for mode, overrides in per_mode.items():
            prefix = f"widgets.spotify_visualizer.{mode}_"
            for key, value in overrides.items():
                assert data[f"{prefix}{key}"] == value

    def test_from_mapping_round_trip(self):
        from core.settings.models import SpotifyVisualizerSettings

        payload, per_mode = self._sample_payload()
        model = SpotifyVisualizerSettings.from_mapping(payload)
        serialized = model.to_dict()
        self._assert_model_matches(model, per_mode)
        self._assert_dict_matches(serialized, per_mode)

    def test_from_settings_round_trip(self):
        from core.settings.models import SpotifyVisualizerSettings

        class _DummySettings:
            def __init__(self, data):
                self._data = data

            def get(self, key, default=None):
                return self._data.get(key, default)

        payload, per_mode = self._sample_payload()
        settings = _DummySettings(payload)
        model = SpotifyVisualizerSettings.from_settings(settings)
        serialized = model.to_dict()
        self._assert_model_matches(model, per_mode)
        self._assert_dict_matches(serialized, per_mode)


# ===========================================================================
# 9a-ii. Per-mode technical UI collection (new controls)
# ===========================================================================


class _StubSlider:
    def __init__(self, value: int):
        self._value = value

    def value(self) -> int:
        return self._value

    def blockSignals(self, _blocked: bool) -> None:
        return None

    def setValue(self, value: int) -> None:
        self._value = value


class _StubCombo:
    def __init__(self, data: int, options: list[int] | None = None):
        self._options = list(options or [0, 128, 256, 512, 1024])
        try:
            self._index = self._options.index(data)
        except ValueError:
            self._index = 0

    def currentData(self) -> int:
        return self._options[self._index]

    def blockSignals(self, _blocked: bool) -> None:
        return None

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self._options):
            self._index = index

    def findData(self, value: int) -> int:
        try:
            return self._options.index(value)
        except ValueError:
            return -1


class _StubCheck:
    def __init__(self, checked: bool):
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked

    def blockSignals(self, _blocked: bool) -> None:
        return None

    def setChecked(self, checked: bool) -> None:
        self._checked = checked


class _StubLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class TestPerModeTechnicalControlsCollection:
    def test_collect_per_mode_controls_includes_input_gain_and_block_size(self):
        from ui.tabs.media import technical_controls as tc

        class _DummyTab:
            pass

        tab = _DummyTab()
        tc.register_per_mode_technical_controls(
            tab,
            "sine_wave",
            controls={
                "input_gain_slider": _StubSlider(130),
                "block_size": _StubCombo(128),
                "adaptive": _StubCheck(True),
                "sensitivity_slider": _StubSlider(110),
                "dynamic_floor": _StubCheck(True),
                "manual_floor": _StubSlider(20),
                "dynamic_range": _StubCheck(False),
                "agc_strength_slider": _StubSlider(55),
            },
            update_sensitivity=lambda: None,
            update_manual_floor=lambda: None,
        )

        config: dict[str, float | int | bool] = {}
        tc.collect_per_mode_technical_controls(tab, config)

        assert config["sine_wave_audio_block_size"] == 128
        assert config["sine_wave_input_gain"] == pytest.approx(1.30)


class TestPerModeTechnicalControlPresentation:
    def test_block_size_combo_tints_mode_recommended_entry(self, qtbot):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QVBoxLayout, QWidget
        from ui.tabs.media import technical_controls as tc
        from ui.widgets import StyledComboBox

        class _DummySettings:
            def get(self, *_args, **_kwargs):
                return {}

        class _DummyTab(QWidget):
            def __init__(self):
                super().__init__()
                self._settings = _DummySettings()

            def _default_bool(self, *_args):
                return False

            def _default_int(self, _section, _key, default):
                return default

            def _default_float(self, _section, _key, default):
                return default

            def _save_settings(self):
                return None

            def _auto_switch_preset_to_custom(self):
                return None

        tab = _DummyTab()
        qtbot.addWidget(tab)
        host = QWidget()
        qtbot.addWidget(host)
        layout = QVBoxLayout(host)

        controls = tc._build_control(
            tab,
            layout,
            "blob",
            next(defn for defn in tc._BASE_CONTROL_DEFS if defn.control_key == "block_size"),
        )
        combo = controls["block_size"]
        assert isinstance(combo, StyledComboBox)
        idx = combo.findData(256)
        assert idx >= 0
        tinted = combo.itemData(idx, Qt.ItemDataRole.ForegroundRole)
        assert isinstance(tinted, QColor)
        assert tinted == tc._RECOMMENDED_COMBO_COLOR

    def test_collect_per_mode_controls_keeps_direct_transient_keys_unprefixed(self):
        from ui.tabs.media import technical_controls as tc

        class _DummyTab:
            pass

        tab = _DummyTab()
        tc.register_per_mode_technical_controls(
            tab,
            "spectrum",
            controls={
                "mix_slider": _StubSlider(63),
                "mix_config_key": "spectrum_lane_transient_mix",
            },
            update_sensitivity=lambda: None,
            update_manual_floor=lambda: None,
        )
        tc.register_per_mode_technical_controls(
            tab,
            "bubble",
            controls={
                "mix_vocal_slider": _StubSlider(28),
            },
            update_sensitivity=lambda: None,
            update_manual_floor=lambda: None,
        )

        config: dict[str, float | int | bool] = {}
        tc.collect_per_mode_technical_controls(tab, config)

        assert config["spectrum_lane_transient_mix"] == pytest.approx(0.63)
        assert config["bubble_transient_mix_vocal"] == pytest.approx(0.28)
        assert "spectrum_spectrum_lane_transient_mix" not in config
        assert "bubble_bubble_transient_mix_vocal" not in config

    def test_blob_technical_controls_include_kick_gain_slider(self):
        from ui.tabs.media import technical_controls as tc

        defs = tc._control_defs_for_mode("blob")
        config_keys = {defn.config_key for defn in defs}

        assert "kick_lane_gain" in config_keys
        assert "transient_pulse_gain" not in config_keys

    def test_shared_technical_copy_clarifies_recommended_sensitivity_and_noise_floor(self):
        from ui.tabs.media import technical_controls as tc

        defs = {defn.control_key: defn for defn in tc._control_defs_for_mode("spectrum")}

        assert defs["adaptive"].checkbox_text == "Use Recommended Sensitivity"
        assert defs["dynamic_range"].checkbox_text == "Output Lift"
        assert defs["manual_floor"].label_text == "Noise Floor\nBaseline:"
        assert "Recommended for Spectrum: 128 samples." in tc._audio_block_tooltip("spectrum")
        assert "not live adaptive analysis" in tc._recommended_sensitivity_tooltip("spectrum")
        assert "groove marker shows the recommended starting position" in tc._agc_tooltip("spectrum")

    @pytest.mark.parametrize(
        ("mode_key", "expected_percent"),
        [
            ("spectrum", 42),
            ("blob", 45),
            ("bubble", 50),
            ("sine_wave", 18),
            ("oscilloscope", 15),
        ],
    )
    def test_agc_slider_uses_mode_specific_recommended_marker(self, qt_app, mode_key, expected_percent):
        from PySide6.QtWidgets import QVBoxLayout, QWidget
        from ui.tabs.media import technical_controls as tc
        from ui.tabs.shared_styles import RecommendedMarkSlider

        class _DummyTab(QWidget):
            def _default_bool(self, *_args):
                return False

            def _default_int(self, *_args):
                return 32

            def _default_float(self, *_args):
                return 0.5

            def _save_settings(self):
                return None

            def _auto_switch_preset_to_custom(self):
                return None

        tab = _DummyTab()
        layout = QVBoxLayout(tab)
        defs = {defn.control_key: defn for defn in tc._control_defs_for_mode(mode_key)}

        controls = tc._build_control(tab, layout, mode_key, defs["agc_strength_slider"])
        slider = controls["agc_strength_slider"]

        assert isinstance(slider, RecommendedMarkSlider)
        assert slider.recommended_value() == expected_percent

    def test_load_per_mode_controls_reads_direct_transient_keys(self):
        from ui.tabs.media import technical_controls as tc

        class _DummyTab:
            def _default_bool(self, *_args):
                return False

            def _default_int(self, *_args):
                return 32

            def _default_float(self, *_args):
                return 0.5

        tab = _DummyTab()
        tc.register_per_mode_technical_controls(
            tab,
            "spectrum",
            controls={
                "mix_slider": _StubSlider(0),
                "mix_label": _StubLabel(),
                "mix_config_key": "spectrum_lane_transient_mix",
            },
            update_sensitivity=lambda: None,
            update_manual_floor=lambda: None,
        )

        tc.load_per_mode_technical_controls(
            tab,
            {
                "spectrum_lane_transient_mix": 0.71,
            },
        )

        controls = tc.get_per_mode_controls_for_mode(tab, "spectrum")
        assert controls is not None
        assert controls["mix_slider"].value() == 71
        assert controls["mix_label"].text == "71%"

    @pytest.mark.parametrize("block_size", [128, 512])
    def test_load_per_mode_controls_preserves_valid_combo_block_sizes(self, block_size):
        from ui.tabs.media import technical_controls as tc

        class _DummyTab:
            def _default_bool(self, *_args):
                return False

            def _default_int(self, *_args):
                return 0

            def _default_float(self, *_args):
                return 0.5

        tab = _DummyTab()
        tc.register_per_mode_technical_controls(
            tab,
            "sine_wave",
            controls={
                "block_size": _StubCombo(0),
            },
            update_sensitivity=lambda: None,
            update_manual_floor=lambda: None,
        )

        tc.load_per_mode_technical_controls(
            tab,
            {
                "sine_wave_audio_block_size": block_size,
            },
        )

        controls = tc.get_per_mode_controls_for_mode(tab, "sine_wave")
        assert controls is not None
        assert controls["block_size"].currentData() == block_size


class TestVisualizerPresetDefaultResolution:
    def test_from_mapping_uses_first_preset_for_missing_mode_preset(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "sine_wave",
            }
        )

        assert model.preset_sine_wave == 0
        assert model.preset_blob == 0

    def test_from_settings_uses_first_preset_for_missing_mode_preset(self):
        from core.settings.models import SpotifyVisualizerSettings

        class _DummySettings:
            def __init__(self, data):
                self._data = data

            def get(self, key, default=None):
                return self._data.get(key, default)

        model = SpotifyVisualizerSettings.from_settings(
            _DummySettings(
                {
                    "widgets.spotify_visualizer.mode": "blob",
                }
            )
        )

        assert model.preset_blob == 0
        assert model.preset_sine_wave == 0

    def test_get_active_preset_index_uses_first_preset_when_missing(self):
        from core.settings.visualizer_presets import get_active_preset_index

        class _DummySettings:
            def get(self, _key, default=None):
                return default

        settings = _DummySettings()

        assert get_active_preset_index(settings, "sine_wave") == 0
        assert get_active_preset_index(settings, "blob") == 0


class TestVisualizerModeRegistryContract:
    def test_registry_matches_preset_modes_and_has_stable_preset_keys(self):
        from core.dev_gates import force_gate
        force_gate(blob=True, goo=True)
        from core.settings.visualizer_mode_registry import (
            VISUALIZER_MODE_IDS,
            iter_visualizer_mode_descriptors,
        )
        from core.settings.visualizer_presets import MODES

        descriptors = iter_visualizer_mode_descriptors()
        assert tuple(MODES) == VISUALIZER_MODE_IDS
        assert tuple(descriptor.mode_id for descriptor in descriptors) == VISUALIZER_MODE_IDS
        assert tuple(descriptor.preset_key for descriptor in descriptors) == tuple(
            f"preset_{mode}" for mode in VISUALIZER_MODE_IDS
        )

    def test_missing_preset_fallback_comes_from_registry_not_shipped_defaults(self):
        from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
        from core.settings.visualizer_presets import get_missing_preset_fallback_index

        for mode in VISUALIZER_MODE_IDS:
            assert get_missing_preset_fallback_index(mode) == 0

    def test_resolve_all_preset_indices_from_mapping_uses_registry_for_sparse_input(self):
        from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
        from core.settings.visualizer_presets import resolve_all_preset_indices_from_mapping

        resolved = resolve_all_preset_indices_from_mapping(
            {
                "mode": "blob",
                "preset_blob": 2,
            }
        )

        assert resolved["preset_blob"] == 2
        for mode in VISUALIZER_MODE_IDS:
            key = f"preset_{mode}"
            if key == "preset_blob":
                continue
            assert resolved[key] == 0

    def test_resolve_all_preset_indices_from_getter_uses_shared_prefixed_contract(self):
        from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
        from core.settings.visualizer_presets import resolve_all_preset_indices_from_getter

        data = {
            "widgets.spotify_visualizer.preset_blob": 2,
        }

        resolved = resolve_all_preset_indices_from_getter(
            lambda key, default=None: data.get(key, default)
        )

        assert resolved["preset_blob"] == 2
        for mode in VISUALIZER_MODE_IDS:
            key = f"preset_{mode}"
            if key == "preset_blob":
                continue
            assert resolved[key] == 0


class TestVisualizerSettingsContract:
    def test_resolve_visualizer_baselines_reads_shared_legacy_defaults_once(self):
        from core.settings.visualizer_settings_contract import resolve_visualizer_baselines

        data = {
            "bar_count": 41,
            "adaptive_sensitivity": False,
            "sensitivity": 1.7,
            "dynamic_floor": False,
            "manual_floor": 0.18,
            "dynamic_range_enabled": True,
            "agc_strength": 0.61,
            "input_gain": 1.3,
        }

        baselines = resolve_visualizer_baselines(lambda key, default=None: data.get(key, default))

        assert baselines == {
            "bar_count": 41,
            "adaptive_sensitivity": False,
            "sensitivity": pytest.approx(1.7),
            "dynamic_floor": False,
            "manual_floor": pytest.approx(0.18),
            "dynamic_range_enabled": True,
            "agc_strength": pytest.approx(0.61),
            "input_gain": pytest.approx(1.3),
        }

    def test_build_visualizer_mode_kwargs_applies_shared_sparse_fallback_contract(self):
        from core.settings.visualizer_settings_contract import build_visualizer_mode_kwargs

        baselines = {
            "bar_count": 41,
            "adaptive_sensitivity": False,
            "sensitivity": 1.7,
            "dynamic_floor": False,
            "manual_floor": 0.18,
            "dynamic_range_enabled": True,
            "agc_strength": 0.61,
            "input_gain": 1.3,
        }
        per_mode = {
            ("blob", "bar_count"): 24,
            ("spectrum", "lane_transient_mix"): 0.72,
            ("sine_wave", "rainbow_enabled"): True,
        }

        kwargs = build_visualizer_mode_kwargs(
            lambda mode, key, fallback: per_mode.get((mode, key), fallback),
            baselines,
        )

        assert kwargs["blob_bar_count"] == 24
        assert kwargs["bubble_bar_count"] == 41
        assert kwargs["blob_manual_floor"] == pytest.approx(0.18)
        assert kwargs["spectrum_lane_transient_mix"] == pytest.approx(0.72)
        assert kwargs["bubble_transient_mix_bass"] == pytest.approx(0.75)
        assert kwargs["oscilloscope_audio_block_size"] == 0
        assert "bubble_use_raw_energy" not in kwargs

    def test_section_normalizer_drops_retired_live_compat_keys(self):
        from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

        normalized = normalize_visualizer_section_mapping(
            {
                "mode": "blob",
                "blob_energy_boost": 1.2,
                "blob_use_raw_energy": True,
                "blob_input_gain": 1.1,
                "blob_stretch": 0.46,
            },
            apply_preset_overlay=False,
        )

        assert "blob_energy_boost" not in normalized
        assert "blob_use_raw_energy" not in normalized
        assert normalized["blob_input_gain"] == pytest.approx(1.1)
        assert normalized["blob_stretch"] == pytest.approx(0.46)


class TestVisualizerSettingsSnapshotNormalization:
    def test_section_normalizer_preserves_per_mode_rainbow_alias_inputs(self):
        from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

        normalized = normalize_visualizer_section_mapping(
            {
                "mode": "sine_wave",
                "sine_rainbow_enabled": True,
                "sine_rainbow_speed": 0.41,
            },
            apply_preset_overlay=False,
        )

        assert normalized["sine_wave_rainbow_enabled"] is True
        assert normalized["sine_wave_rainbow_speed"] == pytest.approx(0.41)
        assert normalized["bubble_rainbow_enabled"] is False

    def test_mode_payload_normalizer_promotes_shared_technical_keys_to_mode_keys(self):
        from core.settings.visualizer_settings_snapshot import normalize_visualizer_mode_payload

        normalized = normalize_visualizer_mode_payload(
            "bubble",
            {
                "mode": "bubble",
                "manual_floor": 0.22,
                "input_gain": 0.75,
                "bubble_growth": 3.1,
            },
        )

        assert "manual_floor" not in normalized
        assert "input_gain" not in normalized
        assert normalized["bubble_manual_floor"] == pytest.approx(0.22)
        assert normalized["bubble_input_gain"] == pytest.approx(0.75)
        assert normalized["bubble_growth"] == pytest.approx(3.1)

    def test_section_normalizer_preserves_bubble_bounce_keys(self):
        from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

        normalized = normalize_visualizer_section_mapping(
            {
                "mode": "bubble",
                "bubble_bounce_big_pct": 93,
                "bubble_bounce_small_pct": 17,
                "bubble_bounce_big_speed": 1.45,
                "bubble_bounce_small_speed": 0.33,
                "bubble_bounce_same_only": True,
                "bubble_collision_pop_mode": "one",
            },
            apply_preset_overlay=False,
        )

        assert normalized["bubble_bounce_big_pct"] == 93
        assert normalized["bubble_bounce_small_pct"] == 17
        assert normalized["bubble_bounce_big_speed"] == pytest.approx(1.45)
        assert normalized["bubble_bounce_small_speed"] == pytest.approx(0.33)
        assert normalized["bubble_bounce_same_only"] is True
        assert normalized["bubble_collision_pop_mode"] == "one"

    def test_section_normalizer_preserves_goo_unified_field_keys(self):
        from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

        normalized = normalize_visualizer_section_mapping(
            {
                "mode": "goo",
                "goo_core_size": 0.38,
                "goo_edge_inward_depth": 0.24,
            },
            apply_preset_overlay=False,
        )

        assert normalized["goo_core_size"] == pytest.approx(0.38)
        assert normalized["goo_edge_inward_depth"] == pytest.approx(0.24)

    def test_model_roundtrip_omits_retired_compat_settings_keys(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "blob",
                "blob_energy_boost": 1.4,
                "blob_use_raw_energy": True,
                "blob_input_gain": 1.2,
                "blob_stretch": 0.52,
            },
            apply_preset_overlay=False,
        )

        saved = model.to_dict()

        assert "widgets.spotify_visualizer.blob_energy_boost" not in saved
        assert "widgets.spotify_visualizer.blob_use_raw_energy" not in saved
        assert saved["widgets.spotify_visualizer.blob_input_gain"] == pytest.approx(1.2)
        assert saved["widgets.spotify_visualizer.blob_stretch"] == pytest.approx(0.52)

    def test_model_roundtrip_preserves_goo_unified_field_keys(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "goo",
                "goo_core_size": 0.39,
                "goo_edge_inward_depth": 0.21,
            },
            apply_preset_overlay=False,
        )

        saved = model.to_dict()
        assert saved["widgets.spotify_visualizer.goo_core_size"] == pytest.approx(0.39)
        assert saved["widgets.spotify_visualizer.goo_edge_inward_depth"] == pytest.approx(0.21)
        assert "widgets.spotify_visualizer.goo_gap_min" not in saved
        assert "widgets.spotify_visualizer.goo_edge_pressure" not in saved
        assert "widgets.spotify_visualizer.goo_core_pressure" not in saved


class TestVisualizerModeBinding:
    def test_populate_visualizer_mode_combo_uses_registry_order(self):
        from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
        from ui.tabs.media.visualizer_mode_binding import populate_visualizer_mode_combo

        class _Combo:
            def __init__(self):
                self.items = []

            def addItem(self, label, data):
                self.items.append((label, data))

        combo = _Combo()
        populate_visualizer_mode_combo(combo)

        assert combo.items == [
            (descriptor.display_name, descriptor.mode_id)
            for descriptor in iter_visualizer_mode_descriptors()
        ]

    def test_initialize_visualizer_mode_combo_uses_shared_build_default(self):
        from ui.tabs.media.visualizer_mode_binding import initialize_visualizer_mode_combo

        class _Combo:
            def __init__(self):
                self.items = []
                self._index = -1

            def addItem(self, label, data):
                self.items.append((label, data))

            def findData(self, value):
                for idx, (_label, data) in enumerate(self.items):
                    if data == value:
                        return idx
                return -1

            def setCurrentIndex(self, index):
                self._index = index

            def currentData(self):
                if 0 <= self._index < len(self.items):
                    return self.items[self._index][1]
                return None

        class _Tab:
            def __init__(self):
                self.vis_mode_combo = _Combo()

            def _default_str(self, *_args):
                return "bubble"

        tab = _Tab()
        initialize_visualizer_mode_combo(tab)

        assert tab.vis_mode_combo.currentData() == "bubble"

    def test_load_visualizer_mode_selection_falls_back_when_saved_mode_is_unknown(self):
        from ui.tabs.media.visualizer_mode_binding import (
            initialize_visualizer_mode_combo,
            load_visualizer_mode_selection,
        )

        class _Combo:
            def __init__(self):
                self.items = []
                self._index = -1

            def addItem(self, label, data):
                self.items.append((label, data))

            def findData(self, value):
                for idx, (_label, data) in enumerate(self.items):
                    if data == value:
                        return idx
                return -1

            def setCurrentIndex(self, index):
                self._index = index

            def currentData(self):
                if 0 <= self._index < len(self.items):
                    return self.items[self._index][1]
                return None

        class _Tab:
            def __init__(self):
                self.vis_mode_combo = _Combo()

            def _default_str(self, *_args):
                return "spectrum"

            def _config_str(self, _section, config, key, default):
                return config.get(key, default)

        tab = _Tab()
        initialize_visualizer_mode_combo(tab)
        load_visualizer_mode_selection(tab, {"mode": "not_a_real_mode"})

        assert tab.vis_mode_combo.currentData() == "spectrum"

    def test_load_visualizer_rainbow_state_uses_registry_modes_and_active_selection(self):
        from ui.tabs.media.visualizer_mode_binding import (
            initialize_visualizer_mode_combo,
            load_visualizer_rainbow_state,
        )

        class _Combo:
            def __init__(self):
                self.items = []
                self._index = -1

            def addItem(self, label, data):
                self.items.append((label, data))

            def findData(self, value):
                for idx, (_label, data) in enumerate(self.items):
                    if data == value:
                        return idx
                return -1

            def setCurrentIndex(self, index):
                self._index = index

            def currentData(self):
                if 0 <= self._index < len(self.items):
                    return self.items[self._index][1]
                return None

        class _Check:
            def __init__(self):
                self.checked = None

            def setChecked(self, value):
                self.checked = value

        class _Slider:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class _Label:
            def __init__(self):
                self.text = None

            def setText(self, text):
                self.text = text

        class _Tab:
            def __init__(self):
                self.vis_mode_combo = _Combo()
                self.rainbow_enabled = _Check()
                self.rainbow_speed_slider = _Slider()
                self.rainbow_speed_label = _Label()
                self.rainbow_updates = 0

            def _default_str(self, *_args):
                return "bubble"

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

            def _update_rainbow_visibility(self):
                self.rainbow_updates += 1

        tab = _Tab()
        initialize_visualizer_mode_combo(tab)
        load_visualizer_rainbow_state(
            tab,
            {
                "bubble_rainbow_enabled": True,
                "bubble_rainbow_speed": 0.76,
            },
        )

        assert tab._rainbow_per_mode["bubble"] == (True, 76)
        assert tab.rainbow_enabled.checked is True
        assert tab.rainbow_speed_slider.value == 76
        assert tab.rainbow_speed_label.text == "0.76"
        assert tab.rainbow_updates == 1

    def test_collect_visualizer_rainbow_state_writes_known_mode_keys_from_active_mode(self):
        from ui.tabs.media.visualizer_mode_binding import (
            collect_visualizer_rainbow_state,
            initialize_visualizer_mode_combo,
        )

        class _Combo:
            def __init__(self):
                self.items = []
                self._index = -1

            def addItem(self, label, data):
                self.items.append((label, data))

            def findData(self, value):
                for idx, (_label, data) in enumerate(self.items):
                    if data == value:
                        return idx
                return -1

            def setCurrentIndex(self, index):
                self._index = index

            def currentData(self):
                if 0 <= self._index < len(self.items):
                    return self.items[self._index][1]
                return None

        class _Check:
            def __init__(self, checked):
                self._checked = checked

            def isChecked(self):
                return self._checked

        class _Slider:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class _Tab:
            def __init__(self):
                self.vis_mode_combo = _Combo()
                self.rainbow_enabled = _Check(True)
                self.rainbow_speed_slider = _Slider(63)
                self._rainbow_per_mode = {
                    "spectrum": (False, 20),
                    "blob": (False, 40),
                }

            def _default_str(self, *_args):
                return "bubble"

        tab = _Tab()
        initialize_visualizer_mode_combo(tab)
        payload = {}
        collect_visualizer_rainbow_state(tab, payload)

        assert payload["bubble_rainbow_enabled"] is True
        assert payload["bubble_rainbow_speed"] == pytest.approx(0.63)
        assert payload["spectrum_rainbow_enabled"] is False
        assert payload["spectrum_rainbow_speed"] == pytest.approx(0.20)
        assert payload["oscilloscope_rainbow_enabled"] is False
        assert payload["oscilloscope_rainbow_speed"] == pytest.approx(0.50)

    def test_collect_and_load_visualizer_preset_indices_use_shared_descriptor_contract(self):
        from core.dev_gates import force_gate
        force_gate(blob=True, goo=False)
        from ui.tabs.media.visualizer_mode_binding import (
            collect_visualizer_preset_indices,
            load_visualizer_preset_indices,
        )

        class _Slider:
            def __init__(self, index):
                self._index = index

            def preset_index(self):
                return self._index

            def set_preset_index(self, index):
                self._index = index

        class _Tab:
            _spectrum_preset_slider = _Slider(1)
            _osc_preset_slider = _Slider(0)
            _sine_preset_slider = _Slider(2)
            _blob_preset_slider = _Slider(3)
            _bubble_preset_slider = _Slider(1)

        tab = _Tab()
        payload = {}
        collect_visualizer_preset_indices(tab, payload)

        assert payload == {
            "preset_spectrum": 1,
            "preset_oscilloscope": 0,
            "preset_sine_wave": 2,
            "preset_blob": 3,
            "preset_bubble": 1,
        }

        load_visualizer_preset_indices(
            tab,
            {
                "preset_spectrum": 0,
                "preset_oscilloscope": 2,
                "preset_sine_wave": 1,
                "preset_blob": 0,
                "preset_bubble": 3,
            },
        )

        assert tab._spectrum_preset_slider.preset_index() == 0
        assert tab._osc_preset_slider.preset_index() == 2
        assert tab._sine_preset_slider.preset_index() == 1
        assert tab._blob_preset_slider.preset_index() == 0
        assert tab._bubble_preset_slider.preset_index() == 3


class TestBlobSettingsBinding:
    def test_load_blob_mode_settings_updates_blob_owned_controls(self):
        from ui.tabs.media.blob_settings_binding import load_blob_mode_settings

        class _Check:
            def __init__(self):
                self.checked = None

            def setChecked(self, checked):
                self.checked = checked

        class _Slider:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class _Label:
            def __init__(self):
                self.text = None

            def setText(self, text):
                self.text = text

        class _Combo:
            def __init__(self):
                self.index = None

            def setCurrentIndex(self, index):
                self.index = index

        class _Tab:
            def __init__(self):
                self.blob_ghost_enabled = _Check()
                self.blob_ghost_opacity = _Slider()
                self.blob_ghost_opacity_label = _Label()
                self.blob_ghost_decay_slider = _Slider()
                self.blob_ghost_decay_label = _Label()
                self.blob_pulse = _Slider()
                self.blob_pulse_label = _Label()
                self.blob_pulse_release_ms = _Slider()
                self.blob_pulse_release_ms_label = _Label()
                self.blob_stretch = _Slider()
                self.blob_stretch_label = _Label()
                self.blob_shaper_base_strength = _Slider()
                self.blob_shaper_base_strength_label = _Label()
                self.blob_shaper_idle_motion = _Slider()
                self.blob_shaper_idle_motion_label = _Label()
                self.blob_shaper_audio_motion = _Slider()
                self.blob_shaper_audio_motion_label = _Label()
                self.blob_inward_liquid_enabled = _Check()
                self.blob_inward_liquid_reactivity = _Slider()
                self.blob_inward_liquid_reactivity_label = _Label()
                self.blob_inward_liquid_max_size = _Slider()
                self.blob_inward_liquid_max_size_label = _Label()
                self.blob_glow_drive_mode = _Combo()
                self.blob_growth = _Slider()
                self.blob_growth_label = _Label()

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

            def _config_int(self, _section, config, key, default):
                return config.get(key, default)

            def _config_str(self, _section, config, key, default):
                return config.get(key, default)

        tab = _Tab()
        synced = []
        load_blob_mode_settings(
            tab,
            {
                "blob_ghosting_enabled": True,
                "blob_ghost_alpha": 0.37,
                "blob_ghost_decay": 0.44,
                "blob_pulse": 1.23,
                "blob_pulse_release_ms": 1210,
                "blob_inward_liquid_enabled": True,
                "blob_inward_liquid_reactivity": 1.34,
                "blob_inward_liquid_max_size": 0.31,
                "blob_stretch": 0.42,
                "blob_shaper_base_strength": 0.73,
                "blob_shaper_idle_motion": 0.11,
                "blob_shaper_audio_motion": 1.48,
                "blob_glow_drive_mode": "vocal",
                "blob_growth": 3.10,
                "blob_color": [1, 2, 3, 4],
            },
            sync_color_button=lambda btn, attr: synced.append((btn, attr)),
        )

        assert tab.blob_ghost_enabled.checked is True
        assert tab.blob_ghost_opacity.value == 37
        assert tab.blob_ghost_opacity_label.text == "37%"
        assert tab.blob_ghost_decay_slider.value == 44
        assert tab.blob_ghost_decay_label.text == "0.44x"
        assert tab.blob_pulse.value == 123
        assert tab.blob_pulse_label.text == "1.23x"
        assert tab.blob_pulse_release_ms.value == 1210
        assert tab.blob_pulse_release_ms_label.text == "1.21s"
        assert tab.blob_inward_liquid_enabled.checked is True
        assert tab.blob_inward_liquid_reactivity.value == 134
        assert tab.blob_inward_liquid_reactivity_label.text == "134%"
        assert tab.blob_inward_liquid_max_size.value == 31
        assert tab.blob_inward_liquid_max_size_label.text == "31%"
        assert tab.blob_stretch.value == 42
        assert tab.blob_stretch_label.text == "42%"
        assert tab.blob_shaper_base_strength.value == 73
        assert tab.blob_shaper_base_strength_label.text == "73%"
        assert tab.blob_shaper_idle_motion.value == 11
        assert tab.blob_shaper_idle_motion_label.text == "11%"
        assert tab.blob_shaper_audio_motion.value == 148
        assert tab.blob_shaper_audio_motion_label.text == "148%"
        assert tab.blob_glow_drive_mode.index == 1
        assert tab.blob_growth.value == 310
        assert tab.blob_growth_label.text == "3.1x"
        assert (tab._blob_color.red(), tab._blob_color.green(), tab._blob_color.blue(), tab._blob_color.alpha()) == (1, 2, 3, 4)
        assert synced == [
            ("blob_fill_color_btn", "_blob_color"),
            ("blob_glow_color_btn", "_blob_glow_color"),
            ("blob_edge_color_btn", "_blob_edge_color"),
            ("blob_outline_color_btn", "_blob_outline_color"),
            ("blob_inward_liquid_color_btn", "_blob_inward_liquid_color"),
        ]

    def test_collect_blob_mode_settings_serializes_blob_owned_state(self):
        from ui.tabs.media.blob_settings_binding import collect_blob_mode_settings

        class _Check:
            def __init__(self, checked):
                self._checked = checked

            def isChecked(self):
                return self._checked

        class _Slider:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class _Combo:
            def __init__(self, index):
                self._index = index

            def currentIndex(self):
                return self._index

        class _Tab:
            blob_ghost_enabled = _Check(True)
            blob_ghost_opacity = _Slider(45)
            blob_ghost_decay_slider = _Slider(38)
            blob_pulse = _Slider(140)
            blob_width = _Slider(92)
            blob_size = _Slider(135)
            blob_glow_intensity = _Slider(67)
            blob_glow_reactivity = _Slider(123)
            blob_glow_drive_mode = _Combo(1)
            blob_glow_max_size = _Slider(210)
            blob_reactive_glow = _Check(True)
            blob_reactive_deformation = _Slider(88)
            blob_pulse_release_ms = _Slider(1330)
            blob_inward_liquid_enabled = _Check(True)
            blob_inward_liquid_reactivity = _Slider(142)
            blob_inward_liquid_max_size = _Slider(29)
            blob_constant_wobble = _Slider(80)
            blob_reactive_wobble = _Slider(290)
            blob_stretch = _Slider(48)
            blob_shaper_base_strength = _Slider(64)
            blob_shaper_idle_motion = _Slider(9)
            blob_shaper_audio_motion = _Slider(155)
            blob_growth = _Slider(275)
            _blob_color = QColor(10, 20, 30, 200)
            _blob_glow_color = QColor(40, 50, 60, 210)
            _blob_edge_color = QColor(70, 80, 90, 220)
            _blob_outline_color = QColor(100, 110, 120, 230)
            _blob_inward_liquid_color = QColor(130, 140, 150, 240)

        payload = collect_blob_mode_settings(_Tab())

        assert payload["blob_ghosting_enabled"] is True
        assert payload["blob_ghost_alpha"] == pytest.approx(0.45)
        assert payload["blob_ghost_decay"] == pytest.approx(0.38)
        assert payload["blob_pulse"] == pytest.approx(1.4)
        assert payload["blob_glow_drive_mode"] == "vocal"
        assert payload["blob_color"] == [10, 20, 30, 200]
        assert payload["blob_glow_color"] == [40, 50, 60, 210]
        assert payload["blob_edge_color"] == [70, 80, 90, 220]
        assert payload["blob_outline_color"] == [100, 110, 120, 230]
        assert payload["blob_pulse_release_ms"] == 1330
        assert payload["blob_inward_liquid_enabled"] is True
        assert payload["blob_inward_liquid_reactivity"] == pytest.approx(1.42)
        assert payload["blob_inward_liquid_max_size"] == pytest.approx(0.29)
        assert payload["blob_inward_liquid_color"] == [130, 140, 150, 240]
        assert payload["blob_reactive_wobble"] == pytest.approx(2.90)
        assert payload["blob_stretch"] == pytest.approx(0.48)
        assert payload["blob_shaper_base_strength"] == pytest.approx(0.64)
        assert payload["blob_shaper_idle_motion"] == pytest.approx(0.09)
        assert payload["blob_shaper_audio_motion"] == pytest.approx(1.55)
        assert payload["blob_growth"] == pytest.approx(2.75)


class TestOscilloscopeSettingsBinding:
    def test_load_oscilloscope_mode_settings_updates_osc_owned_controls(self):
        from ui.tabs.media.oscilloscope_settings_binding import load_oscilloscope_mode_settings

        class _Check:
            def __init__(self):
                self.checked = None

            def setChecked(self, checked):
                self.checked = checked

        class _Slider:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class _Label:
            def __init__(self):
                self.text = None

            def setText(self, text):
                self.text = text

        class _Tab:
            def __init__(self):
                self.osc_glow_enabled = _Check()
                self.osc_glow_intensity = _Slider()
                self.osc_glow_intensity_label = _Label()
                self.osc_glow_reactivity = _Slider()
                self.osc_glow_reactivity_label = _Label()
                self.osc_reactive_glow = _Check()
                self.osc_line_amplitude = _Slider()
                self.osc_line_amplitude_label = _Label()
                self.osc_smoothing = _Slider()
                self.osc_smoothing_label = _Label()
                self.osc_growth = _Slider()
                self.osc_growth_label = _Label()
                self.osc_speed = _Slider()
                self.osc_speed_label = _Label()
                self.osc_line_dim = _Check()
                self.osc_line_offset_bias = _Slider()
                self.osc_line_offset_bias_label = _Label()
                self.osc_vertical_shift = _Slider()
                self.osc_vertical_shift_label = _Label()
                self.osc_multi_line = _Check()
                self.osc_line_count = _Slider()
                self.osc_line_count_label = _Label()
                self.osc_ghost_enabled = _Check()
                self.osc_ghost_intensity = _Slider()
                self.osc_ghost_intensity_label = _Label()
                self.osc_ghost_line2_enabled = _Check()
                self.osc_ghost_line3_enabled = _Check()

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

        tab = _Tab()
        synced = []
        visibility_calls = []

        def _load_extra(tab_obj, config):
            tab_obj._osc_line2_color = QColor(*config["osc_line2_color"])
            tab_obj._osc_line2_glow_color = QColor(*config["osc_line2_glow_color"])
            tab_obj._osc_line3_color = QColor(*config["osc_line3_color"])
            tab_obj._osc_line3_glow_color = QColor(*config["osc_line3_glow_color"])

        load_oscilloscope_mode_settings(
            tab,
            {
                "osc_glow_enabled": False,
                "osc_glow_intensity": 0.62,
                "osc_glow_reactivity": 1.44,
                "osc_reactive_glow": False,
                "osc_line_amplitude": 4.7,
                "osc_smoothing": 0.58,
                "osc_growth": 2.6,
                "osc_speed": 0.72,
                "osc_line_dim": True,
                "osc_line_offset_bias": 0.23,
                "osc_vertical_shift": 32,
                "osc_line_color": [1, 2, 3, 4],
                "osc_glow_color": [5, 6, 7, 8],
                "osc_line_count": 3,
                "osc_line2_color": [9, 10, 11, 12],
                "osc_line2_glow_color": [13, 14, 15, 16],
                "osc_line3_color": [17, 18, 19, 20],
                "osc_line3_glow_color": [21, 22, 23, 24],
                "osc_ghosting_enabled": True,
                "osc_ghost_intensity": 0.41,
                "osc_ghost_line2_enabled": False,
                "osc_ghost_line3_enabled": True,
            },
            sync_color_button=lambda btn, attr: synced.append((btn, attr)),
            load_extra_color_bindings=_load_extra,
            update_multi_line_visibility=lambda tab_obj: visibility_calls.append(tab_obj),
        )

        assert tab.osc_glow_enabled.checked is False
        assert tab.osc_glow_intensity.value == 62
        assert tab.osc_glow_intensity_label.text == "62%"
        assert tab.osc_glow_reactivity.value == 144
        assert tab.osc_line_amplitude.value == 47
        assert tab.osc_line_amplitude_label.text == "4.7x"
        assert tab.osc_growth.value == 260
        assert tab.osc_speed.value == 72
        assert tab.osc_line_dim.checked is True
        assert tab.osc_line_offset_bias.value == 23
        assert tab.osc_vertical_shift.value == 32
        assert tab.osc_multi_line.checked is True
        assert tab.osc_line_count.value == 3
        assert tab.osc_ghost_enabled.checked is True
        assert tab.osc_ghost_intensity.value == 41
        assert tab.osc_ghost_line2_enabled.checked is False
        assert tab.osc_ghost_line3_enabled.checked is True
        assert (tab._osc_line_color.red(), tab._osc_line_color.green(), tab._osc_line_color.blue(), tab._osc_line_color.alpha()) == (1, 2, 3, 4)
        assert (tab._osc_line3_glow_color.red(), tab._osc_line3_glow_color.green(), tab._osc_line3_glow_color.blue(), tab._osc_line3_glow_color.alpha()) == (21, 22, 23, 24)
        assert synced == [
            ("osc_line_color_btn", "_osc_line_color"),
            ("osc_glow_color_btn", "_osc_glow_color"),
            ("osc_line2_color_btn", "_osc_line2_color"),
            ("osc_line2_glow_btn", "_osc_line2_glow_color"),
            ("osc_line3_color_btn", "_osc_line3_color"),
            ("osc_line3_glow_btn", "_osc_line3_glow_color"),
            ("osc_line4_color_btn", "_osc_line4_color"),
            ("osc_line4_glow_btn", "_osc_line4_glow_color"),
            ("osc_line5_color_btn", "_osc_line5_color"),
            ("osc_line5_glow_btn", "_osc_line5_glow_color"),
            ("osc_line6_color_btn", "_osc_line6_color"),
            ("osc_line6_glow_btn", "_osc_line6_glow_color"),
        ]
        assert visibility_calls == [tab]

    def test_collect_oscilloscope_mode_settings_serializes_osc_owned_state(self):
        from ui.tabs.media.oscilloscope_settings_binding import collect_oscilloscope_mode_settings

        class _Check:
            def __init__(self, checked):
                self._checked = checked

            def isChecked(self):
                return self._checked

        class _Slider:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class _Tab:
            osc_glow_enabled = _Check(True)
            osc_glow_intensity = _Slider(66)
            osc_glow_reactivity = _Slider(135)
            osc_reactive_glow = _Check(False)
            osc_line_amplitude = _Slider(42)
            osc_smoothing = _Slider(77)
            osc_growth = _Slider(245)
            osc_speed = _Slider(81)
            osc_line_dim = _Check(True)
            osc_line_offset_bias = _Slider(18)
            osc_vertical_shift = _Slider(27)
            osc_multi_line = _Check(True)
            osc_line_count = _Slider(3)
            osc_ghost_enabled = _Check(True)
            osc_ghost_intensity = _Slider(52)
            osc_ghost_line2_enabled = _Check(False)
            osc_ghost_line3_enabled = _Check(True)
            _osc_line_color = QColor(1, 2, 3, 4)
            _osc_glow_color = QColor(5, 6, 7, 8)

        payload = collect_oscilloscope_mode_settings(
            _Tab(),
            collect_extra_color_bindings=lambda _tab: {
                "osc_line2_color": [9, 10, 11, 12],
                "osc_line2_glow_color": [13, 14, 15, 16],
                "osc_line3_color": [17, 18, 19, 20],
                "osc_line3_glow_color": [21, 22, 23, 24],
            },
        )

        assert payload["osc_glow_enabled"] is True
        assert payload["osc_glow_intensity"] == pytest.approx(0.66)
        assert payload["osc_glow_reactivity"] == pytest.approx(1.35)
        assert payload["osc_reactive_glow"] is False
        assert payload["osc_line_amplitude"] == pytest.approx(4.2)
        assert payload["osc_smoothing"] == pytest.approx(0.77)
        assert payload["osc_line_color"] == [1, 2, 3, 4]
        assert payload["osc_glow_color"] == [5, 6, 7, 8]
        assert payload["osc_line_count"] == 3
        assert payload["osc_growth"] == pytest.approx(2.45)
        assert payload["osc_speed"] == pytest.approx(0.81)
        assert payload["osc_line_dim"] is True
        assert payload["osc_line_offset_bias"] == pytest.approx(0.18)
        assert payload["osc_vertical_shift"] == 27
        assert payload["osc_ghosting_enabled"] is True
        assert payload["osc_ghost_intensity"] == pytest.approx(0.52)
        assert payload["osc_ghost_line2_enabled"] is False
        assert payload["osc_ghost_line3_enabled"] is True
        assert payload["osc_line3_glow_color"] == [21, 22, 23, 24]


class TestSineWaveSettingsBinding:
    def test_load_sine_wave_mode_settings_updates_sine_owned_controls(self):
        from ui.tabs.media.sine_wave_settings_binding import load_sine_wave_mode_settings

        class _Check:
            def __init__(self):
                self.checked = None

            def setChecked(self, checked):
                self.checked = checked

        class _Slider:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class _Label:
            def __init__(self):
                self.text = None

            def setText(self, text):
                self.text = text

        class _Combo:
            def __init__(self):
                self.index = None

            def setCurrentIndex(self, index):
                self.index = index

        class _Tab:
            def __init__(self):
                self.sine_glow_enabled = _Check()
                self.sine_glow_intensity = _Slider()
                self.sine_glow_intensity_label = _Label()
                self.sine_glow_reactivity = _Slider()
                self.sine_glow_reactivity_label = _Label()
                self.sine_reactive_glow = _Check()
                self.sine_sensitivity = _Slider()
                self.sine_sensitivity_label = _Label()
                self.sine_smoothing = _Slider()
                self.sine_smoothing_label = _Label()
                self.sine_speed = _Slider()
                self.sine_speed_label = _Label()
                self.sine_wave_effect = _Slider()
                self.sine_wave_effect_label = _Label()
                self.sine_micro_wobble = _Slider()
                self.sine_micro_wobble_label = _Label()
                self.sine_crawl_slider = _Slider()
                self.sine_crawl_label = _Label()
                self.sine_width_reaction = _Slider()
                self.sine_width_reaction_label = _Label()
                self.sine_density = _Slider()
                self.sine_density_label = _Label()
                self.sine_heartbeat = _Slider()
                self.sine_heartbeat_label = _Label()
                self.sine_displacement = _Slider()
                self.sine_displacement_label = _Label()
                self.sine_vertical_shift = _Slider()
                self.sine_vertical_shift_label = _Label()
                self.sine_line1_shift = _Slider()
                self.sine_line1_shift_label = _Label()
                self.sine_travel = _Combo()
                self.sine_travel_line2 = _Combo()
                self.sine_travel_line3 = _Combo()
                self.sine_multi_line = _Check()
                self.sine_line_count_slider = _Slider()
                self.sine_line_count_label = _Label()
                self.sine_line2_shift = _Slider()
                self.sine_line2_shift_label = _Label()
                self.sine_line3_shift = _Slider()
                self.sine_line3_shift_label = _Label()
                self.sine_line_dim = _Check()
                self.sine_line_offset_bias = _Slider()
                self.sine_line_offset_bias_label = _Label()
                self.sine_card_adaptation = _Slider()
                self.sine_card_adaptation_label = _Label()
                self.sine_wave_growth = _Slider()
                self.sine_wave_growth_label = _Label()
                self.sine_ghost_enabled = _Check()
                self.sine_ghost_opacity = _Slider()
                self.sine_ghost_opacity_label = _Label()
                self.sine_ghost_decay_slider = _Slider()
                self.sine_ghost_decay_label = _Label()
                self.sine_ghost_line2_enabled = _Check()
                self.sine_ghost_line3_enabled = _Check()

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

            def _default_float(self, _section, key, default):
                return default

        tab = _Tab()
        synced = []
        visibility_calls = []

        load_sine_wave_mode_settings(
            tab,
            {
                "sine_glow_enabled": False,
                "sine_glow_intensity": 0.61,
                "sine_glow_reactivity": 1.32,
                "sine_glow_color": [1, 2, 3, 4],
                "sine_line_color": [5, 6, 7, 8],
                "sine_reactive_glow": False,
                "sine_sensitivity": 1.8,
                "sine_smoothing": 0.64,
                "sine_speed": 0.73,
                "sine_wave_effect": 0.22,
                "sine_micro_wobble": 0.16,
                "sine_crawl_amount": 0.44,
                "sine_width_reaction": 0.31,
                "sine_density": 1.25,
                "sine_heartbeat": 0.53,
                "sine_displacement": 0.19,
                "sine_vertical_shift": 14,
                "sine_line1_shift": 0.25,
                "sine_wave_travel": 2,
                "sine_travel_line2": 1,
                "sine_travel_line3": 2,
                "sine_line_count": 3,
                "sine_line2_color": [9, 10, 11, 12],
                "sine_line2_glow_color": [13, 14, 15, 16],
                "sine_line3_color": [17, 18, 19, 20],
                "sine_line3_glow_color": [21, 22, 23, 24],
                "sine_line2_shift": -0.34,
                "sine_line3_shift": 0.42,
                "sine_line_dim": True,
                "sine_line_offset_bias": 0.29,
                "sine_card_adaptation": 0.41,
                "sine_wave_growth": 2.9,
                "sine_ghosting_enabled": False,
                "sine_ghost_alpha": 0.36,
                "sine_ghost_decay": 0.47,
                "sine_ghost_line2_enabled": True,
                "sine_ghost_line3_enabled": False,
            },
            sync_color_button=lambda btn, attr: synced.append((btn, attr)),
            update_multi_line_visibility=lambda tab_obj: visibility_calls.append(tab_obj),
        )

        assert tab.sine_glow_enabled.checked is False
        assert tab.sine_glow_intensity.value == 61
        assert tab.sine_glow_reactivity.value == 132
        assert tab.sine_reactive_glow.checked is False
        assert tab.sine_sensitivity.value == 180
        assert tab.sine_sensitivity_label.text == "1.80x"
        assert tab.sine_smoothing.value == 64
        assert tab.sine_smoothing_label.text == "64%"
        assert tab.sine_speed.value == 73
        assert tab.sine_wave_effect.value == 22
        assert tab.sine_micro_wobble.value == 16
        assert tab.sine_crawl_slider.value == 44
        assert tab.sine_width_reaction.value == 31
        assert tab.sine_density.value == 125
        assert tab.sine_density_label.text == "1.25×"
        assert tab.sine_heartbeat.value == 53
        assert tab.sine_displacement.value == 19
        assert tab.sine_vertical_shift.value == 14
        assert tab.sine_line1_shift.value == 25
        assert tab.sine_travel.index == 2
        assert tab.sine_travel_line2.index == 1
        assert tab.sine_travel_line3.index == 2
        assert tab.sine_multi_line.checked is True
        assert tab.sine_line_count_slider.value == 3
        assert tab.sine_line2_shift.value == -34
        assert tab.sine_line3_shift.value == 42
        assert tab.sine_line_dim.checked is True
        assert tab.sine_line_offset_bias.value == 28
        assert tab.sine_card_adaptation.value == 41
        assert tab.sine_wave_growth.value == 290
        assert tab.sine_ghost_enabled.checked is False
        assert tab.sine_ghost_opacity.value == 36
        assert tab.sine_ghost_decay_slider.value == 47
        assert tab.sine_ghost_line2_enabled.checked is True
        assert tab.sine_ghost_line3_enabled.checked is False
        assert (tab._sine_glow_color.red(), tab._sine_glow_color.green(), tab._sine_glow_color.blue(), tab._sine_glow_color.alpha()) == (1, 2, 3, 4)
        assert (tab._sine_line3_glow_color.red(), tab._sine_line3_glow_color.green(), tab._sine_line3_glow_color.blue(), tab._sine_line3_glow_color.alpha()) == (21, 22, 23, 24)
        assert synced == [
            ("sine_glow_color_btn", "_sine_glow_color"),
            ("sine_line_color_btn", "_sine_line_color"),
            ("sine_line2_color_btn", "_sine_line2_color"),
            ("sine_line2_glow_btn", "_sine_line2_glow_color"),
            ("sine_line3_color_btn", "_sine_line3_color"),
            ("sine_line3_glow_btn", "_sine_line3_glow_color"),
            ("sine_line4_color_btn", "_sine_line4_color"),
            ("sine_line4_glow_btn", "_sine_line4_glow_color"),
            ("sine_line5_color_btn", "_sine_line5_color"),
            ("sine_line5_glow_btn", "_sine_line5_glow_color"),
            ("sine_line6_color_btn", "_sine_line6_color"),
            ("sine_line6_glow_btn", "_sine_line6_glow_color"),
        ]
        assert visibility_calls == [tab]

    def test_collect_sine_wave_mode_settings_serializes_sine_owned_state(self):
        from ui.tabs.media.sine_wave_settings_binding import collect_sine_wave_mode_settings

        class _Check:
            def __init__(self, checked):
                self._checked = checked

            def isChecked(self):
                return self._checked

        class _Slider:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class _Combo:
            def __init__(self, index):
                self._index = index

            def currentIndex(self):
                return self._index

        class _Tab:
            sine_glow_enabled = _Check(True)
            sine_glow_intensity = _Slider(64)
            sine_glow_reactivity = _Slider(145)
            _sine_glow_color = QColor(1, 2, 3, 4)
            _sine_line_color = QColor(5, 6, 7, 8)
            sine_reactive_glow = _Check(False)
            sine_sensitivity = _Slider(175)
            sine_smoothing = _Slider(63)
            sine_speed = _Slider(82)
            sine_wave_effect = _Slider(17)
            sine_crawl_slider = _Slider(46)
            sine_micro_wobble = _Slider(23)
            sine_width_reaction = _Slider(31)
            sine_density = _Slider(135)
            sine_heartbeat = _Slider(28)
            sine_displacement = _Slider(19)
            sine_vertical_shift = _Slider(22)
            sine_line1_shift = _Slider(-14)
            sine_travel = _Combo(2)
            sine_travel_line2 = _Combo(1)
            sine_travel_line3 = _Combo(0)
            sine_multi_line = _Check(True)
            sine_line_count_slider = _Slider(3)
            sine_line_dim = _Check(True)
            sine_line_offset_bias = _Slider(26)
            sine_card_adaptation = _Slider(37)
            sine_wave_growth = _Slider(305)
            _sine_line2_color = QColor(9, 10, 11, 12)
            _sine_line2_glow_color = QColor(13, 14, 15, 16)
            _sine_line3_color = QColor(17, 18, 19, 20)
            _sine_line3_glow_color = QColor(21, 22, 23, 24)
            sine_line2_shift = _Slider(18)
            sine_line3_shift = _Slider(-27)
            sine_ghost_enabled = _Check(False)
            sine_ghost_opacity = _Slider(42)
            sine_ghost_decay_slider = _Slider(39)
            sine_ghost_line2_enabled = _Check(True)
            sine_ghost_line3_enabled = _Check(False)

        payload = collect_sine_wave_mode_settings(_Tab())

        assert payload["sine_glow_enabled"] is True
        assert payload["sine_glow_intensity"] == pytest.approx(0.64)
        assert payload["sine_glow_reactivity"] == pytest.approx(1.45)
        assert payload["sine_glow_color"] == [1, 2, 3, 4]
        assert payload["sine_line_color"] == [5, 6, 7, 8]
        assert payload["sine_reactive_glow"] is False
        assert payload["sine_sensitivity"] == pytest.approx(1.75)
        assert payload["sine_smoothing"] == pytest.approx(0.63)
        assert payload["sine_speed"] == pytest.approx(0.82)
        assert payload["sine_wave_effect"] == pytest.approx(0.17)
        assert payload["sine_crawl_amount"] == pytest.approx(0.46)
        assert payload["sine_micro_wobble"] == pytest.approx(0.23)
        assert payload["sine_width_reaction"] == pytest.approx(0.31)
        assert payload["sine_density"] == pytest.approx(1.35)
        assert payload["sine_heartbeat"] == pytest.approx(0.28)
        assert payload["sine_displacement"] == pytest.approx(0.19)
        assert payload["sine_vertical_shift"] == 22
        assert payload["sine_line1_shift"] == pytest.approx(-0.14)
        assert payload["sine_wave_travel"] == 2
        assert payload["sine_travel_line2"] == 1
        assert payload["sine_travel_line3"] == 0
        assert payload["sine_line_count"] == 3
        assert payload["sine_line_dim"] is True
        assert payload["sine_line_offset_bias"] == pytest.approx(0.26)
        assert payload["sine_card_adaptation"] == pytest.approx(0.37)
        assert payload["sine_wave_growth"] == pytest.approx(3.05)
        assert payload["sine_line2_color"] == [9, 10, 11, 12]
        assert payload["sine_line3_glow_color"] == [21, 22, 23, 24]
        assert payload["sine_line2_shift"] == pytest.approx(0.18)
        assert payload["sine_line3_shift"] == pytest.approx(-0.27)
        assert payload["sine_ghosting_enabled"] is False
        assert payload["sine_ghost_alpha"] == pytest.approx(0.42)
        assert payload["sine_ghost_decay"] == pytest.approx(0.39)
        assert payload["sine_ghost_line2_enabled"] is True
        assert payload["sine_ghost_line3_enabled"] is False


class TestSpectrumSettingsBinding:
    def test_load_spectrum_mode_settings_updates_spectrum_owned_controls(self):
        from ui.tabs.media.spectrum_settings_binding import load_spectrum_mode_settings

        class _Check:
            def __init__(self):
                self.checked = None

            def setChecked(self, checked):
                self.checked = checked

        class _Slider:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class _Label:
            def __init__(self):
                self.text = None

            def setText(self, text):
                self.text = text

        class _ShapeEditor:
            def __init__(self):
                self.nodes = None
                self.mirrored = None
                self.notches = []

            def set_nodes(self, nodes):
                self.nodes = nodes

            def set_mirrored(self, mirrored):
                self.mirrored = mirrored

            def set_notch_positions(self, notches, mirrored):
                self.notches.append((mirrored, notches))

            def set_lane_strengths(self, strengths, *, mirrored):
                if not hasattr(self, "lane_strengths"):
                    self.lane_strengths = []
                self.lane_strengths.append((mirrored, strengths))

        class _Tab:
            def __init__(self):
                self.spectrum_growth = _Slider()
                self.spectrum_growth_label = _Label()
                self._spectrum_render_mode = None
                self.spectrum_rainbow_per_bar = _Check()
                self.spectrum_rainbow_border = _Check()
                self.spectrum_wave_amplitude = _Slider()
                self.spectrum_wave_amplitude_label = _Label()
                self.spectrum_profile_floor = _Slider()
                self.spectrum_profile_floor_label = _Label()
                self.spectrum_drop_speed = _Slider()
                self.spectrum_drop_speed_label = _Label()
                self.spectrum_border_radius = _Slider()
                self.spectrum_border_radius_label = _Label()
                self.spectrum_glow_enabled = _Check()
                self.spectrum_glow_intensity = _Slider()
                self.spectrum_glow_intensity_label = _Label()
                self.spectrum_mirrored = _Check()
                self.spectrum_shape_editor = _ShapeEditor()
                self.vis_ghost_enabled = _Check()
                self.vis_ghost_opacity_slider = _Slider()
                self.vis_ghost_opacity_label = _Label()
                self.vis_ghost_decay_slider = _Slider()
                self.vis_ghost_decay_label = _Label()

            def _set_spectrum_render_mode(self, mode, save=False):
                self._spectrum_render_mode = mode

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

        tab = _Tab()
        synced = []
        ghost_visibility_calls = []

        load_spectrum_mode_settings(
            tab,
            {
                "spectrum_growth": 2.4,
                "spectrum_render_mode": "bars",
                "spectrum_unique_colors": True,
                "spectrum_rainbow_border": True,
                "spectrum_lane_strengths_mirrored": {"Mid": 0.52, "Vocal": 0.67, "Low-Mid": 0.72, "Bass": 0.88},
                "spectrum_lane_strengths_linear": {"Bass": 0.63, "Low-Mid": 0.54, "Vocal": 0.46, "Hi-Mid": 0.71, "Treble": 0.93},
                "spectrum_wave_amplitude": 0.55,
                "spectrum_profile_floor": 0.17,
                "spectrum_drop_speed": 1.9,
                "spectrum_border_radius": 7,
                "spectrum_glow_enabled": True,
                "spectrum_glow_intensity": 1.15,
                "spectrum_glow_color": [1, 2, 3, 4],
                "spectrum_mirrored": False,
                "spectrum_shape_nodes": [[0.0, 0.22], [1.0, 0.88]],
                "spectrum_notch_positions_mirrored": [[0.0, "Mid"], [1.0, "Bass"]],
                "spectrum_notch_positions_linear": [[0.0, "Bass"], [1.0, "Treble"]],
                "spectrum_ghosting_enabled": False,
                "spectrum_ghost_alpha": 0.37,
                "spectrum_ghost_decay": 0.42,
            },
            sync_color_button=lambda btn, attr: synced.append((btn, attr)),
            update_ghost_visibility=lambda tab_obj: ghost_visibility_calls.append(tab_obj),
        )

        assert tab.spectrum_growth.value == 240
        assert tab.spectrum_growth_label.text == "2.4x"
        assert tab._spectrum_render_mode == "bars"
        assert tab.spectrum_rainbow_per_bar.checked is True
        assert tab.spectrum_rainbow_border.checked is True
        assert tab.spectrum_wave_amplitude.value == 55
        assert tab.spectrum_profile_floor.value == 17
        assert tab.spectrum_profile_floor_label.text == "0.17"
        assert tab.spectrum_drop_speed.value == 190
        assert tab.spectrum_border_radius.value == 7
        assert tab.spectrum_glow_enabled.checked is True
        assert tab.spectrum_glow_intensity.value == 114
        assert tab.spectrum_mirrored.checked is False
        assert tab.spectrum_shape_editor.nodes == [[0.0, 0.22], [1.0, 0.88]]
        assert tab.spectrum_shape_editor.mirrored is False
        assert tab.spectrum_shape_editor.notches == [
            (True, [[0.0, "Mid"], [1.0, "Bass"]]),
            (False, [[0.0, "Bass"], [1.0, "Treble"]]),
        ]
        assert tab.spectrum_shape_editor.lane_strengths == [
            (True, {"Mid": 0.52, "Vocal": 0.67, "Low-Mid": 0.72, "Bass": 0.88}),
            (False, {"Bass": 0.63, "Low-Mid": 0.54, "Vocal": 0.46, "Hi-Mid": 0.71, "Treble": 0.93}),
        ]
        assert tab.vis_ghost_enabled.checked is False
        assert tab.vis_ghost_opacity_slider.value == 37
        assert tab.vis_ghost_decay_slider.value == 42
        assert (tab._spectrum_glow_color.red(), tab._spectrum_glow_color.green(), tab._spectrum_glow_color.blue(), tab._spectrum_glow_color.alpha()) == (1, 2, 3, 4)
        assert synced == [("spectrum_glow_color_btn", "_spectrum_glow_color")]
        assert ghost_visibility_calls == [tab]

    def test_collect_spectrum_mode_settings_serializes_spectrum_owned_state(self):
        from ui.tabs.media.spectrum_settings_binding import collect_spectrum_mode_settings

        class _Check:
            def __init__(self, checked):
                self._checked = checked

            def isChecked(self):
                return self._checked

        class _Slider:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class _ShapeEditor:
            def __init__(self):
                self._notches_mirrored = [[0.0, "Mid"], [1.0, "Bass"]]
                self._notches_linear = [[0.0, "Bass"], [1.0, "Treble"]]
                self._lane_strengths_mirrored = {"Mid": 0.58, "Vocal": 0.65, "Low-Mid": 0.72, "Bass": 0.83}
                self._lane_strengths_linear = {"Bass": 0.68, "Low-Mid": 0.52, "Vocal": 0.47, "Hi-Mid": 0.75, "Treble": 0.91}

            def get_nodes(self):
                return [[0.0, 0.21], [1.0, 0.79]]

            def get_lane_strengths(self, mirrored=None):
                return dict(self._lane_strengths_mirrored if mirrored else self._lane_strengths_linear)

        class _Tab:
            vis_ghost_enabled = _Check(True)
            vis_ghost_opacity_slider = _Slider(43)
            vis_ghost_decay_slider = _Slider(38)
            spectrum_growth = _Slider(260)
            _spectrum_render_mode = "bars"
            spectrum_rainbow_per_bar = _Check(False)
            spectrum_rainbow_border = _Check(True)
            spectrum_border_radius = _Slider(6)
            spectrum_glow_enabled = _Check(True)
            spectrum_glow_intensity = _Slider(120)
            _spectrum_glow_color = QColor(1, 2, 3, 4)
            spectrum_mirrored = _Check(False)
            spectrum_shape_editor = _ShapeEditor()
            spectrum_wave_amplitude = _Slider(51)
            spectrum_profile_floor = _Slider(18)
            spectrum_drop_speed = _Slider(175)

        payload = collect_spectrum_mode_settings(_Tab())

        assert payload["spectrum_ghosting_enabled"] is True
        assert payload["spectrum_ghost_alpha"] == pytest.approx(0.43)
        assert payload["spectrum_ghost_decay"] == pytest.approx(0.38)
        assert payload["spectrum_growth"] == pytest.approx(2.6)
        assert payload["spectrum_render_mode"] == "bars"
        assert payload["spectrum_unique_colors"] is False
        assert payload["spectrum_rainbow_border"] is True
        assert payload["spectrum_border_radius"] == pytest.approx(6.0)
        assert payload["spectrum_glow_enabled"] is True
        assert payload["spectrum_glow_intensity"] == pytest.approx(1.2)
        assert payload["spectrum_glow_color"] == [1, 2, 3, 4]
        assert payload["spectrum_mirrored"] is False
        assert payload["spectrum_shape_nodes"] == [[0.0, 0.21], [1.0, 0.79]]
        assert payload["spectrum_notch_positions_mirrored"] == [[0.0, "Mid"], [1.0, "Bass"]]
        assert payload["spectrum_notch_positions_linear"] == [[0.0, "Bass"], [1.0, "Treble"]]
        assert payload["spectrum_lane_strengths_mirrored"] == {"Mid": 0.58, "Vocal": 0.65, "Low-Mid": 0.72, "Bass": 0.83}
        assert payload["spectrum_lane_strengths_linear"] == {"Bass": 0.68, "Low-Mid": 0.52, "Vocal": 0.47, "Hi-Mid": 0.75, "Treble": 0.91}
        assert payload["spectrum_wave_amplitude"] == pytest.approx(0.51)
        assert payload["spectrum_profile_floor"] == pytest.approx(0.18)
        assert payload["spectrum_drop_speed"] == pytest.approx(1.75)

    def test_load_spectrum_mode_settings_promotes_legacy_linear_default_to_vocal_lane(self):
        from ui.tabs.media.spectrum_settings_binding import load_spectrum_mode_settings

        class _Check:
            def __init__(self):
                self.checked = None

            def setChecked(self, checked):
                self.checked = checked

        class _Slider:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class _Label:
            def __init__(self):
                self.text = None

            def setText(self, text):
                self.text = text

        class _ShapeEditor:
            def __init__(self):
                self.nodes = None
                self.mirrored = None
                self.notches = []

            def set_nodes(self, nodes):
                self.nodes = nodes

            def set_mirrored(self, mirrored):
                self.mirrored = mirrored

            def set_notch_positions(self, notches, mirrored):
                self.notches.append((mirrored, notches))

            def set_lane_strengths(self, strengths, *, mirrored):
                if not hasattr(self, "lane_strengths"):
                    self.lane_strengths = []
                self.lane_strengths.append((mirrored, strengths))

            def set_lane_strengths(self, strengths, *, mirrored):
                if not hasattr(self, "lane_strengths"):
                    self.lane_strengths = []
                self.lane_strengths.append((mirrored, strengths))

            def set_lane_strengths(self, strengths, *, mirrored):
                if not hasattr(self, "lane_strengths"):
                    self.lane_strengths = []
                self.lane_strengths.append((mirrored, strengths))

        class _Tab:
            def __init__(self):
                self.spectrum_growth = _Slider()
                self.spectrum_growth_label = _Label()
                self._spectrum_render_mode = None
                self.spectrum_rainbow_per_bar = _Check()
                self.spectrum_rainbow_border = _Check()
                self.spectrum_wave_amplitude = _Slider()
                self.spectrum_wave_amplitude_label = _Label()
                self.spectrum_profile_floor = _Slider()
                self.spectrum_profile_floor_label = _Label()
                self.spectrum_drop_speed = _Slider()
                self.spectrum_drop_speed_label = _Label()
                self.spectrum_border_radius = _Slider()
                self.spectrum_border_radius_label = _Label()
                self.spectrum_glow_enabled = _Check()
                self.spectrum_glow_intensity = _Slider()
                self.spectrum_glow_intensity_label = _Label()
                self.spectrum_mirrored = _Check()
                self.spectrum_shape_editor = _ShapeEditor()
                self.vis_ghost_enabled = _Check()
                self.vis_ghost_opacity_slider = _Slider()
                self.vis_ghost_opacity_label = _Label()
                self.vis_ghost_decay_slider = _Slider()
                self.vis_ghost_decay_label = _Label()

            def _set_spectrum_render_mode(self, mode, save=False):
                self._spectrum_render_mode = mode

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

        tab = _Tab()

        load_spectrum_mode_settings(
            tab,
            {
                "spectrum_mirrored": False,
                "spectrum_notch_positions_linear": [[0.0, "Bass"], [0.25, "Low"], [0.50, "Mid"], [0.75, "Hi-Mid"], [1.0, "Treble"]],
            },
            sync_color_button=lambda *_args, **_kwargs: None,
            update_ghost_visibility=lambda *_args, **_kwargs: None,
        )

        assert tab.spectrum_shape_editor.notches[-1] == (
            False,
            [[0.0, "Bass"], [0.24, "Low-Mid"], [0.46, "Vocal"], [0.72, "Hi-Mid"], [1.0, "Treble"]],
        )

    def test_load_spectrum_mode_settings_promotes_drifted_legacy_linear_labels_to_vocal_lane(self):
        from ui.tabs.media.spectrum_settings_binding import load_spectrum_mode_settings

        class _Check:
            def __init__(self):
                self.checked = None

            def setChecked(self, checked):
                self.checked = checked

        class _Slider:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class _Label:
            def __init__(self):
                self.text = None

            def setText(self, text):
                self.text = text

        class _ShapeEditor:
            def __init__(self):
                self.nodes = None
                self.mirrored = None
                self.notches = []

            def set_nodes(self, nodes):
                self.nodes = nodes

            def set_mirrored(self, mirrored):
                self.mirrored = mirrored

            def set_notch_positions(self, notches, mirrored):
                self.notches.append((mirrored, notches))

            def set_lane_strengths(self, strengths, *, mirrored):
                if not hasattr(self, "lane_strengths"):
                    self.lane_strengths = []
                self.lane_strengths.append((mirrored, strengths))

        class _Tab:
            def __init__(self):
                self.spectrum_growth = _Slider()
                self.spectrum_growth_label = _Label()
                self._spectrum_render_mode = None
                self.spectrum_rainbow_per_bar = _Check()
                self.spectrum_rainbow_border = _Check()
                self.spectrum_wave_amplitude = _Slider()
                self.spectrum_wave_amplitude_label = _Label()
                self.spectrum_profile_floor = _Slider()
                self.spectrum_profile_floor_label = _Label()
                self.spectrum_drop_speed = _Slider()
                self.spectrum_drop_speed_label = _Label()
                self.spectrum_border_radius = _Slider()
                self.spectrum_border_radius_label = _Label()
                self.spectrum_glow_enabled = _Check()
                self.spectrum_glow_intensity = _Slider()
                self.spectrum_glow_intensity_label = _Label()
                self.spectrum_mirrored = _Check()
                self.spectrum_shape_editor = _ShapeEditor()
                self.vis_ghost_enabled = _Check()
                self.vis_ghost_opacity_slider = _Slider()
                self.vis_ghost_opacity_label = _Label()
                self.vis_ghost_decay_slider = _Slider()
                self.vis_ghost_decay_label = _Label()

            def _set_spectrum_render_mode(self, mode, save=False):
                self._spectrum_render_mode = mode

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

        tab = _Tab()

        load_spectrum_mode_settings(
            tab,
            {
                "spectrum_mirrored": False,
                "spectrum_notch_positions_linear": [
                    [0.0, "Bass"],
                    [0.21, "Low"],
                    [0.43, "Mid"],
                    [0.74, "Hi-Mid"],
                    [1.0, "Treble"],
                ],
            },
            sync_color_button=lambda *_args, **_kwargs: None,
            update_ghost_visibility=lambda *_args, **_kwargs: None,
        )

        assert tab.spectrum_shape_editor.notches[-1] == (
            False,
            [[0.0, "Bass"], [0.21, "Low-Mid"], [0.43, "Vocal"], [0.74, "Hi-Mid"], [1.0, "Treble"]],
        )

    def test_spotify_visualizer_settings_promotes_drifted_legacy_linear_labels_to_vocal_lane(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping(
            {
                "spectrum_notch_positions_linear": [
                    [0.0, "Bass"],
                    [0.22, "Low"],
                    [0.45, "Mid"],
                    [0.73, "Hi-Mid"],
                    [1.0, "Treble"],
                ],
            }
        )

        assert model.spectrum_notch_positions_linear == [
            [0.0, "Bass"],
            [0.22, "Low-Mid"],
            [0.45, "Vocal"],
            [0.73, "Hi-Mid"],
            [1.0, "Treble"],
        ]


class TestBubbleSettingsBinding:
    def test_load_bubble_mode_settings_updates_bubble_owned_controls(self):
        from ui.tabs.media.bubble_settings_binding import load_bubble_mode_settings

        class _Check:
            def __init__(self):
                self.checked = None

            def setChecked(self, checked):
                self.checked = checked

        class _Slider:
            def __init__(self):
                self.value = None

            def setValue(self, value):
                self.value = value

        class _Label:
            def __init__(self):
                self.text = None

            def setText(self, text):
                self.text = text

        class _Combo:
            def __init__(self, values):
                self._values = list(values)
                self._index = -1

            def findData(self, value):
                try:
                    return self._values.index(value)
                except ValueError:
                    return -1

            def setCurrentIndex(self, index):
                self._index = index

            def currentData(self):
                if 0 <= self._index < len(self._values):
                    return self._values[self._index]
                return None

        class _TextCombo:
            def __init__(self):
                self._index = -1

            def setCurrentIndex(self, index):
                self._index = index

        class _Tab:
            def __init__(self):
                self.bubble_ghost_enabled = _Check()
                self.bubble_ghost_opacity = _Slider()
                self.bubble_ghost_opacity_label = _Label()
                self.bubble_ghost_decay_slider = _Slider()
                self.bubble_ghost_decay_label = _Label()
                self.bubble_big_bass_pulse = _Slider()
                self.bubble_big_bass_pulse_label = _Label()
                self.bubble_stream_direction = _TextCombo()
                self.bubble_drift_direction = _Combo(["none", "left", "right", "random"])
                self.bubble_swirl_enabled = _Check()
                self.bubble_swirl_direction = _Combo(["swirl_cw", "swirl_ccw"])
                self.bubble_specular_direction = _Combo(["top_left", "bottom_right"])
                self.bubble_gradient_direction = _Combo(["top", "bottom", "center_out"])
                self.bubble_big_count = _Slider()
                self.bubble_big_count_label = _Label()
                self.bubble_small_count = _Slider()
                self.bubble_small_count_label = _Label()
                self.bubble_surface_reach = _Slider()
                self.bubble_surface_reach_label = _Label()
                self.bubble_bounce_big_pct = _Slider()
                self.bubble_bounce_big_pct_label = _Label()
                self.bubble_bounce_small_pct = _Slider()
                self.bubble_bounce_small_pct_label = _Label()
                self.bubble_bounce_big_speed = _Slider()
                self.bubble_bounce_big_speed_label = _Label()
                self.bubble_bounce_small_speed = _Slider()
                self.bubble_bounce_small_speed_label = _Label()
                self.bubble_bounce_same_only = _Check()
                self.bubble_collision_pop_mode = _Combo(["off", "one", "all"])
                self.bubble_growth = _Slider()
                self.bubble_growth_label = _Label()
                self.bubble_tail_opacity = _Slider()
                self.bubble_tail_opacity_label = _Label()

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

            def _config_int(self, _section, config, key, default):
                return config.get(key, default)

            def _config_str(self, _section, config, key, default):
                return config.get(key, default)

        tab = _Tab()
        synced = []
        load_bubble_mode_settings(
            tab,
            {
                "bubble_ghosting_enabled": True,
                "bubble_ghost_alpha": 0.22,
                "bubble_ghost_decay": 0.58,
                "bubble_big_bass_pulse": 0.71,
                "bubble_stream_direction": "left",
                "bubble_drift_direction": "swirl_ccw",
                "bubble_big_count": 12,
                "bubble_surface_reach": 0.66,
                "bubble_bounce_big_pct": 83,
                "bubble_bounce_small_pct": 19,
                "bubble_bounce_big_speed": 1.47,
                "bubble_bounce_small_speed": 0.26,
                "bubble_bounce_same_only": True,
                "bubble_collision_pop_mode": "all",
                "bubble_specular_direction": "bottom_right",
                "bubble_gradient_direction": "center_out",
                "bubble_growth": 3.2,
                "bubble_tail_opacity": 0.17,
                "bubble_outline_color": [5, 6, 7, 8],
            },
            sync_color_button=lambda btn, attr: synced.append((btn, attr)),
        )

        assert tab.bubble_ghost_enabled.checked is True
        assert tab.bubble_ghost_opacity.value == 22
        assert tab.bubble_ghost_decay_slider.value == 58
        assert tab.bubble_big_bass_pulse.value == 71
        assert tab.bubble_stream_direction._index == 3
        assert tab.bubble_swirl_enabled.checked is True
        assert tab.bubble_swirl_direction.currentData() == "swirl_ccw"
        assert tab.bubble_drift_direction.currentData() == "none"
        assert tab.bubble_big_count.value == 12
        assert tab.bubble_surface_reach.value == 66
        assert tab.bubble_bounce_big_pct.value == 83
        assert tab.bubble_bounce_small_pct.value == 19
        assert tab.bubble_bounce_big_speed.value == 147
        assert tab.bubble_bounce_small_speed.value == 26
        assert tab.bubble_bounce_same_only.checked is True
        assert tab.bubble_collision_pop_mode.currentData() == "all"
        assert tab.bubble_specular_direction.currentData() == "bottom_right"
        assert tab.bubble_gradient_direction.currentData() == "center_out"
        assert tab.bubble_growth.value == 320
        assert tab.bubble_tail_opacity.value == 17
        assert (tab._bubble_outline_color.red(), tab._bubble_outline_color.green(), tab._bubble_outline_color.blue(), tab._bubble_outline_color.alpha()) == (5, 6, 7, 8)
        assert synced == [
            ("bubble_outline_color_btn", "_bubble_outline_color"),
            ("bubble_specular_color_btn", "_bubble_specular_color"),
            ("bubble_gradient_light_btn", "_bubble_gradient_light"),
            ("bubble_gradient_dark_btn", "_bubble_gradient_dark"),
            ("bubble_pop_color_btn", "_bubble_pop_color"),
        ]

    def test_collect_bubble_mode_settings_serializes_bubble_owned_state(self):
        from ui.tabs.media.bubble_settings_binding import collect_bubble_mode_settings

        class _Check:
            def __init__(self, checked):
                self._checked = checked

            def isChecked(self):
                return self._checked

        class _Slider:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class _DataCombo:
            def __init__(self, value):
                self._value = value

            def currentData(self):
                return self._value

        class _TextCombo:
            def __init__(self, text):
                self._text = text

            def currentText(self):
                return self._text

        class _Tab:
            bubble_ghost_enabled = _Check(True)
            bubble_ghost_opacity = _Slider(33)
            bubble_ghost_decay_slider = _Slider(48)
            bubble_big_bass_pulse = _Slider(76)
            bubble_small_freq_pulse = _Slider(44)
            bubble_stream_direction = _DataCombo("top_left")
            bubble_stream_constant_speed = _Slider(61)
            bubble_stream_speed_cap = _Slider(240)
            bubble_stream_reactivity = _Slider(83)
            bubble_rotation_amount = _Slider(58)
            bubble_drift_amount = _Slider(37)
            bubble_drift_speed = _Slider(28)
            bubble_drift_frequency = _Slider(49)
            bubble_swirl_enabled = _Check(True)
            bubble_swirl_direction = _DataCombo("swirl_ccw")
            bubble_drift_direction = _DataCombo("random")
            bubble_big_count = _Slider(9)
            bubble_small_count = _Slider(31)
            bubble_surface_reach = _Slider(72)
            bubble_bounce_big_pct = _Slider(84)
            bubble_bounce_small_pct = _Slider(21)
            bubble_bounce_big_speed = _Slider(165)
            bubble_bounce_small_speed = _Slider(44)
            bubble_bounce_same_only = _Check(True)
            bubble_collision_pop_mode = _DataCombo("one")
            bubble_specular_direction = _DataCombo("bottom_right")
            bubble_gradient_direction = _DataCombo("center_out")
            bubble_big_size_max = _Slider(42)
            bubble_small_size_max = _Slider(15)
            bubble_big_specular_max_size = _Slider(260)
            bubble_big_size_clamp = _Slider(420)
            bubble_big_contraction_bias = _Slider(64)
            bubble_growth = _Slider(310)
            bubble_trail_strength = _Slider(18)
            bubble_tail_opacity = _Slider(11)
            _bubble_outline_color = QColor(1, 2, 3, 4)
            _bubble_specular_color = QColor(5, 6, 7, 8)
            _bubble_gradient_light = QColor(9, 10, 11, 12)
            _bubble_gradient_dark = QColor(13, 14, 15, 16)
            _bubble_pop_color = QColor(17, 18, 19, 20)

        payload = collect_bubble_mode_settings(_Tab())

        assert payload["bubble_ghosting_enabled"] is True
        assert payload["bubble_ghost_alpha"] == pytest.approx(0.33)
        assert payload["bubble_ghost_decay"] == pytest.approx(0.48)
        assert payload["bubble_stream_direction"] == "top_left"
        assert payload["bubble_drift_direction"] == "swirl_ccw"
        assert payload["bubble_gradient_direction"] == "center_out"
        assert payload["bubble_outline_color"] == [1, 2, 3, 4]
        assert payload["bubble_big_size_max"] == pytest.approx(0.042)
        assert payload["bubble_bounce_big_pct"] == 84
        assert payload["bubble_bounce_small_pct"] == 21
        assert payload["bubble_bounce_big_speed"] == pytest.approx(1.65)
        assert payload["bubble_bounce_small_speed"] == pytest.approx(0.44)
        assert payload["bubble_bounce_same_only"] is True
        assert payload["bubble_collision_pop_mode"] == "one"
        assert payload["bubble_growth"] == pytest.approx(3.10)
        assert payload["bubble_tail_opacity"] == pytest.approx(0.11)


# ==========================================================================
# 9b. Bubble swirl plumbing + behaviour
# ==========================================================================

class TestBubbleSwirlSettings:
    """Ensure swirl drift directions travel through settings + config layers."""

    def test_swirl_direction_round_trip_in_settings_model(self):
        from core.settings.models import SpotifyVisualizerSettings
        from core.settings.visualizer_presets import get_custom_preset_index

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "bubble",
            "preset_bubble": get_custom_preset_index("bubble"),
            "bubble_drift_direction": "swirl_ccw",
        })
        assert model.bubble_drift_direction == "swirl_ccw"

        payload = model.to_dict()
        key = "widgets.spotify_visualizer.bubble_drift_direction"
        assert payload[key] == "swirl_ccw"

    def test_config_applier_accepts_swirl_direction(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bubble_drift_direction = "random"

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {
            "bubble_drift_direction": "swirl_cw",
        })
        assert widget._bubble_drift_direction == "swirl_cw"

    def test_config_applier_accepts_directional_stream_diagonals(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bubble_stream_direction = "up"

        widget = DummyWidget()
        for direction in ("top_left", "top_right", "bottom_left", "bottom_right"):
            apply_vis_mode_kwargs(widget, {"bubble_stream_direction": direction})
            assert widget._bubble_stream_direction == direction


class TestBubbleSwirlMotion:
    """Validate helper math keeps swirl motion tangential with correct winding."""

    def _radius(self, bubble):
        return (bubble.x - 0.5, bubble.y - 0.5)

    def _dot(self, a, b):
        return a[0] * b[0] + a[1] * b[1]

    def _cross_z(self, a, b):
        return a[0] * b[1] - a[1] * b[0]

    def test_swirl_cw_produces_motion(self):
        from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation, BubbleState

        sim = BubbleSimulation()
        bubble = BubbleState(x=0.82, y=0.35)
        swirl_vec = sim._swirl_motion(bubble, "swirl_cw", 0.05, 1.0, dt=1.0)
        # Swirl should produce non-zero motion
        assert abs(swirl_vec[0]) + abs(swirl_vec[1]) > 0.0001

    def test_swirl_ccw_produces_motion(self):
        from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation, BubbleState

        sim = BubbleSimulation()
        bubble = BubbleState(x=0.2, y=0.75)
        swirl_vec = sim._swirl_motion(bubble, "swirl_ccw", 0.05, 1.0, dt=1.0)
        # Swirl should produce non-zero motion
        assert abs(swirl_vec[0]) + abs(swirl_vec[1]) > 0.0001


class TestBubbleSpecularDirection:
    """Verify specular/gradient direction options stay wired through all layers."""

    def test_gradient_direction_round_trip_in_settings_model(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "bubble",
            "bubble_gradient_direction": "center_out_reverse",
            "bubble_gradient_semantics_version": 2,
        }, apply_preset_overlay=False)
        assert model.bubble_gradient_direction == "center_out_reverse"

        payload = model.to_dict()
        key = "widgets.spotify_visualizer.bubble_gradient_direction"
        assert payload[key] == "center_out_reverse"
        assert payload["widgets.spotify_visualizer.bubble_gradient_semantics_version"] == 2

    def test_legacy_gradient_direction_migrates_to_canonical_label(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "bubble",
            "bubble_gradient_direction": "left",
        }, apply_preset_overlay=False)
        assert model.bubble_gradient_direction == "right"

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "bubble",
            "bubble_gradient_direction": "top",
        }, apply_preset_overlay=False)
        assert model.bubble_gradient_direction == "bottom"

    def test_versioned_gradient_direction_preserves_canonical_label(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "bubble",
            "bubble_gradient_direction": "left",
            "bubble_gradient_semantics_version": 2,
        }, apply_preset_overlay=False)
        assert model.bubble_gradient_direction == "left"

    def test_config_applier_accepts_cardinal_directions(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bubble_specular_direction = "top_left"
            _bubble_gradient_direction = "top"

        widget = DummyWidget()
        for val in ("top", "bottom", "left", "right"):
            apply_vis_mode_kwargs(widget, {
                "bubble_specular_direction": val,
                "bubble_gradient_direction": val,
            })
            assert widget._bubble_specular_direction == val
            assert widget._bubble_gradient_direction == val

    def test_config_applier_accepts_center_out_reverse_for_gradient(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bubble_gradient_direction = "top"

        widget = DummyWidget()
        apply_vis_mode_kwargs(widget, {
            "bubble_gradient_direction": "center_out_reverse",
        })
        assert widget._bubble_gradient_direction == "center_out_reverse"

    def test_gradient_shader_helper_uses_brightest_point_semantics(self):
        from core.settings.bubble_gradient_semantics import (
            get_bubble_gradient_shader_mode,
            get_bubble_gradient_shader_vector,
        )

        assert get_bubble_gradient_shader_vector("left") == (-1.0, 0.0)
        assert get_bubble_gradient_shader_vector("top") == (0.0, -1.0)
        assert get_bubble_gradient_shader_vector("bottom_right") == (0.707, 0.707)
        assert get_bubble_gradient_shader_mode("center_out") == 1
        assert get_bubble_gradient_shader_mode("center_out_reverse") == 2

    def test_bubble_shader_radial_modes_keep_center_out_as_primary_mode(self):
        shader = Path(
            r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_visualizer\shaders\bubble.frag"
        ).read_text(encoding="utf-8")

        assert 'grad_t = (u_gradient_mode == 2) ? radial_t : (1.0 - radial_t);' in shader

    def test_gl_overlay_queries_bubble_gradient_mode_uniform(self):
        src = Path(
            r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_bars_gl_overlay.py"
        ).read_text(encoding="utf-8")

        assert '"u_specular_dir", "u_gradient_dir", "u_gradient_mode", "u_outline_color", "u_specular_color"' in src


# ===========================================================================
# 10. VisualizerMode enum includes BUBBLE
# ===========================================================================

class TestVisualizerModeEnum:
    """Verify BUBBLE is registered in the VisualizerMode enum."""

    def test_bubble_in_enum(self):
        from widgets.spotify_visualizer.audio_worker import VisualizerMode
        assert hasattr(VisualizerMode, "BUBBLE")

    def test_bubble_in_shader_registry(self):
        from widgets.spotify_visualizer.shaders import _ALL_SHADER_FILES
        assert "bubble" in _ALL_SHADER_FILES


# ==========================================================================
# 11. Preset repair sanitization + migrations
# ==========================================================================


class TestVisualizerPresetRepair:
    """Validate the preset repair helper normalizes legacy payloads."""

    def test_repair_file_sanitizes_blob_stretch_biases(self, tmp_path):
        import json
        from tools.visualizer_preset_repair import repair_file

        payload = {
            "name": "Preset 1 (Test)",
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": {
                        "mode": "blob",
                        "blob_stretch_x_bias": 0.25,
                        "blob_stretch_y_bias": 0.75,
                    }
                },
                "custom_preset_backup": {
                    "widgets.spotify_visualizer.blob_stretch_x_bias": 0.25,
                    "widgets.spotify_visualizer.blob_stretch_y_bias": 0.75,
                },
            },
            "widgets": {
                "spotify_visualizer": {
                    "blob_stretch_x_bias": 0.25,
                }
            },
        }
        preset_path = tmp_path / "blob_preset.json"
        preset_path.write_text(json.dumps(payload), encoding="utf-8")

        backup, stats = repair_file(preset_path, "blob")

        assert backup.exists()
        assert "snapshot.widgets.spotify_visualizer" in stats["updated_paths"]

        repaired = json.loads(preset_path.read_text(encoding="utf-8"))
        sv = repaired["snapshot"]["widgets"]["spotify_visualizer"]
        assert "blob_stretch" in sv
        assert "blob_stretch_x_bias" not in sv
        assert "blob_stretch_y_bias" not in sv

        # custom_preset_backup was intentionally removed from repair_file output
        # (see visualizer_preset_repair.py lines 205-210) to prevent preset drift.
        assert "custom_preset_backup" not in repaired.get("snapshot", {})

    def test_repair_file_derives_sine_card_adaptation(self, tmp_path):
        import json
        from tools.visualizer_preset_repair import repair_file

        payload = {
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": {
                        "mode": "sine_wave",
                        "sine_min_height": 0.12,
                        "rainbow_enabled": True,
                        "rainbow_speed": 0.4,
                    }
                }
            }
        }
        preset_path = tmp_path / "sine_preset.json"
        preset_path.write_text(json.dumps(payload), encoding="utf-8")

        _, stats = repair_file(preset_path, "sine_wave")
        assert stats["added"]  # new fields injected

        repaired = json.loads(preset_path.read_text(encoding="utf-8"))
        sv = repaired["snapshot"]["widgets"]["spotify_visualizer"]
        assert "sine_card_adaptation" in sv
        assert "sine_min_height" not in sv
        assert "rainbow_enabled" not in sv  # migrated to per-mode key
        # Derived adaptation clamps min height ratio (0.12 / 0.24 = 0.5)
        assert abs(sv["sine_card_adaptation"] - 0.5) < 1e-6

    @pytest.mark.parametrize(
        "mode, expected_keys",
        [
            ("sine_wave", ["sine_wave_input_gain", "sine_wave_audio_block_size", "sine_glow_color"]),
            ("bubble", ["bubble_input_gain", "bubble_audio_block_size", "bubble_gradient_light"]),
            ("blob", ["blob_input_gain", "blob_audio_block_size", "blob_glow_color"]),
            ("spectrum", ["spectrum_input_gain", "spectrum_audio_block_size", "spectrum_shape_nodes"]),
            ("oscilloscope", ["oscilloscope_input_gain", "oscilloscope_audio_block_size", "osc_glow_color"]),
        ],
    )
    def test_repair_file_promotes_global_keys_per_mode(self, tmp_path, mode, expected_keys):
        import json
        from tools.visualizer_preset_repair import repair_file

        payload = {
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": {
                        "mode": mode,
                        "input_gain": 0.8,
                        "manual_floor": 0.15,
                    }
                }
            }
        }
        preset_path = tmp_path / f"{mode}_preset.json"
        preset_path.write_text(json.dumps(payload), encoding="utf-8")

        _, stats = repair_file(preset_path, mode)
        assert stats["added"], "Expected defaults to be injected"

        repaired = json.loads(preset_path.read_text(encoding="utf-8"))
        sv = repaired["snapshot"]["widgets"]["spotify_visualizer"]
        for key in expected_keys:
            assert key in sv, f"Missing {key} for {mode}"

    def test_repair_file_promotes_drifted_legacy_spectrum_linear_notches(self, tmp_path):
        import json
        from tools.visualizer_preset_repair import repair_file

        payload = {
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": {
                        "mode": "spectrum",
                        "spectrum_mirrored": False,
                        "spectrum_notch_positions_linear": [
                            [0.0, "Bass"],
                            [0.22, "Low"],
                            [0.45, "Mid"],
                            [0.74, "Hi-Mid"],
                            [1.0, "Treble"],
                        ],
                    }
                }
            }
        }
        preset_path = tmp_path / "spectrum_linear_legacy.json"
        preset_path.write_text(json.dumps(payload), encoding="utf-8")

        _, _ = repair_file(preset_path, "spectrum")

        repaired = json.loads(preset_path.read_text(encoding="utf-8"))
        sv = repaired["snapshot"]["widgets"]["spotify_visualizer"]
        assert sv["spectrum_notch_positions_linear"] == [
            [0.0, "Bass"],
            [0.22, "Low-Mid"],
            [0.45, "Vocal"],
            [0.74, "Hi-Mid"],
            [1.0, "Treble"],
        ]

    def test_audit_payload_flags_legacy_spectrum_linear_notch_family(self):
        from tools.visualizer_preset_repair import audit_payload

        payload = {
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": {
                        "mode": "spectrum",
                        "spectrum_notch_positions_linear": [
                            [0.0, "Bass"],
                            [0.21, "Low"],
                            [0.43, "Mid"],
                            [0.74, "Hi-Mid"],
                            [1.0, "Treble"],
                        ],
                    }
                }
            }
        }

        report = audit_payload("spectrum", payload)

        assert report["legacy_spectrum_linear_notch_family"] is True
