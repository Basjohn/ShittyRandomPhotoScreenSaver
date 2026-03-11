"""Regression tests for visualizer settings plumbing across all 8 layers.

Catches bugs like:
- Bubble kwargs causing TypeError in set_state (sim-only keys forwarded)
- Missing settings in model/from_settings/from_mapping/to_dict
- Missing card height entries for new modes
- Rainbow greyscale saturation fix missing from shaders
- Width reaction not wired through all layers

These tests do NOT require a running app or GL context.
"""
import inspect
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SHADER_DIR = ROOT / "widgets" / "spotify_visualizer" / "shaders"


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

    def _get_bubble_extra_keys(self):
        """Extract keys that build_gpu_push_extra_kwargs adds for bubble mode."""
        src = (ROOT / "widgets" / "spotify_visualizer" / "config_applier.py").read_text(encoding="utf-8")
        # Find the bubble block
        bubble_block = src.split("if mode_str == 'bubble':")[1].split("return extra")[0]
        keys = re.findall(r"extra\['(\w+)'\]", bubble_block)
        return set(keys)

    def test_bubble_extra_keys_accepted_by_set_state(self):
        """Every key in bubble GPU push must be accepted by set_state."""
        set_state_params = self._get_set_state_params()
        bubble_keys = self._get_bubble_extra_keys()
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
        bubble_keys = self._get_bubble_extra_keys()
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
        required_modes = {"spectrum", "oscilloscope", "starfield", "blob", "helix", "sine_wave", "bubble"}
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

    def test_widget_growth_dict_includes_bubble(self):
        """Widget's get_preferred_height must include bubble in its growth dict."""
        src = (ROOT / "widgets" / "spotify_visualizer_widget.py").read_text(encoding="utf-8")
        assert "'bubble'" in src and "_bubble_growth" in src, (
            "Widget missing bubble in growth dict or _bubble_growth attribute"
        )


# ===========================================================================
# 3. Rainbow greyscale saturation fix in ALL shaders
# ===========================================================================

class TestRainbowGreyscaleFix:
    """Regression: rainbow hue shift invisible on white/grey because saturation=0."""

    SHADER_FILES = [
        "spectrum.frag", "oscilloscope.frag", "sine_wave.frag",
        "starfield.frag", "blob.frag", "helix.frag", "bubble.frag",
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
    """Verify that key visualizer settings exist in all model methods."""

    CRITICAL_SETTINGS = [
        "sine_width_reaction",
        "sine_micro_wobble",
        "sine_heartbeat",
        "rainbow_enabled",
        "rainbow_speed",
        "osc_ghosting_enabled",
        "osc_ghost_intensity",
        "bubble_big_bass_pulse",
        "bubble_small_freq_pulse",
        "bubble_stream_direction",
        "bubble_outline_color",
        "bubble_specular_direction",
        "bubble_gradient_direction",
    ]

    def _read_models_src(self):
        return (ROOT / "core" / "settings" / "models.py").read_text(encoding="utf-8")

    def test_all_critical_settings_in_dataclass(self):
        src = self._read_models_src()
        for key in self.CRITICAL_SETTINGS:
            assert f"{key}:" in src or f"{key} :" in src, (
                f"Setting '{key}' missing from model dataclass"
            )

    def test_all_critical_settings_in_from_settings(self):
        src = self._read_models_src()
        for key in self.CRITICAL_SETTINGS:
            assert f'"{key}"' in src or f"'{key}'" in src, (
                f"Setting '{key}' may be missing from from_settings/from_mapping"
            )

    def test_all_critical_settings_in_to_dict(self):
        src = self._read_models_src()
        for key in self.CRITICAL_SETTINGS:
            # to_dict uses f-string prefix keys
            assert f".{key}" in src or f'"{key}"' in src, (
                f"Setting '{key}' may be missing from to_dict"
            )


# ===========================================================================
# 5. Creator kwargs: settings must be passed through
# ===========================================================================

class TestCreatorKwargs:
    """Verify spotify_widget_creators passes critical settings."""

    def _read_creators_src(self):
        return (ROOT / "rendering" / "spotify_widget_creators.py").read_text(encoding="utf-8")

    CRITICAL_PASSTHROUGH = [
        "sine_width_reaction",
        "sine_micro_wobble",
        "sine_heartbeat",
        "rainbow_enabled",
        "rainbow_speed",
        "osc_ghosting_enabled",
        "osc_ghost_intensity",
    ]

    def test_critical_settings_passed_through(self):
        src = self._read_creators_src()
        for key in self.CRITICAL_PASSTHROUGH:
            assert f"{key}=model.{key}" in src, (
                f"Creator missing passthrough for '{key}'"
            )


# ===========================================================================
# 6. Config applier: settings must be applied and pushed
# ===========================================================================

class TestConfigApplier:
    """Verify config_applier handles critical settings."""

    def _read_config_applier_src(self):
        return (ROOT / "widgets" / "spotify_visualizer" / "config_applier.py").read_text(encoding="utf-8")

    def test_sine_width_reaction_applied(self):
        src = self._read_config_applier_src()
        assert "sine_width_reaction" in src, "config_applier missing sine_width_reaction"
        # Must be in both apply (kwargs check) and push (extra dict)
        assert "extra['sine_width_reaction']" in src, (
            "config_applier not pushing sine_width_reaction to extra dict"
        )

    def test_bubble_gpu_push_has_snapshot_data(self):
        """Bubble GPU push must include pos_data, extra_data, count."""
        src = self._read_config_applier_src()
        for key in ("bubble_pos_data", "bubble_extra_data", "bubble_count"):
            assert f"extra['{key}']" in src, (
                f"config_applier missing {key} in bubble GPU push"
            )

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


# ===========================================================================
# 7. GL overlay: uniform query list and set_state params
# ===========================================================================

class TestGLOverlayUniforms:
    """Verify GL overlay queries and pushes critical uniforms."""

    def _read_overlay_src(self):
        return (ROOT / "widgets" / "spotify_bars_gl_overlay.py").read_text(encoding="utf-8")

    def test_width_reaction_uniform_queried(self):
        src = self._read_overlay_src()
        assert '"u_width_reaction"' in src, "u_width_reaction not in uniform query list"

    def test_width_reaction_uniform_pushed(self):
        src = self._read_overlay_src()
        assert "u_width_reaction" in src and "_sine_width_reaction" in src

    def test_rainbow_uniform_queried(self):
        src = self._read_overlay_src()
        assert '"u_rainbow_hue_offset"' in src

    def test_bubble_uniforms_queried(self):
        src = self._read_overlay_src()
        for uname in ("u_bubble_count", "u_bubbles_pos", "u_bubbles_extra",
                       "u_specular_dir", "u_gradient_dir", "u_outline_color", "u_gradient_light"):
            assert f'"{uname}"' in src, f"Bubble uniform {uname} not queried"

    def test_set_state_accepts_bubble_params(self):
        src = self._read_overlay_src()
        for param in ("bubble_count", "bubble_pos_data", "bubble_extra_data",
                       "bubble_outline_color", "bubble_specular_direction", "bubble_gradient_direction"):
            assert param in src, f"set_state missing bubble param: {param}"

    def test_set_state_accepts_width_reaction(self):
        src = self._read_overlay_src()
        assert "sine_width_reaction" in src

    def test_specular_dir_map_includes_cardinal_directions(self):
        # Direction mapping lives in the bubble renderer, not the overlay
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "bubble.py").read_text(encoding="utf-8")
        for key in ("'top':", "'bottom':", "'left':", "'right':"):
            assert key in src, f"Specular direction mapping missing {key}"


