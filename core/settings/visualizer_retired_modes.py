"""Forward-only cleanup for retired visualizer modes."""
from __future__ import annotations

from typing import Any, Dict, Mapping


RETIRED_VISUALIZER_MODE_IDS = frozenset({"blob"})
_RETIRED_VISUALIZER_KEYS = frozenset({
    "shockwave_grid_allow_overflow",  # Neon Lake Basin is always inside its bordered card.
    "shockwave_grid_terrain_reactivity",  # Growth; superseded by the Terrain Reaction bucket (2026-10-16).
    "preset_blob",
    # Rejected smooth-Sphere representation controls. The experimental mode
    # survives as Voxel Sphere, but these owned keys do not.
    "sphere_antialiasing",
    "sphere_shadow_strength",
    "sphere_rainbow_enabled",
    "sphere_rainbow_speed",
    # Rejected Voxel-Sphere history effect; superseded by no effect, not shared Rainbow.
    "sphere_rainbow_ghosting",
    "sphere_idle_motion",
    "sphere_surface_detail",
    "sphere_bass_response",
    "sphere_mid_response",
    "sphere_high_response",
    "sphere_energy_curve",
    # Superseded accepted-Voxel-Sphere response controls. Normal migration first
    # maps these to Fragment Strength + Particle Distance; this retired-key seam
    # then guarantees no old authority survives in canonical state.
    "sphere_deformation",
    "sphere_bump_reactivity",
    # The Oscilloscope before its 2026-10-11 rework (six fixed lines, line ghosting, the shared
    # Rainbow and bar colours it never drew, the old width reaction and the analysis controls it no
    # longer consumes). The rework's keys are all new names, so nothing of the old look survives.
    "osc_ghost_decay", "osc_ghost_intensity", "osc_ghosting_enabled",
    "osc_ghost_line2_enabled", "osc_ghost_line3_enabled", "osc_ghost_line4_enabled",
    "osc_ghost_line5_enabled", "osc_ghost_line6_enabled",
    "osc_glow_color", "osc_glow_enabled", "osc_glow_intensity", "osc_glow_reactivity", "osc_reactive_glow",
    "osc_line_color", "osc_line2_color", "osc_line3_color", "osc_line4_color", "osc_line5_color",
    "osc_line6_color", "osc_line2_glow_color", "osc_line3_glow_color", "osc_line4_glow_color",
    "osc_line5_glow_color", "osc_line6_glow_color",
    "osc_line_amplitude", "osc_line_count", "osc_line_dim", "osc_line_offset_bias", "osc_smoothing",
    "osc_speed", "osc_vertical_shift",
    "oscilloscope_agc_strength", "oscilloscope_bar_border_color", "oscilloscope_bar_border_opacity",
    "oscilloscope_bar_fill_color", "oscilloscope_dynamic_range_enabled", "oscilloscope_kick_lane_gain",
    "oscilloscope_rainbow_enabled", "oscilloscope_rainbow_speed", "oscilloscope_transient_pulse_gain",
    "oscilloscope_transient_width_mix", "osc_sensitivity", "oscilloscope_transient_clamp",
    # Spectrum fill/border link state: serialized but never read by any UI or
    # renderer; Fill and Border stay independent controls (2026-10-24, SC3).
    "spectrum_link_fill_border",
})
_RETIRED_VISUALIZER_PREFIXES = ("blob_",)


def strip_retired_visualizer_settings(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, Any]:
    """Migrate retired selections and remove their owned settings.

    Both section-local and dotted mappings pass through this helper during
    settings, import, preset, and generated-default normalization.
    """
    if not isinstance(data, Mapping):
        return {}

    cleaned: Dict[str, Any] = {}
    dotted_prefix = f"{prefix}."
    for key, value in data.items():
        key_text = str(key)
        leaf = key_text[len(dotted_prefix):] if key_text.startswith(dotted_prefix) else key_text
        if leaf in _RETIRED_VISUALIZER_KEYS or leaf.startswith(_RETIRED_VISUALIZER_PREFIXES):
            continue
        if leaf == "mode" and str(value or "").strip().lower() in RETIRED_VISUALIZER_MODE_IDS:
            from core.settings.visualizer_mode_registry import get_default_visualizer_mode_id

            cleaned[key] = get_default_visualizer_mode_id()
            continue
        cleaned[key] = value
    return cleaned
