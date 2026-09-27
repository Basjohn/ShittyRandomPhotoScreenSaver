"""Where the saver places authored (non-CUSTOM) widgets on one display.

Settings Arrange draws uncommitted widgets through this module so the canvas
shows the saver's own placement, not an approximation. It composes exactly the
pure functions the runtime uses, with the runtime's inputs:

- anchor, margin and clamp: :func:`resolve_overlay_geometry_policy` (the
  display presenter's per-widget policy);
- display-wide spill and whole-card shrink: :func:`build_display_auto_scale_plan`
  with the presenter's participants (anchor token, rounded base rectangle,
  build order, margin) and eligibility (uniform-transform resize modes);
- Media + Visualizer: :func:`resolve_visualizer_media_origin` from Media's
  unstacked rectangle, both reserved as obstacles with Media held fixed, or the
  Visualizer on Media's plain slot, as ``DisplayManager`` does.

Global CUSTOM (any effective ``Custom`` route) keeps stacking and adjacency
dormant, as the Spec requires: widgets sit on their plain anchors and an
uncommitted Visualizer on Media's plain slot. Coordinates are display-local.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.settings.default_contract import require_canonical_default
from rendering.quick.custom_layout_size import is_uniform_transform_resize_mode
from rendering.visualizer_media_adjacency import resolve_visualizer_media_origin
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

VISUALIZER_ID = "spotify_visualizer"
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
        vis_width = max(1.0, min(float(visualizer_size[0]), float(width)))
        vis_height = max(1.0, min(float(visualizer_size[1]), float(height)))
        media = base.get("media")
        if authored_enabled and media is not None:
            vis_x, vis_y, _overfull = resolve_visualizer_media_origin(
                (media.x, media.y, media.width, media.height),
                (vis_width, vis_height),
                (float(width), float(height)),
            )
        else:
            # Media disabled, or global CUSTOM: Media's plain authored slot.
            plain = resolve_overlay_geometry_policy("media", widgets_config).resolve(
                (vis_width, vis_height), bounds
            )
            vis_x, vis_y = plain.x, plain.y
        # The Visualizer presentation keeps its whole card on the display.
        vis_x = min(max(0.0, vis_x), max(0.0, width - vis_width))
        vis_y = min(max(0.0, vis_y), max(0.0, height - vis_height))
        placements[VISUALIZER_ID] = ProjectedPlacement(vis_x, vis_y, vis_width, vis_height)
        if authored_enabled:
            visualizer_obstacle = DisplayStackObstacle(
                key=VISUALIZER_ID,
                x=int(round(vis_x)),
                y=int(round(vis_y)),
                width=max(1, int(round(vis_width))),
                height=max(1, int(round(vis_height))),
            )
            if media is None:
                obstacles = (visualizer_obstacle,)
            else:
                obstacles = (
                    DisplayStackObstacle(
                        key="media",
                        x=int(round(media.x)),
                        y=int(round(media.y)),
                        width=max(1, int(round(media.width))),
                        height=max(1, int(round(media.height))),
                    ),
                    visualizer_obstacle,
                )
                fixed = frozenset({"media"})

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
