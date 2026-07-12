from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from core.settings.visualizer_blob_contract import (
    BLOB_TYPE_MIGHTY,
    BLOB_TYPE_SHAPED,
)
from widgets.spotify_visualizer.config_applier import (
    _append_blob_visual_extras,
    apply_vis_mode_kwargs,
)
from widgets.spotify_visualizer.overlay_render_dispatch import (
    resolve_render_program_key,
)
from widgets.spotify_visualizer.overlay_state import reset_blob_variant_state


def _blob_widget_stub(blob_type: str) -> SimpleNamespace:
    return SimpleNamespace(
        _blob_type=blob_type,
        _blob_shaper_enabled=blob_type == BLOB_TYPE_SHAPED,
        _blob_color=QColor(1, 2, 3, 255),
        _blob_glow_color=QColor(4, 5, 6, 255),
        _blob_edge_color=QColor(7, 8, 9, 255),
        _blob_outline_color=QColor(10, 11, 12, 255),
        _blob_inward_liquid_color=QColor(13, 14, 15, 200),
        _blob_pulse=0.8,
        _blob_pulse_release_ms=320.0,
        _blob_width=0.9,
        _blob_size=0.7,
        _blob_glow_intensity=0.5,
        _blob_glow_reactivity=1.1,
        _blob_glow_max_size=1.2,
        _blob_reactive_glow=True,
        _blob_inward_liquid_enabled=True,
        _blob_inward_liquid_reactivity=1.25,
        _blob_inward_liquid_max_size=0.3,
        _blob_glow_drive_mode="vocal",
        _transient_pulse_gain=1.8,
        _transient_clamp=1.25,
        _blob_transient_mix_bass=0.42,
        _blob_transient_mix_vocal=0.76,
        _blob_reactive_deformation=1.2,
        _blob_pulse_cap=0.9,
        _blob_stage_gain=0.75,
        _blob_core_scale=0.85,
        _blob_core_floor_bias=0.25,
        _blob_stage_bias=-0.05,
        _blob_stage2_release_ms=900.0,
        _blob_stage3_release_ms=1200.0,
        _blob_constant_wobble=0.6,
        _blob_reactive_wobble=1.4,
        _blob_stretch_tendency=0.55,
        _blob_stretch_inner=0.4,
        _blob_stretch_outer=0.65,
        _blob_shaper_base_strength=0.8,
        _blob_shaper_react_strength=0.7,
        _blob_shaper_idle_motion=0.25,
        _blob_shaper_audio_motion=1.6,
        _blob_topology="ring",
        _blob_ring_thickness=0.45,
        _blob_shape_base_nodes=[[0.0, 0.8], [0.5, 1.2]],
        _blob_shape_reaction_nodes=[[0.0, 1.0], [0.5, 1.4]],
        _blob_shape_energy_nodes=[{"type": "bass", "x": 0.5, "y": 0.2}],
    )


@pytest.mark.parametrize(
    ("blob_type", "program_key"),
    [
        (BLOB_TYPE_MIGHTY, "blob_mighty"),
        (BLOB_TYPE_SHAPED, "blob_shaped"),
    ],
)
def test_blob_type_selects_a_distinct_renderer_program(blob_type, program_key):
    state = SimpleNamespace(_blob_type=blob_type, _blob_shaper_enabled=False)
    assert resolve_render_program_key(state, "blob") == program_key
    assert resolve_render_program_key(state, "spectrum") == "spectrum"


def test_apply_blob_type_fences_subtype_owned_motion():
    widget = _blob_widget_stub(BLOB_TYPE_MIGHTY)
    apply_vis_mode_kwargs(
        widget,
        {
            "blob_type": BLOB_TYPE_SHAPED,
            "blob_reactive_deformation": 1.8,
            "blob_constant_wobble": 1.2,
            "blob_reactive_wobble": 2.1,
            "blob_stretch": 0.75,
        },
    )
    assert widget._blob_type == BLOB_TYPE_SHAPED
    assert widget._blob_shaper_enabled is True
    assert widget._blob_reactive_deformation == 0.0
    assert widget._blob_constant_wobble == 0.0
    assert widget._blob_reactive_wobble == 0.0
    assert widget._blob_stretch_tendency == 0.0

    apply_vis_mode_kwargs(
        widget,
        {
            "blob_type": BLOB_TYPE_MIGHTY,
            "blob_reactive_deformation": 1.35,
            "blob_constant_wobble": 0.75,
            "blob_reactive_wobble": 1.55,
            "blob_stretch": 0.62,
            "blob_stretch_inner": 0.9,
        },
    )
    assert widget._blob_type == BLOB_TYPE_MIGHTY
    assert widget._blob_shaper_enabled is False
    assert widget._blob_reactive_deformation == pytest.approx(1.35)
    assert widget._blob_constant_wobble == pytest.approx(0.75)
    assert widget._blob_reactive_wobble == pytest.approx(1.55)
    assert widget._blob_stretch_inner == 0.0


