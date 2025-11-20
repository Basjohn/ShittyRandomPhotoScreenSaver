"""Shared helpers for widget drop shadows.

Centralizes configuration for overlay widget shadows (clocks, weather,
media, and future widgets) so behaviour can be tuned in one place.

Shadows are applied via QGraphicsDropShadowEffect where possible, but
will gracefully skip widgets that already use a different graphics
effect (e.g. MediaWidget's opacity effect) to avoid conflicts.
"""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect
from PySide6.QtGui import QColor

from core.logging.logger import get_logger

logger = get_logger(__name__)


def _to_bool(value: Any, default: bool = False) -> bool:
    """Lightweight bool normalisation for local config fields.

    Mirrors SettingsManager.to_bool semantics without introducing a
    hard dependency on core.settings inside this small helper module.
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "on"}:
            return True
        if v in {"false", "0", "no", "off"}:
            return False
        return default
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return bool(value)


def apply_widget_shadow(
    widget: QWidget,
    config: Mapping[str, Any] | None,
    *,
    has_background_frame: bool,
) -> None:
    """Apply or remove a drop shadow on an overlay widget.

    Args:
        widget: Target Qt widget (clock, weather, media, etc.).
        config: ``widgets['shadows']`` settings dictionary.
        has_background_frame: True when the widget is currently drawing
            a solid background/frame (e.g. clock/WeatherWidget
            ``show_background=True``), which uses the stronger
            ``frame_opacity``; otherwise the lighter ``text_opacity``.
    """

    if config is None:
        config = {}

    enabled = _to_bool(config.get("enabled", True), True)

    existing_effect = widget.graphicsEffect()

    if not enabled:
        # Only tear down our own drop-shadow effects; leave other
        # graphics effects (e.g. MediaWidget opacity) untouched.
        if isinstance(existing_effect, QGraphicsDropShadowEffect):
            try:
                widget.setGraphicsEffect(None)
            except Exception:
                logger.debug("[SHADOWS] Failed to clear drop shadow for %r", widget, exc_info=True)
        return

    # If another, non-shadow effect is already attached, we skip shadows
    # entirely rather than overriding important behaviour.
    if existing_effect is not None and not isinstance(existing_effect, QGraphicsDropShadowEffect):
        logger.debug(
            "[SHADOWS] Skipping drop shadow for %r because a non-shadow graphicsEffect is already attached",
            widget,
        )
        return

    # Base colour (usually black) with optional alpha from config.
    color_data = config.get("color", [0, 0, 0, 255])
    try:
        r, g, b = int(color_data[0]), int(color_data[1]), int(color_data[2])
        a = int(color_data[3]) if len(color_data) > 3 else 255
    except Exception:
        r, g, b, a = 0, 0, 0, 255

    # Separate opacities for text-only vs framed widgets.
    text_opacity = float(config.get("text_opacity", 0.3))
    frame_opacity = float(config.get("frame_opacity", 0.7))
    base_opacity = frame_opacity if has_background_frame else text_opacity
    base_opacity = max(0.0, min(1.0, base_opacity))

    color = QColor(r, g, b, int(a * base_opacity))

    # Offset and blur radius (logical pixels).
    offset = config.get("offset", [4, 4])
    try:
        dx, dy = int(offset[0]), int(offset[1])
    except Exception:
        dx, dy = 4, 4

    try:
        blur_radius = int(config.get("blur_radius", 18))
    except Exception:
        blur_radius = 18

    if isinstance(existing_effect, QGraphicsDropShadowEffect):
        effect = existing_effect
    else:
        effect = QGraphicsDropShadowEffect(widget)
        try:
            widget.setGraphicsEffect(effect)
        except Exception:
            logger.debug("[SHADOWS] Failed to attach drop shadow effect for %r", widget, exc_info=True)
            return

    effect.setColor(color)
    effect.setOffset(dx, dy)
    effect.setBlurRadius(blur_radius)
