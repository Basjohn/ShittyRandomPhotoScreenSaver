"""Family size-payload projection for retained Quick CUSTOM sessions."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QRect, QSize

from rendering.custom_layout_contract import (
    CUSTOM_LAYOUT_MIN_WIDGET_SIZE,
    clamp_local_rect_to_bounds,
)
from rendering.custom_layout_session import CustomLayoutSessionItem
from rendering.widget_descriptors import WidgetRuntimeDescriptor
from rendering.widget_stacking import ORDINARY_WIDGET_MIN_RESIZE_SCALE


# Uniform retained transforms are the default for ordinary-widget CUSTOM resize:
# one outer-rect / preferred-baseline scale; authored values remain Settings-owned.
# Clock retains its variant-aware per-value path. Visualizer owns a distinct viewport contract.
CUSTOM_LAYOUT_MIN_RESIZE_SCALE = ORDINARY_WIDGET_MIN_RESIZE_SCALE
CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY = "_custom_resize_scale"
_PAYLOAD_MINIMUMS: dict[str, int] = {
    "font_size": 8,
}


UNIFORM_TRANSFORM_RESIZE_MODES: frozenset[str] = frozenset(
    {"ordinary_uniform", "reddit_font", "media_scale", "gmail_font", "steam_card_scale", "weather_scale"}
)


def is_uniform_transform_resize_mode(mode: object) -> bool:
    """Return whether ``mode`` scales via the single uniform presentation transform."""

    return str(mode or "") in UNIFORM_TRANSFORM_RESIZE_MODES


def capture_quick_size_payload(
    descriptor: WidgetRuntimeDescriptor,
    presentation: Any,
    rect: QRect,
) -> dict[str, Any]:
    config = getattr(getattr(presentation, "model", None), "config", None)
    mode = descriptor.custom_layout_resize_mode
    if is_uniform_transform_resize_mode(mode):
        # Geometry-only: the uniform transform carries the whole scale.
        return {}
    if mode == "clock_font":
        return {"font_size": int(getattr(config, "font_size", 48))}
    if mode == "visualizer_rect":
        return {"width": rect.width(), "height": rect.height()}
    return {}


def scale_quick_size_payload(
    descriptor: WidgetRuntimeDescriptor,
    baseline: Mapping[str, Any],
    scale: float,
) -> dict[str, Any]:
    mode = descriptor.custom_layout_resize_mode
    if is_uniform_transform_resize_mode(mode):
        # The whole-widget scale lives in the geometry (outer rect / baseline
        # preferred), not in any per-value payload; keep the payload geometric.
        return dict(baseline)
    if mode == "visualizer_rect":
        payload = dict(baseline)
        payload["width"] = max(
            48, int(round(float(baseline.get("width", 100)) * scale))
        )
        payload["height"] = max(
            32, int(round(float(baseline.get("height", 80)) * scale))
        )
        return payload
    return {
        key: max(_PAYLOAD_MINIMUMS.get(key, 1), int(round(float(value) * scale)))
        for key, value in baseline.items()
        if isinstance(value, (int, float))
    }


def quick_custom_payload_minimum_scale(
    descriptor: WidgetRuntimeDescriptor,
    baseline: Mapping[str, Any],
) -> float:
    """Return the safe relative floor for legacy per-value resize payloads.

    The shared ordinary-widget floor is 40%, but a legacy family must stop
    earlier when one of its authored values would hit an existing hard minimum.
    Continuing to shrink the shell after that point is exactly how fixed content
    can escape or visually distort. Uniform-transform families do not need this
    because their whole retained presentation scales together.
    """
    mode = descriptor.custom_layout_resize_mode
    if is_uniform_transform_resize_mode(mode) or mode == "visualizer_rect":
        return 0.0
    floor = 0.0
    for key, value in baseline.items():
        minimum = _PAYLOAD_MINIMUMS.get(key)
        if minimum is None or isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if numeric <= 0.0:
            continue
        floor = max(floor, float(minimum) / numeric)
    return max(0.0, floor)


def quick_custom_minimum_size(item: CustomLayoutSessionItem) -> QSize:
    if item.model_identity == "spotify_visualizer":
        return QSize(48, 32)
    return QSize(CUSTOM_LAYOUT_MIN_WIDGET_SIZE)


def quick_custom_content_extent_minimum_size(
    item: CustomLayoutSessionItem,
) -> QSize:
    """Return the physical floor for one direct content-extent gesture.

    ``content_extent_minimum_size`` is the family-authored logical floor.  A
    selected child-edit presentation may additionally report a transient logical
    requirement implied by its *current* customized children.  Direct side and
    two-axis content handles must respect the larger value on each axis so the
    parent cannot be reflowed back through a child that already needs that room.

    The transient requirement is never persisted and never drives a background
    cadence: the retained family re-reports it only while the edit overlay is
    observing that selected parent.  Corner/wheel uniform resize deliberately
    does not consume this floor because it scales the existing logical box as a
    whole rather than changing the box itself.
    """

    authored = item.content_extent_minimum_size
    child = item.child_content_requirement
    if authored is None and child is None:
        return quick_custom_minimum_size(item)

    authored_width, authored_height = authored or (0.0, 0.0)
    child_width, child_height = child or (0.0, 0.0)
    logical_width = max(float(authored_width), float(child_width))
    logical_height = max(float(authored_height), float(child_height))
    scale = max(1.0e-6, float(item.resize_scale))
    generic_floor = quick_custom_minimum_size(item)
    return QSize(
        max(generic_floor.width(), int(round(logical_width * scale))),
        max(generic_floor.height(), int(round(logical_height * scale))),
    )


def edge_resize_rect(
    origin_rect: QRect,
    bounds: QRect,
    minimum: QSize,
    dx: int,
    dy: int,
    *,
    horizontal_edge: str | None = None,
    vertical_edge: str | None = None,
) -> QRect:
    """Move the named edges by a gesture delta while anchoring the opposite ones.

    The delta is measured from gesture start, so grabbing anywhere in a handle
    never jumps. Bounds apply to the moving edge rather than a later generic
    clamp, which keeps the opposite edge (or corner) anchored. Runtime Edit and
    Settings Arrange share this one rule.
    """

    rect = QRect(origin_rect)
    min_width = max(1, int(minimum.width()))
    min_height = max(1, int(minimum.height()))
    if horizontal_edge == "left":
        fixed_right = origin_rect.x() + origin_rect.width()
        left = max(bounds.x(), min(origin_rect.x() + dx, fixed_right - min_width))
        rect.setX(left)
        rect.setWidth(fixed_right - left)
    elif horizontal_edge == "right":
        fixed_left = origin_rect.x()
        right = min(
            bounds.x() + bounds.width(),
            max(fixed_left + min_width, fixed_left + origin_rect.width() + dx),
        )
        rect.setX(fixed_left)
        rect.setWidth(right - fixed_left)
    if vertical_edge == "top":
        fixed_bottom = origin_rect.y() + origin_rect.height()
        top = max(bounds.y(), min(origin_rect.y() + dy, fixed_bottom - min_height))
        rect.setY(top)
        rect.setHeight(fixed_bottom - top)
    elif vertical_edge == "bottom":
        fixed_top = origin_rect.y()
        bottom = min(
            bounds.y() + bounds.height(),
            max(fixed_top + min_height, fixed_top + origin_rect.height() + dy),
        )
        rect.setY(fixed_top)
        rect.setHeight(bottom - fixed_top)
    return rect


def content_extent_resize_payload(
    item: CustomLayoutSessionItem,
    scale: float,
    rect: QRect,
    *,
    change_width: bool,
    change_height: bool,
) -> tuple[dict[str, Any], tuple[float, float]]:
    """Return the size payload and logical box for a content-box side resize.

    The outer rect changes on the dragged axis at constant uniform scale; the
    new logical dimension is ``outer / scale`` and the untouched axis keeps its
    existing logical value exactly.
    """

    scale = max(1.0e-6, float(scale))
    box = item.current_content_extent
    if box is None:
        box = (float(rect.width()) / scale, float(rect.height()) / scale)
    next_box = (
        float(rect.width()) / scale if change_width else float(box[0]),
        float(rect.height()) / scale if change_height else float(box[1]),
    )
    payload = dict(item.current_size_payload)
    payload.update(
        width=rect.width(),
        height=rect.height(),
        content_extent=[next_box[0], next_box[1]],
    )
    return payload, next_box


def viewport_extent_resize_payload(
    item: CustomLayoutSessionItem,
    pixels_per_world: float,
    rect: QRect,
    *,
    change_width: bool,
    change_height: bool,
) -> tuple[dict[str, Any], tuple[float, float]]:
    """Return the size payload and viewport extent for a Visualizer side/corner resize.

    The world extent on a changed axis is ``outer / pixels_per_world``; an
    untouched axis keeps its logical extent exactly, so integer rect rounding
    never nudges it. ``None`` extent means the canonical baseline world.
    """

    from widgets.spotify_visualizer.render_state import (
        CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
    )

    scale = max(1.0e-6, float(pixels_per_world))
    extent = item.current_viewport_extent or (
        float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[0]),
        float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1]),
    )
    # A freeform 3D viewport is an authored *stage*.  Enlarging that stage
    # must enlarge the projected mesh, not expand its virtual world by the
    # same amount (which would cancel the visible resize).  Planar Visualizer
    # side handles retain their existing viewport-world editing semantics.
    if item.geometry_kind == "freeform_3d":
        next_extent = (float(extent[0]), float(extent[1]))
    else:
        next_extent = (
            float(rect.width()) / scale if change_width else float(extent[0]),
            float(rect.height()) / scale if change_height else float(extent[1]),
        )
    payload = dict(item.current_size_payload)
    payload.update(
        width=rect.width(),
        height=rect.height(),
        viewport_extent=[next_extent[0], next_extent[1]],
    )
    return payload, next_extent


@dataclass(frozen=True)
class UniformScaleGeometry:
    """One admitted whole-widget scale: the card's new global rect and absolute scale."""

    rect: QRect
    scale: float


