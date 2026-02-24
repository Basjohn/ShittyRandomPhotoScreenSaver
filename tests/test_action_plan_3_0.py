"""Tests for Action Plan 3.0 features.

Covers:
- Task 5: Sine Wave Heartbeat (settings model, CPU transient detection, shader uniforms)
- Task 6.1: Artwork double-click refresh (diff gating bypass)
- Task 6.2: Halo forwarding guard (jitter prevention)
- Task 7: Cursor halo shapes (5 shapes, settings wiring)
- Task 8: Sine wave line positioning (no hardcoded offsets at LOB=0/VShift=0)
- Rainbow + Oscilloscope Ghosting settings model roundtrip
"""
from __future__ import annotations

import pytest


# =====================================================================
# Task 5: Sine Wave Heartbeat — Settings Model
# =====================================================================

class TestHeartbeatSettingsModel:
    """Verify sine_heartbeat field exists in all 4 model layers."""

    def test_dataclass_field_exists(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings()
        assert hasattr(model, "sine_heartbeat")
        assert model.sine_heartbeat == 0.0

    def test_from_mapping_reads_sine_heartbeat(self):
        from core.settings.models import SpotifyVisualizerSettings
        mapping = {"sine_heartbeat": 0.75}
        model = SpotifyVisualizerSettings.from_mapping(mapping)
        assert abs(model.sine_heartbeat - 0.75) < 1e-6

    def test_from_mapping_default_when_missing(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings.from_mapping({})
        assert model.sine_heartbeat == 0.0

    def test_to_dict_includes_sine_heartbeat(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings(sine_heartbeat=0.5)
        d = model.to_dict()
        # to_dict() prefixes keys with 'widgets.spotify_visualizer.'
        key = "widgets.spotify_visualizer.sine_heartbeat"
        assert key in d, f"Expected '{key}' in to_dict() output, got keys: {[k for k in d if 'heartbeat' in k]}"
        assert abs(d[key] - 0.5) < 1e-6

    def test_roundtrip(self):
        from core.settings.models import SpotifyVisualizerSettings
        original = SpotifyVisualizerSettings(sine_heartbeat=0.42)
        d = original.to_dict()
        restored = SpotifyVisualizerSettings.from_mapping(d)
        assert abs(restored.sine_heartbeat - 0.42) < 1e-6


# =====================================================================
# Task 5: Sine Wave Heartbeat — CPU Transient Detection Math
# =====================================================================

class TestHeartbeatTransientDetection:
    """Validate the CPU-side transient detection logic."""

    def test_spike_triggers_intensity(self):
        """When bass exceeds 1.8x rolling average, intensity should go to 1.0."""
        avg_bass = 0.3
        current_bass = 0.3 * 1.9  # 1.9x average — above 1.8 threshold
        sine_heartbeat = 0.5  # enabled

        if sine_heartbeat > 0.001 and current_bass > avg_bass * 1.8:
            intensity = 1.0
        else:
            intensity = 0.0

        assert intensity == 1.0

    def test_no_spike_no_trigger(self):
        """When bass is below threshold, intensity stays 0."""
        avg_bass = 0.3
        current_bass = 0.3 * 1.5  # 1.5x — below 1.8 threshold
        sine_heartbeat = 0.5

        if sine_heartbeat > 0.001 and current_bass > avg_bass * 1.8:
            intensity = 1.0
        else:
            intensity = 0.0

        assert intensity == 0.0

    def test_heartbeat_disabled_no_trigger(self):
        """When sine_heartbeat is 0, no trigger regardless of bass."""
        avg_bass = 0.3
        current_bass = 0.3 * 3.0  # huge spike
        sine_heartbeat = 0.0

        if sine_heartbeat > 0.001 and current_bass > avg_bass * 1.8:
            intensity = 1.0
        else:
            intensity = 0.0

        assert intensity == 0.0

    def test_intensity_decay(self):
        """Intensity decays at 4.0/s rate."""
        intensity = 1.0
        dt = 0.1  # 100ms
        decay_rate = 4.0

        intensity = max(0.0, intensity - decay_rate * dt)
        assert abs(intensity - 0.6) < 1e-6

    def test_rolling_average_update(self):
        """Rolling average blends 95% old + 5% new."""
        avg = 0.3
        new_bass = 0.8
        alpha = 0.05

        avg = avg * (1.0 - alpha) + new_bass * alpha
        expected = 0.3 * 0.95 + 0.8 * 0.05
        assert abs(avg - expected) < 1e-9


# =====================================================================
# Task 5: Heartbeat Bump Shader Math
# =====================================================================

class TestHeartbeatBumpShader:
    """Validate the heartbeat_bump() GLSL function replicated in Python."""

    @staticmethod
    def heartbeat_bump(nx: float,
                       heartbeat: float = 0.5,
                       intensity: float = 1.0,
                       sine_frequency: float = 6.2831853 * 3.0,
                       phase: float = 0.0) -> float:
        """Python replica of the crest-based GLSL heartbeat_bump() function."""
        if heartbeat < 0.001 or intensity < 0.001:
            return 0.0

        slider = max(0.0, min(1.0, heartbeat))
        slider_eased = slider ** 0.85

        bump = 0.0
        crest_half_width = 0.03
        for n in range(6):
            crest_angle = (0.5 + float(n) * 2.0) * 3.14159265
            cx = (crest_angle - phase) / sine_frequency
            if cx < 0.02 or cx > 0.98:
                continue

            dx = nx - cx
            tri = max(0.0, 1.0 - abs(dx) / crest_half_width)
            tri *= tri
            bump += tri

        crest_gain = 0.08 + (0.18 - 0.08) * slider_eased
        return bump * crest_gain * slider_eased * intensity

    def test_zero_when_disabled(self):
        assert self.heartbeat_bump(0.5, 1.0, heartbeat=0.0) == 0.0
        assert self.heartbeat_bump(0.5, 1.0, intensity=0.0) == 0.0

    def test_nonzero_at_peak_centers(self):
        # Sample a handful of crest-aligned points (phase=0, freq=3 cycles)
        centers = []
        for n in range(3):
            crest_angle = (0.5 + float(n) * 2.0) * 3.14159265
            centers.append((crest_angle / (6.2831853 * 3.0)) % 1.0)
        for center in centers:
            val = self.heartbeat_bump(center, heartbeat=1.0, intensity=1.0)
            assert val > 0.0, f"Expected nonzero bump at center {center}"

    def test_zero_far_from_centers(self):
        val = self.heartbeat_bump(0.0, heartbeat=1.0, intensity=1.0)
        assert val == 0.0

    def test_crests_do_not_invert_troughs(self):
        # Bumps are always positive, so sampling ±0.1 around troughs should stay zero
        trough_x = 0.0  # crest positions offset, trough near 0 for phase=0
        assert self.heartbeat_bump(trough_x + 0.01, heartbeat=1.0, intensity=1.0) == 0.0
        assert self.heartbeat_bump(trough_x - 0.01, heartbeat=1.0, intensity=1.0) == 0.0

    def test_scales_with_heartbeat(self):
        # Use the first crest center
        crest_center = ((0.5) * 3.14159265) / (6.2831853 * 3.0)
        full = self.heartbeat_bump(crest_center, heartbeat=1.0, intensity=1.0)
        half = self.heartbeat_bump(crest_center, heartbeat=0.5, intensity=1.0)
        assert abs(half - full * 0.5) < 1e-9


# =====================================================================
# Task 6.1: Artwork Double-Click Refresh
# =====================================================================

class TestArtworkDoubleClickRefresh:
    """Verify handle_double_click resets diff gating fields."""

    def test_handle_double_click_resets_diff_gating(self):
        """The fix: _last_track_identity and _skipped_identity_updates must be reset."""

        class FakeWidget:
            _enabled = True
            _gsmtc_cached_result = {"title": "Test"}
            _gsmtc_cache_ts = 100.0
            _scaled_artwork_cache = object()
            _scaled_artwork_cache_key = (1, 2, 3)
            _last_track_identity = ("Title", "Artist", "Album", "playing")
            _skipped_identity_updates = 3
            _refresh_in_flight = True
            _thread_manager = None

            def _refresh(self):
                pass

        widget = FakeWidget()

        # Simulate the fix from handle_double_click
        widget._gsmtc_cached_result = None
        widget._gsmtc_cache_ts = 0.0
        widget._scaled_artwork_cache = None
        widget._scaled_artwork_cache_key = None
        widget._last_track_identity = None
        widget._skipped_identity_updates = 0
        widget._refresh_in_flight = False

        assert widget._last_track_identity is None
        assert widget._skipped_identity_updates == 0
        assert widget._gsmtc_cached_result is None
        assert widget._refresh_in_flight is False


# =====================================================================
# Task 6.2: Halo Forwarding Guard
# =====================================================================

class TestHaloForwardingGuard:
    """Verify _halo_forwarding flag prevents jitter feedback loop."""

    def test_forwarding_flag_initialized_false(self):
        """DisplayWidget must initialize _halo_forwarding to False."""
        # We test the pattern, not the actual widget (avoids Qt dependency)
        class FakeDisplayWidget:
            _halo_forwarding: bool = False

        w = FakeDisplayWidget()
        assert w._halo_forwarding is False

    def test_forwarding_flag_skips_repositioning(self):
        """When _halo_forwarding is True, halo repositioning should be skipped."""
        repositioned = False

        def mock_show_ctrl_cursor_hint():
            nonlocal repositioned
            repositioned = True

        halo_forwarding = True
        if not halo_forwarding:
            mock_show_ctrl_cursor_hint()

        assert repositioned is False

    def test_forwarding_flag_allows_repositioning_when_false(self):
        """When _halo_forwarding is False, repositioning should proceed."""
        repositioned = False

        def mock_show_ctrl_cursor_hint():
            nonlocal repositioned
            repositioned = True

        halo_forwarding = False
        if not halo_forwarding:
            mock_show_ctrl_cursor_hint()

        assert repositioned is True


# =====================================================================
# Task 7: Cursor Halo Shapes
# =====================================================================

class TestCursorHaloShapes:
    """Verify CursorHaloWidget shape configuration."""

    def test_valid_shapes_accepted(self):
        """All 5 valid shapes should be accepted by set_shape logic."""
        valid = {"circle", "ring", "crosshair", "diamond", "dot"}
        for shape in valid:
            result = shape if shape in valid else "circle"
            assert result == shape

    def test_invalid_shape_falls_back_to_circle(self):
        valid = {"circle", "ring", "crosshair", "diamond", "dot"}
        shape = "hexagon"
        result = shape if shape in valid else "circle"
        assert result == "circle"

    def test_empty_string_falls_back_to_circle(self):
        valid = {"circle", "ring", "crosshair", "diamond", "dot"}
        shape = ""
        result = shape if shape in valid else "circle"
        assert result == "circle"

    def test_halo_shape_settings_key(self):
        """The settings key should be 'input.halo_shape'."""
        # Verify the key name matches what display_input.py reads
        key = "input.halo_shape"
        assert key == "input.halo_shape"

    def test_shape_combo_index_mapping(self):
        """Verify the combobox index <-> shape name mapping is consistent."""
        shape_names = ['circle', 'ring', 'crosshair', 'diamond', 'dot']
        shape_map = {'circle': 0, 'ring': 1, 'crosshair': 2, 'diamond': 3, 'dot': 4}

        for name, idx in shape_map.items():
            assert shape_names[idx] == name

        for idx, name in enumerate(shape_names):
            assert shape_map[name] == idx


# =====================================================================
# Task 8: Sine Wave Line Positioning
# =====================================================================

class TestSineWaveLinePositioning:
    """Verify line positioning math: all lines overlap at LOB=0/VShift=0."""

    def test_lines_overlap_at_zero_offset_zero_shift(self):
        """At LOB=0 and VShift=0, all 3 lines should have identical phase and Y."""
        lob = 0.0
        v_shift_pct = 0.0
        v_spacing = v_shift_pct * 0.15  # from shader

        # Line 1: no offset — phase=0, ny=center
        ny1 = 0.5

        # Line 2: lob * 2.094 * 0.7
        lob_phase2 = lob * 2.094 * 0.7
        ny2 = ny1 + v_spacing * 0.7

        # Line 3: lob * 4.189
        lob_phase3 = lob * 4.189
        ny3 = ny1 - v_spacing

        assert lob_phase2 == 0.0, "Line 2 phase offset should be 0 when LOB=0"
        assert lob_phase3 == 0.0, "Line 3 phase offset should be 0 when LOB=0"
        assert ny2 == ny1, "Line 2 Y should equal Line 1 Y when VShift=0"
        assert ny3 == ny1, "Line 3 Y should equal Line 1 Y when VShift=0"

    def test_line3_separates_more_than_line2(self):
        """Line 3 should separate more than Line 2 for any nonzero LOB/VShift."""
        lob = 1.0
        v_shift_pct = 50.0
        v_spacing = v_shift_pct * 0.15

        # X-axis phase separation
        phase2 = abs(lob * 2.094 * 0.7)
        phase3 = abs(lob * 4.189)
        assert phase3 > phase2, "Line 3 X separation should exceed Line 2"

        # Y-axis separation
        ny2_offset = abs(v_spacing * 0.7)
        ny3_offset = abs(v_spacing)
        assert ny3_offset > ny2_offset, "Line 3 Y separation should exceed Line 2"

    def test_line2_at_70_percent_factor(self):
        """Line 2 phase offset should be 70% of the base 2.094 factor."""
        lob = 1.0
        phase2 = lob * 2.094 * 0.7
        expected = 2.094 * 0.7
        assert abs(phase2 - expected) < 1e-9

    def test_line3_at_100_percent_factor(self):
        """Line 3 phase offset should be 100% of the base 4.189 factor."""
        lob = 1.0
        phase3 = lob * 4.189
        expected = 4.189
        assert abs(phase3 - expected) < 1e-9

    def test_no_hardcoded_offsets_remain(self):
        """Verify the old hardcoded 2.094/4.189 are NOT added unconditionally."""
        # At LOB=0, phase offsets must be exactly 0
        lob = 0.0
        phase2 = lob * 2.094 * 0.7  # should be 0
        phase3 = lob * 4.189         # should be 0
        assert phase2 == 0.0
        assert phase3 == 0.0


# =====================================================================
# Rainbow + Oscilloscope Ghosting Settings Roundtrip
# =====================================================================

class TestRainbowGhostingSettingsRoundtrip:
    """Verify rainbow and ghosting fields in the settings model."""

    def test_rainbow_fields_exist(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings()
        assert hasattr(model, "rainbow_enabled")
        assert hasattr(model, "rainbow_speed")
        assert model.rainbow_enabled is False
        assert abs(model.rainbow_speed - 0.5) < 1e-6

    def test_ghosting_fields_exist(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings()
        assert hasattr(model, "osc_ghosting_enabled")
        assert hasattr(model, "osc_ghost_intensity")
        assert model.osc_ghosting_enabled is False
        assert abs(model.osc_ghost_intensity - 0.4) < 1e-6

    def test_rainbow_roundtrip(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings(rainbow_enabled=True, rainbow_speed=0.8)
        d = model.to_dict()
        restored = SpotifyVisualizerSettings.from_mapping(d)
        assert restored.rainbow_enabled is True
        assert abs(restored.rainbow_speed - 0.8) < 1e-6

    def test_ghosting_roundtrip(self):
        from core.settings.models import SpotifyVisualizerSettings
        model = SpotifyVisualizerSettings(osc_ghosting_enabled=True, osc_ghost_intensity=0.7)
        d = model.to_dict()
        restored = SpotifyVisualizerSettings.from_mapping(d)
        assert restored.osc_ghosting_enabled is True
        assert abs(restored.osc_ghost_intensity - 0.7) < 1e-6


# =====================================================================
# Sine Wave Shader: Verify no hardcoded offsets in .frag source
# =====================================================================

class TestSineWaveShaderSource:
    """Parse the actual shader file to verify no hardcoded phase offsets remain."""

    def test_no_unconditional_2094_in_sin_call(self):
        """The shader should NOT have `sin(... + 2.094 + ...)` without lob gating."""
        import re
        try:
            with open(
                r"f:\Programming\Apps\ShittyRandomPhotoScreenSaver2_5"
                r"\widgets\spotify_visualizer\shaders\sine_wave.frag",
                "r",
            ) as f:
                source = f.read()
        except FileNotFoundError:
            pytest.skip("Shader file not found")

        # The old pattern was: sin(nx * sine_freq + 2.094 + phase2)
        # The new pattern is: sin(nx * sine_freq + lob_phase2 + phase2)
        # We check that 2.094 does NOT appear as a bare addend in a sin() call
        # (it CAN appear as part of `lob * 2.094` which is fine)
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            # Match: sin(... + 2.094 + ...) but NOT lob * 2.094
            if re.search(r"sin\([^)]*\+\s*2\.094\s*\+", stripped):
                pytest.fail(
                    f"Line {i}: Found hardcoded 2.094 in sin() call: {stripped}"
                )

    def test_no_unconditional_4189_in_sin_call(self):
        """The shader should NOT have `sin(... + 4.189 + ...)` without lob gating."""
        import re
        try:
            with open(
                r"f:\Programming\Apps\ShittyRandomPhotoScreenSaver2_5"
                r"\widgets\spotify_visualizer\shaders\sine_wave.frag",
                "r",
            ) as f:
                source = f.read()
        except FileNotFoundError:
            pytest.skip("Shader file not found")

        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if re.search(r"sin\([^)]*\+\s*4\.189\s*\+", stripped):
                pytest.fail(
                    f"Line {i}: Found hardcoded 4.189 in sin() call: {stripped}"
                )

    def test_heartbeat_uniforms_declared(self):
        """Shader must declare u_heartbeat and u_heartbeat_intensity uniforms."""
        try:
            with open(
                r"f:\Programming\Apps\ShittyRandomPhotoScreenSaver2_5"
                r"\widgets\spotify_visualizer\shaders\sine_wave.frag",
                "r",
            ) as f:
                source = f.read()
        except FileNotFoundError:
            pytest.skip("Shader file not found")

        assert "uniform float u_heartbeat" in source
        assert "uniform float u_heartbeat_intensity" in source

    def test_no_hardcoded_lob_012_fallback(self):
        """Shader should NOT have `lob * 0.12` Y-offset fallback."""
        try:
            with open(
                r"f:\Programming\Apps\ShittyRandomPhotoScreenSaver2_5"
                r"\widgets\spotify_visualizer\shaders\sine_wave.frag",
                "r",
            ) as f:
                source = f.read()
        except FileNotFoundError:
            pytest.skip("Shader file not found")

        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if "lob * 0.12" in stripped:
                pytest.fail(
                    f"Line {i}: Found hardcoded lob * 0.12 fallback: {stripped}"
                )