def test_gpu_payload_contains_only_the_selected_blob_subtype_controls():
    mighty_extra: dict = {}
    _append_blob_visual_extras(mighty_extra, _blob_widget_stub(BLOB_TYPE_MIGHTY))
    assert mighty_extra["blob_type"] == BLOB_TYPE_MIGHTY
    assert "blob_shaper_enabled" not in mighty_extra
    assert "blob_constant_wobble" in mighty_extra
    assert "blob_shape_base_nodes" not in mighty_extra
    assert mighty_extra["transient_pulse_gain"] == pytest.approx(1.8)
    assert mighty_extra["transient_clamp"] == pytest.approx(1.25)
    assert mighty_extra["blob_transient_mix_bass"] == pytest.approx(0.42)
    assert mighty_extra["blob_transient_mix_vocal"] == pytest.approx(0.76)

    shaped_extra: dict = {}
    _append_blob_visual_extras(shaped_extra, _blob_widget_stub(BLOB_TYPE_SHAPED))
    assert shaped_extra["blob_type"] == BLOB_TYPE_SHAPED
    assert "blob_shaper_enabled" not in shaped_extra
    assert "blob_shape_base_nodes" in shaped_extra
    assert "blob_constant_wobble" not in shaped_extra
    assert shaped_extra["blob_inward_liquid_enabled"] is True
    assert shaped_extra["transient_pulse_gain"] == pytest.approx(1.8)


def test_blob_variant_reset_clears_both_solver_families_and_ghost_shape():
    state = SimpleNamespace(
        _blob_unshaped_runtime_profile=[1.2],
        _blob_unshaped_runtime_velocity=[0.2],
        _blob_unshaped_runtime_target_profile=[1.1],
        _blob_shaper_runtime_profile=[0.8],
        _blob_shaper_runtime_velocity=[-0.1],
        _blob_shaper_runtime_target_profile=[0.9],
        _blob_runtime_diag_profile=[1.4],
        _blob_profile_transport_sig=("mighty", 7, 128),
        _blob_peak_energy=1.0,
        _blob_peak_bass=0.9,
        _blob_peak_mid=0.8,
        _blob_peak_high=0.7,
        _blob_peak_overall=1.0,
        _blob_peak_hold_remaining=0.15,
        _blob_pocket_state=None,
    )
    reset_blob_variant_state(state)
    assert state._blob_unshaped_runtime_profile is None
    assert state._blob_shaper_runtime_profile is None
    assert state._blob_runtime_diag_profile is None
    assert state._blob_profile_transport_sig is None
    assert state._blob_peak_energy == 0.0
    assert state._blob_peak_overall == 0.0
    assert state._blob_stage_input_bass is None


@pytest.mark.qt
def test_overlay_type_switch_resets_before_accepting_shaped_state(qt_app, monkeypatch):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    def _handoff(overlay, **_kwargs):
        overlay._vis_mode = "blob"
        return True

    monkeypatch.setattr("widgets.spotify_bars_gl_overlay.apply_state_handoff", _handoff)
    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_type = BLOB_TYPE_MIGHTY
    overlay._blob_unshaped_runtime_profile = [1.3] * 64
    overlay._blob_peak_energy = 0.9
    overlay.set_state(
        QRect(0, 0, 320, 180),
        [],
        0,
        1,
        QColor("white"),
        QColor("white"),
        1.0,
        True,
        True,
        vis_mode="blob",
        blob_type=BLOB_TYPE_SHAPED,
    )
    assert overlay._blob_type == BLOB_TYPE_SHAPED
    assert overlay._blob_shaper_enabled is True
    assert overlay._blob_unshaped_runtime_profile is None
    assert overlay._blob_peak_energy == 0.0
    overlay.deleteLater()


@pytest.mark.qt
def test_blob_overlay_transient_controls_change_real_blob_event_pressure(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
    from widgets.spotify_visualizer.energy_bands import EnergyBands
    from widgets.spotify_visualizer.transient_bus import TransientEnergyBands

    overlay = SpotifyBarsGLOverlay(None)
    overlay._transient_energy = TransientEnergyBands(
        bass_transient=0.80,
        mid_transient=0.60,
        high_transient=0.40,
    )
    overlay._blob_transient_mix_bass = 0.50
    overlay._blob_transient_mix_vocal = 0.75
    overlay._transient_clamp = 1.5

    overlay._transient_pulse_gain = 0.0
    overlay._compute_blob_live_bands(EnergyBands())
    assert overlay._blob_diag_transient_bass == 0.0
    assert overlay._blob_diag_transient_mid == 0.0

    overlay._transient_pulse_gain = 2.0
    overlay._compute_blob_live_bands(EnergyBands())
    assert overlay._blob_diag_transient_bass == pytest.approx(0.80)
    assert overlay._blob_diag_transient_mid == pytest.approx(0.90)
    assert overlay._blob_diag_transient_high == pytest.approx(0.18)
    overlay.deleteLater()


def test_concrete_blob_shader_sources_are_split_and_inner_paint_is_reactive():
    from widgets.spotify_visualizer.shaders import load_fragment_shader

    mighty = load_fragment_shader("blob_mighty")
    shaped = load_fragment_shader("blob_shaped")
    assert mighty and shaped
    assert "#include" not in mighty
    assert "#include" not in shaped
    assert "#define BLOB_VARIANT_SHAPED 0" in mighty
    assert "#define BLOB_VARIANT_SHAPED 1" in shaped
    for source in (mighty, shaped):
        assert "float paint_drive" in source
        assert "u_transient_mid * 0.24" in source
        assert "core_reaction" in source
        assert "uniform int u_blob_shaper_enabled" not in source
        assert "float shaped_tendril_light" in source
        assert "shaped_tip_prominence * 5.2" in source