def uniform_wheel_scale(current_scale: float, angle_delta_y: int) -> float:
    """The absolute scale one wheel event asks for: 5% per notch of the current scale."""

    if not angle_delta_y:
        return float(current_scale)
    steps = int(angle_delta_y / 120)
    if steps == 0:
        steps = 1 if angle_delta_y > 0 else -1
    return max(CUSTOM_LAYOUT_MIN_RESIZE_SCALE, float(current_scale) + 0.05 * steps)


def uniform_corner_drag_scale(
    origin_rect: QRect,
    origin_scale: float,
    corner: str,
    dx: float,
    dy: float,
) -> float:
    """The absolute scale a square-corner drag asks for, from its gesture-start state.

    The card grows about its top-centre, so the dragged corner's distance from
    that point sets the scale; ``dx``/``dy`` are measured from gesture start.
    """

    horizontal = -1.0 if str(corner).endswith("left") else 1.0
    vertical = -1.0 if str(corner).startswith("top_") else 1.0
    half_width = max(1.0, origin_rect.width() / 2.0)
    height = max(1.0, float(origin_rect.height()))
    base = max(1.0, math.hypot(half_width, height))
    target = math.hypot(
        max(1.0, half_width + float(dx) * horizontal),
        max(1.0, height + float(dy) * vertical),
    )
    return float(origin_scale) * target / base


