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


_PER_MODE_TECHNICAL_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "bar_fill_color": list,
    "bar_border_color": list,
    "bar_border_opacity": float,
    "dynamic_floor": bool,
    "manual_floor": float,
    "dynamic_range_enabled": bool,
    "agc_strength": float,
    "input_gain": float,
    "kick_lane_gain": float,
    "transient_pulse_gain": float,
    "transient_clamp": float,
    "audio_block_size": int,
    "adaptive_sensitivity": bool,
    "sensitivity": float,
    "bar_count": int,
}

_PER_MODE_RESOLVERS: Dict[str, Callable[[Any], Any]] = {
    "dynamic_floor": bool,
    "manual_floor": float,
    "dynamic_range_enabled": bool,
    "agc_strength": float,
    "input_gain": float,
    "kick_lane_gain": lambda value: float(value if value is not None else 1.0),
    "transient_pulse_gain": lambda value: float(value if value is not None else 1.0),
    "transient_clamp": lambda value: float(value if value is not None else 1.5),
    "audio_block_size": int,
    "adaptive_sensitivity": bool,
    "sensitivity": float,
    "bar_count": int,
    "bar_fill_color": list,
    "bar_border_color": list,
    "bar_border_opacity": float,
}

_CORE_SETTINGS_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "enabled": bool,
    "visualizers_enabled": bool,
    "monitor": str,
    "position": str,
    "mode": str,
    "rainbow_enabled": bool,
    "rainbow_speed": float,
    "sine_line_dim": bool,
}

_TRANSIENT_MIX_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "spectrum_lane_transient_mix": float,
    "bubble_transient_mix_bass": float,
    "bubble_transient_mix_vocal": float,
    "blob_transient_mix_bass": float,
    "blob_transient_mix_vocal": float,
    "sine_wave_transient_width_mix": float,
    "oscilloscope_transient_width_mix": float,
}

_BLOB_SHAPE_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "blob_shaper_enabled": bool,
    "blob_shape_base_nodes": lambda value: value,
    "blob_shape_reaction_nodes": lambda value: value,
    "blob_shape_energy_nodes": list,
    "blob_shaper_base_strength": float,
    "blob_shaper_react_strength": float,
    "blob_shaper_idle_motion": float,
    "blob_shaper_audio_motion": float,
    "blob_topology": str,
    "blob_ring_thickness": float,
    "blob_inward_liquid_enabled": bool,
    "blob_inward_liquid_reactivity": float,
    "blob_inward_liquid_max_size": float,
    "blob_inward_liquid_color": list,
}

_OSC_BLOB_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "osc_glow_enabled": bool,
    "osc_glow_intensity": float,
    "osc_glow_reactivity": float,
    "osc_glow_color": list,
    "osc_reactive_glow": bool,
    "osc_line_amplitude": float,
    "osc_smoothing": float,
    "blob_color": list,
    "blob_glow_color": list,
    "blob_edge_color": list,
    "blob_outline_color": list,
    "blob_pulse": float,
    "blob_pulse_release_ms": int,
    "blob_width": float,
    "blob_size": float,
    "blob_glow_intensity": float,
    "blob_reactive_glow": bool,
    "blob_glow_drive_mode": str,
    "osc_line_color": list,
    "osc_line_count": int,
    "osc_line2_color": list,
    "osc_line2_glow_color": list,
    "osc_line3_color": list,
    "osc_line3_glow_color": list,
    "osc_line4_color": list,
    "osc_line4_glow_color": list,
    "osc_line5_color": list,
    "osc_line5_glow_color": list,
    "osc_line6_color": list,
    "osc_line6_glow_color": list,
    "spectrum_growth": float,
    "blob_growth": float,
    "osc_speed": float,
    "osc_line_dim": bool,
    "osc_line_offset_bias": float,
    "osc_vertical_shift": int,
    "osc_growth": float,
    "blob_reactive_deformation": float,
    "blob_constant_wobble": float,
    "blob_reactive_wobble": float,
    "blob_stretch": float,
    "blob_stage_gain": float,
    "blob_core_scale": float,
    "blob_core_floor_bias": float,
    "blob_stage_bias": float,
    "blob_stretch_tendency": float,
    "blob_stretch_inner": float,
    "blob_stretch_outer": float,
}

_SPECTRUM_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "spectrum_render_mode": str,
    "spectrum_unique_colors": bool,
    "spectrum_rainbow_border": bool,
    "spectrum_border_radius": float,
    "spectrum_link_fill_border": bool,
    "spectrum_glow_enabled": bool,
    "spectrum_glow_intensity": float,
    "spectrum_glow_color": list,
    "spectrum_ghosting_enabled": bool,
    "spectrum_ghost_alpha": float,
    "spectrum_ghost_decay": float,
    "spectrum_mirrored": bool,
    "spectrum_shape_nodes": lambda value: value,
    "spectrum_notch_positions_mirrored": lambda value: value,
    "spectrum_notch_positions_linear": lambda value: value,
    "spectrum_lane_strengths_mirrored": dict,
    "spectrum_lane_strengths_linear": dict,
    "spectrum_wave_amplitude": float,
    "spectrum_profile_floor": float,
    "spectrum_drop_speed": float,
}

