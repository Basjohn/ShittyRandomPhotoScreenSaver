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


__all__ = [
    "CUSTOM_LAYOUT_MIN_RESIZE_SCALE",
    "CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY",
    "UNIFORM_TRANSFORM_RESIZE_MODES",
    "capture_quick_size_payload",
    "is_uniform_transform_resize_mode",
    "quick_custom_content_extent_minimum_size",
    "quick_custom_minimum_size",
    "quick_custom_payload_minimum_scale",
    "scale_quick_size_payload",
]