def pixels_per_world_from_geometry(
    rect: QRect,
    viewport_extent: tuple[float, float] | None,
    *,
    geometry_kind: str = "planar",
) -> float:
    """Return a usable viewport scale, strictly enforcing planar geometry only.

    3D stage aspect and logical render-world aspect are independent by design.
    The ratio is an interaction aid there, never the stage-size authority.
    """

    if viewport_extent is None:
        raise RuntimeError("CUSTOM visualizer geometry has no viewport extent")
    extent_width = float(viewport_extent[0])
    extent_height = float(viewport_extent[1])
    width = float(rect.width())
    height = float(rect.height())
    if min(extent_width, extent_height, width, height) <= 0.0:
        raise RuntimeError("CUSTOM visualizer geometry must be positive")
    if geometry_kind == "freeform_3d":
        return max(1.0e-6, min(width / extent_width, height / extent_height))
    horizontal = (
        max(0.0, (width - 0.5) / extent_width),
        (width + 0.5) / extent_width,
    )
    vertical = (
        max(0.0, (height - 0.5) / extent_height),
        (height + 0.5) / extent_height,
    )
    lower = max(horizontal[0], vertical[0])
    upper = min(horizontal[1], vertical[1])
    if lower > upper:
        raise RuntimeError(
            "CUSTOM visualizer geometry does not encode one pixels-per-world scale"
        )
    return max(1.0e-6, (lower + upper) * 0.5)


