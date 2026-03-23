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


def _normalize_direction(value: Any, default: str = "top_left") -> str:
    val = str(value).lower()
    valid = {
        "top", "bottom", "left", "right",
        "top_left", "top_right", "bottom_left", "bottom_right",
        "center_out",
    }
    return val if val in valid else default


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
    if 'osc_glow_size' in kwargs:
        widget._osc_glow_size = max(0.1, min(3.0, float(kwargs['osc_glow_size'])))
    if 'osc_glow_reactivity' in kwargs:
        widget._osc_glow_reactivity = max(0.0, min(2.0, float(kwargs['osc_glow_reactivity'])))
    if 'osc_glow_color' in kwargs:
        c = _color_or_none(kwargs['osc_glow_color'])
        if c is not None:
            widget._osc_glow_color = c
    if 'osc_reactive_glow' in kwargs:
        widget._osc_reactive_glow = bool(kwargs['osc_reactive_glow'])
    if 'osc_line_amplitude' in kwargs:
        widget._osc_line_amplitude = max(0.5, min(10.0, float(kwargs['osc_line_amplitude'])))
    elif 'osc_sensitivity' in kwargs:
        # Legacy key fallback (pre-Mar 2026 builds)
        widget._osc_line_amplitude = max(0.5, min(10.0, float(kwargs['osc_sensitivity'])))
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
    if 'osc_ghost_line2_enabled' in kwargs:
        widget._osc_ghost_line2_enabled = bool(kwargs['osc_ghost_line2_enabled'])
    if 'osc_ghost_line3_enabled' in kwargs:
        widget._osc_ghost_line3_enabled = bool(kwargs['osc_ghost_line3_enabled'])


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
    if 'blob_glow_reactivity' in kwargs:
        widget._blob_glow_reactivity = max(0.0, min(2.0, float(kwargs['blob_glow_reactivity'])))
    if 'blob_glow_max_size' in kwargs:
        widget._blob_glow_max_size = max(0.1, min(3.0, float(kwargs['blob_glow_max_size'])))
    if 'blob_reactive_glow' in kwargs:
        widget._blob_reactive_glow = bool(kwargs['blob_reactive_glow'])
    if 'blob_reactive_deformation' in kwargs:
        widget._blob_reactive_deformation = max(0.0, min(3.0, float(kwargs['blob_reactive_deformation'])))
    if 'blob_pulse_cap' in kwargs:
        widget._blob_pulse_cap = max(0.0, min(2.0, float(kwargs['blob_pulse_cap'])))
    if 'blob_pulse_release_ms' in kwargs:
        widget._blob_pulse_release_ms = max(60.0, min(800.0, float(kwargs['blob_pulse_release_ms'])))
    if 'blob_stage_gain' in kwargs:
        widget._blob_stage_gain = max(0.0, min(2.0, float(kwargs['blob_stage_gain'])))
    if 'blob_core_scale' in kwargs:
        widget._blob_core_scale = max(0.25, min(2.5, float(kwargs['blob_core_scale'])))
    if 'blob_core_floor_bias' in kwargs:
        widget._blob_core_floor_bias = max(0.0, min(0.6, float(kwargs['blob_core_floor_bias'])))
    if 'blob_stage_bias' in kwargs:
        widget._blob_stage_bias = max(-0.60, min(0.60, float(kwargs['blob_stage_bias'])))
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
    if 'blob_stretch_inner' in kwargs:
        widget._blob_stretch_inner = max(0.0, min(1.0, float(kwargs['blob_stretch_inner'])))
    if 'blob_stretch_outer' in kwargs:
        widget._blob_stretch_outer = max(0.0, min(1.0, float(kwargs['blob_stretch_outer'])))


    # --- Card + bar styling (global across modes) ---------------------
    if 'bar_fill_color' in kwargs:
        c = _color_or_none(kwargs['bar_fill_color'])
        if c is not None:
            widget._bar_fill_color = c
    if 'bar_border_color' in kwargs:
        c = _color_or_none(kwargs['bar_border_color'])
        if c is not None:
            widget._bar_border_color = c
    if 'bar_border_opacity' in kwargs:
        try:
            opacity = max(0.0, min(1.0, float(kwargs['bar_border_opacity'])))
        except Exception:
            opacity = getattr(widget._bar_border_color, 'alphaF', lambda: 1.0)()
        # Preserve RGB, adjust alpha channel
        color = QColor(widget._bar_border_color)
        color.setAlphaF(opacity)
        widget._bar_border_color = color

    # --- Spectrum -----------------------------------------------------
    if 'spectrum_single_piece' in kwargs:
        widget._spectrum_single_piece = bool(kwargs['spectrum_single_piece'])
    if 'spectrum_rainbow_per_bar' in kwargs:
        widget._rainbow_per_bar = bool(kwargs['spectrum_rainbow_per_bar'])

    if 'spectrum_border_radius' in kwargs:
        widget._spectrum_border_radius = max(0.0, min(20.0, float(kwargs['spectrum_border_radius'])))
    if 'spectrum_glow_enabled' in kwargs:
        widget._spectrum_glow_enabled = bool(kwargs['spectrum_glow_enabled'])
    if 'spectrum_glow_intensity' in kwargs:
        widget._spectrum_glow_intensity = max(0.0, min(1.5, float(kwargs['spectrum_glow_intensity'])))
    if 'spectrum_glow_color' in kwargs:
        c = _color_or_none(kwargs['spectrum_glow_color'])
        if c is not None:
            widget._spectrum_glow_color = c
    if 'spectrum_mirrored' in kwargs:
        _new_mirrored = bool(kwargs['spectrum_mirrored'])
        if _new_mirrored != getattr(widget, '_spectrum_mirrored', True):
            widget._spectrum_mirrored = _new_mirrored
            try:
                from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
                engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
                if engine is not None:
                    engine.set_spectrum_mirrored(_new_mirrored)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to propagate spectrum mirrored", exc_info=True)
    if 'spectrum_shape_nodes' in kwargs:
        _nodes = kwargs['spectrum_shape_nodes']
        if isinstance(_nodes, list) and len(_nodes) >= 1:
            widget._spectrum_shape_nodes = _nodes
            try:
                from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
                engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
                if engine is not None:
                    engine.set_spectrum_shape_nodes(_nodes)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to propagate spectrum shape nodes", exc_info=True)

    # --- Spectrum notch positions -------------------------------------
    _notch_dirty = False
    if 'spectrum_notch_positions_mirrored' in kwargs:
        _npos = kwargs['spectrum_notch_positions_mirrored']
        if isinstance(_npos, list) and len(_npos) >= 2:
            widget._spectrum_notch_positions_mirrored = _npos
            _notch_dirty = True
    if 'spectrum_notch_positions_linear' in kwargs:
        _npos = kwargs['spectrum_notch_positions_linear']
        if isinstance(_npos, list) and len(_npos) >= 2:
            widget._spectrum_notch_positions_linear = _npos
            _notch_dirty = True
    if _notch_dirty:
        _active = (widget._spectrum_notch_positions_mirrored
                   if getattr(widget, '_spectrum_mirrored', True)
                   else widget._spectrum_notch_positions_linear)
        try:
            from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
            engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
            if engine is not None:
                engine.set_notch_positions(_active)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to propagate notch positions to engine", exc_info=True)

    # --- Spectrum shaping parameters ----------------------------------
    _shape_dirty = False
    for _shape_key, _shape_attr, _shape_lo, _shape_hi in (
        ('spectrum_bass_emphasis', '_spectrum_bass_emphasis', 0.0, 1.0),
        ('spectrum_vocal_position', '_spectrum_vocal_position', 0.20, 0.60),
        ('spectrum_mid_suppression', '_spectrum_mid_suppression', 0.0, 1.0),
        ('spectrum_wave_amplitude', '_spectrum_wave_amplitude', 0.0, 1.0),
        ('spectrum_profile_floor', '_spectrum_profile_floor', 0.05, 0.30),
    ):
        if _shape_key in kwargs:
            val = max(_shape_lo, min(_shape_hi, float(kwargs[_shape_key])))
            if val != getattr(widget, _shape_attr, None):
                setattr(widget, _shape_attr, val)
                _shape_dirty = True
    if _shape_dirty:
        try:
            from widgets.spotify_visualizer.bar_computation import SpectrumShapeConfig
            from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
            engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
            if engine is not None:
                engine.set_spectrum_shape_config(SpectrumShapeConfig(
                    bass_emphasis=widget._spectrum_bass_emphasis,
                    vocal_peak_position=widget._spectrum_vocal_position,
                    mid_suppression=widget._spectrum_mid_suppression,
                    wave_amplitude=widget._spectrum_wave_amplitude,
                    profile_floor=widget._spectrum_profile_floor,
                ))
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to propagate spectrum shape config", exc_info=True)

    # --- Spectrum drop speed ------------------------------------------
    if 'spectrum_drop_speed' in kwargs:
        widget._spectrum_drop_speed = max(0.5, min(3.0, float(kwargs['spectrum_drop_speed'])))
        try:
            from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
            engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
            if engine is not None:
                engine.set_drop_speed(widget._spectrum_drop_speed)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to propagate drop speed to engine", exc_info=True)

    # --- Height growth factors ----------------------------------------
    if 'spectrum_growth' in kwargs:
        widget._spectrum_growth = max(0.5, min(5.0, float(kwargs['spectrum_growth'])))
    if 'blob_growth' in kwargs:
        widget._blob_growth = max(0.5, min(5.0, float(kwargs['blob_growth'])))
    if 'osc_growth' in kwargs:
        widget._osc_growth = max(0.5, min(5.0, float(kwargs['osc_growth'])))
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
    if 'sine_crawl_amount' in kwargs:
        widget._sine_crawl_amount = max(0.0, min(1.0, float(kwargs['sine_crawl_amount'])))
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
    if 'sine_glow_size' in kwargs:
        widget._sine_glow_size = max(0.1, min(3.0, float(kwargs['sine_glow_size'])))
    if 'sine_glow_reactivity' in kwargs:
        widget._sine_glow_reactivity = max(0.0, min(2.0, float(kwargs['sine_glow_reactivity'])))
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
    if 'sine_ghost_line2_enabled' in kwargs:
        widget._sine_ghost_line2_enabled = bool(kwargs['sine_ghost_line2_enabled'])
    if 'sine_ghost_line3_enabled' in kwargs:
        widget._sine_ghost_line3_enabled = bool(kwargs['sine_ghost_line3_enabled'])

    # --- Rainbow (per-mode, falls back to global key for compat) --------
    # Per-mode keys like spectrum_rainbow_enabled take priority over the
    # legacy global rainbow_enabled.  The UI writes both.
    _mode_str = getattr(widget, '_vis_mode_str', None) or ''
    _pm_re = f'{_mode_str}_rainbow_enabled' if _mode_str else ''
    _pm_rs = f'{_mode_str}_rainbow_speed' if _mode_str else ''
    if _pm_re and _pm_re in kwargs:
        widget._rainbow_enabled = bool(kwargs[_pm_re])
    elif 'rainbow_enabled' in kwargs:
        widget._rainbow_enabled = bool(kwargs['rainbow_enabled'])
    if _pm_rs and _pm_rs in kwargs:
        widget._rainbow_speed = max(0.01, min(5.0, float(kwargs[_pm_rs])))
    elif 'rainbow_speed' in kwargs:
        widget._rainbow_speed = max(0.01, min(5.0, float(kwargs['rainbow_speed'])))
    if 'rainbow_per_bar' in kwargs:
        widget._rainbow_per_bar = bool(kwargs['rainbow_per_bar'])

    # --- Oscilloscope ghost trail ----------------------------------------
    if 'osc_ghosting_enabled' in kwargs:
        widget._osc_ghosting_enabled = bool(kwargs['osc_ghosting_enabled'])
    if 'osc_ghost_intensity' in kwargs:
        widget._osc_ghost_intensity = max(0.0, min(1.0, float(kwargs['osc_ghost_intensity'])))

    # --- Spectrum ghost ----------------------------------------------------
    if 'spectrum_ghosting_enabled' in kwargs:
        widget._spectrum_ghosting_enabled = bool(kwargs['spectrum_ghosting_enabled'])
    if 'spectrum_ghost_alpha' in kwargs:
        widget._spectrum_ghost_alpha = max(0.0, min(1.0, float(kwargs['spectrum_ghost_alpha'])))
    if 'spectrum_ghost_decay' in kwargs:
        widget._spectrum_ghost_decay = max(0.1, min(1.0, float(kwargs['spectrum_ghost_decay'])))

    # --- Blob ghost -------------------------------------------------------
    if 'blob_ghosting_enabled' in kwargs:
        widget._blob_ghosting_enabled = bool(kwargs['blob_ghosting_enabled'])
    if 'blob_ghost_alpha' in kwargs:
        widget._blob_ghost_alpha = max(0.0, min(1.0, float(kwargs['blob_ghost_alpha'])))
    if 'blob_ghost_decay' in kwargs:
        widget._blob_ghost_decay = max(0.1, min(1.0, float(kwargs['blob_ghost_decay'])))

    # --- Sine ghost -------------------------------------------------------
    if 'sine_ghosting_enabled' in kwargs:
        widget._sine_ghosting_enabled = bool(kwargs['sine_ghosting_enabled'])
    if 'sine_ghost_alpha' in kwargs:
        widget._sine_ghost_alpha = max(0.0, min(1.0, float(kwargs['sine_ghost_alpha'])))
    if 'sine_ghost_decay' in kwargs:
        widget._sine_ghost_decay = max(0.1, min(1.0, float(kwargs['sine_ghost_decay'])))

    # --- Bubble ghost -----------------------------------------------------
    if 'bubble_ghosting_enabled' in kwargs:
        widget._bubble_ghosting_enabled = bool(kwargs['bubble_ghosting_enabled'])
    if 'bubble_ghost_alpha' in kwargs:
        widget._bubble_ghost_alpha = max(0.0, min(1.0, float(kwargs['bubble_ghost_alpha'])))
    if 'bubble_ghost_decay' in kwargs:
        widget._bubble_ghost_decay = max(0.1, min(1.0, float(kwargs['bubble_ghost_decay'])))

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
        widget._bubble_stream_reactivity = max(0.0, min(1.25, float(kwargs['bubble_stream_reactivity'])))
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
        valid_dirs = (
            'none', 'left', 'right', 'diagonal',
            'swish_horizontal', 'swish_vertical',
            'swirl_cw', 'swirl_ccw', 'random'
        )
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
        widget._bubble_specular_direction = _normalize_direction(kwargs['bubble_specular_direction'], default='top_left')
    if 'bubble_gradient_direction' in kwargs:
        widget._bubble_gradient_direction = _normalize_direction(kwargs['bubble_gradient_direction'], default='top')
    if 'bubble_big_size_max' in kwargs:
        widget._bubble_big_size_max = max(0.010, min(0.060, float(kwargs['bubble_big_size_max'])))
    if 'bubble_small_size_max' in kwargs:
        widget._bubble_small_size_max = max(0.004, min(0.030, float(kwargs['bubble_small_size_max'])))
    if 'bubble_big_contraction_bias' in kwargs:
        widget._bubble_big_contraction_bias = max(0.0, min(2.0, float(kwargs['bubble_big_contraction_bias'])))
    if 'bubble_big_size_clamp' in kwargs:
        widget._bubble_big_size_clamp = max(1.5, min(8.0, float(kwargs['bubble_big_size_clamp'])))
    if 'bubble_big_specular_max_size' in kwargs:
        widget._bubble_big_specular_max_size = max(0.5, min(5.0, float(kwargs['bubble_big_specular_max_size'])))
    if 'bubble_growth' in kwargs:
        widget._bubble_growth = max(1.0, min(5.0, float(kwargs['bubble_growth'])))
    if 'bubble_trail_strength' in kwargs:
        widget._bubble_trail_strength = max(0.0, min(1.5, float(kwargs['bubble_trail_strength'])))
    if 'bubble_tail_opacity' in kwargs:
        widget._bubble_tail_opacity = max(0.0, min(0.85, float(kwargs['bubble_tail_opacity'])))


