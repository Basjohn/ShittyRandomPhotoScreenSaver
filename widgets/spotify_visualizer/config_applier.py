"""Centralised keyword→attribute mapping for SpotifyVisualizerWidget settings.

Extracted from ``spotify_visualizer_widget.apply_vis_mode_config`` to reduce
the main widget file below the 1500-line monolith threshold.  The public
function ``apply_vis_mode_kwargs`` takes the widget instance and a kwargs dict
and writes validated values into the widget's per-mode attributes.
"""
from __future__ import annotations

from typing import Any, Dict

from PySide6.QtGui import QColor

from core.logging.logger import get_logger

logger = get_logger(__name__)


def _color_or_none(value: Any) -> QColor | None:
    """Return a QColor if *value* is a list/tuple of ≥3 ints, else None."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return QColor(*value)
    return None


def apply_vis_mode_kwargs(widget: Any, kwargs: Dict[str, Any]) -> None:
    """Apply per-mode keyword settings to *widget*.

    Each key is checked in *kwargs*; if present the value is validated,
    clamped, and written to the corresponding ``widget._*`` attribute.
    """

    # --- Oscilloscope -------------------------------------------------
    if 'osc_glow_enabled' in kwargs:
        widget._osc_glow_enabled = bool(kwargs['osc_glow_enabled'])
    if 'osc_glow_intensity' in kwargs:
        widget._osc_glow_intensity = max(0.0, float(kwargs['osc_glow_intensity']))
    if 'osc_glow_color' in kwargs:
        c = _color_or_none(kwargs['osc_glow_color'])
        if c is not None:
            widget._osc_glow_color = c
    if 'osc_reactive_glow' in kwargs:
        widget._osc_reactive_glow = bool(kwargs['osc_reactive_glow'])
    if 'osc_sensitivity' in kwargs:
        widget._osc_sensitivity = max(0.5, min(10.0, float(kwargs['osc_sensitivity'])))
    if 'osc_smoothing' in kwargs:
        widget._osc_smoothing = max(0.0, min(1.0, float(kwargs['osc_smoothing'])))
    if 'osc_line_color' in kwargs:
        c = _color_or_none(kwargs['osc_line_color'])
        if c is not None:
            widget._osc_line_color = c
    if 'osc_line_count' in kwargs:
        widget._osc_line_count = max(1, min(3, int(kwargs['osc_line_count'])))
    if 'osc_line2_color' in kwargs:
        c = _color_or_none(kwargs['osc_line2_color'])
        if c is not None:
            widget._osc_line2_color = c
    if 'osc_line2_glow_color' in kwargs:
        c = _color_or_none(kwargs['osc_line2_glow_color'])
        if c is not None:
            widget._osc_line2_glow_color = c
    if 'osc_line3_color' in kwargs:
        c = _color_or_none(kwargs['osc_line3_color'])
        if c is not None:
            widget._osc_line3_color = c
    if 'osc_line3_glow_color' in kwargs:
        c = _color_or_none(kwargs['osc_line3_glow_color'])
        if c is not None:
            widget._osc_line3_glow_color = c

    # --- Starfield ----------------------------------------------------
    if 'star_travel_speed' in kwargs:
        widget._star_travel_speed = max(0.0, float(kwargs['star_travel_speed']))
    if 'star_reactivity' in kwargs:
        widget._star_reactivity = max(0.0, float(kwargs['star_reactivity']))
    if 'star_density' in kwargs:
        widget._star_density = max(0.1, float(kwargs['star_density']))
    if 'nebula_tint1' in kwargs:
        c = kwargs['nebula_tint1']
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            widget._nebula_tint1 = QColor(c[0], c[1], c[2])
    if 'nebula_tint2' in kwargs:
        c = kwargs['nebula_tint2']
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            widget._nebula_tint2 = QColor(c[0], c[1], c[2])
    if 'nebula_cycle_speed' in kwargs:
        widget._nebula_cycle_speed = max(0.0, min(1.0, float(kwargs['nebula_cycle_speed'])))

    # --- Blob ---------------------------------------------------------
    if 'blob_color' in kwargs:
        c = _color_or_none(kwargs['blob_color'])
        if c is not None:
            widget._blob_color = c
    if 'blob_glow_color' in kwargs:
        c = _color_or_none(kwargs['blob_glow_color'])
        if c is not None:
            widget._blob_glow_color = c
    if 'blob_edge_color' in kwargs:
        c = _color_or_none(kwargs['blob_edge_color'])
        if c is not None:
            widget._blob_edge_color = c
    if 'blob_outline_color' in kwargs:
        c = _color_or_none(kwargs['blob_outline_color'])
        if c is not None:
            widget._blob_outline_color = c
    if 'blob_pulse' in kwargs:
        widget._blob_pulse = max(0.0, float(kwargs['blob_pulse']))
    if 'blob_width' in kwargs:
        widget._blob_width = max(0.1, min(1.0, float(kwargs['blob_width'])))
    if 'blob_size' in kwargs:
        widget._blob_size = max(0.3, min(2.0, float(kwargs['blob_size'])))
    if 'blob_glow_intensity' in kwargs:
        widget._blob_glow_intensity = max(0.0, min(1.0, float(kwargs['blob_glow_intensity'])))
    if 'blob_reactive_glow' in kwargs:
        widget._blob_reactive_glow = bool(kwargs['blob_reactive_glow'])
    if 'blob_reactive_deformation' in kwargs:
        widget._blob_reactive_deformation = max(0.0, min(3.0, float(kwargs['blob_reactive_deformation'])))
    if 'blob_stage_gain' in kwargs:
        widget._blob_stage_gain = max(0.0, min(2.0, float(kwargs['blob_stage_gain'])))
    if 'blob_core_scale' in kwargs:
        widget._blob_core_scale = max(0.25, min(2.5, float(kwargs['blob_core_scale'])))
    if 'blob_core_floor_bias' in kwargs:
        widget._blob_core_floor_bias = max(0.0, min(0.6, float(kwargs['blob_core_floor_bias'])))
    if 'blob_stage_bias' in kwargs:
        widget._blob_stage_bias = max(-0.35, min(0.35, float(kwargs['blob_stage_bias'])))
    if 'blob_stage2_release_ms' in kwargs:
        widget._blob_stage2_release_ms = max(200.0, min(4000.0, float(kwargs['blob_stage2_release_ms'])))
    if 'blob_stage3_release_ms' in kwargs:
        widget._blob_stage3_release_ms = max(200.0, min(4000.0, float(kwargs['blob_stage3_release_ms'])))
    if 'blob_constant_wobble' in kwargs:
        widget._blob_constant_wobble = max(0.0, min(2.0, float(kwargs['blob_constant_wobble'])))
    if 'blob_reactive_wobble' in kwargs:
        widget._blob_reactive_wobble = max(0.0, min(2.0, float(kwargs['blob_reactive_wobble'])))
    if 'blob_stretch_tendency' in kwargs:
        widget._blob_stretch_tendency = max(0.0, min(1.0, float(kwargs['blob_stretch_tendency'])))

    # --- Helix --------------------------------------------------------
    if 'helix_turns' in kwargs:
        widget._helix_turns = max(2, int(kwargs['helix_turns']))
    if 'helix_double' in kwargs:
        widget._helix_double = bool(kwargs['helix_double'])
    if 'helix_speed' in kwargs:
        widget._helix_speed = max(0.0, float(kwargs['helix_speed']))
    if 'helix_glow_enabled' in kwargs:
        widget._helix_glow_enabled = bool(kwargs['helix_glow_enabled'])
    if 'helix_glow_intensity' in kwargs:
        widget._helix_glow_intensity = max(0.0, float(kwargs['helix_glow_intensity']))
    if 'helix_glow_color' in kwargs:
        c = _color_or_none(kwargs['helix_glow_color'])
        if c is not None:
            widget._helix_glow_color = c
    if 'helix_reactive_glow' in kwargs:
        widget._helix_reactive_glow = bool(kwargs['helix_reactive_glow'])

    # --- Spectrum -----------------------------------------------------
    if 'spectrum_single_piece' in kwargs:
        widget._spectrum_single_piece = bool(kwargs['spectrum_single_piece'])
    if 'spectrum_rainbow_per_bar' in kwargs:
        widget._rainbow_per_bar = bool(kwargs['spectrum_rainbow_per_bar'])

    if 'spectrum_border_radius' in kwargs:
        widget._spectrum_border_radius = max(0.0, min(20.0, float(kwargs['spectrum_border_radius'])))

    if 'spectrum_bar_profile' in kwargs:
        new_profile = str(kwargs['spectrum_bar_profile'])
        if new_profile not in ('legacy', 'curved', 'slanted'):
            new_profile = 'legacy'
        old_profile = getattr(widget, '_spectrum_bar_profile', 'legacy')
        widget._spectrum_bar_profile = new_profile
        # Curved profile flag for beat engine (both curved and slanted use non-legacy profile)
        new_curved = (new_profile != 'legacy')
        old_curved = (old_profile != 'legacy')
        if new_curved != old_curved:
            try:
                from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
                engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
                if engine is not None:
                    engine.set_curved_profile(new_curved)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to propagate bar profile to engine", exc_info=True)
    elif 'spectrum_curved_profile' in kwargs:
        # Backward compat: old bool key → new string
        new_curved = bool(kwargs['spectrum_curved_profile'])
        new_profile = 'curved' if new_curved else 'legacy'
        old_profile = getattr(widget, '_spectrum_bar_profile', 'legacy')
        widget._spectrum_bar_profile = new_profile
        old_curved = (old_profile != 'legacy')
        if new_curved != old_curved:
            try:
                from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
                engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
                if engine is not None:
                    engine.set_curved_profile(new_curved)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to propagate bar profile to engine", exc_info=True)

    # --- Height growth factors ----------------------------------------
    if 'spectrum_growth' in kwargs:
        widget._spectrum_growth = max(0.5, min(5.0, float(kwargs['spectrum_growth'])))
    if 'starfield_growth' in kwargs:
        widget._starfield_growth = max(0.5, min(5.0, float(kwargs['starfield_growth'])))
    if 'blob_growth' in kwargs:
        widget._blob_growth = max(0.5, min(5.0, float(kwargs['blob_growth'])))
    if 'osc_growth' in kwargs:
        widget._osc_growth = max(0.5, min(5.0, float(kwargs['osc_growth'])))
    if 'helix_growth' in kwargs:
        widget._helix_growth = max(0.5, min(5.0, float(kwargs['helix_growth'])))
    if 'osc_speed' in kwargs:
        widget._osc_speed = max(0.1, min(1.0, float(kwargs['osc_speed'])))
    if 'osc_line_dim' in kwargs:
        widget._osc_line_dim = bool(kwargs['osc_line_dim'])
    if 'osc_line_offset_bias' in kwargs:
        widget._osc_line_offset_bias = max(0.0, min(1.0, float(kwargs['osc_line_offset_bias'])))
    if 'osc_vertical_shift' in kwargs:
        widget._osc_vertical_shift = int(kwargs['osc_vertical_shift'])

    # --- Sine wave ----------------------------------------------------
    if 'sine_wave_growth' in kwargs:
        widget._sine_wave_growth = max(0.5, min(5.0, float(kwargs['sine_wave_growth'])))
    if 'sine_wave_travel' in kwargs:
        widget._sine_wave_travel = max(0, min(2, int(kwargs['sine_wave_travel'])))
    if 'sine_travel_line2' in kwargs:
        widget._sine_travel_line2 = max(0, min(2, int(kwargs['sine_travel_line2'])))
    if 'sine_travel_line3' in kwargs:
        widget._sine_travel_line3 = max(0, min(2, int(kwargs['sine_travel_line3'])))
    if 'sine_line1_shift' in kwargs:
        widget._sine_line1_shift = max(-1.0, min(1.0, float(kwargs['sine_line1_shift'])))
    if 'sine_line2_shift' in kwargs:
        widget._sine_line2_shift = max(-1.0, min(1.0, float(kwargs['sine_line2_shift'])))
    if 'sine_line3_shift' in kwargs:
        widget._sine_line3_shift = max(-1.0, min(1.0, float(kwargs['sine_line3_shift'])))
    if 'sine_wave_effect' in kwargs:
        widget._sine_wave_effect = max(0.0, min(1.0, float(kwargs['sine_wave_effect'])))
    if 'sine_micro_wobble' in kwargs:
        widget._sine_micro_wobble = max(0.0, min(1.0, float(kwargs['sine_micro_wobble'])))
    if 'sine_width_reaction' in kwargs:
        widget._sine_width_reaction = max(0.0, min(1.0, float(kwargs['sine_width_reaction'])))
    if 'sine_density' in kwargs:
        widget._sine_density = max(0.25, min(3.0, float(kwargs['sine_density'])))
    if 'sine_displacement' in kwargs:
        widget._sine_displacement = max(0.0, min(1.0, float(kwargs['sine_displacement'])))
    if 'sine_vertical_shift' in kwargs:
        widget._sine_vertical_shift = int(kwargs['sine_vertical_shift'])
    if 'sine_card_adaptation' in kwargs:
        widget._sine_card_adaptation = max(0.05, min(1.0, float(kwargs['sine_card_adaptation'])))
    if 'sine_glow_enabled' in kwargs:
        widget._sine_glow_enabled = bool(kwargs['sine_glow_enabled'])
    if 'sine_glow_intensity' in kwargs:
        widget._sine_glow_intensity = max(0.0, float(kwargs['sine_glow_intensity']))
    if 'sine_glow_color' in kwargs:
        c = _color_or_none(kwargs['sine_glow_color'])
        if c is not None:
            widget._sine_glow_color = c
    if 'sine_line_color' in kwargs:
        c = _color_or_none(kwargs['sine_line_color'])
        if c is not None:
            widget._sine_line_color = c
    if 'sine_reactive_glow' in kwargs:
        widget._sine_reactive_glow = bool(kwargs['sine_reactive_glow'])
    if 'sine_sensitivity' in kwargs:
        widget._sine_sensitivity = max(0.1, min(5.0, float(kwargs['sine_sensitivity'])))
    if 'sine_speed' in kwargs:
        widget._sine_speed = max(0.1, min(1.0, float(kwargs['sine_speed'])))
    if 'sine_line_count' in kwargs:
        widget._sine_line_count = max(1, min(3, int(kwargs['sine_line_count'])))
    if 'sine_line_offset_bias' in kwargs:
        widget._sine_line_offset_bias = max(0.0, min(1.0, float(kwargs['sine_line_offset_bias'])))
    if 'sine_line_dim' in kwargs:
        widget._sine_line_dim = bool(kwargs['sine_line_dim'])
    if 'sine_line2_color' in kwargs:
        c = _color_or_none(kwargs['sine_line2_color'])
        if c is not None:
            widget._sine_line2_color = c
    if 'sine_line2_glow_color' in kwargs:
        c = _color_or_none(kwargs['sine_line2_glow_color'])
        if c is not None:
            widget._sine_line2_glow_color = c
    if 'sine_line3_color' in kwargs:
        c = _color_or_none(kwargs['sine_line3_color'])
        if c is not None:
            widget._sine_line3_color = c
    if 'sine_line3_glow_color' in kwargs:
        c = _color_or_none(kwargs['sine_line3_glow_color'])
        if c is not None:
            widget._sine_line3_glow_color = c

    # --- Rainbow (global, all modes) -----------------------------------
    if 'rainbow_enabled' in kwargs:
        widget._rainbow_enabled = bool(kwargs['rainbow_enabled'])
    if 'rainbow_speed' in kwargs:
        widget._rainbow_speed = max(0.01, min(5.0, float(kwargs['rainbow_speed'])))
    if 'rainbow_per_bar' in kwargs:
        widget._rainbow_per_bar = bool(kwargs['rainbow_per_bar'])

    # --- Oscilloscope ghost trail ----------------------------------------
    if 'osc_ghosting_enabled' in kwargs:
        widget._osc_ghosting_enabled = bool(kwargs['osc_ghosting_enabled'])
    if 'osc_ghost_intensity' in kwargs:
        widget._osc_ghost_intensity = max(0.0, min(1.0, float(kwargs['osc_ghost_intensity'])))

    # --- Sine Wave Heartbeat -----------------------------------------------
    if 'sine_heartbeat' in kwargs:
        widget._sine_heartbeat = max(0.0, min(1.0, float(kwargs['sine_heartbeat'])))

    # --- Bubble -----------------------------------------------------------
    if 'bubble_big_bass_pulse' in kwargs:
        widget._bubble_big_bass_pulse = max(0.0, min(1.0, float(kwargs['bubble_big_bass_pulse'])))
    if 'bubble_small_freq_pulse' in kwargs:
        widget._bubble_small_freq_pulse = max(0.0, min(1.0, float(kwargs['bubble_small_freq_pulse'])))
    if 'bubble_stream_direction' in kwargs:
        val = str(kwargs['bubble_stream_direction']).lower()
        if val not in ('none', 'up', 'down', 'left', 'right', 'diagonal', 'random'):
            val = 'up'
        widget._bubble_stream_direction = val
    if 'bubble_stream_constant_speed' in kwargs:
        widget._bubble_stream_constant_speed = max(
            0.0, min(2.0, float(kwargs['bubble_stream_constant_speed']))
        )
    if 'bubble_stream_speed_cap' in kwargs:
        widget._bubble_stream_speed_cap = max(
            0.1, min(4.0, float(kwargs['bubble_stream_speed_cap']))
        )
    if 'bubble_stream_reactivity' in kwargs:
        widget._bubble_stream_reactivity = max(0.0, min(1.0, float(kwargs['bubble_stream_reactivity'])))
    if 'bubble_rotation_amount' in kwargs:
        widget._bubble_rotation_amount = max(0.0, min(1.0, float(kwargs['bubble_rotation_amount'])))
    if 'bubble_drift_amount' in kwargs:
        widget._bubble_drift_amount = max(0.0, min(1.0, float(kwargs['bubble_drift_amount'])))
    if 'bubble_drift_speed' in kwargs:
        widget._bubble_drift_speed = max(0.0, min(1.0, float(kwargs['bubble_drift_speed'])))
    if 'bubble_drift_frequency' in kwargs:
        widget._bubble_drift_frequency = max(0.0, min(1.0, float(kwargs['bubble_drift_frequency'])))
    if 'bubble_drift_direction' in kwargs:
        val = str(kwargs['bubble_drift_direction']).lower()
        valid_dirs = ('none', 'left', 'right', 'diagonal', 'swish_horizontal', 'swish_vertical', 'random')
        if val not in valid_dirs:
            val = 'random'
        widget._bubble_drift_direction = val
    if 'bubble_big_count' in kwargs:
        widget._bubble_big_count = max(1, min(30, int(kwargs['bubble_big_count'])))
    if 'bubble_small_count' in kwargs:
        widget._bubble_small_count = max(5, min(80, int(kwargs['bubble_small_count'])))
    if 'bubble_surface_reach' in kwargs:
        widget._bubble_surface_reach = max(0.0, min(1.0, float(kwargs['bubble_surface_reach'])))
    if 'bubble_outline_color' in kwargs:
        c = _color_or_none(kwargs['bubble_outline_color'])
        if c is not None:
            widget._bubble_outline_color = c
    if 'bubble_specular_color' in kwargs:
        c = _color_or_none(kwargs['bubble_specular_color'])
        if c is not None:
            widget._bubble_specular_color = c
    if 'bubble_gradient_light' in kwargs:
        c = _color_or_none(kwargs['bubble_gradient_light'])
        if c is not None:
            widget._bubble_gradient_light = c
    if 'bubble_gradient_dark' in kwargs:
        c = _color_or_none(kwargs['bubble_gradient_dark'])
        if c is not None:
            widget._bubble_gradient_dark = c
    if 'bubble_pop_color' in kwargs:
        c = _color_or_none(kwargs['bubble_pop_color'])
        if c is not None:
            widget._bubble_pop_color = c
    if 'bubble_specular_direction' in kwargs:
        val = str(kwargs['bubble_specular_direction']).lower()
        if val not in ('top_left', 'top_right', 'bottom_left', 'bottom_right'):
            val = 'top_left'
        widget._bubble_specular_direction = val
    if 'bubble_big_size_max' in kwargs:
        widget._bubble_big_size_max = max(0.010, min(0.060, float(kwargs['bubble_big_size_max'])))
    if 'bubble_small_size_max' in kwargs:
        widget._bubble_small_size_max = max(0.004, min(0.030, float(kwargs['bubble_small_size_max'])))
    if 'bubble_growth' in kwargs:
        widget._bubble_growth = max(1.0, min(5.0, float(kwargs['bubble_growth'])))
    if 'bubble_trail_strength' in kwargs:
        # Trails are temporarily disabled until the gradient taper rework lands.
        widget._bubble_trail_strength = 0.0


def build_gpu_push_extra_kwargs(widget: Any, mode_str: str, engine: Any) -> Dict[str, Any]:
    """Build the extra kwargs dict for non-spectrum GPU push.

    Reads per-mode attributes from *widget* and returns a dict suitable for
    ``push_spotify_visualizer_frame(**extra)``.
    """
    extra: Dict[str, Any] = {}
    # Rainbow applies to ALL modes (including spectrum)
    extra['rainbow_enabled'] = getattr(widget, '_rainbow_enabled', False)
    extra['rainbow_speed'] = getattr(widget, '_rainbow_speed', 0.5)
    extra['rainbow_per_bar'] = getattr(widget, '_rainbow_per_bar', False)
    extra['osc_ghosting_enabled'] = getattr(widget, '_osc_ghosting_enabled', False)
    extra['osc_ghost_intensity'] = getattr(widget, '_osc_ghost_intensity', 0.4)
    extra['sine_heartbeat'] = getattr(widget, '_sine_heartbeat', 0.0)
    extra['heartbeat_intensity'] = getattr(widget, '_heartbeat_intensity', 0.0)
    extra['sine_density'] = getattr(widget, '_sine_density', 1.0)
    extra['sine_displacement'] = getattr(widget, '_sine_displacement', 0.0)
    if mode_str == 'spectrum':
        return extra

    if engine is not None:
        extra['waveform'] = engine.get_waveform()
        extra['energy_bands'] = engine.get_energy_bands()

    _is_sine = (mode_str == 'sine_wave')
    extra['glow_enabled'] = widget._sine_glow_enabled if _is_sine else widget._osc_glow_enabled
    extra['glow_intensity'] = widget._sine_glow_intensity if _is_sine else widget._osc_glow_intensity
    extra['glow_color'] = widget._sine_glow_color if _is_sine else widget._osc_glow_color
    extra['reactive_glow'] = widget._sine_reactive_glow if _is_sine else widget._osc_reactive_glow
    extra['osc_sensitivity'] = widget._sine_sensitivity if _is_sine else widget._osc_sensitivity
    extra['osc_smoothing'] = widget._osc_smoothing
    extra['star_density'] = widget._star_density
    extra['travel_speed'] = widget._star_travel_speed
    extra['star_reactivity'] = widget._star_reactivity
    extra['nebula_tint1'] = widget._nebula_tint1
    extra['nebula_tint2'] = widget._nebula_tint2
    extra['nebula_cycle_speed'] = widget._nebula_cycle_speed
    extra['blob_color'] = widget._blob_color
    extra['blob_glow_color'] = widget._blob_glow_color
    extra['blob_edge_color'] = widget._blob_edge_color
    extra['blob_outline_color'] = widget._blob_outline_color
    extra['blob_pulse'] = widget._blob_pulse
    extra['blob_width'] = widget._blob_width
    extra['blob_size'] = widget._blob_size
    extra['blob_glow_intensity'] = widget._blob_glow_intensity
    extra['blob_reactive_glow'] = widget._blob_reactive_glow
    extra['blob_reactive_deformation'] = widget._blob_reactive_deformation
    extra['blob_stage_gain'] = widget._blob_stage_gain
    extra['blob_core_scale'] = widget._blob_core_scale
    extra['blob_core_floor_bias'] = widget._blob_core_floor_bias
    extra['blob_stage_bias'] = getattr(widget, '_blob_stage_bias', 0.0)
    extra['blob_stage2_release_ms'] = getattr(widget, '_blob_stage2_release_ms', 900.0)
    extra['blob_stage3_release_ms'] = getattr(widget, '_blob_stage3_release_ms', 1200.0)
    extra['blob_constant_wobble'] = widget._blob_constant_wobble
    extra['blob_reactive_wobble'] = widget._blob_reactive_wobble
    extra['blob_stretch_tendency'] = widget._blob_stretch_tendency
    extra['osc_speed'] = widget._sine_speed if _is_sine else widget._osc_speed
    extra['osc_line_dim'] = widget._sine_line_dim if _is_sine else widget._osc_line_dim
    extra['osc_line_offset_bias'] = widget._sine_line_offset_bias if _is_sine else widget._osc_line_offset_bias
    extra['osc_vertical_shift'] = widget._osc_vertical_shift
    extra['osc_sine_travel'] = widget._sine_wave_travel
    extra['sine_card_adaptation'] = widget._sine_card_adaptation
    extra['sine_travel_line2'] = widget._sine_travel_line2
    extra['sine_travel_line3'] = widget._sine_travel_line3
    extra['sine_line1_shift'] = getattr(widget, '_sine_line1_shift', 0.0)
    extra['sine_line2_shift'] = getattr(widget, '_sine_line2_shift', 0.0)
    extra['sine_line3_shift'] = getattr(widget, '_sine_line3_shift', 0.0)
    extra['sine_wave_effect'] = widget._sine_wave_effect
    extra['sine_micro_wobble'] = widget._sine_micro_wobble
    extra['sine_width_reaction'] = widget._sine_width_reaction
    extra['sine_vertical_shift'] = widget._sine_vertical_shift
    extra['helix_turns'] = widget._helix_turns
    extra['helix_double'] = widget._helix_double
    extra['helix_speed'] = widget._helix_speed
    extra['helix_glow_enabled'] = widget._helix_glow_enabled
    extra['helix_glow_intensity'] = widget._helix_glow_intensity
    extra['helix_glow_color'] = widget._helix_glow_color
    extra['helix_reactive_glow'] = widget._helix_reactive_glow
    extra['line_color'] = widget._sine_line_color if _is_sine else widget._osc_line_color
    extra['osc_line_count'] = widget._sine_line_count if _is_sine else widget._osc_line_count
    extra['osc_line2_color'] = widget._sine_line2_color if _is_sine else widget._osc_line2_color
    extra['osc_line2_glow_color'] = widget._sine_line2_glow_color if _is_sine else widget._osc_line2_glow_color
    extra['osc_line3_color'] = widget._sine_line3_color if _is_sine else widget._osc_line3_color
    extra['osc_line3_glow_color'] = widget._sine_line3_glow_color if _is_sine else widget._osc_line3_glow_color

    # --- Bubble -----------------------------------------------------------
    # Only pass GL-relevant keys to set_state (colours, simulation snapshot).
    # Simulation settings (counts, speeds, directions) stay on the widget for
    # the COMPUTE-thread simulation and must NOT be forwarded to set_state
    # which would reject them as unexpected kwargs.
    if mode_str == 'bubble':
        extra['bubble_outline_color'] = getattr(widget, '_bubble_outline_color', None)
        extra['bubble_specular_color'] = getattr(widget, '_bubble_specular_color', None)
        extra['bubble_gradient_light'] = getattr(widget, '_bubble_gradient_light', None)
        extra['bubble_gradient_dark'] = getattr(widget, '_bubble_gradient_dark', None)
        extra['bubble_pop_color'] = getattr(widget, '_bubble_pop_color', None)
        extra['bubble_specular_direction'] = getattr(widget, '_bubble_specular_direction', 'top_left')
        extra['bubble_pos_data'] = getattr(widget, '_bubble_pos_data', [])
        extra['bubble_extra_data'] = getattr(widget, '_bubble_extra_data', [])
        extra['bubble_trail_data'] = getattr(widget, '_bubble_trail_data', [])
        extra['bubble_trail_strength'] = getattr(widget, '_bubble_trail_strength', 0.0)
        extra['bubble_count'] = getattr(widget, '_bubble_count', 0)

    return extra
