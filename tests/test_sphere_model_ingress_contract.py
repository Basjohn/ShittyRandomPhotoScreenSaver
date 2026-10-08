"""Regression: Sphere view-pose conversion must not poison global Settings or preset imports.

R-121 accidentally used numeric (min, max) tuples as the coercers in the
Sphere build/serialize tables. Canonical defaults crashed during import, and
preset loader's per-file exception handling produced a misleading
"spectrum has no authored presets" error for unrelated curated families.
"""
from __future__ import annotations

import pytest


def test_sphere_conversion_specs_are_functions_not_range_tuples():
    from core.settings.models._spotify_visualizer import (
        _SPHERE_BUILD_SPECS, _SPHERE_SERIALIZERS,
    )

    for table in (_SPHERE_BUILD_SPECS, _SPHERE_SERIALIZERS):
        assert table['sphere_turn'] is float
        assert table['sphere_tilt'] is float
        assert all(callable(converter) for converter in table.values())


def test_canonical_startup_ingests_sphere_view_pose_and_clamps_range():
    from core.settings.defaults import get_default_settings
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

    original = get_default_settings('Screensaver')['widgets']['spotify_visualizer']
    assert isinstance(original['sphere_turn'], float)
    assert isinstance(original['sphere_tilt'], float)

    authored = normalize_visualizer_section_mapping(
        {**original, 'sphere_turn': 0.42, 'sphere_tilt': 0.75},
        apply_preset_overlay=False,
    )
    assert authored['sphere_turn'] == pytest.approx(0.42)
    assert authored['sphere_tilt'] == pytest.approx(0.75)

    invalid = normalize_visualizer_section_mapping(
        {**original, 'sphere_turn': 5.0, 'sphere_tilt': -5.0},
        apply_preset_overlay=False,
    )
    assert invalid['sphere_turn'] == pytest.approx(1.0)
    assert invalid['sphere_tilt'] == pytest.approx(0.0)


def test_all_curated_catalogues_survive_sphere_settings_startup():
    from core.settings.defaults import get_default_settings
    from core.settings.visualizer_presets import get_presets

    assert get_default_settings('Screensaver')['widgets']['spotify_visualizer']
    # Preset import performs whole-mode normalization. A Sphere model error
    # must never make Spectrum, Extruded or Shockwave appear to be empty.
    for mode in ('spectrum', 'extruded_spectrum', 'shockwave_grid', 'sphere'):
        presets = get_presets(mode)
        assert any(not preset.is_custom for preset in presets), mode
        assert presets[-1].is_custom