def _build_shared_visualizer_extras(widget: Any) -> Dict[str, Any]:
    """Return cross-mode visual extras that all GPU paths understand."""
    return {
        'rainbow_enabled': getattr(widget, '_rainbow_enabled', False),
        'rainbow_speed': getattr(widget, '_rainbow_speed', 0.5),
        'rainbow_per_bar': getattr(widget, '_rainbow_per_bar', False),
        'spectrum_glow_enabled': getattr(widget, '_spectrum_glow_enabled', False),
        'spectrum_glow_intensity': getattr(widget, '_spectrum_glow_intensity', 0.55),
        'spectrum_glow_color': getattr(widget, '_spectrum_glow_color', None),
        'spectrum_ghosting_enabled': getattr(widget, '_spectrum_ghosting_enabled', True),
        'spectrum_ghost_alpha': getattr(widget, '_spectrum_ghost_alpha', 0.4),
        'spectrum_ghost_decay': getattr(widget, '_spectrum_ghost_decay', 0.4),
        'osc_ghosting_enabled': getattr(widget, '_osc_ghosting_enabled', False),
        'osc_ghost_intensity': getattr(widget, '_osc_ghost_intensity', 0.4),
        'osc_ghost_line2_enabled': getattr(widget, '_osc_ghost_line2_enabled', True),
        'osc_ghost_line3_enabled': getattr(widget, '_osc_ghost_line3_enabled', True),
        'blob_ghosting_enabled': getattr(widget, '_blob_ghosting_enabled', False),
        'blob_ghost_alpha': getattr(widget, '_blob_ghost_alpha', 0.4),
        'blob_ghost_decay': getattr(widget, '_blob_ghost_decay', 0.3),
        'sine_ghosting_enabled': getattr(widget, '_sine_ghosting_enabled', True),
        'sine_ghost_alpha': getattr(widget, '_sine_ghost_alpha', 0.45),
        'sine_ghost_decay': getattr(widget, '_sine_ghost_decay', 0.3),
        'sine_ghost_line2_enabled': getattr(widget, '_sine_ghost_line2_enabled', True),
        'sine_ghost_line3_enabled': getattr(widget, '_sine_ghost_line3_enabled', True),
        'bubble_ghosting_enabled': getattr(widget, '_bubble_ghosting_enabled', False),
        'bubble_ghost_alpha': getattr(widget, '_bubble_ghost_alpha', 0.0),
        'bubble_ghost_decay': getattr(widget, '_bubble_ghost_decay', 0.4),
        'sine_heartbeat': getattr(widget, '_sine_heartbeat', 0.0),
        'heartbeat_intensity': getattr(widget, '_heartbeat_intensity', 0.0),
        'sine_density': getattr(widget, '_sine_density', 1.0),
        'sine_displacement': getattr(widget, '_sine_displacement', 0.0),
    }


