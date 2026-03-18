"""Phase 1 Ghost Isolation Tests — Visualizer Parity Recovery.

Validates that per-mode ghosting fields are strictly isolated:
- Widget attrs exist for all modes
- config_applier applies and pushes per-mode ghost fields
- Overlay set_state stores per-mode ghost attrs without cross-mode bleed
- Renderers read mode-specific ghost fields
- Settings model round-trips per-mode ghost settings
"""
from __future__ import annotations

import inspect
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# 1. Widget per-mode ghost attributes exist
# ===========================================================================

class TestWidgetGhostAttrs:
    """Every mode's ghost attrs must exist on the widget with correct defaults."""

    GHOST_ATTRS = {
        "spectrum": {
            "_spectrum_ghosting_enabled": True,
            "_spectrum_ghost_alpha": 0.4,
            "_spectrum_ghost_decay": 0.4,
        },
        "blob": {
            "_blob_ghosting_enabled": False,
            "_blob_ghost_alpha": 0.4,
            "_blob_ghost_decay": 0.3,
        },
        "sine_wave": {
            "_sine_ghosting_enabled": True,
            "_sine_ghost_alpha": 0.45,
            "_sine_ghost_decay": 0.3,
        },
        "bubble": {
            "_bubble_ghosting_enabled": False,
            "_bubble_ghost_alpha": 0.0,
            "_bubble_ghost_decay": 0.4,
        },
        "oscilloscope": {
            "_osc_ghosting_enabled": False,
            "_osc_ghost_intensity": 0.4,
        },
    }

    def test_widget_has_all_ghost_attrs(self):
        src = (ROOT / "widgets" / "spotify_visualizer_widget.py").read_text(encoding="utf-8")
        for mode, attrs in self.GHOST_ATTRS.items():
            for attr in attrs:
                assert attr in src, f"Widget missing ghost attr {attr} for mode {mode}"

    def test_overlay_init_has_all_ghost_attrs(self):
        src = (ROOT / "widgets" / "spotify_bars_gl_overlay.py").read_text(encoding="utf-8")
        for mode, attrs in self.GHOST_ATTRS.items():
            if mode == "oscilloscope":
                continue  # osc uses _osc_ghost_alpha derived from intensity
            for attr in attrs:
                assert f"self.{attr}" in src, (
                    f"Overlay __init__ missing ghost attr {attr} for mode {mode}"
                )


# ===========================================================================
# 2. config_applier handles all per-mode ghost fields
# ===========================================================================

