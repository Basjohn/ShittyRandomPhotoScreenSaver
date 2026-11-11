"""Visualizer configuration mapping for the retained Quick architecture.

Authored-logical settings are applied to controller-owned logical state and
pure renderer styling to ``VisualizerPresentationState``. Source/BeatEngine
configuration is owned separately by ``source_config_applier``. This module
contains no retired QWidget catch-all configuration authority.
"""
from __future__ import annotations

from typing import Any, Dict

from core.logging.logger import get_logger
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
from widgets.spotify_visualizer.render_state import FrozenFields, freeze_render_fields

logger = get_logger(__name__)

# Derived once; the immutable Sphere bundle still freezes only when configuration changes.
from core.settings.visualizer_mode_settings import require_mode_settings

_SPHERE_PARAMETER_KEYS = tuple(control.key for control in require_mode_settings("sphere").logical_controls())


def _visualizer_default(key: str) -> Any:
    return require_canonical_default(f"widgets.spotify_visualizer.{key}")


def _color_or_none(value: Any) -> tuple[int, int, int, int] | None:
    """A presentation colour (the shared bar fill and border) as the (r, g, b, a) ``QColor(*value).getRgb()`` gives,
    or None (native core P2b, work order 5 slice 5.4).

    The logical capture reads these from the presentation state into the frame's style, which freezes a ``QColor`` to
    exactly this tuple (``render_state.freeze_render_value``), and nothing else reads them; holding the tuple keeps the
    presentation config Qt-free, so an activation in the engine worker loads QtCore only (checkpoint audit 5, A5-L2).
    Frames are unchanged (``tests/test_visualizer_owner_production_path.py``)."""
    return _rgba_or_none(value)


def _with_alpha_f(rgba: Any, opacity: float) -> tuple[int, int, int, int]:
    """``rgba`` with the alpha ``QColor.setAlphaF(opacity)`` then ``getRgb()`` gives (Qt rounds the opacity to a
    16-bit channel, then that to 8 bits), Qt-free."""
    red, green, blue = (int(channel) for channel in tuple(rgba)[:3])
    alpha16 = int(float(opacity) * 65535.0 + 0.5)
    return (red, green, blue, int(alpha16 / 257.0 + 0.5))


