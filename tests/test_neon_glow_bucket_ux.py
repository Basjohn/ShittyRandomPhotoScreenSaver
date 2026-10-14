"""Pure Neon Settings regrouping contract: controls move, not their owners or values."""

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.visualizer_mode_settings import require_mode_settings, Slider, Toggle, Colour


def _terms(conditions):
    return (conditions,) if isinstance(conditions[0], str) else conditions


def test_neon_buckets_group_existing_glow_wave_and_material_controls():
    spec = require_mode_settings("shockwave_grid")
    controls = {entry.key: entry for entry in spec.controls}
    expected = {
        "glow": (
            "glow", "horizon", "celestial_glow_enabled", "celestial_glow_strength",
            "celestial_glow_reactivity", "sun_rays_enabled", "sun_rays_strength",
            "sun_rays_color", "starscape_beat", "star_glow_strength", "star_glow_reactivity",
        ),
        "waves": ("water_detail", "wave_height", "wave_speed", "terrain_reactivity", "scroll", "idle"),
        "render": ("wire_display", "glass_tint", "glass_strength", "glass_roughness",
                   "vertex_color", "vertex_accent_color", "vertex_outline_color", "density",
                   "water_reflection", "floor"),
    }
    for bucket, suffixes in expected.items():
        assert [entry.key for entry in spec.controls if entry.bucket == bucket] == [
            "shockwave_grid_" + suffix for suffix in suffixes
        ]
    assert set(controls) == set(spec.keys()) and len(controls) == len(spec.keys())
    assert {entry.key for entry in spec.controls if entry.bucket == "sky"} == {
        "shockwave_grid_sky_enabled", "shockwave_grid_sky_strength", "shockwave_grid_sky_color",
        "shockwave_grid_star_color", "shockwave_grid_cloud_color", "shockwave_grid_horizon_color",
    }
    assert {entry.key for entry in spec.controls if entry.bucket == "celestial"} == {
        "shockwave_grid_sun_enabled", "shockwave_grid_sun_mode", "shockwave_grid_sun_color",
        "shockwave_grid_moon_color", "shockwave_grid_moon_phase", "shockwave_grid_sun_x",
        "shockwave_grid_sun_y", "shockwave_grid_sun_z", "shockwave_grid_sun_size",
        "shockwave_grid_sun_orbit_enabled", "shockwave_grid_sun_orbit_speed",
    }
    defaults = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    assert all(key in defaults for key in controls)
    assert DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"]["shockwave_grid:glow"] is False
    assert isinstance(controls["shockwave_grid_starscape_beat"], Toggle)
    assert isinstance(controls["shockwave_grid_sun_rays_color"], Colour)
    assert isinstance(controls["shockwave_grid_horizon"], Slider)
    assert spec.bucket("terrain_motion").title == "Growth Timing"


def test_visibility_requires_all_parents_without_changing_stored_controls():
    spec = require_mode_settings("shockwave_grid")
    expected = {
        "celestial_glow_enabled": (("shockwave_grid_sun_enabled", True),),
        "celestial_glow_strength": (("shockwave_grid_sun_enabled", True), ("shockwave_grid_celestial_glow_enabled", True)),
        "celestial_glow_reactivity": (("shockwave_grid_sun_enabled", True), ("shockwave_grid_celestial_glow_enabled", True)),
        "sun_rays_enabled": (("shockwave_grid_sun_enabled", True),),
        "sun_rays_strength": (("shockwave_grid_sun_enabled", True), ("shockwave_grid_sun_rays_enabled", True)),
        "sun_rays_color": (("shockwave_grid_sun_enabled", True), ("shockwave_grid_sun_rays_enabled", True)),
        "starscape_beat": (("shockwave_grid_sky_enabled", True),),
        "star_glow_strength": (("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True)),
        "star_glow_reactivity": (("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True)),
    }
    for suffix, pairs in expected.items():
        control = spec.control("shockwave_grid_" + suffix)
        assert _terms(control.when) == pairs
        for key, _ in pairs:
            assert key in spec.keys()  # no shadow owner or unresolved condition
    assert all(key in spec.keys() for key in (
        "shockwave_grid_glow", "shockwave_grid_horizon", "shockwave_grid_water_reflection"
    ))
    for suffix in ("celestial_glow_strength", "sun_rays_strength", "sun_rays_color",
                   "star_glow_strength", "star_glow_reactivity"):
        assert spec.control("shockwave_grid_" + suffix).enabled_when
