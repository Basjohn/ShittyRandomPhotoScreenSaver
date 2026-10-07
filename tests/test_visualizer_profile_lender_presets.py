"""3D Spectrum-family profiles are promoted once and then resolve independently."""
from __future__ import annotations

from copy import deepcopy

import pytest

from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_profile_lender_modes,
    get_visualizer_mode_descriptor,
)
from core.settings.visualizer_presets import apply_preset_to_config
from core.settings.visualizer_settings_contract import migrate_profile_lender_owned_settings
from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config
from widgets.spotify_visualizer.technical_config import build_technical_cache, resolve_technical_config


_SOURCE_SUFFIXES = (
    "mirrored",
    "shape_nodes",
    "notch_positions_mirrored",
    "notch_positions_linear",
    "lane_strengths_mirrored",
    "lane_strengths_linear",
    "wave_amplitude",
    "profile_floor",
    "drop_speed",
)


def test_3d_modes_own_profiles_and_keep_only_spheres_preserved_raw_reference() -> None:
    assert get_profile_lender_modes("extruded_spectrum") == ()
    assert get_profile_lender_modes("shockwave_grid") == ()
    for mode in ("extruded_spectrum", "shockwave_grid"):
        descriptor = get_visualizer_mode_descriptor(mode)
        assert descriptor.technical_controls and descriptor.spectrum_shape_controls
        assert descriptor.profile_migration_source_mode == "spectrum"
    sphere = get_visualizer_mode_descriptor("sphere")
    assert sphere.technical_profile_mode == "spectrum" and get_profile_lender_modes("sphere") == ()


@pytest.mark.parametrize("mode", ("extruded_spectrum", "shockwave_grid"))
def test_missing_3d_profile_keys_copy_the_selected_spectrum_preset_once(mode: str) -> None:
    source_index = 1
    input_config = {"preset_spectrum": source_index, "mode": mode}
    migrated = migrate_profile_lender_owned_settings(input_config)
    source = apply_preset_to_config("spectrum", source_index, dict(input_config))

    for suffix in ("bar_count", "sensitivity", *_SOURCE_SUFFIXES):
        assert migrated[f"{mode}_{suffix}"] == source[f"spectrum_{suffix}"]
    if mode == "extruded_spectrum":
        for suffix in ("bar_border_color", "bar_border_opacity", "ghosting_enabled"):
            assert migrated[f"{mode}_{suffix}"] == source[f"spectrum_{suffix}"]
        assert migrated[f"{mode}_bar_fill_color"] == [
            *source["spectrum_bar_fill_color"][:3],
            255,
        ]

    # The migration result is a persisted owner. A later Spectrum selection
    # cannot alter it through a hidden lender route.
    changed_source = deepcopy(migrated)
    changed_source["preset_spectrum"] = 0
    model = SpotifyVisualizerSettings.from_mapping(
        changed_source, apply_preset_overlay=False, resolve_preset_indices=False
    )
    technical = resolve_technical_config(build_technical_cache(None, model), mode)
    assert technical["bar_count"] == migrated[f"{mode}_bar_count"]
    assert technical["sensitivity"] == pytest.approx(migrated[f"{mode}_sensitivity"])


@pytest.mark.parametrize("mode", ("extruded_spectrum", "shockwave_grid"))
def test_owned_source_profile_projects_to_the_single_shared_dsp_seam(mode: str) -> None:
    model = SpotifyVisualizerSettings.from_mapping(
        {
            "mode": mode,
            f"{mode}_mirrored": False,
            f"{mode}_wave_amplitude": 0.37,
            f"{mode}_profile_floor": 0.19,
            f"{mode}_drop_speed": 2.2,
        },
        apply_preset_overlay=False,
        resolve_preset_indices=False,
    )
    owned = {
        f"{mode}_{suffix}": getattr(model, f"{mode}_{suffix}")
        for suffix in _SOURCE_SUFFIXES
    }
    resolved = resolve_mode_source_config(mode, owned)
    for suffix in _SOURCE_SUFFIXES:
        assert resolved[f"spectrum_{suffix}"] == owned[f"{mode}_{suffix}"]
    if mode == "shockwave_grid":
        assert "spectrum_ghost_alpha" not in resolved


def test_extruded_projection_carries_its_owned_bar_and_ghost_values_to_consumers() -> None:
    model = SpotifyVisualizerSettings.from_mapping(
        {
            "mode": "extruded_spectrum",
            "extruded_spectrum_bar_fill_color": [17, 34, 51, 128],
            "extruded_spectrum_bar_border_color": [220, 210, 200, 255],
            "extruded_spectrum_bar_border_opacity": 0.37,
            "extruded_spectrum_ghosting_enabled": True,
            "extruded_spectrum_ghost_alpha": 0.29,
            "extruded_spectrum_ghost_decay": 0.64,
        },
        apply_preset_overlay=False,
        resolve_preset_indices=False,
    )
    resolved = resolve_mode_source_config(
        "extruded_spectrum",
        {
            "extruded_spectrum_bar_fill_color": model.extruded_spectrum_bar_fill_color,
            "extruded_spectrum_bar_border_color": model.extruded_spectrum_bar_border_color,
            "extruded_spectrum_bar_border_opacity": model.extruded_spectrum_bar_border_opacity,
            "extruded_spectrum_ghosting_enabled": model.extruded_spectrum_ghosting_enabled,
            "extruded_spectrum_ghost_alpha": model.extruded_spectrum_ghost_alpha,
            "extruded_spectrum_ghost_decay": model.extruded_spectrum_ghost_decay,
        },
    )
    assert resolved["bar_fill_color"] == [17, 34, 51, 128]
    assert resolved["bar_border_color"] == [220, 210, 200, 255]
    assert resolved["bar_border_opacity"] == pytest.approx(0.37)
    assert resolved["spectrum_ghosting_enabled"] is True
    assert resolved["spectrum_ghost_alpha"] == pytest.approx(0.29)
    assert resolved["spectrum_ghost_decay"] == pytest.approx(0.64)


def test_runtime_profile_resolution_has_no_other_mode_lenders() -> None:
    assert all(
        not get_profile_lender_modes(mode)
        for mode in VISUALIZER_MODE_IDS
        if mode != "sphere"
    )
    # This model-level assertion catches a descriptor edit that changes routing
    # without updating cache construction.
    model = SpotifyVisualizerSettings.from_mapping({"mode": "extruded_spectrum"})
    assert resolve_technical_config(build_technical_cache(None, model), "extruded_spectrum")["bar_count"] == (
        model.extruded_spectrum_bar_count
    )


def test_legacy_extruded_fill_promotion_keeps_the_pre_alpha_body_opaque() -> None:
    legacy = SpotifyVisualizerSettings.from_mapping(
        {"bar_fill_color": [17, 34, 51, 230]}, apply_preset_overlay=False
    )
    explicit = SpotifyVisualizerSettings.from_mapping(
        {"extruded_spectrum_bar_fill_color": [17, 34, 51, 230]},
        apply_preset_overlay=False,
    )
    assert legacy.extruded_spectrum_bar_fill_color == [17, 34, 51, 255]
    assert explicit.extruded_spectrum_bar_fill_color == [17, 34, 51, 230]