def _rgba_or_none(value: Any) -> tuple[int, int, int, int] | None:
    """The (r, g, b, a) a [r, g, b(, a)] settings colour has as ``QColor(*value).getRgb()``, for logical state.

    Logical state stays Qt-free (native core P2: the tick runs in an engine worker that imports QtCore at most); the
    logical frame freezes colours to exactly this tuple (``render_state.freeze_render_value``), so frames are
    unchanged. Out-of-range channels (never produced by validated settings) are refused like a missing value."""
    if isinstance(value, (list, tuple)) and 3 <= len(value) <= 4:
        channels = [int(channel) for channel in value] + ([255] if len(value) == 3 else [])
        if all(0 <= channel <= 255 for channel in channels):
            return (channels[0], channels[1], channels[2], channels[3])
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
    Spectrum/Oscilloscope inputs consumed by each mode's
    ``*FrameRuntime.resolve`` and the DevCurve inputs consumed by the DevCurve
    logical field solve). Pure renderer/chrome/style values (bar/line/glow
    colours, glow sizing, card radius, rainbow styling) stay presentation-owned
    in ``apply_presentation_vis_mode_kwargs``.
    """

    # Spec'd modes' controls their logical evolution reads (visualizer_mode_settings).
    _apply_spec_controls(host, kwargs, logical=True)

    # Sphere keeps one configure-owned immutable parameter bundle.
    if any(key in kwargs for key in _SPHERE_PARAMETER_KEYS):
        host._sphere_parameters = freeze_render_fields({
            key: getattr(host, f"_{key}")
            for key in _SPHERE_PARAMETER_KEYS
        })

    # Spectrum smoothing remains with its existing Custom/logical owner.
    if 'spectrum_visual_smoothing_enabled' in kwargs:
        host._spectrum_visual_smoothing_enabled = bool(
            kwargs['spectrum_visual_smoothing_enabled']
        )
    if 'spectrum_visual_smoothing' in kwargs:
        host._spectrum_visual_smoothing = max(
            0.0, min(1.0, float(kwargs['spectrum_visual_smoothing']))
        )
    # --- DevCurve authored logical inputs (_devcurve_parameter_snapshot) ---
    # The DevCurve field solve runs on the authored logical clock and consumes
    # its full parameter snapshot (including per-layer colour/outline), so these
    # are logical-owned even though some read as styling.
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
            c = _rgba_or_none(kwargs[color_key])
            if c is not None:
                setattr(host, f'_devcurve_layer_{src}_color', c)
        if outline_color_key in kwargs:
            oc = _rgba_or_none(kwargs[outline_color_key])
            if oc is not None:
                setattr(host, f'_devcurve_layer_{src}_outline_color', (*oc[:3], 255))
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

    # --- Card + bar styling (global across modes) --------------------
    if ("shockwave_grid_terrain" in kwargs
            and getattr(getattr(host, "runtime_controller", None), "mode_id", None) == "shockwave_grid"):
        from rendering.gl_programs.heightfield import (
            heightfield_basin, heightfield_grid_transform, heightfield_origin, heightfield_origin_extent,
            heightfield_surface_bytes, normalize_heightfield,
        )
        from rendering.gl_programs.neon_terrain_extent import overlay_fields

        terrain = normalize_heightfield(kwargs["shockwave_grid_terrain"])
        signature = (terrain["size"], tuple(terrain["heights"]), heightfield_basin(terrain),
                     heightfield_origin(terrain))
        if signature != getattr(host, "_shockwave_grid_terrain_signature", None):
            host._shockwave_grid_terrain = freeze_render_fields({
                "size": terrain["size"], "data": heightfield_surface_bytes(terrain),
                "maximum": max(terrain["heights"]),
                # Where the basin sits in a grid reaching toward the horizon (identity when unextended).
                "basin": list(heightfield_basin(terrain)),
                "grid": list(heightfield_grid_transform(terrain)),
                # The authored origin's reach past the basin (the whole grid's unless the brush grew it): the mark
                # lattice's fine part.
                "extent": list(heightfield_origin_extent(terrain)),
                # A grown grid only: where its origin sits (the generated landscape's start), its cells' overlay
                # on the generated land, the painted bounds (the triangles' fine region) and the summit without
                # the unpainted cells.
                **overlay_fields(terrain),
            })
            host._shockwave_grid_terrain_signature = signature
    if "shockwave_grid_terrain_shaper" in kwargs:
        from rendering.gl_programs.neon_terrain_reaction import bake_terrain_shaper, normalize_terrain_shaper

        shaper = normalize_terrain_shaper(kwargs["shockwave_grid_terrain_shaper"],
                                          _visualizer_default("shockwave_grid_terrain_shaper"))
        signature = repr(shaper)
        if signature != getattr(host, "_shockwave_grid_terrain_shaper_signature", None):
            host._shockwave_grid_terrain_shaper = freeze_render_fields(bake_terrain_shaper(shaper))
            host._shockwave_grid_terrain_shaper_signature = signature
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
        host._bar_border_color = _with_alpha_f(host._bar_border_color, opacity)

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


    if 'scene3d_detail' in kwargs:
        from rendering.gl_programs.scene3d import scene3d_detail

        host._scene3d_detail = scene3d_detail(kwargs['scene3d_detail']).name   # resolved upstream

    # --- Spec'd modes' renderer-only controls (core/settings/visualizer_mode_settings.py) ---
    _apply_spec_controls(host, kwargs, logical=False)


def _apply_spec_controls(host: Any, kwargs: Dict[str, Any], *, logical: bool) -> None:
    """Store each spec'd control present in ``kwargs`` on its owner as ``_<key>``, admitted by
    its control. Canonical ingress repairs and trusted runtime admission are distinct: controls
    retaining a strict runtime contract reject malformed values instead of substituting defaults."""
    from core.settings.visualizer_mode_settings import iter_mode_settings
    from core.settings.visualizer_mode_settings import control_runtime_attr, control_runtime_value, read_control_value

    for spec in iter_mode_settings():
        for control in (spec.logical_controls() if logical else spec.presentation_controls()):
            if control.key in kwargs or any(key in kwargs for key in getattr(control, "input_aliases", ())):
                default = _visualizer_default(control.key)
                value = control.admit_runtime(read_control_value(control, kwargs.get, default), default)
                setattr(host, control_runtime_attr(control), control_runtime_value(control, value))

    if not logical:
        # One admission path for live drags, scroll, config reload and repair: a framed mode's declared pan
        # envelope. View transform keys stay spec-owned, and the outer card never moves.
        from core.settings.visualizer_mode_registry import SCENE_PAN_ENVELOPE_DESCRIPTORS
        for descriptor in SCENE_PAN_ENVELOPE_DESCRIPTORS:
            transform = descriptor.scene_transform_settings
            if not any(key in kwargs for key in transform):
                continue
            from widgets.spotify_visualizer.view_orbit import bounded_scene_pan
            scale_key, pan_x_key, pan_y_key = transform
            scale = float(getattr(host, f"_{scale_key}", _visualizer_default(scale_key)))
            x, y = bounded_scene_pan(descriptor.scene_pan_envelope, scale,
                                     float(getattr(host, f"_{pan_x_key}", _visualizer_default(pan_x_key))),
                                     float(getattr(host, f"_{pan_y_key}", _visualizer_default(pan_y_key))))
            setattr(host, f"_{pan_x_key}", x)
            setattr(host, f"_{pan_y_key}", y)

        from core.settings.framed_camera import FRAMED_CAMERA_SPECS, admit_camera_parameters
        for spec in FRAMED_CAMERA_SPECS():
            if any(key in kwargs for key in spec.input_keys):
                camera = {key: getattr(host, f'_{key}', _visualizer_default(key)) for key in spec.input_keys}
                setattr(host, '_' + spec.key('camera_position'), admit_camera_parameters(spec, camera))


def spec_mode_parameters(owner: Any, mode_id: str) -> Dict[str, object]:
    """A spec'd mode's renderer parameters: every presentation control, under its own key
    (colours as tuples)."""
    from core.settings.visualizer_mode_settings import require_mode_settings

    values: Dict[str, object] = {}
    for key, attr in require_mode_settings(mode_id).presentation_runtime_attrs:
        value = getattr(owner, attr)
        values[key] = tuple(value) if isinstance(value, list) else value
    return values


def presentation_setting_range(key: str) -> tuple[float, float]:
    """The canonical (low, high) of a ranged presentation-only setting (for live orbiting)."""
    from core.settings.visualizer_mode_settings import Slider, spec_control

    control = spec_control(key)
    if isinstance(control, Slider):
        return control.low, control.high
    raise KeyError(f"no ranged presentation setting {key!r}")


def shockwave_grid_parameters(widget: Any, now_ts: float | None = None) -> Dict[str, object]:
    """Shockwave Grid's renderer-only parameters from the presentation owner, with any
    held-key view orbit evaluated at the capture's ``now_ts``."""
    pres = _presentation_source(widget)
    values = spec_mode_parameters(pres, "shockwave_grid")
    values["shockwave_grid_terrain"] = pres._shockwave_grid_terrain
    values["shockwave_grid_terrain_shaper"] = pres._shockwave_grid_terrain_shaper
    values["scene3d_detail"] = str(pres._scene3d_detail)
    if now_ts is not None:
        from widgets.spotify_visualizer.view_orbit import apply_view_orbit_motion

        values = apply_view_orbit_motion(pres, "shockwave_grid", values, now_ts)
    return values


