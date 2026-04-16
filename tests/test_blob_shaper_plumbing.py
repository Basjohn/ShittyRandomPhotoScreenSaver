"""Regression tests for Blob Shaper plumbing — persistence, runtime, renderer."""
from __future__ import annotations

import math
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent


class TestBlobShaperModels:
    """Verify Blob Shaper fields exist on SpotifyVisualizerSettings and roundtrip."""

    def test_dataclass_defaults(self):
        from core.settings.models import SpotifyVisualizerSettings
        s = SpotifyVisualizerSettings()
        assert s.blob_shaper_enabled is False
        assert s.blob_shaper_base_strength == 0.5
        assert s.blob_shaper_react_strength == 0.5
        assert s.blob_shaper_idle_motion == 0.18
        assert s.blob_shaper_audio_motion == 1.20
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
            blob_shaper_idle_motion=0.12,
            blob_shaper_audio_motion=1.65,
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
        assert d[f"{prefix}.blob_shaper_idle_motion"] == pytest.approx(0.12)
        assert d[f"{prefix}.blob_shaper_audio_motion"] == pytest.approx(1.65)
        assert d[f"{prefix}.blob_shape_energy_nodes"] == [{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0, "dir_len": 22.0}]

        flat = {k.split(".", 2)[-1]: v for k, v in d.items() if k.startswith(prefix)}
        s2 = SpotifyVisualizerSettings.from_mapping(flat)
        assert s2.blob_shaper_enabled is True
        assert s2.blob_shaper_idle_motion == pytest.approx(0.12)
        assert s2.blob_shaper_audio_motion == pytest.approx(1.65)
        assert s2.blob_topology == "ring"
        assert s2.blob_ring_thickness == 0.5
        assert len(s2.blob_shape_energy_nodes) == 1

    def test_override_keys_include_shaper(self):
        from core.settings.models import _VISUALIZER_RUNTIME_OVERRIDE_KEYS
        for key in (
            "blob_shaper_enabled",
            "blob_shaper_base_strength",
            "blob_shaper_react_strength",
            "blob_shaper_idle_motion",
            "blob_shaper_audio_motion",
            "blob_topology",
            "blob_ring_thickness",
            "blob_shape_base_nodes",
            "blob_shape_reaction_nodes",
            "blob_shape_energy_nodes",
        ):
            assert key in _VISUALIZER_RUNTIME_OVERRIDE_KEYS, f"{key} missing from override keys"


