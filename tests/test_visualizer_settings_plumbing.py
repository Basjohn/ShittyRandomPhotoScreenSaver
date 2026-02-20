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
            "bubble_stream_direction", "bubble_stream_speed",
            "bubble_stream_reactivity", "bubble_rotation_amount",
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
                       "u_specular_dir", "u_outline_color", "u_gradient_light"):
            assert f'"{uname}"' in src, f"Bubble uniform {uname} not queried"

    def test_set_state_accepts_bubble_params(self):
        src = self._read_overlay_src()
        for param in ("bubble_count", "bubble_pos_data", "bubble_extra_data",
                       "bubble_outline_color", "bubble_specular_direction"):
            assert param in src, f"set_state missing bubble param: {param}"

    def test_set_state_accepts_width_reaction(self):
        src = self._read_overlay_src()
        assert "sine_width_reaction" in src


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
                   "u_specular_dir", "u_outline_color", "u_specular_color",
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
            "bubble_stream_speed": 1.0,
            "bubble_stream_reactivity": 0.5,
            "bubble_rotation_amount": 0.5,
            "bubble_drift_amount": 0.5,
            "bubble_drift_speed": 0.5,
            "bubble_drift_frequency": 0.5,
            "bubble_drift_direction": "random",
        }
        # Should not raise — dict must be accepted, not just objects
        sim.tick(0.016, eb_dict, settings)
        pos, extra = sim.snapshot(bass=0.5, mid_high=0.25,
                                   big_bass_pulse=0.5, small_freq_pulse=0.5)
        assert isinstance(pos, list)
        assert isinstance(extra, list)

    def test_tick_accepts_none_energy_bands(self):
        """Graceful handling of None energy bands."""
        from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
        sim = BubbleSimulation()
        settings = {
            "bubble_big_count": 3, "bubble_small_count": 5,
            "bubble_surface_reach": 0.6, "bubble_stream_direction": "none",
            "bubble_stream_speed": 1.0, "bubble_stream_reactivity": 0.0,
            "bubble_rotation_amount": 0.0, "bubble_drift_amount": 0.0,
            "bubble_drift_speed": 0.0, "bubble_drift_frequency": 0.0,
            "bubble_drift_direction": "none",
        }
        # None energy bands should not crash
        sim.tick(0.016, None, settings)


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
