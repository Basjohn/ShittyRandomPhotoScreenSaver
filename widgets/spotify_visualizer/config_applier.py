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
from core.settings.default_contract import require_canonical_default
from core.settings.bubble_gradient_semantics import (
    normalize_bubble_gradient_direction,
    normalize_bubble_specular_direction,
)
from core.settings.visualizer_settings_contract import normalize_spectrum_render_mode
from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
from widgets.spotify_visualizer.render_state import FrozenFields, freeze_render_fields

logger = get_logger(__name__)

_SPHERE_PARAMETER_KEYS = (
    "sphere_fill_color",
    "sphere_edge_color",
    "sphere_allow_overflow",
    "sphere_cel_shading",
    "sphere_light_tracer_enabled",
    "sphere_fragment_interpolation_enabled",
    "sphere_incoming_density_response_enabled",
    "sphere_incoming_transient_velocity_enabled",
    "sphere_particle_outtake_enabled",
    "sphere_rainbow_ghosting",
    "sphere_shadow_enabled",
    "sphere_fade_incoming_blocks",
    "sphere_deformation",
    "sphere_base_rotation_speed",
    "sphere_rotation_speed",
    "sphere_gloss",
    "sphere_specular",
    "sphere_light_direction",
    "sphere_idle_motion",
    "sphere_surface_detail",
    "sphere_bass_response",
    "sphere_mid_response",
    "sphere_high_response",
    "sphere_vocal_response",
    "sphere_bump_reactivity",
    "sphere_size_response",
    "sphere_energy_curve",
)