def uniform_scale_geometry(
    item: CustomLayoutSessionItem,
    descriptor: WidgetRuntimeDescriptor | None,
    requested_scale: float,
    anchor_rect: QRect,
    display_geometry: QRect,
    *,
    pixels_per_world: float | None = None,
) -> UniformScaleGeometry | None:
    """Whole-widget uniform scale (wheel, square corner, slider) for both editors.

    Runtime Edit and Settings Arrange share this one rule. The scale is
    absolute: against the current logical content box when a side resize made
    one, against the Visualizer's current world (``pixels_per_world``, required
    when it has a viewport extent), otherwise against the admitted reference
    (baseline rect / baseline scale; ``descriptor`` adds a legacy per-value
    payload floor there). The card keeps ``anchor_rect``'s
    top-centre (or the centre for freeform 3D stages) and is clamped into the display. Returns ``None`` when the
    admitted scale does not change.
    """

    display_size = display_geometry.size()
    minimum = quick_custom_minimum_size(item)
    box = item.current_content_extent
    world = (item.current_viewport_extent if item.viewport_resize_capable
             and item.geometry_kind != "freeform_3d" else None)
    current_scale = max(1.0e-6, float(item.resize_scale))
    if item.content_extent_capable and not item.viewport_resize_capable and box is not None:
        # Scale the user's logical content box as a whole (a side drag may have
        # given it a non-authored aspect); the box itself is unchanged.
        reference_width = max(1.0, float(box[0]))
        reference_height = max(1.0, float(box[1]))
        floor_scale = max(
            CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
            float(minimum.width()) / reference_width,
            float(minimum.height()) / reference_height,
        )
        world = None
    elif item.geometry_kind == "freeform_3d" and item.viewport_resize_capable:
        # Uniform Edit/Arrange scaling multiplies the existing authored stage
        # as one rectangle.  Using viewport_extent here would silently snap its
        # proportions back to the renderer's unrelated virtual-world aspect.
        stage_reference = item.uniform_stage_reference
        # CUSTOM's working QRect is the geometry authority. A direct geometry
        # replacement can bypass the gesture setter (e.g. host rehydration or
        # Settings reconciliation); an obsolete rounding reference may not drag
        # the stage back to an earlier size on the next wheel step.
        if (stage_reference is None or
                abs(float(item.current_global_rect.width()) - stage_reference[0] * current_scale) > 0.501 or
                abs(float(item.current_global_rect.height()) - stage_reference[1] * current_scale) > 0.501):
            stage_reference = (
                float(item.current_global_rect.width()) / current_scale,
                float(item.current_global_rect.height()) / current_scale,
            )
            item.uniform_stage_reference = stage_reference
        reference_width = max(1.0, float(stage_reference[0]))
        reference_height = max(1.0, float(stage_reference[1]))
        floor_scale = max(
            CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
            float(minimum.width()) / reference_width,
            float(minimum.height()) / reference_height,
        )
    else:
        admitted_scale = max(1.0e-6, float(item.baseline_resize_scale))
        reference_width = max(1.0, float(item.baseline_global_rect.width()) / admitted_scale)
        reference_height = max(1.0, float(item.baseline_global_rect.height()) / admitted_scale)
        floor_scale = max(
            CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
            float(minimum.width()) / reference_width,
            float(minimum.height()) / reference_height,
            (admitted_scale * quick_custom_payload_minimum_scale(descriptor, item.baseline_size_payload)
             if descriptor is not None else 0.0),
        )
    max_scale = min(
        float(display_size.width()) / reference_width,
        float(display_size.height()) / reference_height,
    )
    if world is not None:
        if (
            pixels_per_world is None
            or not math.isfinite(float(pixels_per_world))
            or float(pixels_per_world) <= 0.0
        ):
            raise RuntimeError(
                "CUSTOM visualizer uniform scale has no stable pixels-per-world authority"
            )
        current_width = max(1.0, float(world[0]) * float(pixels_per_world))
        current_height = max(1.0, float(world[1]) * float(pixels_per_world))
        max_scale = current_scale * min(
            float(display_size.width()) / current_width,
            float(display_size.height()) / current_height,
        )
        floor_scale = max(
            floor_scale,
            current_scale * max(
                float(minimum.width()) / current_width,
                float(minimum.height()) / current_height,
            ),
        )
    scale = min(max_scale, max(floor_scale, float(requested_scale)))
    if abs(scale - float(item.resize_scale)) < 1.0e-6:
        return None
    if world is not None:
        next_pixels_per_world = float(pixels_per_world) * scale / current_scale
        width = max(1, int(round(float(world[0]) * next_pixels_per_world)))
        height = max(1, int(round(float(world[1]) * next_pixels_per_world)))
    else:
        width = max(1, int(round(reference_width * scale)))
        height = max(1, int(round(reference_height * scale)))
    center_x = float(anchor_rect.x()) + float(anchor_rect.width()) / 2.0
    top_y = (int(round(float(anchor_rect.y()) + (float(anchor_rect.height()) - height) / 2.0))
             if item.geometry_kind == "freeform_3d" else anchor_rect.y())
    local = clamp_local_rect_to_bounds(
        QRect(
            int(round(center_x - width / 2.0)) - display_geometry.x(),
            top_y - display_geometry.y(),
            width,
            height,
        ),
        display_size,
        min_size=minimum,
    )
    return UniformScaleGeometry(
        rect=QRect(
            display_geometry.x() + local.x(),
            display_geometry.y() + local.y(),
            local.width(),
            local.height(),
        ),
        scale=scale,
    )