def _populate_engine_signal_snapshot(extra: Dict[str, Any], widget: Any, mode_str: str, engine: Any) -> None:
    """Attach waveform, continuous energy, transient bus, and scheduler peeks."""
    if engine is None:
        return

    extra['waveform'] = engine.get_waveform()
    try:
        extra['waveform_count'] = engine.get_waveform_count()
    except Exception:
        extra['waveform_count'] = len(extra['waveform'])

    use_raw = getattr(widget, '_use_raw_energy', False)
    if use_raw:
        extra['energy_bands'] = engine.get_pre_agc_energy_bands()
    else:
        extra['energy_bands'] = engine.get_energy_bands()
    extra['transient_energy'] = engine.get_transient_energy_bands()

    try:
        scheduler = engine.get_event_scheduler()
    except Exception:
        scheduler = None
    if scheduler is None:
        return

    if mode_str == 'blob':
        kick_evt = scheduler.peek_latest('kick', max_age_s=0.18)
        snare_evt = scheduler.peek_latest('snare', max_age_s=0.22)
        extra['blob_kick_event_strength'] = (
            float(getattr(kick_evt, 'strength', 0.0)) if kick_evt is not None else 0.0
        )
        extra['blob_snare_event_strength'] = (
            float(getattr(snare_evt, 'strength', 0.0)) if snare_evt is not None else 0.0
        )
    elif mode_str in {'sine_wave', 'oscilloscope'}:
        kick_evt = scheduler.peek_latest('kick', max_age_s=0.16)
        snare_evt = scheduler.peek_latest('snare', max_age_s=0.20)
        extra['line_kick_event_strength'] = (
            float(getattr(kick_evt, 'strength', 0.0)) if kick_evt is not None else 0.0
        )
        extra['line_snare_event_strength'] = (
            float(getattr(snare_evt, 'strength', 0.0)) if snare_evt is not None else 0.0
        )