def _visualizer_default(key: str) -> Any:
    return require_canonical_default(f"widgets.spotify_visualizer.{key}")


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

    # The experimental Sphere keeps one configure-owned immutable parameter
    for key in ('sphere_allow_overflow', 'sphere_cel_shading', 'sphere_light_tracer_enabled', 'sphere_fragment_interpolation_enabled', 'sphere_incoming_density_response_enabled', 'sphere_incoming_transient_velocity_enabled', 'sphere_particle_outtake_enabled', 'sphere_rainbow_ghosting', 'sphere_shadow_enabled', 'sphere_fade_incoming_blocks'):
        if key in kwargs:
            setattr(host, f"_{key}", bool(kwargs[key]))
    # bundle. The voxel renderer consumes that snapshot without a second
    # settings/runtime authority or per-frame Python geometry rebuild.
    for key in ('sphere_fill_color', 'sphere_edge_color'):
        if key in kwargs:
            raw = kwargs[key]
            if not isinstance(raw, (list, tuple)) or len(raw) < 3:
                raise ValueError(f"{key} must be an RGB/RGBA sequence")
            values = list(raw[:4])
            while len(values) < 4:
                values.append(255)
            try:
                rgba = tuple(max(0, min(255, int(round(float(v))))) for v in values)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must contain numeric RGB/RGBA channels") from exc
            setattr(host, f"_{key}", rgba)
    if 'sphere_deformation' in kwargs:
        host._sphere_deformation = _sphere_bounded(kwargs['sphere_deformation'], 0.0, 4.5, 'sphere_deformation')
    if 'sphere_base_rotation_speed' in kwargs:
        host._sphere_base_rotation_speed = _sphere_bounded(kwargs['sphere_base_rotation_speed'], 0.0, 0.5, 'sphere_base_rotation_speed')
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
        ('sphere_energy_curve', 2.0),
    ):
        if key in kwargs:
            setattr(host, f"_{key}", _sphere_bounded(kwargs[key], 0.2 if key == "sphere_energy_curve" else 0.0, maximum, key))
    if any(key in kwargs for key in _SPHERE_PARAMETER_KEYS):
        host._sphere_parameters = freeze_render_fields({
            key: getattr(host, f"_{key}")
            for key in _SPHERE_PARAMETER_KEYS
        })
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
            val = str(_visualizer_default('bubble_stream_direction')).lower()
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
            val = str(_visualizer_default('bubble_drift_direction')).lower()
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
            mode = str(_visualizer_default('bubble_collision_pop_mode')).strip().lower()
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
    if 'bubble_ghosting_enabled' in kwargs:
        host._bubble_ghosting_enabled = bool(kwargs['bubble_ghosting_enabled'])

    # --- Spectrum authored logical inputs (SpectrumFrameRuntime.resolve) ---
    # Canonical presets/settings store ``spectrum_render_mode``.  The historical
    # creator translated that value to the boolean consumed by authored state;
    # Quick has no creator façade, so the logical owner performs that tiny
    # semantic translation directly.  Retain the legacy boolean only as a
    # fallback for old focused callers.
    if 'spectrum_render_mode' in kwargs:
        host._spectrum_single_piece = (
            normalize_spectrum_render_mode(
                kwargs['spectrum_render_mode'],
                str(_visualizer_default('spectrum_render_mode')),
            )
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
        opacity = max(0.0, min(1.0, float(kwargs['bar_border_opacity'])))
        color = QColor(host._bar_border_color)
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
    _rainbow_keys = (
        get_owned_mode_setting_keys(_mode_str, "rainbow")
        if _mode_str
        else {}
    )
    _pm_re = _rainbow_keys.get("rainbow_enabled", "")
    _pm_rs = _rainbow_keys.get("rainbow_speed", "")
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
    """Copy the already-resolved cross-mode logical/presentation contract."""
    pres = _presentation_source(widget)
    extra['rainbow_enabled'] = pres._rainbow_enabled
    extra['rainbow_speed'] = pres._rainbow_speed
    extra['rainbow_per_bar'] = pres._rainbow_per_bar
    extra['spectrum_rainbow_fill'] = pres._spectrum_rainbow_fill
    extra['spectrum_rainbow_border'] = pres._spectrum_rainbow_border
    extra['spectrum_glow_enabled'] = pres._spectrum_glow_enabled
    extra['spectrum_glow_intensity'] = pres._spectrum_glow_intensity
    extra['spectrum_glow_color'] = pres._spectrum_glow_color
    extra['spectrum_ghosting_enabled'] = widget._spectrum_ghosting_enabled
    extra['spectrum_ghost_alpha'] = pres._spectrum_ghost_alpha
    extra['spectrum_ghost_decay'] = widget._spectrum_ghost_decay
    extra['osc_ghosting_enabled'] = widget._osc_ghosting_enabled
    extra['osc_ghost_intensity'] = widget._osc_ghost_intensity
    extra['osc_ghost_decay'] = widget._osc_ghost_decay
    extra['osc_ghost_line2_enabled'] = pres._osc_ghost_line2_enabled
    extra['osc_ghost_line3_enabled'] = pres._osc_ghost_line3_enabled
    extra['sine_ghosting_enabled'] = widget._sine_ghosting_enabled
    extra['sine_ghost_alpha'] = widget._sine_ghost_alpha
    extra['sine_ghost_decay'] = widget._sine_ghost_decay
    extra['sine_ghost_line2_enabled'] = pres._sine_ghost_line2_enabled
    extra['sine_ghost_line3_enabled'] = pres._sine_ghost_line3_enabled
    extra['bubble_ghosting_enabled'] = pres._bubble_ghosting_enabled
    extra['bubble_ghost_alpha'] = pres._bubble_ghost_alpha
    extra['bubble_ghost_decay'] = pres._bubble_ghost_decay
    extra['sine_heartbeat'] = widget._sine_heartbeat
    extra['heartbeat_intensity'] = widget._heartbeat_intensity
    extra['sine_density'] = pres._sine_density
    extra['sine_displacement'] = pres._sine_displacement





def _append_line_mode_visual_extras(extra: Dict[str, Any], widget: Any, *, is_sine: bool) -> None:
    """Attach the shared Sine/Osc visual parameters.

    Authored-logical inputs (sensitivity/speed/travel/shift/width-reaction/
    sine line-count) read from the logical host; pure renderer styling (glow,
    colours, per-line styling, ghost-line toggles) from the presentation owner.
    """
    pres = _presentation_source(widget)
    extra['glow_enabled'] = getattr(pres, '_sine_glow_enabled' if is_sine else '_osc_glow_enabled')
    extra['glow_intensity'] = getattr(pres, '_sine_glow_intensity' if is_sine else '_osc_glow_intensity')
    extra['glow_size'] = 1.0  # fixed shader-space expansion; no longer a product setting
    extra['glow_reactivity'] = (
        pres._sine_glow_reactivity
        if is_sine
        else pres._osc_glow_reactivity
    )
    extra['glow_color'] = getattr(pres, '_sine_glow_color' if is_sine else '_osc_glow_color')
    extra['reactive_glow'] = getattr(pres, '_sine_reactive_glow' if is_sine else '_osc_reactive_glow')
    # Authored-logical.
    extra['line_sensitivity'] = getattr(widget, '_sine_sensitivity' if is_sine else '_osc_line_amplitude')
    extra['line_speed'] = getattr(widget, '_sine_speed' if is_sine else '_osc_speed')
    # Renderer styling.
    extra['line_smoothing'] = getattr(pres, '_sine_smoothing' if is_sine else '_osc_smoothing')
    extra['line_dim'] = getattr(pres, '_sine_line_dim' if is_sine else '_osc_line_dim')
    extra['line_offset_bias'] = getattr(pres, '_sine_line_offset_bias' if is_sine else '_osc_line_offset_bias')
    extra['osc_vertical_shift'] = pres._osc_vertical_shift
    extra['sine_card_adaptation'] = pres._sine_card_adaptation
    extra['sine_wave_effect'] = pres._sine_wave_effect
    extra['sine_micro_wobble'] = pres._sine_micro_wobble
    extra['sine_crawl_amount'] = pres._sine_crawl_amount
    extra['sine_vertical_shift'] = pres._sine_vertical_shift
    # Authored-logical (Sine travels / shifts / width reaction).
    extra['sine_wave_travel'] = widget._sine_wave_travel
    extra['sine_travel_line2'] = widget._sine_travel_line2
    extra['sine_travel_line3'] = widget._sine_travel_line3
    extra['sine_travel_line4'] = widget._sine_travel_line4
    extra['sine_travel_line5'] = widget._sine_travel_line5
    extra['sine_travel_line6'] = widget._sine_travel_line6
    extra['sine_line1_shift'] = widget._sine_line1_shift
    extra['sine_line2_shift'] = widget._sine_line2_shift
    extra['sine_line3_shift'] = widget._sine_line3_shift
    extra['sine_line4_shift'] = widget._sine_line4_shift
    extra['sine_line5_shift'] = widget._sine_line5_shift
    extra['sine_line6_shift'] = widget._sine_line6_shift
    extra['sine_width_reaction'] = widget._sine_width_reaction
    # Line colours / count (sine line-count is authored-logical; osc is styling).
    extra['line_color'] = getattr(pres, '_sine_line_color' if is_sine else '_osc_line_color')
    extra['line_count'] = (
        widget._sine_line_count
        if is_sine
        else pres._osc_line_count
    )
    _side = 'sine' if is_sine else 'osc'
    for _i in range(2, 7):
        extra[f'line{_i}_color'] = getattr(pres, f'_{_side}_line{_i}_color')
        extra[f'line{_i}_glow_color'] = getattr(pres, f'_{_side}_line{_i}_glow_color')
    for _i in range(2, 7):
        extra[f'ghost_line{_i}_enabled'] = bool(
            getattr(pres, f'_{_side}_ghost_line{_i}_enabled')
        )
    # Legacy ghost enabled keys (for shader compatibility)
    for _i in range(2, 7):
        extra[f'osc_ghost_line{_i}_enabled'] = bool(getattr(pres, f'_osc_ghost_line{_i}_enabled'))
        extra[f'sine_ghost_line{_i}_enabled'] = bool(getattr(pres, f'_sine_ghost_line{_i}_enabled'))

    # Preset guardrail: when paused, ensure Sine has minimum travel so it
    # remains visibly alive even if a preset stores travel as NONE.
    if is_sine and not bool(getattr(widget, "_spotify_playing", False)):
        t1 = int(extra['sine_wave_travel'])
        t2 = int(extra['sine_travel_line2'])
        t3 = int(extra['sine_travel_line3'])
        t4 = int(extra['sine_travel_line4'])
        t5 = int(extra['sine_travel_line5'])
        t6 = int(extra['sine_travel_line6'])
        preferred = next((d for d in (t1, t2, t3, t4, t5, t6) if d in (1, 2)), 2)
        if t1 == 0:
            extra['sine_wave_travel'] = preferred
        # Ensure fallback travel is actually visible at idle without becoming
        # distractingly fast for quiet/paused scenes.
        extra['line_speed'] = max(0.22, float(extra['line_speed']))




def _append_bubble_visual_extras(extra: Dict[str, Any], widget: Any) -> None:
    """Attach only GL-safe Bubble extras.

    Renderer colours/directions/tail read from the presentation owner; the
    simulation arrays/counts read from the authored logical host.
    """
    pres = _presentation_source(widget)
    extra['bubble_outline_color'] = pres._bubble_outline_color
    extra['bubble_specular_color'] = pres._bubble_specular_color
    extra['bubble_gradient_light'] = pres._bubble_gradient_light
    extra['bubble_gradient_dark'] = pres._bubble_gradient_dark
    extra['bubble_pop_color'] = pres._bubble_pop_color
    extra['bubble_specular_direction'] = pres._bubble_specular_direction
    extra['bubble_gradient_direction'] = pres._bubble_gradient_direction
    extra['bubble_pos_data'] = getattr(widget, '_bubble_pos_data', [])
    extra['bubble_extra_data'] = getattr(widget, '_bubble_extra_data', [])
    extra['bubble_trail_data'] = getattr(widget, '_bubble_trail_data', [])
    extra['bubble_trail_strength'] = widget._bubble_trail_strength
    extra['bubble_tail_opacity'] = pres._bubble_tail_opacity
    extra['bubble_count'] = widget._bubble_count