class TestConfigApplierGhost:
    """config_applier must apply and push per-mode ghost settings."""

    PER_MODE_GHOST_KEYS = [
        "spectrum_ghosting_enabled", "spectrum_ghost_alpha", "spectrum_ghost_decay",
        "blob_ghosting_enabled", "blob_ghost_alpha", "blob_ghost_decay",
        "sine_ghosting_enabled", "sine_ghost_alpha", "sine_ghost_decay",
        "bubble_ghosting_enabled", "bubble_ghost_alpha", "bubble_ghost_decay",
        "osc_ghosting_enabled", "osc_ghost_intensity",
    ]

    def test_apply_vis_mode_kwargs_handles_all_ghost_keys(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "config_applier.py").read_text(encoding="utf-8")
        for key in self.PER_MODE_GHOST_KEYS:
            assert f"'{key}'" in src, (
                f"config_applier.apply_vis_mode_kwargs missing handler for '{key}'"
            )

    def test_build_gpu_push_extra_kwargs_includes_all_ghost_keys(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "config_applier.py").read_text(encoding="utf-8")
        for key in self.PER_MODE_GHOST_KEYS:
            assert f"extra['{key}']" in src, (
                f"build_gpu_push_extra_kwargs missing '{key}' in extra dict"
            )

    def test_apply_spectrum_ghost_sets_widget_attrs(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _spectrum_ghosting_enabled = True
            _spectrum_ghost_alpha = 0.4
            _spectrum_ghost_decay = 0.4

        w = DummyWidget()
        apply_vis_mode_kwargs(w, {
            "spectrum_ghosting_enabled": False,
            "spectrum_ghost_alpha": 0.7,
            "spectrum_ghost_decay": 0.5,
        })
        assert w._spectrum_ghosting_enabled is False
        assert abs(w._spectrum_ghost_alpha - 0.7) < 1e-6
        assert abs(w._spectrum_ghost_decay - 0.5) < 1e-6

    def test_apply_sine_ghost_sets_widget_attrs(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _sine_ghosting_enabled = True
            _sine_ghost_alpha = 0.45
            _sine_ghost_decay = 0.3

        w = DummyWidget()
        apply_vis_mode_kwargs(w, {
            "sine_ghosting_enabled": False,
            "sine_ghost_alpha": 0.2,
            "sine_ghost_decay": 0.8,
        })
        assert w._sine_ghosting_enabled is False
        assert abs(w._sine_ghost_alpha - 0.2) < 1e-6
        assert abs(w._sine_ghost_decay - 0.8) < 1e-6

    def test_apply_bubble_ghost_sets_widget_attrs(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _bubble_ghosting_enabled = False
            _bubble_ghost_alpha = 0.0
            _bubble_ghost_decay = 0.4

        w = DummyWidget()
        apply_vis_mode_kwargs(w, {
            "bubble_ghosting_enabled": True,
            "bubble_ghost_alpha": 0.6,
            "bubble_ghost_decay": 0.9,
        })
        assert w._bubble_ghosting_enabled is True
        assert abs(w._bubble_ghost_alpha - 0.6) < 1e-6
        assert abs(w._bubble_ghost_decay - 0.9) < 1e-6


# ===========================================================================
# 3. Overlay set_state accepts all per-mode ghost params
# ===========================================================================

class TestOverlaySetStateGhostParams:
    """set_state must accept per-mode ghost params in its signature."""

    REQUIRED_PARAMS = [
        "spectrum_ghosting_enabled", "spectrum_ghost_alpha", "spectrum_ghost_decay",
        "blob_ghosting_enabled", "blob_ghost_alpha", "blob_ghost_decay",
        "sine_ghosting_enabled", "sine_ghost_alpha", "sine_ghost_decay",
        "bubble_ghosting_enabled", "bubble_ghost_alpha", "bubble_ghost_decay",
        "osc_ghosting_enabled", "osc_ghost_intensity",
    ]

    def test_set_state_signature_has_all_ghost_params(self):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
        sig = inspect.signature(SpotifyBarsGLOverlay.set_state)
        params = set(sig.parameters.keys()) - {"self"}
        for p in self.REQUIRED_PARAMS:
            assert p in params, f"set_state missing per-mode ghost param: {p}"


# ===========================================================================
# 4. Renderers read mode-specific ghost fields (no global bleed)
# ===========================================================================

class TestRendererGhostIsolation:
    """Renderers must read mode-specific ghost fields, not global ones."""

    def test_spectrum_renderer_reads_spectrum_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "spectrum.py").read_text(encoding="utf-8")
        assert "_spectrum_ghosting_enabled" in src, (
            "Spectrum renderer must read _spectrum_ghosting_enabled, not global"
        )
        assert "_spectrum_ghost_alpha" in src, (
            "Spectrum renderer must read _spectrum_ghost_alpha, not global"
        )

    def test_spectrum_renderer_does_not_read_global_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "spectrum.py").read_text(encoding="utf-8")
        # Should NOT contain bare s._ghosting_enabled (global) or s._ghost_alpha (global)
        # but may contain _spectrum_ghosting_enabled which includes the substring
        import re
        global_ghost_refs = re.findall(r's\._ghosting_enabled(?!_)', src)
        assert not global_ghost_refs, (
            f"Spectrum renderer still reads global s._ghosting_enabled: {global_ghost_refs}"
        )
        global_alpha_refs = re.findall(r's\._ghost_alpha(?!_)', src)
        assert not global_alpha_refs, (
            f"Spectrum renderer still reads global s._ghost_alpha: {global_alpha_refs}"
        )

    def test_blob_renderer_reads_blob_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "blob.py").read_text(encoding="utf-8")
        assert "_blob_ghosting_enabled" in src, (
            "Blob renderer must read _blob_ghosting_enabled, not global"
        )
        assert "_blob_ghost_alpha" in src, (
            "Blob renderer must read _blob_ghost_alpha, not global"
        )

    def test_blob_renderer_does_not_read_global_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "blob.py").read_text(encoding="utf-8")
        import re
        global_ghost_refs = re.findall(r's\._ghosting_enabled(?!_)', src)
        assert not global_ghost_refs, (
            f"Blob renderer still reads global s._ghosting_enabled: {global_ghost_refs}"
        )
        global_alpha_refs = re.findall(r's\._ghost_alpha(?!_)', src)
        assert not global_alpha_refs, (
            f"Blob renderer still reads global s._ghost_alpha: {global_alpha_refs}"
        )

    def test_osc_renderer_reads_osc_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "oscilloscope.py").read_text(encoding="utf-8")
        assert "_osc_ghost_alpha" in src, (
            "Oscilloscope renderer must read _osc_ghost_alpha"
        )

    def test_sine_renderer_reads_sine_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "sine_wave.py").read_text(encoding="utf-8")
        assert "_sine_ghosting_enabled" in src, (
            "Sine wave renderer must read _sine_ghosting_enabled, not global"
        )
        assert "_sine_ghost_alpha" in src, (
            "Sine wave renderer must read _sine_ghost_alpha, not global"
        )

    def test_sine_renderer_does_not_read_global_ghost(self):
        import re
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "sine_wave.py").read_text(encoding="utf-8")
        global_ghost_refs = re.findall(r's\._ghosting_enabled(?!_)', src)
        assert not global_ghost_refs, (
            f"Sine wave renderer still reads global s._ghosting_enabled: {global_ghost_refs}"
        )
        global_alpha_refs = re.findall(r's\._ghost_alpha(?!_)', src)
        assert not global_alpha_refs, (
            f"Sine wave renderer still reads global s._ghost_alpha: {global_alpha_refs}"
        )

    def test_bubble_renderer_reads_bubble_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "bubble.py").read_text(encoding="utf-8")
        assert "_bubble_ghosting_enabled" in src, (
            "Bubble renderer must read _bubble_ghosting_enabled, not global"
        )
        assert "_bubble_ghost_alpha" in src, (
            "Bubble renderer must read _bubble_ghost_alpha, not global"
        )

    def test_bubble_renderer_does_not_read_global_ghost(self):
        import re
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "bubble.py").read_text(encoding="utf-8")
        global_ghost_refs = re.findall(r's\._ghosting_enabled(?!_)', src)
        assert not global_ghost_refs, (
            f"Bubble renderer still reads global s._ghosting_enabled: {global_ghost_refs}"
        )
        global_alpha_refs = re.findall(r's\._ghost_alpha(?!_)', src)
        assert not global_alpha_refs, (
            f"Bubble renderer still reads global s._ghost_alpha: {global_alpha_refs}"
        )

    def test_sine_shader_has_ghost_uniform(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "sine_wave.frag").read_text(encoding="utf-8")
        assert "uniform float u_ghost_alpha" in src, (
            "sine_wave.frag must declare uniform float u_ghost_alpha"
        )

    def test_bubble_shader_has_ghost_uniform(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "bubble.frag").read_text(encoding="utf-8")
        assert "uniform float u_ghost_alpha" in src, (
            "bubble.frag must declare uniform float u_ghost_alpha"
        )


