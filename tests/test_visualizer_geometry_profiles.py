"""Descriptor-owned Visualizer CUSTOM geometry profile routing."""
from __future__ import annotations


def test_registered_modes_resolve_one_of_the_two_canonical_geometry_profiles():
    from core.settings.visualizer_mode_registry import (
        VISUALIZER_MODE_IDS,
        get_visualizer_geometry_profile,
    )

    profiles = {
        mode_id: get_visualizer_geometry_profile(mode_id)
        for mode_id in VISUALIZER_MODE_IDS
    }
    assert set(profiles.values()) <= {"planar", "freeform_3d"}
    assert {
        mode_id for mode_id, profile in profiles.items()
        if profile == "freeform_3d"
    } == {"sphere", "extruded_spectrum", "shockwave_grid"}