_SINE_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "sine_wave_growth": float,
    "sine_wave_travel": int,
    "sine_density": float,
    "sine_displacement": float,
    "sine_glow_enabled": bool,
    "sine_glow_intensity": float,
    "sine_glow_reactivity": float,
    "sine_glow_color": list,
    "sine_line_color": list,
    "sine_reactive_glow": bool,
    "sine_ghosting_enabled": bool,
    "sine_ghost_alpha": float,
    "sine_ghost_decay": float,
    "sine_ghost_line2_enabled": bool,
    "sine_ghost_line3_enabled": bool,
    "sine_ghost_line4_enabled": bool,
    "sine_ghost_line5_enabled": bool,
    "sine_ghost_line6_enabled": bool,
    "sine_sensitivity": float,
    "sine_smoothing": float,
    "sine_speed": float,
    "sine_line_count": int,
    "sine_line_offset_bias": float,
    "sine_line2_color": list,
    "sine_line2_glow_color": list,
    "sine_line3_color": list,
    "sine_line3_glow_color": list,
    "sine_line4_color": list,
    "sine_line4_glow_color": list,
    "sine_line5_color": list,
    "sine_line5_glow_color": list,
    "sine_line6_color": list,
    "sine_line6_glow_color": list,
    "sine_travel_line2": int,
    "sine_travel_line3": int,
    "sine_travel_line4": int,
    "sine_travel_line5": int,
    "sine_travel_line6": int,
    "sine_line1_shift": float,
    "sine_line2_shift": float,
    "sine_line3_shift": float,
    "sine_line4_shift": float,
    "sine_line5_shift": float,
    "sine_line6_shift": float,
    "sine_wave_effect": float,
    "sine_vertical_shift": int,
    "sine_card_adaptation": float,
    "sine_micro_wobble": float,
    "sine_crawl_amount": float,
    "sine_width_reaction": float,
    "osc_ghosting_enabled": bool,
    "osc_ghost_intensity": float,
    "osc_ghost_line2_enabled": bool,
    "osc_ghost_line3_enabled": bool,
    "osc_ghost_line4_enabled": bool,
    "osc_ghost_line5_enabled": bool,
    "osc_ghost_line6_enabled": bool,
    "sine_heartbeat": float,
}

_BUBBLE_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "bubble_big_bass_pulse": float,
    "bubble_small_freq_pulse": float,
    "bubble_stream_direction": lambda value: value,
    "bubble_stream_constant_speed": float,
    "bubble_stream_speed_cap": float,
    "bubble_stream_reactivity": float,
    "bubble_rotation_amount": float,
    "bubble_drift_amount": float,
    "bubble_drift_speed": float,
    "bubble_drift_frequency": float,
    "bubble_drift_direction": lambda value: value,
    "bubble_big_count": int,
    "bubble_small_count": int,
    "bubble_surface_reach": float,
    "bubble_bounce_big_pct": int,
    "bubble_bounce_small_pct": int,
    "bubble_bounce_big_speed": float,
    "bubble_bounce_small_speed": float,
    "bubble_bounce_same_only": bool,
    "bubble_collision_pop_mode": str,
    "bubble_outline_color": list,
    "bubble_specular_color": list,
    "bubble_gradient_light": list,
    "bubble_gradient_dark": list,
    "bubble_pop_color": list,
    "bubble_specular_direction": lambda value: value,
    "bubble_gradient_direction": lambda value: value,
    "bubble_big_size_max": float,
    "bubble_small_size_max": float,
    "bubble_big_contraction_bias": float,
    "bubble_big_size_clamp": float,
    "bubble_big_specular_max_size": float,
    "bubble_growth": float,
    "devcurve_growth": float,
    "bubble_trail_strength": float,
    "bubble_tail_opacity": float,
    "bubble_ghosting_enabled": bool,
    "bubble_ghost_alpha": float,
    "bubble_ghost_decay": float,
    "blob_glow_reactivity": float,
    "blob_glow_max_size": float,
    "blob_ghosting_enabled": bool,
    "blob_ghost_alpha": float,
    "blob_ghost_decay": float,
}

_CORE_BUILD_SPECS: Dict[str, Tuple[Any, Callable[[Any], Any]]] = {
    "enabled": (False, bool),
    "visualizers_enabled": (True, bool),
    "monitor": ("ALL", str),
    "position": ("Follow Media", str),
    "ghosting_enabled": (True, bool),
    "ghost_alpha": (0.4, float),
    "ghost_decay": (0.35, float),
    "sine_line_dim": (False, bool),
}

_SPECTRUM_BUILD_SPECS: Dict[str, Tuple[Any, Callable[[Any], Any]]] = {
    "spectrum_rainbow_border": (False, bool),
    "spectrum_border_radius": (0.0, float),
    "spectrum_link_fill_border": (False, bool),
    "spectrum_glow_enabled": (False, bool),
    "spectrum_glow_intensity": (0.55, float),
    "spectrum_glow_color": ([110, 220, 255, 235], list),
    "spectrum_ghosting_enabled": (True, bool),
    "spectrum_ghost_alpha": (0.4, float),
    "spectrum_ghost_decay": (0.35, float),
    "spectrum_mirrored": (True, bool),
    "spectrum_shape_nodes": ([[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]], list),
    "spectrum_notch_positions_mirrored": ([[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]], list),
    "spectrum_wave_amplitude": (0.50, float),
    "spectrum_profile_floor": (0.12, float),
    "spectrum_drop_speed": (1.0, float),
}

_BUBBLE_BUILD_SPECS: Dict[str, Tuple[Any, Callable[[Any], Any]]] = {
    "bubble_big_bass_pulse": (0.5, float),
    "bubble_small_freq_pulse": (0.5, float),
    "bubble_stream_direction": ("up", str),
    "bubble_stream_reactivity": (0.5, float),
    "bubble_rotation_amount": (0.5, float),
    "bubble_drift_amount": (0.5, float),
    "bubble_drift_speed": (0.5, float),
    "bubble_drift_frequency": (0.5, float),
    "bubble_drift_direction": ("random", str),
    "bubble_big_count": (8, int),
    "bubble_small_count": (25, int),
    "bubble_surface_reach": (0.6, float),
    "bubble_bounce_big_pct": (70, int),
    "bubble_bounce_small_pct": (30, int),
    "bubble_bounce_big_speed": (0.8, float),
    "bubble_bounce_small_speed": (0.5, float),
    "bubble_bounce_same_only": (False, bool),
    "bubble_outline_color": ([255, 255, 255, 230], list),
    "bubble_specular_color": ([255, 255, 255, 255], list),
    "bubble_gradient_light": ([210, 170, 120, 255], list),
    "bubble_gradient_dark": ([80, 60, 50, 255], list),
    "bubble_pop_color": ([255, 255, 255, 180], list),
    "bubble_big_size_max": (0.038, float),
    "bubble_small_size_max": (0.018, float),
    "bubble_big_contraction_bias": (1.0, float),
    "bubble_big_size_clamp": (4.0, float),
    "bubble_big_specular_max_size": (2.5, float),
    "bubble_growth": (3.0, float),
    "devcurve_growth": (3.0, float),
    "bubble_trail_strength": (0.0, float),
    "bubble_tail_opacity": (0.0, float),
    "bubble_ghosting_enabled": (False, bool),
    "bubble_ghost_alpha": (0.0, float),
    "bubble_ghost_decay": (0.4, float),
    "blob_glow_reactivity": (1.0, float),
    "blob_glow_max_size": (1.0, float),
    "blob_ghosting_enabled": (False, bool),
    "blob_ghost_alpha": (0.4, float),
    "blob_ghost_decay": (0.3, float),
}

