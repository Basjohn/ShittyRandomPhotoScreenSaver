"""Regression tests for Blob Shaper plumbing — persistence, runtime, renderer."""
from __future__ import annotations

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
            blob_shape_energy_nodes=[{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0}],
        )
        d = s.to_dict()
        prefix = "widgets.spotify_visualizer"
        assert d[f"{prefix}.blob_shaper_enabled"] is True
        assert d[f"{prefix}.blob_topology"] == "ring"
        assert d[f"{prefix}.blob_shape_energy_nodes"] == [{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0}]

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
        result = _resample_nodes([[0.0, 0.0], [1.0, 1.0]], 4)
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
            "blob_shape_energy_nodes": [{"type": "bass", "x": 0.5, "y": 0.5}],
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
            blob_shape_energy_nodes=[{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0}],
            blob_stretch_inner=0.3,
            blob_stretch_outer=0.7,
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
        assert kw.get("blob_shape_energy_nodes") == [{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0}]
        assert kw.get("blob_stretch_inner") == pytest.approx(0.3)
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