# ===========================================================================
# 5. Overlay blob peak gate uses blob-specific, not global
# ===========================================================================

class TestOverlayBlobPeakGate:
    """Blob peak energy tracking must be gated by _blob_ghosting_enabled."""

    def test_blob_peak_gate_uses_blob_specific(self):
        src = (ROOT / "widgets" / "spotify_bars_gl_overlay.py").read_text(encoding="utf-8")
        assert "self._blob_ghosting_enabled" in src, (
            "Overlay blob peak gate must use self._blob_ghosting_enabled"
        )

    def test_peak_decay_routed_per_mode(self):
        """peak_decay_per_sec must be routed from mode-specific ghost_decay."""
        src = (ROOT / "widgets" / "spotify_bars_gl_overlay.py").read_text(encoding="utf-8")
        assert "self._spectrum_ghost_decay" in src and "_peak_decay_per_sec" in src, (
            "Spectrum peak decay must be routed from _spectrum_ghost_decay"
        )
        assert "self._blob_ghost_decay" in src and "_peak_decay_per_sec" in src, (
            "Blob peak decay must be routed from _blob_ghost_decay"
        )


# ===========================================================================
# 6. Creator kwargs pass per-mode ghost settings
# ===========================================================================

class TestCreatorGhostKwargs:
    """spotify_widget_creators must pass all per-mode ghost settings."""

    GHOST_KWARGS = [
        "spectrum_ghosting_enabled", "spectrum_ghost_alpha", "spectrum_ghost_decay",
        "blob_ghosting_enabled", "blob_ghost_alpha", "blob_ghost_decay",
        "sine_ghosting_enabled", "sine_ghost_alpha", "sine_ghost_decay",
        "bubble_ghosting_enabled", "bubble_ghost_alpha", "bubble_ghost_decay",
        "osc_ghosting_enabled", "osc_ghost_intensity",
    ]

    def test_all_ghost_kwargs_passed_from_model(self):
        src = (ROOT / "rendering" / "spotify_widget_creators.py").read_text(encoding="utf-8")
        for key in self.GHOST_KWARGS:
            assert f"{key}=model.{key}" in src, (
                f"Creator missing ghost passthrough: {key}=model.{key}"
            )


