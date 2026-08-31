"""Family size-payload projection for retained Quick CUSTOM sessions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QRect, QSize

from rendering.custom_layout_contract import CUSTOM_LAYOUT_MIN_WIDGET_SIZE
from rendering.custom_layout_session import CustomLayoutSessionItem
from rendering.widget_descriptors import WidgetRuntimeDescriptor


# H9: resize modes that obey the single uniform retained-presentation scale
# (``OverlayWidget.uniformScaleTransform``). Their CUSTOM resize is purely
# geometric - the QML derives one whole-widget scale from the outer-rect /
# baseline-preferred ratio - so they carry NO per-value size payload. Font and
# other authored sizes stay Settings-owned; nothing Settings-like is mutated or
# persisted by a temporary CUSTOM resize. Families that still project a handful
# of family values (clock/weather/steam) remain on their existing payload path;
# Gmail joins Reddit/Media because fixed header/row minima must scale with the
# whole retained card rather than diverge from the outer geometry.
CUSTOM_LAYOUT_MIN_RESIZE_SCALE = 0.40
CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY = "_custom_resize_scale"
_PAYLOAD_MINIMUMS: dict[str, int] = {
    "font_size": 8,
    "icon_size": 12,
    "detail_icon_size": 8,
    "artwork_size": 48,
    "square_artwork_size": 48,
    "capsule_font_size": 8,
}


UNIFORM_TRANSFORM_RESIZE_MODES: frozenset[str] = frozenset(
    {"reddit_font", "media_scale", "gmail_font"}
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
    if mode == "weather_scale":
        return {
            "font_size": int(getattr(config, "font_size", 18)),
            "icon_size": int(getattr(config, "icon_size", 32)),
            "detail_icon_size": int(getattr(config, "detail_icon_size", 16)),
        }
    if mode == "steam_card_scale":
        payload = {"font_size": int(getattr(config, "font_size", 14))}
        if hasattr(config, "square_artwork_size"):
            payload.update(
                square_artwork_size=int(config.square_artwork_size),
                capsule_font_size=int(config.capsule_font_size),
            )
        if hasattr(config, "artwork_size"):
            payload["artwork_size"] = int(config.artwork_size)
        return payload
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


__all__ = [
    "CUSTOM_LAYOUT_MIN_RESIZE_SCALE",
    "CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY",
    "UNIFORM_TRANSFORM_RESIZE_MODES",
    "capture_quick_size_payload",
    "is_uniform_transform_resize_mode",
    "quick_custom_minimum_size",
    "quick_custom_payload_minimum_scale",
    "scale_quick_size_payload",
]