def _append_line_mode_visual_extras(extra: Dict[str, Any], widget: Any, *, is_sine: bool) -> None:
    """Attach the shared Sine/Osc visual parameters."""
    extra['glow_enabled'] = widget._sine_glow_enabled if is_sine else widget._osc_glow_enabled
    extra['glow_intensity'] = widget._sine_glow_intensity if is_sine else widget._osc_glow_intensity
    extra['glow_size'] = widget._sine_glow_size if is_sine else widget._osc_glow_size
    extra['glow_reactivity'] = (
        getattr(widget, '_sine_glow_reactivity', 1.0)
        if is_sine
        else getattr(widget, '_osc_glow_reactivity', 1.0)
    )
    extra['glow_color'] = widget._sine_glow_color if is_sine else widget._osc_glow_color
    extra['reactive_glow'] = widget._sine_reactive_glow if is_sine else widget._osc_reactive_glow
    extra['osc_line_amplitude'] = widget._sine_sensitivity if is_sine else widget._osc_line_amplitude
    extra['osc_smoothing'] = widget._osc_smoothing
    extra['osc_speed'] = widget._sine_speed if is_sine else widget._osc_speed
    extra['osc_line_dim'] = widget._sine_line_dim if is_sine else widget._osc_line_dim
    extra['osc_line_offset_bias'] = widget._sine_line_offset_bias if is_sine else widget._osc_line_offset_bias
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
    extra['sine_crawl_amount'] = getattr(widget, '_sine_crawl_amount', 0.0)
    extra['sine_width_reaction'] = widget._sine_width_reaction
    extra['sine_vertical_shift'] = widget._sine_vertical_shift
    extra['line_color'] = widget._sine_line_color if is_sine else widget._osc_line_color
    extra['osc_line_count'] = widget._sine_line_count if is_sine else widget._osc_line_count
    extra['osc_line2_color'] = widget._sine_line2_color if is_sine else widget._osc_line2_color
    extra['osc_line2_glow_color'] = widget._sine_line2_glow_color if is_sine else widget._osc_line2_glow_color
    extra['osc_line3_color'] = widget._sine_line3_color if is_sine else widget._osc_line3_color
    extra['osc_line3_glow_color'] = widget._sine_line3_glow_color if is_sine else widget._osc_line3_glow_color
    extra['osc_ghost_line2_enabled'] = bool(getattr(widget, '_osc_ghost_line2_enabled', True))
    extra['osc_ghost_line3_enabled'] = bool(getattr(widget, '_osc_ghost_line3_enabled', True))
    extra['sine_ghost_line2_enabled'] = bool(getattr(widget, '_sine_ghost_line2_enabled', True))
    extra['sine_ghost_line3_enabled'] = bool(getattr(widget, '_sine_ghost_line3_enabled', True))


