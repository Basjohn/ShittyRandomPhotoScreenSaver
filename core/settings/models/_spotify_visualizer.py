"""Spotify visualizer settings model and per-mode helper functions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Tuple, TYPE_CHECKING

from core.settings.bubble_gradient_semantics import (
    CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION,
    get_bubble_gradient_semantics_version,
    normalize_bubble_specular_direction,
    resolve_bubble_gradient_direction,
)
from core.settings.visualizer_mode_registry import (
    coerce_visualizer_mode_id,
    get_preset_key,
    get_setting_prefixes,
    VISUALIZER_MODE_IDS,
)
from core.settings.visualizer_preset_indices import (
    get_missing_preset_fallback_index,
    resolve_all_preset_indices_from_getter,
    resolve_all_preset_indices_from_mapping,
    resolve_preset_index_from_mapping,
)
from core.settings.visualizer_settings_contract import (
    migrate_legacy_global_technical_keys,
    migrate_legacy_global_visual_keys,
    PER_MODE_BASELINE_KEYS,
    SPECIAL_PER_MODE_KEYS,
    resolve_visualizer_active_mode_rainbow_state,
    resolve_spectrum_render_mode,
    resolve_spectrum_unique_colors,
)
from core.settings.models._visualizer_helpers import (
    _normalize_visualizer_direction,
    _normalize_spectrum_linear_notches,
    _normalize_spectrum_lane_strengths,
    _SPECTRUM_DEFAULT_NOTCHES_LINEAR,
    _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED,
    _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR,
    PER_MODE_TECHNICAL_MODES,
    _ACTIVE_MODE_TECHNICAL_KEYS,
    _ACTIVE_MODE_SHARED_VISUAL_KEYS,
    _coerce_live_visualizer_bool,
    _coerce_live_visualizer_int,
    _coerce_live_visualizer_float,
    _build_live_visualizer_mode_kwargs,
    _build_live_visualizer_mode_shared_visual_kwargs,
    _resolve_active_mode_technical_state,
    _resolve_active_mode_shared_visual_state,
)

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager


def _build_visualizer_model_kwargs(
    read_value: Callable[[str, Any], Any],
    *,
    active_mode: str,
    bubble_gradient_semantics_version: int,
    active_technical: Mapping[str, Any],
    active_visuals: Mapping[str, Any],
    rainbow_kwargs: Mapping[str, Any],
    preset_kwargs: Mapping[str, Any],
    bubble_stream_constant_speed_default: float,
    bubble_stream_speed_cap_default: float,
    ) -> Dict[str, Any]:
    """Build the shared constructor payload for visualizer ingestion paths."""

    return {
        "enabled": read_value("enabled", False),
        "visualizers_enabled": read_value("visualizers_enabled", True),
        "monitor": read_value("monitor", "ALL"),
        "bar_count": int(active_technical["bar_count"]),
        "ghosting_enabled": bool(read_value("spectrum_ghosting_enabled", True)),
        "ghost_alpha": float(read_value("spectrum_ghost_alpha", 0.4)),
        "ghost_decay": float(read_value("spectrum_ghost_decay", 0.35)),
        "adaptive_sensitivity": bool(active_technical["adaptive_sensitivity"]),
        "sensitivity": float(active_technical["sensitivity"]),
        "dynamic_floor": bool(active_technical["dynamic_floor"]),
        "manual_floor": float(active_technical["manual_floor"]),
        "dynamic_range_enabled": bool(active_technical["dynamic_range_enabled"]),
        "agc_strength": float(active_technical["agc_strength"]),
        "input_gain": float(active_technical["input_gain"]),
        "kick_lane_gain": float(active_technical["kick_lane_gain"]),
        "transient_pulse_gain": float(active_technical["transient_pulse_gain"]),
        "transient_clamp": float(active_technical["transient_clamp"]),
        "bar_fill_color": active_visuals["bar_fill_color"],
        "bar_border_color": active_visuals["bar_border_color"],
        "bar_border_opacity": float(active_visuals["bar_border_opacity"]),
        "mode": active_mode,
        "osc_glow_enabled": read_value("osc_glow_enabled", True),
        "osc_glow_intensity": float(read_value("osc_glow_intensity", 0.5)),
        "osc_glow_reactivity": float(read_value("osc_glow_reactivity", read_value("osc_glow_size", 1.0))),
        "osc_glow_color": read_value("osc_glow_color", [0, 200, 255, 230]),
        "osc_reactive_glow": read_value("osc_reactive_glow", True),
        "osc_line_amplitude": float(read_value("osc_line_amplitude", 3.0)),
        "osc_smoothing": float(read_value("osc_smoothing", 0.7)),
        "blob_color": read_value("blob_color", [0, 180, 255, 230]),
        "blob_glow_color": read_value("blob_glow_color", [0, 140, 255, 180]),
        "blob_edge_color": read_value("blob_edge_color", [100, 220, 255, 230]),
        "blob_outline_color": read_value("blob_outline_color", [0, 0, 0, 0]),
        "blob_pulse": float(read_value("blob_pulse", 1.0)),
        "blob_pulse_release_ms": int(read_value("blob_pulse_release_ms", 220)),
        "blob_width": float(read_value("blob_width", 1.0)),
        "blob_size": float(read_value("blob_size", 1.0)),
        "blob_glow_intensity": float(read_value("blob_glow_intensity", 0.5)),
        "blob_reactive_glow": read_value("blob_reactive_glow", True),
        "blob_glow_drive_mode": str(read_value("blob_glow_drive_mode", "bass")),
        "osc_line_color": read_value("osc_line_color", [255, 255, 255, 255]),
        "osc_line_count": int(read_value("osc_line_count", 1)),
        "osc_line2_color": read_value("osc_line2_color", [255, 120, 50, 230]),
        "osc_line2_glow_color": read_value("osc_line2_glow_color", [255, 120, 50, 180]),
        "osc_line3_color": read_value("osc_line3_color", [50, 255, 120, 230]),
        "osc_line3_glow_color": read_value("osc_line3_glow_color", [50, 255, 120, 180]),
        "osc_line4_color": read_value("osc_line4_color", [255, 0, 150, 230]),
        "osc_line4_glow_color": read_value("osc_line4_glow_color", [255, 0, 150, 180]),
        "osc_line5_color": read_value("osc_line5_color", [0, 255, 200, 230]),
        "osc_line5_glow_color": read_value("osc_line5_glow_color", [0, 255, 200, 180]),
        "osc_line6_color": read_value("osc_line6_color", [200, 100, 255, 230]),
        "osc_line6_glow_color": read_value("osc_line6_glow_color", [200, 100, 255, 180]),
        "spectrum_growth": float(read_value("spectrum_growth", 1.0)),
        "blob_growth": float(read_value("blob_growth", 2.5)),
        "osc_speed": float(read_value("osc_speed", 1.0)),
        "osc_line_dim": read_value("osc_line_dim", False),
        "osc_line_offset_bias": float(read_value("osc_line_offset_bias", 0.0)),
        "osc_vertical_shift": int(read_value("osc_vertical_shift", 0)),
        "osc_growth": float(read_value("osc_growth", 1.0)),
        "blob_reactive_deformation": float(read_value("blob_reactive_deformation", 1.0)),
        "blob_constant_wobble": float(read_value("blob_constant_wobble", 1.0)),
        "blob_reactive_wobble": float(read_value("blob_reactive_wobble", 1.0)),
        "blob_stretch": float(read_value("blob_stretch", 0.35)),
        "blob_stage_gain": float(read_value("blob_stage_gain", 1.0)),
        "blob_core_scale": float(read_value("blob_core_scale", 1.0)),
        "blob_core_floor_bias": float(read_value("blob_core_floor_bias", 0.35)),
        "blob_stage_bias": float(read_value("blob_stage_bias", 0.0)),
        "blob_stretch_tendency": float(read_value("blob_stretch_tendency", read_value("blob_stretch", 0.35))),
        "blob_stretch_inner": float(read_value("blob_stretch_inner", 0.0)),
        "blob_stretch_outer": float(read_value("blob_stretch_outer", read_value("blob_stretch", 0.35))),
        "spectrum_render_mode": resolve_spectrum_render_mode(read_value),
        "spectrum_unique_colors": resolve_spectrum_unique_colors(read_value),
        "spectrum_rainbow_border": bool(read_value("spectrum_rainbow_border", False)),
        "spectrum_border_radius": float(read_value("spectrum_border_radius", 0.0)),
        "spectrum_link_fill_border": bool(read_value("spectrum_link_fill_border", False)),
        "spectrum_glow_enabled": bool(read_value("spectrum_glow_enabled", False)),
        "spectrum_glow_intensity": float(read_value("spectrum_glow_intensity", 0.55)),
        "spectrum_glow_color": list(read_value("spectrum_glow_color", [110, 220, 255, 235])),
        "spectrum_ghosting_enabled": bool(read_value("spectrum_ghosting_enabled", True)),
        "spectrum_ghost_alpha": float(read_value("spectrum_ghost_alpha", 0.4)),
        "spectrum_ghost_decay": float(read_value("spectrum_ghost_decay", 0.35)),
        "spectrum_mirrored": bool(read_value("spectrum_mirrored", True)),
        "spectrum_shape_nodes": list(read_value("spectrum_shape_nodes", [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]])),
        "spectrum_notch_positions_mirrored": list(read_value("spectrum_notch_positions_mirrored", [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]])),
        "spectrum_notch_positions_linear": _normalize_spectrum_linear_notches(
            read_value("spectrum_notch_positions_linear", _SPECTRUM_DEFAULT_NOTCHES_LINEAR)
        ),
        "spectrum_lane_strengths_mirrored": _normalize_spectrum_lane_strengths(
            read_value("spectrum_lane_strengths_mirrored", _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED),
            _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED,
        ),
        "spectrum_lane_strengths_linear": _normalize_spectrum_lane_strengths(
            read_value("spectrum_lane_strengths_linear", _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR),
            _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR,
        ),
        "spectrum_wave_amplitude": float(read_value("spectrum_wave_amplitude", 0.50)),
        "spectrum_profile_floor": float(read_value("spectrum_profile_floor", 0.12)),
        "spectrum_drop_speed": float(read_value("spectrum_drop_speed", 1.0)),
        "sine_wave_growth": float(read_value("sine_wave_growth", 1.0)),
        "sine_wave_travel": int(read_value("sine_wave_travel", 0)),
        "sine_density": float(read_value("sine_density", 1.0)),
        "sine_displacement": float(read_value("sine_displacement", 0.0)),
        "sine_glow_enabled": read_value("sine_glow_enabled", True),
        "sine_glow_intensity": float(read_value("sine_glow_intensity", 0.5)),
        "sine_glow_reactivity": float(read_value("sine_glow_reactivity", read_value("sine_glow_size", 1.0))),
        "sine_glow_color": read_value("sine_glow_color", [0, 200, 255, 230]),
        "sine_line_color": read_value("sine_line_color", [255, 255, 255, 255]),
        "sine_reactive_glow": read_value("sine_reactive_glow", True),
        "sine_ghosting_enabled": read_value("sine_ghosting_enabled", True),
        "sine_ghost_alpha": float(read_value("sine_ghost_alpha", 0.45)),
        "sine_ghost_decay": float(read_value("sine_ghost_decay", 0.3)),
        "sine_ghost_line2_enabled": bool(read_value("sine_ghost_line2_enabled", True)),
        "sine_ghost_line3_enabled": bool(read_value("sine_ghost_line3_enabled", True)),
        "sine_ghost_line4_enabled": bool(read_value("sine_ghost_line4_enabled", True)),
        "sine_ghost_line5_enabled": bool(read_value("sine_ghost_line5_enabled", True)),
        "sine_ghost_line6_enabled": bool(read_value("sine_ghost_line6_enabled", True)),
        "sine_sensitivity": float(read_value("sine_sensitivity", 1.0)),
        "sine_smoothing": float(read_value("sine_smoothing", 0.7)),
        "sine_speed": float(read_value("sine_speed", 1.0)),
        "sine_line_count": int(read_value("sine_line_count", 1)),
        "sine_line_offset_bias": float(read_value("sine_line_offset_bias", 0.0)),
        "sine_line2_color": read_value("sine_line2_color", [255, 255, 255, 230]),
        "sine_line2_glow_color": read_value("sine_line2_glow_color", [7, 114, 255, 180]),
        "sine_line3_color": read_value("sine_line3_color", [255, 255, 255, 230]),
        "sine_line3_glow_color": read_value("sine_line3_glow_color", [14, 159, 255, 180]),
        "sine_line4_color": read_value("sine_line4_color", [255, 120, 50, 230]),
        "sine_line4_glow_color": read_value("sine_line4_glow_color", [255, 120, 50, 180]),
        "sine_line5_color": read_value("sine_line5_color", [50, 255, 120, 230]),
        "sine_line5_glow_color": read_value("sine_line5_glow_color", [50, 255, 120, 180]),
        "sine_line6_color": read_value("sine_line6_color", [255, 0, 150, 230]),
        "sine_line6_glow_color": read_value("sine_line6_glow_color", [255, 0, 150, 180]),
        "sine_travel_line2": int(read_value("sine_travel_line2", 0)),
        "sine_travel_line3": int(read_value("sine_travel_line3", 0)),
        "sine_travel_line4": int(read_value("sine_travel_line4", 0)),
        "sine_travel_line5": int(read_value("sine_travel_line5", 0)),
        "sine_travel_line6": int(read_value("sine_travel_line6", 0)),
        "sine_line1_shift": float(read_value("sine_line1_shift", 0.0)),
        "sine_line2_shift": float(read_value("sine_line2_shift", 0.0)),
        "sine_line3_shift": float(read_value("sine_line3_shift", 0.0)),
        "sine_line4_shift": float(read_value("sine_line4_shift", 0.0)),
        "sine_line5_shift": float(read_value("sine_line5_shift", 0.0)),
        "sine_line6_shift": float(read_value("sine_line6_shift", 0.0)),
        "sine_wave_effect": float(read_value("sine_wave_effect", read_value("sine_wobble_amount", 0.0))),
        "sine_vertical_shift": int(read_value("sine_vertical_shift", 0)),
        "sine_card_adaptation": float(read_value("sine_card_adaptation", 0.3)),
        "sine_micro_wobble": float(read_value("sine_micro_wobble", 0.0)),
        "sine_crawl_amount": float(read_value("sine_crawl_amount", 0.25)),
        "sine_width_reaction": float(read_value("sine_width_reaction", 0.0)),
        "rainbow_enabled": rainbow_kwargs["rainbow_enabled"],
        "rainbow_speed": rainbow_kwargs["rainbow_speed"],
        "osc_ghosting_enabled": bool(read_value("osc_ghosting_enabled", False)),
        "osc_ghost_intensity": float(read_value("osc_ghost_intensity", 0.4)),
        "osc_ghost_line2_enabled": bool(read_value("osc_ghost_line2_enabled", True)),
        "osc_ghost_line3_enabled": bool(read_value("osc_ghost_line3_enabled", True)),
        "osc_ghost_line4_enabled": bool(read_value("osc_ghost_line4_enabled", True)),
        "osc_ghost_line5_enabled": bool(read_value("osc_ghost_line5_enabled", True)),
        "osc_ghost_line6_enabled": bool(read_value("osc_ghost_line6_enabled", True)),
        "sine_heartbeat": float(read_value("sine_heartbeat", 0.0)),
        "bubble_big_bass_pulse": float(read_value("bubble_big_bass_pulse", 0.5)),
        "bubble_small_freq_pulse": float(read_value("bubble_small_freq_pulse", 0.5)),
        "bubble_stream_direction": str(read_value("bubble_stream_direction", "up")),
        "bubble_stream_constant_speed": float(read_value("bubble_stream_constant_speed", read_value("bubble_stream_speed", bubble_stream_constant_speed_default))),
        "bubble_stream_speed_cap": float(read_value("bubble_stream_speed_cap", read_value("bubble_stream_speed", bubble_stream_speed_cap_default))),
        "bubble_stream_reactivity": float(read_value("bubble_stream_reactivity", 0.5)),
        "bubble_rotation_amount": float(read_value("bubble_rotation_amount", 0.5)),
        "bubble_drift_amount": float(read_value("bubble_drift_amount", 0.5)),
        "bubble_drift_speed": float(read_value("bubble_drift_speed", 0.5)),
        "bubble_drift_frequency": float(read_value("bubble_drift_frequency", 0.5)),
        "bubble_drift_direction": str(read_value("bubble_drift_direction", "random")),
        "bubble_big_count": int(read_value("bubble_big_count", 8)),
        "bubble_small_count": int(read_value("bubble_small_count", 25)),
        "bubble_surface_reach": float(read_value("bubble_surface_reach", 0.6)),
        "bubble_bounce_big_pct": int(read_value("bubble_bounce_big_pct", 70)),
        "bubble_bounce_small_pct": int(read_value("bubble_bounce_small_pct", 30)),
        "bubble_bounce_big_speed": float(read_value("bubble_bounce_big_speed", 0.8)),
        "bubble_bounce_small_speed": float(read_value("bubble_bounce_small_speed", 0.5)),
        "bubble_bounce_same_only": bool(read_value("bubble_bounce_same_only", False)),
        "bubble_collision_pop_mode": str(read_value("bubble_collision_pop_mode", "off")).strip().lower(),
        "bubble_outline_color": read_value("bubble_outline_color", [255, 255, 255, 230]),
        "bubble_specular_color": read_value("bubble_specular_color", [255, 255, 255, 255]),
        "bubble_gradient_light": read_value("bubble_gradient_light", [210, 170, 120, 255]),
        "bubble_gradient_dark": read_value("bubble_gradient_dark", [80, 60, 50, 255]),
        "bubble_pop_color": read_value("bubble_pop_color", [255, 255, 255, 180]),
        "bubble_specular_direction": normalize_bubble_specular_direction(read_value("bubble_specular_direction", "top_left")),
        "bubble_gradient_direction": resolve_bubble_gradient_direction(
            read_value("bubble_gradient_direction", "top"),
            semantics_version=bubble_gradient_semantics_version,
            default="top",
        ),
        "bubble_big_size_max": float(read_value("bubble_big_size_max", 0.038)),
        "bubble_small_size_max": float(read_value("bubble_small_size_max", 0.018)),
        "bubble_big_contraction_bias": float(read_value("bubble_big_contraction_bias", 1.0)),
        "bubble_big_size_clamp": float(read_value("bubble_big_size_clamp", 4.0)),
        "bubble_big_specular_max_size": float(read_value("bubble_big_specular_max_size", 2.5)),
        "bubble_growth": float(read_value("bubble_growth", 3.0)),
        "devcurve_growth": float(read_value("devcurve_growth", 3.0)),
        "bubble_trail_strength": float(read_value("bubble_trail_strength", 0.0)),
        "bubble_tail_opacity": float(read_value("bubble_tail_opacity", 0.0)),
        "bubble_ghosting_enabled": bool(read_value("bubble_ghosting_enabled", False)),
        "bubble_ghost_alpha": float(read_value("bubble_ghost_alpha", 0.0)),
        "bubble_ghost_decay": float(read_value("bubble_ghost_decay", 0.4)),
        "blob_glow_reactivity": float(read_value("blob_glow_reactivity", 1.0)),
        "blob_glow_max_size": float(read_value("blob_glow_max_size", 1.0)),
        "blob_ghosting_enabled": bool(read_value("blob_ghosting_enabled", False)),
        "blob_ghost_alpha": float(read_value("blob_ghost_alpha", 0.4)),
        "blob_ghost_decay": float(read_value("blob_ghost_decay", 0.3)),
        "blob_shaper_enabled": bool(read_value("blob_shaper_enabled", False)),
        "blob_shape_base_nodes": list(read_value("blob_shape_base_nodes", [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])),
        "blob_shape_reaction_nodes": list(read_value("blob_shape_reaction_nodes", [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])),
        "blob_shape_energy_nodes": list(read_value("blob_shape_energy_nodes", [])),
        "blob_shaper_base_strength": float(read_value("blob_shaper_base_strength", 0.5)),
        "blob_shaper_react_strength": float(read_value("blob_shaper_react_strength", 0.5)),
        "blob_shaper_idle_motion": float(read_value("blob_shaper_idle_motion", 0.18)),
        "blob_shaper_audio_motion": float(read_value("blob_shaper_audio_motion", 1.20)),
        "blob_topology": str(read_value("blob_topology", "circle")),
        "blob_ring_thickness": float(read_value("blob_ring_thickness", 0.3)),
        "blob_inward_liquid_enabled": bool(read_value("blob_inward_liquid_enabled", False)),
        "blob_inward_liquid_reactivity": float(read_value("blob_inward_liquid_reactivity", 1.0)),
        "blob_inward_liquid_max_size": float(read_value("blob_inward_liquid_max_size", 0.28)),
        "blob_inward_liquid_color": read_value("blob_inward_liquid_color", [170, 225, 255, 190]),
        "devcurve_active_layer": str(read_value("devcurve_active_layer", "bass")),
        "devcurve_layer_bass_shape_nodes": list(read_value("devcurve_layer_bass_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
        "devcurve_layer_vocals_shape_nodes": list(read_value("devcurve_layer_vocals_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
        "devcurve_layer_mids_shape_nodes": list(read_value("devcurve_layer_mids_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
        "devcurve_layer_transients_shape_nodes": list(read_value("devcurve_layer_transients_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
        "devcurve_base_level": float(read_value("devcurve_base_level", 0.58)),
        "devcurve_motion_power": float(read_value("devcurve_motion_power", 1.0)),
        "devcurve_idle_motion": float(read_value("devcurve_idle_motion", 0.20)),
        "devcurve_idle_speed": float(read_value("devcurve_idle_speed", 0.60)),
        "devcurve_smoothness": float(read_value("devcurve_smoothness", 0.55)),
        "devcurve_layer_bass_enabled": bool(read_value("devcurve_layer_bass_enabled", True)),
        "devcurve_layer_bass_color": read_value("devcurve_layer_bass_color", [82, 167, 255, 230]),
        "devcurve_layer_bass_alpha": float(read_value("devcurve_layer_bass_alpha", 0.55)),
        "devcurve_layer_bass_power": float(read_value("devcurve_layer_bass_power", 1.0)),
        "devcurve_layer_bass_offset": float(read_value("devcurve_layer_bass_offset", 0.0)),
        "devcurve_layer_bass_outline_color": read_value("devcurve_layer_bass_outline_color", [255, 255, 255, 255]),
        "devcurve_layer_bass_outline_width": float(read_value("devcurve_layer_bass_outline_width", 0.006)),
        "devcurve_layer_bass_order": int(read_value("devcurve_layer_bass_order", 1)),
        "devcurve_layer_vocals_enabled": bool(read_value("devcurve_layer_vocals_enabled", True)),
        "devcurve_layer_vocals_color": read_value("devcurve_layer_vocals_color", [136, 190, 255, 220]),
        "devcurve_layer_vocals_alpha": float(read_value("devcurve_layer_vocals_alpha", 0.42)),
        "devcurve_layer_vocals_power": float(read_value("devcurve_layer_vocals_power", 1.0)),
        "devcurve_layer_vocals_offset": float(read_value("devcurve_layer_vocals_offset", -0.01)),
        "devcurve_layer_vocals_outline_color": read_value("devcurve_layer_vocals_outline_color", [255, 255, 255, 255]),
        "devcurve_layer_vocals_outline_width": float(read_value("devcurve_layer_vocals_outline_width", 0.006)),
        "devcurve_layer_vocals_order": int(read_value("devcurve_layer_vocals_order", 2)),
        "devcurve_layer_mids_enabled": bool(read_value("devcurve_layer_mids_enabled", True)),
        "devcurve_layer_mids_color": read_value("devcurve_layer_mids_color", [100, 145, 255, 220]),
        "devcurve_layer_mids_alpha": float(read_value("devcurve_layer_mids_alpha", 0.46)),
        "devcurve_layer_mids_power": float(read_value("devcurve_layer_mids_power", 1.0)),
        "devcurve_layer_mids_offset": float(read_value("devcurve_layer_mids_offset", 0.01)),
        "devcurve_layer_mids_outline_color": read_value("devcurve_layer_mids_outline_color", [255, 255, 255, 255]),
        "devcurve_layer_mids_outline_width": float(read_value("devcurve_layer_mids_outline_width", 0.006)),
        "devcurve_layer_mids_order": int(read_value("devcurve_layer_mids_order", 3)),
        "devcurve_layer_transients_enabled": bool(read_value("devcurve_layer_transients_enabled", True)),
        "devcurve_layer_transients_color": read_value("devcurve_layer_transients_color", [215, 240, 255, 240]),
        "devcurve_layer_transients_alpha": float(read_value("devcurve_layer_transients_alpha", 0.66)),
        "devcurve_layer_transients_power": float(read_value("devcurve_layer_transients_power", 1.15)),
        "devcurve_layer_transients_offset": float(read_value("devcurve_layer_transients_offset", 0.0)),
        "devcurve_layer_transients_outline_color": read_value("devcurve_layer_transients_outline_color", [255, 255, 255, 255]),
        "devcurve_layer_transients_outline_width": float(read_value("devcurve_layer_transients_outline_width", 0.006)),
        "devcurve_layer_transients_order": int(read_value("devcurve_layer_transients_order", 4)),
        "devcurve_ghosting_enabled": bool(read_value("devcurve_ghosting_enabled", False)),
        "devcurve_ghost_alpha": float(read_value("devcurve_ghost_alpha", 0.0)),
        "devcurve_ghost_decay": float(read_value("devcurve_ghost_decay", 0.4)),
        "devcurve_foreground_shadow_enabled": bool(read_value("devcurve_foreground_shadow_enabled", False)),
        "devcurve_foreground_shadow_alpha": float(read_value("devcurve_foreground_shadow_alpha", 0.36)),
        "devcurve_foreground_shadow_darken": float(read_value("devcurve_foreground_shadow_darken", 0.42)),
        "devcurve_foreground_shadow_offset": float(read_value("devcurve_foreground_shadow_offset", 0.10)),
        "devcurve_foreground_specular_enabled": bool(read_value("devcurve_foreground_specular_enabled", False)),
        "devcurve_foreground_specular_alpha": float(read_value("devcurve_foreground_specular_alpha", 0.78)),
        "devcurve_foreground_specular_width": float(read_value("devcurve_foreground_specular_width", 0.022)),
        "devcurve_foreground_specular_offset": float(read_value("devcurve_foreground_specular_offset", 0.028)),
        "devcurve_foreground_specular_crest_bias": float(read_value("devcurve_foreground_specular_crest_bias", 1.05)),
        "sine_line_dim": bool(read_value("sine_line_dim", False)),
        **preset_kwargs,
    }


def _build_settings_readers(
    settings: "SettingsManager",
    *,
    prefix: str,
) -> Tuple[Callable[[str, Any], Any], Callable[[str, str, Any], Any]]:
    """Build the SettingsManager-backed key readers for visualizer ingestion."""

    get = settings.get
    sentinel = object()

    def _get(key: str, default: Any) -> Any:
        return get(f"{prefix}.{key}", default)

    def _mode_value(mode: str, key: str, fallback: Any) -> Any:
        raw = get(f"{prefix}.{mode}_{key}", sentinel)
        if raw is sentinel:
            return fallback
        return raw

    return _get, _mode_value


def _build_mapping_readers(
    raw: Mapping[str, Any],
    *,
    prefix: str,
    active_mode: str,
) -> Tuple[
    Callable[[str, Any], Any],
    Callable[[str, Any], Any],
    Callable[[str, str, Any], Any],
]:
    """Build section/dotted/mode-aware readers for mapping ingestion."""

    def _get(key: str, default: Any) -> Any:
        dotted = f"{prefix}.{key}"
        # Accept both dotted (full key) and plain key inside section mapping.
        if dotted in raw:
            return raw.get(dotted, default)
        return raw.get(key, default)

    def _get_mode_value(base_key: str, default: Any) -> Any:
        sentinel = object()
        for prefix_token in get_setting_prefixes(str(active_mode)):
            value = _get(f"{prefix_token}{base_key}", sentinel)
            if value is not sentinel:
                return value
        if active_mode:
            value = _get(f"{active_mode}_{base_key}", sentinel)
            if value is not sentinel:
                return value
        return _get(base_key, default)

    def _get_per_mode_value(mode: str, base_key: str, default: Any) -> Any:
        sentinel = object()
        seen: set[str] = set()
        candidates = [f"{mode}_{base_key}"]
        candidates.extend(f"{token}{base_key}" for token in get_setting_prefixes(mode))
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            value = _get(candidate, sentinel)
            if value is not sentinel:
                return value
        return default

    return _get, _get_mode_value, _get_per_mode_value


def _coerce_preset_index(raw: Any, *, default: int = 0) -> int:
    """Return a safe integer preset index from persisted mapping data."""

    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _resolve_mapping_preset_kwargs(
    raw: Mapping[str, Any],
    *,
    prefix: str,
    resolve_preset_indices: bool,
) -> Dict[str, int]:
    """Resolve per-mode preset indices from a persisted visualizer mapping."""

    if resolve_preset_indices:
        return resolve_all_preset_indices_from_mapping(raw, prefix=prefix)

    return {
        get_preset_key(mode_id): _coerce_preset_index(
            raw.get(
                get_preset_key(mode_id),
                raw.get(f"{prefix}.{get_preset_key(mode_id)}", 0),
            )
        )
        for mode_id in VISUALIZER_MODE_IDS
    }


def _serialize_outline_rgb(color_value: Any) -> list[int]:
    """Serialize an outline color as RGB with forced full alpha."""

    return [
        int(color_value[0]),
        int(color_value[1]),
        int(color_value[2]),
        255,
    ]



@dataclass
class SpotifyVisualizerSettings:
    """Spotify visualizer widget settings."""

    enabled: bool = False
    visualizers_enabled: bool = True
    monitor: str = "ALL"
    bar_count: int = 32
    bar_fill_color: list | None = None
    bar_border_color: list | None = None
    bar_border_opacity: float = 0.85
    spectrum_bar_fill_color: list | None = None
    spectrum_bar_border_color: list | None = None
    spectrum_bar_border_opacity: float = 0.85
    bubble_bar_fill_color: list | None = None
    bubble_bar_border_color: list | None = None
    bubble_bar_border_opacity: float = 0.85
    blob_bar_fill_color: list | None = None
    blob_bar_border_color: list | None = None
    blob_bar_border_opacity: float = 0.85
    sine_wave_bar_fill_color: list | None = None
    sine_wave_bar_border_color: list | None = None
    sine_wave_bar_border_opacity: float = 0.85
    oscilloscope_bar_fill_color: list | None = None
    oscilloscope_bar_border_color: list | None = None
    oscilloscope_bar_border_opacity: float = 0.85
    devcurve_bar_fill_color: list | None = None
    devcurve_bar_border_color: list | None = None
    devcurve_bar_border_opacity: float = 0.85
    ghosting_enabled: bool = True
    ghost_alpha: float = 0.4
    ghost_decay: float = 0.35
    adaptive_sensitivity: bool = True
    sensitivity: float = 1.0
    dynamic_floor: bool = True
    manual_floor: float = 0.12
    dynamic_range_enabled: bool = False
    agc_strength: float = 0.5
    input_gain: float = 1.0
    kick_lane_gain: float = 1.0
    transient_pulse_gain: float = 1.0
    transient_clamp: float = 1.5
    spectrum_lane_transient_mix: float = 0.65
    spectrum_dynamic_floor: bool = True
    spectrum_manual_floor: float = 0.12
    spectrum_dynamic_range_enabled: bool = False
    spectrum_agc_strength: float = 0.5
    spectrum_input_gain: float = 1.0
    spectrum_kick_lane_gain: float = 1.0
    spectrum_transient_pulse_gain: float = 1.0
    spectrum_transient_clamp: float = 1.5
    spectrum_audio_block_size: int = 512
    spectrum_adaptive_sensitivity: bool = True
    spectrum_sensitivity: float = 0.4
    spectrum_bar_count: int = 33
    bubble_dynamic_floor: bool = True
    bubble_manual_floor: float = 0.12
    bubble_dynamic_range_enabled: bool = False
    bubble_agc_strength: float = 0.5
    bubble_input_gain: float = 1.0
    bubble_kick_lane_gain: float = 1.0
    bubble_transient_pulse_gain: float = 1.0
    bubble_transient_clamp: float = 1.5
    bubble_transient_mix_bass: float = 0.75
    bubble_transient_mix_vocal: float = 0.25
    bubble_audio_block_size: int = 512
    bubble_adaptive_sensitivity: bool = True
    bubble_sensitivity: float = 0.4
    bubble_bar_count: int = 48
    blob_dynamic_floor: bool = True
    blob_manual_floor: float = 0.12
    blob_dynamic_range_enabled: bool = False
    blob_agc_strength: float = 0.5
    blob_input_gain: float = 1.0
    blob_kick_lane_gain: float = 1.0
    blob_transient_pulse_gain: float = 1.0
    blob_transient_clamp: float = 1.5
    blob_transient_mix_bass: float = 0.5
    blob_transient_mix_vocal: float = 0.35
    blob_audio_block_size: int = 512
    blob_adaptive_sensitivity: bool = True
    blob_sensitivity: float = 0.4
    blob_bar_count: int = 32
    sine_wave_dynamic_floor: bool = True
    sine_wave_manual_floor: float = 0.12
    sine_wave_dynamic_range_enabled: bool = False
    sine_wave_agc_strength: float = 0.5
    sine_wave_input_gain: float = 1.0
    sine_wave_kick_lane_gain: float = 1.0
    sine_wave_transient_pulse_gain: float = 1.0
    sine_wave_transient_clamp: float = 1.5
    sine_wave_transient_width_mix: float = 0.4
    sine_wave_audio_block_size: int = 512
    sine_wave_adaptive_sensitivity: bool = True
    sine_wave_sensitivity: float = 0.4
    sine_wave_bar_count: int = 40
    oscilloscope_dynamic_floor: bool = True
    oscilloscope_manual_floor: float = 0.12
    oscilloscope_dynamic_range_enabled: bool = False
    oscilloscope_agc_strength: float = 0.5
    oscilloscope_input_gain: float = 1.0
    oscilloscope_kick_lane_gain: float = 1.0
    oscilloscope_transient_pulse_gain: float = 1.0
    oscilloscope_transient_clamp: float = 1.5
    oscilloscope_transient_width_mix: float = 0.35
    oscilloscope_audio_block_size: int = 512
    oscilloscope_adaptive_sensitivity: bool = True
    oscilloscope_sensitivity: float = 0.4
    oscilloscope_bar_count: int = 32
    devcurve_dynamic_floor: bool = True
    devcurve_manual_floor: float = 0.12
    devcurve_dynamic_range_enabled: bool = False
    devcurve_agc_strength: float = 0.5
    devcurve_input_gain: float = 1.0
    devcurve_kick_lane_gain: float = 1.0
    devcurve_transient_pulse_gain: float = 1.0
    devcurve_transient_clamp: float = 1.5
    devcurve_audio_block_size: int = 0
    devcurve_adaptive_sensitivity: bool = True
    devcurve_sensitivity: float = 1.0
    devcurve_bar_count: int = 32
    mode: str = "bubble"
    osc_glow_enabled: bool = True
    osc_glow_intensity: float = 0.5
    osc_glow_reactivity: float = 1.0
    osc_glow_color: list = None
    osc_reactive_glow: bool = True
    osc_line_amplitude: float = 3.0
    osc_smoothing: float = 0.7
    blob_color: list = None
    blob_glow_color: list = None
    blob_edge_color: list = None
    blob_outline_color: list = None
    blob_pulse: float = 1.0
    blob_pulse_release_ms: int = 220
    blob_width: float = 1.0
    blob_size: float = 1.0
    blob_glow_intensity: float = 0.5
    blob_reactive_glow: bool = True
    blob_glow_drive_mode: str = "bass"
    osc_line_color: list = None
    osc_line_count: int = 1
    osc_line2_color: list = None
    osc_line2_glow_color: list = None
    osc_line3_color: list = None
    osc_line3_glow_color: list = None
    osc_line4_color: list = None
    osc_line4_glow_color: list = None
    osc_line5_color: list = None
    osc_line5_glow_color: list = None
    osc_line6_color: list = None
    osc_line6_glow_color: list = None
    spectrum_growth: float = 1.0
    blob_growth: float = 2.5
    osc_speed: float = 1.0
    osc_line_dim: bool = False
    osc_line_offset_bias: float = 0.0
    osc_vertical_shift: int = 0
    osc_growth: float = 1.0
    blob_reactive_deformation: float = 1.0
    blob_constant_wobble: float = 1.0
    blob_reactive_wobble: float = 1.0
    blob_stretch: float = 0.35
    blob_stage_gain: float = 1.0
    blob_core_scale: float = 1.0
    blob_core_floor_bias: float = 0.35
    blob_stage_bias: float = 0.0
    blob_stretch_tendency: float = 0.35
    blob_stretch_inner: float = 0.0
    blob_stretch_outer: float = 0.35
    spectrum_render_mode: str = "bars"
    spectrum_unique_colors: bool = True
    spectrum_rainbow_border: bool = False
    spectrum_border_radius: float = 0.0
    spectrum_link_fill_border: bool = False
    spectrum_glow_enabled: bool = False
    spectrum_glow_intensity: float = 0.55
    spectrum_glow_color: List[int] = field(default_factory=lambda: [110, 220, 255, 235])
    spectrum_ghosting_enabled: bool = True
    spectrum_ghost_alpha: float = 0.4
    spectrum_ghost_decay: float = 0.4
    spectrum_mirrored: bool = True
    spectrum_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]])
    spectrum_notch_positions_mirrored: List[List] = field(default_factory=lambda: [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]])
    spectrum_notch_positions_linear: List[List] = field(default_factory=lambda: [[0.0, "Bass"], [0.24, "Low-Mid"], [0.46, "Vocal"], [0.72, "Hi-Mid"], [1.0, "Treble"]])
    spectrum_lane_strengths_mirrored: Dict[str, float] = field(
        default_factory=lambda: dict(_SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED)
    )
    spectrum_lane_strengths_linear: Dict[str, float] = field(
        default_factory=lambda: dict(_SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR)
    )
    spectrum_wave_amplitude: float = 0.50
    spectrum_profile_floor: float = 0.12
    spectrum_drop_speed: float = 1.0
    sine_wave_growth: float = 1.0
    sine_wave_travel: int = 0
    sine_density: float = 1.0
    sine_displacement: float = 0.0
    sine_glow_enabled: bool = True
    sine_glow_intensity: float = 0.5
    sine_glow_reactivity: float = 1.0
    sine_glow_color: list = None
    sine_line_color: list = None
    sine_reactive_glow: bool = True
    sine_ghosting_enabled: bool = True
    sine_ghost_alpha: float = 0.45
    sine_ghost_decay: float = 0.3
    sine_ghost_line2_enabled: bool = True
    sine_ghost_line3_enabled: bool = True
    sine_ghost_line4_enabled: bool = True
    sine_ghost_line5_enabled: bool = True
    sine_ghost_line6_enabled: bool = True
    sine_sensitivity: float = 1.0
    sine_smoothing: float = 0.7
    sine_speed: float = 1.0
    sine_line_count: int = 1
    sine_line_offset_bias: float = 0.0
    sine_line2_color: list = None
    sine_line2_glow_color: list = None
    sine_line3_color: list = None
    sine_line3_glow_color: list = None
    sine_line4_color: list = None
    sine_line4_glow_color: list = None
    sine_line5_color: list = None
    sine_line5_glow_color: list = None
    sine_line6_color: list = None
    sine_line6_glow_color: list = None
    sine_travel_line2: int = 0
    sine_travel_line3: int = 0
    sine_travel_line4: int = 0
    sine_travel_line5: int = 0
    sine_travel_line6: int = 0
    sine_line1_shift: float = 0.0
    sine_line2_shift: float = 0.0
    sine_line3_shift: float = 0.0
    sine_line4_shift: float = 0.0
    sine_line5_shift: float = 0.0
    sine_line6_shift: float = 0.0
    sine_wave_effect: float = 0.0
    sine_vertical_shift: int = 0
    sine_micro_wobble: float = 0.0  # legacy, hidden
    sine_crawl_amount: float = 0.25
    sine_width_reaction: float = 0.0
    sine_card_adaptation: float = 0.3
    rainbow_enabled: bool = False
    rainbow_speed: float = 0.5
    osc_ghosting_enabled: bool = False
    osc_ghost_intensity: float = 0.4
    osc_ghost_line2_enabled: bool = True
    osc_ghost_line3_enabled: bool = True
    osc_ghost_line4_enabled: bool = True
    osc_ghost_line5_enabled: bool = True
    osc_ghost_line6_enabled: bool = True
    sine_heartbeat: float = 0.0
    # Bubble visualizer
    bubble_big_bass_pulse: float = 0.5
    bubble_small_freq_pulse: float = 0.5
    bubble_stream_direction: str = "up"
    bubble_stream_constant_speed: float = 0.5
    bubble_stream_speed_cap: float = 2.0
    bubble_stream_reactivity: float = 0.5
    bubble_rotation_amount: float = 0.5
    bubble_drift_amount: float = 0.5
    bubble_drift_speed: float = 0.5
    bubble_drift_frequency: float = 0.5
    bubble_drift_direction: str = "random"  # none/left/right/diagonal/swish_{horizontal,vertical}/swirl_{cw,ccw}/random
    bubble_big_count: int = 8
    bubble_small_count: int = 25
    bubble_surface_reach: float = 0.6
    bubble_bounce_big_pct: int = 70
    bubble_bounce_small_pct: int = 30
    bubble_bounce_big_speed: float = 0.8
    bubble_bounce_small_speed: float = 0.5
    bubble_bounce_same_only: bool = False
    bubble_collision_pop_mode: str = "off"  # off/one/all
    bubble_outline_color: Any = None
    bubble_specular_color: Any = None
    bubble_gradient_light: Any = None
    bubble_gradient_dark: Any = None
    bubble_pop_color: Any = None
    bubble_specular_direction: str = "top_left"  # top/bottom/left/right + diagonals
    bubble_gradient_direction: str = "top"  # gradient vector independent of specular highlight
    bubble_big_size_max: float = 0.038
    bubble_small_size_max: float = 0.018
    bubble_big_contraction_bias: float = 1.0
    bubble_big_size_clamp: float = 4.0
    bubble_big_specular_max_size: float = 2.5
    bubble_growth: float = 3.0
    devcurve_growth: float = 3.0
    bubble_tail_opacity: float = 0.3
    bubble_trail_strength: float = 0.0
    bubble_ghosting_enabled: bool = False
    bubble_ghost_alpha: float = 0.0
    bubble_ghost_decay: float = 0.4
    blob_glow_reactivity: float = 1.0
    blob_glow_max_size: float = 1.0
    blob_ghosting_enabled: bool = False
    blob_ghost_alpha: float = 0.4
    blob_ghost_decay: float = 0.3
    sine_line_dim: bool = False
    # Blob Shaper
    blob_shaper_enabled: bool = False
    blob_shape_base_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])
    blob_shape_reaction_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])
    blob_shape_energy_nodes: List[Dict[str, Any]] = field(default_factory=list)
    blob_shaper_base_strength: float = 0.5
    blob_shaper_react_strength: float = 0.5
    blob_shaper_idle_motion: float = 0.18
    blob_shaper_audio_motion: float = 1.20
    blob_topology: str = "circle"
    blob_ring_thickness: float = 0.3
    blob_inward_liquid_enabled: bool = False
    blob_inward_liquid_reactivity: float = 1.0
    blob_inward_liquid_max_size: float = 0.28
    blob_inward_liquid_color: Any = None
    # Dev Curve visualizer
    devcurve_active_layer: str = "bass"
    devcurve_layer_bass_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])
    devcurve_layer_vocals_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])
    devcurve_layer_mids_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])
    devcurve_layer_transients_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])
    devcurve_base_level: float = 0.58
    devcurve_motion_power: float = 1.0
    devcurve_idle_motion: float = 0.20
    devcurve_idle_speed: float = 0.60
    devcurve_smoothness: float = 0.55
    devcurve_layer_bass_enabled: bool = True
    devcurve_layer_bass_color: Any = None
    devcurve_layer_bass_alpha: float = 0.55
    devcurve_layer_bass_power: float = 1.0
    devcurve_layer_bass_offset: float = 0.0
    devcurve_layer_bass_outline_color: Any = None
    devcurve_layer_bass_outline_width: float = 0.006
    devcurve_layer_bass_order: int = 1
    devcurve_layer_vocals_enabled: bool = True
    devcurve_layer_vocals_color: Any = None
    devcurve_layer_vocals_alpha: float = 0.42
    devcurve_layer_vocals_power: float = 1.0
    devcurve_layer_vocals_offset: float = -0.01
    devcurve_layer_vocals_outline_color: Any = None
    devcurve_layer_vocals_outline_width: float = 0.006
    devcurve_layer_vocals_order: int = 2
    devcurve_layer_mids_enabled: bool = True
    devcurve_layer_mids_color: Any = None
    devcurve_layer_mids_alpha: float = 0.46
    devcurve_layer_mids_power: float = 1.0
    devcurve_layer_mids_offset: float = 0.01
    devcurve_layer_mids_outline_color: Any = None
    devcurve_layer_mids_outline_width: float = 0.006
    devcurve_layer_mids_order: int = 3
    devcurve_layer_transients_enabled: bool = True
    devcurve_layer_transients_color: Any = None
    devcurve_layer_transients_alpha: float = 0.66
    devcurve_layer_transients_power: float = 1.15
    devcurve_layer_transients_offset: float = 0.0
    devcurve_layer_transients_outline_color: Any = None
    devcurve_layer_transients_outline_width: float = 0.006
    devcurve_layer_transients_order: int = 4
    devcurve_ghosting_enabled: bool = False
    devcurve_ghost_alpha: float = 0.0
    devcurve_ghost_decay: float = 0.4
    devcurve_foreground_shadow_enabled: bool = False
    devcurve_foreground_shadow_alpha: float = 0.36
    devcurve_foreground_shadow_darken: float = 0.42
    devcurve_foreground_shadow_offset: float = 0.10
    devcurve_foreground_specular_enabled: bool = False
    devcurve_foreground_specular_alpha: float = 0.78
    devcurve_foreground_specular_width: float = 0.022
    devcurve_foreground_specular_offset: float = 0.028
    devcurve_foreground_specular_crest_bias: float = 1.05
    # Visualizer presets (0=Preset 1/Default, 1=Preset 2, 2=Preset 3, 3=Custom)
    preset_spectrum: int = field(default_factory=lambda: get_missing_preset_fallback_index("spectrum"))
    preset_oscilloscope: int = field(default_factory=lambda: get_missing_preset_fallback_index("oscilloscope"))
    preset_sine_wave: int = field(default_factory=lambda: get_missing_preset_fallback_index("sine_wave"))
    preset_blob: int = field(default_factory=lambda: get_missing_preset_fallback_index("blob"))
    preset_bubble: int = field(default_factory=lambda: get_missing_preset_fallback_index("bubble"))
    preset_devcurve: int = field(default_factory=lambda: get_missing_preset_fallback_index("devcurve"))

    def __post_init__(self):
        self._apply_core_visual_defaults()
        self._apply_blob_defaults()
        self._apply_oscilloscope_defaults()
        self._apply_sine_defaults()
        self._apply_bubble_defaults()
        self._apply_devcurve_defaults()

    def _apply_list_default(self, attr: str, value: list[int]) -> None:
        if getattr(self, attr) is None:
            setattr(self, attr, list(value))

    def _ensure_non_empty_nodes(self, attr: str, default_nodes: list[list[float]]) -> None:
        value = getattr(self, attr)
        if not isinstance(value, list) or not value:
            setattr(self, attr, deepcopy(default_nodes))

    def _apply_core_visual_defaults(self) -> None:
        if self.osc_glow_color is None:
            self.osc_glow_color = [0, 200, 255, 230]
        if self.bar_fill_color is None:
            self.bar_fill_color = [0, 255, 128, 230]
        if self.bar_border_color is None:
            self.bar_border_color = [255, 255, 255, 230]
        for mode in PER_MODE_TECHNICAL_MODES:
            fill_attr = f"{mode}_bar_fill_color"
            border_attr = f"{mode}_bar_border_color"
            opacity_attr = f"{mode}_bar_border_opacity"
            if getattr(self, fill_attr) is None:
                setattr(self, fill_attr, list(self.bar_fill_color))
            if getattr(self, border_attr) is None:
                setattr(self, border_attr, list(self.bar_border_color))
            try:
                mode_opacity = float(getattr(self, opacity_attr))
            except Exception:
                mode_opacity = float(self.bar_border_opacity)
            setattr(self, opacity_attr, mode_opacity)
 
    def _apply_blob_defaults(self) -> None:
        self._apply_list_default("blob_color", [0, 180, 255, 230])
        self._apply_list_default("blob_glow_color", [0, 140, 255, 180])
        self._apply_list_default("blob_edge_color", [100, 220, 255, 230])
        self._apply_list_default("blob_outline_color", [0, 0, 0, 0])
        self._apply_list_default("blob_inward_liquid_color", [170, 225, 255, 190])
        self.blob_glow_drive_mode = (
            "vocal" if str(self.blob_glow_drive_mode).strip().lower() == "vocal" else "bass"
        )

    def _apply_oscilloscope_defaults(self) -> None:
        for attr, value in (
            ("osc_line_color", [255, 255, 255, 255]),
            ("osc_line2_color", [255, 120, 50, 230]),
            ("osc_line2_glow_color", [255, 120, 50, 180]),
            ("osc_line3_color", [50, 255, 120, 230]),
            ("osc_line3_glow_color", [50, 255, 120, 180]),
            ("osc_line4_color", [255, 0, 150, 230]),
            ("osc_line4_glow_color", [255, 0, 150, 180]),
            ("osc_line5_color", [0, 255, 200, 230]),
            ("osc_line5_glow_color", [0, 255, 200, 180]),
            ("osc_line6_color", [200, 100, 255, 230]),
            ("osc_line6_glow_color", [200, 100, 255, 180]),
        ):
            self._apply_list_default(attr, value)

    def _apply_sine_defaults(self) -> None:
        for attr, value in (
            ("sine_glow_color", [0, 200, 255, 230]),
            ("sine_line_color", [255, 255, 255, 255]),
            ("sine_line2_color", [255, 255, 255, 230]),
            ("sine_line2_glow_color", [7, 114, 255, 180]),
            ("sine_line3_color", [255, 255, 255, 230]),
            ("sine_line3_glow_color", [14, 159, 255, 180]),
            ("sine_line4_color", [255, 120, 50, 230]),
            ("sine_line4_glow_color", [255, 120, 50, 180]),
            ("sine_line5_color", [50, 255, 120, 230]),
            ("sine_line5_glow_color", [50, 255, 120, 180]),
            ("sine_line6_color", [255, 0, 150, 230]),
            ("sine_line6_glow_color", [255, 0, 150, 180]),
        ):
            self._apply_list_default(attr, value)

    def _apply_bubble_defaults(self) -> None:
        for attr, value in (
            ("bubble_outline_color", [255, 255, 255, 230]),
            ("bubble_specular_color", [255, 255, 255, 255]),
            ("bubble_gradient_light", [210, 170, 120, 255]),
            ("bubble_gradient_dark", [80, 60, 50, 255]),
            ("bubble_pop_color", [255, 255, 255, 180]),
        ):
            self._apply_list_default(attr, value)

    def _apply_devcurve_defaults(self) -> None:
        for attr, value in (
            ("devcurve_layer_bass_color", [82, 167, 255, 230]),
            ("devcurve_layer_vocals_color", [136, 190, 255, 220]),
            ("devcurve_layer_mids_color", [100, 145, 255, 220]),
            ("devcurve_layer_transients_color", [215, 240, 255, 240]),
            ("devcurve_layer_bass_outline_color", [255, 255, 255, 255]),
            ("devcurve_layer_vocals_outline_color", [255, 255, 255, 255]),
            ("devcurve_layer_mids_outline_color", [255, 255, 255, 255]),
            ("devcurve_layer_transients_outline_color", [255, 255, 255, 255]),
        ):
            self._apply_list_default(attr, value)
        self.devcurve_active_layer = (
            str(self.devcurve_active_layer).strip().lower()
            if str(self.devcurve_active_layer).strip().lower() in {"bass", "vocals", "mids", "transients"}
            else "bass"
        )
        self.devcurve_layer_bass_outline_width = max(0.001, min(0.020, float(self.devcurve_layer_bass_outline_width)))
        self.devcurve_layer_vocals_outline_width = max(0.001, min(0.020, float(self.devcurve_layer_vocals_outline_width)))
        self.devcurve_layer_mids_outline_width = max(0.001, min(0.020, float(self.devcurve_layer_mids_outline_width)))
        self.devcurve_layer_transients_outline_width = max(0.001, min(0.020, float(self.devcurve_layer_transients_outline_width)))
        for attr in (
            "devcurve_layer_bass_outline_color",
            "devcurve_layer_vocals_outline_color",
            "devcurve_layer_mids_outline_color",
            "devcurve_layer_transients_outline_color",
        ):
            value = list(getattr(self, attr))
            while len(value) < 4:
                value.append(255)
            value[3] = 255
            setattr(self, attr, value[:4])
        self.devcurve_smoothness = max(0.0, min(1.0, float(self.devcurve_smoothness)))
        self.devcurve_foreground_shadow_alpha = max(0.0, min(1.0, float(self.devcurve_foreground_shadow_alpha)))
        self.devcurve_foreground_shadow_darken = max(0.0, min(1.0, float(self.devcurve_foreground_shadow_darken)))
        self.devcurve_foreground_shadow_offset = max(0.0, min(0.45, float(self.devcurve_foreground_shadow_offset)))
        self.devcurve_foreground_specular_alpha = max(0.0, min(1.0, float(self.devcurve_foreground_specular_alpha)))
        self.devcurve_foreground_specular_width = max(0.002, min(0.120, float(self.devcurve_foreground_specular_width)))
        self.devcurve_foreground_specular_offset = max(-0.20, min(0.20, float(self.devcurve_foreground_specular_offset)))
        self.devcurve_foreground_specular_crest_bias = max(0.0, min(2.0, float(self.devcurve_foreground_specular_crest_bias)))
        default_nodes = [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
        for attr in (
            "devcurve_layer_bass_shape_nodes",
            "devcurve_layer_vocals_shape_nodes",
            "devcurve_layer_mids_shape_nodes",
            "devcurve_layer_transients_shape_nodes",
        ):
            self._ensure_non_empty_nodes(attr, default_nodes)
        _order_pairs = [
            ("devcurve_layer_bass_order", int(self.devcurve_layer_bass_order)),
            ("devcurve_layer_vocals_order", int(self.devcurve_layer_vocals_order)),
            ("devcurve_layer_mids_order", int(self.devcurve_layer_mids_order)),
            ("devcurve_layer_transients_order", int(self.devcurve_layer_transients_order)),
        ]
        _order_pairs.sort(key=lambda item: item[1])
        for idx, (attr_name, _raw_rank) in enumerate(_order_pairs, start=1):
            setattr(self, attr_name, idx)

    @classmethod
    def from_settings(cls, settings: "SettingsManager", prefix: str = "widgets.spotify_visualizer") -> "SpotifyVisualizerSettings":
        """Load Spotify visualizer settings from SettingsManager."""
        get = settings.get
        _get, _mode_value = _build_settings_readers(settings, prefix=prefix)

        try:
            bubble_gradient_semantics_version = int(_get("bubble_gradient_semantics_version", 0))
        except (TypeError, ValueError):
            bubble_gradient_semantics_version = 0
        _defaults_model = cls()

        _mode_kwargs = _build_live_visualizer_mode_kwargs(_mode_value, _defaults_model)
        _mode_visual_kwargs = _build_live_visualizer_mode_shared_visual_kwargs(_mode_value, _defaults_model)
        _preset_kwargs = resolve_all_preset_indices_from_getter(get, prefix=prefix)
        _active_mode = coerce_visualizer_mode_id(str(get(f"{prefix}.mode", "bubble")))
        _active_technical = _resolve_active_mode_technical_state(
            _active_mode,
            _mode_kwargs,
        )
        _active_visuals = _resolve_active_mode_shared_visual_state(
            _active_mode,
            _mode_visual_kwargs,
        )
        _rainbow_kwargs = resolve_visualizer_active_mode_rainbow_state(
            lambda key, default: _mode_value(
                _active_mode,
                key,
                _get(key, default),
            )
        )

        return cls(
            **_build_visualizer_model_kwargs(
                _get,
                active_mode=_active_mode,
                bubble_gradient_semantics_version=bubble_gradient_semantics_version,
                active_technical=_active_technical,
                active_visuals=_active_visuals,
                rainbow_kwargs=_rainbow_kwargs,
                preset_kwargs={**_preset_kwargs, **_mode_kwargs, **_mode_visual_kwargs},
                bubble_stream_constant_speed_default=0.5,
                bubble_stream_speed_cap_default=2.0,
            )
        )

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        prefix: str = "widgets.spotify_visualizer",
        *,
        apply_preset_overlay: bool = True,
        resolve_preset_indices: bool = True,
    ) -> "SpotifyVisualizerSettings":
        """Load Spotify visualizer settings from a plain mapping (e.g., widgets dict)."""
        # Apply visualizer preset overlay before reading individual fields.
        # For non-Custom presets with a non-empty settings dict, the preset
        # values override the stored user values.  Custom (index 3) and empty
        # preset dicts are no-ops so existing behaviour is fully preserved.
        _raw = migrate_legacy_global_visual_keys(
            migrate_legacy_global_technical_keys(dict(data), prefix=prefix),
            prefix=prefix,
        )
        _mode = coerce_visualizer_mode_id(
            _raw.get("mode", _raw.get(f"{prefix}.mode", "bubble"))
        )
        bubble_gradient_semantics_version = get_bubble_gradient_semantics_version(_raw, prefix=prefix)
        if apply_preset_overlay:
            from core.settings.visualizer_presets import apply_preset_to_config

            _preset_idx = resolve_preset_index_from_mapping(str(_mode), _raw, prefix=prefix)
            _raw = apply_preset_to_config(str(_mode), _preset_idx, _raw)
        _get, _get_mode_value, _get_per_mode_value = _build_mapping_readers(
            _raw,
            prefix=prefix,
            active_mode=str(_mode),
        )

        _defaults_model = cls()
        _mode_kwargs = _build_live_visualizer_mode_kwargs(_get_per_mode_value, _defaults_model)
        _mode_visual_kwargs = _build_live_visualizer_mode_shared_visual_kwargs(_get_per_mode_value, _defaults_model)
        _preset_kwargs = _resolve_mapping_preset_kwargs(
            _raw,
            prefix=prefix,
            resolve_preset_indices=resolve_preset_indices,
        )
        _active_technical = _resolve_active_mode_technical_state(
            _mode,
            _mode_kwargs,
        )
        _active_visuals = _resolve_active_mode_shared_visual_state(
            _mode,
            _mode_visual_kwargs,
        )
        _rainbow_kwargs = resolve_visualizer_active_mode_rainbow_state(
            lambda key, default: _get_mode_value(key, default)
        )

        return cls(
            **_build_visualizer_model_kwargs(
                _get,
                active_mode=_mode,
                bubble_gradient_semantics_version=bubble_gradient_semantics_version,
                active_technical=_active_technical,
                active_visuals=_active_visuals,
                rainbow_kwargs=_rainbow_kwargs,
                preset_kwargs={**_preset_kwargs, **_mode_kwargs, **_mode_visual_kwargs},
                bubble_stream_constant_speed_default=0.6,
                bubble_stream_speed_cap_default=1.0,
            )
        )

    def to_dict(self, prefix: str = "widgets.spotify_visualizer") -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        data = {
            f"{prefix}.enabled": self.enabled,
            f"{prefix}.visualizers_enabled": self.visualizers_enabled,
            f"{prefix}.monitor": self.monitor,
            f"{prefix}.mode": self.mode,
            f"{prefix}.osc_glow_enabled": self.osc_glow_enabled,
            f"{prefix}.osc_glow_intensity": float(self.osc_glow_intensity),
            f"{prefix}.osc_glow_reactivity": float(self.osc_glow_reactivity),
            f"{prefix}.osc_glow_color": list(self.osc_glow_color),
            f"{prefix}.osc_reactive_glow": self.osc_reactive_glow,
            f"{prefix}.osc_line_amplitude": float(self.osc_line_amplitude),
            f"{prefix}.osc_smoothing": float(self.osc_smoothing),
            f"{prefix}.blob_color": list(self.blob_color),
            f"{prefix}.blob_glow_color": list(self.blob_glow_color),
            f"{prefix}.blob_edge_color": list(self.blob_edge_color),
            f"{prefix}.blob_outline_color": list(self.blob_outline_color),
            f"{prefix}.blob_pulse": float(self.blob_pulse),
            f"{prefix}.blob_pulse_release_ms": int(self.blob_pulse_release_ms),
            f"{prefix}.blob_width": float(self.blob_width),
            f"{prefix}.blob_size": float(self.blob_size),
            f"{prefix}.blob_glow_intensity": float(self.blob_glow_intensity),
            f"{prefix}.blob_reactive_glow": self.blob_reactive_glow,
            f"{prefix}.blob_glow_drive_mode": str(self.blob_glow_drive_mode),
            f"{prefix}.osc_line_color": list(self.osc_line_color),
            f"{prefix}.osc_line_count": int(self.osc_line_count),
            f"{prefix}.osc_line2_color": list(self.osc_line2_color),
            f"{prefix}.osc_line2_glow_color": list(self.osc_line2_glow_color),
            f"{prefix}.osc_line3_color": list(self.osc_line3_color),
            f"{prefix}.osc_line3_glow_color": list(self.osc_line3_glow_color),
            f"{prefix}.osc_line4_color": list(self.osc_line4_color),
            f"{prefix}.osc_line4_glow_color": list(self.osc_line4_glow_color),
            f"{prefix}.osc_line5_color": list(self.osc_line5_color),
            f"{prefix}.osc_line5_glow_color": list(self.osc_line5_glow_color),
            f"{prefix}.osc_line6_color": list(self.osc_line6_color),
            f"{prefix}.osc_line6_glow_color": list(self.osc_line6_glow_color),
            f"{prefix}.spectrum_growth": float(self.spectrum_growth),
            f"{prefix}.blob_growth": float(self.blob_growth),
            f"{prefix}.osc_speed": float(self.osc_speed),
            f"{prefix}.osc_line_dim": self.osc_line_dim,
            f"{prefix}.osc_line_offset_bias": float(self.osc_line_offset_bias),
            f"{prefix}.osc_vertical_shift": int(self.osc_vertical_shift),
            f"{prefix}.osc_growth": float(self.osc_growth),
            f"{prefix}.blob_reactive_deformation": float(self.blob_reactive_deformation),
            f"{prefix}.blob_constant_wobble": float(self.blob_constant_wobble),
            f"{prefix}.blob_reactive_wobble": float(self.blob_reactive_wobble),
            f"{prefix}.blob_stretch": float(self.blob_stretch),
            f"{prefix}.blob_stage_gain": float(self.blob_stage_gain),
            f"{prefix}.blob_core_scale": float(self.blob_core_scale),
            f"{prefix}.blob_core_floor_bias": float(self.blob_core_floor_bias),
            f"{prefix}.blob_stage_bias": float(self.blob_stage_bias),
            f"{prefix}.blob_stretch_tendency": float(self.blob_stretch_tendency),
            f"{prefix}.blob_stretch_inner": float(self.blob_stretch_inner),
            f"{prefix}.blob_stretch_outer": float(self.blob_stretch_outer),
            f"{prefix}.spectrum_render_mode": str(self.spectrum_render_mode),
            f"{prefix}.spectrum_unique_colors": self.spectrum_unique_colors,
            f"{prefix}.spectrum_rainbow_border": self.spectrum_rainbow_border,
            f"{prefix}.spectrum_border_radius": float(self.spectrum_border_radius),
            f"{prefix}.spectrum_link_fill_border": self.spectrum_link_fill_border,
            f"{prefix}.spectrum_glow_enabled": self.spectrum_glow_enabled,
            f"{prefix}.spectrum_glow_intensity": float(self.spectrum_glow_intensity),
            f"{prefix}.spectrum_glow_color": list(self.spectrum_glow_color),
            f"{prefix}.spectrum_ghosting_enabled": self.spectrum_ghosting_enabled,
            f"{prefix}.spectrum_ghost_alpha": float(self.spectrum_ghost_alpha),
            f"{prefix}.spectrum_ghost_decay": float(self.spectrum_ghost_decay),
            f"{prefix}.spectrum_mirrored": self.spectrum_mirrored,
            f"{prefix}.spectrum_shape_nodes": self.spectrum_shape_nodes,
            f"{prefix}.spectrum_notch_positions_mirrored": self.spectrum_notch_positions_mirrored,
            f"{prefix}.spectrum_notch_positions_linear": self.spectrum_notch_positions_linear,
            f"{prefix}.spectrum_lane_strengths_mirrored": dict(self.spectrum_lane_strengths_mirrored),
            f"{prefix}.spectrum_lane_strengths_linear": dict(self.spectrum_lane_strengths_linear),
            f"{prefix}.spectrum_wave_amplitude": float(self.spectrum_wave_amplitude),
            f"{prefix}.spectrum_profile_floor": float(self.spectrum_profile_floor),
            f"{prefix}.spectrum_drop_speed": float(self.spectrum_drop_speed),
            f"{prefix}.sine_wave_growth": float(self.sine_wave_growth),
            f"{prefix}.sine_wave_travel": int(self.sine_wave_travel),
            f"{prefix}.sine_density": float(self.sine_density),
            f"{prefix}.sine_displacement": float(self.sine_displacement),
            f"{prefix}.sine_glow_enabled": self.sine_glow_enabled,
            f"{prefix}.sine_glow_intensity": float(self.sine_glow_intensity),
            f"{prefix}.sine_glow_reactivity": float(self.sine_glow_reactivity),
            f"{prefix}.sine_glow_color": list(self.sine_glow_color),
            f"{prefix}.sine_line_color": list(self.sine_line_color),
            f"{prefix}.sine_reactive_glow": self.sine_reactive_glow,
            f"{prefix}.sine_ghosting_enabled": self.sine_ghosting_enabled,
            f"{prefix}.sine_ghost_alpha": float(self.sine_ghost_alpha),
            f"{prefix}.sine_ghost_decay": float(self.sine_ghost_decay),
            f"{prefix}.sine_ghost_line2_enabled": self.sine_ghost_line2_enabled,
            f"{prefix}.sine_ghost_line3_enabled": self.sine_ghost_line3_enabled,
            f"{prefix}.sine_ghost_line4_enabled": self.sine_ghost_line4_enabled,
            f"{prefix}.sine_ghost_line5_enabled": self.sine_ghost_line5_enabled,
            f"{prefix}.sine_ghost_line6_enabled": self.sine_ghost_line6_enabled,
            f"{prefix}.sine_sensitivity": float(self.sine_sensitivity),
            f"{prefix}.sine_smoothing": float(self.sine_smoothing),
            f"{prefix}.sine_speed": float(self.sine_speed),
            f"{prefix}.sine_line_count": int(self.sine_line_count),
            f"{prefix}.sine_line_offset_bias": float(self.sine_line_offset_bias),
            f"{prefix}.sine_line2_color": list(self.sine_line2_color),
            f"{prefix}.sine_line2_glow_color": list(self.sine_line2_glow_color),
            f"{prefix}.sine_line3_color": list(self.sine_line3_color),
            f"{prefix}.sine_line3_glow_color": list(self.sine_line3_glow_color),
            f"{prefix}.sine_line4_color": list(self.sine_line4_color),
            f"{prefix}.sine_line4_glow_color": list(self.sine_line4_glow_color),
            f"{prefix}.sine_line5_color": list(self.sine_line5_color),
            f"{prefix}.sine_line5_glow_color": list(self.sine_line5_glow_color),
            f"{prefix}.sine_line6_color": list(self.sine_line6_color),
            f"{prefix}.sine_line6_glow_color": list(self.sine_line6_glow_color),
            f"{prefix}.sine_travel_line2": int(self.sine_travel_line2),
            f"{prefix}.sine_travel_line3": int(self.sine_travel_line3),
            f"{prefix}.sine_travel_line4": int(self.sine_travel_line4),
            f"{prefix}.sine_travel_line5": int(self.sine_travel_line5),
            f"{prefix}.sine_travel_line6": int(self.sine_travel_line6),
            f"{prefix}.sine_line1_shift": float(self.sine_line1_shift),
            f"{prefix}.sine_line2_shift": float(self.sine_line2_shift),
            f"{prefix}.sine_line3_shift": float(self.sine_line3_shift),
            f"{prefix}.sine_line4_shift": float(self.sine_line4_shift),
            f"{prefix}.sine_line5_shift": float(self.sine_line5_shift),
            f"{prefix}.sine_line6_shift": float(self.sine_line6_shift),
            f"{prefix}.sine_wave_effect": float(self.sine_wave_effect),
            f"{prefix}.sine_vertical_shift": int(self.sine_vertical_shift),
            f"{prefix}.sine_card_adaptation": float(self.sine_card_adaptation),
            f"{prefix}.sine_micro_wobble": float(self.sine_micro_wobble),
            f"{prefix}.sine_crawl_amount": float(self.sine_crawl_amount),
            f"{prefix}.sine_width_reaction": float(self.sine_width_reaction),
            f"{prefix}.rainbow_enabled": self.rainbow_enabled,
            f"{prefix}.rainbow_speed": float(self.rainbow_speed),
            f"{prefix}.osc_ghosting_enabled": self.osc_ghosting_enabled,
            f"{prefix}.osc_ghost_intensity": float(self.osc_ghost_intensity),
            f"{prefix}.osc_ghost_line2_enabled": self.osc_ghost_line2_enabled,
            f"{prefix}.osc_ghost_line3_enabled": self.osc_ghost_line3_enabled,
            f"{prefix}.osc_ghost_line4_enabled": self.osc_ghost_line4_enabled,
            f"{prefix}.osc_ghost_line5_enabled": self.osc_ghost_line5_enabled,
            f"{prefix}.osc_ghost_line6_enabled": self.osc_ghost_line6_enabled,
            f"{prefix}.sine_heartbeat": float(self.sine_heartbeat),
            # Bubble
            f"{prefix}.bubble_big_bass_pulse": float(self.bubble_big_bass_pulse),
            f"{prefix}.bubble_small_freq_pulse": float(self.bubble_small_freq_pulse),
            f"{prefix}.bubble_stream_direction": self.bubble_stream_direction,
            f"{prefix}.bubble_stream_constant_speed": float(self.bubble_stream_constant_speed),
            f"{prefix}.bubble_stream_speed_cap": float(self.bubble_stream_speed_cap),
            f"{prefix}.bubble_stream_reactivity": float(self.bubble_stream_reactivity),
            f"{prefix}.bubble_rotation_amount": float(self.bubble_rotation_amount),
            f"{prefix}.bubble_drift_amount": float(self.bubble_drift_amount),
            f"{prefix}.bubble_drift_speed": float(self.bubble_drift_speed),
            f"{prefix}.bubble_drift_frequency": float(self.bubble_drift_frequency),
            f"{prefix}.bubble_drift_direction": self.bubble_drift_direction,
            f"{prefix}.bubble_big_count": int(self.bubble_big_count),
            f"{prefix}.bubble_small_count": int(self.bubble_small_count),
            f"{prefix}.bubble_surface_reach": float(self.bubble_surface_reach),
            f"{prefix}.bubble_bounce_big_pct": int(self.bubble_bounce_big_pct),
            f"{prefix}.bubble_bounce_small_pct": int(self.bubble_bounce_small_pct),
            f"{prefix}.bubble_bounce_big_speed": float(self.bubble_bounce_big_speed),
            f"{prefix}.bubble_bounce_small_speed": float(self.bubble_bounce_small_speed),
            f"{prefix}.bubble_bounce_same_only": bool(self.bubble_bounce_same_only),
            f"{prefix}.bubble_collision_pop_mode": str(self.bubble_collision_pop_mode),
            f"{prefix}.bubble_outline_color": list(self.bubble_outline_color),
            f"{prefix}.bubble_specular_color": list(self.bubble_specular_color),
            f"{prefix}.bubble_gradient_light": list(self.bubble_gradient_light),
            f"{prefix}.bubble_gradient_dark": list(self.bubble_gradient_dark),
            f"{prefix}.bubble_pop_color": list(self.bubble_pop_color),
            f"{prefix}.bubble_specular_direction": self.bubble_specular_direction,
            f"{prefix}.bubble_gradient_direction": self.bubble_gradient_direction,
            f"{prefix}.bubble_gradient_semantics_version": CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION,
            f"{prefix}.bubble_big_size_max": float(self.bubble_big_size_max),
            f"{prefix}.bubble_small_size_max": float(self.bubble_small_size_max),
            f"{prefix}.bubble_big_contraction_bias": float(self.bubble_big_contraction_bias),
            f"{prefix}.bubble_big_size_clamp": float(self.bubble_big_size_clamp),
            f"{prefix}.bubble_big_specular_max_size": float(self.bubble_big_specular_max_size),
            f"{prefix}.bubble_growth": float(self.bubble_growth),
            f"{prefix}.devcurve_growth": float(self.devcurve_growth),
            f"{prefix}.bubble_trail_strength": float(self.bubble_trail_strength),
            f"{prefix}.bubble_tail_opacity": float(self.bubble_tail_opacity),
            f"{prefix}.bubble_ghosting_enabled": self.bubble_ghosting_enabled,
            f"{prefix}.bubble_ghost_alpha": float(self.bubble_ghost_alpha),
            f"{prefix}.bubble_ghost_decay": float(self.bubble_ghost_decay),
            f"{prefix}.blob_glow_reactivity": float(self.blob_glow_reactivity),
            f"{prefix}.blob_glow_max_size": float(self.blob_glow_max_size),
            f"{prefix}.blob_ghosting_enabled": bool(self.blob_ghosting_enabled),
            f"{prefix}.blob_ghost_alpha": float(self.blob_ghost_alpha),
            f"{prefix}.blob_ghost_decay": float(self.blob_ghost_decay),
            f"{prefix}.blob_shaper_enabled": bool(self.blob_shaper_enabled),
            f"{prefix}.blob_shape_base_nodes": self.blob_shape_base_nodes,
            f"{prefix}.blob_shape_reaction_nodes": self.blob_shape_reaction_nodes,
            f"{prefix}.blob_shape_energy_nodes": list(self.blob_shape_energy_nodes),
            f"{prefix}.blob_shaper_base_strength": float(self.blob_shaper_base_strength),
            f"{prefix}.blob_shaper_react_strength": float(self.blob_shaper_react_strength),
            f"{prefix}.blob_shaper_idle_motion": float(self.blob_shaper_idle_motion),
            f"{prefix}.blob_shaper_audio_motion": float(self.blob_shaper_audio_motion),
            f"{prefix}.blob_topology": str(self.blob_topology),
            f"{prefix}.blob_ring_thickness": float(self.blob_ring_thickness),
            f"{prefix}.blob_inward_liquid_enabled": bool(self.blob_inward_liquid_enabled),
            f"{prefix}.blob_inward_liquid_reactivity": float(self.blob_inward_liquid_reactivity),
            f"{prefix}.blob_inward_liquid_max_size": float(self.blob_inward_liquid_max_size),
            f"{prefix}.blob_inward_liquid_color": list(self.blob_inward_liquid_color),
            f"{prefix}.sine_line_dim": bool(self.sine_line_dim),
        }
        data.update(self._serialize_devcurve_settings(prefix))
        data.update(self._serialize_preset_indices(prefix))
        data.update(self._serialize_per_mode_technical_settings(prefix))
        data.update(self._serialize_transient_mix_settings(prefix))

        return data

    def _serialize_preset_indices(self, prefix: str) -> Dict[str, int]:
        return {
            f"{prefix}.{get_preset_key(mode_id)}": int(getattr(self, get_preset_key(mode_id)))
            for mode_id in VISUALIZER_MODE_IDS
        }

    def _serialize_transient_mix_settings(self, prefix: str) -> Dict[str, float]:
        return {
            f"{prefix}.spectrum_lane_transient_mix": float(self.spectrum_lane_transient_mix),
            f"{prefix}.bubble_transient_mix_bass": float(self.bubble_transient_mix_bass),
            f"{prefix}.bubble_transient_mix_vocal": float(self.bubble_transient_mix_vocal),
            f"{prefix}.blob_transient_mix_bass": float(self.blob_transient_mix_bass),
            f"{prefix}.blob_transient_mix_vocal": float(self.blob_transient_mix_vocal),
            f"{prefix}.sine_wave_transient_width_mix": float(self.sine_wave_transient_width_mix),
            f"{prefix}.oscilloscope_transient_width_mix": float(self.oscilloscope_transient_width_mix),
        }

    def _serialize_per_mode_technical_settings(self, prefix: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        for mode_name in PER_MODE_TECHNICAL_MODES:
            data[f"{prefix}.{mode_name}_bar_fill_color"] = list(getattr(self, f"{mode_name}_bar_fill_color"))
            data[f"{prefix}.{mode_name}_bar_border_color"] = list(getattr(self, f"{mode_name}_bar_border_color"))
            data[f"{prefix}.{mode_name}_bar_border_opacity"] = float(getattr(self, f"{mode_name}_bar_border_opacity"))
            data[f"{prefix}.{mode_name}_dynamic_floor"] = bool(getattr(self, f"{mode_name}_dynamic_floor"))
            data[f"{prefix}.{mode_name}_manual_floor"] = float(getattr(self, f"{mode_name}_manual_floor"))
            data[f"{prefix}.{mode_name}_dynamic_range_enabled"] = bool(getattr(self, f"{mode_name}_dynamic_range_enabled"))
            data[f"{prefix}.{mode_name}_agc_strength"] = float(getattr(self, f"{mode_name}_agc_strength"))
            data[f"{prefix}.{mode_name}_input_gain"] = float(getattr(self, f"{mode_name}_input_gain"))
            data[f"{prefix}.{mode_name}_kick_lane_gain"] = float(getattr(self, f"{mode_name}_kick_lane_gain"))
            data[f"{prefix}.{mode_name}_transient_pulse_gain"] = float(getattr(self, f"{mode_name}_transient_pulse_gain"))
            data[f"{prefix}.{mode_name}_transient_clamp"] = float(getattr(self, f"{mode_name}_transient_clamp"))
            data[f"{prefix}.{mode_name}_audio_block_size"] = int(getattr(self, f"{mode_name}_audio_block_size"))
            data[f"{prefix}.{mode_name}_adaptive_sensitivity"] = bool(getattr(self, f"{mode_name}_adaptive_sensitivity"))
            data[f"{prefix}.{mode_name}_sensitivity"] = float(getattr(self, f"{mode_name}_sensitivity"))
            data[f"{prefix}.{mode_name}_bar_count"] = int(getattr(self, f"{mode_name}_bar_count"))
        return data

    def _serialize_devcurve_settings(self, prefix: str) -> Dict[str, Any]:
        return {
            f"{prefix}.devcurve_active_layer": str(self.devcurve_active_layer),
            f"{prefix}.devcurve_layer_bass_shape_nodes": list(self.devcurve_layer_bass_shape_nodes),
            f"{prefix}.devcurve_layer_vocals_shape_nodes": list(self.devcurve_layer_vocals_shape_nodes),
            f"{prefix}.devcurve_layer_mids_shape_nodes": list(self.devcurve_layer_mids_shape_nodes),
            f"{prefix}.devcurve_layer_transients_shape_nodes": list(self.devcurve_layer_transients_shape_nodes),
            f"{prefix}.devcurve_base_level": float(self.devcurve_base_level),
            f"{prefix}.devcurve_motion_power": float(self.devcurve_motion_power),
            f"{prefix}.devcurve_idle_motion": float(self.devcurve_idle_motion),
            f"{prefix}.devcurve_idle_speed": float(self.devcurve_idle_speed),
            f"{prefix}.devcurve_smoothness": float(self.devcurve_smoothness),
            f"{prefix}.devcurve_layer_bass_enabled": bool(self.devcurve_layer_bass_enabled),
            f"{prefix}.devcurve_layer_bass_color": list(self.devcurve_layer_bass_color),
            f"{prefix}.devcurve_layer_bass_alpha": float(self.devcurve_layer_bass_alpha),
            f"{prefix}.devcurve_layer_bass_power": float(self.devcurve_layer_bass_power),
            f"{prefix}.devcurve_layer_bass_offset": float(self.devcurve_layer_bass_offset),
            f"{prefix}.devcurve_layer_bass_outline_color": _serialize_outline_rgb(self.devcurve_layer_bass_outline_color),
            f"{prefix}.devcurve_layer_bass_outline_width": float(self.devcurve_layer_bass_outline_width),
            f"{prefix}.devcurve_layer_bass_order": int(self.devcurve_layer_bass_order),
            f"{prefix}.devcurve_layer_vocals_enabled": bool(self.devcurve_layer_vocals_enabled),
            f"{prefix}.devcurve_layer_vocals_color": list(self.devcurve_layer_vocals_color),
            f"{prefix}.devcurve_layer_vocals_alpha": float(self.devcurve_layer_vocals_alpha),
            f"{prefix}.devcurve_layer_vocals_power": float(self.devcurve_layer_vocals_power),
            f"{prefix}.devcurve_layer_vocals_offset": float(self.devcurve_layer_vocals_offset),
            f"{prefix}.devcurve_layer_vocals_outline_color": _serialize_outline_rgb(self.devcurve_layer_vocals_outline_color),
            f"{prefix}.devcurve_layer_vocals_outline_width": float(self.devcurve_layer_vocals_outline_width),
            f"{prefix}.devcurve_layer_vocals_order": int(self.devcurve_layer_vocals_order),
            f"{prefix}.devcurve_layer_mids_enabled": bool(self.devcurve_layer_mids_enabled),
            f"{prefix}.devcurve_layer_mids_color": list(self.devcurve_layer_mids_color),
            f"{prefix}.devcurve_layer_mids_alpha": float(self.devcurve_layer_mids_alpha),
            f"{prefix}.devcurve_layer_mids_power": float(self.devcurve_layer_mids_power),
            f"{prefix}.devcurve_layer_mids_offset": float(self.devcurve_layer_mids_offset),
            f"{prefix}.devcurve_layer_mids_outline_color": _serialize_outline_rgb(self.devcurve_layer_mids_outline_color),
            f"{prefix}.devcurve_layer_mids_outline_width": float(self.devcurve_layer_mids_outline_width),
            f"{prefix}.devcurve_layer_mids_order": int(self.devcurve_layer_mids_order),
            f"{prefix}.devcurve_layer_transients_enabled": bool(self.devcurve_layer_transients_enabled),
            f"{prefix}.devcurve_layer_transients_color": list(self.devcurve_layer_transients_color),
            f"{prefix}.devcurve_layer_transients_alpha": float(self.devcurve_layer_transients_alpha),
            f"{prefix}.devcurve_layer_transients_power": float(self.devcurve_layer_transients_power),
            f"{prefix}.devcurve_layer_transients_offset": float(self.devcurve_layer_transients_offset),
            f"{prefix}.devcurve_layer_transients_outline_color": _serialize_outline_rgb(self.devcurve_layer_transients_outline_color),
            f"{prefix}.devcurve_layer_transients_outline_width": float(self.devcurve_layer_transients_outline_width),
            f"{prefix}.devcurve_layer_transients_order": int(self.devcurve_layer_transients_order),
            f"{prefix}.devcurve_ghosting_enabled": self.devcurve_ghosting_enabled,
            f"{prefix}.devcurve_ghost_alpha": float(self.devcurve_ghost_alpha),
            f"{prefix}.devcurve_ghost_decay": float(self.devcurve_ghost_decay),
            f"{prefix}.devcurve_foreground_shadow_enabled": bool(self.devcurve_foreground_shadow_enabled),
            f"{prefix}.devcurve_foreground_shadow_alpha": float(self.devcurve_foreground_shadow_alpha),
            f"{prefix}.devcurve_foreground_shadow_darken": float(self.devcurve_foreground_shadow_darken),
            f"{prefix}.devcurve_foreground_shadow_offset": float(self.devcurve_foreground_shadow_offset),
            f"{prefix}.devcurve_foreground_specular_enabled": bool(self.devcurve_foreground_specular_enabled),
            f"{prefix}.devcurve_foreground_specular_alpha": float(self.devcurve_foreground_specular_alpha),
            f"{prefix}.devcurve_foreground_specular_width": float(self.devcurve_foreground_specular_width),
            f"{prefix}.devcurve_foreground_specular_offset": float(self.devcurve_foreground_specular_offset),
            f"{prefix}.devcurve_foreground_specular_crest_bias": float(self.devcurve_foreground_specular_crest_bias),
        }

    @staticmethod
    def _normalize_mode_name(mode: str) -> str:
        mode_key = str(mode).lower()
        if mode_key in PER_MODE_TECHNICAL_MODES:
            return mode_key
        return PER_MODE_TECHNICAL_MODES[0]

    def _mode_attr_name(self, mode: str, base_key: str) -> str:
        normalized = self._normalize_mode_name(mode)
        return f"{normalized}_{base_key}"

    def resolve_dynamic_floor(self, mode: str) -> bool:
        return bool(getattr(self, self._mode_attr_name(mode, "dynamic_floor")))

    def resolve_manual_floor(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "manual_floor")))

    def resolve_dynamic_range_enabled(self, mode: str) -> bool:
        return bool(getattr(self, self._mode_attr_name(mode, "dynamic_range_enabled")))

    def resolve_agc_strength(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "agc_strength")))

    def resolve_input_gain(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "input_gain")))

    def resolve_kick_lane_gain(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "kick_lane_gain"), 1.0))

    def resolve_transient_pulse_gain(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "transient_pulse_gain"), 1.0))

    def resolve_transient_clamp(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "transient_clamp"), 1.5))

    def resolve_audio_block_size(self, mode: str) -> int:
        return int(getattr(self, self._mode_attr_name(mode, "audio_block_size")))

    def resolve_adaptive_sensitivity(self, mode: str) -> bool:
        return bool(getattr(self, self._mode_attr_name(mode, "adaptive_sensitivity")))

    def resolve_sensitivity(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "sensitivity")))

    def resolve_bar_count(self, mode: str) -> int:
        return int(getattr(self, self._mode_attr_name(mode, "bar_count")))

    def resolve_bar_fill_color(self, mode: str) -> list:
        return list(getattr(self, self._mode_attr_name(mode, "bar_fill_color")))

    def resolve_bar_border_color(self, mode: str) -> list:
        return list(getattr(self, self._mode_attr_name(mode, "bar_border_color")))

    def resolve_bar_border_opacity(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "bar_border_opacity")))

    def resolve_spectrum_lane_transient_mix(self) -> float:
        return float(self.spectrum_lane_transient_mix)

    def resolve_bubble_transient_mix_bass(self) -> float:
        return float(self.bubble_transient_mix_bass)

    def resolve_bubble_transient_mix_vocal(self) -> float:
        return float(self.bubble_transient_mix_vocal)

    def resolve_blob_transient_mix_bass(self) -> float:
        return float(self.blob_transient_mix_bass)

    def resolve_blob_transient_mix_vocal(self) -> float:
        return float(self.blob_transient_mix_vocal)

    def resolve_sine_wave_transient_width_mix(self) -> float:
        return float(self.sine_wave_transient_width_mix)

    def resolve_oscilloscope_transient_width_mix(self) -> float:
        return float(self.oscilloscope_transient_width_mix)

