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
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor
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
            "_sine_ghost_line2_enabled": True,
            "_sine_ghost_line3_enabled": True,
        },
        "bubble": {
            "_bubble_ghosting_enabled": False,
            "_bubble_ghost_alpha": 0.0,
            "_bubble_ghost_decay": 0.4,
        },
        "oscilloscope": {
            "_osc_ghosting_enabled": False,
            "_osc_ghost_intensity": 0.4,
            "_osc_ghost_line2_enabled": True,
            "_osc_ghost_line3_enabled": True,
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
        "sine_ghost_line2_enabled", "sine_ghost_line3_enabled",
        "bubble_ghosting_enabled", "bubble_ghost_alpha", "bubble_ghost_decay",
        "osc_ghosting_enabled", "osc_ghost_intensity", "osc_ghost_line2_enabled", "osc_ghost_line3_enabled",
    ]

    def test_apply_vis_mode_kwargs_handles_all_ghost_keys(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "config_applier.py").read_text(encoding="utf-8")
        for key in self.PER_MODE_GHOST_KEYS:
            assert f"'{key}'" in src, (
                f"config_applier.apply_vis_mode_kwargs missing handler for '{key}'"
            )

    def test_build_gpu_push_extra_kwargs_includes_all_ghost_keys(self):
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs

        class DummyWidget:
            def __getattr__(self, name):
                if name.endswith("enabled"):
                    return False
                if "alpha" in name or "decay" in name or "intensity" in name:
                    return 0.0
                return 0

        extra = build_gpu_push_extra_kwargs(DummyWidget(), "spectrum", None)
        for key in self.PER_MODE_GHOST_KEYS:
            assert key in extra, (
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
        "sine_ghost_line2_enabled", "sine_ghost_line3_enabled",
        "bubble_ghosting_enabled", "bubble_ghost_alpha", "bubble_ghost_decay",
        "osc_ghosting_enabled", "osc_ghost_intensity", "osc_ghost_line2_enabled", "osc_ghost_line3_enabled",
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

    def test_blob_renderer_prefers_blob_live_energy_channels(self):
        from widgets.spotify_visualizer.renderers import blob as blob_renderer

        class FakeGL:
            def __init__(self):
                self.floats = {}
                self.ints = {}

            def glUniform1f(self, loc, value):
                self.floats[loc] = float(value)

            def glUniform1i(self, loc, value):
                self.ints[loc] = int(value)

            def glUniform3f(self, loc, a, b, c):
                self.floats[loc] = (float(a), float(b), float(c))

            def glUniform4f(self, loc, a, b, c, d):
                self.floats[loc] = (float(a), float(b), float(c), float(d))

        class FakeColor:
            def __init__(self, r=1.0, g=1.0, b=1.0, a=1.0):
                self._rgba = (r, g, b, a)

            def redF(self): return self._rgba[0]
            def greenF(self): return self._rgba[1]
            def blueF(self): return self._rgba[2]
            def alphaF(self): return self._rgba[3]

        gl = FakeGL()
        uniforms = {
            "u_playing": 1,
            "u_ghost_alpha": 2,
            "u_blob_color": 3,
            "u_blob_glow_color": 4,
            "u_blob_edge_color": 5,
            "u_blob_pulse": 6,
            "u_blob_width": 7,
            "u_blob_size": 8,
            "u_blob_glow_intensity": 9,
            "u_blob_glow_reactivity": 10,
            "u_blob_glow_max_size": 11,
            "u_blob_reactive_glow": 12,
            "u_blob_outline_color": 13,
            "u_blob_smoothed_energy": 14,
            "u_blob_peak_energy": 15,
            "u_blob_peak_bass": 16,
            "u_blob_peak_mid": 17,
            "u_blob_peak_high": 18,
            "u_blob_peak_overall": 19,
            "u_blob_reactive_deformation": 20,
            "u_blob_stage_gain": 21,
            "u_blob_core_scale": 22,
            "u_blob_core_floor_bias": 23,
            "u_blob_stage_bias": 24,
            "u_blob_stage_progress_override": 25,
            "u_blob_constant_wobble": 26,
            "u_blob_reactive_wobble": 27,
            "u_blob_stretch_tendency": 28,
            "u_blob_stretch_inner": 29,
            "u_blob_stretch_outer": 30,
            "u_overall_energy": 31,
            "u_bass_energy": 32,
            "u_mid_energy": 33,
            "u_high_energy": 34,
            "u_transient_bass": 35,
            "u_transient_mid": 36,
            "u_transient_high": 37,
        }
        state = SimpleNamespace(
            _playing=True,
            _blob_ghosting_enabled=True,
            _blob_ghost_alpha=0.4,
            _blob_color=FakeColor(),
            _blob_glow_color=FakeColor(),
            _blob_edge_color=FakeColor(),
            _blob_pulse=1.0,
            _blob_width=1.0,
            _blob_size=1.0,
            _blob_glow_intensity=0.5,
            _blob_glow_reactivity=1.0,
            _blob_glow_max_size=1.0,
            _blob_reactive_glow=True,
            _blob_outline_color=FakeColor(),
            _blob_smoothed_energy=0.7,
            _blob_peak_energy=0.9,
            _blob_peak_bass=0.8,
            _blob_peak_mid=0.6,
            _blob_peak_high=0.5,
            _blob_peak_overall=0.85,
            _blob_reactive_deformation=1.0,
            _blob_stage_gain=1.0,
            _blob_core_scale=1.0,
            _blob_core_floor_bias=0.35,
            _blob_stage_bias=0.0,
            _blob_stage_progress_filtered=(0.2, 0.3, 0.4),
            _blob_stage_progress_ready=True,
            _blob_constant_wobble=1.0,
            _blob_reactive_wobble=1.0,
            _blob_stretch_tendency=0.35,
            _blob_stretch_inner=0.5,
            _blob_stretch_outer=0.5,
            _blob_live_overall_energy=1.1,
            _blob_live_bass_energy=1.2,
            _blob_live_mid_energy=0.9,
            _blob_live_high_energy=0.4,
            _energy_bands=SimpleNamespace(overall=0.1, bass=0.2, mid=0.3, high=0.4),
            _transient_energy=SimpleNamespace(bass_transient=0.0, mid_transient=0.0, high_transient=0.0),
        )

        assert blob_renderer.upload_uniforms(gl, uniforms, state) is True
        assert gl.floats[31] == pytest.approx(1.1)
        assert gl.floats[32] == pytest.approx(1.2)
        assert gl.floats[33] == pytest.approx(0.9)
        assert gl.floats[34] == pytest.approx(0.4)

    @pytest.mark.qt
    def test_blob_set_state_uses_current_event_snapshot_consistently(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = 'blob'
        overlay._last_time_ts = time.time() - 0.016
        overlay._blob_kick_event_strength = 0.0
        overlay._blob_snare_event_strength = 0.0

        calls = []
        original = overlay._compute_blob_live_bands

        def _spy(energy_bands):
            calls.append(
                (
                    float(getattr(overlay, "_blob_kick_event_strength", 0.0)),
                    float(getattr(overlay, "_blob_snare_event_strength", 0.0)),
                )
            )
            return original(energy_bands)

        overlay._compute_blob_live_bands = _spy
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.0],
            bar_count=1,
            segments=1,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode='blob',
            energy_bands=SimpleNamespace(bass=0.2, mid=0.3, high=0.4, overall=0.25),
            blob_kick_event_strength=1.0,
            blob_snare_event_strength=0.5,
        )

        assert calls
        first_kick, first_snare = calls[0]
        assert first_kick > 0.0
        assert first_snare > 0.0
        assert all(kick == pytest.approx(first_kick) for kick, _ in calls)
        assert all(snare == pytest.approx(first_snare) for _, snare in calls)

    @pytest.mark.qt
    def test_blob_scheduler_event_envelope_persists_live_blob_between_frames(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = 'blob'
        energy = SimpleNamespace(bass=0.2, mid=0.15, high=0.1, overall=0.18)

        overlay._last_time_ts = time.time() - 0.016
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.0],
            bar_count=1,
            segments=1,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode='blob',
            energy_bands=energy,
            blob_kick_event_strength=1.0,
            blob_snare_event_strength=0.6,
        )
        first_bass = overlay._blob_live_bass_energy
        first_mid = overlay._blob_live_mid_energy
        first_stage_bass = overlay._blob_stage_input_bass
        first_stage_overall = overlay._blob_stage_input_overall

        overlay._last_time_ts = time.time() - 0.016
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.0],
            bar_count=1,
            segments=1,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode='blob',
            energy_bands=energy,
            blob_kick_event_strength=0.0,
            blob_snare_event_strength=0.0,
        )

        assert overlay._blob_kick_event_strength > 0.0
        assert overlay._blob_snare_event_strength > 0.0
        assert overlay._blob_live_bass_energy >= float(energy.bass)
        assert overlay._blob_live_mid_energy > float(energy.mid)
        assert overlay._blob_live_bass_energy <= first_bass
        assert overlay._blob_live_mid_energy < first_mid
        assert overlay._blob_stage_input_bass > float(energy.bass)
        assert overlay._blob_stage_input_overall > float(energy.overall)
        assert overlay._blob_stage_input_bass <= first_stage_bass
        assert overlay._blob_stage_input_overall <= first_stage_overall

    @pytest.mark.qt
    def test_blob_live_band_filter_prevents_one_frame_snap_back(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = 'blob'
        calm = SimpleNamespace(bass=0.10, mid=0.12, high=0.05, overall=0.10)
        hot_mid = SimpleNamespace(bass=0.12, mid=0.55, high=0.08, overall=0.20)

        overlay._last_time_ts = time.time() - 0.016
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.0],
            bar_count=1,
            segments=1,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode='blob',
            energy_bands=calm,
            blob_kick_event_strength=0.0,
            blob_snare_event_strength=0.0,
        )
        calm_live_mid = overlay._blob_live_mid_energy

        overlay._last_time_ts = time.time() - 0.016
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.0],
            bar_count=1,
            segments=1,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode='blob',
            energy_bands=hot_mid,
            blob_kick_event_strength=0.0,
            blob_snare_event_strength=1.0,
        )
        hot_live_mid = overlay._blob_live_mid_energy
        raw_hot_mid = overlay._blob_raw_mid_energy

        assert raw_hot_mid > hot_live_mid
        assert hot_live_mid > calm_live_mid

        overlay._last_time_ts = time.time() - 0.016
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.0],
            bar_count=1,
            segments=1,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode='blob',
            energy_bands=calm,
            blob_kick_event_strength=0.0,
            blob_snare_event_strength=0.0,
        )

        assert overlay._blob_live_mid_energy > calm.mid
        assert overlay._blob_live_mid_energy < hot_live_mid
        assert overlay._blob_live_overall_energy > calm.overall

    @pytest.mark.qt
    def test_blob_scheduler_boost_stays_bounded_on_calm_passages(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._blob_kick_event_strength = 1.0
        overlay._blob_snare_event_strength = 1.0

        bass, mid, high, overall = overlay._compute_blob_live_bands(
            SimpleNamespace(bass=0.05, mid=0.05, high=0.03, overall=0.04)
        )

        assert bass < 0.30
        assert mid < 0.22
        assert high < 0.13
        assert overall < 0.22

    @pytest.mark.qt
    def test_blob_scheduler_boost_tracks_underlying_music_support(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._blob_kick_event_strength = 1.0
        overlay._blob_snare_event_strength = 1.0

        calm = overlay._compute_blob_live_bands(
            SimpleNamespace(bass=0.05, mid=0.05, high=0.03, overall=0.04)
        )
        calm_stage = (
            overlay._blob_stage_input_bass,
            overlay._blob_stage_input_overall,
        )
        loud = overlay._compute_blob_live_bands(
            SimpleNamespace(bass=0.45, mid=0.35, high=0.20, overall=0.38)
        )
        loud_stage = (
            overlay._blob_stage_input_bass,
            overlay._blob_stage_input_overall,
        )

        assert loud[1] - 0.35 > calm[1] - 0.05
        assert loud_stage[0] - 0.45 > calm_stage[0] - 0.05
        assert loud_stage[1] - 0.38 > calm_stage[1] - 0.04

    @pytest.mark.qt
    def test_blob_snare_help_does_not_inflate_stage_overall_like_kick(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
        from widgets.spotify_visualizer.blob_math import compute_stage_progress

        overlay = SpotifyBarsGLOverlay(None)
        base = SimpleNamespace(bass=0.10, mid=0.26, high=0.10, overall=0.12)

        overlay._blob_kick_event_strength = 0.0
        overlay._blob_snare_event_strength = 1.0
        snare_bands = overlay._compute_blob_live_bands(base)
        snare_stage_inputs = (
            overlay._blob_stage_input_bass,
            overlay._blob_stage_input_mid,
            overlay._blob_stage_input_high,
            overlay._blob_stage_input_overall,
        )

        overlay._blob_kick_event_strength = 1.0
        overlay._blob_snare_event_strength = 0.0
        kick_bands = overlay._compute_blob_live_bands(base)
        kick_stage_inputs = (
            overlay._blob_stage_input_bass,
            overlay._blob_stage_input_mid,
            overlay._blob_stage_input_high,
            overlay._blob_stage_input_overall,
        )

        assert snare_bands[1] > kick_bands[1]
        assert snare_bands[3] <= kick_bands[3] + 0.02
        assert snare_stage_inputs[3] <= kick_stage_inputs[3]
        assert snare_stage_inputs[0] <= kick_stage_inputs[0]

        snare_stage = compute_stage_progress(
            bass_energy=snare_stage_inputs[0],
            mid_energy=snare_stage_inputs[1],
            high_energy=snare_stage_inputs[2],
            overall_energy=snare_stage_inputs[3],
            smoothed_energy=snare_bands[3],
        )
        kick_stage = compute_stage_progress(
            bass_energy=kick_stage_inputs[0],
            mid_energy=kick_stage_inputs[1],
            high_energy=kick_stage_inputs[2],
            overall_energy=kick_stage_inputs[3],
            smoothed_energy=kick_bands[3],
        )

        assert snare_stage[0] <= kick_stage[0]

    @pytest.mark.qt
    def test_blob_kick_lane_gain_can_disable_scheduler_kick_assist(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        base = SimpleNamespace(bass=0.10, mid=0.08, high=0.03, overall=0.09)
        transient = SimpleNamespace(bass_transient=0.35, mid_transient=0.0, high_transient=0.0)

        disabled = SpotifyBarsGLOverlay(None)
        disabled._kick_lane_gain = 0.0
        disabled._blob_kick_event_strength = 1.0
        disabled._blob_snare_event_strength = 0.0
        disabled._transient_energy = transient
        disabled_bands = disabled._compute_blob_live_bands(base)
        disabled_stage = (
            disabled._blob_stage_input_bass,
            disabled._blob_stage_input_overall,
        )

        enabled = SpotifyBarsGLOverlay(None)
        enabled._kick_lane_gain = 1.0
        enabled._blob_kick_event_strength = 1.0
        enabled._blob_snare_event_strength = 0.0
        enabled._transient_energy = transient
        enabled_bands = enabled._compute_blob_live_bands(base)
        enabled_stage = (
            enabled._blob_stage_input_bass,
            enabled._blob_stage_input_overall,
        )

        assert disabled_bands[0] <= enabled_bands[0]
        assert disabled_bands[3] <= enabled_bands[3]
        assert disabled_stage[0] < enabled_stage[0]
        assert disabled_stage[1] < enabled_stage[1]

    def test_osc_renderer_reads_osc_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "oscilloscope.py").read_text(encoding="utf-8")
        assert "_osc_ghost_alpha" in src, (
            "Oscilloscope renderer must read _osc_ghost_alpha"
        )
        assert "_osc_ghost_line2_enabled" in src, (
            "Oscilloscope renderer must read _osc_ghost_line2_enabled"
        )
        assert "_osc_ghost_line3_enabled" in src, (
            "Oscilloscope renderer must read _osc_ghost_line3_enabled"
        )

    def test_sine_renderer_reads_sine_ghost(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "renderers" / "sine_wave.py").read_text(encoding="utf-8")
        assert "_sine_ghosting_enabled" in src, (
            "Sine wave renderer must read _sine_ghosting_enabled, not global"
        )
        assert "_sine_ghost_alpha" in src, (
            "Sine wave renderer must read _sine_ghost_alpha, not global"
        )
        assert "_sine_ghost_line2_enabled" in src, (
            "Sine wave renderer must read _sine_ghost_line2_enabled"
        )
        assert "_sine_ghost_line3_enabled" in src, (
            "Sine wave renderer must read _sine_ghost_line3_enabled"
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

    def test_osc_renderer_uploads_zero_waveforms_after_reset(self):
        from widgets.spotify_visualizer.renderers import oscilloscope

        class FakeGL:
            def __init__(self):
                self.uniforms = {}

            def glUniform1fv(self, loc, count, values):
                self.uniforms[loc] = np.array(values, copy=True)

            def glUniform1f(self, loc, value):
                self.uniforms[loc] = float(value)

            def glUniform1i(self, loc, value):
                self.uniforms[loc] = int(value)

            def glUniform4f(self, loc, a, b, c, d):
                self.uniforms[loc] = (float(a), float(b), float(c), float(d))

        class FakeColor:
            def __init__(self, r=0.0, g=0.0, b=0.0, a=1.0):
                self._rgba = (r, g, b, a)

            def redF(self):
                return self._rgba[0]

            def greenF(self):
                return self._rgba[1]

            def blueF(self):
                return self._rgba[2]

            def alphaF(self):
                return self._rgba[3]

        gl = FakeGL()
        white = FakeColor(1.0, 1.0, 1.0, 1.0)
        clear = FakeColor(0.0, 0.0, 0.0, 1.0)
        uniforms = {
            "u_waveform": 1,
            "u_prev_waveform": 2,
            "u_waveform_count": 3,
            "u_osc_ghost_alpha": 4,
            "u_ghost_line2_enabled": 27,
            "u_ghost_line3_enabled": 28,
            "u_glow_enabled": 5,
            "u_glow_intensity": 6,
            "u_glow_size": 7,
            "u_glow_reactivity": 8,
            "u_glow_color": 9,
            "u_reactive_glow": 10,
            "u_sensitivity": 11,
            "u_smoothing": 12,
            "u_line_color": 13,
            "u_line_count": 14,
            "u_line2_color": 15,
            "u_line2_glow_color": 16,
            "u_line3_color": 17,
            "u_line3_glow_color": 18,
            "u_osc_speed": 19,
            "u_osc_line_dim": 20,
            "u_osc_line_offset_bias": 21,
            "u_osc_vertical_shift": 22,
            "u_overall_energy": 23,
            "u_bass_energy": 24,
            "u_mid_energy": 25,
            "u_high_energy": 26,
        }
        state = SimpleNamespace(
            _waveform=[],
            _waveform_count=0,
            _prev_waveform=[],
            _osc_ghost_alpha=0.0,
            _osc_ghost_line2_enabled=False,
            _osc_ghost_line3_enabled=True,
            _glow_enabled=False,
            _glow_intensity=0.0,
            _glow_size=1.0,
            _glow_reactivity=1.0,
            _glow_color=clear,
            _reactive_glow=False,
            _line_sensitivity=1.0,
            _line_smoothing=0.5,
            _line_color=white,
            _line_count=1,
            _line2_color=white,
            _line2_glow_color=white,
            _line3_color=white,
            _line3_glow_color=white,
            _line_smoothed_bass=0.0,
            _line_smoothed_mid=0.0,
            _line_smoothed_high=0.0,
            _osc_transient_width_mix=0.35,
            _line_kick_event_strength=0.0,
            _line_snare_event_strength=0.0,
            _energy_bands=SimpleNamespace(overall=0.0),
            _line_speed=1.0,
            _line_dim=False,
            _line_offset_bias=0.0,
            _osc_vertical_shift=0,
        )

        assert oscilloscope.upload_uniforms(gl, uniforms, state) is True
        assert np.count_nonzero(gl.uniforms[1]) == 0
        assert np.count_nonzero(gl.uniforms[2]) == 0
        assert gl.uniforms[3] == 2
        assert gl.uniforms[27] == 0
        assert gl.uniforms[28] == 1

    def test_osc_renderer_respects_waveform_count_for_padded_buffers(self):
        from widgets.spotify_visualizer.renderers import oscilloscope

        class FakeGL:
            def __init__(self):
                self.uniforms = {}

            def glUniform1fv(self, loc, count, values):
                self.uniforms[loc] = np.array(values, copy=True)

            def glUniform1f(self, loc, value):
                self.uniforms[loc] = float(value)

            def glUniform1i(self, loc, value):
                self.uniforms[loc] = int(value)

            def glUniform4f(self, loc, a, b, c, d):
                self.uniforms[loc] = (float(a), float(b), float(c), float(d))

        class FakeColor:
            def __init__(self, r=0.0, g=0.0, b=0.0, a=1.0):
                self._rgba = (r, g, b, a)

            def redF(self):
                return self._rgba[0]

            def greenF(self):
                return self._rgba[1]

            def blueF(self):
                return self._rgba[2]

            def alphaF(self):
                return self._rgba[3]

        gl = FakeGL()
        white = FakeColor(1.0, 1.0, 1.0, 1.0)
        clear = FakeColor(0.0, 0.0, 0.0, 1.0)
        uniforms = {
            "u_waveform": 1,
            "u_prev_waveform": 2,
            "u_waveform_count": 3,
            "u_osc_ghost_alpha": 4,
            "u_ghost_line2_enabled": 27,
            "u_ghost_line3_enabled": 28,
            "u_glow_enabled": 5,
            "u_glow_intensity": 6,
            "u_glow_size": 7,
            "u_glow_reactivity": 8,
            "u_glow_color": 9,
            "u_reactive_glow": 10,
            "u_sensitivity": 11,
            "u_smoothing": 12,
            "u_line_color": 13,
            "u_line_count": 14,
            "u_line2_color": 15,
            "u_line2_glow_color": 16,
            "u_line3_color": 17,
            "u_line3_glow_color": 18,
            "u_osc_speed": 19,
            "u_osc_line_dim": 20,
            "u_osc_line_offset_bias": 21,
            "u_osc_vertical_shift": 22,
            "u_overall_energy": 23,
            "u_bass_energy": 24,
            "u_mid_energy": 25,
            "u_high_energy": 26,
        }
        padded_waveform = [0.25] * 128 + [0.0] * 128
        state = SimpleNamespace(
            _waveform=padded_waveform,
            _waveform_count=128,
            _prev_waveform=[],
            _osc_ghost_alpha=0.0,
            _osc_ghost_line2_enabled=True,
            _osc_ghost_line3_enabled=False,
            _glow_enabled=False,
            _glow_intensity=0.0,
            _glow_size=1.0,
            _glow_reactivity=1.0,
            _glow_color=clear,
            _reactive_glow=False,
            _line_sensitivity=1.0,
            _line_smoothing=0.5,
            _line_color=white,
            _line_count=1,
            _line2_color=white,
            _line2_glow_color=white,
            _line3_color=white,
            _line3_glow_color=white,
            _line_smoothed_bass=0.0,
            _line_smoothed_mid=0.0,
            _line_smoothed_high=0.0,
            _osc_transient_width_mix=0.35,
            _line_kick_event_strength=0.0,
            _line_snare_event_strength=0.0,
            _energy_bands=SimpleNamespace(overall=0.0),
            _line_speed=1.0,
            _line_dim=False,
            _line_offset_bias=0.0,
            _osc_vertical_shift=0,
        )

        assert oscilloscope.upload_uniforms(gl, uniforms, state) is True
        assert gl.uniforms[3] == 128
        assert gl.uniforms[27] == 1
        assert gl.uniforms[28] == 0


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

    def test_blob_ghost_min_offset_stays_small(self):
        from widgets.spotify_visualizer.blob_math import compute_blob_ghost_min_offset

        offsets = [
            compute_blob_ghost_min_offset(0.0),
            compute_blob_ghost_min_offset(0.5),
            compute_blob_ghost_min_offset(1.0),
        ]
        assert offsets[0] >= 0.015
        assert offsets[1] > offsets[0]
        assert offsets[2] <= 0.035


class TestSpectrumGlowUniforms:
    def test_spectrum_renderer_uploads_rim_glow_uniforms(self):
        from widgets.spotify_visualizer.renderers import spectrum

        class FakeGL:
            def __init__(self):
                self.uniforms = {}

            def glUniform1fv(self, loc, count, values):
                self.uniforms[loc] = np.array(values, copy=True)

            def glUniform1f(self, loc, value):
                self.uniforms[loc] = float(value)

            def glUniform1i(self, loc, value):
                self.uniforms[loc] = int(value)

            def glUniform4f(self, loc, a, b, c, d):
                self.uniforms[loc] = (float(a), float(b), float(c), float(d))

        gl = FakeGL()
        uniforms = {
            "u_bar_count": 1,
            "u_segments": 2,
            "u_bar_height_scale": 3,
            "u_bars_left": 4,
            "u_bar_width_px": 5,
            "u_bar_gap_px": 6,
            "u_bar_span_px": 7,
            "u_single_piece": 8,
            "u_slanted": 9,
            "u_border_radius": 10,
            "u_bars": 11,
            "u_peaks": 12,
            "u_playing": 13,
            "u_ghost_alpha": 14,
            "u_fill_color": 15,
            "u_border_color": 16,
            "u_spectrum_glow_enabled": 17,
            "u_spectrum_glow_intensity": 18,
            "u_spectrum_glow_color": 19,
            "u_rainbow_per_bar": 20,
        }
        state = SimpleNamespace(
            _bar_count=5,
            _segments=12,
            _render_rect=SimpleNamespace(width=lambda: 320, height=lambda: 120),
            _single_piece=True,
            _slanted=False,
            _border_radius=3.0,
            _bars=[0.2, 0.4, 0.8, 0.4, 0.2],
            _peaks=[0.3, 0.5, 0.9, 0.5, 0.3],
            _bars_buffer=np.zeros(64, dtype="float32"),
            _peaks_buffer=np.zeros(64, dtype="float32"),
            _debug_bars_logged=True,
            _playing=True,
            _spectrum_ghost_alpha=0.25,
            _spectrum_ghosting_enabled=True,
            _fill_color=QColor(255, 180, 80, 230),
            _border_color=QColor(255, 240, 180, 255),
            _spectrum_glow_enabled=True,
            _spectrum_glow_intensity=0.94,
            _spectrum_glow_color=QColor(15, 230, 255, 210),
        )

        assert spectrum.upload_uniforms(gl, uniforms, state) is True
        assert gl.uniforms[17] == 1
        assert gl.uniforms[18] == pytest.approx(0.94)

    def test_oscilloscope_secondary_ghosts_use_glow_colors(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "oscilloscope.frag").read_text(encoding="utf-8")
        assert "u_line2_glow_color" in src
        assert "u_line3_glow_color" in src
        assert "u_line2_color, glowColor2" in src, (
            "Osc secondary ghost path must use line 2 glow color, not only the raw line color."
        )
        assert "u_line3_color, glowColor3" in src, (
            "Osc secondary ghost path must use line 3 glow color, not only the raw line color."
        )

    def test_blob_overlay_uses_peak_hold_instead_of_history_snapshot_path(self):
        src = (ROOT / "widgets" / "spotify_bars_gl_overlay.py").read_text(encoding="utf-8")
        assert "_blob_peak_hold_remaining = 0.15" in src
        assert "_blob_ghost_history" not in src

    def test_blob_overlay_tracks_live_blob_source_for_peak_memory(self):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = 'blob'
        overlay._blob_ghosting_enabled = True
        overlay._last_time_ts = time.time() - 0.016

        energy = SimpleNamespace(bass=0.22, mid=0.18, high=0.09, overall=0.20)
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.0],
            bar_count=1,
            segments=1,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode='blob',
            energy_bands=energy,
            blob_kick_event_strength=1.0,
            blob_snare_event_strength=0.4,
        )

        assert overlay._blob_stage_input_bass > float(energy.bass)
        assert overlay._blob_peak_bass >= overlay._blob_live_bass_energy
        assert overlay._blob_peak_energy >= overlay._blob_smoothed_energy

    def test_blob_shader_tracks_peak_phase_uniforms(self):
        src = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "blob.frag").read_text(encoding="utf-8")
        assert "u_blob_peak_stage_progress_override" not in src
        assert "u_blob_peak_time" not in src
        assert "float smoothed_energy" not in src
        assert "u_blob_smoothed_energy);" in src

    def test_blob_overlay_snapshots_peak_stage_progress(self):
        src = (ROOT / "widgets" / "spotify_bars_gl_overlay.py").read_text(encoding="utf-8")
        assert "_blob_peak_snapshot_pending" not in src
        assert "_blob_peak_stage_progress_filtered" not in src

    @pytest.mark.qt
    def test_blob_hitch_dt_does_not_force_full_one_frame_event_snap(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = 'blob'
        overlay._blob_ghosting_enabled = True
        overlay._last_time_ts = time.time() - 0.18

        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.0],
            bar_count=1,
            segments=1,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode='blob',
            energy_bands=SimpleNamespace(bass=0.16, mid=0.12, high=0.08, overall=0.14),
            blob_kick_event_strength=1.0,
            blob_snare_event_strength=0.9,
        )

        assert overlay._blob_kick_event_strength < 0.80
        assert overlay._blob_snare_event_strength < 0.75