def _append_blob_visual_extras(extra: Dict[str, Any], widget: Any) -> None:
    """Attach Blob-only live-core and retained-ghost parameters."""
    extra['blob_color'] = widget._blob_color
    extra['blob_glow_color'] = widget._blob_glow_color
    extra['blob_edge_color'] = widget._blob_edge_color
    extra['blob_outline_color'] = widget._blob_outline_color
    extra['blob_pulse'] = widget._blob_pulse
    extra['blob_width'] = widget._blob_width
    extra['blob_size'] = widget._blob_size
    extra['blob_glow_intensity'] = widget._blob_glow_intensity
    extra['blob_glow_reactivity'] = getattr(widget, '_blob_glow_reactivity', 1.0)
    extra['blob_glow_max_size'] = getattr(widget, '_blob_glow_max_size', 1.0)
    extra['blob_reactive_glow'] = widget._blob_reactive_glow
    extra['blob_reactive_deformation'] = widget._blob_reactive_deformation
    extra['blob_pulse_cap'] = getattr(widget, '_blob_pulse_cap', 1.0)
    extra['blob_pulse_release_ms'] = getattr(widget, '_blob_pulse_release_ms', 220.0)
    extra['blob_stage_gain'] = widget._blob_stage_gain
    extra['blob_core_scale'] = widget._blob_core_scale
    extra['blob_core_floor_bias'] = widget._blob_core_floor_bias
    extra['blob_stage_bias'] = getattr(widget, '_blob_stage_bias', 0.0)
    extra['blob_stage2_release_ms'] = getattr(widget, '_blob_stage2_release_ms', 900.0)
    extra['blob_stage3_release_ms'] = getattr(widget, '_blob_stage3_release_ms', 1200.0)
    extra['blob_constant_wobble'] = widget._blob_constant_wobble
    extra['blob_reactive_wobble'] = widget._blob_reactive_wobble
    extra['blob_stretch_tendency'] = widget._blob_stretch_tendency
    extra['blob_stretch_inner'] = getattr(widget, '_blob_stretch_inner', 0.5)
    extra['blob_stretch_outer'] = getattr(widget, '_blob_stretch_outer', 0.5)


