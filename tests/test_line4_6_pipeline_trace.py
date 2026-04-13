"""Trace lines 4-6 color values through settings → widget → overlay → renderer pipeline.

This test identifies where the disconnect occurs when lines 4-6 show as black
despite the code stack appearing correct.
"""
import inspect

import pytest
from PySide6.QtGui import QColor

# Test will verify pipeline stages:
# 1. Settings → widget (config_applier)
# 2. Widget → GPU kwargs (build_gpu_push_extra_kwargs)
# 3. GPU kwargs → overlay (set_state param acceptance)
# 4. Overlay → renderer (upload_mode_uniforms)


class TestLine4To6PipelineTrace:
    """Trace line 4-6 color propagation through the full visualizer pipeline."""

    def _create_test_color(self, r: int, g: int, b: int, a: int = 255) -> QColor:
        """Create a distinct test color."""
        return QColor(r, g, b, a)

    def _make_widget_with_line_colors(self, mode: str):
        """Create a widget with lines 4-6 set to specific test colors."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from widgets.spotify_visualizer.audio_worker import VisualizerMode

        widget = SpotifyVisualizerWidget(parent=None, bar_count=16)

        # Set visualization mode
        mode_map = {
            'sine_wave': VisualizerMode.SINE_WAVE,
            'oscilloscope': VisualizerMode.OSCILLOSCOPE,
        }
        if mode in mode_map:
            widget.set_visualization_mode(mode_map[mode])

        # Set distinct test colors for lines 4-6
        if mode == 'sine_wave':
            widget._sine_line4_color = self._create_test_color(100, 101, 102, 200)
            widget._sine_line4_glow_color = self._create_test_color(103, 104, 105, 180)
            widget._sine_line5_color = self._create_test_color(110, 111, 112, 200)
            widget._sine_line5_glow_color = self._create_test_color(113, 114, 115, 180)
            widget._sine_line6_color = self._create_test_color(120, 121, 122, 200)
            widget._sine_line6_glow_color = self._create_test_color(123, 124, 125, 180)
            # Also set line count to ensure lines 4-6 would render
            widget._sine_line_count = 6
        else:  # oscilloscope
            widget._osc_line4_color = self._create_test_color(100, 101, 102, 200)
            widget._osc_line4_glow_color = self._create_test_color(103, 104, 105, 180)
            widget._osc_line5_color = self._create_test_color(110, 111, 112, 200)
            widget._osc_line5_glow_color = self._create_test_color(113, 114, 115, 180)
            widget._osc_line6_color = self._create_test_color(120, 121, 122, 200)
            widget._osc_line6_glow_color = self._create_test_color(123, 124, 125, 180)
            widget._line_count = 6

        return widget

    @pytest.mark.qt
    def test_sine_line4_6_colors_reach_gpu_kwargs(self, qt_app):
        """Verify line 4-6 colors flow from widget to GPU extra kwargs for sine mode."""
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
        from widgets.spotify_visualizer.audio_worker import VisualizerMode

        widget = self._make_widget_with_line_colors('sine_wave')
        qt_app.processEvents()

        # Build GPU kwargs as the widget does during frame push
        class _StubEngine:
            def get_waveform(self):
                return [0.0] * 256
            def get_energy_bands(self):
                from widgets.spotify_visualizer.energy_bands import EnergyBands
                return EnergyBands(bass=0.11, mid=0.22, high=0.33, overall=0.44)
            def get_raw_energy_bands(self):
                from widgets.spotify_visualizer.energy_bands import EnergyBands
                return EnergyBands()
            def get_pre_agc_energy_bands(self):
                from widgets.spotify_visualizer.energy_bands import EnergyBands
                return EnergyBands(bass=0.71, mid=0.72, high=0.73, overall=0.74)
            def get_transient_energy_bands(self):
                from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
                return TransientEnergyBands()

        stub_engine = _StubEngine()
        widget.set_visualization_mode(VisualizerMode.SINE_WAVE)
        extras = build_gpu_push_extra_kwargs(widget, 'sine_wave', stub_engine)

        # Verify line 4-6 colors are present in GPU kwargs
        assert 'line4_color' in extras, "line4_color missing from GPU extras"
        assert 'line5_color' in extras, "line5_color missing from GPU extras"
        assert 'line6_color' in extras, "line6_color missing from GPU extras"

        # Verify the color values are correct (not black, not default)
        line4 = extras['line4_color']
        assert isinstance(line4, QColor), f"line4_color is not QColor, got {type(line4)}"
        assert (line4.red(), line4.green(), line4.blue()) == (100, 101, 102), \
            f"line4_color wrong RGB: got ({line4.red()}, {line4.green()}, {line4.blue()})"

        line5 = extras['line5_color']
        assert (line5.red(), line5.green(), line5.blue()) == (110, 111, 112), \
            f"line5_color wrong RGB: got ({line5.red()}, {line5.green()}, {line5.blue()})"

        line6 = extras['line6_color']
        assert (line6.red(), line6.green(), line6.blue()) == (120, 121, 122), \
            f"line6_color wrong RGB: got ({line6.red()}, {line6.green()}, {line6.blue()})"

        widget.deleteLater()

    @pytest.mark.qt
    def test_osc_line4_6_colors_reach_gpu_kwargs(self, qt_app):
        """Verify line 4-6 colors flow from widget to GPU extra kwargs for oscilloscope mode."""
        from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
        from widgets.spotify_visualizer.audio_worker import VisualizerMode

        widget = self._make_widget_with_line_colors('oscilloscope')
        qt_app.processEvents()

        class _StubEngine:
            def get_waveform(self):
                return [0.0] * 256
            def get_energy_bands(self):
                from widgets.spotify_visualizer.energy_bands import EnergyBands
                return EnergyBands(bass=0.11, mid=0.22, high=0.33, overall=0.44)
            def get_raw_energy_bands(self):
                from widgets.spotify_visualizer.energy_bands import EnergyBands
                return EnergyBands()
            def get_pre_agc_energy_bands(self):
                from widgets.spotify_visualizer.energy_bands import EnergyBands
                return EnergyBands(bass=0.71, mid=0.72, high=0.73, overall=0.74)
            def get_transient_energy_bands(self):
                from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
                return TransientEnergyBands()

        stub_engine = _StubEngine()
        widget.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)
        extras = build_gpu_push_extra_kwargs(widget, 'oscilloscope', stub_engine)

        # Verify line 4-6 colors are present
        assert 'line4_color' in extras, "line4_color missing from GPU extras"
        assert 'line5_color' in extras, "line5_color missing from GPU extras"
        assert 'line6_color' in extras, "line6_color missing from GPU extras"

        line4 = extras['line4_color']
        assert (line4.red(), line4.green(), line4.blue()) == (100, 101, 102), \
            f"line4_color wrong RGB: got ({line4.red()}, {line4.green()}, {line4.blue()})"

        widget.deleteLater()

    @pytest.mark.qt
    def test_line4_6_kwargs_accepted_by_overlay(self, qt_app):
        """Verify overlay.set_state accepts line 4-6 kwargs without error."""
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        overlay = SpotifyBarsGLOverlay()
        qt_app.processEvents()

        # Build test kwargs with line 4-6 colors
        test_kwargs = {
            'rect': None,  # Will be set by caller
            'bars': [0.5] * 16,
            'bar_count': 16,
            'segments': 8,
            'line_count': 6,
            'line4_color': self._create_test_color(100, 101, 102),
            'line4_glow_color': self._create_test_color(103, 104, 105, 180),
            'line5_color': self._create_test_color(110, 111, 112),
            'line5_glow_color': self._create_test_color(113, 114, 115, 180),
            'line6_color': self._create_test_color(120, 121, 122),
            'line6_glow_color': self._create_test_color(123, 124, 125, 180),
            'vis_mode': 'sine_wave',
        }

        # Verify these are valid parameters for set_state
        sig = inspect.signature(overlay.set_state)
        overlay_params = set(sig.parameters.keys())

        for key in ['line4_color', 'line4_glow_color', 'line5_color', 'line5_glow_color',
                    'line6_color', 'line6_glow_color']:
            assert key in overlay_params, f"{key} not in overlay.set_state parameters"

        # Suppress unused variable warning by validating test_kwargs contents
        assert 'line4_color' in test_kwargs
        overlay.deleteLater()

    @pytest.mark.qt
    def test_line4_6_colors_set_on_overlay(self, qt_app):
        """Verify line 4-6 colors are actually stored on overlay after set_state."""
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
        from PySide6.QtCore import QRect

        overlay = SpotifyBarsGLOverlay()
        qt_app.processEvents()

        # Call set_state with required params plus line 4-6 colors
        overlay.set_state(
            rect=QRect(0, 0, 100, 100),
            bars=[0.5] * 16,
            bar_count=16,
            segments=8,
            fill_color=self._create_test_color(255, 255, 255),
            border_color=self._create_test_color(0, 0, 0),
            fade=1.0,
            playing=True,
            visible=True,
            line4_color=self._create_test_color(100, 101, 102, 200),
            line4_glow_color=self._create_test_color(103, 104, 105, 180),
            line5_color=self._create_test_color(110, 111, 112, 200),
            line5_glow_color=self._create_test_color(113, 114, 115, 180),
            line6_color=self._create_test_color(120, 121, 122, 200),
            line6_glow_color=self._create_test_color(123, 124, 125, 180),
        )

        # Verify colors were stored
        assert overlay._line4_color is not None, "_line4_color is None"
        assert (overlay._line4_color.red(), overlay._line4_color.green(),
                overlay._line4_color.blue(), overlay._line4_color.alpha()) == \
               (100, 101, 102, 200), \
            f"_line4_color wrong: got ({overlay._line4_color.red()}, {overlay._line4_color.green()}, " \
            f"{overlay._line4_color.blue()}, {overlay._line4_color.alpha()})"

        assert (overlay._line5_color.red(), overlay._line5_color.green(),
                overlay._line5_color.blue()) == (110, 111, 112), \
            "_line5_color wrong RGB"

        assert (overlay._line6_color.red(), overlay._line6_color.green(),
                overlay._line6_color.blue()) == (120, 121, 122), \
            "_line6_color wrong RGB"

        overlay.deleteLater()

    def test_line4_6_color_format_conversion(self):
        """Verify QColor line 4-6 colors are properly converted for GL upload."""
        from widgets.spotify_visualizer.renderers.gl_helpers import set_color4

        # Mock GL and uniform location
        class MockGL:
            def __init__(self):
                self.calls = []
            def glUniform4f(self, loc, r, g, b, a):
                self.calls.append(('glUniform4f', loc, r, g, b, a))
            def glUniform1i(self, loc, val):
                self.calls.append(('glUniform1i', loc, val))

        mock_gl = MockGL()
        test_color = self._create_test_color(100, 101, 102, 200)

        # Test color conversion - should convert 0-255 to 0.0-1.0
        u = {'u_test_color': 5}  # Mock uniform location
        set_color4(mock_gl, u, 'u_test_color', test_color)

        # Verify the call was made with normalized values
        calls = [c for c in mock_gl.calls if c[0] == 'glUniform4f']
        assert len(calls) == 1, f"Expected 1 glUniform4f call, got {len(calls)}"

        _, loc, r, g, b, a = calls[0]
        # Check normalized values (100/255 ≈ 0.392, etc.)
        assert abs(r - 100/255.0) < 0.001, f"Red not normalized correctly: {r}"
        assert abs(g - 101/255.0) < 0.001, f"Green not normalized correctly: {g}"
        assert abs(b - 102/255.0) < 0.001, f"Blue not normalized correctly: {b}"
        assert abs(a - 200/255.0) < 0.001, f"Alpha not normalized correctly: {a}"


class TestLine4To6SettingsRoundTrip:
    """Test settings save/load round-trip for line 4-6 colors."""

    def test_sine_line4_6_settings_roundtrip(self, qt_app):
        """Verify line 4-6 colors survive settings save/load cycle."""
        from ui.tabs.media.sine_wave_settings_binding import collect_sine_wave_mode_settings

        # Create a mock tab with line 4-6 color attributes (as set by color buttons)
        class MockTab:
            def __init__(self):
                # These attributes are set by the color button callbacks
                self._sine_line4_color = QColor(100, 101, 102)
                self._sine_line4_glow_color = QColor(103, 104, 105)
                self._sine_line5_color = QColor(110, 111, 112)
                self._sine_line5_glow_color = QColor(113, 114, 115)
                self._sine_line6_color = QColor(120, 121, 122)
                self._sine_line6_glow_color = QColor(123, 124, 125)

        tab = MockTab()
        config = {}

        # Apply settings (as would happen on save)
        config.update(collect_sine_wave_mode_settings(tab))

        # Verify line 4-6 colors were captured in config
        assert 'sine_line4_color' in config, "sine_line4_color missing from config"
        assert 'sine_line5_color' in config, "sine_line5_color missing from config"
        assert 'sine_line6_color' in config, "sine_line6_color missing from config"

        # Verify values (config stores as list, e.g., [100, 101, 102, 255])
        assert config['sine_line4_color'][:3] == [100, 101, 102], \
            f"Wrong sine_line4_color in config: {config['sine_line4_color']}"


    @pytest.mark.qt
    def test_full_pipeline_sine_line4_6_to_uniforms(self, qt_app, monkeypatch):
        """Full pipeline test: verify line 4-6 colors reach GL uniform upload stage."""
        from widgets.spotify_visualizer.renderers import upload_mode_uniforms
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        # Create overlay with specific test colors
        overlay = SpotifyBarsGLOverlay()
        overlay._vis_mode = 'sine_wave'
        overlay._line_count = 6
        overlay._line_color = QColor(255, 255, 255, 255)
        overlay._line2_color = QColor(255, 120, 50, 230)
        overlay._line3_color = QColor(50, 255, 120, 230)
        overlay._line4_color = QColor(100, 101, 102, 200)  # Test color
        overlay._line5_color = QColor(110, 111, 112, 200)
        overlay._line6_color = QColor(120, 121, 122, 200)
        overlay._line2_glow_color = QColor(255, 120, 50, 180)
        overlay._line3_glow_color = QColor(50, 255, 120, 180)
        overlay._line4_glow_color = QColor(103, 104, 105, 180)
        overlay._line5_glow_color = QColor(113, 114, 115, 180)
        overlay._line6_glow_color = QColor(123, 124, 125, 180)
        overlay._line_smoothing = 0.7
        overlay._line_sensitivity = 3.0
        overlay._glow_color = QColor(0, 200, 255, 230)
        overlay._glow_intensity = 0.5
        overlay._glow_size = 1.0
        overlay._glow_reactivity = 1.0
        overlay._reactive_glow = True
        overlay._sine_ghost_alpha = 0.0
        overlay._sine_speed = 1.0
        overlay._sine_card_adaptation = 0.3
        overlay._sine_line_offset_bias = 0.0
        overlay._sine_travel = 0
        overlay._sine_travel_line2 = 0
        overlay._sine_travel_line3 = 0
        overlay._sine_travel_line4 = 0
        overlay._sine_travel_line5 = 0
        overlay._sine_travel_line6 = 0
        overlay._sine_wave_effect = 0.0
        overlay._sine_micro_wobble = 0.0
        overlay._sine_crawl_amount = 0.0
        overlay._sine_vertical_shift = 0
        overlay._sine_heartbeat = 0.0
        overlay._heartbeat_intensity = 0.0
        overlay._sine_width_reaction = 0.0
        overlay._sine_density = 1.0
        overlay._sine_displacement = 0.0
        overlay._sine_line1_shift = 0.0
        overlay._sine_line2_shift = 0.0
        overlay._sine_line3_shift = 0.0
        overlay._sine_line4_shift = 0.0
        overlay._sine_line5_shift = 0.0
        overlay._sine_line6_shift = 0.0

        # Mock GL to capture uniform uploads
        uploaded_uniforms = {}

        class MockGL:
            def glUniform1f(self, loc, val):
                if loc >= 0:
                    uploaded_uniforms[loc] = ('float', val)
            def glUniform1i(self, loc, val):
                if loc >= 0:
                    uploaded_uniforms[loc] = ('int', val)
            def glUniform4f(self, loc, r, g, b, a):
                if loc >= 0:
                    uploaded_uniforms[loc] = ('vec4', (r, g, b, a))

        mock_gl = MockGL()

        # Create uniform location map for sine_wave
        u = {
            'u_resolution': 1,
            'u_dpr': 2,
            'u_time': 3,
            'u_fade': 4,
            'u_line_color': 10,
            'u_line_count': 11,
            'u_line2_color': 12,
            'u_line2_glow_color': 13,
            'u_line3_color': 14,
            'u_line3_glow_color': 15,
            'u_line4_color': 16,
            'u_line4_glow_color': 17,
            'u_line5_color': 18,
            'u_line5_glow_color': 19,
            'u_line6_color': 20,
            'u_line6_glow_color': 21,
            'u_glow_color': 22,
            'u_glow_intensity': 23,
            'u_sensitivity': 24,
            'u_smoothing': 25,
        }

        # Call the upload function
        upload_mode_uniforms('sine_wave', mock_gl, u, overlay)

        # Verify line 4-6 uniforms were uploaded
        assert 16 in uploaded_uniforms, "u_line4_color uniform not uploaded (loc 16)"
        assert 18 in uploaded_uniforms, "u_line5_color uniform not uploaded (loc 18)"
        assert 20 in uploaded_uniforms, "u_line6_color uniform not uploaded (loc 20)"

        # Verify the color values (normalized to 0-1 range)
        line4_uploaded = uploaded_uniforms[16]
        assert line4_uploaded[0] == 'vec4'
        r, g, b, a = line4_uploaded[1]
        assert abs(r - 100/255.0) < 0.001, f"Line4 red wrong: {r}"
        assert abs(g - 101/255.0) < 0.001, f"Line4 green wrong: {g}"
        assert abs(b - 102/255.0) < 0.001, f"Line4 blue wrong: {b}"

        overlay.deleteLater()

    def test_apply_vis_mode_kwargs_sets_line4_6(self):
        """Verify apply_vis_mode_kwargs actually sets line 4-6 colors on widget."""
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        # Create a minimal mock widget
        class MockWidget:
            def __init__(self):
                self._sine_line4_color = None
                self._sine_line4_glow_color = None
                self._sine_line5_color = None
                self._sine_line5_glow_color = None
                self._sine_line6_color = None
                self._sine_line6_glow_color = None
                self.vis_mode = 'sine_wave'

        widget = MockWidget()

        # Apply kwargs with line 4-6 colors (as lists, which is the correct format)
        kwargs = {
            'sine_line4_color': [100, 101, 102, 200],
            'sine_line4_glow_color': [103, 104, 105, 180],
            'sine_line5_color': [110, 111, 112, 200],
            'sine_line5_glow_color': [113, 114, 115, 180],
            'sine_line6_color': [120, 121, 122, 200],
            'sine_line6_glow_color': [123, 124, 125, 180],
        }

        apply_vis_mode_kwargs(widget, kwargs)

        # Verify colors were set
        assert widget._sine_line4_color is not None, "_sine_line4_color not set"
        assert isinstance(widget._sine_line4_color, QColor), "_sine_line4_color not QColor"
        assert widget._sine_line4_color.red() == 100, f"Wrong red: {widget._sine_line4_color.red()}"

        assert widget._sine_line5_color is not None, "_sine_line5_color not set"
        assert widget._sine_line6_color is not None, "_sine_line6_color not set"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
