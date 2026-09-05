"""Visualizer configuration mapping for the retained Quick architecture.

Authored-logical settings are applied to controller-owned logical state and
pure renderer styling to ``VisualizerPresentationState``. Source/BeatEngine
configuration is owned separately by ``source_config_applier``. This module
contains no retired QWidget catch-all configuration authority.
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
from widgets.spotify_visualizer.render_state import FrozenFields, freeze_render_fields

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

SPHERE_DEFAULT_PARAMETERS = freeze_render_fields({
    "sphere_material": "Chrome", "sphere_deformation": 1.0,
    "sphere_rotation_speed": 0.35, "sphere_gloss": 0.65,
    "sphere_specular": 0.8, "sphere_light_direction": "NW",
    "sphere_idle_motion": 0.12, "sphere_surface_detail": 1.15,
    "sphere_bass_response": 1.0, "sphere_mid_response": 1.0,
    "sphere_high_response": 1.0, "sphere_vocal_response": 1.4,
    "sphere_bump_reactivity": 0.65,
    "sphere_size_response": 1.5,
    "sphere_energy_curve": 0.60,
    "sphere_material_fx": 1.0,
    "sphere_antialiasing": True,
    "sphere_shadow_enabled": True,
    "sphere_shadow_strength": 0.62,
})
_SPHERE_PARAMETER_KEYS = tuple(SPHERE_DEFAULT_PARAMETERS)


def _sphere_bounded(value: object, minimum: float, maximum: float, key: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{key} must be finite")
    return max(minimum, min(maximum, number))


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
    (normally ``VisualizerLogicalTickState``).

    This is the single authority for the logical portion of the per-mode
    settings apply. "Logical" here is classified by the actual consumer, not by
    naming: a value is applied here iff authored logical evolution or a
    mode-owned logical frame runtime reads it (Bubble physics, plus the
    Spectrum/Oscilloscope/Sine inputs consumed by each mode's
    ``*FrameRuntime.resolve`` and the DevCurve inputs consumed by the DevCurve
    logical field solve). Pure renderer/chrome/style values (bar/line/glow
    colours, glow sizing, card radius, rainbow styling) stay presentation-owned
    in ``apply_presentation_vis_mode_kwargs``.
    """

    # Sphere is fully logical-frame configuration. Normalize and freeze this
    # once at configuration ownership; capture/runtime only transport it.
    if 'sphere_material' in kwargs:
        material = str(kwargs['sphere_material']).strip().title()
        if material not in {'Chrome', 'Obsidian', 'Magma', 'Silver', 'Water'}:
            raise ValueError(f"invalid sphere material {material!r}")
        host._sphere_material = material
    if 'sphere_deformation' in kwargs:
        host._sphere_deformation = _sphere_bounded(kwargs['sphere_deformation'], 0.0, 4.5, 'sphere_deformation')
    if 'sphere_rotation_speed' in kwargs:
        host._sphere_rotation_speed = _sphere_bounded(kwargs['sphere_rotation_speed'], 0.0, 2.0, 'sphere_rotation_speed')
    if 'sphere_gloss' in kwargs:
        host._sphere_gloss = _sphere_bounded(kwargs['sphere_gloss'], 0.0, 1.0, 'sphere_gloss')
    if 'sphere_specular' in kwargs:
        host._sphere_specular = _sphere_bounded(kwargs['sphere_specular'], 0.0, 2.0, 'sphere_specular')
    if 'sphere_light_direction' in kwargs:
        direction = str(kwargs['sphere_light_direction']).strip().upper()
        if direction not in {'N','NE','E','SE','S','SW','W','NW'}:
            raise ValueError(f"invalid sphere light direction {direction!r}")
        host._sphere_light_direction = direction
    if 'sphere_idle_motion' in kwargs:
        host._sphere_idle_motion = _sphere_bounded(kwargs['sphere_idle_motion'], 0.0, 1.0, 'sphere_idle_motion')
    if 'sphere_surface_detail' in kwargs:
        host._sphere_surface_detail = _sphere_bounded(kwargs['sphere_surface_detail'], 0.0, 2.0, 'sphere_surface_detail')
    for key, maximum in (
        ('sphere_bass_response', 2.0), ('sphere_mid_response', 2.0),
        ('sphere_high_response', 2.0), ('sphere_vocal_response', 3.0),
        ('sphere_bump_reactivity', 2.0),
        ('sphere_size_response', 3.0),
        ('sphere_shadow_strength', 1.0),
        ('sphere_energy_curve', 2.0),
        ('sphere_material_fx', 2.0),
    ):
        if key in kwargs:
            setattr(host, f"_{key}", _sphere_bounded(kwargs[key], 0.2 if key == "sphere_energy_curve" else 0.0, maximum, key))
    if 'sphere_antialiasing' in kwargs:
        host._sphere_antialiasing = bool(kwargs['sphere_antialiasing'])
    if 'sphere_shadow_enabled' in kwargs:
        host._sphere_shadow_enabled = bool(kwargs['sphere_shadow_enabled'])
    if any(key in kwargs for key in _SPHERE_PARAMETER_KEYS):
        host._sphere_parameters = freeze_render_fields({
            key: getattr(host, f"_{key}", SPHERE_DEFAULT_PARAMETERS[key])
            for key in _SPHERE_PARAMETER_KEYS
        })
    elif not isinstance(getattr(host, "_sphere_parameters", None), FrozenFields):
        host._sphere_parameters = SPHERE_DEFAULT_PARAMETERS
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
        host._bubble_big_count = max(0, min(30, int(kwargs['bubble_big_count'])))
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
    colours - exactly the fields current immutable logical-frame capture reads
    when composing renderer parameters. Authored logical inputs flow through
    ``apply_logical_vis_mode_kwargs``; BeatEngine/source and technical config
    have separate controller-owned appliers.

    ``host`` is normally the controller-owned ``VisualizerPresentationState``.
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
    if 'spectrum_rainbow_fill' in kwargs:
        host._spectrum_rainbow_fill = bool(kwargs['spectrum_rainbow_fill'])
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
    if not _mode_str:
        controller = getattr(host, 'runtime_controller', None)
        _mode_str = getattr(controller, 'mode_id', None) or ''
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
    extra['spectrum_rainbow_fill'] = getattr(pres, '_spectrum_rainbow_fill', True)
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