# ===========================================================================
# 7. Settings model round-trip for per-mode ghost fields
# ===========================================================================

class TestSettingsModelGhostRoundTrip:
    """Per-mode ghost settings must survive model load/save."""

    def test_spectrum_ghost_round_trip(self):
        from core.settings.models import SpotifyVisualizerSettings
        P = "widgets.spotify_visualizer"

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "spectrum",
            f"{P}.preset_spectrum": 3,
            f"{P}.spectrum_ghosting_enabled": False,
            f"{P}.spectrum_ghost_alpha": 0.8,
            f"{P}.spectrum_ghost_decay": 0.6,
        })
        assert model.spectrum_ghosting_enabled is False
        assert abs(model.spectrum_ghost_alpha - 0.8) < 1e-6
        assert abs(model.spectrum_ghost_decay - 0.6) < 1e-6

        d = model.to_dict()
        assert d[f"{P}.spectrum_ghosting_enabled"] is False
        assert abs(d[f"{P}.spectrum_ghost_alpha"] - 0.8) < 1e-6

    def test_sine_ghost_round_trip(self):
        from core.settings.models import SpotifyVisualizerSettings
        P = "widgets.spotify_visualizer"

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "sine_wave",
            f"{P}.preset_sine_wave": 3,
            f"{P}.sine_ghosting_enabled": False,
            f"{P}.sine_ghost_alpha": 0.9,
            f"{P}.sine_ghost_decay": 0.7,
        })
        assert model.sine_ghosting_enabled is False
        assert abs(model.sine_ghost_alpha - 0.9) < 1e-6

    def test_bubble_ghost_round_trip(self):
        from core.settings.models import SpotifyVisualizerSettings
        P = "widgets.spotify_visualizer"

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "bubble",
            f"{P}.preset_bubble": 3,
            f"{P}.bubble_ghosting_enabled": True,
            f"{P}.bubble_ghost_alpha": 0.5,
            f"{P}.bubble_ghost_decay": 0.3,
        })
        assert model.bubble_ghosting_enabled is True
        assert abs(model.bubble_ghost_alpha - 0.5) < 1e-6

    def test_blob_ghost_round_trip(self):
        from core.settings.models import SpotifyVisualizerSettings
        P = "widgets.spotify_visualizer"

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "blob",
            f"{P}.preset_blob": 3,
            f"{P}.blob_ghosting_enabled": True,
            f"{P}.blob_ghost_alpha": 0.6,
            f"{P}.blob_ghost_decay": 0.5,
        })
        assert model.blob_ghosting_enabled is True
        assert abs(model.blob_ghost_alpha - 0.6) < 1e-6


