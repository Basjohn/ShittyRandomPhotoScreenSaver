"""Descriptor-owned Visualizer CUSTOM geometry mechanics and layout routing."""
from __future__ import annotations


def test_registered_modes_separate_geometry_kind_from_layout_profile():
    from core.settings.visualizer_mode_registry import (
        VISUALIZER_MODE_IDS,
        get_visualizer_geometry_kind,
        get_visualizer_layout_profile,
    )

    kinds = {mode: get_visualizer_geometry_kind(mode) for mode in VISUALIZER_MODE_IDS}
    profiles = {mode: get_visualizer_layout_profile(mode) for mode in VISUALIZER_MODE_IDS}

    assert set(kinds.values()) <= {"planar", "freeform_3d"}
    assert {mode for mode, kind in kinds.items() if kind == "freeform_3d"} == {
        "sphere", "extruded_spectrum", "shockwave_grid",
    }
    assert {profile for mode, profile in profiles.items() if kinds[mode] == "planar"} == {"planar"}
    assert profiles["extruded_spectrum"] == "3d:extruded_spectrum"
    assert profiles["shockwave_grid"] == "3d:shockwave_grid"
    assert profiles["sphere"] == "3d:sphere"
    assert len({profiles[mode] for mode in ("extruded_spectrum", "shockwave_grid", "sphere")}) == 3


def test_layout_profile_is_compatibility_metadata_not_camera_state():
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

    extruded = get_visualizer_mode_descriptor("extruded_spectrum")
    shockwave = get_visualizer_mode_descriptor("shockwave_grid")
    sphere = get_visualizer_mode_descriptor("sphere")

    assert extruded.view_orbit_settings == (
        "extruded_spectrum_turn", "extruded_spectrum_tilt",
    )
    assert shockwave.view_orbit_settings == (
        "shockwave_grid_turn", "shockwave_grid_tilt",
    )
    # Sphere has the same persistent authored camera lane as the other 3D
    # modes; none of these view keys is a CUSTOM stage or a preset field.
    assert sphere.view_orbit_settings == ("sphere_turn", "sphere_tilt")
    assert extruded.layout_profile != shockwave.layout_profile
    assert all("turn" not in d.layout_profile and "tilt" not in d.layout_profile
               for d in (extruded, shockwave, sphere))


def test_view_pose_keys_are_explicitly_inert_when_curated_presets_are_applied():
    from core.settings.visualizer_presets import apply_preset_to_config, get_presets
    from core.settings.visualizer_mode_registry import get_visualizer_view_pose_keys

    for mode in ("extruded_spectrum", "shockwave_grid", "sphere"):
        turn, tilt = get_visualizer_view_pose_keys(mode)
        # 0.275 is valid for every registered 3D tilt range, including
        # Sphere's non-negative authored camera tilt.
        live = {turn: 0.741, tilt: 0.275, "mode": mode}
        for index, preset in enumerate(get_presets(mode)):
            if preset.is_custom:
                continue
            result = apply_preset_to_config(mode, index, live)
            assert result[turn] == 0.741
            assert result[tilt] == 0.275