_OSC_BLOB_BUILD_SPECS: Dict[str, Tuple[Any, Callable[[Any], Any]]] = {
    "osc_glow_enabled": (False, bool),
    "osc_glow_intensity": (1.0, float),
    "osc_glow_reactivity": (1.0, float),
    "osc_glow_color": ([0, 200, 255, 230], list),
    "osc_reactive_glow": (True, bool),
    "osc_line_amplitude": (1.0, float),
    "osc_smoothing": (0.7, float),
    "blob_color": ([255, 255, 255, 255], list),
    "blob_glow_color": ([0, 200, 255, 230], list),
    "blob_edge_color": ([255, 255, 255, 255], list),
    "blob_outline_color": ([255, 255, 255, 255], list),
    "blob_pulse": (0.5, float),
    "blob_pulse_release_ms": (250, int),
    "blob_width": (1.0, float),
    "blob_size": (1.0, float),
    "blob_glow_intensity": (1.0, float),
    "blob_reactive_glow": (True, bool),
    "blob_glow_drive_mode": ("bass", str),
    "osc_line_color": ([255, 255, 255, 255], list),
    "osc_line_count": (1, int),
    "osc_line2_color": ([255, 120, 50, 230], list),
    "osc_line2_glow_color": ([255, 120, 50, 180], list),
    "osc_line3_color": ([50, 255, 120, 230], list),
    "osc_line3_glow_color": ([50, 255, 120, 180], list),
    "osc_line4_color": ([255, 0, 150, 230], list),
    "osc_line4_glow_color": ([255, 0, 150, 180], list),
    "osc_line5_color": ([0, 255, 200, 230], list),
    "osc_line5_glow_color": ([0, 255, 200, 180], list),
    "osc_line6_color": ([200, 100, 255, 230], list),
    "osc_line6_glow_color": ([200, 100, 255, 180], list),
    "spectrum_growth": (1.0, float),
    "blob_growth": (2.5, float),
    "osc_speed": (1.0, float),
    "osc_line_dim": (False, bool),
    "osc_line_offset_bias": (0.0, float),
    "osc_vertical_shift": (0, int),
    "osc_growth": (1.0, float),
    "blob_reactive_deformation": (1.0, float),
    "blob_constant_wobble": (1.0, float),
    "blob_reactive_wobble": (1.0, float),
    "blob_stretch": (0.35, float),
    "blob_stage_gain": (1.0, float),
    "blob_core_scale": (1.0, float),
    "blob_core_floor_bias": (0.35, float),
    "blob_stage_bias": (0.0, float),
    "blob_stretch_inner": (0.0, float),
}

_SINE_BUILD_SPECS: Dict[str, Tuple[Any, Callable[[Any], Any]]] = {
    "sine_wave_growth": (1.0, float),
    "sine_wave_travel": (0, int),
    "sine_density": (1.0, float),
    "sine_displacement": (0.0, float),
    "sine_glow_enabled": (True, bool),
    "sine_glow_intensity": (0.5, float),
    "sine_glow_color": ([0, 200, 255, 230], list),
    "sine_line_color": ([255, 255, 255, 255], list),
    "sine_reactive_glow": (True, bool),
    "sine_ghosting_enabled": (True, bool),
    "sine_ghost_alpha": (0.45, float),
    "sine_ghost_decay": (0.3, float),
    "sine_ghost_line2_enabled": (True, bool),
    "sine_ghost_line3_enabled": (True, bool),
    "sine_ghost_line4_enabled": (True, bool),
    "sine_ghost_line5_enabled": (True, bool),
    "sine_ghost_line6_enabled": (True, bool),
    "sine_sensitivity": (1.0, float),
    "sine_smoothing": (0.7, float),
    "sine_speed": (1.0, float),
    "sine_line_count": (1, int),
    "sine_line_offset_bias": (0.0, float),
    "sine_line2_color": ([255, 255, 255, 230], list),
    "sine_line2_glow_color": ([7, 114, 255, 180], list),
    "sine_line3_color": ([255, 255, 255, 230], list),
    "sine_line3_glow_color": ([14, 159, 255, 180], list),
    "sine_line4_color": ([255, 120, 50, 230], list),
    "sine_line4_glow_color": ([255, 120, 50, 180], list),
    "sine_line5_color": ([50, 255, 120, 230], list),
    "sine_line5_glow_color": ([50, 255, 120, 180], list),
    "sine_line6_color": ([255, 0, 150, 230], list),
    "sine_line6_glow_color": ([255, 0, 150, 180], list),
    "sine_travel_line2": (0, int),
    "sine_travel_line3": (0, int),
    "sine_travel_line4": (0, int),
    "sine_travel_line5": (0, int),
    "sine_travel_line6": (0, int),
    "sine_line1_shift": (0.0, float),
    "sine_line2_shift": (0.0, float),
    "sine_line3_shift": (0.0, float),
    "sine_line4_shift": (0.0, float),
    "sine_line5_shift": (0.0, float),
    "sine_line6_shift": (0.0, float),
    "sine_vertical_shift": (0, int),
    "sine_card_adaptation": (0.3, float),
    "sine_micro_wobble": (0.0, float),
    "sine_crawl_amount": (0.25, float),
    "sine_width_reaction": (0.0, float),
    "osc_ghosting_enabled": (False, bool),
    "osc_ghost_intensity": (0.4, float),
    "osc_ghost_line2_enabled": (True, bool),
    "osc_ghost_line3_enabled": (True, bool),
    "osc_ghost_line4_enabled": (True, bool),
    "osc_ghost_line5_enabled": (True, bool),
    "osc_ghost_line6_enabled": (True, bool),
    "sine_heartbeat": (0.0, float),
}

