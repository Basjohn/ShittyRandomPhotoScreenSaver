"""Family size-payload projection for retained Quick CUSTOM sessions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QRect, QSize

from rendering.custom_layout_contract import CUSTOM_LAYOUT_MIN_WIDGET_SIZE
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


def settings_content_extent_edges(
    item: CustomLayoutSessionItem,
    descriptor: WidgetRuntimeDescriptor,
) -> tuple[str, ...]:
    """Return the side handles Settings may offer without live QML measurement.

    Settings cannot measure retained content, so a side resize there is admitted
    only when every input Runtime Edit would use is already persisted: a saved
    logical box that a Runtime Edit established (never a content-sized estimate,
    whose untouched axis would be baked in from a guess), a floor fully declared
    by the family descriptor (not the live authored-size floor) and no customized
    children (their room requirement is reported only by the live family).
    """

    if (
        not item.resize_capable
        or item.viewport_resize_capable
        or item.content_sized
        or item.current_content_extent is None
        or descriptor.content_extent_floor_at_authored_size
        or item.current_child_sizes
    ):
        return ()
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
    "capture_quick_size_payload",
    "content_extent_resize_payload",
    "edge_resize_rect",
    "is_uniform_transform_resize_mode",
    "quick_custom_content_extent_minimum_size",
    "quick_custom_minimum_size",
    "quick_custom_payload_minimum_scale",
    "scale_quick_size_payload",
    "settings_content_extent_edges",
]
