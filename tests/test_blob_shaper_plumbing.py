"""Regression tests for Blob Shaper plumbing — persistence, runtime, renderer."""
from __future__ import annotations

from pathlib import Path
import pytest
from unittest.mock import MagicMock


class TestBlobShaperModels:
    """Verify Blob Shaper fields exist on SpotifyVisualizerSettings and roundtrip."""

    def test_dataclass_defaults(self):
        from core.settings.models import SpotifyVisualizerSettings
        s = SpotifyVisualizerSettings()
        assert s.blob_shaper_enabled is False
        assert s.blob_shaper_base_strength == 0.5
        assert s.blob_shaper_react_strength == 0.5
        assert s.blob_topology == "circle"
        assert s.blob_ring_thickness == 0.3
        assert isinstance(s.blob_shape_base_nodes, list)
        assert isinstance(s.blob_shape_reaction_nodes, list)
        assert isinstance(s.blob_shape_energy_nodes, list)
        assert len(s.blob_shape_energy_nodes) == 0

    def test_roundtrip_to_dict_from_mapping(self):
        from core.settings.models import SpotifyVisualizerSettings
        s = SpotifyVisualizerSettings(
            blob_shaper_enabled=True,
            blob_shaper_base_strength=0.8,
            blob_shaper_react_strength=0.3,
            blob_topology="ring",
            blob_ring_thickness=0.5,
            blob_shape_base_nodes=[[0.0, 0.5], [0.5, 1.5], [1.0, 0.8]],
            blob_shape_reaction_nodes=[[0.0, 0.7], [1.0, 1.2]],
            blob_shape_energy_nodes=[{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0, "dir_len": 22.0}],
        )
        d = s.to_dict()
        prefix = "widgets.spotify_visualizer"
        assert d[f"{prefix}.blob_shaper_enabled"] is True
        assert d[f"{prefix}.blob_topology"] == "ring"
        assert d[f"{prefix}.blob_shape_energy_nodes"] == [{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0, "dir_len": 22.0}]

        flat = {k.split(".", 2)[-1]: v for k, v in d.items() if k.startswith(prefix)}
        s2 = SpotifyVisualizerSettings.from_mapping(flat)
        assert s2.blob_shaper_enabled is True
        assert s2.blob_topology == "ring"
        assert s2.blob_ring_thickness == 0.5
        assert len(s2.blob_shape_energy_nodes) == 1

    def test_override_keys_include_shaper(self):
        from core.settings.models import _VISUALIZER_RUNTIME_OVERRIDE_KEYS
        for key in (
            "blob_shaper_enabled",
            "blob_shaper_base_strength",
            "blob_shaper_react_strength",
            "blob_topology",
            "blob_ring_thickness",
            "blob_shape_base_nodes",
            "blob_shape_reaction_nodes",
            "blob_shape_energy_nodes",
        ):
            assert key in _VISUALIZER_RUNTIME_OVERRIDE_KEYS, f"{key} missing from override keys"