_BLOB_SHAPE_BUILD_SPECS: Dict[str, Tuple[Any, Callable[[Any], Any]]] = {
    "blob_shaper_enabled": (False, bool),
    "blob_shape_base_nodes": ([[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]], list),
    "blob_shape_reaction_nodes": ([[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]], list),
    "blob_shape_energy_nodes": ([], list),
    "blob_shaper_base_strength": (0.5, float),
    "blob_shaper_react_strength": (0.5, float),
    "blob_shaper_idle_motion": (0.18, float),
    "blob_shaper_audio_motion": (1.20, float),
    "blob_topology": ("circle", str),
    "blob_ring_thickness": (0.3, float),
    "blob_inward_liquid_enabled": (False, bool),
    "blob_inward_liquid_reactivity": (1.0, float),
    "blob_inward_liquid_max_size": (0.28, float),
    "blob_inward_liquid_color": ([170, 225, 255, 190], list),
}


_OSCILLOSCOPE_COLOR_DEFAULTS: Dict[str, list[int]] = {
    "osc_line_color": [255, 255, 255, 255],
    "osc_line2_color": [255, 120, 50, 230],
    "osc_line2_glow_color": [255, 120, 50, 180],
    "osc_line3_color": [50, 255, 120, 230],
    "osc_line3_glow_color": [50, 255, 120, 180],
    "osc_line4_color": [255, 0, 150, 230],
    "osc_line4_glow_color": [255, 0, 150, 180],
    "osc_line5_color": [0, 255, 200, 230],
    "osc_line5_glow_color": [0, 255, 200, 180],
    "osc_line6_color": [200, 100, 255, 230],
    "osc_line6_glow_color": [200, 100, 255, 180],
}

_SINE_COLOR_DEFAULTS: Dict[str, list[int]] = {
    "sine_glow_color": [0, 200, 255, 230],
    "sine_line_color": [255, 255, 255, 255],
    "sine_line2_color": [255, 255, 255, 230],
    "sine_line2_glow_color": [7, 114, 255, 180],
    "sine_line3_color": [255, 255, 255, 230],
    "sine_line3_glow_color": [14, 159, 255, 180],
    "sine_line4_color": [255, 120, 50, 230],
    "sine_line4_glow_color": [255, 120, 50, 180],
    "sine_line5_color": [50, 255, 120, 230],
    "sine_line5_glow_color": [50, 255, 120, 180],
    "sine_line6_color": [255, 0, 150, 230],
    "sine_line6_glow_color": [255, 0, 150, 180],
}

_BUBBLE_COLOR_DEFAULTS: Dict[str, list[int]] = {
    "bubble_outline_color": [255, 255, 255, 230],
    "bubble_specular_color": [255, 255, 255, 255],
    "bubble_gradient_light": [210, 170, 120, 255],
    "bubble_gradient_dark": [80, 60, 50, 255],
    "bubble_pop_color": [255, 255, 255, 180],
}

_DEVCURVE_COLOR_DEFAULTS: Dict[str, list[int]] = {
    "devcurve_layer_bass_color": [82, 167, 255, 230],
    "devcurve_layer_vocals_color": [136, 190, 255, 220],
    "devcurve_layer_mids_color": [100, 145, 255, 220],
    "devcurve_layer_transients_color": [215, 240, 255, 240],
    "devcurve_layer_bass_outline_color": [255, 255, 255, 255],
    "devcurve_layer_vocals_outline_color": [255, 255, 255, 255],
    "devcurve_layer_mids_outline_color": [255, 255, 255, 255],
    "devcurve_layer_transients_outline_color": [255, 255, 255, 255],
}

_DEVCURVE_DEFAULT_SHAPE_NODES: list[list[float]] = [
    [0.0, 0.58],
    [0.35, 0.64],
    [0.70, 0.52],
    [1.0, 0.60],
]

_DEVCURVE_BUILD_SPECS: Dict[str, Tuple[Any, Callable[[Any], Any]]] = {
    "devcurve_active_layer": ("bass", str),
    "devcurve_layer_bass_shape_nodes": (_DEVCURVE_DEFAULT_SHAPE_NODES, list),
    "devcurve_layer_vocals_shape_nodes": (_DEVCURVE_DEFAULT_SHAPE_NODES, list),
    "devcurve_layer_mids_shape_nodes": (_DEVCURVE_DEFAULT_SHAPE_NODES, list),
    "devcurve_layer_transients_shape_nodes": (_DEVCURVE_DEFAULT_SHAPE_NODES, list),
    "devcurve_base_level": (0.58, float),
    "devcurve_motion_power": (1.0, float),
    "devcurve_idle_motion": (0.20, float),
    "devcurve_idle_speed": (0.60, float),
    "devcurve_smoothness": (0.55, float),
    "devcurve_layer_bass_enabled": (True, bool),
    "devcurve_layer_bass_color": (_DEVCURVE_COLOR_DEFAULTS["devcurve_layer_bass_color"], list),
    "devcurve_layer_bass_alpha": (0.55, float),
    "devcurve_layer_bass_power": (1.0, float),
    "devcurve_layer_bass_offset": (0.0, float),
    "devcurve_layer_bass_outline_color": (_DEVCURVE_COLOR_DEFAULTS["devcurve_layer_bass_outline_color"], list),
    "devcurve_layer_bass_outline_width": (0.006, float),
    "devcurve_layer_bass_order": (1, int),
    "devcurve_layer_vocals_enabled": (True, bool),
    "devcurve_layer_vocals_color": (_DEVCURVE_COLOR_DEFAULTS["devcurve_layer_vocals_color"], list),
    "devcurve_layer_vocals_alpha": (0.42, float),
    "devcurve_layer_vocals_power": (1.0, float),
    "devcurve_layer_vocals_offset": (-0.01, float),
    "devcurve_layer_vocals_outline_color": (_DEVCURVE_COLOR_DEFAULTS["devcurve_layer_vocals_outline_color"], list),
    "devcurve_layer_vocals_outline_width": (0.006, float),
    "devcurve_layer_vocals_order": (2, int),
    "devcurve_layer_mids_enabled": (True, bool),
    "devcurve_layer_mids_color": (_DEVCURVE_COLOR_DEFAULTS["devcurve_layer_mids_color"], list),
    "devcurve_layer_mids_alpha": (0.46, float),
    "devcurve_layer_mids_power": (1.0, float),
    "devcurve_layer_mids_offset": (0.01, float),
    "devcurve_layer_mids_outline_color": (_DEVCURVE_COLOR_DEFAULTS["devcurve_layer_mids_outline_color"], list),
    "devcurve_layer_mids_outline_width": (0.006, float),
    "devcurve_layer_mids_order": (3, int),
    "devcurve_layer_transients_enabled": (True, bool),
    "devcurve_layer_transients_color": (_DEVCURVE_COLOR_DEFAULTS["devcurve_layer_transients_color"], list),
    "devcurve_layer_transients_alpha": (0.66, float),
    "devcurve_layer_transients_power": (1.15, float),
    "devcurve_layer_transients_offset": (0.0, float),
    "devcurve_layer_transients_outline_color": (_DEVCURVE_COLOR_DEFAULTS["devcurve_layer_transients_outline_color"], list),
    "devcurve_layer_transients_outline_width": (0.006, float),
    "devcurve_layer_transients_order": (4, int),
    "devcurve_ghosting_enabled": (False, bool),
    "devcurve_ghost_alpha": (0.0, float),
    "devcurve_ghost_decay": (0.4, float),
    "devcurve_foreground_shadow_enabled": (False, bool),
    "devcurve_foreground_shadow_alpha": (0.36, float),
    "devcurve_foreground_shadow_darken": (0.42, float),
    "devcurve_foreground_shadow_offset": (0.10, float),
    "devcurve_foreground_specular_enabled": (False, bool),
    "devcurve_foreground_specular_alpha": (0.78, float),
    "devcurve_foreground_specular_width": (0.022, float),
    "devcurve_foreground_specular_offset": (0.028, float),
    "devcurve_foreground_specular_crest_bias": (1.05, float),
}

