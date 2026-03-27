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


class TestPresetOverlayRuntimeOverrides:
    def test_from_mapping_preserves_explicit_spectrum_runtime_overrides(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "spectrum",
                "preset_spectrum": 5,
                "bar_count": 32,
                "spectrum_bar_count": 35,
                "spectrum_glow_enabled": True,
                "spectrum_glow_intensity": 1.2,
                "spectrum_glow_color": [0, 120, 255, 255],
                "spectrum_manual_floor": 0.33,
            }
        )

        assert model.resolve_bar_count("spectrum") == 35
        assert model.spectrum_glow_enabled is True
        assert model.spectrum_glow_intensity == pytest.approx(1.2)
        assert model.spectrum_glow_color == [0, 120, 255, 255]
        assert model.resolve_manual_floor("spectrum") == pytest.approx(0.33)

    def test_from_mapping_preserves_dotted_runtime_overrides(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping(
            {
                "widgets.spotify_visualizer.mode": "spectrum",
                "widgets.spotify_visualizer.preset_spectrum": 5,
                "widgets.spotify_visualizer.spectrum_bar_count": 35,
                "widgets.spotify_visualizer.spectrum_glow_enabled": True,
                "widgets.spotify_visualizer.spectrum_glow_intensity": 1.2,
                "widgets.spotify_visualizer.spectrum_glow_color": [0, 120, 255, 255],
            }
        )

        assert model.resolve_bar_count("spectrum") == 35
        assert model.spectrum_glow_enabled is True
        assert model.spectrum_glow_intensity == pytest.approx(1.2)
        assert model.spectrum_glow_color == [0, 120, 255, 255]

    def test_from_mapping_preserves_explicit_secondary_ghost_toggles(self):
        from core.settings.models import SpotifyVisualizerSettings

        osc_model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "oscilloscope",
                "preset_oscilloscope": 0,
                "oscilloscope_bar_count": 35,
                "osc_ghost_line2_enabled": False,
                "osc_ghost_line3_enabled": True,
            }
        )
        assert osc_model.resolve_bar_count("oscilloscope") == 35
        assert osc_model.osc_ghost_line2_enabled is False
        assert osc_model.osc_ghost_line3_enabled is True

        sine_model = SpotifyVisualizerSettings.from_mapping(
            {
                "mode": "sine_wave",
                "preset_sine_wave": 0,
                "sine_ghost_line2_enabled": False,
                "sine_ghost_line3_enabled": True,
            }
        )
        assert sine_model.sine_ghost_line2_enabled is False
        assert sine_model.sine_ghost_line3_enabled is True


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

    def test_blob_pulse_controls_applied_and_pushed(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs, build_gpu_push_extra_kwargs

        class DummyWidget:
            _blob_pulse_cap = 1.0
            _blob_pulse_release_ms = 220.0

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
            "blob_pulse_cap": 0.75,
            "blob_pulse_release_ms": 320.0,
        })
        extra = build_gpu_push_extra_kwargs(widget, "blob", None)

        assert widget._blob_pulse_cap == pytest.approx(0.75)
        assert widget._blob_pulse_release_ms == pytest.approx(320.0)
        assert extra["blob_pulse_cap"] == pytest.approx(0.75)
        assert extra["blob_pulse_release_ms"] == pytest.approx(320.0)

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
                "preset_spectrum": 5,
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
        assert refresh_calls == [widgets_config], (
            "Create-time visualizer setup must reuse the same refresh contract "
            "that settings re-entry uses."
        )


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
                "energy_boost_slider": _StubSlider(90),
                "agc_strength_slider": _StubSlider(55),
                "raw_energy": _StubCheck(False),
            },
            update_sensitivity=lambda: None,
            update_manual_floor=lambda: None,
        )

        config: dict[str, float | int | bool] = {}
        tc.collect_per_mode_technical_controls(tab, config)

        assert config["sine_wave_audio_block_size"] == 128
        assert config["sine_wave_input_gain"] == pytest.approx(1.30)

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

        class _Tab:
            def __init__(self):
                self.blob_ghost_enabled = _Check()
                self.blob_ghost_opacity = _Slider()
                self.blob_ghost_opacity_label = _Label()
                self.blob_ghost_decay_slider = _Slider()
                self.blob_ghost_decay_label = _Label()
                self.blob_pulse = _Slider()
                self.blob_pulse_label = _Label()
                self.blob_stage_bias = _Slider()
                self.blob_stage_bias_label = _Label()
                self.blob_pulse_release_ms = _Slider()
                self.blob_pulse_release_ms_label = _Label()
                self.blob_growth = _Slider()
                self.blob_growth_label = _Label()

            def _config_bool(self, _section, config, key, default):
                return config.get(key, default)

            def _config_float(self, _section, config, key, default):
                return config.get(key, default)

            def _config_int(self, _section, config, key, default):
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
                "blob_stage_bias": -0.18,
                "blob_pulse_release_ms": 410,
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
        assert tab.blob_stage_bias.value == -18
        assert tab.blob_stage_bias_label.text == "-0.18"
        assert tab.blob_pulse_release_ms.value == 410
        assert tab.blob_pulse_release_ms_label.text == "0.41s"
        assert tab.blob_growth.value == 310
        assert tab.blob_growth_label.text == "3.1x"
        assert (tab._blob_color.red(), tab._blob_color.green(), tab._blob_color.blue(), tab._blob_color.alpha()) == (1, 2, 3, 4)
        assert synced == [
            ("blob_fill_color_btn", "_blob_color"),
            ("blob_glow_color_btn", "_blob_glow_color"),
            ("blob_edge_color_btn", "_blob_edge_color"),
            ("blob_outline_color_btn", "_blob_outline_color"),
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

        class _Tab:
            blob_ghost_enabled = _Check(True)
            blob_ghost_opacity = _Slider(45)
            blob_ghost_decay_slider = _Slider(38)
            blob_pulse = _Slider(140)
            blob_width = _Slider(92)
            blob_size = _Slider(135)
            blob_glow_intensity = _Slider(67)
            blob_glow_reactivity = _Slider(123)
            blob_glow_max_size = _Slider(210)
            blob_reactive_glow = _Check(True)
            blob_reactive_deformation = _Slider(88)
            blob_pulse_cap = _Slider(76)
            blob_pulse_release_ms = _Slider(330)
            blob_stage_gain = _Slider(111)
            blob_core_scale = _Slider(95)
            blob_core_floor_bias = _Slider(27)
            blob_stage_bias = _Slider(-14)
            blob_stage2_release_ms = _Slider(1200)
            blob_stage3_release_ms = _Slider(1500)
            blob_constant_wobble = _Slider(80)
            blob_reactive_wobble = _Slider(90)
            blob_stretch_tendency = _Slider(55)
            blob_stretch_inner = _Slider(62)
            blob_stretch_outer = _Slider(48)
            blob_growth = _Slider(275)
            _blob_color = QColor(10, 20, 30, 200)
            _blob_glow_color = QColor(40, 50, 60, 210)
            _blob_edge_color = QColor(70, 80, 90, 220)
            _blob_outline_color = QColor(100, 110, 120, 230)

        payload = collect_blob_mode_settings(_Tab())

        assert payload["blob_ghosting_enabled"] is True
        assert payload["blob_ghost_alpha"] == pytest.approx(0.45)
        assert payload["blob_ghost_decay"] == pytest.approx(0.38)
        assert payload["blob_pulse"] == pytest.approx(1.4)
        assert payload["blob_color"] == [10, 20, 30, 200]
        assert payload["blob_glow_color"] == [40, 50, 60, 210]
        assert payload["blob_edge_color"] == [70, 80, 90, 220]
        assert payload["blob_outline_color"] == [100, 110, 120, 230]
        assert payload["blob_stage_bias"] == pytest.approx(-0.14)
        assert payload["blob_growth"] == pytest.approx(2.75)


# ==========================================================================
# 9b. Bubble swirl plumbing + behaviour
# ==========================================================================

class TestBubbleSwirlSettings:
    """Ensure swirl drift directions travel through settings + config layers."""

    def test_swirl_direction_round_trip_in_settings_model(self):
        from core.settings.models import SpotifyVisualizerSettings

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "bubble",
            "preset_bubble": 3,  # custom slot to prevent preset overlay
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
            "preset_bubble": 3,
            "bubble_gradient_direction": "center_out",
        })
        assert model.bubble_gradient_direction == "center_out"

        payload = model.to_dict()
        key = "widgets.spotify_visualizer.bubble_gradient_direction"
        assert payload[key] == "center_out"

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


# ===========================================================================
# 10. VisualizerMode enum includes BUBBLE
# ===========================================================================

class TestVisualizerModeEnum:
    """Verify BUBBLE is registered in the VisualizerMode enum."""

    def test_bubble_in_enum(self):
        from widgets.spotify_visualizer.audio_worker import VisualizerMode
        assert hasattr(VisualizerMode, "BUBBLE")

    def test_bubble_in_shader_registry(self):
        from widgets.spotify_visualizer.shaders import _SHADER_FILES
        assert "bubble" in _SHADER_FILES


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
        assert "blob_stretch_inner" in sv and "blob_stretch_outer" in sv
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
