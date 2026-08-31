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
from core.settings.bubble_gradient_semantics import (
    normalize_bubble_gradient_direction,
    normalize_bubble_specular_direction,
)
from core.settings.visualizer_settings_contract import normalize_spectrum_render_mode

logger = get_logger(__name__)

_SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED = {
    "Mid": 0.60,
    "Vocal": 0.64,
    "Low-Mid": 0.70,
    "Bass": 0.80,
}
_SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR = {
    "Bass": 0.80,
    "Low-Mid": 0.70,
    "Vocal": 0.64,
    "Hi-Mid": 0.80,
    "Treble": 1.00,
}


def _color_or_none(value: Any) -> QColor | None:
    """Return a QColor if *value* is a list/tuple of ≥3 ints, else None."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return QColor(*value)
    return None


def _presentation_source(host: Any) -> Any:
    """Where pure renderer/presentation-only config is read from.

    Authored logical inputs are read from ``host`` directly; renderer styling is
    owned by the controller-owned ``VisualizerPresentationState``. The widget-free
    logical state exposes ``presentation_config_host`` pointing there; the legacy
    widget delegates its presentation fields to the same state, so either host
    resolves to one presentation storage. A bare host (e.g. a test double whose
    ``__getattr__`` fabricates values) reads its own attributes.
    """

    from widgets.spotify_visualizer.presentation_state import (
        VisualizerPresentationState,
    )

    pres = getattr(host, "presentation_config_host", None)
    return pres if isinstance(pres, VisualizerPresentationState) else host


def _normalize_direction(value: Any, default: str = "top_left") -> str:
    val = str(value).lower()
    valid = {
        "top", "bottom", "left", "right",
        "top_left", "top_right", "bottom_left", "bottom_right",
        "center_out", "center_out_reverse",
    }
    return val if val in valid else default


def _normalize_lane_strengths(value: Any, defaults: Dict[str, float]) -> Dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    normalized: Dict[str, float] = {}
    for label, default in defaults.items():
        try:
            lane_value = float(value.get(label, default))
        except Exception:
            lane_value = float(default)
        normalized[label] = max(0.0, min(1.0, lane_value))
    return normalized


def apply_logical_vis_mode_kwargs(host: Any, kwargs: Dict[str, Any]) -> None:
    """Apply ONLY the authored logical config to a presentation-neutral host
    (``VisualizerLogicalTickState`` or the legacy widget that delegates to it).

    This is the single authority for the logical portion of the per-mode
    settings apply. "Logical" here is classified by the actual consumer, not by
    naming: a value is applied here iff authored logical evolution or a
    mode-owned logical frame runtime reads it (Bubble physics, plus the
    Spectrum/Oscilloscope/Sine inputs consumed by each mode's
    ``*FrameRuntime.resolve`` and the DevCurve inputs consumed by the DevCurve
    logical field solve). Pure renderer/chrome/style values (bar/line/glow
    colours, glow sizing, card radius, rainbow styling) stay presentation-owned
    in ``apply_vis_mode_kwargs``.
    """

    if 'sine_heartbeat' in kwargs:
        host._sine_heartbeat = max(0.0, min(1.0, float(kwargs['sine_heartbeat'])))
    if 'bubble_big_bass_pulse' in kwargs:
        host._bubble_big_bass_pulse = max(0.0, min(1.0, float(kwargs['bubble_big_bass_pulse'])))
    if 'bubble_small_freq_pulse' in kwargs:
        host._bubble_small_freq_pulse = max(0.0, min(1.0, float(kwargs['bubble_small_freq_pulse'])))
    if 'bubble_stream_direction' in kwargs:
        val = str(kwargs['bubble_stream_direction']).lower()
        if val == 'diagonal':
            val = 'top_right'
        if val not in (
            'none',
            'up',
            'down',
            'left',
            'right',
            'top_left',
            'top_right',
            'bottom_left',
            'bottom_right',
            'random',
        ):
            val = 'up'
        host._bubble_stream_direction = val
    if 'bubble_stream_constant_speed' in kwargs:
        host._bubble_stream_constant_speed = max(
            0.0, min(2.0, float(kwargs['bubble_stream_constant_speed']))
        )
    if 'bubble_stream_speed_cap' in kwargs:
        host._bubble_stream_speed_cap = max(
            0.1, min(4.0, float(kwargs['bubble_stream_speed_cap']))
        )
    if 'bubble_stream_reactivity' in kwargs:
        host._bubble_stream_reactivity = max(0.0, min(1.25, float(kwargs['bubble_stream_reactivity'])))
    if 'bubble_rotation_amount' in kwargs:
        host._bubble_rotation_amount = max(0.0, min(1.0, float(kwargs['bubble_rotation_amount'])))
    if 'bubble_drift_amount' in kwargs:
        host._bubble_drift_amount = max(0.0, min(1.0, float(kwargs['bubble_drift_amount'])))
    if 'bubble_group_drift' in kwargs:
        host._bubble_group_drift = bool(kwargs['bubble_group_drift'])
    if 'bubble_drift_speed' in kwargs:
        host._bubble_drift_speed = max(0.0, min(1.0, float(kwargs['bubble_drift_speed'])))
    if 'bubble_drift_frequency' in kwargs:
        host._bubble_drift_frequency = max(0.0, min(1.0, float(kwargs['bubble_drift_frequency'])))
    if 'bubble_drift_direction' in kwargs:
        val = str(kwargs['bubble_drift_direction']).lower()
        valid_dirs = (
            'none', 'left', 'right', 'diagonal',
            'swish_horizontal', 'swish_vertical',
            'swirl_cw', 'swirl_ccw', 'random'
        )
        if val not in valid_dirs:
            val = 'random'
        host._bubble_drift_direction = val
    if 'bubble_big_count' in kwargs:
        host._bubble_big_count = max(1, min(30, int(kwargs['bubble_big_count'])))
    if 'bubble_small_count' in kwargs:
        host._bubble_small_count = max(5, min(80, int(kwargs['bubble_small_count'])))
    if 'bubble_surface_reach' in kwargs:
        host._bubble_surface_reach = max(0.0, min(1.0, float(kwargs['bubble_surface_reach'])))
    if 'bubble_bounce_big_pct' in kwargs:
        host._bubble_bounce_big_pct = max(0, min(100, int(kwargs['bubble_bounce_big_pct'])))
    if 'bubble_bounce_small_pct' in kwargs:
        host._bubble_bounce_small_pct = max(0, min(100, int(kwargs['bubble_bounce_small_pct'])))
    if 'bubble_bounce_big_speed' in kwargs:
        host._bubble_bounce_big_speed = max(0.0, min(2.0, float(kwargs['bubble_bounce_big_speed'])))
    if 'bubble_bounce_small_speed' in kwargs:
        host._bubble_bounce_small_speed = max(0.0, min(2.0, float(kwargs['bubble_bounce_small_speed'])))
    if 'bubble_bounce_same_only' in kwargs:
        host._bubble_bounce_same_only = bool(kwargs['bubble_bounce_same_only'])
    if 'bubble_collision_pop_mode' in kwargs:
        mode = str(kwargs['bubble_collision_pop_mode']).strip().lower()
        if mode not in {"off", "one", "all"}:
            mode = "off"
        host._bubble_collision_pop_mode = mode
    if 'bubble_big_size_max' in kwargs:
        host._bubble_big_size_max = max(0.010, min(0.060, float(kwargs['bubble_big_size_max'])))
    if 'bubble_small_size_max' in kwargs:
        host._bubble_small_size_max = max(0.004, min(0.030, float(kwargs['bubble_small_size_max'])))
    if 'bubble_big_visual_smoothing' in kwargs:
        host._bubble_big_visual_smoothing = max(
            0.0, min(1.0, float(kwargs['bubble_big_visual_smoothing']))
        )
    if 'bubble_big_contraction_bias' in kwargs:
        host._bubble_big_contraction_bias = max(0.0, min(2.0, float(kwargs['bubble_big_contraction_bias'])))
    if 'bubble_big_size_clamp' in kwargs:
        host._bubble_big_size_clamp = max(1.5, min(8.0, float(kwargs['bubble_big_size_clamp'])))
    if 'bubble_big_specular_max_size' in kwargs:
        host._bubble_big_specular_max_size = max(0.5, min(5.0, float(kwargs['bubble_big_specular_max_size'])))
    if 'bubble_trail_strength' in kwargs:
        host._bubble_trail_strength = max(0.0, min(1.5, float(kwargs['bubble_trail_strength'])))

    # --- Spectrum authored logical inputs (SpectrumFrameRuntime.resolve) ---
    # Canonical presets/settings store ``spectrum_render_mode``.  The historical
    # creator translated that value to the boolean consumed by authored state;
    # Quick has no creator façade, so the logical owner performs that tiny
    # semantic translation directly.  Retain the legacy boolean only as a
    # fallback for old focused callers.
    if 'spectrum_render_mode' in kwargs:
        host._spectrum_single_piece = (
            normalize_spectrum_render_mode(kwargs['spectrum_render_mode'], 'bars')
            == 'bars'
        )
    elif 'spectrum_single_piece' in kwargs:
        host._spectrum_single_piece = bool(kwargs['spectrum_single_piece'])
    if 'spectrum_visual_smoothing_enabled' in kwargs:
        host._spectrum_visual_smoothing_enabled = bool(
            kwargs['spectrum_visual_smoothing_enabled']
        )
    if 'spectrum_visual_smoothing' in kwargs:
        host._spectrum_visual_smoothing = max(
            0.0, min(1.0, float(kwargs['spectrum_visual_smoothing']))
        )
    if 'spectrum_ghosting_enabled' in kwargs:
        host._spectrum_ghosting_enabled = bool(kwargs['spectrum_ghosting_enabled'])
    if 'spectrum_ghost_decay' in kwargs:
        host._spectrum_ghost_decay = max(0.1, min(1.0, float(kwargs['spectrum_ghost_decay'])))

    # --- Oscilloscope authored logical inputs (OscilloscopeFrameRuntime.resolve)
    if 'osc_speed' in kwargs:
        host._osc_speed = max(0.1, min(1.0, float(kwargs['osc_speed'])))
    if 'osc_line_amplitude' in kwargs:
        host._osc_line_amplitude = max(0.5, min(10.0, float(kwargs['osc_line_amplitude'])))
    if 'osc_ghosting_enabled' in kwargs:
        host._osc_ghosting_enabled = bool(kwargs['osc_ghosting_enabled'])
    if 'osc_ghost_intensity' in kwargs:
        host._osc_ghost_intensity = max(0.0, min(1.0, float(kwargs['osc_ghost_intensity'])))
    if 'osc_ghost_decay' in kwargs:
        host._osc_ghost_decay = max(0.1, min(1.0, float(kwargs['osc_ghost_decay'])))

    # --- Sine authored logical inputs (SineFrameRuntime.resolve) -----------
    if 'sine_speed' in kwargs:
        host._sine_speed = max(0.1, min(1.0, float(kwargs['sine_speed'])))
    if 'sine_line_count' in kwargs:
        host._sine_line_count = max(1, min(6, int(kwargs['sine_line_count'])))
    if 'sine_wave_travel' in kwargs:
        host._sine_wave_travel = max(0, min(2, int(kwargs['sine_wave_travel'])))
    if 'sine_travel_line2' in kwargs:
        host._sine_travel_line2 = max(0, min(2, int(kwargs['sine_travel_line2'])))
    if 'sine_travel_line3' in kwargs:
        host._sine_travel_line3 = max(0, min(2, int(kwargs['sine_travel_line3'])))
    if 'sine_travel_line4' in kwargs:
        host._sine_travel_line4 = max(0, min(2, int(kwargs['sine_travel_line4'])))
    if 'sine_travel_line5' in kwargs:
        host._sine_travel_line5 = max(0, min(2, int(kwargs['sine_travel_line5'])))
    if 'sine_travel_line6' in kwargs:
        host._sine_travel_line6 = max(0, min(2, int(kwargs['sine_travel_line6'])))
    if 'sine_line1_shift' in kwargs:
        host._sine_line1_shift = max(-1.0, min(1.0, float(kwargs['sine_line1_shift'])))
    if 'sine_line2_shift' in kwargs:
        host._sine_line2_shift = max(-1.0, min(1.0, float(kwargs['sine_line2_shift'])))
    if 'sine_line3_shift' in kwargs:
        host._sine_line3_shift = max(-1.0, min(1.0, float(kwargs['sine_line3_shift'])))
    if 'sine_line4_shift' in kwargs:
        host._sine_line4_shift = max(-1.0, min(1.0, float(kwargs['sine_line4_shift'])))
    if 'sine_line5_shift' in kwargs:
        host._sine_line5_shift = max(-1.0, min(1.0, float(kwargs['sine_line5_shift'])))
    if 'sine_line6_shift' in kwargs:
        host._sine_line6_shift = max(-1.0, min(1.0, float(kwargs['sine_line6_shift'])))
    if 'sine_width_reaction' in kwargs:
        host._sine_width_reaction = max(0.0, min(1.0, float(kwargs['sine_width_reaction'])))
    if 'sine_sensitivity' in kwargs:
        host._sine_sensitivity = max(0.1, min(5.0, float(kwargs['sine_sensitivity'])))
    if 'sine_ghosting_enabled' in kwargs:
        host._sine_ghosting_enabled = bool(kwargs['sine_ghosting_enabled'])
    if 'sine_ghost_alpha' in kwargs:
        host._sine_ghost_alpha = max(0.0, min(1.0, float(kwargs['sine_ghost_alpha'])))
    if 'sine_ghost_decay' in kwargs:
        host._sine_ghost_decay = max(0.1, min(1.0, float(kwargs['sine_ghost_decay'])))

    # --- DevCurve authored logical inputs (_devcurve_parameter_snapshot) ---
    # The DevCurve field solve runs on the authored logical clock and consumes
    # its full parameter snapshot (including per-layer colour/outline), so these
    # are logical-owned even though some read as styling.
    if 'devcurve_base_level' in kwargs:
        host._devcurve_base_level = max(0.10, min(0.90, float(kwargs['devcurve_base_level'])))
    if 'devcurve_motion_power' in kwargs:
        host._devcurve_motion_power = max(0.0, min(3.0, float(kwargs['devcurve_motion_power'])))
    if 'devcurve_idle_motion' in kwargs:
        host._devcurve_idle_motion = max(0.0, min(1.5, float(kwargs['devcurve_idle_motion'])))
    if 'devcurve_idle_speed' in kwargs:
        host._devcurve_idle_speed = max(0.05, min(2.0, float(kwargs['devcurve_idle_speed'])))
    if 'devcurve_smoothness' in kwargs:
        host._devcurve_smoothness = max(0.0, min(1.0, float(kwargs['devcurve_smoothness'])))
    if 'devcurve_ghosting_enabled' in kwargs:
        host._devcurve_ghosting_enabled = bool(kwargs['devcurve_ghosting_enabled'])
    if 'devcurve_ghost_alpha' in kwargs:
        host._devcurve_ghost_alpha = max(0.0, min(1.0, float(kwargs['devcurve_ghost_alpha'])))
    if 'devcurve_ghost_decay' in kwargs:
        host._devcurve_ghost_decay = max(0.1, min(1.0, float(kwargs['devcurve_ghost_decay'])))
    if 'devcurve_foreground_shadow_enabled' in kwargs:
        host._devcurve_foreground_shadow_enabled = bool(kwargs['devcurve_foreground_shadow_enabled'])
    if 'devcurve_foreground_shadow_alpha' in kwargs:
        host._devcurve_foreground_shadow_alpha = max(0.0, min(1.0, float(kwargs['devcurve_foreground_shadow_alpha'])))
    if 'devcurve_foreground_shadow_darken' in kwargs:
        host._devcurve_foreground_shadow_darken = max(0.0, min(1.0, float(kwargs['devcurve_foreground_shadow_darken'])))
    if 'devcurve_foreground_shadow_offset' in kwargs:
        host._devcurve_foreground_shadow_offset = max(0.0, min(0.45, float(kwargs['devcurve_foreground_shadow_offset'])))
    if 'devcurve_foreground_specular_enabled' in kwargs:
        host._devcurve_foreground_specular_enabled = bool(kwargs['devcurve_foreground_specular_enabled'])
    if 'devcurve_foreground_specular_alpha' in kwargs:
        host._devcurve_foreground_specular_alpha = max(0.0, min(1.0, float(kwargs['devcurve_foreground_specular_alpha'])))
    if 'devcurve_foreground_specular_width' in kwargs:
        host._devcurve_foreground_specular_width = max(0.002, min(0.120, float(kwargs['devcurve_foreground_specular_width'])))
    if 'devcurve_foreground_specular_offset' in kwargs:
        host._devcurve_foreground_specular_offset = max(-0.20, min(0.20, float(kwargs['devcurve_foreground_specular_offset'])))
    if 'devcurve_foreground_specular_crest_bias' in kwargs:
        host._devcurve_foreground_specular_crest_bias = max(0.0, min(2.0, float(kwargs['devcurve_foreground_specular_crest_bias'])))
    if 'devcurve_active_layer' in kwargs:
        active = str(kwargs['devcurve_active_layer']).strip().lower()
        host._devcurve_active_layer = active if active in {'bass', 'vocals', 'mids', 'transients'} else 'bass'
    for src in ('bass', 'vocals', 'mids', 'transients'):
        en_key = f'devcurve_layer_{src}_enabled'
        color_key = f'devcurve_layer_{src}_color'
        alpha_key = f'devcurve_layer_{src}_alpha'
        power_key = f'devcurve_layer_{src}_power'
        offset_key = f'devcurve_layer_{src}_offset'
        order_key = f'devcurve_layer_{src}_order'
        outline_color_key = f'devcurve_layer_{src}_outline_color'
        outline_width_key = f'devcurve_layer_{src}_outline_width'
        shape_key = f'devcurve_layer_{src}_shape_nodes'
        if en_key in kwargs:
            setattr(host, f'_devcurve_layer_{src}_enabled', bool(kwargs[en_key]))
        if color_key in kwargs:
            c = _color_or_none(kwargs[color_key])
            if c is not None:
                setattr(host, f'_devcurve_layer_{src}_color', c)
        if outline_color_key in kwargs:
            oc = _color_or_none(kwargs[outline_color_key])
            if oc is not None:
                oc.setAlpha(255)
                setattr(host, f'_devcurve_layer_{src}_outline_color', oc)
        if alpha_key in kwargs:
            setattr(host, f'_devcurve_layer_{src}_alpha', max(0.0, min(1.0, float(kwargs[alpha_key]))))
        if power_key in kwargs:
            setattr(host, f'_devcurve_layer_{src}_power', max(0.0, min(3.0, float(kwargs[power_key]))))
        if offset_key in kwargs:
            setattr(host, f'_devcurve_layer_{src}_offset', max(-0.45, min(0.45, float(kwargs[offset_key]))))
        if outline_width_key in kwargs:
            setattr(host, f'_devcurve_layer_{src}_outline_width', max(0.001, min(0.020, float(kwargs[outline_width_key]))))
        if order_key in kwargs:
            setattr(host, f'_devcurve_layer_{src}_order', max(1, min(4, int(kwargs[order_key]))))
        if shape_key in kwargs and isinstance(kwargs[shape_key], list):
            setattr(host, f'_devcurve_layer_{src}_shape_nodes', list(kwargs[shape_key]))


def apply_presentation_vis_mode_kwargs(host: Any, kwargs: Dict[str, Any]) -> None:
    """Apply the pure renderer/presentation-only per-mode config to *host*.

    This is the single authority for the presentation (styling) portion of the
    per-mode settings apply: bar/line/glow colours, glow sizing/reactivity,
    per-line styling, ghost-line toggles, rainbow styling and Bubble renderer
    colours - exactly the fields the legacy adapter reads when composing the
    immutable renderer parameters. Authored logical inputs flow through
    ``apply_logical_vis_mode_kwargs``; engine/technical config and card-growth
    stay in ``apply_vis_mode_kwargs`` (they need the widget's engine).

    ``host`` is the ``VisualizerPresentationState`` (widget-free path) or the
    legacy widget, whose presentation fields delegate to that same state.
    """

    # --- Oscilloscope styling ----------------------------------------
    if 'osc_glow_enabled' in kwargs:
        host._osc_glow_enabled = bool(kwargs['osc_glow_enabled'])
    if 'osc_glow_intensity' in kwargs:
        host._osc_glow_intensity = max(0.0, float(kwargs['osc_glow_intensity']))
    if 'osc_glow_size' in kwargs:
        host._osc_glow_size = max(0.1, min(3.0, float(kwargs['osc_glow_size'])))
    if 'osc_glow_reactivity' in kwargs:
        host._osc_glow_reactivity = max(0.0, min(2.0, float(kwargs['osc_glow_reactivity'])))
    if 'osc_glow_color' in kwargs:
        c = _color_or_none(kwargs['osc_glow_color'])
        if c is not None:
            host._osc_glow_color = c
    if 'osc_reactive_glow' in kwargs:
        host._osc_reactive_glow = bool(kwargs['osc_reactive_glow'])
    if 'osc_smoothing' in kwargs:
        host._osc_smoothing = max(0.0, min(1.0, float(kwargs['osc_smoothing'])))
    if 'osc_line_color' in kwargs:
        c = _color_or_none(kwargs['osc_line_color'])
        if c is not None:
            host._osc_line_color = c
    if 'osc_line_count' in kwargs:
        host._osc_line_count = max(1, min(6, int(kwargs['osc_line_count'])))
    for _idx in range(2, 7):
        _ck = f'osc_line{_idx}_color'
        _gk = f'osc_line{_idx}_glow_color'
        if _ck in kwargs:
            c = _color_or_none(kwargs[_ck])
            if c is not None:
                setattr(host, f'_osc_line{_idx}_color', c)
        if _gk in kwargs:
            c = _color_or_none(kwargs[_gk])
            if c is not None:
                setattr(host, f'_osc_line{_idx}_glow_color', c)
    for _idx in range(2, 7):
        _ek = f'osc_ghost_line{_idx}_enabled'
        if _ek in kwargs:
            setattr(host, f'_osc_ghost_line{_idx}_enabled', bool(kwargs[_ek]))
    if 'osc_line_dim' in kwargs:
        host._osc_line_dim = bool(kwargs['osc_line_dim'])
    if 'osc_line_offset_bias' in kwargs:
        host._osc_line_offset_bias = max(0.0, min(1.0, float(kwargs['osc_line_offset_bias'])))
    if 'osc_vertical_shift' in kwargs:
        host._osc_vertical_shift = int(kwargs['osc_vertical_shift'])

    # --- Card + bar styling (global across modes) --------------------
    if 'bar_fill_color' in kwargs:
        c = _color_or_none(kwargs['bar_fill_color'])
        if c is not None:
            host._bar_fill_color = c
    if 'bar_border_color' in kwargs:
        c = _color_or_none(kwargs['bar_border_color'])
        if c is not None:
            host._bar_border_color = c
    if 'bar_border_opacity' in kwargs:
        try:
            opacity = max(0.0, min(1.0, float(kwargs['bar_border_opacity'])))
        except Exception:
            opacity = getattr(getattr(host, '_bar_border_color', None), 'alphaF', lambda: 1.0)()
        base = getattr(host, '_bar_border_color', None)
        if base is not None:
            color = QColor(base)
            color.setAlphaF(opacity)
            host._bar_border_color = color

    # --- Spectrum styling (glow / border / rainbow border) -----------
    # ``spectrum_unique_colors`` is the canonical settings/preset key.  The old
    # QWidget creator translated it to ``spectrum_rainbow_per_bar`` before the
    # mixed applier ran; Quick consumes the canonical model directly.
    if 'spectrum_unique_colors' in kwargs:
        host._rainbow_per_bar = bool(kwargs['spectrum_unique_colors'])
    elif 'spectrum_rainbow_per_bar' in kwargs:
        host._rainbow_per_bar = bool(kwargs['spectrum_rainbow_per_bar'])
    if 'spectrum_rainbow_border' in kwargs:
        host._spectrum_rainbow_border = bool(kwargs['spectrum_rainbow_border'])
    if 'spectrum_border_radius' in kwargs:
        host._spectrum_border_radius = max(0.0, min(20.0, float(kwargs['spectrum_border_radius'])))
    if 'spectrum_glow_enabled' in kwargs:
        host._spectrum_glow_enabled = bool(kwargs['spectrum_glow_enabled'])
    if 'spectrum_glow_intensity' in kwargs:
        host._spectrum_glow_intensity = max(0.0, min(1.5, float(kwargs['spectrum_glow_intensity'])))
    if 'spectrum_glow_color' in kwargs:
        c = _color_or_none(kwargs['spectrum_glow_color'])
        if c is not None:
            host._spectrum_glow_color = c
    if 'spectrum_ghost_alpha' in kwargs:
        host._spectrum_ghost_alpha = max(0.0, min(1.0, float(kwargs['spectrum_ghost_alpha'])))

    # --- Sine styling ------------------------------------------------
    if 'sine_vertical_shift' in kwargs:
        host._sine_vertical_shift = int(kwargs['sine_vertical_shift'])
    if 'sine_card_adaptation' in kwargs:
        host._sine_card_adaptation = max(0.05, min(1.0, float(kwargs['sine_card_adaptation'])))
    if 'sine_wave_effect' in kwargs:
        host._sine_wave_effect = max(0.0, min(1.0, float(kwargs['sine_wave_effect'])))
    if 'sine_micro_wobble' in kwargs:
        host._sine_micro_wobble = max(0.0, min(1.0, float(kwargs['sine_micro_wobble'])))
    if 'sine_crawl_amount' in kwargs:
        host._sine_crawl_amount = max(0.0, min(1.0, float(kwargs['sine_crawl_amount'])))
    if 'sine_density' in kwargs:
        host._sine_density = max(0.25, min(3.0, float(kwargs['sine_density'])))
    if 'sine_displacement' in kwargs:
        host._sine_displacement = max(0.0, min(1.0, float(kwargs['sine_displacement'])))
    if 'sine_glow_enabled' in kwargs:
        host._sine_glow_enabled = bool(kwargs['sine_glow_enabled'])
    if 'sine_glow_intensity' in kwargs:
        host._sine_glow_intensity = max(0.0, float(kwargs['sine_glow_intensity']))
    if 'sine_glow_size' in kwargs:
        host._sine_glow_size = max(0.1, min(3.0, float(kwargs['sine_glow_size'])))
    if 'sine_glow_reactivity' in kwargs:
        host._sine_glow_reactivity = max(0.0, min(2.0, float(kwargs['sine_glow_reactivity'])))
    if 'sine_glow_color' in kwargs:
        c = _color_or_none(kwargs['sine_glow_color'])
        if c is not None:
            host._sine_glow_color = c
    if 'sine_line_color' in kwargs:
        c = _color_or_none(kwargs['sine_line_color'])
        if c is not None:
            host._sine_line_color = c
    if 'sine_reactive_glow' in kwargs:
        host._sine_reactive_glow = bool(kwargs['sine_reactive_glow'])
    if 'sine_smoothing' in kwargs:
        host._sine_smoothing = max(0.0, min(1.0, float(kwargs['sine_smoothing'])))
    if 'sine_line_offset_bias' in kwargs:
        host._sine_line_offset_bias = max(0.0, min(1.0, float(kwargs['sine_line_offset_bias'])))
    if 'sine_line_dim' in kwargs:
        host._sine_line_dim = bool(kwargs['sine_line_dim'])
    for _idx in range(2, 7):
        _ck = f'sine_line{_idx}_color'
        _gk = f'sine_line{_idx}_glow_color'
        if _ck in kwargs:
            c = _color_or_none(kwargs[_ck])
            if c is not None:
                setattr(host, f'_sine_line{_idx}_color', c)
        if _gk in kwargs:
            c = _color_or_none(kwargs[_gk])
            if c is not None:
                setattr(host, f'_sine_line{_idx}_glow_color', c)
    for _idx in range(2, 7):
        _ek = f'sine_ghost_line{_idx}_enabled'
        if _ek in kwargs:
            setattr(host, f'_sine_ghost_line{_idx}_enabled', bool(kwargs[_ek]))

    # --- Rainbow (per-mode keys fall back to the global key) ---------
    _mode_str = getattr(host, '_vis_mode_str', None) or ''
    _pm_re = f'{_mode_str}_rainbow_enabled' if _mode_str else ''
    _pm_rs = f'{_mode_str}_rainbow_speed' if _mode_str else ''
    if _pm_re and _pm_re in kwargs:
        host._rainbow_enabled = bool(kwargs[_pm_re])
    elif 'rainbow_enabled' in kwargs:
        host._rainbow_enabled = bool(kwargs['rainbow_enabled'])
    if _pm_rs and _pm_rs in kwargs:
        host._rainbow_speed = max(0.01, min(5.0, float(kwargs[_pm_rs])))
    elif 'rainbow_speed' in kwargs:
        host._rainbow_speed = max(0.01, min(5.0, float(kwargs['rainbow_speed'])))
    if 'rainbow_per_bar' in kwargs:
        host._rainbow_per_bar = bool(kwargs['rainbow_per_bar'])

    # --- Bubble renderer styling -------------------------------------
    if 'bubble_ghosting_enabled' in kwargs:
        host._bubble_ghosting_enabled = bool(kwargs['bubble_ghosting_enabled'])
    if 'bubble_ghost_alpha' in kwargs:
        host._bubble_ghost_alpha = max(0.0, min(1.0, float(kwargs['bubble_ghost_alpha'])))
    if 'bubble_ghost_decay' in kwargs:
        host._bubble_ghost_decay = max(0.1, min(1.0, float(kwargs['bubble_ghost_decay'])))
    if 'bubble_outline_color' in kwargs:
        c = _color_or_none(kwargs['bubble_outline_color'])
        if c is not None:
            host._bubble_outline_color = c
    if 'bubble_specular_color' in kwargs:
        c = _color_or_none(kwargs['bubble_specular_color'])
        if c is not None:
            host._bubble_specular_color = c
    if 'bubble_gradient_light' in kwargs:
        c = _color_or_none(kwargs['bubble_gradient_light'])
        if c is not None:
            host._bubble_gradient_light = c
    if 'bubble_gradient_dark' in kwargs:
        c = _color_or_none(kwargs['bubble_gradient_dark'])
        if c is not None:
            host._bubble_gradient_dark = c
    if 'bubble_pop_color' in kwargs:
        c = _color_or_none(kwargs['bubble_pop_color'])
        if c is not None:
            host._bubble_pop_color = c
    if 'bubble_specular_direction' in kwargs:
        host._bubble_specular_direction = normalize_bubble_specular_direction(kwargs['bubble_specular_direction'])
    if 'bubble_gradient_direction' in kwargs:
        host._bubble_gradient_direction = normalize_bubble_gradient_direction(kwargs['bubble_gradient_direction'])
    if 'bubble_tail_opacity' in kwargs:
        host._bubble_tail_opacity = max(0.0, min(0.85, float(kwargs['bubble_tail_opacity'])))


def apply_vis_mode_kwargs(widget: Any, kwargs: Dict[str, Any]) -> None:
    """Apply per-mode keyword settings to *widget*.

    Each key is checked in *kwargs*; if present the value is validated,
    clamped, and written to the corresponding ``widget._*`` attribute. Authored
    logical inputs go through ``apply_logical_vis_mode_kwargs``; pure renderer
    styling through ``apply_presentation_vis_mode_kwargs`` (both delegate to the
    controller-owned neutral state); engine/technical config and card-growth are
    applied here directly because they need the widget's engine.
    """

    apply_logical_vis_mode_kwargs(widget, kwargs)
    apply_presentation_vis_mode_kwargs(widget, kwargs)

    # NOTE: pure renderer/presentation-only styling is applied above through
    # apply_presentation_vis_mode_kwargs (the single presentation authority).
    # Only engine/technical config (needs the widget's engine), card-height
    # growth and Bubble simulation/layout controls remain here.

    # --- Spectrum engine / technical config ---------------------------
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
        ('spectrum_wave_amplitude', '_spectrum_wave_amplitude', 0.0, 1.0),
        ('spectrum_profile_floor', '_spectrum_profile_floor', 0.05, 0.30),
    ):
        if _shape_key in kwargs:
            val = max(_shape_lo, min(_shape_hi, float(kwargs[_shape_key])))
            if val != getattr(widget, _shape_attr, None):
                setattr(widget, _shape_attr, val)
                _shape_dirty = True
    if 'spectrum_lane_strengths_mirrored' in kwargs:
        _normalized = _normalize_lane_strengths(
            kwargs['spectrum_lane_strengths_mirrored'],
            _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED,
        )
        if _normalized is not None and _normalized != getattr(widget, '_spectrum_lane_strengths_mirrored', None):
            widget._spectrum_lane_strengths_mirrored = _normalized
            _shape_dirty = True
    if 'spectrum_lane_strengths_linear' in kwargs:
        _normalized = _normalize_lane_strengths(
            kwargs['spectrum_lane_strengths_linear'],
            _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR,
        )
        if _normalized is not None and _normalized != getattr(widget, '_spectrum_lane_strengths_linear', None):
            widget._spectrum_lane_strengths_linear = _normalized
            _shape_dirty = True
    if _shape_dirty:
        try:
            from widgets.spotify_visualizer.bar_computation import SpectrumShapeConfig
            from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine
            engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
            if engine is not None:
                engine.set_spectrum_shape_config(SpectrumShapeConfig(
                    lane_strengths_mirrored=dict(widget._spectrum_lane_strengths_mirrored),
                    lane_strengths_linear=dict(widget._spectrum_lane_strengths_linear),
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
    if 'osc_growth' in kwargs:
        widget._osc_growth = max(0.5, min(5.0, float(kwargs['osc_growth'])))
    if 'devcurve_growth' in kwargs:
        widget._devcurve_growth = max(1.0, min(5.0, float(kwargs['devcurve_growth'])))
    # --- Sine wave card-height growth ---------------------------------
    if 'sine_wave_growth' in kwargs:
        widget._sine_wave_growth = max(0.5, min(5.0, float(kwargs['sine_wave_growth'])))

    # --- Bubble simulation / layout controls (widget-owned) -----------
    if 'bubble_group_drift' in kwargs:
        widget._bubble_group_drift = bool(kwargs['bubble_group_drift'])
    if 'bubble_collision_pop_mode' in kwargs:
        mode = str(kwargs['bubble_collision_pop_mode']).strip().lower()
        if mode not in {"off", "one", "all"}:
            mode = "off"
        widget._bubble_collision_pop_mode = mode
    if 'bubble_big_visual_smoothing' in kwargs:
        widget._bubble_big_visual_smoothing = max(0.0, min(1.0, float(kwargs['bubble_big_visual_smoothing'])))
    if 'bubble_growth' in kwargs:
        widget._bubble_growth = max(1.0, min(5.0, float(kwargs['bubble_growth'])))


def _populate_shared_visualizer_extras(extra: Dict[str, Any], widget: Any) -> None:
    """Update *extra* with the cross-mode visual fields every GPU path understands.

    Authored-logical inputs (ghosting gates/decays, heartbeat) read from the
    logical host; pure renderer styling (rainbow, glow, ghost-line toggles,
    density/displacement) reads from the presentation-config owner.
    """
    pres = _presentation_source(widget)
    extra['rainbow_enabled'] = getattr(pres, '_rainbow_enabled', False)
    extra['rainbow_speed'] = getattr(pres, '_rainbow_speed', 0.5)
    extra['rainbow_per_bar'] = getattr(pres, '_rainbow_per_bar', False)
    extra['spectrum_rainbow_border'] = getattr(pres, '_spectrum_rainbow_border', False)
    extra['spectrum_glow_enabled'] = getattr(pres, '_spectrum_glow_enabled', False)
    extra['spectrum_glow_intensity'] = getattr(pres, '_spectrum_glow_intensity', 0.55)
    extra['spectrum_glow_color'] = getattr(pres, '_spectrum_glow_color', None)
    extra['spectrum_ghosting_enabled'] = getattr(widget, '_spectrum_ghosting_enabled', True)
    extra['spectrum_ghost_alpha'] = getattr(pres, '_spectrum_ghost_alpha', 0.4)
    extra['spectrum_ghost_decay'] = getattr(widget, '_spectrum_ghost_decay', 0.4)
    extra['osc_ghosting_enabled'] = getattr(widget, '_osc_ghosting_enabled', False)
    extra['osc_ghost_intensity'] = getattr(widget, '_osc_ghost_intensity', 0.4)
    extra['osc_ghost_decay'] = getattr(widget, '_osc_ghost_decay', 0.4)
    extra['osc_ghost_line2_enabled'] = getattr(pres, '_osc_ghost_line2_enabled', True)
    extra['osc_ghost_line3_enabled'] = getattr(pres, '_osc_ghost_line3_enabled', True)
    extra['sine_ghosting_enabled'] = getattr(widget, '_sine_ghosting_enabled', True)
    extra['sine_ghost_alpha'] = getattr(widget, '_sine_ghost_alpha', 0.45)
    extra['sine_ghost_decay'] = getattr(widget, '_sine_ghost_decay', 0.3)
    extra['sine_ghost_line2_enabled'] = getattr(pres, '_sine_ghost_line2_enabled', True)
    extra['sine_ghost_line3_enabled'] = getattr(pres, '_sine_ghost_line3_enabled', True)
    extra['bubble_ghosting_enabled'] = getattr(pres, '_bubble_ghosting_enabled', False)
    extra['bubble_ghost_alpha'] = getattr(pres, '_bubble_ghost_alpha', 0.0)
    extra['bubble_ghost_decay'] = getattr(pres, '_bubble_ghost_decay', 0.4)
    extra['sine_heartbeat'] = getattr(widget, '_sine_heartbeat', 0.0)
    extra['heartbeat_intensity'] = getattr(widget, '_heartbeat_intensity', 0.0)
    extra['sine_density'] = getattr(pres, '_sine_density', 1.0)
    extra['sine_displacement'] = getattr(pres, '_sine_displacement', 0.0)


def _build_shared_visualizer_extras(widget: Any) -> Dict[str, Any]:
    """Return cross-mode visual extras that all GPU paths understand."""
    extra: Dict[str, Any] = {}
    _populate_shared_visualizer_extras(extra, widget)
    return extra


def _resolve_continuous_energy_bands(widget: Any, mode_str: str, engine: Any):
    return engine.get_energy_bands()


def _populate_engine_signal_snapshot(extra: Dict[str, Any], widget: Any, mode_str: str, engine: Any) -> None:
    """Attach waveform, continuous energy, transient bus, and mode-local event edges."""
    if engine is None:
        return

    try:
        extra['activation_id'] = engine.get_activation_id()
    except Exception:
        extra['activation_id'] = None
    try:
        extra['engine_generation'] = engine.get_generation_id()
    except Exception:
        extra['engine_generation'] = None
    try:
        extra['latest_frame_generation'] = engine.get_latest_generation_with_frame()
    except Exception:
        extra['latest_frame_generation'] = None
    try:
        extra['latest_waveform_generation'] = engine.get_latest_generation_with_waveform()
    except Exception:
        extra['latest_waveform_generation'] = None

    extra['waveform'] = engine.get_waveform()
    try:
        extra['waveform_count'] = engine.get_waveform_count()
    except Exception:
        extra['waveform_count'] = len(extra['waveform'])

    extra['energy_bands'] = _resolve_continuous_energy_bands(widget, mode_str, engine)
    extra['transient_energy'] = engine.get_transient_energy_bands()
    try:
        floor_snapshot = engine.get_floor_snapshot()
    except Exception:
        floor_snapshot = None
    if floor_snapshot is not None:
        extra['floor_snapshot'] = floor_snapshot

    try:
        scheduler = engine.get_event_scheduler()
    except Exception:
        scheduler = None
    if scheduler is None:
        return

    if mode_str in {'sine_wave', 'oscilloscope'}:
        kick_evt = scheduler.peek_latest('kick', max_age_s=0.16)
        snare_evt = scheduler.peek_latest('snare', max_age_s=0.20)
        extra['line_kick_event_strength'] = (
            float(getattr(kick_evt, 'strength', 0.0)) if kick_evt is not None else 0.0
        )
        extra['line_snare_event_strength'] = (
            float(getattr(snare_evt, 'strength', 0.0)) if snare_evt is not None else 0.0
        )


def _append_line_mode_visual_extras(extra: Dict[str, Any], widget: Any, *, is_sine: bool) -> None:
    """Attach the shared Sine/Osc visual parameters.

    Authored-logical inputs (sensitivity/speed/travel/shift/width-reaction/
    sine line-count) read from the logical host; pure renderer styling (glow,
    colours, per-line styling, ghost-line toggles) from the presentation owner.
    """
    pres = _presentation_source(widget)
    extra['glow_enabled'] = getattr(pres, '_sine_glow_enabled' if is_sine else '_osc_glow_enabled', True if is_sine else False)
    extra['glow_intensity'] = getattr(pres, '_sine_glow_intensity' if is_sine else '_osc_glow_intensity', 0.5 if is_sine else 0.4)
    extra['glow_size'] = getattr(pres, '_sine_glow_size' if is_sine else '_osc_glow_size', 1.0)
    extra['glow_reactivity'] = (
        getattr(pres, '_sine_glow_reactivity', 1.0)
        if is_sine
        else getattr(pres, '_osc_glow_reactivity', 1.0)
    )
    extra['glow_color'] = getattr(pres, '_sine_glow_color' if is_sine else '_osc_glow_color', None)
    extra['reactive_glow'] = getattr(pres, '_sine_reactive_glow' if is_sine else '_osc_reactive_glow', True)
    # Authored-logical.
    extra['line_sensitivity'] = getattr(widget, '_sine_sensitivity' if is_sine else '_osc_line_amplitude', 1.0 if is_sine else 3.0)
    extra['line_speed'] = getattr(widget, '_sine_speed' if is_sine else '_osc_speed', 1.0)
    # Renderer styling.
    extra['line_smoothing'] = getattr(pres, '_sine_smoothing' if is_sine else '_osc_smoothing', 0.7)
    extra['line_dim'] = getattr(pres, '_sine_line_dim' if is_sine else '_osc_line_dim', False)
    extra['line_offset_bias'] = getattr(pres, '_sine_line_offset_bias' if is_sine else '_osc_line_offset_bias', 0.0)
    extra['osc_vertical_shift'] = getattr(pres, '_osc_vertical_shift', 0)
    extra['sine_card_adaptation'] = getattr(pres, '_sine_card_adaptation', 0.3)
    extra['sine_wave_effect'] = getattr(pres, '_sine_wave_effect', 0.0)
    extra['sine_micro_wobble'] = getattr(pres, '_sine_micro_wobble', 0.0)
    extra['sine_crawl_amount'] = getattr(pres, '_sine_crawl_amount', 0.0)
    extra['sine_vertical_shift'] = getattr(pres, '_sine_vertical_shift', 0)
    # Authored-logical (Sine travels / shifts / width reaction).
    extra['sine_wave_travel'] = getattr(widget, '_sine_wave_travel', 0)
    extra['sine_travel_line2'] = getattr(widget, '_sine_travel_line2', 0)
    extra['sine_travel_line3'] = getattr(widget, '_sine_travel_line3', 0)
    extra['sine_travel_line4'] = getattr(widget, '_sine_travel_line4', 0)
    extra['sine_travel_line5'] = getattr(widget, '_sine_travel_line5', 0)
    extra['sine_travel_line6'] = getattr(widget, '_sine_travel_line6', 0)
    extra['sine_line1_shift'] = getattr(widget, '_sine_line1_shift', 0.0)
    extra['sine_line2_shift'] = getattr(widget, '_sine_line2_shift', 0.0)
    extra['sine_line3_shift'] = getattr(widget, '_sine_line3_shift', 0.0)
    extra['sine_line4_shift'] = getattr(widget, '_sine_line4_shift', 0.0)
    extra['sine_line5_shift'] = getattr(widget, '_sine_line5_shift', 0.0)
    extra['sine_line6_shift'] = getattr(widget, '_sine_line6_shift', 0.0)
    extra['sine_width_reaction'] = getattr(widget, '_sine_width_reaction', 0.0)
    # Line colours / count (sine line-count is authored-logical; osc is styling).
    extra['line_color'] = getattr(pres, '_sine_line_color' if is_sine else '_osc_line_color', None)
    extra['line_count'] = (
        getattr(widget, '_sine_line_count', 1)
        if is_sine
        else getattr(pres, '_osc_line_count', 1)
    )
    _side = 'sine' if is_sine else 'osc'
    for _i in range(2, 7):
        extra[f'line{_i}_color'] = getattr(pres, f'_{_side}_line{_i}_color', None)
        extra[f'line{_i}_glow_color'] = getattr(pres, f'_{_side}_line{_i}_glow_color', None)
    for _i in range(2, 7):
        extra[f'ghost_line{_i}_enabled'] = bool(
            getattr(pres, f'_{_side}_ghost_line{_i}_enabled', True)
        )
    # Legacy ghost enabled keys (for shader compatibility)
    for _i in range(2, 7):
        extra[f'osc_ghost_line{_i}_enabled'] = bool(getattr(pres, f'_osc_ghost_line{_i}_enabled', True))
        extra[f'sine_ghost_line{_i}_enabled'] = bool(getattr(pres, f'_sine_ghost_line{_i}_enabled', True))

    # Preset guardrail: when paused, ensure Sine has minimum travel so it
    # remains visibly alive even if a preset stores travel as NONE.
    if is_sine and not bool(getattr(widget, "_spotify_playing", False)):
        t1 = int(extra.get('sine_wave_travel', 0) or 0)
        t2 = int(extra.get('sine_travel_line2', 0) or 0)
        t3 = int(extra.get('sine_travel_line3', 0) or 0)
        t4 = int(extra.get('sine_travel_line4', 0) or 0)
        t5 = int(extra.get('sine_travel_line5', 0) or 0)
        t6 = int(extra.get('sine_travel_line6', 0) or 0)
        preferred = next((d for d in (t1, t2, t3, t4, t5, t6) if d in (1, 2)), 2)
        if t1 == 0:
            extra['sine_wave_travel'] = preferred
        # Ensure fallback travel is actually visible at idle without becoming
        # distractingly fast for quiet/paused scenes.
        extra['line_speed'] = max(0.22, float(extra.get('line_speed', 0.0) or 0.0))




def _append_bubble_visual_extras(extra: Dict[str, Any], widget: Any) -> None:
    """Attach only GL-safe Bubble extras.

    Renderer colours/directions/tail read from the presentation owner; the
    simulation arrays/counts read from the authored logical host.
    """
    pres = _presentation_source(widget)
    extra['bubble_outline_color'] = getattr(pres, '_bubble_outline_color', None)
    extra['bubble_specular_color'] = getattr(pres, '_bubble_specular_color', None)
    extra['bubble_gradient_light'] = getattr(pres, '_bubble_gradient_light', None)
    extra['bubble_gradient_dark'] = getattr(pres, '_bubble_gradient_dark', None)
    extra['bubble_pop_color'] = getattr(pres, '_bubble_pop_color', None)
    extra['bubble_specular_direction'] = getattr(pres, '_bubble_specular_direction', 'top_left')
    extra['bubble_gradient_direction'] = getattr(pres, '_bubble_gradient_direction', 'top')
    extra['bubble_pos_data'] = getattr(widget, '_bubble_pos_data', [])
    extra['bubble_extra_data'] = getattr(widget, '_bubble_extra_data', [])
    extra['bubble_trail_data'] = getattr(widget, '_bubble_trail_data', [])
    extra['bubble_trail_strength'] = getattr(widget, '_bubble_trail_strength', 0.0)
    extra['bubble_tail_opacity'] = getattr(pres, '_bubble_tail_opacity', 0.0)
    extra['bubble_count'] = getattr(widget, '_bubble_count', 0)


def build_gpu_push_extra_kwargs(widget: Any, mode_str: str, engine: Any) -> Dict[str, Any]:
    """Build the mode-local GPU extras payload for the compositor overlay."""
    if mode_str == 'spectrum':
        extra = getattr(widget, '_spectrum_gpu_push_extras', None)
        if not isinstance(extra, dict):
            extra = {}
            widget._spectrum_gpu_push_extras = extra
        extra.clear()
        _populate_shared_visualizer_extras(extra, widget)
        _populate_engine_signal_snapshot(extra, widget, mode_str, engine)
        return extra

    extra = _build_shared_visualizer_extras(widget)
    _populate_engine_signal_snapshot(extra, widget, mode_str, engine)
    if mode_str in {'sine_wave', 'oscilloscope'}:
        _append_line_mode_visual_extras(extra, widget, is_sine=(mode_str == 'sine_wave'))
    elif mode_str == 'bubble':
        _append_bubble_visual_extras(extra, widget)
    elif mode_str == 'devcurve':
        _append_devcurve_visual_extras(extra, widget)
    return extra


def _append_devcurve_visual_extras(extra: Dict[str, Any], widget: Any) -> None:
    """Attach GL-safe Dev Curve extras for the compositor overlay."""
    extra['devcurve_base_level'] = float(getattr(widget, '_devcurve_base_level', 0.58))
    extra['devcurve_sample_count'] = int(getattr(widget, '_devcurve_sample_count', 96))
    extra['devcurve_curve_bass'] = list(getattr(widget, '_devcurve_curve_bass', []))
    extra['devcurve_curve_vocals'] = list(getattr(widget, '_devcurve_curve_vocals', []))
    extra['devcurve_curve_mids'] = list(getattr(widget, '_devcurve_curve_mids', []))
    extra['devcurve_curve_transients'] = list(getattr(widget, '_devcurve_curve_transients', []))
    extra['devcurve_layer_bass_color'] = getattr(widget, '_devcurve_layer_bass_color', None)
    extra['devcurve_layer_vocals_color'] = getattr(widget, '_devcurve_layer_vocals_color', None)
    extra['devcurve_layer_mids_color'] = getattr(widget, '_devcurve_layer_mids_color', None)
    extra['devcurve_layer_transients_color'] = getattr(widget, '_devcurve_layer_transients_color', None)
    extra['devcurve_layer_bass_outline_color'] = getattr(widget, '_devcurve_layer_bass_outline_color', None)
    extra['devcurve_layer_vocals_outline_color'] = getattr(widget, '_devcurve_layer_vocals_outline_color', None)
    extra['devcurve_layer_mids_outline_color'] = getattr(widget, '_devcurve_layer_mids_outline_color', None)
    extra['devcurve_layer_transients_outline_color'] = getattr(widget, '_devcurve_layer_transients_outline_color', None)
    extra['devcurve_layer_bass_outline_width'] = float(getattr(widget, '_devcurve_layer_bass_outline_width', 0.006))
    extra['devcurve_layer_vocals_outline_width'] = float(getattr(widget, '_devcurve_layer_vocals_outline_width', 0.006))
    extra['devcurve_layer_mids_outline_width'] = float(getattr(widget, '_devcurve_layer_mids_outline_width', 0.006))
    extra['devcurve_layer_transients_outline_width'] = float(getattr(widget, '_devcurve_layer_transients_outline_width', 0.006))
    extra['devcurve_layer_bass_alpha'] = float(getattr(widget, '_devcurve_layer_bass_alpha', 0.55))
    extra['devcurve_layer_vocals_alpha'] = float(getattr(widget, '_devcurve_layer_vocals_alpha', 0.42))
    extra['devcurve_layer_mids_alpha'] = float(getattr(widget, '_devcurve_layer_mids_alpha', 0.46))
    extra['devcurve_layer_transients_alpha'] = float(getattr(widget, '_devcurve_layer_transients_alpha', 0.66))
    extra['devcurve_layer_bass_enabled'] = bool(getattr(widget, '_devcurve_layer_bass_enabled', True))
    extra['devcurve_layer_vocals_enabled'] = bool(getattr(widget, '_devcurve_layer_vocals_enabled', True))
    extra['devcurve_layer_mids_enabled'] = bool(getattr(widget, '_devcurve_layer_mids_enabled', True))
    extra['devcurve_layer_transients_enabled'] = bool(getattr(widget, '_devcurve_layer_transients_enabled', True))
    extra['devcurve_layer_bass_order'] = int(getattr(widget, '_devcurve_layer_bass_order', 1))
    extra['devcurve_layer_vocals_order'] = int(getattr(widget, '_devcurve_layer_vocals_order', 2))
    extra['devcurve_layer_mids_order'] = int(getattr(widget, '_devcurve_layer_mids_order', 3))
    extra['devcurve_layer_transients_order'] = int(getattr(widget, '_devcurve_layer_transients_order', 4))
    extra['devcurve_ghosting_enabled'] = bool(getattr(widget, '_devcurve_ghosting_enabled', False))
    extra['devcurve_ghost_alpha'] = float(getattr(widget, '_devcurve_ghost_alpha', 0.0))
    extra['devcurve_ghost_decay'] = float(getattr(widget, '_devcurve_ghost_decay', 0.4))
    extra['devcurve_foreground_layer_id'] = int(getattr(widget, '_devcurve_foreground_layer_id', -1))
    extra['devcurve_foreground_shadow_enabled'] = bool(getattr(widget, '_devcurve_foreground_shadow_enabled', False))
    extra['devcurve_foreground_shadow_alpha'] = float(getattr(widget, '_devcurve_foreground_shadow_alpha', 0.36))
    extra['devcurve_foreground_shadow_darken'] = float(getattr(widget, '_devcurve_foreground_shadow_darken', 0.42))
    extra['devcurve_foreground_shadow_offset'] = float(getattr(widget, '_devcurve_foreground_shadow_offset', 0.10))
    extra['devcurve_foreground_specular_enabled'] = bool(getattr(widget, '_devcurve_foreground_specular_enabled', False))
    specular_activity = max(0.0, min(1.0, float(getattr(widget, '_devcurve_specular_activity_alpha', 1.0))))
    extra['devcurve_foreground_specular_alpha'] = (
        float(getattr(widget, '_devcurve_foreground_specular_alpha', 0.78))
        * specular_activity
    )
    extra['devcurve_foreground_specular_width'] = float(getattr(widget, '_devcurve_foreground_specular_width', 0.022))
    extra['devcurve_foreground_specular_offset'] = float(getattr(widget, '_devcurve_foreground_specular_offset', 0.028))
    extra['devcurve_foreground_specular_crest_bias'] = float(getattr(widget, '_devcurve_foreground_specular_crest_bias', 1.05))
    _slot0 = getattr(widget, '_devcurve_specular_slot0', [0.0, 0.0, 0.0])
    _slot1 = getattr(widget, '_devcurve_specular_slot1', [0.0, 0.0, 0.0])
    _slot2 = getattr(widget, '_devcurve_specular_slot2', [0.0, 0.0, 0.0])
    extra['devcurve_specular_slot0'] = [
        max(-1.5, min(2.5, float(_slot0[0] if isinstance(_slot0, (list, tuple)) and len(_slot0) > 0 else 0.0))),
        max(0.0, min(1.0, float(_slot0[1] if isinstance(_slot0, (list, tuple)) and len(_slot0) > 1 else 0.0))),
        max(0.0, min(1.0, float(_slot0[2] if isinstance(_slot0, (list, tuple)) and len(_slot0) > 2 else 0.0))),
        max(0.0, min(1.0, float(_slot0[3] if isinstance(_slot0, (list, tuple)) and len(_slot0) > 3 else 0.0))),
    ]
    extra['devcurve_specular_slot1'] = [
        max(-1.5, min(2.5, float(_slot1[0] if isinstance(_slot1, (list, tuple)) and len(_slot1) > 0 else 0.0))),
        max(0.0, min(1.0, float(_slot1[1] if isinstance(_slot1, (list, tuple)) and len(_slot1) > 1 else 0.0))),
        max(0.0, min(1.0, float(_slot1[2] if isinstance(_slot1, (list, tuple)) and len(_slot1) > 2 else 0.0))),
        max(0.0, min(1.0, float(_slot1[3] if isinstance(_slot1, (list, tuple)) and len(_slot1) > 3 else 0.0))),
    ]
    extra['devcurve_specular_slot2'] = [
        max(-1.5, min(2.5, float(_slot2[0] if isinstance(_slot2, (list, tuple)) and len(_slot2) > 0 else 0.0))),
        max(0.0, min(1.0, float(_slot2[1] if isinstance(_slot2, (list, tuple)) and len(_slot2) > 1 else 0.0))),
        max(0.0, min(1.0, float(_slot2[2] if isinstance(_slot2, (list, tuple)) and len(_slot2) > 2 else 0.0))),
        max(0.0, min(1.0, float(_slot2[3] if isinstance(_slot2, (list, tuple)) and len(_slot2) > 3 else 0.0))),
    ]


def replay_engine_config(widget: Any, engine: Any) -> None:
    """Ensure the shared engine reflects the authoritative config for current mode.

    Reads the authoritative per-mode technical config from settings/presets
    and replays it to the engine, audio worker, and GL overlay so that all
    subsystems stay in sync after a reset or mode switch.
    """
    if engine is None:
        return

    config = widget._get_mode_technical_config(widget._vis_mode)
    if config is None:
        logger.debug("[SPOTIFY_VIS] No technical config available for mode=%s, skipping replay", widget._vis_mode.name)
        return

    dynamic_floor = bool(config.get("dynamic_floor", True))
    manual_floor = float(config.get("manual_floor", 0.12))
    adaptive = bool(config.get("adaptive_sensitivity", True))
    sensitivity = float(config.get("sensitivity", 1.0))
    audio_block_size = int(config.get("audio_block_size", 0) or 0)
    dynamic_range_enabled = bool(config.get("dynamic_range_enabled", False))
    energy_boost = widget._compute_energy_boost(dynamic_range_enabled)
    agc_strength = max(0.0, min(1.0, float(config.get("agc_strength", 0.5))))
    input_gain = max(0.05, min(2.0, float(config.get("input_gain", 1.0))))

    kick_lane_gain = max(0.0, min(2.0, float(config.get("kick_lane_gain", 1.0))))
    transient_pulse_gain = max(0.0, min(3.0, float(config.get("transient_pulse_gain", 1.5))))
    transient_clamp = max(0.0, min(3.0, float(config.get("transient_clamp", 1.5))))
    spectrum_lane_transient_mix = max(0.0, min(1.0, float(config.get("spectrum_lane_transient_mix", 0.65))))
    bubble_transient_mix_bass = max(0.0, min(1.0, float(config.get("bubble_transient_mix_bass", 0.75))))
    bubble_transient_mix_vocal = max(0.0, min(1.0, float(config.get("bubble_transient_mix_vocal", 0.25))))
    sine_wave_transient_width_mix = max(0.0, min(1.0, float(config.get("sine_wave_transient_width_mix", 0.4))))
    osc_transient_width_mix = max(0.0, min(1.0, float(config.get("oscilloscope_transient_width_mix", 0.35))))

    widget._use_raw_energy = False
    widget._kick_lane_gain = kick_lane_gain
    widget._transient_pulse_gain = transient_pulse_gain
    widget._transient_clamp = transient_clamp
    widget._spectrum_lane_transient_mix = spectrum_lane_transient_mix
    widget._bubble_transient_mix_bass = bubble_transient_mix_bass
    widget._bubble_transient_mix_vocal = bubble_transient_mix_vocal
    widget._sine_wave_transient_width_mix = sine_wave_transient_width_mix
    widget._osc_transient_width_mix = osc_transient_width_mix

    widget.apply_floor_config(dynamic_floor, manual_floor)
    widget.apply_sensitivity_config(adaptive, sensitivity)
    widget._apply_audio_block_size(audio_block_size)
    widget._apply_energy_boost(energy_boost)
    widget._apply_agc_strength(agc_strength)
    widget._apply_input_gain(input_gain)

    if engine is not None:
        aw = getattr(engine, '_audio_worker', None)
        if aw is not None:
            try:
                aw._kick_lane_gain = kick_lane_gain
                aw._spectrum_lane_transient_mix = spectrum_lane_transient_mix
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to replay transient config to audio worker", exc_info=True)

    parent = widget.parent()
    overlay = getattr(parent, '_spotify_bars_overlay', None) if parent else None
    if overlay is not None:
        try:
            overlay._transient_pulse_gain = transient_pulse_gain
            overlay._transient_clamp = transient_clamp
            overlay._sine_wave_transient_width_mix = sine_wave_transient_width_mix
            overlay._osc_transient_width_mix = osc_transient_width_mix
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replay transient config to GL overlay", exc_info=True)

    logger.debug("[SPOTIFY_VIS] Replayed authoritative config for mode=%s", widget._vis_mode.name)
    try:
        _active_notches = (widget._spectrum_notch_positions_mirrored
                           if widget._spectrum_mirrored
                           else widget._spectrum_notch_positions_linear)
        engine.set_notch_positions(_active_notches)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to replay notch positions config", exc_info=True)
