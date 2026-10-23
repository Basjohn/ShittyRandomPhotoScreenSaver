"""Surface fan control is not displayed for Deep Light (independent of coverage)."""

from core.settings.visualizer_mode_settings import require_mode_settings


def test_ray_fan_spread_requires_surface_light_and_enabled_rays():
    spec = require_mode_settings("extruded_bubble")
    reach = spec.control("extruded_bubble_ray_reach")
    conditions = reach.when
    assert ("extruded_bubble_rays_enabled", True) in conditions
    assert ("extruded_bubble_light_type", "Sunlit Surface") in conditions


def test_physical_coverage_is_independent_of_surface_fan_visibility():
    spec = require_mode_settings("extruded_bubble")
    reach = spec.control("extruded_bubble_ray_reach")
    assert not any(key == "extruded_bubble_lighting_coverage" for key, _ in reach.when)
    assert spec.control("extruded_bubble_beam_width").when != reach.when


def test_ray_fan_spread_visibility_truth_table():
    spec = require_mode_settings("extruded_bubble")
    for surface in (True, False):
        for rays in (True, False):
            for coverage in ("BEAM", "SCENE"):
                settings = {
                    "extruded_bubble_light_type": "Sunlit Surface" if surface else "Deep Light",
                    "extruded_bubble_rays_enabled": rays,
                    "extruded_bubble_lighting_coverage": coverage,
                }
                conditions = spec.control("extruded_bubble_ray_reach").when
                visible = all(settings[key] == expected for key, expected in conditions)
                assert visible is (surface and rays)