def settings_side_edges(item: CustomLayoutSessionItem) -> tuple[str, ...]:
    """The width-only / height-only handles an outer-widget editor offers.

    Every axis the item really has: a Visualizer's viewport world (both axes)
    and each declared content-extent axis. Sizes are measured through the
    family's own QML, so a box with no saved extent starts from its real
    preferred size exactly as Runtime Edit's first side drag does. Children are
    never edited here; their saved payload is carried unchanged.
    """

    if not item.resize_capable:
        return ()
    if item.viewport_resize_capable:
        return ("left", "right", "top", "bottom")
    edges: list[str] = []
    if "horizontal" in item.content_extent_axes:
        edges.extend(("left", "right"))
    if "vertical" in item.content_extent_axes:
        edges.extend(("top", "bottom"))
    return tuple(edges)


__all__ = [
    "CUSTOM_LAYOUT_MIN_RESIZE_SCALE",
    "CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY",
    "UNIFORM_TRANSFORM_RESIZE_MODES",
    "UniformScaleGeometry",
    "capture_quick_size_payload",
    "content_extent_resize_payload",
    "edge_resize_rect",
    "is_uniform_transform_resize_mode",
    "pixels_per_world_from_geometry",
    "quick_custom_content_extent_minimum_size",
    "quick_custom_minimum_size",
    "quick_custom_payload_minimum_scale",
    "scale_quick_size_payload",
    "settings_side_edges",
    "uniform_corner_drag_scale",
    "uniform_scale_geometry",
    "uniform_wheel_scale",
    "viewport_extent_resize_payload",
]