class TestBlobShaperRenderer:
    """Verify renderer helper functions."""

    @staticmethod
    def _simulate_runtime_profile_series(
        *,
        base_profile: list[float],
        react_profile: list[float],
        weights: list[list[float]],
        times: list[float],
        bass_energy: float = 0.0,
        mid_energy: float = 0.0,
        high_energy: float = 0.0,
        overall_energy: float = 0.0,
        shaper_idle_motion: float = 0.18,
        shaper_audio_motion: float = 1.20,
        react_strength: float = 1.0,
        playing: bool = True,
    ) -> list[list[float]]:
        from widgets.spotify_visualizer.renderers.blob import _solve_runtime_shaper_profile_step

        current = list(base_profile)
        velocity = [0.0] * len(base_profile)
        target_profile = list(base_profile)
        frames: list[list[float]] = []
        last_t = 0.0
        for idx, t in enumerate(times):
            dt = (t - last_t) if idx > 0 else 0.016
            current, velocity, target_profile = _solve_runtime_shaper_profile_step(
                base_profile=base_profile,
                react_profile=react_profile,
                weights=weights,
                previous_profile=current,
                previous_velocity=velocity,
                previous_target_profile=target_profile,
                dt=dt,
                time_value=t,
                bass=bass_energy,
                mid=mid_energy,
                high=high_energy,
                overall=overall_energy,
                react_strength=react_strength,
                shaper_idle_motion=shaper_idle_motion,
                shaper_audio_motion=shaper_audio_motion,
                playing=playing,
                seed=0.37,
            )
            frames.append(list(current))
            last_t = t
        return frames

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

    def test_build_energy_routing_treats_inward_arrow_on_inward_react_dip_as_toward_reaction(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing

        nodes = [{"type": "vocals", "x": 0.5, "y": 0.0, "strength": 1.0, "dir_x": 0.0, "dir_y": 1.0}]
        base_profile = [1.0] * 8
        react_profile = [0.62, 0.70, 0.88, 1.0, 1.0, 1.0, 0.88, 0.70]
        weights = _build_energy_routing(
            nodes,
            8,
            base_profile=base_profile,
            react_profile=react_profile,
        )

        assert max(weights[2]) > 0.0
        assert weights[2][0] > 0.0

    def test_build_energy_routing_uses_editor_top_zero_angle_convention(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing

        nodes = [{"type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0}]
        weights = _build_energy_routing(nodes, 32)
        peak_index = max(range(32), key=lambda idx: weights[0][idx])
        assert peak_index in {0, 31}

    def test_shaper_runtime_profile_uses_shaper_motion_knobs_not_unshaped_wobble(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_runtime_shaper_profile

        base = [1.0] * 16
        react = [1.2] * 16
        weights = [[0.0] * 16 for _ in range(5)]

        quiet = MagicMock()
        quiet._last_update_ts = 1.0
        quiet._blob_shaper_solver_ts = 0.98
        quiet._blob_shaper_react_strength = 0.6
        quiet._blob_constant_wobble = 2.0
        quiet._blob_reactive_wobble = 3.0
        quiet._blob_shaper_idle_motion = 0.0
        quiet._blob_shaper_audio_motion = 0.0
        quiet._playing = True

        driven = MagicMock()
        driven._last_update_ts = 1.0
        driven._blob_shaper_solver_ts = 0.98
        driven._blob_shaper_react_strength = 0.6
        driven._blob_constant_wobble = 0.0
        driven._blob_reactive_wobble = 0.0
        driven._blob_shaper_idle_motion = 0.35
        driven._blob_shaper_audio_motion = 1.8
        driven._playing = True

        quiet_profile = _resolve_runtime_shaper_profile(
            quiet,
            base_profile=base,
            react_profile=react,
            weights=weights,
            bass=0.12,
            mid=0.28,
            high=0.10,
            overall=0.22,
        )
        driven_profile = _resolve_runtime_shaper_profile(
            driven,
            base_profile=base,
            react_profile=react,
            weights=weights,
            bass=0.12,
            mid=0.28,
            high=0.10,
            overall=0.22,
        )

        quiet_spread = max(quiet_profile) - min(quiet_profile)
        driven_spread = max(driven_profile) - min(driven_profile)
        assert driven_spread > quiet_spread * 1.8

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

    def test_resample_nodes_clamp_catmull_overshoot_inside_local_authored_bounds(self):
        from widgets.spotify_visualizer.renderers.blob import _resample_nodes

        result = _resample_nodes([[0.0, 1.0], [0.2, 0.25], [0.4, 1.0], [0.6, 1.0], [0.8, 1.0]], 64)
        assert min(result) >= 0.25 - 1e-6

    def test_shaper_drive_deadzone_keeps_low_idle_energy_on_base_shape(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        radius = _resolve_shaper_radius(1.0, 1.6, 0.04, playing=True)
        assert radius == pytest.approx(1.0)

    def test_shaper_base_shape_stays_authoritative_even_if_base_strength_is_low(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        radius = _resolve_shaper_radius(1.35, 1.9, 0.0, base_strength=0.0, playing=True)
        assert radius == pytest.approx(1.35)

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

    def test_inward_opposite_push_is_clamped_to_safe_target_for_large_outward_shapes(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        radius = _resolve_shaper_radius(1.0, 2.0, -1.0, playing=True)
        assert radius == pytest.approx(0.82)

    def test_positive_shaper_drive_can_slightly_overshoot_reaction_limit_on_kicks(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        resting = _resolve_shaper_radius(1.0, 1.6, 1.0, playing=True)
        kicked = _resolve_shaper_radius(
            1.0,
            1.6,
            1.0,
            bass_energy=1.0,
            overall_energy=1.0,
            playing=True,
        )

        assert kicked > resting
        assert kicked < 1.65

    def test_shaper_drive_gives_visible_motion_on_moderate_signed_energy(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        radius = _resolve_shaper_radius(1.0, 1.5, 0.20, playing=True)
        assert radius > 1.17

    def test_larger_authored_gap_needs_more_energy_to_reach_same_fraction_of_target(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius, _resolve_shaper_targets

        small_gap = _resolve_shaper_radius(1.0, 1.25, 0.45, playing=True)
        large_gap = _resolve_shaper_radius(1.0, 1.90, 0.45, playing=True)
        small_base, small_target, _ = _resolve_shaper_targets(1.0, 1.25)
        large_base, large_target, _ = _resolve_shaper_targets(1.0, 1.90)
        small_fraction = (small_gap - small_base) / (small_target - small_base)
        large_fraction = (large_gap - large_base) / (large_target - large_base)

        assert small_fraction > large_fraction

    def test_routed_shaper_energy_prefers_strongest_local_signed_contributor(self):
        from widgets.spotify_visualizer.renderers.blob import (
            _build_energy_routing,
            _sample_routed_shaper_energy,
        )

        nodes = [
            {"type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0},
            {"type": "mid", "x": 0.5, "y": 0.0, "strength": 1.0, "dir_x": 0.0, "dir_y": 1.0},
        ]
        weights = _build_energy_routing(nodes, 32)

        signed = _sample_routed_shaper_energy(
            0.0,
            weights,
            bass=0.82,
            mid=0.41,
            high=0.0,
            overall=0.0,
        )

        assert signed > 0.75

    def test_routed_shaper_energy_does_not_collapse_to_base_when_opposing_bands_overlap(self):
        from widgets.spotify_visualizer.renderers.blob import (
            _build_energy_routing,
            _sample_routed_shaper_energy,
        )

        nodes = [
            {"type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0},
            {"type": "mid", "x": 0.56, "y": 0.04, "strength": 1.0, "dir_x": 0.0, "dir_y": 1.0},
        ]
        weights = _build_energy_routing(nodes, 64)

        signed = _sample_routed_shaper_energy(
            0.0,
            weights,
            bass=0.66,
            mid=0.61,
            high=0.0,
            overall=0.0,
        )

        assert abs(signed) > 0.50

    def test_shaper_react_strength_scales_reachable_reaction_limit_without_flattening_base(self):
        from widgets.spotify_visualizer.renderers.blob import _resolve_shaper_radius

        half = _resolve_shaper_radius(1.0, 1.8, 1.0, react_strength=0.5, playing=True)
        full = _resolve_shaper_radius(1.0, 1.8, 1.0, react_strength=1.0, playing=True)

        assert half == pytest.approx(1.4)
        assert full == pytest.approx(1.8)

    def test_blob_shader_uses_cpu_solved_runtime_profile(self):
        shader_path = Path(
            r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_visualizer\shaders\blob.frag"
        )
        shader_source = shader_path.read_text(encoding="utf-8")

        assert "u_blob_runtime_profile" in shader_source
        assert "sample_profile(angle_frac, u_blob_runtime_profile)" in shader_source
        assert "shaper_contour_and_shell_motion(" not in shader_source

    def test_contour_residual_motion_is_quiet_when_motion_sliders_are_zero(self):
        from widgets.spotify_visualizer.blob_shaper_solver import build_contour_residual_profile

        residual = build_contour_residual_profile(
            sample_count=64,
            time_value=1.2,
            idle_motion=0.0,
            audio_motion=0.0,
            overall_energy=0.9,
            vocal_energy=0.9,
            high_energy=0.4,
            playing=True,
        )
        assert max(abs(value) for value in residual) < 1e-6

    def test_shaper_runtime_profile_moves_toward_reaction_shape_and_keeps_temporal_motion(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing

        base_profile = [1.0] * 64
        react_profile = [1.0] * 64
        react_profile[0] = 1.48
        react_profile[1] = 1.42
        react_profile[-1] = 1.42
        weights = _build_energy_routing(
            [{"type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0}],
            64,
            base_profile=base_profile,
            react_profile=react_profile,
        )
        frames = self._simulate_runtime_profile_series(
            base_profile=base_profile,
            react_profile=react_profile,
            weights=weights,
            times=[i * 0.10 for i in range(40)],
            bass_energy=1.0,
            mid_energy=0.95,
            high_energy=0.34,
            overall_energy=0.96,
            shaper_idle_motion=1.2,
            shaper_audio_motion=2.4,
            react_strength=0.9,
            playing=True,
        )
        leading_edge = [frame[0] for frame in frames]

        assert max(leading_edge) > 1.24
        assert max(leading_edge) - min(leading_edge) > 0.035

    def test_shaper_runtime_profile_releases_back_toward_base_slowly_instead_of_snapping(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing, _solve_runtime_shaper_profile_step

        base_profile = [1.0] * 64
        react_profile = [1.0] * 64
        react_profile[0] = 1.58
        react_profile[1] = 1.46
        react_profile[-1] = 1.46
        weights = _build_energy_routing(
            [{"type": "bass", "x": 0.5, "y": 0.0, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0}],
            64,
            base_profile=base_profile,
            react_profile=react_profile,
        )

        profile = list(base_profile)
        velocity = [0.0] * 64
        target = list(base_profile)
        time_value = 0.0

        for _ in range(18):
            time_value += 0.05
            profile, velocity, target = _solve_runtime_shaper_profile_step(
                base_profile=base_profile,
                react_profile=react_profile,
                weights=weights,
                previous_profile=profile,
                previous_velocity=velocity,
                previous_target_profile=target,
                dt=0.05,
                time_value=time_value,
                bass=1.0,
                mid=0.92,
                high=0.28,
                overall=0.94,
                react_strength=1.0,
                shaper_idle_motion=0.5,
                shaper_audio_motion=1.0,
                playing=True,
                seed=0.37,
            )
        peak = profile[0]
        assert peak > 1.30

        releases = []
        for _ in range(8):
            time_value += 0.05
            profile, velocity, target = _solve_runtime_shaper_profile_step(
                base_profile=base_profile,
                react_profile=react_profile,
                weights=weights,
                previous_profile=profile,
                previous_velocity=velocity,
                previous_target_profile=target,
                dt=0.05,
                time_value=time_value,
                bass=0.0,
                mid=0.0,
                high=0.0,
                overall=0.0,
                react_strength=1.0,
                shaper_idle_motion=0.0,
                shaper_audio_motion=0.0,
                playing=True,
                seed=0.37,
            )
            releases.append(profile[0])

        assert releases[0] > 1.18
        assert releases[-1] > 1.04
        assert releases[-1] < peak

    def test_shaper_runtime_profile_stays_angularly_smooth_inward_case(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing, _resample_nodes

        base_nodes = [[0.0, 1.0], [0.16, 0.98], [0.34, 1.02], [0.56, 1.0], [0.80, 1.01]]
        react_nodes = [[0.0, 0.62], [0.12, 1.28], [0.34, 0.72], [0.56, 1.18], [0.78, 0.68]]
        base_profile = _resample_nodes(base_nodes, 64)
        react_profile = _resample_nodes(react_nodes, 64)
        weights = _build_energy_routing(
            [
                {"type": "bass", "x": 0.85, "y": 0.50, "strength": 1.0, "dir_x": -1.0, "dir_y": 0.0},
                {"type": "vocals", "x": 0.50, "y": 0.20, "strength": 1.0, "dir_x": 0.0, "dir_y": 1.0},
                {"type": "mid", "x": 0.22, "y": 0.54, "strength": 1.0, "dir_x": 1.0, "dir_y": 0.0},
            ],
            64,
            base_profile=base_profile,
            react_profile=react_profile,
        )
        frames = self._simulate_runtime_profile_series(
            base_profile=base_profile,
            react_profile=react_profile,
            weights=weights,
            times=[i * 0.08 for i in range(30)],
            bass_energy=0.88,
            mid_energy=0.82,
            high_energy=0.30,
            overall_energy=0.72,
            shaper_idle_motion=1.0,
            shaper_audio_motion=2.0,
            react_strength=0.9,
            playing=True,
        )
        runtime_profile = frames[-1]
        max_neighbor_jump = max(abs(runtime_profile[i] - runtime_profile[(i + 1) % 64]) for i in range(64))
        assert max_neighbor_jump < 0.09

    def test_routed_shaper_energy_series_stays_angularly_smooth_without_blade_cut(self):
        from widgets.spotify_visualizer.renderers.blob import _build_energy_routing, _sample_routed_shaper_energy

        nodes = [
            {"type": "mid", "x": 0.85, "y": 0.45, "strength": 1.0, "dir_x": 1.0, "dir_y": 0.0},
            {"type": "mid", "x": 0.88, "y": 0.32, "strength": 1.0, "dir_x": 0.8, "dir_y": -0.6},
        ]
        weights = _build_energy_routing(nodes, 64)
        signed = [
            _sample_routed_shaper_energy(i / 64.0, weights, bass=0.0, mid=0.85, high=0.0, overall=0.0)
            for i in range(64)
        ]
        max_neighbor_jump = max(abs(signed[i] - signed[(i + 1) % 64]) for i in range(64))
        assert max_neighbor_jump < 0.30

    def test_final_shaper_radius_series_stays_angularly_smooth_without_radial_blades(self):
        from widgets.spotify_visualizer.renderers.blob import (
            _build_energy_routing,
            _resample_nodes,
            _resolve_shaper_radius_at_angle,
        )

        base_nodes = [[0.0, 1.0], [0.18, 1.02], [0.35, 0.96], [0.55, 0.98], [0.78, 1.01]]
        react_nodes = [[0.0, 1.42], [0.18, 1.06], [0.28, 1.28], [0.42, 0.98], [0.62, 1.20], [0.82, 1.05]]
        base_profile = _resample_nodes(base_nodes, 64)
        react_profile = _resample_nodes(react_nodes, 64)
        nodes = [
            {"type": "bass", "x": 0.84, "y": 0.46, "strength": 1.0, "dir_x": 1.0, "dir_y": 0.0},
            {"type": "mid", "x": 0.80, "y": 0.32, "strength": 1.0, "dir_x": 0.8, "dir_y": -0.6},
        ]
        weights = _build_energy_routing(nodes, 64, base_profile=base_profile, react_profile=react_profile)
        radii = [
            _resolve_shaper_radius_at_angle(
                i / 64.0,
                base_profile=base_profile,
                react_profile=react_profile,
                weights=weights,
                staged_radius=1.0,
                bass=0.78,
                mid=0.82,
                high=0.20,
                overall=0.65,
                react_strength=0.7,
                playing=True,
            )
            for i in range(64)
        ]
        max_neighbor_jump = max(abs(radii[i] - radii[(i + 1) % 64]) for i in range(64))
        assert max_neighbor_jump < 0.16

    def test_inward_directed_radius_series_stays_angularly_smooth_without_sector_cuts(self):
        from widgets.spotify_visualizer.renderers.blob import (
            _build_energy_routing,
            _resample_nodes,
            _resolve_shaper_radius_at_angle,
        )

        base_nodes = [[0.0, 1.0], [0.16, 0.98], [0.34, 1.02], [0.56, 1.0], [0.80, 1.01]]
        react_nodes = [[0.0, 0.62], [0.12, 1.28], [0.34, 0.72], [0.56, 1.18], [0.78, 0.68]]
        base_profile = _resample_nodes(base_nodes, 64)
        react_profile = _resample_nodes(react_nodes, 64)
        nodes = [
            {"type": "bass", "x": 0.85, "y": 0.50, "strength": 1.0, "dir_x": -1.0, "dir_y": 0.0},
            {"type": "vocals", "x": 0.50, "y": 0.20, "strength": 1.0, "dir_x": 0.0, "dir_y": 1.0},
            {"type": "mid", "x": 0.22, "y": 0.54, "strength": 1.0, "dir_x": 1.0, "dir_y": 0.0},
        ]
        weights = _build_energy_routing(nodes, 64, base_profile=base_profile, react_profile=react_profile)
        radii = [
            _resolve_shaper_radius_at_angle(
                i / 64.0,
                base_profile=base_profile,
                react_profile=react_profile,
                weights=weights,
                staged_radius=1.0,
                bass=0.88,
                mid=0.82,
                high=0.30,
                overall=0.72,
                react_strength=0.9,
                playing=True,
            )
            for i in range(64)
        ]
        max_neighbor_jump = max(abs(radii[i] - radii[(i + 1) % 64]) for i in range(64))
        assert max_neighbor_jump < 0.14

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
        assert bands[0] <= state._blob_stage_input_bass
        assert bands[0] > 0.28
        assert bands[1] > state._blob_live_mid_energy
        assert bands[1] <= state._blob_stage_input_mid
        assert bands[1] > 0.35
        assert bands[2] > state._blob_live_high_energy
        assert bands[2] <= state._blob_stage_input_high
        assert bands[2] > 0.16
        assert bands[3] > state._blob_live_overall_energy
        assert bands[3] <= state._blob_stage_input_overall
        assert bands[3] > 0.30

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

    def test_blob_shader_renders_shaper_mode_from_runtime_profile_not_per_fragment_energy_resolution(self):
        shader_path = Path(
            r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_visualizer\shaders\blob.frag"
        )
        shader_source = shader_path.read_text(encoding="utf-8")

        assert "sample_smoothed_shaper_energy(" not in shader_source
        assert "shape_shaper_energy_for_gap(" not in shader_source
        assert "float d_fill = d_base;" in shader_source
        assert "float d_shell = d_fill;" in shader_source

    def test_blob_ring_shader_keeps_hollow_center_out_of_outer_glow_and_ghost_fill(self):
        shader_path = Path(
            r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_visualizer\shaders\blob.frag"
        )
        shader_source = shader_path.read_text(encoding="utf-8")

        assert "d_glow = d_signed - ring_thickness;" in shader_source
        assert "if (d_glow > 0.0 && glow_sigma > 0.0)" in shader_source
        assert "ghost_d = abs(ghost_signed_d) - ring_thickness;" in shader_source
        assert "float outside_current = smoothstep(-0.01, 0.02, d_fill);" in shader_source

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
            "u_blob_runtime_profile",
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

    def test_overlay_uniform_lookup_uses_array_element_zero_for_gl_arrays(self):
        from widgets.spotify_bars_gl_overlay import _uniform_lookup_name

        assert _uniform_lookup_name("u_blob_base_profile") == "u_blob_base_profile[0]"
        assert _uniform_lookup_name("u_blob_runtime_profile") == "u_blob_runtime_profile[0]"
        assert _uniform_lookup_name("u_waveform") == "u_waveform[0]"
        assert _uniform_lookup_name("u_bars") == "u_bars[0]"
        assert _uniform_lookup_name("u_blob_ring_mode") == "u_blob_ring_mode"

    def test_overlay_shader_manifest_includes_runtime_profile_uniform(self):
        overlay_path = Path(
            r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\widgets\spotify_bars_gl_overlay.py"
        )
        source = overlay_path.read_text(encoding="utf-8")
        assert '"u_blob_runtime_profile"' in source

    @staticmethod
    def _mouse_event(event_type, x, y, button, buttons=None):
        if buttons is None:
            buttons = button
        return QMouseEvent(
            event_type,
            QPointF(x, y),
            QPointF(x, y),
            QPointF(x, y),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )

    @pytest.mark.qt
    def test_blob_shape_editor_right_click_removes_profile_node(self, qt_app):
        from ui.tabs.media.blob_shape_editor import _PolarEditorCanvas

        canvas = _PolarEditorCanvas("Test")
        try:
            canvas.show()
            canvas.set_profile_nodes([
                [0.0, 1.0],
                [0.25, 1.0],
                [0.50, 1.0],
                [0.75, 1.0],
                [0.125, 1.35],
            ])
            initial_nodes = canvas.get_profile_nodes()
            assert len(initial_nodes) == 5

            remove_target = canvas._node_to_screen(0.125, 1.35)
            canvas.mousePressEvent(
                self._mouse_event(
                    QEvent.Type.MouseButtonPress,
                    remove_target.x(),
                    remove_target.y(),
                    Qt.MouseButton.RightButton,
                )
            )
            qt_app.processEvents()

            updated_nodes = canvas.get_profile_nodes()
            assert len(updated_nodes) == 4
            assert not any(
                abs(float(node[0]) - 0.125) < 1e-4 and abs(float(node[1]) - 1.35) < 1e-4
                for node in updated_nodes
            )
        finally:
            canvas.deleteLater()


class TestBlobShaperConfigApplier:
    """Verify config applier routes shaper keys to widget attributes."""

    def test_blob_mode_contract_normalizer_zeros_unshaped_motion_for_shaper(self):
        from widgets.spotify_visualizer.config_applier import normalize_blob_mode_contract_values

        normalized = normalize_blob_mode_contract_values(
            blob_shaper_enabled=True,
            blob_reactive_deformation=1.6,
            blob_constant_wobble=0.8,
            blob_reactive_wobble=1.1,
            blob_stretch_tendency=0.65,
            blob_stretch_inner=0.25,
            blob_stretch_outer=0.65,
        )

        assert normalized == {
            "blob_reactive_deformation": 0.0,
            "blob_constant_wobble": 0.0,
            "blob_reactive_wobble": 0.0,
            "blob_stretch_tendency": 0.0,
            "blob_stretch_inner": 0.0,
            "blob_stretch_outer": 0.0,
        }

    def test_apply_shaper_kwargs_enforces_runtime_motion_fence_even_if_stale_values_arrive(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

        widget = MagicMock()
        widget._blob_shaper_enabled = False
        widget._blob_reactive_deformation = 0.0
        widget._blob_constant_wobble = 0.0
        widget._blob_reactive_wobble = 0.0
        widget._blob_stretch_tendency = 0.0
        widget._blob_stretch_inner = 0.0
        widget._blob_stretch_outer = 0.0

        apply_vis_mode_kwargs(widget, {
            "blob_reactive_deformation": 1.7,
            "blob_constant_wobble": 0.9,
            "blob_reactive_wobble": 1.4,
            "blob_stretch": 0.6,
            "blob_stretch_inner": 0.2,
            "blob_stretch_outer": 0.6,
            "blob_shaper_enabled": True,
        })

        assert widget._blob_shaper_enabled is True
        assert widget._blob_reactive_deformation == pytest.approx(0.0)
        assert widget._blob_constant_wobble == pytest.approx(0.0)
        assert widget._blob_reactive_wobble == pytest.approx(0.0)
        assert widget._blob_stretch_tendency == pytest.approx(0.0)
        assert widget._blob_stretch_inner == pytest.approx(0.0)
        assert widget._blob_stretch_outer == pytest.approx(0.0)

    def test_apply_shaper_kwargs(self):
        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        widget = MagicMock()
        widget._blob_shaper_enabled = False
        apply_vis_mode_kwargs(widget, {
            "blob_shaper_enabled": True,
            "blob_shaper_base_strength": 0.7,
            "blob_shaper_idle_motion": 0.16,
            "blob_shaper_audio_motion": 1.7,
            "blob_topology": "ring",
            "blob_ring_thickness": 0.6,
            "blob_shape_base_nodes": [[0.0, 0.5], [1.0, 1.5]],
            "blob_shape_energy_nodes": [{"type": "bass", "x": 0.5, "y": 0.5, "dir_x": 1.0, "dir_y": 0.0, "dir_len": 24.0}],
        })
        assert widget._blob_shaper_enabled is True
        assert widget._blob_shaper_base_strength == pytest.approx(0.7)
        assert widget._blob_shaper_idle_motion == pytest.approx(0.16)
        assert widget._blob_shaper_audio_motion == pytest.approx(1.7)
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
            blob_shaper_idle_motion=0.12,
            blob_shaper_audio_motion=1.65,
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
        assert kw.get("blob_shaper_idle_motion") == pytest.approx(0.12)
        assert kw.get("blob_shaper_audio_motion") == pytest.approx(1.65)
        assert kw.get("blob_topology") == "ring"
        assert kw.get("blob_ring_thickness") == 0.5
        assert kw.get("blob_shape_base_nodes") == [[0.0, 0.5], [1.0, 1.5]]
        assert kw.get("blob_shape_energy_nodes") == [{"type": "bass", "x": 0.3, "y": 0.7, "strength": 1.0, "dir_x": 0.0, "dir_y": -1.0, "dir_len": 22.0}]
        assert kw.get("blob_reactive_deformation") == pytest.approx(0.0)
        assert kw.get("blob_constant_wobble") == pytest.approx(0.0)
        assert kw.get("blob_reactive_wobble") == pytest.approx(0.0)
        assert kw.get("blob_stretch") == pytest.approx(0.0)
        assert kw.get("blob_stretch_inner") == pytest.approx(0.0)
        assert kw.get("blob_stretch_outer") == pytest.approx(0.0)

    def test_blob_extras_include_shaper(self):
        from widgets.spotify_visualizer.config_applier import _append_blob_visual_extras
        widget = MagicMock()
        widget._blob_color = MagicMock()
        widget._blob_glow_color = MagicMock()
        widget._blob_edge_color = MagicMock()
        widget._blob_outline_color = MagicMock()
        widget._blob_inward_liquid_color = MagicMock()
        widget._blob_inward_liquid_enabled = True
        widget._blob_inward_liquid_reactivity = 1.15
        widget._blob_inward_liquid_max_size = 0.31
        widget._blob_shaper_enabled = True
        widget._blob_shaper_base_strength = 0.8
        widget._blob_shaper_react_strength = 0.4
        widget._blob_shaper_idle_motion = 0.14
        widget._blob_shaper_audio_motion = 1.55
        widget._blob_topology = "ring"
        widget._blob_ring_thickness = 0.5
        widget._blob_shape_base_nodes = [[0.0, 1.0]]
        widget._blob_shape_reaction_nodes = [[0.0, 1.0]]
        widget._blob_shape_energy_nodes = []
        widget._blob_reactive_deformation = 1.4
        widget._blob_constant_wobble = 1.1
        widget._blob_reactive_wobble = 1.7
        widget._blob_stretch_tendency = 0.6
        widget._blob_stretch_outer = 0.6
        extra = {}
        _append_blob_visual_extras(extra, widget)
        assert extra["blob_shaper_enabled"] is True
        assert extra["blob_inward_liquid_color"] is widget._blob_inward_liquid_color
        assert extra["blob_inward_liquid_enabled"] is True
        assert extra["blob_inward_liquid_reactivity"] == pytest.approx(1.15)
        assert extra["blob_inward_liquid_max_size"] == pytest.approx(0.31)
        assert extra["blob_shaper_idle_motion"] == pytest.approx(0.14)
        assert extra["blob_shaper_audio_motion"] == pytest.approx(1.55)
        assert extra["blob_topology"] == "ring"
        assert extra["blob_ring_thickness"] == 0.5
        assert extra["blob_reactive_deformation"] == pytest.approx(0.0)
        assert extra["blob_constant_wobble"] == pytest.approx(0.0)
        assert extra["blob_reactive_wobble"] == pytest.approx(0.0)
        assert extra["blob_stretch_tendency"] == pytest.approx(0.0)
        assert extra["blob_stretch_inner"] == pytest.approx(0.0)
        assert extra["blob_stretch_outer"] == pytest.approx(0.0)

    def test_blob_extras_preserve_unshaped_motion_controls_when_shaper_is_off(self):
        from widgets.spotify_visualizer.config_applier import _append_blob_visual_extras

        widget = MagicMock()
        widget._blob_color = MagicMock()
        widget._blob_glow_color = MagicMock()
        widget._blob_edge_color = MagicMock()
        widget._blob_outline_color = MagicMock()
        widget._blob_pulse = 1.0
        widget._blob_width = 1.0
        widget._blob_size = 1.0
        widget._blob_glow_intensity = 0.5
        widget._blob_glow_reactivity = 1.0
        widget._blob_glow_max_size = 1.0
        widget._blob_reactive_glow = True
        widget._blob_inward_liquid_color = MagicMock()
        widget._blob_inward_liquid_enabled = True
        widget._blob_inward_liquid_reactivity = 1.33
        widget._blob_inward_liquid_max_size = 0.27
        widget._blob_glow_drive_mode = "bass"
        widget._blob_shaper_enabled = False
        widget._blob_reactive_deformation = 1.3
        widget._blob_constant_wobble = 0.9
        widget._blob_reactive_wobble = 1.4
        widget._blob_stretch_tendency = 0.52
        widget._blob_core_scale = 1.0
        widget._blob_core_floor_bias = 0.35
        widget._blob_shaper_base_strength = 0.5
        widget._blob_shaper_react_strength = 0.5
        widget._blob_shaper_idle_motion = 0.18
        widget._blob_shaper_audio_motion = 1.20
        widget._blob_topology = "circle"
        widget._blob_ring_thickness = 0.3
        widget._blob_shape_base_nodes = []
        widget._blob_shape_reaction_nodes = []
        widget._blob_shape_energy_nodes = []
        widget._blob_stretch_outer = 0.52

        extra = {}
        _append_blob_visual_extras(extra, widget)

        assert extra["blob_reactive_deformation"] == pytest.approx(1.3)
        assert extra["blob_inward_liquid_enabled"] is True
        assert extra["blob_inward_liquid_reactivity"] == pytest.approx(1.33)
        assert extra["blob_inward_liquid_max_size"] == pytest.approx(0.27)
        assert extra["blob_constant_wobble"] == pytest.approx(0.9)
        assert extra["blob_reactive_wobble"] == pytest.approx(1.4)
        assert extra["blob_stretch_tendency"] == pytest.approx(0.52)
        assert extra["blob_stretch_inner"] == pytest.approx(0.0)
        assert extra["blob_stretch_outer"] == pytest.approx(0.52)

    def test_apply_spotify_vis_model_config_carries_blob_inward_liquid_contract(self):
        from core.settings.models import SpotifyVisualizerSettings
        from rendering.spotify_widget_creators import apply_spotify_vis_model_config

        model = SpotifyVisualizerSettings(
            mode="blob",
            blob_inward_liquid_enabled=True,
            blob_inward_liquid_reactivity=1.27,
            blob_inward_liquid_max_size=0.33,
            blob_inward_liquid_color=[11, 22, 33, 144],
        )
        vis = MagicMock()

        apply_spotify_vis_model_config(vis, model)

        vis.apply_vis_mode_config.assert_called_once()
        kwargs = vis.apply_vis_mode_config.call_args
        kw = kwargs.kwargs if kwargs.kwargs else {}
        if not kw:
            _, kw = kwargs
        assert kw.get("blob_inward_liquid_enabled") is True
        assert kw.get("blob_inward_liquid_reactivity") == pytest.approx(1.27)
        assert kw.get("blob_inward_liquid_max_size") == pytest.approx(0.33)
        assert kw.get("blob_inward_liquid_color") == [11, 22, 33, 144]