_DEVCURVE_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "devcurve_active_layer": str,
    "devcurve_layer_bass_shape_nodes": list,
    "devcurve_layer_vocals_shape_nodes": list,
    "devcurve_layer_mids_shape_nodes": list,
    "devcurve_layer_transients_shape_nodes": list,
    "devcurve_base_level": float,
    "devcurve_motion_power": float,
    "devcurve_idle_motion": float,
    "devcurve_idle_speed": float,
    "devcurve_smoothness": float,
    "devcurve_layer_bass_enabled": bool,
    "devcurve_layer_bass_color": list,
    "devcurve_layer_bass_alpha": float,
    "devcurve_layer_bass_power": float,
    "devcurve_layer_bass_offset": float,
    "devcurve_layer_bass_outline_color": lambda value: _serialize_outline_rgb(value),
    "devcurve_layer_bass_outline_width": float,
    "devcurve_layer_bass_order": int,
    "devcurve_layer_vocals_enabled": bool,
    "devcurve_layer_vocals_color": list,
    "devcurve_layer_vocals_alpha": float,
    "devcurve_layer_vocals_power": float,
    "devcurve_layer_vocals_offset": float,
    "devcurve_layer_vocals_outline_color": lambda value: _serialize_outline_rgb(value),
    "devcurve_layer_vocals_outline_width": float,
    "devcurve_layer_vocals_order": int,
    "devcurve_layer_mids_enabled": bool,
    "devcurve_layer_mids_color": list,
    "devcurve_layer_mids_alpha": float,
    "devcurve_layer_mids_power": float,
    "devcurve_layer_mids_offset": float,
    "devcurve_layer_mids_outline_color": lambda value: _serialize_outline_rgb(value),
    "devcurve_layer_mids_outline_width": float,
    "devcurve_layer_mids_order": int,
    "devcurve_layer_transients_enabled": bool,
    "devcurve_layer_transients_color": list,
    "devcurve_layer_transients_alpha": float,
    "devcurve_layer_transients_power": float,
    "devcurve_layer_transients_offset": float,
    "devcurve_layer_transients_outline_color": lambda value: _serialize_outline_rgb(value),
    "devcurve_layer_transients_outline_width": float,
    "devcurve_layer_transients_order": int,
    "devcurve_ghosting_enabled": bool,
    "devcurve_ghost_alpha": float,
    "devcurve_ghost_decay": float,
    "devcurve_foreground_shadow_enabled": bool,
    "devcurve_foreground_shadow_alpha": float,
    "devcurve_foreground_shadow_darken": float,
    "devcurve_foreground_shadow_offset": float,
    "devcurve_foreground_specular_enabled": bool,
    "devcurve_foreground_specular_alpha": float,
    "devcurve_foreground_specular_width": float,
    "devcurve_foreground_specular_offset": float,
    "devcurve_foreground_specular_crest_bias": float,
}

_DEVCURVE_ACTIVE_LAYERS = {"bass", "vocals", "mids", "transients"}
_DEVCURVE_OUTLINE_WIDTH_LIMITS: Dict[str, Tuple[float, float]] = {
    "devcurve_layer_bass_outline_width": (0.001, 0.020),
    "devcurve_layer_vocals_outline_width": (0.001, 0.020),
    "devcurve_layer_mids_outline_width": (0.001, 0.020),
    "devcurve_layer_transients_outline_width": (0.001, 0.020),
}
_DEVCURVE_CLAMP_LIMITS: Dict[str, Tuple[float, float]] = {
    "devcurve_smoothness": (0.0, 1.0),
    "devcurve_foreground_shadow_alpha": (0.0, 1.0),
    "devcurve_foreground_shadow_darken": (0.0, 1.0),
    "devcurve_foreground_shadow_offset": (0.0, 0.45),
    "devcurve_foreground_specular_alpha": (0.0, 1.0),
    "devcurve_foreground_specular_width": (0.002, 0.120),
    "devcurve_foreground_specular_offset": (-0.20, 0.20),
    "devcurve_foreground_specular_crest_bias": (0.0, 2.0),
}
_DEVCURVE_OUTLINE_COLOR_ATTRS = (
    "devcurve_layer_bass_outline_color",
    "devcurve_layer_vocals_outline_color",
    "devcurve_layer_mids_outline_color",
    "devcurve_layer_transients_outline_color",
)
_DEVCURVE_SHAPE_NODE_ATTRS = (
    "devcurve_layer_bass_shape_nodes",
    "devcurve_layer_vocals_shape_nodes",
    "devcurve_layer_mids_shape_nodes",
    "devcurve_layer_transients_shape_nodes",
)
_DEVCURVE_ORDER_ATTRS = (
    "devcurve_layer_bass_order",
    "devcurve_layer_vocals_order",
    "devcurve_layer_mids_order",
    "devcurve_layer_transients_order",
)