class TestBlobShaperRenderer:
    """Verify renderer helper functions."""

    def test_resample_nodes_flat(self):
        from widgets.spotify_visualizer.renderers.blob import _resample_nodes
        result = _resample_nodes([[0.0, 1.0], [1.0, 1.0]], 8)
        assert len(result) == 8
        for v in result:
            assert abs(v - 1.0) < 0.01

    def test_resample_nodes_ramp(self):
        from widgets.spotify_visualizer.renderers.blob import _resample_nodes
        result = _resample_nodes([[0.0, 0.0], [0.5, 1.0]], 4)
        assert len(result) == 4
        assert result[0] < result[-1]

    def test_resample_nodes_empty(self):
        from widgets.spotify_visualizer.renderers.blob import _resample_nodes
        result = _resample_nodes([], 8)
        assert result == [1.0] * 8

    def test_build_energy_routing_default(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing
        weights = _build_energy_routing([], 8)
        assert len(weights) == 5
        assert weights[0] == [1.0] * 8  # bass default everywhere

    def test_build_energy_routing_single_node(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing
        nodes = [{"type": "mid", "x": 0.5, "y": 0.0, "strength": 1.0}]
        weights = _build_energy_routing(nodes, 8)
        assert len(weights) == 5
        assert max(weights[1]) > 0  # mid channel has some weight

    def test_build_energy_routing_preserves_inward_direction(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing

        nodes = [{"type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0, "dir_x": 0.0, "dir_y": 1.0}]
        weights = _build_energy_routing(nodes, 8)
        assert len(weights) == 5
        assert min(weights[0]) < 0

    def test_build_energy_routing_uses_editor_top_zero_angle_convention(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing

        nodes = [{"type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0}]
        weights = _build_energy_routing(nodes, 32)
        peak_index = max(range(32), key=lambda idx: weights[0][idx])
        assert peak_index in {0, 31}

    def test_build_energy_routing_keeps_authored_influence_broad_and_smooth(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing

        nodes = [{"type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0}]
        weights = _build_energy_routing(nodes, 32)[0]

        assert weights[0] > 0.95
        assert weights[1] > 0.85
        assert weights[2] > 0.55
        assert max(abs(weights[i] - weights[(i + 1) % 32]) for i in range(32)) < 0.22

    def test_runtime_energy_nodes_prefer_react_canvas_when_present(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing

        nodes = [
            {"canvas": "base", "type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0},
            {
                "canvas": "react",
                "type": "mid",
                "x": 1.0,
                "y": 0.5,
                "strength": 1.0,
                "dir_x": 1.0,
                "dir_y": 0.0,
            },
        ]
        weights = _build_energy_routing(nodes, 32)
        assert max(weights[0]) == pytest.approx(0.0)
        assert max(weights[1]) > 0.0

    def test_runtime_energy_nodes_fall_back_to_legacy_base_canvas_when_needed(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing

        nodes = [{"canvas": "base", "type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0}]
        weights = _build_energy_routing(nodes, 32)
        assert max(weights[0]) > 0.0

    def test_resample_nodes_ignores_duplicate_wrap_point(self):
        from widgets.spotify_visualizer.renderers.blob import _resample_nodes

        result = _resample_nodes([[0.0, 1.0], [1.0, 1.6], [0.5, 1.4]], 16)
        assert len(result) == 16
        assert result[0] == pytest.approx(1.0, rel=1e-5)

    def test_resample_nodes_prefers_outer_radius_for_duplicate_angles(self):
        from widgets.spotify_visualizer.renderers.blob import _resample_nodes

        result = _resample_nodes([[0.0, 0.6], [0.0, 1.2], [0.5, 1.0]], 16)
        assert result[0] == pytest.approx(1.2, rel=1e-5)

    def test_shaper_drive_deadzone_keeps_low_idle_energy_on_base_shape(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        radius = _resolve_shaper_radius(1.0, 1.6, 0.04, playing=True)
        assert radius == pytest.approx(1.0)

    def test_shaper_drive_returns_to_base_shape_when_paused(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        radius = _resolve_shaper_radius(1.0, 1.6, 1.0, playing=False)
        assert radius == pytest.approx(1.0)

    def test_shaper_drive_preserves_directional_push_against_reaction_delta(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        outward = _resolve_shaper_radius(1.0, 1.5, 1.0, playing=True)
        inward_from_outward = _resolve_shaper_radius(1.0, 1.5, -1.0, playing=True)
        inward = _resolve_shaper_radius(1.0, 0.7, 1.0, playing=True)
        outward_from_inward = _resolve_shaper_radius(1.0, 0.7, -1.0, playing=True)

        assert outward > 1.0
        assert inward_from_outward < 1.0
        assert inward < 1.0
        assert outward_from_inward > 1.0

    def test_shaper_drive_gives_visible_motion_on_moderate_signed_energy(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        radius = _resolve_shaper_radius(1.0, 1.5, 0.20, playing=True)
        assert radius > 1.10

    def test_blob_shader_uses_interpolated_shaper_radius_as_runtime_core_radius(self):
        shader_path = Path(
            r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_visualizer\shaders\blob.frag"
        )
        shader_source = shader_path.read_text(encoding="utf-8")

        assert "staged_r = r;" in shader_source
        assert "staged_r = shaped_base_r;" not in shader_source

    def test_shaper_wobble_scales_drop_to_zero_at_rest(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_wobble_scales

        paused = _resolve_shaper_wobble_scales(1.0, 1.0, 1.0, playing=False)
        idle = _resolve_shaper_wobble_scales(1.0, 1.0, 0.05, playing=True)
        active = _resolve_shaper_wobble_scales(1.0, 1.0, 1.0, playing=True)

        assert paused == pytest.approx((0.0, 0.0))
        assert idle == pytest.approx((0.0, 0.0))
        assert 0.0 < active[0] < 1.0
        assert 0.0 < active[1] < 1.0

    def test_shaper_energy_bands_prefer_stage_inputs_over_calm_live_bands(self):
        from types import SimpleNamespace
        from widgets.spotify_visualizer.renderers.blob import _get_shaper_energy_bands

        state = SimpleNamespace(
            _energy_bands=SimpleNamespace(bass=0.1, mid=0.1, high=0.1, overall=0.1),
            _blob_live_bass_energy=0.12,
            _blob_live_mid_energy=0.18,
            _blob_live_high_energy=0.10,
            _blob_live_overall_energy=0.14,
            _blob_stage_input_bass=0.32,
            _blob_stage_input_mid=0.41,
            _blob_stage_input_high=0.19,
            _blob_stage_input_overall=0.36,
        )

        bands = _get_shaper_energy_bands(state)
        assert bands[0] > state._blob_live_bass_energy
        assert bands[0] < state._blob_stage_input_bass
        assert bands[1] > state._blob_live_mid_energy
        assert bands[1] < state._blob_stage_input_mid
        assert bands[2] > state._blob_live_high_energy
        assert bands[2] < state._blob_stage_input_high
        assert bands[3] > state._blob_live_overall_energy
        assert bands[3] < state._blob_stage_input_overall

    def test_shaper_energy_bands_fall_back_to_live_bands_when_stage_inputs_missing(self):
        from types import SimpleNamespace
        from widgets.spotify_visualizer.renderers.blob import _get_shaper_energy_bands

        state = SimpleNamespace(
            _energy_bands=SimpleNamespace(bass=0.1, mid=0.1, high=0.1, overall=0.1),
            _blob_live_bass_energy=0.12,
            _blob_live_mid_energy=0.18,
            _blob_live_high_energy=0.10,
            _blob_live_overall_energy=0.14,
        )

        assert _get_shaper_energy_bands(state) == pytest.approx((0.12, 0.18, 0.10, 0.14))

    def test_shaper_energy_bands_keep_live_support_when_stage_inputs_drop_to_zero(self):
        from types import SimpleNamespace
        from widgets.spotify_visualizer.renderers.blob import _get_shaper_energy_bands

        state = SimpleNamespace(
            _energy_bands=SimpleNamespace(bass=0.2, mid=0.2, high=0.2, overall=0.2),
            _blob_live_bass_energy=0.12,
            _blob_live_mid_energy=0.18,
            _blob_live_high_energy=0.10,
            _blob_live_overall_energy=0.14,
            _blob_stage_input_bass=0.0,
            _blob_stage_input_mid=0.0,
            _blob_stage_input_high=0.0,
            _blob_stage_input_overall=0.0,
        )

        assert _get_shaper_energy_bands(state) == pytest.approx((0.12, 0.18, 0.10, 0.14))

    def test_blob_shader_samples_shaper_energy_routing_linearly_to_avoid_overshoot(self):
        shader_path = Path(
            r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_visualizer\shaders\blob.frag"
        )
        shader_source = shader_path.read_text(encoding="utf-8")

        assert "sample_linear_series(angle_frac, u_blob_energy_bass)" in shader_source

    def test_editor_profile_sampler_handles_duplicate_wrap_point_without_seam_spike(self):
        from ui.tabs.media.blob_shape_editor import _sample_profile_smooth

        nodes = [[0.0, 1.0], [0.25, 1.2], [0.75, 0.8], [1.0, 1.6]]
        near_end = _sample_profile_smooth(nodes, 0.99)
        near_start = _sample_profile_smooth(nodes, 0.01)
        assert abs(near_end - near_start) < 0.12

    def test_editor_profile_sampler_prefers_outer_radius_for_duplicate_angles(self):
        from ui.tabs.media.blob_shape_editor import _sample_profile_smooth

        sample = _sample_profile_smooth([[0.0, 0.55], [0.0, 1.15], [0.5, 0.9]], 0.0)
        assert sample == pytest.approx(1.15, rel=1e-5)

    def test_uniform_names_include_shaper(self):
        from widgets.spotify_visualizer.renderers.blob import get_uniform_names
        names = get_uniform_names()
        for u in (
            "u_blob_shaper_enabled",
            "u_blob_shaper_base_strength",
            "u_blob_shaper_react_strength",
            "u_blob_ring_mode",
            "u_blob_ring_thickness",
            "u_blob_base_profile",
            "u_blob_react_profile",
            "u_blob_energy_bass",
            "u_blob_energy_mid",
            "u_blob_energy_vocals",
            "u_blob_energy_treble",
            "u_blob_energy_transient",
            "u_blob_shaper_bass_energy",
            "u_blob_shaper_mid_energy",
            "u_blob_shaper_high_energy",
            "u_blob_shaper_overall_energy",
        ):
            assert u in names, f"Uniform {u} missing from get_uniform_names()"


class TestBlobShaperConfigApplier:
    """Verify config applier routes shaper keys to widget attributes."""

    def test_apply_shaper_kwargs(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        widget = MagicMock()
        widget._blob_shaper_enabled = False
        apply_vis_mode_kwargs(widget, {
            "blob_shaper_enabled": True,
            "blob_shaper_base_strength": 0.7,
            "blob_topology": "ring",
            "blob_ring_thickness": 0.6,
            "blob_shape_base_nodes": [[0.0, 0.5], [1.0, 1.5]],
            "blob_shape_energy_nodes": [{"type": "bass", "x": 0.5, "y": 0.5, "dir_x": 1.0, "dir_y": 0.0, "dir_len": 24.0}],
        })
        assert widget._blob_shaper_enabled is True
        assert widget._blob_shaper_base_strength == pytest.approx(0.7)
        assert widget._blob_topology == "ring"
        assert widget._blob_ring_thickness == pytest.approx(0.6)
        assert widget._blob_shape_base_nodes == [[0.0, 0.5], [1.0, 1.5]]

    def test_topology_validation(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        widget = MagicMock()
        apply_vis_mode_kwargs(widget, {"blob_topology": "invalid_value"})
        assert widget._blob_topology == "circle"

    def test_creator_passes_shaper_kwargs(self):
        """apply_spotify_vis_model_config must pass all shaper kwargs to the widget."""
        from core.settings.models import SpotifyVisualizerSettings
        from rendering.spotify_widget_creators import apply_spotify_vis_model_config
        model = SpotifyVisualizerSettings(
            blob_shaper_enabled=True,
            blob_shaper_base_strength=0.8,
            blob_shaper_react_strength=0.3,
            blob_topology="ring",
            blob_ring_thickness=0.5,
            blob_shape_base_nodes=[[0.0, 0.5], [1.0, 1.5]],
            blob_shape_reaction_nodes=[[0.0, 0.7], [1.0, 1.2]],
            blob_shape_energy_nodes=[{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0, "dir_len": 22.0}],
            blob_stretch=0.7,
        )
        vis = MagicMock()
        apply_spotify_vis_model_config(vis, model)
        vis.apply_vis_mode_config.assert_called_once()
        kwargs = vis.apply_vis_mode_config.call_args
        kw = kwargs.kwargs if kwargs.kwargs else {}
        if not kw:
            _, kw = kwargs
        assert kw.get("blob_shaper_enabled") is True
        assert kw.get("blob_topology") == "ring"
        assert kw.get("blob_ring_thickness") == 0.5
        assert kw.get("blob_shape_base_nodes") == [[0.0, 0.5], [1.0, 1.5]]
        assert kw.get("blob_shape_energy_nodes") == [{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0, "dir_len": 22.0}]
        assert kw.get("blob_stretch") == pytest.approx(0.7)
        assert kw.get("blob_stretch_inner") == pytest.approx(0.0)
        assert kw.get("blob_stretch_outer") == pytest.approx(0.7)

    def test_blob_extras_include_shaper(self):
        from widgets.spotify_visualizer.config_applier import _append_blob_visual_extras
        widget = MagicMock()
        widget._blob_color = MagicMock()
        widget._blob_glow_color = MagicMock()
        widget._blob_edge_color = MagicMock()
        widget._blob_outline_color = MagicMock()
        widget._blob_shaper_enabled = True
        widget._blob_shaper_base_strength = 0.8
        widget._blob_shaper_react_strength = 0.4
        widget._blob_topology = "ring"
        widget._blob_ring_thickness = 0.5
        widget._blob_shape_base_nodes = [[0.0, 1.0]]
        widget._blob_shape_reaction_nodes = [[0.0, 1.0]]
        widget._blob_shape_energy_nodes = []
        extra = {}
        _append_blob_visual_extras(extra, widget)
        assert extra["blob_shaper_enabled"] is True
        assert extra["blob_topology"] == "ring"
        assert extra["blob_ring_thickness"] == 0.5