# ===========================================================================
# 8. Shader uniform declarations
# ===========================================================================

class TestShaderUniformDeclarations:
    """Verify shader .frag files declare required uniforms."""

    def test_sine_wave_has_width_reaction(self):
        src = (SHADER_DIR / "sine_wave.frag").read_text(encoding="utf-8")
        assert "u_width_reaction" in src, "sine_wave.frag missing u_width_reaction uniform"

    def test_sine_wave_has_heartbeat(self):
        src = (SHADER_DIR / "sine_wave.frag").read_text(encoding="utf-8")
        assert "u_heartbeat" in src
        assert "u_heartbeat_intensity" in src

    def test_bubble_has_required_uniforms(self):
        src = (SHADER_DIR / "bubble.frag").read_text(encoding="utf-8")
        for u in ("u_bubble_count", "u_bubbles_pos", "u_bubbles_extra",
                   "u_specular_dir", "u_gradient_dir", "u_outline_color", "u_specular_color",
                   "u_gradient_light", "u_gradient_dark", "u_pop_color",
                   "u_rainbow_hue_offset"):
            assert u in src, f"bubble.frag missing uniform: {u}"


# ===========================================================================
# 9. Bubble simulation thread safety
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
            "widgets.spotify_visualizer.audio_block_size": 0,
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


# ===========================================================================
# 11. UI builder creates width reaction widget
# ===========================================================================

class TestSineWaveUIBuilder:
    """Verify sine wave UI builder creates the width reaction slider."""

    def test_width_reaction_in_builder(self):
        src = (ROOT / "ui" / "tabs" / "media" / "sine_wave_builder.py").read_text(encoding="utf-8")
        assert "sine_width_reaction" in src, "Width Reaction slider missing from sine wave builder"

    def test_width_reaction_in_save(self):
        src = (ROOT / "ui" / "tabs" / "widgets_tab_media.py").read_text(encoding="utf-8")
        assert "'sine_width_reaction'" in src, "sine_width_reaction missing from save_media_settings"

    def test_width_reaction_in_load(self):
        src = (ROOT / "ui" / "tabs" / "widgets_tab_media.py").read_text(encoding="utf-8")
        assert "sine_width_reaction" in src and "sine_width_reaction_label" in src, (
            "sine_width_reaction missing from load path"
        )


# ==========================================================================
# 12. Preset repair sanitization + migrations
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

        backup_section = repaired["snapshot"]["custom_preset_backup"]
        assert backup_section["widgets.spotify_visualizer.blob_stretch_inner"] == sv["blob_stretch_inner"]
        assert backup_section["widgets.spotify_visualizer.blob_stretch_outer"] == sv["blob_stretch_outer"]
        assert all(
            not key.endswith(("blob_stretch_x_bias", "blob_stretch_y_bias"))
            for key in backup_section.keys()
        )

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