class TestOverlayModeResetIsolation:
    @pytest.mark.qt
    def test_request_mode_reset_ignores_unknown_modes(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)

        overlay.request_mode_reset("not_a_real_mode")

        assert overlay._pending_mode_resets == set()

    @pytest.mark.qt
    def test_spectrum_mode_change_clears_shared_peak_history(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = "blob"
        overlay._peaks = [0.9, 0.8, 0.7]
        overlay._last_peak_ts = 123.0

        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.2, 0.3, 0.4],
            bar_count=3,
            segments=4,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode="spectrum",
        )

        assert overlay._vis_mode == "spectrum"
        assert overlay._peaks == pytest.approx([0.2, 0.3, 0.4])
        assert overlay._last_peak_ts > 0.0

    @pytest.mark.qt
    def test_non_spectrum_mode_change_clears_spectrum_peak_history(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = "spectrum"
        overlay._peaks = [0.6, 0.4, 0.2]
        overlay._last_peak_ts = 42.0

        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[1.0, 1.0, 1.0],
            bar_count=3,
            segments=4,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode="devcurve",
            devcurve_sample_count=4,
            devcurve_curve_bass=[0.2, 0.3, 0.2, 0.1],
        )

        assert overlay._vis_mode == "devcurve"
        assert overlay._peaks == []
        assert overlay._last_peak_ts == pytest.approx(0.0)

    @pytest.mark.qt
    def test_line_mode_reset_clears_waveform_count_and_buffers(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = "blob"
        overlay._waveform = [0.5] * 16
        overlay._prev_waveform = [0.25] * 16
        overlay._ghost_waveform_ring = [[0.1] * 16]
        overlay._waveform_count = 16

        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.2, 0.2, 0.2],
            bar_count=3,
            segments=4,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode="sine_wave",
            waveform=[0.1] * 8,
            waveform_count=8,
        )

        assert overlay._vis_mode == "sine_wave"
        assert overlay._prev_waveform == []
        assert overlay._ghost_waveform_ring == []
        assert overlay._waveform_count == 8
        assert overlay._blob_smoothed_energy < 0.45

    @pytest.mark.qt
    def test_line_mode_reset_clears_line_event_envelopes(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = "blob"
        overlay._line_kick_event_strength = 0.7
        overlay._line_snare_event_strength = 0.6
        overlay._line_kick_event_envelope = 0.7
        overlay._line_snare_event_envelope = 0.6

        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.2, 0.2, 0.2],
            bar_count=3,
            segments=4,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode="oscilloscope",
            waveform=[0.1] * 8,
            waveform_count=8,
        )

        assert overlay._vis_mode == "oscilloscope"
        assert overlay._line_kick_event_strength == pytest.approx(0.0)
        assert overlay._line_snare_event_strength == pytest.approx(0.0)
        assert overlay._line_kick_event_envelope == pytest.approx(0.0)
        assert overlay._line_snare_event_envelope == pytest.approx(0.0)

    @pytest.mark.qt
    def test_manual_overlay_reset_clears_mode_runtime_and_tracks_generation_handoff(self, qt_app):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay(None)
        overlay._vis_mode = "devcurve"
        overlay._waveform = [0.4] * 8
        overlay._prev_waveform = [0.2] * 8
        overlay._bubble_count = 5
        overlay._blob_smoothed_energy = 0.9
        overlay._line_kick_event_strength = 0.8

        overlay.request_mode_reset("devcurve")
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.2, 0.3, 0.4],
            bar_count=3,
            segments=4,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode="devcurve",
            devcurve_sample_count=4,
            devcurve_curve_bass=[0.2, 0.3, 0.4, 0.3],
            activation_id=11,
            engine_generation=17,
            latest_frame_generation=17,
            latest_waveform_generation=16,
            border_width_px=3.5,
        )

        assert overlay._vis_mode == "devcurve"
        assert overlay._last_reset_mode == "devcurve"
        assert overlay._last_reset_reason == "manual_reset"
        assert overlay._pending_mode_resets == set()
        assert overlay._waveform == []
        assert overlay._prev_waveform == []
        assert overlay._bubble_count == 0
        assert overlay._activation_id == 11
        assert overlay._engine_generation == 17
        assert overlay._latest_frame_generation == 17
        assert overlay._latest_waveform_generation == 16
        assert overlay._border_width_px == pytest.approx(3.5)


