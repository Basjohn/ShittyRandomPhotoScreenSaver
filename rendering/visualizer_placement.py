"""The Visualizer's authored (non-CUSTOM) placement, one function for saver and Arrange.

Media docking is a declared placement policy in the layout descriptor
vocabulary: ``WidgetRuntimeDescriptor.docked_to`` is ``"media"`` or ``"none"``.
The effective policy is the declared one while authored placement applies and
``"none"`` under global CUSTOM (or while live Edit holds authored layout off):

- ``docked_to == "media"`` with a Media rectangle: the Visualizer sits beside
  Media (:func:`resolve_visualizer_media_origin`), moves when Media moves, and
  Media plus the Visualizer are reserved as stacking obstacles with Media fixed;
- otherwise: the Visualizer sits on Media's plain authored slot (Media's
  position/monitor route, no Media-relative displacement) and moving Media's
  card leaves it in place.

``VisualizerHostBinding`` (the saver) and ``project_authored_display_layout``
(Settings Arrange) both resolve through :func:`resolve_visualizer_authored_placement`,
so the canvas shows the Visualizer exactly where the saver puts it.
Coordinates are display-local. No Qt object, timer or settings write.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rendering.visualizer_media_adjacency import resolve_visualizer_media_origin
from rendering.widget_descriptors import (
    get_widget_runtime_descriptor,
    is_global_custom_layout_mode_selected,
)

VISUALIZER_ID = "spotify_visualizer"
DOCKED_TO_MEDIA = "media"
DOCKED_TO_NONE = "none"
DOCKING_TARGETS = frozenset({DOCKED_TO_MEDIA, DOCKED_TO_NONE})


def declared_visualizer_docked_to() -> str:
    """The Visualizer descriptor's declared docking target."""

    descriptor = get_widget_runtime_descriptor(VISUALIZER_ID)
    declared = getattr(descriptor, "docked_to", DOCKED_TO_NONE) if descriptor is not None else DOCKED_TO_NONE
    if declared not in DOCKING_TARGETS:
        raise ValueError(f"unknown Visualizer docking target: {declared!r}")
    return declared


def resolve_visualizer_docked_to(
    widgets_config: Mapping[str, object],
    *,
    authored_layout_enabled: bool = True,
) -> str:
    """The effective docking policy: declared while authored placement applies, else none."""

    if not authored_layout_enabled or is_global_custom_layout_mode_selected(widgets_config):
        return DOCKED_TO_NONE
    return declared_visualizer_docked_to()


@dataclass(frozen=True)
class VisualizerAuthoredPlacement:
    """One resolved authored Visualizer rectangle (display-local) and its policy."""

    x: float
    y: float
    width: float
    height: float
    # Authored placement applies (not global CUSTOM, not held off by live Edit).
    authored: bool
    docked_to: str
    # Media's display-local rectangle when docked beside a presented Media card.
    media_rect: tuple[float, float, float, float] | None = None
    overfull: bool = False

    def stack_obstacles(self):
        """The authored stacking reservation: ``(obstacles, fixed_widget_ids)``.

        The Visualizer always occupies its box; a docked Media card is reserved
        too and held fixed. Global CUSTOM reserves nothing (stacking is off).
        """

        from rendering.widget_stacking import DisplayStackObstacle

        if not self.authored:
            return (), ()
        visualizer = DisplayStackObstacle(
            key=VISUALIZER_ID,
            x=int(round(self.x)),
            y=int(round(self.y)),
            width=max(1, int(round(self.width))),
            height=max(1, int(round(self.height))),
        )
        if self.media_rect is None:
            return (visualizer,), ()
        media_x, media_y, media_width, media_height = self.media_rect
        media = DisplayStackObstacle(
            key="media",
            x=int(round(media_x)),
            y=int(round(media_y)),
            width=max(1, int(round(media_width))),
            height=max(1, int(round(media_height))),
        )
        return (media, visualizer), ("media",)


def resolve_visualizer_authored_placement(
    widgets_config: Mapping[str, object],
    *,
    display_size: Sequence[float],
    visualizer_size: Sequence[float],
    media_rect: Sequence[float] | None = None,
    authored_layout_enabled: bool = True,
) -> VisualizerAuthoredPlacement:
    """Resolve where the authored Visualizer sits on one display.

    ``media_rect`` is Media's unstacked display-local rectangle when the Media
    card presents there. The Visualizer is reduced to the display and kept whole
    on it.
    """

    from rendering.quick.widgets.geometry_resolver import resolve_overlay_geometry_policy
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    width, height = float(display_size[0]), float(display_size[1])
    vis_width = max(1.0, min(float(visualizer_size[0]), width))
    vis_height = max(1.0, min(float(visualizer_size[1]), height))
    authored = bool(authored_layout_enabled) and not is_global_custom_layout_mode_selected(
        widgets_config
    )
    docked_to = declared_visualizer_docked_to() if authored else DOCKED_TO_NONE
    docked_media = None
    overfull = False
    if docked_to == DOCKED_TO_MEDIA and media_rect is not None:
        docked_media = tuple(float(value) for value in media_rect)
        x, y, overfull = resolve_visualizer_media_origin(
            docked_media, (vis_width, vis_height), (width, height)
        )
    else:
        # Undocked, or Media's card is not presented: Media's plain authored slot.
        plain = resolve_overlay_geometry_policy("media", widgets_config).resolve(
            (vis_width, vis_height), OverlayWidgetGeometry(0.0, 0.0, width, height)
        )
        x, y = float(plain.x), float(plain.y)
    # The Visualizer presentation keeps its whole card on the display.
    x = min(max(0.0, x), max(0.0, width - vis_width))
    y = min(max(0.0, y), max(0.0, height - vis_height))
    return VisualizerAuthoredPlacement(
        x=x,
        y=y,
        width=vis_width,
        height=vis_height,
        authored=authored,
        docked_to=docked_to,
        media_rect=docked_media,
        overfull=overfull,
    )


def resolve_authored_visualizer_outer_size(display_size: Sequence[float]) -> tuple[float, float]:
    """The outer box of an uncommitted authored Visualizer when no owner is live.

    Settings Arrange uses it where the saver asks its live owner
    (``resolved_outer_size``): the canonical viewport at scale 1 reduced
    uniformly to fit the display. The mode policy and card chrome shape only the
    inside, so neutral values stand in for them.
    """

    from core.settings.visualizer_mode_registry import (
        get_default_visualizer_mode_id,
        get_visualizer_presentation_policy,
    )
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(get_default_visualizer_mode_id()),
        display_size=(display_size[0], display_size[1]),
        border_width=0.0, corner_radius=0.0, content_inset=0.0,
        background_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0),
        shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
        shadow_offset=(0.0, 0.0), shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0),
    )
    return float(presentation.outer_rect[2]), float(presentation.outer_rect[3])


__all__ = [
    "DOCKED_TO_MEDIA",
    "DOCKED_TO_NONE",
    "DOCKING_TARGETS",
    "VISUALIZER_ID",
    "VisualizerAuthoredPlacement",
    "declared_visualizer_docked_to",
    "resolve_authored_visualizer_outer_size",
    "resolve_visualizer_authored_placement",
    "resolve_visualizer_docked_to",
]
