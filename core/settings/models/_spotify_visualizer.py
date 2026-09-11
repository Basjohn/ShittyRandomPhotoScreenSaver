"""Spotify visualizer settings model and per-mode helper functions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Tuple, TYPE_CHECKING

from core.settings.default_contract import require_canonical_default
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
    normalize_visualizer_mode_activation,
    resolve_effective_enabled_modes,
    VISUALIZER_MODE_IDS,
)
from core.settings.visualizer_retired_modes import strip_retired_visualizer_settings
from core.settings.visualizer_preset_indices import (
    get_missing_preset_fallback_index,
    resolve_all_preset_indices_from_getter,
    resolve_all_preset_indices_from_mapping,
    resolve_preset_index_from_mapping,
)
from core.settings.visualizer_settings_contract import (
    migrate_legacy_global_visual_keys,
    migrate_legacy_sphere_finish_keys,
    migrate_legacy_sphere_control_keys,
    normalize_sphere_finish,
    PER_MODE_BASELINE_KEYS,
    SPECIAL_PER_MODE_KEYS,
    resolve_visualizer_active_mode_rainbow_state,
    resolve_spectrum_render_mode,
    resolve_spectrum_unique_colors,
    strip_legacy_global_technical_keys,
)
from core.settings.models._visualizer_helpers import (
    _normalize_spectrum_linear_notches,
    _normalize_spectrum_lane_strengths,
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


_VISUALIZER_DEFAULT_PREFIX = "widgets.spotify_visualizer"

def _visualizer_default(key: str) -> Any:
    """Return one persisted Visualizer product default from canonical authority."""

    return require_canonical_default(f"{_VISUALIZER_DEFAULT_PREFIX}.{key}")


def _active_visualizer_default(key: str) -> Any:
    """Return the default active-mode mirror for a non-persisted model field.

    These mirror fields (bar_* visuals + the technical audio profile) exist only
    for modes in ``PER_MODE_TECHNICAL_MODES``. A mode without its own technical
    profile (e.g. ``sphere``, which reacts through its own sphere_* keys) mirrors
    them from the reference technical mode instead of resolving a non-existent
    ``sphere_<key>`` canonical default -- matching ``_normalize_mode_name`` used
    for per-mode attr resolution elsewhere in this model.
    """

    from core.settings.visualizer_mode_registry import get_technical_profile_mode

    mode = get_technical_profile_mode(str(_visualizer_default("mode")).lower())
    if mode not in PER_MODE_TECHNICAL_MODES:
        raise ValueError(f"invalid canonical visualizer technical profile: {mode!r}")
    return _visualizer_default(f"{mode}_{key}")



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
    "kick_lane_gain": float,
    "transient_pulse_gain": float,
    "transient_clamp": float,
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
    # Persisted per-mode capability activation. Every registered mode owns one
    # explicit boolean, mirroring transition dormancy; the enabled-id tuple is
    # derived only for runtime/UI consumers.
    "mode_activation": normalize_visualizer_mode_activation,
    "rainbow_enabled": bool,
    "rainbow_speed": float,
    "sine_line_dim": bool,
}

_TRANSIENT_MIX_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "spectrum_lane_transient_mix": float,
    "bubble_transient_mix_bass": float,
    "bubble_transient_mix_vocal": float,
    "sine_wave_transient_width_mix": float,
    "oscilloscope_transient_width_mix": float,
}

_OSC_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "osc_glow_enabled": bool,
    "osc_glow_intensity": float,
    "osc_glow_reactivity": float,
    "osc_glow_color": list,
    "osc_reactive_glow": bool,
    "osc_line_amplitude": float,
    "osc_smoothing": float,
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
    "osc_speed": float,
    "osc_line_dim": bool,
    "osc_line_offset_bias": float,
    "osc_vertical_shift": int,
    "osc_ghosting_enabled": bool,
    "osc_ghost_intensity": float,
    "osc_ghost_decay": float,
    "osc_ghost_line2_enabled": bool,
    "osc_ghost_line3_enabled": bool,
    "osc_ghost_line4_enabled": bool,
    "osc_ghost_line5_enabled": bool,
    "osc_ghost_line6_enabled": bool,
}

_SPECTRUM_SERIALIZERS: Dict[str, Callable[[Any], Any]] = {
    "spectrum_render_mode": str,
    "spectrum_visual_smoothing_enabled": bool,
    "spectrum_visual_smoothing": float,
    "spectrum_unique_colors": bool,
    "spectrum_rainbow_fill": bool,
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
    "osc_ghost_decay": float,
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
    "bubble_group_drift": bool,
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
    "bubble_big_visual_smoothing": float,
    "bubble_big_contraction_bias": float,
    "bubble_big_size_clamp": float,
    "bubble_big_specular_max_size": float,
    "bubble_trail_strength": float,
    "bubble_tail_opacity": float,
    "bubble_ghosting_enabled": bool,
    "bubble_ghost_alpha": float,
    "bubble_ghost_decay": float,
}

_CORE_BUILD_SPECS: Dict[str, Callable[[Any], Any]] = {
    'enabled': bool,
    'visualizers_enabled': bool,
    'monitor': str,
    'position': str,
    'sine_line_dim': bool,
}

_SPECTRUM_BUILD_SPECS: Dict[str, Callable[[Any], Any]] = {
    'spectrum_visual_smoothing_enabled': bool,
    'spectrum_visual_smoothing': float,
    'spectrum_rainbow_fill': bool,
    'spectrum_rainbow_border': bool,
    'spectrum_border_radius': float,
    'spectrum_link_fill_border': bool,
    'spectrum_glow_enabled': bool,
    'spectrum_glow_intensity': float,
    'spectrum_glow_color': list,
    'spectrum_ghosting_enabled': bool,
    'spectrum_ghost_alpha': float,
    'spectrum_ghost_decay': float,
    'spectrum_mirrored': bool,
    'spectrum_shape_nodes': list,
    'spectrum_notch_positions_mirrored': list,
    'spectrum_wave_amplitude': float,
    'spectrum_profile_floor': float,
    'spectrum_drop_speed': float,
}

_BUBBLE_BUILD_SPECS: Dict[str, Callable[[Any], Any]] = {
    'bubble_big_bass_pulse': float,
    'bubble_small_freq_pulse': float,
    'bubble_stream_direction': str,
    'bubble_stream_reactivity': float,
    'bubble_rotation_amount': float,
    'bubble_drift_amount': float,
    'bubble_group_drift': bool,
    'bubble_drift_speed': float,
    'bubble_drift_frequency': float,
    'bubble_drift_direction': str,
    'bubble_big_count': int,
    'bubble_small_count': int,
    'bubble_surface_reach': float,
    'bubble_bounce_big_pct': int,
    'bubble_bounce_small_pct': int,
    'bubble_bounce_big_speed': float,
    'bubble_bounce_small_speed': float,
    'bubble_bounce_same_only': bool,
    'bubble_outline_color': list,
    'bubble_specular_color': list,
    'bubble_gradient_light': list,
    'bubble_gradient_dark': list,
    'bubble_pop_color': list,
    'bubble_big_size_max': float,
    'bubble_small_size_max': float,
    'bubble_big_visual_smoothing': float,
    'bubble_big_contraction_bias': float,
    'bubble_big_size_clamp': float,
    'bubble_big_specular_max_size': float,
    'bubble_trail_strength': float,
    'bubble_tail_opacity': float,
    'bubble_ghosting_enabled': bool,
    'bubble_ghost_alpha': float,
    'bubble_ghost_decay': float,
}

_OSC_BUILD_SPECS: Dict[str, Callable[[Any], Any]] = {
    'osc_glow_enabled': bool,
    'osc_glow_intensity': float,
    'osc_glow_reactivity': float,
    'osc_glow_color': list,
    'osc_reactive_glow': bool,
    'osc_line_amplitude': float,
    'osc_smoothing': float,
    'osc_line_color': list,
    'osc_line_count': int,
    'osc_line2_color': list,
    'osc_line2_glow_color': list,
    'osc_line3_color': list,
    'osc_line3_glow_color': list,
    'osc_line4_color': list,
    'osc_line4_glow_color': list,
    'osc_line5_color': list,
    'osc_line5_glow_color': list,
    'osc_line6_color': list,
    'osc_line6_glow_color': list,
    'osc_speed': float,
    'osc_line_dim': bool,
    'osc_line_offset_bias': float,
    'osc_vertical_shift': int,
}

_SINE_BUILD_SPECS: Dict[str, Callable[[Any], Any]] = {
    'sine_wave_travel': int,
    'sine_density': float,
    'sine_displacement': float,
    'sine_glow_enabled': bool,
    'sine_glow_intensity': float,
    'sine_glow_color': list,
    'sine_line_color': list,
    'sine_reactive_glow': bool,
    'sine_ghosting_enabled': bool,
    'sine_ghost_alpha': float,
    'sine_ghost_decay': float,
    'sine_ghost_line2_enabled': bool,
    'sine_ghost_line3_enabled': bool,
    'sine_ghost_line4_enabled': bool,
    'sine_ghost_line5_enabled': bool,
    'sine_ghost_line6_enabled': bool,
    'sine_sensitivity': float,
    'sine_smoothing': float,
    'sine_speed': float,
    'sine_line_count': int,
    'sine_line_offset_bias': float,
    'sine_line2_color': list,
    'sine_line2_glow_color': list,
    'sine_line3_color': list,
    'sine_line3_glow_color': list,
    'sine_line4_color': list,
    'sine_line4_glow_color': list,
    'sine_line5_color': list,
    'sine_line5_glow_color': list,
    'sine_line6_color': list,
    'sine_line6_glow_color': list,
    'sine_travel_line2': int,
    'sine_travel_line3': int,
    'sine_travel_line4': int,
    'sine_travel_line5': int,
    'sine_travel_line6': int,
    'sine_line1_shift': float,
    'sine_line2_shift': float,
    'sine_line3_shift': float,
    'sine_line4_shift': float,
    'sine_line5_shift': float,
    'sine_line6_shift': float,
    'sine_vertical_shift': int,
    'sine_card_adaptation': float,
    'sine_micro_wobble': float,
    'sine_crawl_amount': float,
    'sine_width_reaction': float,
    'osc_ghosting_enabled': bool,
    'osc_ghost_intensity': float,
    'osc_ghost_decay': float,
    'osc_ghost_line2_enabled': bool,
    'osc_ghost_line3_enabled': bool,
    'osc_ghost_line4_enabled': bool,
    'osc_ghost_line5_enabled': bool,
    'osc_ghost_line6_enabled': bool,
    'sine_heartbeat': float,
}

_DEVCURVE_BUILD_SPECS: Dict[str, Callable[[Any], Any]] = {
    'devcurve_active_layer': str,
    'devcurve_layer_bass_shape_nodes': list,
    'devcurve_layer_vocals_shape_nodes': list,
    'devcurve_layer_mids_shape_nodes': list,
    'devcurve_layer_transients_shape_nodes': list,
    'devcurve_base_level': float,
    'devcurve_motion_power': float,
    'devcurve_idle_motion': float,
    'devcurve_idle_speed': float,
    'devcurve_smoothness': float,
    'devcurve_layer_bass_enabled': bool,
    'devcurve_layer_bass_color': list,
    'devcurve_layer_bass_alpha': float,
    'devcurve_layer_bass_power': float,
    'devcurve_layer_bass_offset': float,
    'devcurve_layer_bass_outline_color': list,
    'devcurve_layer_bass_outline_width': float,
    'devcurve_layer_bass_order': int,
    'devcurve_layer_vocals_enabled': bool,
    'devcurve_layer_vocals_color': list,
    'devcurve_layer_vocals_alpha': float,
    'devcurve_layer_vocals_power': float,
    'devcurve_layer_vocals_offset': float,
    'devcurve_layer_vocals_outline_color': list,
    'devcurve_layer_vocals_outline_width': float,
    'devcurve_layer_vocals_order': int,
    'devcurve_layer_mids_enabled': bool,
    'devcurve_layer_mids_color': list,
    'devcurve_layer_mids_alpha': float,
    'devcurve_layer_mids_power': float,
    'devcurve_layer_mids_offset': float,
    'devcurve_layer_mids_outline_color': list,
    'devcurve_layer_mids_outline_width': float,
    'devcurve_layer_mids_order': int,
    'devcurve_layer_transients_enabled': bool,
    'devcurve_layer_transients_color': list,
    'devcurve_layer_transients_alpha': float,
    'devcurve_layer_transients_power': float,
    'devcurve_layer_transients_offset': float,
    'devcurve_layer_transients_outline_color': list,
    'devcurve_layer_transients_outline_width': float,
    'devcurve_layer_transients_order': int,
    'devcurve_ghosting_enabled': bool,
    'devcurve_ghost_alpha': float,
    'devcurve_ghost_decay': float,
    'devcurve_foreground_shadow_enabled': bool,
    'devcurve_foreground_shadow_alpha': float,
    'devcurve_foreground_shadow_darken': float,
    'devcurve_foreground_shadow_offset': float,
    'devcurve_foreground_specular_enabled': bool,
    'devcurve_foreground_specular_alpha': float,
    'devcurve_foreground_specular_width': float,
    'devcurve_foreground_specular_offset': float,
    'devcurve_foreground_specular_crest_bias': float,
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

_SPHERE_BUILD_SPECS: Dict[str, Callable[[Any], Any]] = {
    'sphere_finish': str,
    'sphere_fill_color': list,
    'sphere_edge_color': list,
    'sphere_tracer_color': list,
    'sphere_edge_weight': float,
    'sphere_voxel_size_variation': float,
    'sphere_depth_shading_enabled': bool,
    'sphere_depth_shading_strength': float,
    'sphere_allow_overflow': bool,
    'sphere_cel_shading': bool,
    'sphere_light_tracer_enabled': bool,
    'sphere_fragment_interpolation_enabled': bool,
    'sphere_incoming_density_response_enabled': bool,
    'sphere_incoming_transient_velocity_enabled': bool,
    'sphere_particle_outtake_enabled': bool,
    'sphere_shadow_enabled': bool,
    'sphere_shadow_opacity': float,
    'sphere_shadow_softness': float,
    'sphere_shadow_distance': float,
    'sphere_shadow_size': float,
    'sphere_fade_incoming_blocks': bool,
    'sphere_fragment_strength': float,
    'sphere_particle_distance': float,
    'sphere_particle_amount': float,
    'sphere_perspective_strength': float,
    'sphere_taste_the_rainbow_enabled': bool,
    'sphere_taste_the_rainbow_surfaces': bool,
    'sphere_taste_the_rainbow_edges': bool,
    'sphere_base_rotation_speed': float,
    'sphere_rotation_speed': float,
    'sphere_gloss': float,
    'sphere_specular': float,
    'sphere_light_direction': str,
    'sphere_vocal_response': float,
    'sphere_size_response': float,
}
_SPHERE_SERIALIZERS: Dict[str, Callable[[Any], Any]] = dict(_SPHERE_BUILD_SPECS)

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
        _build_visualizer_osc_kwargs(read_value),
        _build_visualizer_spectrum_kwargs(read_value),
        _build_visualizer_sine_kwargs(read_value),
        _build_visualizer_bubble_kwargs(
            read_value,
            bubble_gradient_semantics_version=bubble_gradient_semantics_version,
        ),
        _build_visualizer_devcurve_kwargs(read_value),
        _build_visualizer_sphere_kwargs(read_value),
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


def _build_visualizer_osc_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _OSC_BUILD_SPECS)
    data["osc_glow_reactivity"] = float(
        read_value("osc_glow_reactivity", _visualizer_default("osc_glow_reactivity"))
    )
    return data


def _build_visualizer_spectrum_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _SPECTRUM_BUILD_SPECS)
    data["spectrum_render_mode"] = resolve_spectrum_render_mode(
        read_value, fallback=str(_visualizer_default("spectrum_render_mode"))
    )
    data["spectrum_unique_colors"] = resolve_spectrum_unique_colors(
        read_value, fallback=bool(_visualizer_default("spectrum_unique_colors"))
    )
    canonical_linear_notches = _visualizer_default("spectrum_notch_positions_linear")
    data["spectrum_notch_positions_linear"] = _normalize_spectrum_linear_notches(
        read_value("spectrum_notch_positions_linear", canonical_linear_notches),
        canonical_linear_notches,
    )
    data["spectrum_lane_strengths_mirrored"] = _normalize_spectrum_lane_strengths(
        read_value("spectrum_lane_strengths_mirrored", _visualizer_default("spectrum_lane_strengths_mirrored")),
        _visualizer_default("spectrum_lane_strengths_mirrored"),
    )
    data["spectrum_lane_strengths_linear"] = _normalize_spectrum_lane_strengths(
        read_value("spectrum_lane_strengths_linear", _visualizer_default("spectrum_lane_strengths_linear")),
        _visualizer_default("spectrum_lane_strengths_linear"),
    )
    return data


def _build_visualizer_sine_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _SINE_BUILD_SPECS)
    data["sine_glow_reactivity"] = float(
        read_value("sine_glow_reactivity", _visualizer_default("sine_glow_reactivity"))
    )
    data["sine_wave_effect"] = float(
        read_value("sine_wave_effect", _visualizer_default("sine_wave_effect"))
    )
    return data


def _build_visualizer_bubble_kwargs(
    read_value: Callable[[str, Any], Any],
    *,
    bubble_gradient_semantics_version: int,
) -> Dict[str, Any]:
    data = _build_read_value_map(read_value, _BUBBLE_BUILD_SPECS)
    data["bubble_stream_constant_speed"] = float(
        read_value("bubble_stream_constant_speed", _visualizer_default("bubble_stream_constant_speed"))
    )
    data["bubble_stream_speed_cap"] = float(
        read_value("bubble_stream_speed_cap", _visualizer_default("bubble_stream_speed_cap"))
    )
    data["bubble_collision_pop_mode"] = str(
        read_value("bubble_collision_pop_mode", _visualizer_default("bubble_collision_pop_mode"))
    ).strip().lower()
    data["bubble_specular_direction"] = normalize_bubble_specular_direction(
        read_value("bubble_specular_direction", _visualizer_default("bubble_specular_direction"))
    )
    default_gradient_direction = str(_visualizer_default("bubble_gradient_direction"))
    data["bubble_gradient_direction"] = resolve_bubble_gradient_direction(
        read_value("bubble_gradient_direction", default_gradient_direction),
        semantics_version=bubble_gradient_semantics_version,
        default=default_gradient_direction,
    )
    return data


def _build_visualizer_devcurve_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    return _build_read_value_map(read_value, _DEVCURVE_BUILD_SPECS)


def _build_visualizer_sphere_kwargs(
    read_value: Callable[[str, Any], Any],
) -> Dict[str, Any]:
    return _build_read_value_map(read_value, _SPHERE_BUILD_SPECS)


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
        return default

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
                raw.get(
                    f"{prefix}.{get_preset_key(mode_id)}",
                    _visualizer_default(get_preset_key(mode_id)),
                ),
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


def _apply_canonical_list_defaults(
    target: Any,
    serializers: Mapping[str, Callable[[Any], Any]],
) -> None:
    """Repair missing list-valued model attributes from canonical defaults."""

    for attr, serializer in serializers.items():
        if serializer is list and getattr(target, attr) is None:
            setattr(target, attr, deepcopy(_visualizer_default(attr)))


def _build_read_value_map(
    read_value: Callable[[str, Any], Any],
    specs: Mapping[str, Callable[[Any], Any]],
) -> Dict[str, Any]:
    """Build kwargs using canonical defaults as the only missing-value authority."""

    return {
        attr_name: coercer(read_value(attr_name, _visualizer_default(attr_name)))
        for attr_name, coercer in specs.items()
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

    enabled: bool = field(default_factory=lambda: _visualizer_default('enabled'))
    visualizers_enabled: bool = field(default_factory=lambda: _visualizer_default('visualizers_enabled'))
    monitor: str = field(default_factory=lambda: _visualizer_default('monitor'))
    position: str = field(default_factory=lambda: _visualizer_default('position'))
    bar_count: int = field(default_factory=lambda: _active_visualizer_default('bar_count'))
    bar_fill_color: list | None = field(default_factory=lambda: _active_visualizer_default('bar_fill_color'))
    bar_border_color: list | None = field(default_factory=lambda: _active_visualizer_default('bar_border_color'))
    bar_border_opacity: float = field(default_factory=lambda: _active_visualizer_default('bar_border_opacity'))
    spectrum_bar_fill_color: list | None = field(default_factory=lambda: _visualizer_default('spectrum_bar_fill_color'))
    spectrum_bar_border_color: list | None = field(default_factory=lambda: _visualizer_default('spectrum_bar_border_color'))
    spectrum_bar_border_opacity: float = field(default_factory=lambda: _visualizer_default('spectrum_bar_border_opacity'))
    bubble_bar_fill_color: list | None = field(default_factory=lambda: _visualizer_default('bubble_bar_fill_color'))
    bubble_bar_border_color: list | None = field(default_factory=lambda: _visualizer_default('bubble_bar_border_color'))
    bubble_bar_border_opacity: float = field(default_factory=lambda: _visualizer_default('bubble_bar_border_opacity'))
    sine_wave_bar_fill_color: list | None = field(default_factory=lambda: _visualizer_default('sine_wave_bar_fill_color'))
    sine_wave_bar_border_color: list | None = field(default_factory=lambda: _visualizer_default('sine_wave_bar_border_color'))
    sine_wave_bar_border_opacity: float = field(default_factory=lambda: _visualizer_default('sine_wave_bar_border_opacity'))
    oscilloscope_bar_fill_color: list | None = field(default_factory=lambda: _visualizer_default('oscilloscope_bar_fill_color'))
    oscilloscope_bar_border_color: list | None = field(default_factory=lambda: _visualizer_default('oscilloscope_bar_border_color'))
    oscilloscope_bar_border_opacity: float = field(default_factory=lambda: _visualizer_default('oscilloscope_bar_border_opacity'))
    devcurve_bar_fill_color: list | None = field(default_factory=lambda: _visualizer_default('devcurve_bar_fill_color'))
    devcurve_bar_border_color: list | None = field(default_factory=lambda: _visualizer_default('devcurve_bar_border_color'))
    devcurve_bar_border_opacity: float = field(default_factory=lambda: _visualizer_default('devcurve_bar_border_opacity'))
    adaptive_sensitivity: bool = field(default_factory=lambda: _active_visualizer_default('adaptive_sensitivity'))
    sensitivity: float = field(default_factory=lambda: _active_visualizer_default('sensitivity'))
    dynamic_floor: bool = field(default_factory=lambda: _active_visualizer_default('dynamic_floor'))
    manual_floor: float = field(default_factory=lambda: _active_visualizer_default('manual_floor'))
    dynamic_range_enabled: bool = field(default_factory=lambda: _active_visualizer_default('dynamic_range_enabled'))
    agc_strength: float = field(default_factory=lambda: _active_visualizer_default('agc_strength'))
    input_gain: float = field(default_factory=lambda: _active_visualizer_default('input_gain'))
    kick_lane_gain: float = field(default_factory=lambda: _active_visualizer_default('kick_lane_gain'))
    transient_pulse_gain: float = field(default_factory=lambda: _active_visualizer_default('transient_pulse_gain'))
    transient_clamp: float = field(default_factory=lambda: _active_visualizer_default('transient_clamp'))
    spectrum_lane_transient_mix: float = field(default_factory=lambda: _visualizer_default('spectrum_lane_transient_mix'))
    spectrum_dynamic_floor: bool = field(default_factory=lambda: _visualizer_default('spectrum_dynamic_floor'))
    spectrum_manual_floor: float = field(default_factory=lambda: _visualizer_default('spectrum_manual_floor'))
    spectrum_dynamic_range_enabled: bool = field(default_factory=lambda: _visualizer_default('spectrum_dynamic_range_enabled'))
    spectrum_agc_strength: float = field(default_factory=lambda: _visualizer_default('spectrum_agc_strength'))
    spectrum_input_gain: float = field(default_factory=lambda: _visualizer_default('spectrum_input_gain'))
    spectrum_kick_lane_gain: float = field(default_factory=lambda: _visualizer_default('spectrum_kick_lane_gain'))
    spectrum_transient_pulse_gain: float = field(default_factory=lambda: _visualizer_default('spectrum_transient_pulse_gain'))
    spectrum_transient_clamp: float = field(default_factory=lambda: _visualizer_default('spectrum_transient_clamp'))
    spectrum_audio_block_size: int = field(default_factory=lambda: _visualizer_default('spectrum_audio_block_size'))
    spectrum_adaptive_sensitivity: bool = field(default_factory=lambda: _visualizer_default('spectrum_adaptive_sensitivity'))
    spectrum_sensitivity: float = field(default_factory=lambda: _visualizer_default('spectrum_sensitivity'))
    spectrum_bar_count: int = field(default_factory=lambda: _visualizer_default('spectrum_bar_count'))
    bubble_dynamic_floor: bool = field(default_factory=lambda: _visualizer_default('bubble_dynamic_floor'))
    bubble_manual_floor: float = field(default_factory=lambda: _visualizer_default('bubble_manual_floor'))
    bubble_dynamic_range_enabled: bool = field(default_factory=lambda: _visualizer_default('bubble_dynamic_range_enabled'))
    bubble_agc_strength: float = field(default_factory=lambda: _visualizer_default('bubble_agc_strength'))
    bubble_input_gain: float = field(default_factory=lambda: _visualizer_default('bubble_input_gain'))
    bubble_kick_lane_gain: float = field(default_factory=lambda: _visualizer_default('bubble_kick_lane_gain'))
    bubble_transient_pulse_gain: float = field(default_factory=lambda: _visualizer_default('bubble_transient_pulse_gain'))
    bubble_transient_clamp: float = field(default_factory=lambda: _visualizer_default('bubble_transient_clamp'))
    bubble_transient_mix_bass: float = field(default_factory=lambda: _visualizer_default('bubble_transient_mix_bass'))
    bubble_transient_mix_vocal: float = field(default_factory=lambda: _visualizer_default('bubble_transient_mix_vocal'))
    bubble_audio_block_size: int = field(default_factory=lambda: _visualizer_default('bubble_audio_block_size'))
    bubble_adaptive_sensitivity: bool = field(default_factory=lambda: _visualizer_default('bubble_adaptive_sensitivity'))
    bubble_sensitivity: float = field(default_factory=lambda: _visualizer_default('bubble_sensitivity'))
    bubble_bar_count: int = field(default_factory=lambda: _visualizer_default('bubble_bar_count'))
    sine_wave_dynamic_floor: bool = field(default_factory=lambda: _visualizer_default('sine_wave_dynamic_floor'))
    sine_wave_manual_floor: float = field(default_factory=lambda: _visualizer_default('sine_wave_manual_floor'))
    sine_wave_dynamic_range_enabled: bool = field(default_factory=lambda: _visualizer_default('sine_wave_dynamic_range_enabled'))
    sine_wave_agc_strength: float = field(default_factory=lambda: _visualizer_default('sine_wave_agc_strength'))
    sine_wave_input_gain: float = field(default_factory=lambda: _visualizer_default('sine_wave_input_gain'))
    sine_wave_kick_lane_gain: float = field(default_factory=lambda: _visualizer_default('sine_wave_kick_lane_gain'))
    sine_wave_transient_pulse_gain: float = field(default_factory=lambda: _visualizer_default('sine_wave_transient_pulse_gain'))
    sine_wave_transient_clamp: float = field(default_factory=lambda: _visualizer_default('sine_wave_transient_clamp'))
    sine_wave_transient_width_mix: float = field(default_factory=lambda: _visualizer_default('sine_wave_transient_width_mix'))
    sine_wave_audio_block_size: int = field(default_factory=lambda: _visualizer_default('sine_wave_audio_block_size'))
    sine_wave_adaptive_sensitivity: bool = field(default_factory=lambda: _visualizer_default('sine_wave_adaptive_sensitivity'))
    sine_wave_sensitivity: float = field(default_factory=lambda: _visualizer_default('sine_wave_sensitivity'))
    sine_wave_bar_count: int = field(default_factory=lambda: _visualizer_default('sine_wave_bar_count'))
    oscilloscope_dynamic_floor: bool = field(default_factory=lambda: _visualizer_default('oscilloscope_dynamic_floor'))
    oscilloscope_manual_floor: float = field(default_factory=lambda: _visualizer_default('oscilloscope_manual_floor'))
    oscilloscope_dynamic_range_enabled: bool = field(default_factory=lambda: _visualizer_default('oscilloscope_dynamic_range_enabled'))
    oscilloscope_agc_strength: float = field(default_factory=lambda: _visualizer_default('oscilloscope_agc_strength'))
    oscilloscope_input_gain: float = field(default_factory=lambda: _visualizer_default('oscilloscope_input_gain'))
    oscilloscope_kick_lane_gain: float = field(default_factory=lambda: _visualizer_default('oscilloscope_kick_lane_gain'))
    oscilloscope_transient_pulse_gain: float = field(default_factory=lambda: _visualizer_default('oscilloscope_transient_pulse_gain'))
    oscilloscope_transient_clamp: float = field(default_factory=lambda: _visualizer_default('oscilloscope_transient_clamp'))
    oscilloscope_transient_width_mix: float = field(default_factory=lambda: _visualizer_default('oscilloscope_transient_width_mix'))
    oscilloscope_audio_block_size: int = field(default_factory=lambda: _visualizer_default('oscilloscope_audio_block_size'))
    oscilloscope_adaptive_sensitivity: bool = field(default_factory=lambda: _visualizer_default('oscilloscope_adaptive_sensitivity'))
    oscilloscope_sensitivity: float = field(default_factory=lambda: _visualizer_default('oscilloscope_sensitivity'))
    oscilloscope_bar_count: int = field(default_factory=lambda: _visualizer_default('oscilloscope_bar_count'))
    devcurve_dynamic_floor: bool = field(default_factory=lambda: _visualizer_default('devcurve_dynamic_floor'))
    devcurve_manual_floor: float = field(default_factory=lambda: _visualizer_default('devcurve_manual_floor'))
    devcurve_dynamic_range_enabled: bool = field(default_factory=lambda: _visualizer_default('devcurve_dynamic_range_enabled'))
    devcurve_agc_strength: float = field(default_factory=lambda: _visualizer_default('devcurve_agc_strength'))
    devcurve_input_gain: float = field(default_factory=lambda: _visualizer_default('devcurve_input_gain'))
    devcurve_kick_lane_gain: float = field(default_factory=lambda: _visualizer_default('devcurve_kick_lane_gain'))
    devcurve_transient_pulse_gain: float = field(default_factory=lambda: _visualizer_default('devcurve_transient_pulse_gain'))
    devcurve_transient_clamp: float = field(default_factory=lambda: _visualizer_default('devcurve_transient_clamp'))
    devcurve_audio_block_size: int = field(default_factory=lambda: _visualizer_default('devcurve_audio_block_size'))
    devcurve_adaptive_sensitivity: bool = field(default_factory=lambda: _visualizer_default('devcurve_adaptive_sensitivity'))
    devcurve_sensitivity: float = field(default_factory=lambda: _visualizer_default('devcurve_sensitivity'))
    devcurve_bar_count: int = field(default_factory=lambda: _visualizer_default('devcurve_bar_count'))
    mode: str = field(default_factory=lambda: _visualizer_default('mode'))
    # Explicit per-mode capability activation. A disabled mode keeps all authored
    # settings/presets; this mapping owns admission only.
    mode_activation: Dict[str, bool] = field(
        default_factory=lambda: normalize_visualizer_mode_activation(
            _visualizer_default('mode_activation')
        )
    )
    osc_glow_enabled: bool = field(default_factory=lambda: _visualizer_default('osc_glow_enabled'))
    osc_glow_intensity: float = field(default_factory=lambda: _visualizer_default('osc_glow_intensity'))
    osc_glow_reactivity: float = field(default_factory=lambda: _visualizer_default('osc_glow_reactivity'))
    osc_glow_color: list = field(default_factory=lambda: _visualizer_default('osc_glow_color'))
    osc_reactive_glow: bool = field(default_factory=lambda: _visualizer_default('osc_reactive_glow'))
    osc_line_amplitude: float = field(default_factory=lambda: _visualizer_default('osc_line_amplitude'))
    osc_smoothing: float = field(default_factory=lambda: _visualizer_default('osc_smoothing'))
    osc_line_color: list = field(default_factory=lambda: _visualizer_default('osc_line_color'))
    osc_line_count: int = field(default_factory=lambda: _visualizer_default('osc_line_count'))
    osc_line2_color: list = field(default_factory=lambda: _visualizer_default('osc_line2_color'))
    osc_line2_glow_color: list = field(default_factory=lambda: _visualizer_default('osc_line2_glow_color'))
    osc_line3_color: list = field(default_factory=lambda: _visualizer_default('osc_line3_color'))
    osc_line3_glow_color: list = field(default_factory=lambda: _visualizer_default('osc_line3_glow_color'))
    osc_line4_color: list = field(default_factory=lambda: _visualizer_default('osc_line4_color'))
    osc_line4_glow_color: list = field(default_factory=lambda: _visualizer_default('osc_line4_glow_color'))
    osc_line5_color: list = field(default_factory=lambda: _visualizer_default('osc_line5_color'))
    osc_line5_glow_color: list = field(default_factory=lambda: _visualizer_default('osc_line5_glow_color'))
    osc_line6_color: list = field(default_factory=lambda: _visualizer_default('osc_line6_color'))
    osc_line6_glow_color: list = field(default_factory=lambda: _visualizer_default('osc_line6_glow_color'))
    osc_speed: float = field(default_factory=lambda: _visualizer_default('osc_speed'))
    osc_line_dim: bool = field(default_factory=lambda: _visualizer_default('osc_line_dim'))
    osc_line_offset_bias: float = field(default_factory=lambda: _visualizer_default('osc_line_offset_bias'))
    osc_vertical_shift: int = field(default_factory=lambda: _visualizer_default('osc_vertical_shift'))
    spectrum_render_mode: str = field(default_factory=lambda: _visualizer_default('spectrum_render_mode'))
    spectrum_visual_smoothing_enabled: bool = field(default_factory=lambda: _visualizer_default('spectrum_visual_smoothing_enabled'))
    spectrum_visual_smoothing: float = field(default_factory=lambda: _visualizer_default('spectrum_visual_smoothing'))
    spectrum_unique_colors: bool = field(default_factory=lambda: _visualizer_default('spectrum_unique_colors'))
    spectrum_rainbow_fill: bool = field(default_factory=lambda: _visualizer_default('spectrum_rainbow_fill'))
    spectrum_rainbow_border: bool = field(default_factory=lambda: _visualizer_default('spectrum_rainbow_border'))
    spectrum_border_radius: float = field(default_factory=lambda: _visualizer_default('spectrum_border_radius'))
    spectrum_link_fill_border: bool = field(default_factory=lambda: _visualizer_default('spectrum_link_fill_border'))
    spectrum_glow_enabled: bool = field(default_factory=lambda: _visualizer_default('spectrum_glow_enabled'))
    spectrum_glow_intensity: float = field(default_factory=lambda: _visualizer_default('spectrum_glow_intensity'))
    spectrum_glow_color: List[int] = field(default_factory=lambda: _visualizer_default('spectrum_glow_color'))
    spectrum_ghosting_enabled: bool = field(default_factory=lambda: _visualizer_default('spectrum_ghosting_enabled'))
    spectrum_ghost_alpha: float = field(default_factory=lambda: _visualizer_default('spectrum_ghost_alpha'))
    spectrum_ghost_decay: float = field(default_factory=lambda: _visualizer_default('spectrum_ghost_decay'))
    spectrum_mirrored: bool = field(default_factory=lambda: _visualizer_default('spectrum_mirrored'))
    spectrum_shape_nodes: List[List[float]] = field(default_factory=lambda: _visualizer_default('spectrum_shape_nodes'))
    spectrum_notch_positions_mirrored: List[List] = field(default_factory=lambda: _visualizer_default('spectrum_notch_positions_mirrored'))
    spectrum_notch_positions_linear: List[List] = field(default_factory=lambda: _visualizer_default('spectrum_notch_positions_linear'))
    spectrum_lane_strengths_mirrored: Dict[str, float] = field(default_factory=lambda: _visualizer_default('spectrum_lane_strengths_mirrored'))
    spectrum_lane_strengths_linear: Dict[str, float] = field(default_factory=lambda: _visualizer_default('spectrum_lane_strengths_linear'))
    spectrum_wave_amplitude: float = field(default_factory=lambda: _visualizer_default('spectrum_wave_amplitude'))
    spectrum_profile_floor: float = field(default_factory=lambda: _visualizer_default('spectrum_profile_floor'))
    spectrum_drop_speed: float = field(default_factory=lambda: _visualizer_default('spectrum_drop_speed'))
    sine_wave_travel: int = field(default_factory=lambda: _visualizer_default('sine_wave_travel'))
    sine_density: float = field(default_factory=lambda: _visualizer_default('sine_density'))
    sine_displacement: float = field(default_factory=lambda: _visualizer_default('sine_displacement'))
    sine_glow_enabled: bool = field(default_factory=lambda: _visualizer_default('sine_glow_enabled'))
    sine_glow_intensity: float = field(default_factory=lambda: _visualizer_default('sine_glow_intensity'))
    sine_glow_reactivity: float = field(default_factory=lambda: _visualizer_default('sine_glow_reactivity'))
    sine_glow_color: list = field(default_factory=lambda: _visualizer_default('sine_glow_color'))
    sine_line_color: list = field(default_factory=lambda: _visualizer_default('sine_line_color'))
    sine_reactive_glow: bool = field(default_factory=lambda: _visualizer_default('sine_reactive_glow'))
    sine_ghosting_enabled: bool = field(default_factory=lambda: _visualizer_default('sine_ghosting_enabled'))
    sine_ghost_alpha: float = field(default_factory=lambda: _visualizer_default('sine_ghost_alpha'))
    sine_ghost_decay: float = field(default_factory=lambda: _visualizer_default('sine_ghost_decay'))
    sine_ghost_line2_enabled: bool = field(default_factory=lambda: _visualizer_default('sine_ghost_line2_enabled'))
    sine_ghost_line3_enabled: bool = field(default_factory=lambda: _visualizer_default('sine_ghost_line3_enabled'))
    sine_ghost_line4_enabled: bool = field(default_factory=lambda: _visualizer_default('sine_ghost_line4_enabled'))
    sine_ghost_line5_enabled: bool = field(default_factory=lambda: _visualizer_default('sine_ghost_line5_enabled'))
    sine_ghost_line6_enabled: bool = field(default_factory=lambda: _visualizer_default('sine_ghost_line6_enabled'))
    sine_sensitivity: float = field(default_factory=lambda: _visualizer_default('sine_sensitivity'))
    sine_smoothing: float = field(default_factory=lambda: _visualizer_default('sine_smoothing'))
    sine_speed: float = field(default_factory=lambda: _visualizer_default('sine_speed'))
    sine_line_count: int = field(default_factory=lambda: _visualizer_default('sine_line_count'))
    sine_line_offset_bias: float = field(default_factory=lambda: _visualizer_default('sine_line_offset_bias'))
    sine_line2_color: list = field(default_factory=lambda: _visualizer_default('sine_line2_color'))
    sine_line2_glow_color: list = field(default_factory=lambda: _visualizer_default('sine_line2_glow_color'))
    sine_line3_color: list = field(default_factory=lambda: _visualizer_default('sine_line3_color'))
    sine_line3_glow_color: list = field(default_factory=lambda: _visualizer_default('sine_line3_glow_color'))
    sine_line4_color: list = field(default_factory=lambda: _visualizer_default('sine_line4_color'))
    sine_line4_glow_color: list = field(default_factory=lambda: _visualizer_default('sine_line4_glow_color'))
    sine_line5_color: list = field(default_factory=lambda: _visualizer_default('sine_line5_color'))
    sine_line5_glow_color: list = field(default_factory=lambda: _visualizer_default('sine_line5_glow_color'))
    sine_line6_color: list = field(default_factory=lambda: _visualizer_default('sine_line6_color'))
    sine_line6_glow_color: list = field(default_factory=lambda: _visualizer_default('sine_line6_glow_color'))
    sine_travel_line2: int = field(default_factory=lambda: _visualizer_default('sine_travel_line2'))
    sine_travel_line3: int = field(default_factory=lambda: _visualizer_default('sine_travel_line3'))
    sine_travel_line4: int = field(default_factory=lambda: _visualizer_default('sine_travel_line4'))
    sine_travel_line5: int = field(default_factory=lambda: _visualizer_default('sine_travel_line5'))
    sine_travel_line6: int = field(default_factory=lambda: _visualizer_default('sine_travel_line6'))
    sine_line1_shift: float = field(default_factory=lambda: _visualizer_default('sine_line1_shift'))
    sine_line2_shift: float = field(default_factory=lambda: _visualizer_default('sine_line2_shift'))
    sine_line3_shift: float = field(default_factory=lambda: _visualizer_default('sine_line3_shift'))
    sine_line4_shift: float = field(default_factory=lambda: _visualizer_default('sine_line4_shift'))
    sine_line5_shift: float = field(default_factory=lambda: _visualizer_default('sine_line5_shift'))
    sine_line6_shift: float = field(default_factory=lambda: _visualizer_default('sine_line6_shift'))
    sine_wave_effect: float = field(default_factory=lambda: _visualizer_default('sine_wave_effect'))
    sine_vertical_shift: int = field(default_factory=lambda: _visualizer_default('sine_vertical_shift'))
    sine_micro_wobble: float = field(default_factory=lambda: _visualizer_default('sine_micro_wobble'))  # legacy, hidden
    sine_crawl_amount: float = field(default_factory=lambda: _visualizer_default('sine_crawl_amount'))
    sine_width_reaction: float = field(default_factory=lambda: _visualizer_default('sine_width_reaction'))
    sine_card_adaptation: float = field(default_factory=lambda: _visualizer_default('sine_card_adaptation'))
    rainbow_enabled: bool = field(default_factory=lambda: _visualizer_default('rainbow_enabled'))
    rainbow_speed: float = field(default_factory=lambda: _visualizer_default('rainbow_speed'))
    osc_ghosting_enabled: bool = field(default_factory=lambda: _visualizer_default('osc_ghosting_enabled'))
    osc_ghost_intensity: float = field(default_factory=lambda: _visualizer_default('osc_ghost_intensity'))
    osc_ghost_decay: float = field(default_factory=lambda: _visualizer_default('osc_ghost_decay'))
    osc_ghost_line2_enabled: bool = field(default_factory=lambda: _visualizer_default('osc_ghost_line2_enabled'))
    osc_ghost_line3_enabled: bool = field(default_factory=lambda: _visualizer_default('osc_ghost_line3_enabled'))
    osc_ghost_line4_enabled: bool = field(default_factory=lambda: _visualizer_default('osc_ghost_line4_enabled'))
    osc_ghost_line5_enabled: bool = field(default_factory=lambda: _visualizer_default('osc_ghost_line5_enabled'))
    osc_ghost_line6_enabled: bool = field(default_factory=lambda: _visualizer_default('osc_ghost_line6_enabled'))
    sine_heartbeat: float = field(default_factory=lambda: _visualizer_default('sine_heartbeat'))
    # Bubble visualizer
    bubble_big_bass_pulse: float = field(default_factory=lambda: _visualizer_default('bubble_big_bass_pulse'))
    bubble_small_freq_pulse: float = field(default_factory=lambda: _visualizer_default('bubble_small_freq_pulse'))
    bubble_stream_direction: str = field(default_factory=lambda: _visualizer_default('bubble_stream_direction'))
    bubble_stream_constant_speed: float = field(default_factory=lambda: _visualizer_default('bubble_stream_constant_speed'))
    bubble_stream_speed_cap: float = field(default_factory=lambda: _visualizer_default('bubble_stream_speed_cap'))
    bubble_stream_reactivity: float = field(default_factory=lambda: _visualizer_default('bubble_stream_reactivity'))
    bubble_rotation_amount: float = field(default_factory=lambda: _visualizer_default('bubble_rotation_amount'))
    bubble_drift_amount: float = field(default_factory=lambda: _visualizer_default('bubble_drift_amount'))
    bubble_group_drift: bool = field(default_factory=lambda: _visualizer_default('bubble_group_drift'))
    bubble_drift_speed: float = field(default_factory=lambda: _visualizer_default('bubble_drift_speed'))
    bubble_drift_frequency: float = field(default_factory=lambda: _visualizer_default('bubble_drift_frequency'))
    bubble_drift_direction: str = field(default_factory=lambda: _visualizer_default('bubble_drift_direction'))  # none/left/right/diagonal/swish_{horizontal,vertical}/swirl_{cw,ccw}/random
    bubble_big_count: int = field(default_factory=lambda: _visualizer_default('bubble_big_count'))
    bubble_small_count: int = field(default_factory=lambda: _visualizer_default('bubble_small_count'))
    bubble_surface_reach: float = field(default_factory=lambda: _visualizer_default('bubble_surface_reach'))
    bubble_bounce_big_pct: int = field(default_factory=lambda: _visualizer_default('bubble_bounce_big_pct'))
    bubble_bounce_small_pct: int = field(default_factory=lambda: _visualizer_default('bubble_bounce_small_pct'))
    bubble_bounce_big_speed: float = field(default_factory=lambda: _visualizer_default('bubble_bounce_big_speed'))
    bubble_bounce_small_speed: float = field(default_factory=lambda: _visualizer_default('bubble_bounce_small_speed'))
    bubble_bounce_same_only: bool = field(default_factory=lambda: _visualizer_default('bubble_bounce_same_only'))
    bubble_collision_pop_mode: str = field(default_factory=lambda: _visualizer_default('bubble_collision_pop_mode'))  # off/one/all
    bubble_outline_color: Any = field(default_factory=lambda: _visualizer_default('bubble_outline_color'))
    bubble_specular_color: Any = field(default_factory=lambda: _visualizer_default('bubble_specular_color'))
    bubble_gradient_light: Any = field(default_factory=lambda: _visualizer_default('bubble_gradient_light'))
    bubble_gradient_dark: Any = field(default_factory=lambda: _visualizer_default('bubble_gradient_dark'))
    bubble_pop_color: Any = field(default_factory=lambda: _visualizer_default('bubble_pop_color'))
    bubble_specular_direction: str = field(default_factory=lambda: _visualizer_default('bubble_specular_direction'))  # top/bottom/left/right + diagonals
    bubble_gradient_direction: str = field(default_factory=lambda: _visualizer_default('bubble_gradient_direction'))  # gradient vector independent of specular highlight
    bubble_big_size_max: float = field(default_factory=lambda: _visualizer_default('bubble_big_size_max'))
    bubble_small_size_max: float = field(default_factory=lambda: _visualizer_default('bubble_small_size_max'))
    bubble_big_visual_smoothing: float = field(default_factory=lambda: _visualizer_default('bubble_big_visual_smoothing'))
    bubble_big_contraction_bias: float = field(default_factory=lambda: _visualizer_default('bubble_big_contraction_bias'))
    bubble_big_size_clamp: float = field(default_factory=lambda: _visualizer_default('bubble_big_size_clamp'))
    bubble_big_specular_max_size: float = field(default_factory=lambda: _visualizer_default('bubble_big_specular_max_size'))
    bubble_tail_opacity: float = field(default_factory=lambda: _visualizer_default('bubble_tail_opacity'))
    bubble_trail_strength: float = field(default_factory=lambda: _visualizer_default('bubble_trail_strength'))
    bubble_ghosting_enabled: bool = field(default_factory=lambda: _visualizer_default('bubble_ghosting_enabled'))
    bubble_ghost_alpha: float = field(default_factory=lambda: _visualizer_default('bubble_ghost_alpha'))
    bubble_ghost_decay: float = field(default_factory=lambda: _visualizer_default('bubble_ghost_decay'))
    sine_line_dim: bool = field(default_factory=lambda: _visualizer_default('sine_line_dim'))
    # Dev Curve visualizer
    devcurve_active_layer: str = field(default_factory=lambda: _visualizer_default('devcurve_active_layer'))
    devcurve_layer_bass_shape_nodes: List[List[float]] = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_shape_nodes'))
    devcurve_layer_vocals_shape_nodes: List[List[float]] = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_shape_nodes'))
    devcurve_layer_mids_shape_nodes: List[List[float]] = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_shape_nodes'))
    devcurve_layer_transients_shape_nodes: List[List[float]] = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_shape_nodes'))
    devcurve_base_level: float = field(default_factory=lambda: _visualizer_default('devcurve_base_level'))
    devcurve_motion_power: float = field(default_factory=lambda: _visualizer_default('devcurve_motion_power'))
    devcurve_idle_motion: float = field(default_factory=lambda: _visualizer_default('devcurve_idle_motion'))
    devcurve_idle_speed: float = field(default_factory=lambda: _visualizer_default('devcurve_idle_speed'))
    devcurve_smoothness: float = field(default_factory=lambda: _visualizer_default('devcurve_smoothness'))
    devcurve_layer_bass_enabled: bool = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_enabled'))
    devcurve_layer_bass_color: Any = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_color'))
    devcurve_layer_bass_alpha: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_alpha'))
    devcurve_layer_bass_power: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_power'))
    devcurve_layer_bass_offset: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_offset'))
    devcurve_layer_bass_outline_color: Any = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_outline_color'))
    devcurve_layer_bass_outline_width: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_outline_width'))
    devcurve_layer_bass_order: int = field(default_factory=lambda: _visualizer_default('devcurve_layer_bass_order'))
    devcurve_layer_vocals_enabled: bool = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_enabled'))
    devcurve_layer_vocals_color: Any = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_color'))
    devcurve_layer_vocals_alpha: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_alpha'))
    devcurve_layer_vocals_power: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_power'))
    devcurve_layer_vocals_offset: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_offset'))
    devcurve_layer_vocals_outline_color: Any = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_outline_color'))
    devcurve_layer_vocals_outline_width: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_outline_width'))
    devcurve_layer_vocals_order: int = field(default_factory=lambda: _visualizer_default('devcurve_layer_vocals_order'))
    devcurve_layer_mids_enabled: bool = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_enabled'))
    devcurve_layer_mids_color: Any = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_color'))
    devcurve_layer_mids_alpha: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_alpha'))
    devcurve_layer_mids_power: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_power'))
    devcurve_layer_mids_offset: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_offset'))
    devcurve_layer_mids_outline_color: Any = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_outline_color'))
    devcurve_layer_mids_outline_width: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_outline_width'))
    devcurve_layer_mids_order: int = field(default_factory=lambda: _visualizer_default('devcurve_layer_mids_order'))
    devcurve_layer_transients_enabled: bool = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_enabled'))
    devcurve_layer_transients_color: Any = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_color'))
    devcurve_layer_transients_alpha: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_alpha'))
    devcurve_layer_transients_power: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_power'))
    devcurve_layer_transients_offset: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_offset'))
    devcurve_layer_transients_outline_color: Any = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_outline_color'))
    devcurve_layer_transients_outline_width: float = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_outline_width'))
    devcurve_layer_transients_order: int = field(default_factory=lambda: _visualizer_default('devcurve_layer_transients_order'))
    devcurve_ghosting_enabled: bool = field(default_factory=lambda: _visualizer_default('devcurve_ghosting_enabled'))
    devcurve_ghost_alpha: float = field(default_factory=lambda: _visualizer_default('devcurve_ghost_alpha'))
    devcurve_ghost_decay: float = field(default_factory=lambda: _visualizer_default('devcurve_ghost_decay'))
    devcurve_foreground_shadow_enabled: bool = field(default_factory=lambda: _visualizer_default('devcurve_foreground_shadow_enabled'))
    devcurve_foreground_shadow_alpha: float = field(default_factory=lambda: _visualizer_default('devcurve_foreground_shadow_alpha'))
    devcurve_foreground_shadow_darken: float = field(default_factory=lambda: _visualizer_default('devcurve_foreground_shadow_darken'))
    devcurve_foreground_shadow_offset: float = field(default_factory=lambda: _visualizer_default('devcurve_foreground_shadow_offset'))
    devcurve_foreground_specular_enabled: bool = field(default_factory=lambda: _visualizer_default('devcurve_foreground_specular_enabled'))
    devcurve_foreground_specular_alpha: float = field(default_factory=lambda: _visualizer_default('devcurve_foreground_specular_alpha'))
    devcurve_foreground_specular_width: float = field(default_factory=lambda: _visualizer_default('devcurve_foreground_specular_width'))
    devcurve_foreground_specular_offset: float = field(default_factory=lambda: _visualizer_default('devcurve_foreground_specular_offset'))
    devcurve_foreground_specular_crest_bias: float = field(default_factory=lambda: _visualizer_default('devcurve_foreground_specular_crest_bias'))
    sphere_finish: str = field(default_factory=lambda: _visualizer_default('sphere_finish'))
    sphere_fill_color: list[int] = field(default_factory=lambda: deepcopy(_visualizer_default('sphere_fill_color')))
    sphere_edge_color: list[int] = field(default_factory=lambda: deepcopy(_visualizer_default('sphere_edge_color')))
    sphere_tracer_color: list[int] = field(default_factory=lambda: deepcopy(_visualizer_default('sphere_tracer_color')))
    sphere_edge_weight: float = field(default_factory=lambda: _visualizer_default('sphere_edge_weight'))
    sphere_voxel_size_variation: float = field(default_factory=lambda: _visualizer_default('sphere_voxel_size_variation'))
    sphere_depth_shading_enabled: bool = field(default_factory=lambda: _visualizer_default('sphere_depth_shading_enabled'))
    sphere_depth_shading_strength: float = field(default_factory=lambda: _visualizer_default('sphere_depth_shading_strength'))
    sphere_allow_overflow: bool = field(default_factory=lambda: _visualizer_default('sphere_allow_overflow'))
    sphere_cel_shading: bool = field(default_factory=lambda: _visualizer_default('sphere_cel_shading'))
    sphere_light_tracer_enabled: bool = field(default_factory=lambda: _visualizer_default('sphere_light_tracer_enabled'))
    sphere_fragment_interpolation_enabled: bool = field(default_factory=lambda: _visualizer_default('sphere_fragment_interpolation_enabled'))
    sphere_incoming_density_response_enabled: bool = field(default_factory=lambda: _visualizer_default('sphere_incoming_density_response_enabled'))
    sphere_incoming_transient_velocity_enabled: bool = field(default_factory=lambda: _visualizer_default('sphere_incoming_transient_velocity_enabled'))
    sphere_particle_outtake_enabled: bool = field(default_factory=lambda: _visualizer_default('sphere_particle_outtake_enabled'))
    sphere_shadow_enabled: bool = field(default_factory=lambda: _visualizer_default('sphere_shadow_enabled'))
    sphere_shadow_opacity: float = field(default_factory=lambda: _visualizer_default('sphere_shadow_opacity'))
    sphere_shadow_softness: float = field(default_factory=lambda: _visualizer_default('sphere_shadow_softness'))
    sphere_shadow_distance: float = field(default_factory=lambda: _visualizer_default('sphere_shadow_distance'))
    sphere_shadow_size: float = field(default_factory=lambda: _visualizer_default('sphere_shadow_size'))
    sphere_fade_incoming_blocks: bool = field(default_factory=lambda: _visualizer_default('sphere_fade_incoming_blocks'))
    sphere_fragment_strength: float = field(default_factory=lambda: _visualizer_default('sphere_fragment_strength'))
    sphere_particle_distance: float = field(default_factory=lambda: _visualizer_default('sphere_particle_distance'))
    sphere_particle_amount: float = field(default_factory=lambda: _visualizer_default('sphere_particle_amount'))
    sphere_perspective_strength: float = field(default_factory=lambda: _visualizer_default('sphere_perspective_strength'))
    sphere_taste_the_rainbow_enabled: bool = field(default_factory=lambda: _visualizer_default('sphere_taste_the_rainbow_enabled'))
    sphere_taste_the_rainbow_surfaces: bool = field(default_factory=lambda: _visualizer_default('sphere_taste_the_rainbow_surfaces'))
    sphere_taste_the_rainbow_edges: bool = field(default_factory=lambda: _visualizer_default('sphere_taste_the_rainbow_edges'))
    sphere_base_rotation_speed: float = field(default_factory=lambda: _visualizer_default('sphere_base_rotation_speed'))
    sphere_rotation_speed: float = field(default_factory=lambda: _visualizer_default('sphere_rotation_speed'))
    sphere_gloss: float = field(default_factory=lambda: _visualizer_default('sphere_gloss'))
    sphere_specular: float = field(default_factory=lambda: _visualizer_default('sphere_specular'))
    sphere_light_direction: str = field(default_factory=lambda: _visualizer_default('sphere_light_direction'))
    sphere_vocal_response: float = field(default_factory=lambda: _visualizer_default('sphere_vocal_response'))
    sphere_size_response: float = field(default_factory=lambda: _visualizer_default('sphere_size_response'))
    # Visualizer presets (0=Preset 1/Default, 1=Preset 2, 2=Preset 3, 3=Custom)
    preset_spectrum: int = field(default_factory=lambda: _visualizer_default('preset_spectrum'))
    preset_oscilloscope: int = field(default_factory=lambda: _visualizer_default('preset_oscilloscope'))
    preset_sine_wave: int = field(default_factory=lambda: _visualizer_default('preset_sine_wave'))
    preset_bubble: int = field(default_factory=lambda: _visualizer_default('preset_bubble'))
    preset_devcurve: int = field(default_factory=lambda: _visualizer_default('preset_devcurve'))
    preset_sphere: int = field(default_factory=lambda: _visualizer_default('preset_sphere'))

    def __post_init__(self):
        self._apply_core_visual_defaults()
        self._apply_oscilloscope_defaults()
        self._apply_sine_defaults()
        self._apply_bubble_defaults()
        self._apply_devcurve_defaults()
        self._apply_sphere_defaults()

    def _apply_list_default(self, attr: str, value: list[int]) -> None:
        if getattr(self, attr) is None:
            setattr(self, attr, list(value))

    def _ensure_non_empty_nodes(self, attr: str) -> None:
        value = getattr(self, attr)
        if not isinstance(value, list) or not value:
            setattr(self, attr, deepcopy(_visualizer_default(attr)))

    def _apply_core_visual_defaults(self) -> None:
        if self.osc_glow_color is None:
            self.osc_glow_color = deepcopy(_visualizer_default("osc_glow_color"))
        if self.bar_fill_color is None:
            self.bar_fill_color = deepcopy(_active_visualizer_default("bar_fill_color"))
        if self.bar_border_color is None:
            self.bar_border_color = deepcopy(_active_visualizer_default("bar_border_color"))
        for mode in PER_MODE_TECHNICAL_MODES:
            fill_attr = f"{mode}_bar_fill_color"
            border_attr = f"{mode}_bar_border_color"
            opacity_attr = f"{mode}_bar_border_opacity"
            if getattr(self, fill_attr) is None:
                setattr(self, fill_attr, deepcopy(_visualizer_default(fill_attr)))
            if getattr(self, border_attr) is None:
                setattr(self, border_attr, deepcopy(_visualizer_default(border_attr)))
            try:
                mode_opacity = float(getattr(self, opacity_attr))
            except Exception:
                mode_opacity = float(_visualizer_default(opacity_attr))
            setattr(self, opacity_attr, mode_opacity)
 
    def _apply_oscilloscope_defaults(self) -> None:
        _apply_canonical_list_defaults(self, _OSC_SERIALIZERS)

    def _apply_sine_defaults(self) -> None:
        _apply_canonical_list_defaults(self, _SINE_SERIALIZERS)

    def _apply_bubble_defaults(self) -> None:
        _apply_canonical_list_defaults(self, _BUBBLE_SERIALIZERS)

    def _apply_devcurve_defaults(self) -> None:
        _apply_canonical_list_defaults(self, _DEVCURVE_SERIALIZERS)
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
            self._ensure_non_empty_nodes(attr)
        _normalize_ranked_attrs(self, _DEVCURVE_ORDER_ATTRS)

    def _apply_sphere_defaults(self) -> None:
        _apply_canonical_list_defaults(self, _SPHERE_SERIALIZERS)
        self.sphere_allow_overflow = bool(self.sphere_allow_overflow)
        self.sphere_cel_shading = bool(self.sphere_cel_shading)
        self.sphere_light_tracer_enabled = bool(self.sphere_light_tracer_enabled)
        self.sphere_fragment_interpolation_enabled = bool(self.sphere_fragment_interpolation_enabled)
        self.sphere_incoming_density_response_enabled = bool(self.sphere_incoming_density_response_enabled)
        self.sphere_incoming_transient_velocity_enabled = bool(self.sphere_incoming_transient_velocity_enabled)
        self.sphere_particle_outtake_enabled = bool(self.sphere_particle_outtake_enabled)
        self.sphere_shadow_enabled = bool(self.sphere_shadow_enabled)
        self.sphere_depth_shading_enabled = bool(self.sphere_depth_shading_enabled)
        self.sphere_fade_incoming_blocks = bool(self.sphere_fade_incoming_blocks)
        self.sphere_taste_the_rainbow_enabled = bool(self.sphere_taste_the_rainbow_enabled)
        self.sphere_taste_the_rainbow_surfaces = bool(self.sphere_taste_the_rainbow_surfaces)
        self.sphere_taste_the_rainbow_edges = bool(self.sphere_taste_the_rainbow_edges)
        self.sphere_finish = normalize_sphere_finish(self.sphere_finish)
        for attr in ("sphere_fill_color", "sphere_edge_color", "sphere_tracer_color"):
            value = list(getattr(self, attr))
            fallback = list(_visualizer_default(attr))
            if len(value) < 3:
                value = fallback
            while len(value) < 4:
                value.append(255)
            setattr(
                self,
                attr,
                [max(0, min(255, int(round(float(channel))))) for channel in value[:4]],
            )
        self.sphere_light_direction = str(self.sphere_light_direction).strip().upper()
        if self.sphere_light_direction not in {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}:
            raise ValueError(f"invalid sphere light direction {self.sphere_light_direction!r}")
        for attr, low, high in (("sphere_fragment_strength", 0.0, 9.0), ("sphere_particle_distance", 0.0, 4.5), ("sphere_particle_amount", 0.25, 1.75), ("sphere_perspective_strength", 0.0, 1.0), ("sphere_edge_weight", 0.25, 1.75), ("sphere_voxel_size_variation", 0.0, 1.0), ("sphere_depth_shading_strength", 0.0, 0.5), ("sphere_shadow_opacity", 0.0, 2.0), ("sphere_shadow_softness", 0.0, 0.45), ("sphere_shadow_distance", 0.0, 2.5), ("sphere_shadow_size", 0.6, 1.6), ("sphere_base_rotation_speed", 0.0, 0.5), ("sphere_rotation_speed", 0.0, 2.0), ("sphere_gloss", 0.0, 1.0), ("sphere_specular", 0.0, 2.0), ("sphere_vocal_response", 0.0, 1.35), ("sphere_size_response", 0.0, 2.54)):
            _clamp_attr_range(self, attr, low, high)

    @property
    def enabled_modes(self) -> tuple[str, ...]:
        """Derived canonical enabled-id view; never persisted as product state."""

        return resolve_effective_enabled_modes(self.mode_activation)

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
        )

    @classmethod
    def from_settings(cls, settings: "SettingsManager", prefix: str = "widgets.spotify_visualizer") -> "SpotifyVisualizerSettings":
        """Load Spotify visualizer settings from SettingsManager."""
        get = settings.get
        _get, _mode_value = _build_settings_readers(settings, prefix=prefix)

        try:
            bubble_gradient_semantics_version = int(
                _get(
                    "bubble_gradient_semantics_version",
                    _visualizer_default("bubble_gradient_semantics_version"),
                )
            )
        except (TypeError, ValueError):
            bubble_gradient_semantics_version = int(
                _visualizer_default("bubble_gradient_semantics_version")
            )
        _preset_kwargs = resolve_all_preset_indices_from_getter(get, prefix=prefix)
        _active_mode = coerce_visualizer_mode_id(
            str(get(f"{prefix}.mode", _visualizer_default("mode")))
        )

        kwargs = cls._build_constructor_kwargs_from_mode_state(
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
        )
        kwargs["mode_activation"] = normalize_visualizer_mode_activation(
            get(f"{prefix}.mode_activation", _visualizer_default("mode_activation"))
        )
        return cls(**kwargs)

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
        _raw = migrate_legacy_sphere_finish_keys(data, prefix=prefix)
        _raw = migrate_legacy_sphere_control_keys(_raw, prefix=prefix)
        _raw = strip_retired_visualizer_settings(_raw, prefix=prefix)
        _raw = strip_legacy_global_technical_keys(_raw, prefix=prefix)
        _raw = migrate_legacy_global_visual_keys(_raw, prefix=prefix)
        _mode = coerce_visualizer_mode_id(
            _raw.get(
                "mode",
                _raw.get(f"{prefix}.mode", _visualizer_default("mode")),
            )
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

        kwargs = cls._build_constructor_kwargs_from_mode_state(
            _get,
            lambda mode, key, default: _get_per_mode_value(mode, key, default),
            lambda key, default: _get_mode_value(key, default),
            active_mode=_mode,
            preset_kwargs=_preset_kwargs,
            bubble_gradient_semantics_version=bubble_gradient_semantics_version,
        )
        kwargs["mode_activation"] = normalize_visualizer_mode_activation(
            _get("mode_activation", _visualizer_default("mode_activation"))
        )
        return cls(**kwargs)

    def to_dict(self, prefix: str = "widgets.spotify_visualizer") -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return _merge_serialized_sections(
            self._serialize_core_settings(prefix),
            self._serialize_osc_settings(prefix),
            self._serialize_spectrum_settings(prefix),
            self._serialize_sine_settings(prefix),
            self._serialize_bubble_settings(prefix),
            self._serialize_devcurve_settings(prefix),
            self._serialize_sphere_settings(prefix),
            self._serialize_preset_indices(prefix),
            self._serialize_per_mode_technical_settings(prefix),
            self._serialize_transient_mix_settings(prefix),
        )

    def _serialize_core_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _CORE_SETTINGS_SERIALIZERS)

    def _serialize_osc_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _OSC_SERIALIZERS)

    def _serialize_spectrum_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _SPECTRUM_SERIALIZERS)

    def _serialize_sine_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _SINE_SERIALIZERS)

    def _serialize_bubble_settings(self, prefix: str) -> Dict[str, Any]:
        data = _serialize_prefixed_fields(self, prefix, _BUBBLE_SERIALIZERS)
        data[f"{prefix}.bubble_gradient_semantics_version"] = CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION
        return data

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

    def _serialize_sphere_settings(self, prefix: str) -> Dict[str, Any]:
        return _serialize_prefixed_fields(self, prefix, _SPHERE_SERIALIZERS)

    @staticmethod
    def _normalize_mode_name(mode: str) -> str:
        from core.settings.visualizer_mode_registry import get_technical_profile_mode

        profile = get_technical_profile_mode(str(mode).lower())
        if profile not in PER_MODE_TECHNICAL_MODES:
            raise ValueError(f"invalid visualizer technical profile: {profile!r}")
        return profile

    def _mode_attr_name(self, mode: str, base_key: str) -> str:
        normalized = self._normalize_mode_name(mode)
        return f"{normalized}_{base_key}"

    def _resolve_mode_value(self, mode: str, base_key: str) -> Any:
        return getattr(self, self._mode_attr_name(mode, base_key))

    def _resolve_mode_value_with(self, mode: str, base_key: str) -> Any:
        resolver = _PER_MODE_RESOLVERS[base_key]
        attr_name = self._mode_attr_name(mode, base_key)
        value = getattr(self, attr_name)
        if value is None:
            value = _visualizer_default(attr_name)
        return resolver(value)

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

    def resolve_sine_wave_transient_width_mix(self) -> float:
        return float(self.sine_wave_transient_width_mix)

    def resolve_oscilloscope_transient_width_mix(self) -> float:
        return float(self.oscilloscope_transient_width_mix)