def extruded_bubble_parameters(widget: Any, now_ts: float | None = None) -> Dict[str, object]:
    """Extruded Bubble's parameters from the presentation owner, with the live orbit or Auto Rotate swivel
    evaluated at the capture's ``now_ts``."""
    pres = _presentation_source(widget)
    values = spec_mode_parameters(pres, "extruded_bubble")
    values["scene3d_detail"] = str(pres._scene3d_detail)
    if now_ts is not None:
        from widgets.spotify_visualizer.view_orbit import apply_view_orbit_motion

        values = apply_view_orbit_motion(pres, "extruded_bubble", values, now_ts)
    return values


def extruded_spectrum_parameters(widget: Any, now_ts: float | None = None) -> Dict[str, object]:
    """Extruded Spectrum's renderer-only parameters from the presentation owner, with any
    held-key view orbit evaluated at the capture's ``now_ts``."""
    pres = _presentation_source(widget)
    values = spec_mode_parameters(pres, "extruded_spectrum")
    values["scene3d_detail"] = str(pres._scene3d_detail)
    values["backdrop"] = getattr(pres, "_backdrop", None)    # the reflected wallpaper, when it reflects
    values["backdrop_blend_s"] = getattr(pres, "_backdrop_blend_s", None)
    if now_ts is not None:
        from widgets.spotify_visualizer.view_orbit import apply_view_orbit_motion

        values = apply_view_orbit_motion(pres, "extruded_spectrum", values, now_ts)
    return values


def _populate_shared_visualizer_extras(extra: Dict[str, Any], widget: Any) -> None:
    """Copy the already-resolved cross-mode logical/presentation contract."""
    pres = _presentation_source(widget)
    extra['rainbow_enabled'] = pres._rainbow_enabled
    extra['rainbow_speed'] = pres._rainbow_speed
    extra['rainbow_per_bar'] = pres._rainbow_per_bar
    extra['spectrum_rainbow_fill'] = pres._spectrum_rainbow_fill
    extra['spectrum_rainbow_border'] = pres._spectrum_rainbow_border
    extra['spectrum_rainbow_ghost'] = pres._spectrum_rainbow_ghost
    extra['spectrum_glow_enabled'] = pres._spectrum_glow_enabled
    extra['spectrum_glow_intensity'] = pres._spectrum_glow_intensity
    extra['spectrum_glow_color'] = pres._spectrum_glow_color
    extra['spectrum_ghosting_enabled'] = widget._spectrum_ghosting_enabled
    extra['spectrum_ghost_alpha'] = pres._spectrum_ghost_alpha
    extra['spectrum_ghost_decay'] = widget._spectrum_ghost_decay
    extra['bubble_ghosting_enabled'] = pres._bubble_ghosting_enabled
    extra['bubble_ghost_alpha'] = pres._bubble_ghost_alpha
    extra['bubble_ghost_decay'] = pres._bubble_ghost_decay