# ===========================================================================
# 6. Creator kwargs pass per-mode ghost settings
# ===========================================================================

class TestCreatorGhostKwargs:
    """spotify_widget_creators must pass all per-mode ghost settings."""

    GHOST_KWARGS = [
        "spectrum_ghosting_enabled", "spectrum_ghost_alpha", "spectrum_ghost_decay",
        "blob_ghosting_enabled", "blob_ghost_alpha", "blob_ghost_decay",
        "sine_ghosting_enabled", "sine_ghost_alpha", "sine_ghost_decay",
        "sine_ghost_line2_enabled", "sine_ghost_line3_enabled",
        "bubble_ghosting_enabled", "bubble_ghost_alpha", "bubble_ghost_decay",
        "osc_ghosting_enabled", "osc_ghost_intensity", "osc_ghost_line2_enabled", "osc_ghost_line3_enabled",
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
        from core.settings.visualizer_presets import get_custom_preset_index
        P = "widgets.spotify_visualizer"

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "spectrum",
            f"{P}.preset_spectrum": get_custom_preset_index("spectrum"),
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
        from core.settings.visualizer_presets import get_custom_preset_index
        P = "widgets.spotify_visualizer"

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "sine_wave",
            f"{P}.preset_sine_wave": get_custom_preset_index("sine_wave"),
            f"{P}.sine_ghosting_enabled": False,
            f"{P}.sine_ghost_alpha": 0.9,
            f"{P}.sine_ghost_decay": 0.7,
        })
        assert model.sine_ghosting_enabled is False
        assert abs(model.sine_ghost_alpha - 0.9) < 1e-6

    def test_bubble_ghost_round_trip(self):
        from core.settings.models import SpotifyVisualizerSettings
        from core.settings.visualizer_presets import get_custom_preset_index
        P = "widgets.spotify_visualizer"

        model = SpotifyVisualizerSettings.from_mapping({
            "mode": "bubble",
            f"{P}.preset_bubble": get_custom_preset_index("bubble"),
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

    def test_bubble_specular_growth_does_not_double_count_render_growth(self):
        """Specular size must stay bounded relative to the rendered bubble radius."""
        from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
        import random

        random.seed(10123)
        sim = BubbleSimulation()
        settings = {
            "bubble_big_count": 6,
            "bubble_small_count": 18,
            "bubble_surface_reach": 0.75,
            "bubble_stream_direction": "up",
            "bubble_stream_constant_speed": 0.15,
            "bubble_stream_speed_cap": 1.8,
            "bubble_stream_reactivity": 0.9,
            "bubble_rotation_amount": 0.15,
            "bubble_drift_amount": 0.5,
            "bubble_drift_speed": 0.3,
            "bubble_drift_frequency": 0.5,
            "bubble_drift_direction": "swish_horizontal",
            "bubble_big_size_max": 0.035,
            "bubble_small_size_max": 0.012,
            "bubble_trail_strength": 0.8,
            "bubble_big_bass_pulse": 0.8,
            "bubble_small_freq_pulse": 0.6,
            "bubble_big_contraction_bias": 0.5,
            "bubble_big_size_clamp": 3.0,
        }

        quiet = {"bass": 0.15, "mid": 0.10, "high": 0.05, "overall": 0.15, "smooth_mid": 0.10, "smooth_high": 0.05}
        hot = {"bass": 1.55, "mid": 0.65, "high": 0.16, "overall": 1.55, "smooth_mid": 0.65, "smooth_high": 0.16}

        for _ in range(80):
            sim.tick(1 / 60, quiet, settings)
        for _ in range(24):
            sim.tick(1 / 60, hot, settings)

        pos, extra, _trail = sim.snapshot(
            bass=1.55,
            mid_high=0.81,
            big_bass_pulse=settings["bubble_big_bass_pulse"],
            small_freq_pulse=settings["bubble_small_freq_pulse"],
            big_specular_max_size=2.5,
            big_contraction_bias=settings["bubble_big_contraction_bias"],
            big_size_clamp=settings["bubble_big_size_clamp"],
        )

        ratios = []
        for idx, bubble in enumerate(sim._bubbles):
            if getattr(bubble, "exiting", False):
                continue
            render_radius = pos[idx * 4 + 2]
            spec_factor = extra[idx * 4]
            if render_radius <= 1e-6:
                continue
            ratios.append(0.18 * spec_factor)

        assert ratios, "Need live Bubble specular ratios for the highlight-size regression guard."
        assert max(ratios) <= 0.24, (
            f"Bubble specular highlight ratio still balloons too far beyond the rendered bubble size (max {max(ratios):.3f})."
        )

    def test_bubble_big_specular_scales_modestly_with_larger_big_bubbles(self):
        """Very large big bubbles should earn a slightly larger highlight than medium big bubbles."""
        from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation

        sim = BubbleSimulation()
        settings = {
            "bubble_big_count": 2,
            "bubble_small_count": 0,
            "bubble_surface_reach": 0.75,
            "bubble_stream_direction": "up",
            "bubble_stream_constant_speed": 0.15,
            "bubble_stream_speed_cap": 1.8,
            "bubble_stream_reactivity": 0.9,
            "bubble_rotation_amount": 0.15,
            "bubble_drift_amount": 0.5,
            "bubble_drift_speed": 0.3,
            "bubble_drift_frequency": 0.5,
            "bubble_drift_direction": "swish_horizontal",
            "bubble_big_size_max": 0.035,
            "bubble_small_size_max": 0.012,
            "bubble_trail_strength": 0.0,
        }

        quiet = {"bass": 0.15, "mid": 0.10, "high": 0.05, "overall": 0.15, "smooth_mid": 0.10, "smooth_high": 0.05}
        for _ in range(24):
            sim.tick(1 / 60, quiet, settings)

        bigs = [b for b in sim._bubbles if b.is_big and not getattr(b, "exiting", False)]
        assert len(bigs) >= 2, "Need two active big bubbles for Bubble specular proportionality coverage."
        bigs[0].radius = 0.024
        bigs[1].radius = 0.040
        bigs[0].pulse_energy = 1.0
        bigs[1].pulse_energy = 1.0
        bigs[0].spec_size_mut = 1.0
        bigs[1].spec_size_mut = 1.0
        bigs[0].size_gate_energy = 1.0
        bigs[1].size_gate_energy = 1.0

        pos, extra, _trail = sim.snapshot(
            bass=1.25,
            mid_high=0.50,
            big_bass_pulse=1.0,
            small_freq_pulse=0.5,
            big_specular_max_size=2.5,
        )

        large_idx = sim._bubbles.index(bigs[1])
        medium_idx = sim._bubbles.index(bigs[0])
        large_spec_r = pos[large_idx * 4 + 2] * 0.18 * extra[large_idx * 4]
        medium_spec_r = pos[medium_idx * 4 + 2] * 0.18 * extra[medium_idx * 4]
        assert large_spec_r >= medium_spec_r * 1.18, (
            "Largest Bubble highlights still are not separating enough from medium big bubbles."
        )

    def test_spectrum_ghost_ui_save_includes_mode_specific_keys(self):
        """The UI save dict must include spectrum_ghosting_enabled/alpha/decay
        alongside legacy global keys so from_mapping picks them up."""
        from core.settings.models import SpotifyVisualizerSettings
        from core.settings import visualizer_presets as vp

        # Simulate what the save path produces
        save_dict = {
            "mode": "spectrum",
            "preset_spectrum": vp.get_custom_preset_index("spectrum"),
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
        from core.settings import visualizer_presets as vp

        save_dict = {
            "mode": "sine_wave",
            "preset_sine_wave": vp.get_custom_preset_index("sine_wave"),
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
        from core.settings import visualizer_presets as vp

        save_dict = {
            "mode": "bubble",
            "preset_bubble": vp.get_custom_preset_index("bubble"),
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
        from core.settings import visualizer_presets as vp

        save_dict = {
            "mode": "spectrum",
            "preset_spectrum": vp.get_custom_preset_index("spectrum"),
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
        w._agc_strength = 0.5
        w._env_bass_short = 1.3
        w._env_bass_long = 1.2
        w._env_mix_short = 1.2
        w._env_mix_long = 1.1
        w._pre_agc_bass = 1.3
        w._pre_agc_mid = 1.1
        w._pre_agc_treble = 1.0

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
        w._agc_strength = 0.5
        w._env_bass_short = 0.7
        w._env_bass_long = 0.7
        w._env_mix_short = 0.7
        w._env_mix_long = 0.7
        w._pre_agc_bass = 0.7
        w._pre_agc_mid = 0.7
        w._pre_agc_treble = 0.7

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
        w._agc_strength = 0.5
        w._env_bass_short = 0.1
        w._env_bass_long = 0.7
        w._env_mix_short = 0.1
        w._env_mix_long = 0.7
        w._pre_agc_bass = 0.05
        w._pre_agc_mid = 0.04
        w._pre_agc_treble = 0.03

        arr = np.array([0.15, 0.10, 0.08, 0.05], dtype="float32")
        before_sum = float(arr.sum())
        _apply_adaptive_normalization(w, arr, 0.0, False, np)
        after_sum = float(arr.sum())
        # Should have been gently boosted
        assert after_sum > before_sum, "Recovery did not boost quiet-after-loud signal"

    def test_notch_positions_round_trip(self):
        """spectrum_notch_positions_mirrored/linear must survive from_mapping → to_dict."""
        from core.settings.models import SpotifyVisualizerSettings
        from core.settings import visualizer_presets as vp

        custom_mir = [[0.0, "Mid"], [0.40, "Vocal"], [0.70, "Low-Mid"], [1.0, "Bass"]]
        custom_lin = [[0.0, "Bass"], [0.20, "Low-Mid"], [0.55, "Vocal"], [0.80, "Hi-Mid"], [1.0, "Treble"]]
        save_dict = {
            "mode": "spectrum",
            "preset_spectrum": vp.get_custom_preset_index("spectrum"),
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