def _extend_visualizer_kwargs(
    target: Dict[str, Any],
    *groups: Mapping[str, Any],
) -> Dict[str, Any]:
    """Update one kwargs payload from ordered group mappings."""

    for group in groups:
        target.update(group)
    return target


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

    data = _build_visualizer_core_kwargs(
        read_value,
        active_mode=active_mode,
        active_technical=active_technical,
        active_visuals=active_visuals,
        rainbow_kwargs=rainbow_kwargs,
    )
    return _extend_visualizer_kwargs(
        data,
        _build_visualizer_osc_blob_kwargs(read_value),
        _build_visualizer_spectrum_kwargs(read_value),
        _build_visualizer_sine_kwargs(read_value),
        _build_visualizer_bubble_kwargs(
            read_value,
            bubble_gradient_semantics_version=bubble_gradient_semantics_version,
            bubble_stream_constant_speed_default=bubble_stream_constant_speed_default,
            bubble_stream_speed_cap_default=bubble_stream_speed_cap_default,
        ),
        _build_visualizer_blob_shape_kwargs(read_value),
        _build_visualizer_devcurve_kwargs(read_value),
        preset_kwargs,
    )


def _build_visualizer_core_kwargs(
    read_value: Callable[[str, Any], Any],
    *,
    active_mode: str,
    active_technical: Mapping[str, Any],
    active_visuals: Mapping[str, Any],
    rainbow_kwargs: Mapping[str, Any],
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _CORE_BUILD_SPECS)
    data.update(
        {
            "bar_count": int(active_technical["bar_count"]),
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
            "rainbow_enabled": rainbow_kwargs["rainbow_enabled"],
            "rainbow_speed": rainbow_kwargs["rainbow_speed"],
        }
    )
    return data


def _build_visualizer_osc_blob_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _OSC_BLOB_BUILD_SPECS)
    data["osc_glow_reactivity"] = float(
        read_value("osc_glow_reactivity", read_value("osc_glow_size", 1.0))
    )
    data["blob_stretch_tendency"] = float(
        read_value("blob_stretch_tendency", read_value("blob_stretch", 0.35))
    )
    data["blob_stretch_outer"] = float(
        read_value("blob_stretch_outer", read_value("blob_stretch", 0.35))
    )
    return data


def _build_visualizer_spectrum_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _SPECTRUM_BUILD_SPECS)
    data["spectrum_render_mode"] = resolve_spectrum_render_mode(read_value)
    data["spectrum_unique_colors"] = resolve_spectrum_unique_colors(read_value)
    data["spectrum_notch_positions_linear"] = _normalize_spectrum_linear_notches(
        read_value("spectrum_notch_positions_linear", _SPECTRUM_DEFAULT_NOTCHES_LINEAR)
    )
    data["spectrum_lane_strengths_mirrored"] = _normalize_spectrum_lane_strengths(
        read_value("spectrum_lane_strengths_mirrored", _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED),
        _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED,
    )
    data["spectrum_lane_strengths_linear"] = _normalize_spectrum_lane_strengths(
        read_value("spectrum_lane_strengths_linear", _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR),
        _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR,
    )
    return data


def _build_visualizer_sine_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _SINE_BUILD_SPECS)
    data["sine_glow_reactivity"] = float(
        read_value("sine_glow_reactivity", read_value("sine_glow_size", 1.0))
    )
    data["sine_wave_effect"] = float(
        read_value("sine_wave_effect", read_value("sine_wobble_amount", 0.0))
    )
    return data


def _build_visualizer_bubble_kwargs(
    read_value: Callable[[str, Any], Any],
    *,
    bubble_gradient_semantics_version: int,
    bubble_stream_constant_speed_default: float,
    bubble_stream_speed_cap_default: float,
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _BUBBLE_BUILD_SPECS)
    data["bubble_stream_constant_speed"] = float(
        read_value(
            "bubble_stream_constant_speed",
            read_value("bubble_stream_speed", bubble_stream_constant_speed_default),
        )
    )
    data["bubble_stream_speed_cap"] = float(
        read_value(
            "bubble_stream_speed_cap",
            read_value("bubble_stream_speed", bubble_stream_speed_cap_default),
        )
    )
    data["bubble_collision_pop_mode"] = str(
        read_value("bubble_collision_pop_mode", "off")
    ).strip().lower()
    data["bubble_specular_direction"] = normalize_bubble_specular_direction(
        read_value("bubble_specular_direction", "top_left")
    )
    data["bubble_gradient_direction"] = resolve_bubble_gradient_direction(
        read_value("bubble_gradient_direction", "top"),
        semantics_version=bubble_gradient_semantics_version,
        default="top",
    )
    return data


def _build_visualizer_blob_shape_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    return _build_read_value_map(read_value, _BLOB_SHAPE_BUILD_SPECS)


def _build_visualizer_devcurve_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    return _build_read_value_map(read_value, _DEVCURVE_BUILD_SPECS)


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


def _serialize_prefixed_fields(
    source: Any,
    prefix: str,
    field_serializers: Mapping[str, Callable[[Any], Any]],
) -> Dict[str, Any]:
    """Serialize a mapping of field names under the given prefix."""

    return {
        f"{prefix}.{field_name}": serializer(getattr(source, field_name))
        for field_name, serializer in field_serializers.items()
    }


def _serialize_attr_map(
    source: Any,
    key_prefix: str,
    attr_serializers: Mapping[str, Callable[[Any], Any]],
) -> Dict[str, Any]:
    """Serialize explicit attribute names under the given key prefix."""

    return {
        f"{key_prefix}.{attr_name}": serializer(getattr(source, attr_name))
        for attr_name, serializer in attr_serializers.items()
    }


