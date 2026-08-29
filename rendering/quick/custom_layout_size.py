"""Family size-payload projection for retained Quick CUSTOM sessions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QRect, QSize

from rendering.custom_layout_contract import CUSTOM_LAYOUT_MIN_WIDGET_SIZE
from rendering.custom_layout_session import CustomLayoutSessionItem
from rendering.widget_descriptors import WidgetRuntimeDescriptor


def capture_quick_size_payload(
    descriptor: WidgetRuntimeDescriptor,
    presentation: Any,
    rect: QRect,
) -> dict[str, Any]:
    config = getattr(getattr(presentation, "model", None), "config", None)
    mode = descriptor.custom_layout_resize_mode
    if mode == "clock_font":
        return {"font_size": int(getattr(config, "font_size", 48))}
    if mode == "weather_scale":
        return {
            "font_size": int(getattr(config, "font_size", 18)),
            "icon_size": int(getattr(config, "icon_size", 32)),
            "detail_icon_size": int(getattr(config, "detail_icon_size", 16)),
        }
    if mode == "media_scale":
        return {
            "font_size": int(getattr(config, "font_size", 14)),
            "artwork_size": int(getattr(config, "artwork_size", 80)),
        }
    if mode in {"reddit_font", "gmail_font"}:
        return {"font_size": int(getattr(config, "font_size", 14))}
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
    minimums = {
        "font_size": 8,
        "icon_size": 12,
        "detail_icon_size": 8,
        "artwork_size": 48,
        "square_artwork_size": 48,
        "capsule_font_size": 8,
    }
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
        key: max(minimums.get(key, 1), int(round(float(value) * scale)))
        for key, value in baseline.items()
        if isinstance(value, (int, float))
    }


def quick_custom_minimum_size(item: CustomLayoutSessionItem) -> QSize:
    if item.model_identity == "spotify_visualizer":
        return QSize(48, 32)
    return QSize(CUSTOM_LAYOUT_MIN_WIDGET_SIZE)


__all__ = [
    "capture_quick_size_payload",
    "quick_custom_minimum_size",
    "scale_quick_size_payload",
]