# ===========================================================================
# 8. No cross-mode bleed: changing one mode's ghost doesn't affect others
# ===========================================================================

class TestNoCrossModeGhostBleed:
    """Applying ghost settings for one mode must not affect other modes."""

    def test_spectrum_ghost_does_not_affect_blob(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _spectrum_ghosting_enabled = True
            _spectrum_ghost_alpha = 0.4
            _spectrum_ghost_decay = 0.4
            _blob_ghosting_enabled = False
            _blob_ghost_alpha = 0.4
            _blob_ghost_decay = 0.3

        w = DummyWidget()
        apply_vis_mode_kwargs(w, {
            "spectrum_ghosting_enabled": False,
            "spectrum_ghost_alpha": 0.9,
        })
        assert w._spectrum_ghosting_enabled is False
        assert abs(w._spectrum_ghost_alpha - 0.9) < 1e-6
        # Blob must NOT be affected
        assert w._blob_ghosting_enabled is False
        assert abs(w._blob_ghost_alpha - 0.4) < 1e-6

    def test_bubble_specular_max_size_caps_big_bubble(self):
        """big_specular_max_size must cap spec_factor for big bubbles only."""
        from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation

        sim = BubbleSimulation()
        settings = {
            "bubble_big_count": 2,
            "bubble_small_count": 2,
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
            "bubble_big_size_max": 0.038,
            "bubble_small_size_max": 0.018,
            "bubble_trail_strength": 0.0,
        }
        eb = {"bass": 0.0, "mid": 0.0, "high": 0.0, "overall": 0.0,
              "smooth_mid": 0.0, "smooth_high": 0.0}
        sim.tick(0.016, eb, settings)
        sim.tick(0.016, eb, settings)

        # Force high pulse energy on all big bubbles
        for b in sim._bubbles:
            b.pulse_energy = 1.0

        # Snapshot with a tight cap
        cap = 1.5
        pos, extra, trail = sim.snapshot(
            bass=1.0, mid_high=0.5,
            big_bass_pulse=1.0, small_freq_pulse=1.0,
            big_specular_max_size=cap,
        )
        # extra is [spec_factor, rotation, spec_ox, spec_oy] × count
        for i, b in enumerate(sim._bubbles):
            sf = extra[i * 4]  # spec_factor for this bubble
            if b.is_big:
                assert sf <= cap + 1e-6, f"big bubble spec_factor {sf} exceeds cap {cap}"

    def test_spectrum_ghost_ui_save_includes_mode_specific_keys(self):
        """The UI save dict must include spectrum_ghosting_enabled/alpha/decay
        alongside legacy global keys so from_mapping picks them up."""
        from core.settings.models import SpotifyVisualizerSettings

        # Simulate what the save path produces
        save_dict = {
            "mode": "spectrum",
            "preset_spectrum": 3,
            "ghosting_enabled": False,
            "ghost_alpha": 0.75,
            "ghost_decay": 0.55,
            "spectrum_ghosting_enabled": False,
            "spectrum_ghost_alpha": 0.75,
            "spectrum_ghost_decay": 0.55,
        }
        model = SpotifyVisualizerSettings.from_mapping(save_dict)
        assert model.spectrum_ghosting_enabled is False
        assert abs(model.spectrum_ghost_alpha - 0.75) < 1e-6
        assert abs(model.spectrum_ghost_decay - 0.55) < 1e-6

        # Verify to_dict round-trip preserves mode-specific keys
        d = model.to_dict()
        P = "widgets.spotify_visualizer"
        assert d[f"{P}.spectrum_ghosting_enabled"] is False
        assert abs(d[f"{P}.spectrum_ghost_alpha"] - 0.75) < 1e-6
        assert abs(d[f"{P}.spectrum_ghost_decay"] - 0.55) < 1e-6

    def test_sine_ghost_ui_save_includes_mode_specific_keys(self):
        """The UI save dict must include sine_ghosting_enabled/alpha/decay
        so from_mapping picks them up correctly."""
        from core.settings.models import SpotifyVisualizerSettings

        save_dict = {
            "mode": "sine_wave",
            "sine_ghosting_enabled": False,
            "sine_ghost_alpha": 0.65,
            "sine_ghost_decay": 0.50,
        }
        model = SpotifyVisualizerSettings.from_mapping(save_dict)
        assert model.sine_ghosting_enabled is False
        assert abs(model.sine_ghost_alpha - 0.65) < 1e-6
        assert abs(model.sine_ghost_decay - 0.50) < 1e-6

        d = model.to_dict()
        P = "widgets.spotify_visualizer"
        assert d[f"{P}.sine_ghosting_enabled"] is False
        assert abs(d[f"{P}.sine_ghost_alpha"] - 0.65) < 1e-6
        assert abs(d[f"{P}.sine_ghost_decay"] - 0.50) < 1e-6

    def test_bubble_ghost_ui_save_includes_mode_specific_keys(self):
        """The UI save dict must include bubble_ghosting_enabled/alpha/decay
        so from_mapping picks them up correctly."""
        from core.settings.models import SpotifyVisualizerSettings

        save_dict = {
            "mode": "bubble",
            "bubble_ghosting_enabled": True,
            "bubble_ghost_alpha": 0.30,
            "bubble_ghost_decay": 0.60,
        }
        model = SpotifyVisualizerSettings.from_mapping(save_dict)
        assert model.bubble_ghosting_enabled is True
        assert abs(model.bubble_ghost_alpha - 0.30) < 1e-6
        assert abs(model.bubble_ghost_decay - 0.60) < 1e-6

        d = model.to_dict()
        P = "widgets.spotify_visualizer"
        assert d[f"{P}.bubble_ghosting_enabled"] is True
        assert abs(d[f"{P}.bubble_ghost_alpha"] - 0.30) < 1e-6
        assert abs(d[f"{P}.bubble_ghost_decay"] - 0.60) < 1e-6

    def test_spectrum_drop_speed_round_trip(self):
        """spectrum_drop_speed must survive from_mapping → to_dict round-trip."""
        from core.settings.models import SpotifyVisualizerSettings

        save_dict = {
            "mode": "spectrum",
            "spectrum_drop_speed": 2.5,
        }
        model = SpotifyVisualizerSettings.from_mapping(save_dict)
        assert abs(model.spectrum_drop_speed - 2.5) < 1e-6

        d = model.to_dict()
        P = "widgets.spotify_visualizer"
        assert abs(d[f"{P}.spectrum_drop_speed"] - 2.5) < 1e-6

    def test_spectrum_drop_speed_affects_visual_smoothing(self):
        """Higher drop speed → faster bar decay in visual smoothing."""
        from widgets.spotify_visualizer.tick_helpers import apply_visual_smoothing

        class FakeWidget:
            _bar_count = 4
            _visual_bars = [0.8, 0.8, 0.8, 0.8]
            _last_visual_smooth_ts = 100.0
            _visual_smoothing_tau = 0.055
            _vis_mode_str = 'spectrum'
            _spectrum_drop_speed = 1.0

        # Bars dropping from 0.8 → 0.0
        target = [0.0, 0.0, 0.0, 0.0]
        now = 100.016  # ~16ms later

        # Default speed (1.0)
        w1 = FakeWidget()
        apply_visual_smoothing(w1, target, now)
        after_default = list(w1._visual_bars)

        # Fast speed (2.5)
        w2 = FakeWidget()
        w2._spectrum_drop_speed = 2.5
        apply_visual_smoothing(w2, target, now)
        after_fast = list(w2._visual_bars)

        # Fast drop should produce LOWER bar values (closer to target 0)
        for i in range(4):
            assert after_fast[i] < after_default[i], (
                f"Bar {i}: fast={after_fast[i]:.4f} should be < default={after_default[i]:.4f}"
            )

    def test_all_color_fields_roundtrip(self):
        """Every color list field in SpotifyVisualizerSettings must survive from_mapping → to_dict."""
        from core.settings.models import SpotifyVisualizerSettings

        COLOR_FIELDS = {
            "osc_glow_color": [10, 20, 30, 200],
            "osc_line_color": [100, 110, 120, 255],
            "osc_line2_color": [130, 140, 150, 230],
            "osc_line2_glow_color": [160, 170, 180, 180],
            "osc_line3_color": [190, 200, 210, 230],
            "osc_line3_glow_color": [220, 230, 240, 180],
            "blob_color": [11, 22, 33, 230],
            "blob_glow_color": [44, 55, 66, 180],
            "blob_edge_color": [77, 88, 99, 230],
            "blob_outline_color": [111, 122, 133, 200],
            "sine_glow_color": [177, 188, 199, 230],
            "sine_line_color": [200, 201, 202, 255],
            "sine_line2_color": [203, 204, 205, 230],
            "sine_line2_glow_color": [206, 207, 208, 180],
            "sine_line3_color": [209, 210, 211, 230],
            "sine_line3_glow_color": [212, 213, 214, 180],
            "bubble_outline_color": [215, 216, 217, 230],
            "bubble_specular_color": [218, 219, 220, 255],
            "bubble_pop_color": [221, 222, 223, 180],
        }
        save_dict = {"mode": "spectrum"}
        save_dict.update(COLOR_FIELDS)

        model = SpotifyVisualizerSettings.from_mapping(save_dict)
        d = model.to_dict()
        P = "widgets.spotify_visualizer"

        for key, expected in COLOR_FIELDS.items():
            actual = d.get(f"{P}.{key}")
            assert actual == expected, (
                f"Color field '{key}' roundtrip failed: expected {expected}, got {actual}"
            )

    def test_spectrum_drop_speed_affects_dsp_decay(self):
        """Higher drop_speed on audio worker → faster decay in bar_computation reactive smoothing."""
        import time
        import numpy as np
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        from widgets.spotify_visualizer.bar_computation import _apply_reactive_smoothing

        recent_ts = time.time() - 0.016  # 16ms ago — normal frame interval

        def _make_worker(drop_speed: float):
            w = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
            w._bar_count = 4
            w._bar_history = np.array([0.8, 0.8, 0.8, 0.8], dtype="float32")
            w._bar_hold_timers = np.zeros(4, dtype="int32")
            w._last_fft_ts = recent_ts
            w._drop_threshold = 0.16
            w._drop_hold_frames = 2
            w._drop_snap_fraction = 0.58
            w._drop_speed = drop_speed
            return w

        # Bars dropping from 0.8 → 0.2 (a large drop)
        target = np.array([0.2, 0.2, 0.2, 0.2], dtype="float32")

        w_default = _make_worker(1.0)
        arr_default = target.copy()
        _apply_reactive_smoothing(w_default, arr_default, 4, np)

        w_fast = _make_worker(2.5)
        arr_fast = target.copy()
        _apply_reactive_smoothing(w_fast, arr_fast, 4, np)

        # Faster drop speed → bars decay more toward target (lower values)
        for i in range(4):
            assert arr_fast[i] < arr_default[i], (
                f"Bar {i}: fast_dsp={arr_fast[i]:.4f} should be < default_dsp={arr_default[i]:.4f}"
            )

    def test_audio_worker_set_drop_speed(self):
        """Audio worker set_drop_speed stores clamped value."""
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        w = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
        w._drop_speed = 1.0
        w.set_drop_speed(2.5)
        assert abs(w._drop_speed - 2.5) < 1e-6
        w.set_drop_speed(0.1)
        assert abs(w._drop_speed - 0.5) < 1e-6  # clamped to 0.5
        w.set_drop_speed(5.0)
        assert abs(w._drop_speed - 3.0) < 1e-6  # clamped to 3.0

    def test_agc_limiter_scales_down_hot_signal(self):
        """When short-term envelope > 1.0, normalizer should scale bars down."""
        import numpy as np
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        from widgets.spotify_visualizer.bar_computation import _apply_adaptive_normalization

        w = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
        w._env_short = 1.3   # already hot
        w._env_long = 1.2
        w._running_peak = 1.3

        arr = np.array([1.4, 1.2, 0.9, 0.6], dtype="float32")
        original_max = float(arr.max())
        _apply_adaptive_normalization(w, arr, 0.0, False, np)
        # Should have been scaled down
        assert float(arr.max()) < original_max, "Limiter did not scale down hot signal"

    def test_agc_sustained_loud_preserves_dynamics(self):
        """When short ≈ long (sustained loud), normalizer should NOT compress."""
        import numpy as np
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        from widgets.spotify_visualizer.bar_computation import _apply_adaptive_normalization

        w = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
        w._env_short = 0.7   # both envelopes roughly equal = sustained level
        w._env_long = 0.7
        w._running_peak = 0.7

        arr = np.array([0.7, 0.5, 0.3, 0.2], dtype="float32")
        before = arr.copy()
        _apply_adaptive_normalization(w, arr, 0.0, False, np)
        # Should be mostly unchanged (no limiter, no recovery)
        diff = float(np.max(np.abs(arr - before)))
        assert diff < 0.05, f"Sustained-loud section was altered by {diff:.3f}"

    def test_agc_recovery_after_loud(self):
        """When short << long (quiet after loud), normalizer should gently boost."""
        import numpy as np
        from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
        from widgets.spotify_visualizer.bar_computation import _apply_adaptive_normalization

        w = SpotifyVisualizerAudioWorker.__new__(SpotifyVisualizerAudioWorker)
        w._env_short = 0.1    # sudden quiet
        w._env_long = 0.7     # still remembers loud section
        w._running_peak = 0.1

        arr = np.array([0.15, 0.10, 0.08, 0.05], dtype="float32")
        before_sum = float(arr.sum())
        _apply_adaptive_normalization(w, arr, 0.0, False, np)
        after_sum = float(arr.sum())
        # Should have been gently boosted
        assert after_sum > before_sum, "Recovery did not boost quiet-after-loud signal"

    def test_notch_positions_round_trip(self):
        """spectrum_notch_positions_mirrored/linear must survive from_mapping → to_dict."""
        from core.settings.models import SpotifyVisualizerSettings

        custom_mir = [[0.0, "Mid"], [0.40, "Vocal"], [0.70, "Low-Mid"], [1.0, "Bass"]]
        custom_lin = [[0.0, "Bass"], [0.20, "Low"], [0.55, "Mid"], [0.80, "Hi-Mid"], [1.0, "Treble"]]
        save_dict = {
            "mode": "spectrum",
            "spectrum_notch_positions_mirrored": custom_mir,
            "spectrum_notch_positions_linear": custom_lin,
        }
        model = SpotifyVisualizerSettings.from_mapping(save_dict)
        assert model.spectrum_notch_positions_mirrored == custom_mir
        assert model.spectrum_notch_positions_linear == custom_lin

        d = model.to_dict()
        P = "widgets.spotify_visualizer"
        assert d[f"{P}.spectrum_notch_positions_mirrored"] == custom_mir
        assert d[f"{P}.spectrum_notch_positions_linear"] == custom_lin

    def test_blob_ghost_does_not_affect_sine(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        class DummyWidget:
            _blob_ghosting_enabled = False
            _blob_ghost_alpha = 0.4
            _sine_ghosting_enabled = True
            _sine_ghost_alpha = 0.45

        w = DummyWidget()
        apply_vis_mode_kwargs(w, {
            "blob_ghosting_enabled": True,
            "blob_ghost_alpha": 0.8,
        })
        assert w._blob_ghosting_enabled is True
        # Sine must NOT be affected
        assert w._sine_ghosting_enabled is True
        assert abs(w._sine_ghost_alpha - 0.45) < 1e-6