def _merge_serialized_sections(
    *sections: Mapping[str, Any],
) -> Dict[str, Any]:
    """Merge ordered serialized sections into one persisted payload."""

    data: Dict[str, Any] = {}
    for section in sections:
        data.update(section)
    return data


def _apply_list_defaults(target: Any, defaults: Mapping[str, list[int]]) -> None:
    """Apply list-valued defaults to missing attributes on the target."""

    for attr, value in defaults.items():
        if getattr(target, attr) is None:
            setattr(target, attr, list(value))


def _build_read_value_map(
    read_value: Callable[[str, Any], Any],
    specs: Mapping[str, Tuple[Any, Callable[[Any], Any]]],
) -> Dict[str, Any]:
    """Build a kwargs mapping from keyed defaults and coercers."""

    return {
        attr_name: coercer(read_value(attr_name, default))
        for attr_name, (default, coercer) in specs.items()
    }


def _clamp_attr_range(target: Any, attr: str, minimum: float, maximum: float) -> None:
    """Clamp one float-like attribute in place."""

    setattr(target, attr, max(minimum, min(maximum, float(getattr(target, attr)))))


def _force_full_alpha_on_attrs(target: Any, attrs: Tuple[str, ...]) -> None:
    """Normalize RGBA-style attrs so outline colors always serialize opaque alpha."""

    for attr in attrs:
        value = list(getattr(target, attr))
        while len(value) < 4:
            value.append(255)
        value[3] = 255
        setattr(target, attr, value[:4])


def _normalize_ranked_attrs(target: Any, attrs: Tuple[str, ...]) -> None:
    """Reassign ranked attrs to a stable 1..N ordering based on current numeric rank."""

    order_pairs = [(attr_name, int(getattr(target, attr_name))) for attr_name in attrs]
    order_pairs.sort(key=lambda item: item[1])
    for idx, (attr_name, _raw_rank) in enumerate(order_pairs, start=1):
        setattr(target, attr_name, idx)



