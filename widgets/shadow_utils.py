"""Shared helpers for widget drop shadows.

Centralizes configuration for overlay widget shadows (clocks, weather,
media, and future widgets) so behaviour can be tuned in one place.

Shadows are applied via QGraphicsDropShadowEffect where possible, but
will gracefully skip widgets that already use a different graphics
effect (e.g. MediaWidget's opacity effect) to avoid conflicts.
"""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect
from PySide6.QtCore import QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor

from core.logging.logger import get_logger

logger = get_logger(__name__)

# Global multiplier to make widget shadows slightly larger/softer by
# increasing their blur radius. This applies both to immediate shadows
# and to the animated shadow fade so visuals stay consistent.
SHADOW_SIZE_MULTIPLIER: float = 1.2


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
    try:
        blur_radius = max(0, int(blur_radius * SHADOW_SIZE_MULTIPLIER))
    except Exception:
        pass

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


class ShadowFadeProfile:
    """Global helper for widget fade-in + shadow application.

    Widgets call :meth:`start_fade_in` when they first become visible.
    The helper installs a temporary opacity effect, animates from 0.0 to
    1.0 with a single shared duration/easing, then removes the effect and
    re-applies the configured drop shadow via :func:`apply_widget_shadow`.

    A pair of attributes, ``_shadowfade_effect`` and ``_shadowfade_anim``,
    are attached to the widget instance to keep the effect and animation
    alive for the duration of the fade.
    """

    # Single global profile for all widgets – not user-configurable for
    # now. Duration and easing should match the existing 1.5s InOutCubic
    # behaviour used by the individual widgets.
    DURATION_MS: int = 1500
    EASING: QEasingCurve.Type = QEasingCurve.InOutCubic

    @classmethod
    def attach_shadow(
        cls,
        widget: QWidget,
        config: Mapping[str, Any] | None,
        *,
        has_background_frame: bool,
    ) -> None:
        """Attach a drop shadow immediately using the shared helper."""

        try:
            apply_widget_shadow(widget, config or {}, has_background_frame=has_background_frame)
        except Exception:
            logger.debug("[SHADOW_FADE] attach_shadow failed for %r", widget, exc_info=True)

    @classmethod
    def _start_shadow_fade(
        cls,
        widget: QWidget,
        config: Mapping[str, Any],
        *,
        has_background_frame: bool,
    ) -> None:
        """Fade in a drop shadow using the shared shadow configuration.

        This helper mirrors :func:`apply_widget_shadow`'s configuration but
        animates the shadow colour alpha from 0 to the configured value so
        shadows appear gradually rather than popping in.
        """

        try:
            enabled = _to_bool(config.get("enabled", True), True)
        except Exception:
            enabled = True

        if not enabled:
            return

        existing_effect = widget.graphicsEffect()
        if isinstance(existing_effect, QGraphicsDropShadowEffect):
            effect = existing_effect
        else:
            effect = QGraphicsDropShadowEffect(widget)
            try:
                widget.setGraphicsEffect(effect)
            except Exception:
                logger.debug(
                    "[SHADOW_FADE] Failed to attach drop shadow effect for %r",
                    widget,
                    exc_info=True,
                )
                return

        color_data = config.get("color", [0, 0, 0, 255])
        try:
            r, g, b = int(color_data[0]), int(color_data[1]), int(color_data[2])
            a = int(color_data[3]) if len(color_data) > 3 else 255
        except Exception:
            r, g, b, a = 0, 0, 0, 255

        text_opacity = float(config.get("text_opacity", 0.3))
        frame_opacity = float(config.get("frame_opacity", 0.7))
        base_opacity = frame_opacity if has_background_frame else text_opacity
        base_opacity = max(0.0, min(1.0, base_opacity))
        target_alpha = int(a * base_opacity)

        offset = config.get("offset", [4, 4])
        try:
            dx, dy = int(offset[0]), int(offset[1])
        except Exception:
            dx, dy = 4, 4

        try:
            blur_radius = int(config.get("blur_radius", 18))
        except Exception:
            blur_radius = 18
        try:
            blur_radius = max(0, int(blur_radius * SHADOW_SIZE_MULTIPLIER))
        except Exception:
            pass

        start_color = QColor(r, g, b, 0)
        effect.setColor(start_color)
        effect.setOffset(dx, dy)
        effect.setBlurRadius(blur_radius)

        anim = QVariantAnimation(widget)
        anim.setDuration(max(0, int(cls.DURATION_MS)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        try:
            anim.setEasingCurve(cls.EASING)
        except Exception:
            pass

        def _on_value_changed(value: float) -> None:
            try:
                t = float(value)
            except Exception:
                t = 1.0
            t = max(0.0, min(1.0, t))
            alpha = int(target_alpha * t)
            color = QColor(r, g, b, alpha)
            try:
                effect.setColor(color)
            except Exception:
                pass

        anim.valueChanged.connect(_on_value_changed)

        def _on_finished() -> None:
            try:
                setattr(widget, "_shadowfade_shadow_anim", None)
            except Exception:
                pass
            try:
                final_color = QColor(r, g, b, target_alpha)
                effect.setColor(final_color)
            except Exception:
                pass

        anim.finished.connect(_on_finished)
        try:
            setattr(widget, "_shadowfade_shadow_anim", anim)
        except Exception:
            pass
        anim.start()

    @classmethod
    def start_fade_in(
        cls,
        widget: QWidget,
        config: Mapping[str, Any] | None,
        *,
        has_background_frame: bool,
    ) -> None:
        """Fade ``widget`` in, then apply the shared drop shadow.

        This helper intentionally does **not** look at any fade-related
        settings; duration and easing are global and fixed so that all
        widgets fade in with identical timing. The only configuration that
        matters here is whether shadows are enabled at all, which is
        handled inside :func:`apply_widget_shadow`.
        """

        cfg = config or {}

        try:
            # Stop any in-flight fade animation created by this helper.
            anim = getattr(widget, "_shadowfade_anim", None)
            if isinstance(anim, QVariantAnimation):
                try:
                    anim.stop()
                except Exception:
                    pass

            effect = getattr(widget, "_shadowfade_effect", None)
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                setattr(widget, "_shadowfade_effect", effect)

            # Start fully transparent so we never briefly flash at full
            # opacity before the fade is visible.
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)

            logger.debug(
                "[SHADOW_FADE] start_fade_in widget=%r duration=%sms easing=%s",
                widget,
                cls.DURATION_MS,
                cls.EASING,
            )

            try:
                widget.show()
            except Exception:
                # Showing may fail during shutdown; in that case we still
                # allow the animation/shadow logic to proceed.
                pass

            anim = QVariantAnimation(widget)
            anim.setDuration(max(0, int(cls.DURATION_MS)))
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            try:
                anim.setEasingCurve(cls.EASING)
            except Exception:
                # Easing failures should not break the fade.
                pass

            def _on_value_changed(value: float) -> None:
                try:
                    effect.setOpacity(float(value))
                except Exception:
                    pass

            anim.valueChanged.connect(_on_value_changed)

            def _on_finished() -> None:
                try:
                    widget.setGraphicsEffect(None)
                except Exception:
                    pass

                try:
                    setattr(widget, "_shadowfade_anim", None)
                except Exception:
                    pass

                try:
                    setattr(widget, "_shadowfade_effect", None)
                except Exception:
                    pass

                try:
                    cls._start_shadow_fade(widget, cfg, has_background_frame=has_background_frame)
                except Exception:
                    logger.debug(
                        "[SHADOW_FADE] Failed to start shadow fade for %r",
                        widget,
                        exc_info=True,
                    )

            anim.finished.connect(_on_finished)
            setattr(widget, "_shadowfade_anim", anim)
            anim.start()
        except Exception:
            logger.debug("[SHADOW_FADE] start_fade_in fallback path triggered for %r", widget, exc_info=True)
            try:
                widget.show()
            except Exception:
                pass
            cls.attach_shadow(widget, cfg, has_background_frame=has_background_frame)