def _append_bubble_visual_extras(extra: Dict[str, Any], widget: Any) -> None:
    """Attach only GL-safe Bubble extras; sim controls stay on the widget."""
    extra['bubble_outline_color'] = getattr(widget, '_bubble_outline_color', None)
    extra['bubble_specular_color'] = getattr(widget, '_bubble_specular_color', None)
    extra['bubble_gradient_light'] = getattr(widget, '_bubble_gradient_light', None)
    extra['bubble_gradient_dark'] = getattr(widget, '_bubble_gradient_dark', None)
    extra['bubble_pop_color'] = getattr(widget, '_bubble_pop_color', None)
    extra['bubble_specular_direction'] = getattr(widget, '_bubble_specular_direction', 'top_left')
    extra['bubble_gradient_direction'] = getattr(widget, '_bubble_gradient_direction', 'top')
    extra['bubble_pos_data'] = getattr(widget, '_bubble_pos_data', [])
    extra['bubble_extra_data'] = getattr(widget, '_bubble_extra_data', [])
    extra['bubble_trail_data'] = getattr(widget, '_bubble_trail_data', [])
    extra['bubble_trail_strength'] = getattr(widget, '_bubble_trail_strength', 0.0)
    extra['bubble_tail_opacity'] = getattr(widget, '_bubble_tail_opacity', 0.0)
    extra['bubble_count'] = getattr(widget, '_bubble_count', 0)


def build_gpu_push_extra_kwargs(widget: Any, mode_str: str, engine: Any) -> Dict[str, Any]:
    """Build the mode-local GPU extras payload for the compositor overlay."""
    extra = _build_shared_visualizer_extras(widget)
    if mode_str == 'spectrum':
        return extra

    _populate_engine_signal_snapshot(extra, widget, mode_str, engine)
    _append_line_mode_visual_extras(extra, widget, is_sine=(mode_str == 'sine_wave'))
    _append_blob_visual_extras(extra, widget)
    if mode_str == 'bubble':
        _append_bubble_visual_extras(extra, widget)
    return extra