@dataclass
class SpotifyVisualizerSettings:
    """Spotify visualizer widget settings."""

    enabled: bool = False
    visualizers_enabled: bool = True
    monitor: str = "ALL"
    position: str = "Follow Media"
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
        _apply_list_defaults(self, _OSCILLOSCOPE_COLOR_DEFAULTS)

    def _apply_sine_defaults(self) -> None:
        _apply_list_defaults(self, _SINE_COLOR_DEFAULTS)

    def _apply_bubble_defaults(self) -> None:
        _apply_list_defaults(self, _BUBBLE_COLOR_DEFAULTS)

    def _apply_devcurve_defaults(self) -> None:
        _apply_list_defaults(self, _DEVCURVE_COLOR_DEFAULTS)
        self.devcurve_active_layer = (
            str(self.devcurve_active_layer).strip().lower()
            if str(self.devcurve_active_layer).strip().lower() in _DEVCURVE_ACTIVE_LAYERS
            else "bass"
        )
        for attr_name, (minimum, maximum) in _DEVCURVE_OUTLINE_WIDTH_LIMITS.items():
            _clamp_attr_range(self, attr_name, minimum, maximum)
        _force_full_alpha_on_attrs(self, _DEVCURVE_OUTLINE_COLOR_ATTRS)
        for attr_name, (minimum, maximum) in _DEVCURVE_CLAMP_LIMITS.items():
            _clamp_attr_range(self, attr_name, minimum, maximum)
        for attr in _DEVCURVE_SHAPE_NODE_ATTRS:
            self._ensure_non_empty_nodes(attr, _DEVCURVE_DEFAULT_SHAPE_NODES)
        _normalize_ranked_attrs(self, _DEVCURVE_ORDER_ATTRS)

    @classmethod
    def _build_constructor_kwargs_from_mode_state(
        cls,
        read_value: Callable[[str, Any], Any],
        per_mode_value_reader: Callable[[str, str, Any], Any],
        active_mode_value_reader: Callable[[str, Any], Any],
        *,
        active_mode: str,
        preset_kwargs: Mapping[str, Any],
        bubble_gradient_semantics_version: int,
        bubble_stream_constant_speed_default: float,
        bubble_stream_speed_cap_default: float,
    ) -> Dict[str, Any]:
        """Assemble constructor kwargs from shared active-mode reader state."""

        defaults_model = cls()
        mode_kwargs = _build_live_visualizer_mode_kwargs(per_mode_value_reader, defaults_model)
        mode_visual_kwargs = _build_live_visualizer_mode_shared_visual_kwargs(
            per_mode_value_reader,
            defaults_model,
        )
        active_technical = _resolve_active_mode_technical_state(
            active_mode,
            mode_kwargs,
        )
        active_visuals = _resolve_active_mode_shared_visual_state(
            active_mode,
            mode_visual_kwargs,
        )
        rainbow_kwargs = resolve_visualizer_active_mode_rainbow_state(active_mode_value_reader)
        return _build_visualizer_model_kwargs(
            read_value,
            active_mode=active_mode,
            bubble_gradient_semantics_version=bubble_gradient_semantics_version,
            active_technical=active_technical,
            active_visuals=active_visuals,
            rainbow_kwargs=rainbow_kwargs,
            preset_kwargs={**preset_kwargs, **mode_kwargs, **mode_visual_kwargs},
            bubble_stream_constant_speed_default=bubble_stream_constant_speed_default,
            bubble_stream_speed_cap_default=bubble_stream_speed_cap_default,
        )

    @classmethod
    def from_settings(cls, settings: "SettingsManager", prefix: str = "widgets.spotify_visualizer") -> "SpotifyVisualizerSettings":
        """Load Spotify visualizer settings from SettingsManager."""
        get = settings.get
        _get, _mode_value = _build_settings_readers(settings, prefix=prefix)

        try:
            bubble_gradient_semantics_version = int(_get("bubble_gradient_semantics_version", 0))
        except (TypeError, ValueError):
            bubble_gradient_semantics_version = 0
        _preset_kwargs = resolve_all_preset_indices_from_getter(get, prefix=prefix)
        _active_mode = coerce_visualizer_mode_id(str(get(f"{prefix}.mode", "bubble")))

        return cls(
            **cls._build_constructor_kwargs_from_mode_state(
                _get,
                lambda mode, key, default: _mode_value(mode, key, default),
                lambda key, default: _mode_value(
                    _active_mode,
                    key,
                    _get(key, default),
                ),
                active_mode=_active_mode,
                preset_kwargs=_preset_kwargs,
                bubble_gradient_semantics_version=bubble_gradient_semantics_version,
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

        _preset_kwargs = _resolve_mapping_preset_kwargs(
            _raw,
            prefix=prefix,
            resolve_preset_indices=resolve_preset_indices,
        )

        return cls(
            **cls._build_constructor_kwargs_from_mode_state(
                _get,
                lambda mode, key, default: _get_per_mode_value(mode, key, default),
                lambda key, default: _get_mode_value(key, default),
                active_mode=_mode,
                preset_kwargs=_preset_kwargs,
                bubble_gradient_semantics_version=bubble_gradient_semantics_version,
                bubble_stream_constant_speed_default=0.6,
                bubble_stream_speed_cap_default=1.0,
            )
        )

    def to_dict(self, prefix: str = "widgets.spotify_visualizer") -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return _merge_serialized_sections(
            self._serialize_core_settings(prefix),
            self._serialize_osc_blob_settings(prefix),
            self._serialize_spectrum_settings(prefix),
            self._serialize_sine_settings(prefix),
            self._serialize_bubble_settings(prefix),
            self._serialize_blob_shape_settings(prefix),
            self._serialize_devcurve_settings(prefix),
            self._serialize_preset_indices(prefix),
            self._serialize_per_mode_technical_settings(prefix),
            self._serialize_transient_mix_settings(prefix),
        )

    def _serialize_core_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _CORE_SETTINGS_SERIALIZERS)

    def _serialize_osc_blob_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _OSC_BLOB_SERIALIZERS)

    def _serialize_spectrum_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _SPECTRUM_SERIALIZERS)

    def _serialize_sine_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _SINE_SERIALIZERS)

    def _serialize_bubble_settings(self, prefix: str) -> Dict[str, Any]:
        data = _serialize_prefixed_fields(self, prefix, _BUBBLE_SERIALIZERS)
        data[f"{prefix}.bubble_gradient_semantics_version"] = CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION
        return data

    def _serialize_blob_shape_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _BLOB_SHAPE_SERIALIZERS)

    def _serialize_preset_indices(self, prefix: str) -> Dict[str, int]:
        return {
            f"{prefix}.{get_preset_key(mode_id)}": int(getattr(self, get_preset_key(mode_id)))
            for mode_id in VISUALIZER_MODE_IDS
        }

    def _serialize_transient_mix_settings(self, prefix: str) -> Dict[str, float]:
        return _serialize_prefixed_fields(self, prefix, _TRANSIENT_MIX_SERIALIZERS)

    def _serialize_per_mode_technical_settings(self, prefix: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        for mode_name in PER_MODE_TECHNICAL_MODES:
            data.update(
                _serialize_attr_map(
                    self,
                    prefix,
                    {
                        f"{mode_name}_{suffix}": serializer
                        for suffix, serializer in _PER_MODE_TECHNICAL_SERIALIZERS.items()
                    },
                )
            )
        return data

    def _serialize_devcurve_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _DEVCURVE_SERIALIZERS)

    @staticmethod
    def _normalize_mode_name(mode: str) -> str:
        mode_key = str(mode).lower()
        if mode_key in PER_MODE_TECHNICAL_MODES:
            return mode_key
        return PER_MODE_TECHNICAL_MODES[0]

    def _mode_attr_name(self, mode: str, base_key: str) -> str:
        normalized = self._normalize_mode_name(mode)
        return f"{normalized}_{base_key}"

    def _resolve_mode_value(self, mode: str, base_key: str) -> Any:
        return getattr(self, self._mode_attr_name(mode, base_key))

    def _resolve_mode_value_with(self, mode: str, base_key: str) -> Any:
        resolver = _PER_MODE_RESOLVERS[base_key]
        return resolver(self._resolve_mode_value(mode, base_key))

    def resolve_dynamic_floor(self, mode: str) -> bool:
        return self._resolve_mode_value_with(mode, "dynamic_floor")

    def resolve_manual_floor(self, mode: str) -> float:
        return self._resolve_mode_value_with(mode, "manual_floor")

    def resolve_dynamic_range_enabled(self, mode: str) -> bool:
        return self._resolve_mode_value_with(mode, "dynamic_range_enabled")

    def resolve_agc_strength(self, mode: str) -> float:
        return self._resolve_mode_value_with(mode, "agc_strength")

    def resolve_input_gain(self, mode: str) -> float:
        return self._resolve_mode_value_with(mode, "input_gain")

    def resolve_kick_lane_gain(self, mode: str) -> float:
        return self._resolve_mode_value_with(mode, "kick_lane_gain")

    def resolve_transient_pulse_gain(self, mode: str) -> float:
        return self._resolve_mode_value_with(mode, "transient_pulse_gain")

    def resolve_transient_clamp(self, mode: str) -> float:
        return self._resolve_mode_value_with(mode, "transient_clamp")

    def resolve_audio_block_size(self, mode: str) -> int:
        return self._resolve_mode_value_with(mode, "audio_block_size")

    def resolve_adaptive_sensitivity(self, mode: str) -> bool:
        return self._resolve_mode_value_with(mode, "adaptive_sensitivity")

    def resolve_sensitivity(self, mode: str) -> float:
        return self._resolve_mode_value_with(mode, "sensitivity")

    def resolve_bar_count(self, mode: str) -> int:
        return self._resolve_mode_value_with(mode, "bar_count")

    def resolve_bar_fill_color(self, mode: str) -> list:
        return self._resolve_mode_value_with(mode, "bar_fill_color")

    def resolve_bar_border_color(self, mode: str) -> list:
        return self._resolve_mode_value_with(mode, "bar_border_color")

    def resolve_bar_border_opacity(self, mode: str) -> float:
        return self._resolve_mode_value_with(mode, "bar_border_opacity")

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

