"""Read-only CUSTOM Edit framing for freeform Visualizer scenes.

The persisted CUSTOM rectangle remains the stage. Extruded's primary frame uses
the accepted immutable bars and production projection, sampled only at Edit
edges; its conservative render-target reach is not a selectable content bound.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from typing import Any

from widgets.spotify_visualizer.render_state import ResolvedVisualizerPresentation


_ENVELOPE_PARAMETER_KEYS = {
    "extruded_spectrum": (
        "extruded_spectrum_depth", "extruded_spectrum_turn", "extruded_spectrum_tilt",
        "extruded_spectrum_reflection", "extruded_spectrum_allow_overflow",
        "extruded_spectrum_shadow_enabled", "extruded_spectrum_shadow_strength",
        "extruded_spectrum_shadow_reach",
        "extruded_spectrum_colouring",
        "spectrum_ghosting_enabled", "spectrum_ghost_alpha",
    ),
    "shockwave_grid": (
        "shockwave_grid_turn", "shockwave_grid_tilt", "shockwave_grid_horizon",
        "shockwave_grid_wave_height", "shockwave_grid_idle",
    ),
    "sphere": (
        "sphere_fragment_strength", "sphere_particle_distance", "sphere_perspective_strength",
        "sphere_turn", "sphere_tilt", "sphere_shadow_enabled",
        "sphere_shadow_softness", "sphere_shadow_size", "sphere_shadow_distance",
    ),
}


def edit_content_envelope_parameters(
    mode_id: str, parameters: Mapping[str, object], *, bar_count: int,
) -> dict[str, object]:
    """Select only authored reach inputs from a renderer's frozen parameter map.

    This is an invalidation/input filter, not another projection authority.
    Dynamic audio/style metadata and reflected wallpaper pixels cannot cause
    envelope work or remain retained by its transient comparison record.
    """
    keys = _ENVELOPE_PARAMETER_KEYS.get(str(mode_id), ())
    selected = {key: parameters[key] for key in keys}
    if mode_id == "extruded_spectrum":
        selected["bar_count"] = int(bar_count)
    return selected


def _local_content_rect(
    presentation: ResolvedVisualizerPresentation,
) -> tuple[float, float, float, float]:
    outer_x, outer_y, _outer_width, _outer_height = presentation.outer_rect
    content_x, content_y, content_width, content_height = presentation.content_rect
    return (
        float(content_x - outer_x),
        float(content_y - outer_y),
        float(content_width),
        float(content_height),
    )


def _record(
    mode_id: str,
    reach: tuple[float, float, float, float],
    pivot: tuple[float, float],
    *,
    cage_points: tuple[tuple[float, float], ...] = (),
    north_face: tuple[float, float, float] | None = None,
) -> dict[str, object] | None:
    left, top, right, bottom = (float(value) for value in reach)
    pivot_x, pivot_y = (float(value) for value in pivot)
    values = [left, top, right, bottom, pivot_x, pivot_y]
    values.extend(component for point in cage_points for component in point)
    if north_face is not None:
        values.extend((float(north_face[0]), float(north_face[1]), float(north_face[2])))
    if not all(math.isfinite(value) for value in values):
        return None
    if right <= left or bottom <= top:
        return None
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

    record: dict[str, object] = {
        "admitted": True,
        "orbit_admitted": bool(get_visualizer_mode_descriptor(mode_id).view_orbit_settings),
        "mode": str(mode_id),
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "pivot_x": pivot_x,
        "pivot_y": pivot_y,
    }
    if len(cage_points) == 8:
        record["cage_points"] = tuple(
            {"x": float(x), "y": float(y)} for x, y in cage_points
        )
        if north_face is not None:
            record["north_x"] = float(north_face[0])
            record["north_y"] = float(north_face[1])
            record["north_angle"] = float(north_face[2])
    return record


def _north_face_pose(points: tuple[tuple[float, float], ...]) -> tuple[float, float, float]:
    """Project a direction marker onto the world -Z face, aligned to its 4→5 edge.

    Position and angle derive exclusively from the *same eight cage vertices*;
    there is no separately authored compass, camera or renderer. The cage uses
    world -Z as North consistently for every 3D mode, even when viewed edge-on.
    """
    x = sum(points[index][0] for index in (4, 5, 6, 7)) / 4.0
    y = sum(points[index][1] for index in (4, 5, 6, 7)) / 4.0
    dx = points[5][0] - points[4][0]
    dy = points[5][1] - points[4][1]
    # Degenerate screen-space edges provide no reliable tangent: do not invent
    # an unrelated angle merely because a user has turned the stage edge-on.
    degrees = math.degrees(math.atan2(dy, dx)) if math.hypot(dx, dy) > 1e-6 else 0.0
    return (x, y, degrees)


def _extruded_envelope(
    presentation: ResolvedVisualizerPresentation,
    parameters: Mapping[str, object],
    logical,
) -> dict[str, object] | None:
    # Import only after the active mode has admitted Edit chrome.  Merely
    # registering an inactive 3D mode must not pull in its renderer stack.
    from rendering.gl_programs.extruded_spectrum_program import (
        EXTRUDED_CEILING,
        EXTRUDED_MAX_DEPTH,
        EXTRUDED_MAX_TILT,
        EXTRUDED_MAX_TURN,
        EXTRUDED_PIVOT,
        extruded_fit,
        extruded_project,
        extruded_footprint,
    )
    from rendering.quick.visualizer.implementations.spectrum import (
        compute_quick_spectrum_layout,
        prepare_spectrum_shader_levels,
    )

    if logical is not None and logical.mode_id != "extruded_spectrum":
        return None

    local_content = _local_content_rect(presentation)
    # Match QuickExtrudedSpectrumRenderer's bounded draw admission exactly.
    count = min(64, int(logical.common.bar_count if logical is not None
                        else parameters.get("bar_count", 32)))
    if count <= 0:
        return None
    layout = compute_quick_spectrum_layout(
        local_content_rect=local_content,
        viewport_extent=presentation.logical_viewport_extent,
        visual_scale=presentation.uniform_visual_scale,
        bar_count=count,
    )
    content_x, content_y, content_width, content_height = layout.content_rect
    margin_y = 6.0 * presentation.uniform_visual_scale
    field = (content_x, content_y + margin_y, content_width, content_height - 2.0 * margin_y)
    if field[3] <= 0.0:
        return None
    centre = layout.bars_left + 0.5 * layout.bar_span
    depth = min(
        EXTRUDED_MAX_DEPTH,
        layout.bar_width / field[3] * float(parameters["extruded_spectrum_depth"]),
    )
    tilt = EXTRUDED_MAX_TILT * float(parameters["extruded_spectrum_tilt"])
    turn = EXTRUDED_MAX_TURN * float(parameters["extruded_spectrum_turn"])
    reflection = float(parameters["extruded_spectrum_reflection"])
    overflow = bool(parameters["extruded_spectrum_allow_overflow"])
    shadow_vector = (0.0, 0.0)
    if (bool(parameters["extruded_spectrum_shadow_enabled"])
            and float(parameters["extruded_spectrum_shadow_strength"]) > 0.0):
        shadow_color = presentation.shell_style["shadow_color"]
        if len(shadow_color) < 4 or float(shadow_color[3]) > 0.0:
            from rendering.quick.scene3d.shadows import directional_shadow_vector, extruded_shadow_length

            shadow_vector = directional_shadow_vector(
                presentation.shell_style['shadow_offset'],
                extruded_shadow_length(str(parameters['extruded_spectrum_shadow_reach'])))
    fit = extruded_fit(
        0.5 * layout.bar_span / field[3], depth, tilt, reflection,
        content_width / field[3], turn, overflow,
    )
    scale, floor = fit
    projected_pivot = extruded_project((0.0, EXTRUDED_PIVOT, 0.0), tilt, turn)
    pivot = (
        centre + projected_pivot[0] * scale * field[3],
        field[1] + field[3] - (floor + projected_pivot[1] * scale) * field[3],
    )
    half_span = 0.5 * layout.bar_span / field[3]
    world = (
        (-half_span, 0.0, 0.0), (half_span, 0.0, 0.0),
        (half_span, EXTRUDED_CEILING, 0.0), (-half_span, EXTRUDED_CEILING, 0.0),
        (-half_span, 0.0, -depth), (half_span, 0.0, -depth),
        (half_span, EXTRUDED_CEILING, -depth), (-half_span, EXTRUDED_CEILING, -depth),
    )
    cage = tuple(
        (centre + projected[0] * scale * field[3],
         field[1] + field[3] - (floor + projected[1] * scale) * field[3])
        for projected in (extruded_project(point, tilt, turn) for point in world)
    )
    if logical is None or presentation.content_fade <= 0.0:
        # The authored stage cage is independent of the audio-dependent visual
        # footprint. Show the true projected guide in an empty/revealing scene,
        # but DO NOT claim a render footprint has been admitted.
        bounds = (
            min(point[0] for point in cage), min(point[1] for point in cage),
            max(point[0] for point in cage), max(point[1] for point in cage),
        )
        guide = _record(
            "extruded_spectrum", bounds, pivot, cage_points=cage,
            north_face=_north_face_pose(cage),
        )
        if guide is not None:
            guide["admitted"] = False
            guide["cage_admitted"] = True
        return guide
    levels, peaks = prepare_spectrum_shader_levels(
        logical.common.bars, logical.mode_state.peaks, bar_count=count,
    )
    # Spectral Edges deliberately has opaque trim even when authored edge alpha
    # is zero. Ghost/reflection/shadow have their own independent shader alpha.
    style = logical.common.style
    surface_visible = (float(style["fill_color"][3]) > 0.0
                       or float(style["border_color"][3]) > 0.0
                       or parameters["extruded_spectrum_colouring"] == "Spectral Edges")
    reach = extruded_footprint(
        field, centre, (layout.bars_left + 0.5 * layout.bar_width - centre) / field[3],
        (layout.bar_width + layout.bar_gap) / field[3], 0.5 * layout.bar_width / field[3],
        depth, tilt, turn, fit, levels[:count], peaks[:count], layout.height_scale,
        body_visible=surface_visible,
        ghost_alpha=(float(parameters["spectrum_ghost_alpha"])
                     if bool(parameters["spectrum_ghosting_enabled"]) else 0.0),
        reflection=reflection, shadow_vector=shadow_vector,
    )
    if reach is None:
        return None
    if not overflow:
        reach = (max(0.0, reach[0]), max(0.0, reach[1]),
                 min(presentation.outer_rect[2], reach[2]), min(presentation.outer_rect[3], reach[3]))

    return _record(
        "extruded_spectrum", reach, pivot, cage_points=cage,
        north_face=_north_face_pose(cage),
    )


def _shockwave_envelope(
    presentation: ResolvedVisualizerPresentation,
    parameters: Mapping[str, object],
) -> dict[str, object] | None:
    from rendering.gl_programs.shockwave_grid_program import (
        SHOCKWAVE_DEPTH,
        SHOCKWAVE_MAX_RIDGE,
        SHOCKWAVE_MAX_TILT,
        SHOCKWAVE_MAX_TURN,
        SHOCKWAVE_MAX_STRENGTH,
        SHOCKWAVE_IDLE_HEIGHT,
        SHOCKWAVE_VISIBLE,
        shockwave_camera,
        shockwave_fit,
        shockwave_half_width,
        shockwave_amplitude,
        shockwave_project,
        shockwave_reach,
    )

    field = _local_content_rect(presentation)
    if field[3] <= 0.0:
        return None
    half_width = shockwave_half_width(field[2] / field[3])
    tilt = SHOCKWAVE_MAX_TILT * float(parameters["shockwave_grid_tilt"])
    turn = SHOCKWAVE_MAX_TURN * float(parameters["shockwave_grid_turn"])
    ridge = SHOCKWAVE_MAX_RIDGE * float(parameters["shockwave_grid_horizon"])
    fit = shockwave_fit(tilt, turn, half_width, ridge)
    scale, base = fit
    projected_pivot = shockwave_project(
        (0.0, 0.0, -0.5 * SHOCKWAVE_DEPTH), tilt, turn,
        shockwave_camera(half_width),
    )
    pivot = (
        field[0] + 0.5 * field[2] + projected_pivot[0] * scale * field[3],
        field[1] + field[3] * (base - projected_pivot[1] * scale),
    )
    wave_height = float(parameters["shockwave_grid_wave_height"])
    idle = float(parameters["shockwave_grid_idle"])
    reach = shockwave_reach(
        field, fit, tilt, turn, half_width, ridge, wave_height, idle,
    )
    amplitude = shockwave_amplitude(wave_height)
    crest = (
        1.25 * amplitude * SHOCKWAVE_MAX_STRENGTH
        + amplitude * SHOCKWAVE_IDLE_HEIGHT * max(0.0, idle)
    )
    reach_x = min(1.0, 1.05 * SHOCKWAVE_VISIBLE) * half_width
    reach_z = min(1.0, 1.05 * SHOCKWAVE_VISIBLE) * SHOCKWAVE_DEPTH
    low_y = -0.5 * crest
    high_y = max(crest, 1.05 * ridge)
    camera = shockwave_camera(half_width)
    world = (
        (-reach_x, low_y, 0.0), (reach_x, low_y, 0.0),
        (reach_x, high_y, 0.0), (-reach_x, high_y, 0.0),
        (-reach_x, low_y, -reach_z), (reach_x, low_y, -reach_z),
        (reach_x, high_y, -reach_z), (-reach_x, high_y, -reach_z),
    )
    cage = tuple(
        (field[0] + 0.5 * field[2] + projected[0] * scale * field[3],
         field[1] + field[3] * (base - projected[1] * scale))
        for projected in (shockwave_project(point, tilt, turn, camera) for point in world)
    )
    return _record(
        "shockwave_grid", reach, pivot, cage_points=cage,
        north_face=_north_face_pose(cage),
    )


def _sphere_envelope(
    presentation: ResolvedVisualizerPresentation,
    parameters: Mapping[str, object],
) -> dict[str, object] | None:
    from rendering.quick.visualizer.implementations.sphere_voxel import (
        sphere_pixel_geometry,
        sphere_reach,
    )

    centre_x, centre_y, radius = sphere_pixel_geometry(presentation)
    from rendering.gl_programs.scene3d import scene3d_sphere_item_position
    perspective = max(0.0, min(1.0, float(parameters.get("sphere_perspective_strength", 1.0))))
    view = (float(parameters.get("sphere_turn", 0.0)) * math.pi,
            float(parameters.get("sphere_tilt", 0.0)) * math.pi / 2.0)
    extent = 1.22

    def project(point: tuple[float, float, float]) -> tuple[float, float]:
        return scene3d_sphere_item_position(point, (centre_x, centre_y, radius),
                                             perspective, view=view)

    world = (
        (-extent, -extent, extent), (extent, -extent, extent),
        (extent, extent, extent), (-extent, extent, extent),
        (-extent, -extent, -extent), (extent, -extent, -extent),
        (extent, extent, -extent), (-extent, extent, -extent),
    )
    cage = tuple(project(point) for point in world)
    return _record(
        "sphere", sphere_reach(presentation, parameters), (centre_x, centre_y),
        cage_points=cage, north_face=_north_face_pose(cage),
    )


def resolve_edit_content_envelope(
    mode_id: str,
    presentation: ResolvedVisualizerPresentation,
    parameters: Mapping[str, object],
    *, logical=None,
) -> dict[str, object] | None:
    """Return an item-local read-only framing record for one active 3D mode.

    Extruded requires an accepted immutable logical frame. Missing or silent
    source is unadmitted, never substituted with a maximum-height fake item.
    """

    if not isinstance(presentation, ResolvedVisualizerPresentation):
        raise TypeError("Edit content envelope needs a resolved presentation")
    if not isinstance(parameters, Mapping):
        raise TypeError("Edit content envelope parameters must be a mapping")
    mode = str(mode_id or "").strip()
    if mode == "extruded_spectrum":
        return _extruded_envelope(presentation, parameters, logical)
    if mode == "shockwave_grid":
        return _shockwave_envelope(presentation, parameters)
    if mode == "sphere":
        return _sphere_envelope(presentation, parameters)
    return None


def resolve_owner_edit_content_envelope(
    owner: Any,
    presentation: ResolvedVisualizerPresentation,
    *,
    now: float | None = None,
    logical=None,
) -> dict[str, object] | None:
    """Resolve an Edit edge from authored state and existing accepted input."""

    controller = owner.controller
    mode_id = str(controller.mode_id)
    when = time.time() if now is None else float(now)
    if mode_id == "extruded_spectrum":
        from widgets.spotify_visualizer.config_applier import extruded_spectrum_parameters
        from widgets.spotify_visualizer.view_orbit import view_orbit_values

        # With no admitted audio frame, project only the static stage cage.
        # The live footprint remains unadmitted until an actual render snapshot.
        values = (dict(logical.mode_state.parameters) if logical is not None
                  else {})
        values.update(extruded_spectrum_parameters(controller.presentation_state))
        values.update(view_orbit_values(controller.presentation_state, mode_id, when))
        values["bar_count"] = controller.bar_count
        return resolve_edit_content_envelope(mode_id, presentation, values, logical=logical)
    if mode_id == "shockwave_grid":
        from widgets.spotify_visualizer.config_applier import shockwave_grid_parameters
        from widgets.spotify_visualizer.view_orbit import view_orbit_values

        values = shockwave_grid_parameters(controller.presentation_state)
        values.update(view_orbit_values(controller.presentation_state, mode_id, when))
        return resolve_edit_content_envelope(mode_id, presentation, values)
    if mode_id == 'sphere':
        parameters = getattr(controller.logical_tick_state, '_sphere_parameters', None)
        if not isinstance(parameters, Mapping):
            return None
        from widgets.spotify_visualizer.view_orbit import view_orbit_values
        # Live view is presentation-owned, exactly as in the render capture.
        # The logical parameter cache does not change during pointer orbiting.
        view = view_orbit_values(controller.presentation_state, mode_id, when)
        return resolve_edit_content_envelope(mode_id, presentation, {**dict(parameters), **view})
    return None


__all__ = ["edit_content_envelope_parameters", "resolve_edit_content_envelope", "resolve_owner_edit_content_envelope"]
