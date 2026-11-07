"""Where the saver places authored (non-CUSTOM) widgets on one display.

Settings Arrange draws uncommitted widgets through this module so the canvas
shows the saver's own placement, not an approximation. It composes exactly the
pure functions the runtime uses, with the runtime's inputs:

- anchor, margin and clamp: :func:`resolve_overlay_geometry_policy` (the
  display presenter's per-widget policy);
- display-wide spill and whole-card shrink: :func:`build_display_auto_scale_plan`
  with the presenter's participants (anchor token, rounded base rectangle,
  build order, margin) and eligibility (uniform-transform resize modes);
- Media + Visualizer: :func:`resolve_visualizer_authored_placement`, the one
  function the saver's ``VisualizerHostBinding`` places the Visualizer with
  (Media docking is its declared ``docked_to`` policy): beside Media's unstacked
  rectangle with both reserved and Media held fixed, or on Media's plain slot.

Global CUSTOM (any effective ``Custom`` route) keeps stacking and adjacency
dormant, as the Spec requires: widgets sit on their plain anchors and an
uncommitted Visualizer on Media's plain slot. Coordinates are display-local.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.settings.default_contract import require_canonical_default
from rendering.quick.custom_layout_size import is_uniform_transform_resize_mode
from rendering import visualizer_placement
from rendering.widget_descriptors import (
    get_widget_runtime_descriptor,
    is_global_custom_layout_mode_selected,
)
from rendering.widget_stacking import (
    DisplayStackObstacle,
    DisplayStackParticipant,
    build_display_auto_scale_plan,
)

from .geometry_resolver import resolve_overlay_geometry_policy
from .host import OverlayWidgetGeometry

VISUALIZER_ID = visualizer_placement.VISUALIZER_ID
_STACK_SPACING = 10


@dataclass(frozen=True)
class ProjectedPlacement:
    """One widget's display-local outer rectangle and automatic whole-card scale."""

    x: float
    y: float
    width: float
    height: float
    scale: float = 1.0


def project_authored_display_layout(
    widgets_config: Mapping[str, object],
    *,
    display_size: tuple[int, int],
    ordinary: Sequence[tuple[str, tuple[float, float]]],
    visualizer_size: tuple[float, float] | None = None,
) -> dict[str, ProjectedPlacement]:
    """Resolve the saver's authored placement for one display.

    ``ordinary`` lists the uncommitted ordinary widgets on this display with
    their measured preferred sizes, in the saver's build order (which is its
    stacking order). ``visualizer_size`` is the uncommitted Visualizer's outer
    size when it presents on this display.
    """

    width, height = int(display_size[0]), int(display_size[1])
    bounds = OverlayWidgetGeometry(0.0, 0.0, float(width), float(height))
    authored_enabled = not is_global_custom_layout_mode_selected(widgets_config)
    policies = {
        widget_id: resolve_overlay_geometry_policy(widget_id, widgets_config)
        for widget_id, _size in ordinary
    }
    base = {
        widget_id: policies[widget_id].resolve((float(size[0]), float(size[1])), bounds)
        for widget_id, size in ordinary
    }
    placements = {
        widget_id: ProjectedPlacement(geometry.x, geometry.y, geometry.width, geometry.height)
        for widget_id, geometry in base.items()
    }

    obstacles: tuple[DisplayStackObstacle, ...] = ()
    fixed: frozenset[str] = frozenset()
    if visualizer_size is not None:
        media = base.get("media")
        # The saver's own placement function and docking policy.
        visualizer = visualizer_placement.resolve_visualizer_authored_placement(
            widgets_config,
            display_size=(float(width), float(height)),
            visualizer_size=visualizer_size,
            media_rect=None if media is None else (media.x, media.y, media.width, media.height),
        )
        placements[VISUALIZER_ID] = ProjectedPlacement(
            visualizer.x, visualizer.y, visualizer.width, visualizer.height
        )
        obstacles, fixed_ids = visualizer.stack_obstacles()
        fixed = frozenset(fixed_ids)

    global_section = widgets_config.get("global", {})
    if not isinstance(global_section, Mapping):
        global_section = {}
    stacking_enabled = bool(
        global_section.get(
            "stacking_enabled",
            require_canonical_default("widgets.global.stacking_enabled"),
        )
    )
    if not (authored_enabled and stacking_enabled):
        return placements

    participants = [
        DisplayStackParticipant(
            key=widget_id,
            position_key=policies[widget_id].anchor.value,
            base_x=int(round(base[widget_id].x)),
            base_y=int(round(base[widget_id].y)),
            width=max(1, int(round(base[widget_id].width))),
            height=max(1, int(round(base[widget_id].height))),
            order=order,
            margin=max(0, int(round(float(policies[widget_id].margin)))),
        )
        for order, (widget_id, _size) in enumerate(ordinary)
        if widget_id not in fixed
    ]
    if not participants:
        return placements
    eligible = []
    for participant in participants:
        descriptor = get_widget_runtime_descriptor(participant.key)
        if descriptor is not None and is_uniform_transform_resize_mode(
            descriptor.custom_layout_resize_mode
        ):
            eligible.append(participant.key)
    plan, scales = build_display_auto_scale_plan(
        participants,
        eligible_keys=eligible,
        obstacles=obstacles,
        container_width=width,
        container_height=height,
        spacing=_STACK_SPACING,
    )
    for participant in participants:
        placement = plan.placements.get(participant.key)
        if placement is None:
            continue
        scale = scales[participant.key]
        geometry = base[participant.key]
        placements[participant.key] = ProjectedPlacement(
            float(placement.desired_x),
            float(placement.desired_y),
            geometry.width if scale == 1.0 else float(max(1, round(participant.width * scale))),
            geometry.height if scale == 1.0 else float(max(1, round(participant.height * scale))),
            float(scale),
        )
    return placements


__all__ = ["ProjectedPlacement", "VISUALIZER_ID", "project_authored_display_layout"]
