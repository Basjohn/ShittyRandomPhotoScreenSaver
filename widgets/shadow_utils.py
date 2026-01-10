"""Shared helpers for widget drop shadows and overlay widget attributes.

Centralizes configuration for overlay widget shadows (clocks, weather,
media, and future widgets) so behaviour can be tuned in one place.

Shadows are applied via QGraphicsDropShadowEffect where possible, but
will gracefully skip widgets that already use a different graphics
effect (e.g. MediaWidget's opacity effect) to avoid conflicts.

Also provides `configure_overlay_widget_attributes()` to set Qt widget
attributes that prevent flickering when sibling QOpenGLWidgets repaint.

Text shadow helpers are provided for QPainter-based text rendering with
subtle drop shadows that improve readability on varied backgrounds.
"""
from __future__ import annotations

from typing import Any, Mapping, Callable, Optional

from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect
from PySide6.QtCore import QVariantAnimation, QEasingCurve, Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging

logger = get_logger(__name__)


def configure_overlay_widget_attributes(widget: QWidget) -> None:
    """Configure Qt widget attributes to reduce flicker with GL siblings.
    
    On Windows, QOpenGLWidget repaints can cause sibling widgets to flicker.
    These settings help reduce (but may not eliminate) the flicker by:
    1. Disabling auto-fill to prevent redundant background paints
    2. Setting styled background so QSS backgrounds still work
    
    Note: WA_NoSystemBackground was tried but breaks widget backgrounds entirely.
    The real fix for GL flicker is ensuring proper Z-order via raise_overlay().
    
    This should be called in the __init__ or _setup_ui of ALL overlay widgets
    (clock, weather, media, spotify_visualizer, reddit, etc.).
    
    Args:
        widget: The overlay widget to configure.
    """
    try:
        # Disable auto-fill to reduce redundant background paints
        widget.setAutoFillBackground(False)
        # Ensure QSS-based backgrounds still work
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    except Exception as e:
        logger.debug("[SHADOW] Exception suppressed: %s", e)

# Global multiplier to make widget shadows slightly larger/softer by
# increasing their blur radius. This applies both to immediate shadows
# and to the animated shadow fade so visuals stay consistent.
SHADOW_SIZE_MULTIPLIER: float = 1.2

# Intense shadow multipliers - dramatically enhanced shadow effect
# These values are tuned to match the analogue clock's intense shadow styling
INTENSE_SHADOW_BLUR_MULTIPLIER: float = 3.0      # 3x blur for soft, dramatic glow
INTENSE_SHADOW_OPACITY_MULTIPLIER: float = 2.5   # 2.5x opacity for visibility
INTENSE_SHADOW_OFFSET_MULTIPLIER: float = 2.0    # 2x offset for depth


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
    intense: bool = False,
) -> None:
    """Apply or remove a drop shadow on an overlay widget.

    Args:
        widget: Target Qt widget (clock, weather, media, etc.).
        config: ``widgets['shadows']`` settings dictionary.
        has_background_frame: True when the widget is currently drawing
            a solid background/frame (e.g. clock/WeatherWidget
            ``show_background=True``), which uses the stronger
            ``frame_opacity``; otherwise the lighter ``text_opacity``.
        intense: If True, applies intensified shadow styling with
            doubled blur radius, increased opacity, and larger offset
            for dramatic visual effect on large displays.
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
    
    # Clear any existing shadow effect to prevent doubling artifacts
    if isinstance(existing_effect, QGraphicsDropShadowEffect):
        try:
            widget.setGraphicsEffect(None)
        except Exception as e:
            logger.debug("[SHADOWS] Exception suppressed: %s", e)
        finally:
            existing_effect = None

    # Base colour (usually black) with optional alpha from config.
    color_data = config.get("color", [0, 0, 0, 255])
    try:
        r, g, b = int(color_data[0]), int(color_data[1]), int(color_data[2])
        a = int(color_data[3]) if len(color_data) > 3 else 255
    except Exception as e:
        logger.debug("[SHADOW] Exception suppressed: %s", e)
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
    except Exception as e:
        logger.debug("[SHADOW] Exception suppressed: %s", e)
        dx, dy = 4, 4

    try:
        blur_radius = int(config.get("blur_radius", 18))
    except Exception as e:
        logger.debug("[SHADOW] Exception suppressed: %s", e)
        blur_radius = 18
    try:
        blur_radius = max(0, int(blur_radius * SHADOW_SIZE_MULTIPLIER))
    except Exception as e:
        logger.debug("[SHADOW] Exception suppressed: %s", e)

    # Apply intense shadow multipliers if enabled
    if intense:
        try:
            blur_radius = int(blur_radius * INTENSE_SHADOW_BLUR_MULTIPLIER)
            dx = int(dx * INTENSE_SHADOW_OFFSET_MULTIPLIER)
            dy = int(dy * INTENSE_SHADOW_OFFSET_MULTIPLIER)
            # Increase opacity significantly for intense shadows - ensure minimum visibility
            # For text-only widgets, boost from ~0.3 to ~0.75; for framed, from ~0.7 to ~1.0
            base_opacity = min(1.0, max(0.6, base_opacity * INTENSE_SHADOW_OPACITY_MULTIPLIER))
            # Use full alpha channel for maximum shadow visibility
            color = QColor(r, g, b, int(255 * base_opacity))
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)

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
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)
            enabled = True

        if not enabled:
            return

        # CRITICAL: Always create a fresh effect to avoid shadow doubling
        # Reusing an existing effect can cause the old shadow to persist
        # while the new one fades in, creating a "double shadow" artifact
        existing_effect = widget.graphicsEffect()
        if isinstance(existing_effect, QGraphicsDropShadowEffect):
            # Clear the old effect first to prevent doubling
            try:
                widget.setGraphicsEffect(None)
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)
        
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
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)
            r, g, b, a = 0, 0, 0, 255

        text_opacity = float(config.get("text_opacity", 0.3))
        frame_opacity = float(config.get("frame_opacity", 0.7))
        base_opacity = frame_opacity if has_background_frame else text_opacity
        base_opacity = max(0.0, min(1.0, base_opacity))
        target_alpha = int(a * base_opacity)

        offset = config.get("offset", [4, 4])
        try:
            dx, dy = int(offset[0]), int(offset[1])
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)
            dx, dy = 4, 4

        try:
            blur_radius = int(config.get("blur_radius", 18))
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)
            blur_radius = 18
        try:
            blur_radius = max(0, int(blur_radius * SHADOW_SIZE_MULTIPLIER))
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)

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
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)

        def _on_value_changed(value: float) -> None:
            try:
                t = float(value)
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)
                t = 1.0
            t = max(0.0, min(1.0, t))
            alpha = int(target_alpha * t)
            color = QColor(r, g, b, alpha)
            try:
                effect.setColor(color)
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)

        anim.valueChanged.connect(_on_value_changed)

        def _on_finished() -> None:
            try:
                setattr(widget, "_shadowfade_shadow_anim", None)
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)
            try:
                final_color = QColor(r, g, b, target_alpha)
                effect.setColor(final_color)
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)

        anim.finished.connect(_on_finished)
        try:
            setattr(widget, "_shadowfade_shadow_anim", anim)
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)
        anim.start()

    @classmethod
    def start_fade_in(
        cls,
        widget: QWidget,
        config: Mapping[str, Any] | None,
        *,
        has_background_frame: bool,
        on_finished: Optional[Callable[[], None]] = None,
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
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)

            effect = getattr(widget, "_shadowfade_effect", None)
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                setattr(widget, "_shadowfade_effect", effect)

            # Start fully transparent so we never briefly flash at full
            # opacity before the fade is visible.
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)

            if is_verbose_logging():
                logger.debug(
                    "[SHADOW_FADE] start_fade_in widget=%r duration=%sms easing=%s",
                    widget,
                    cls.DURATION_MS,
                    cls.EASING,
                )

            anim = QVariantAnimation(widget)
            anim.setDuration(max(0, int(cls.DURATION_MS)))
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            try:
                anim.setEasingCurve(cls.EASING)
            except Exception:
                # Easing failures should not break the fade.
                pass

            # Track whether we've shown the widget yet
            widget_shown = [False]

            def _on_value_changed(value: float) -> None:
                try:
                    f = float(value)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)
                    f = 0.0
                
                # Show the widget on first animation tick when opacity is confirmed at 0.0
                if not widget_shown[0]:
                    try:
                        widget.show()
                        widget_shown[0] = True
                    except Exception:
                        # Showing may fail during shutdown; in that case we still
                        # allow the animation/shadow logic to proceed.
                        pass
                
                try:
                    effect.setOpacity(f)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)
                # Expose the instantaneous fade progress on the widget so
                # GPU clients (e.g. GL compositor overlays) can track the
                # same curve without duplicating easing logic.
                try:
                    setattr(widget, "_shadowfade_progress", f)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)

            anim.valueChanged.connect(_on_value_changed)

            def _on_finished() -> None:
                try:
                    widget.setGraphicsEffect(None)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)

                try:
                    setattr(widget, "_shadowfade_anim", None)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)

                try:
                    setattr(widget, "_shadowfade_effect", None)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)

                # Ensure final progress is pinned at 1.0 for clients that
                # read the attribute after the fade completes.
                try:
                    setattr(widget, "_shadowfade_progress", 1.0)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)
                # Mark fade as completed so GPU overlays know they can show
                # even if _shadowfade_progress is later cleared or unavailable.
                try:
                    setattr(widget, "_shadowfade_completed", True)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)

                try:
                    cls._start_shadow_fade(widget, cfg, has_background_frame=has_background_frame)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)
                    if is_verbose_logging():
                        logger.debug(
                            "[SHADOW_FADE] Failed to start shadow fade for %r",
                            widget,
                            exc_info=True,
                        )
                if on_finished is not None:
                    try:
                        on_finished()
                    except Exception as e:
                        logger.debug("[SHADOW] Exception suppressed in on_finished: %s", e)

            anim.finished.connect(_on_finished)
            setattr(widget, "_shadowfade_anim", anim)
            anim.start()
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)
            if is_verbose_logging():
                logger.debug("[SHADOW_FADE] start_fade_in fallback path triggered for %r", widget, exc_info=True)
            try:
                widget.show()
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)
            cls.attach_shadow(widget, cfg, has_background_frame=has_background_frame)
            if on_finished is not None:
                try:
                    on_finished()
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed in on_finished: %s", e)

    @classmethod
    def start_fade_out(
        cls,
        widget: QWidget,
        *,
        duration_ms: int = 800,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """Fade ``widget`` out and invoke ``on_complete`` when finished."""

        try:
            if not Shiboken.isValid(widget):
                if on_complete is not None:
                    on_complete()
                return

            if duration_ms <= 0:
                try:
                    widget.hide()
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)
                if on_complete is not None:
                    on_complete()
                return

            existing_effect = widget.graphicsEffect()
            if isinstance(existing_effect, QGraphicsDropShadowEffect):
                try:
                    widget.setGraphicsEffect(None)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)

            opacity_effect = QGraphicsOpacityEffect(widget)
            opacity_effect.setOpacity(1.0)
            widget.setGraphicsEffect(opacity_effect)

            anim = QVariantAnimation(widget)
            anim.setDuration(max(0, int(duration_ms)))
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            try:
                anim.setEasingCurve(QEasingCurve.InOutCubic)
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)

            def _on_value_changed(value: float) -> None:
                try:
                    opacity_effect.setOpacity(max(0.0, min(1.0, float(value))))
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)

            def _on_finished() -> None:
                try:
                    widget.setGraphicsEffect(None)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)
                try:
                    widget.hide()
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)
                if on_complete is not None:
                    try:
                        on_complete()
                    except Exception as e:
                        logger.debug("[SHADOW] Exception suppressed in on_complete: %s", e)

            anim.valueChanged.connect(_on_value_changed)
            anim.finished.connect(_on_finished)
            anim.start()
        except Exception as e:
            logger.debug("[SHADOW] Exception suppressed: %s", e)
            try:
                widget.hide()
            except Exception as inner:
                logger.debug("[SHADOW] Exception suppressed: %s", inner)
            if on_complete is not None:
                try:
                    on_complete()
                except Exception as inner:
                    logger.debug("[SHADOW] Exception suppressed in on_complete: %s", inner)


# ---------------------------------------------------------------------------
# Text Shadow Helpers for QPainter-based rendering
# ---------------------------------------------------------------------------

# Default text shadow settings - bottom-right offset matching widget shadows
TEXT_SHADOW_OFFSET_X: int = 1
TEXT_SHADOW_OFFSET_Y: int = 1
TEXT_SHADOW_COLOR: QColor = QColor(0, 0, 0, 100)

# Smaller text gets less shadow to avoid overwhelming the text
TEXT_SHADOW_MIN_FONT_SIZE: int = 10  # Below this, shadow is reduced


def draw_text_with_shadow(
    painter: QPainter,
    x: int,
    y: int,
    text: str,
    *,
    shadow_color: QColor = None,
    shadow_offset_x: int = None,
    shadow_offset_y: int = None,
    font_size: int = 12,
) -> None:
    """Draw text with a subtle drop shadow for better readability.
    
    The shadow is drawn first (offset bottom-right), then the main text
    is drawn on top. Shadow opacity is scaled based on font size - smaller
    text gets less shadow to avoid overwhelming it.
    
    Args:
        painter: QPainter to draw with (must have font/pen already set)
        x: X coordinate for text baseline
        y: Y coordinate for text baseline
        text: Text string to draw
        shadow_color: Shadow color (default: semi-transparent black)
        shadow_offset_x: Horizontal shadow offset (default: 1px right)
        shadow_offset_y: Vertical shadow offset (default: 1px down)
        font_size: Font size in points (used to scale shadow intensity)
    """
    if not text:
        return
    
    # Use defaults if not specified
    if shadow_color is None:
        shadow_color = TEXT_SHADOW_COLOR
    if shadow_offset_x is None:
        shadow_offset_x = TEXT_SHADOW_OFFSET_X
    if shadow_offset_y is None:
        shadow_offset_y = TEXT_SHADOW_OFFSET_Y
    
    # Scale shadow opacity based on font size (smaller text = less shadow)
    if font_size < TEXT_SHADOW_MIN_FONT_SIZE:
        scale = max(0.3, font_size / TEXT_SHADOW_MIN_FONT_SIZE)
        alpha = int(shadow_color.alpha() * scale)
        shadow_color = QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha)
    
    # Save current pen
    original_pen = painter.pen()
    
    # Draw shadow
    painter.setPen(shadow_color)
    painter.drawText(x + shadow_offset_x, y + shadow_offset_y, text)
    
    # Draw main text
    painter.setPen(original_pen)
    painter.drawText(x, y, text)


def draw_text_rect_with_shadow(
    painter: QPainter,
    rect: QRect,
    flags: int,
    text: str,
    *,
    shadow_color: QColor = None,
    shadow_offset_x: int = None,
    shadow_offset_y: int = None,
    font_size: int = 12,
) -> None:
    """Draw text in a rect with a subtle drop shadow.
    
    Similar to draw_text_with_shadow but uses drawText(rect, flags, text).
    
    Args:
        painter: QPainter to draw with
        rect: Bounding rectangle for text
        flags: Qt alignment flags
        text: Text string to draw
        shadow_color: Shadow color (default: semi-transparent black)
        shadow_offset_x: Horizontal shadow offset (default: 1px right)
        shadow_offset_y: Vertical shadow offset (default: 1px down)
        font_size: Font size in points (used to scale shadow intensity)
    """
    if not text:
        return
    
    # Use defaults if not specified
    if shadow_color is None:
        shadow_color = TEXT_SHADOW_COLOR
    if shadow_offset_x is None:
        shadow_offset_x = TEXT_SHADOW_OFFSET_X
    if shadow_offset_y is None:
        shadow_offset_y = TEXT_SHADOW_OFFSET_Y
    
    # Scale shadow opacity based on font size
    if font_size < TEXT_SHADOW_MIN_FONT_SIZE:
        scale = max(0.3, font_size / TEXT_SHADOW_MIN_FONT_SIZE)
        alpha = int(shadow_color.alpha() * scale)
        shadow_color = QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha)
    
    # Save current pen
    original_pen = painter.pen()
    
    # Draw shadow (offset rect)
    shadow_rect = QRect(
        rect.x() + shadow_offset_x,
        rect.y() + shadow_offset_y,
        rect.width(),
        rect.height(),
    )
    painter.setPen(shadow_color)
    painter.drawText(shadow_rect, flags, text)
    
    # Draw main text
    painter.setPen(original_pen)
    painter.drawText(rect, flags, text)


def draw_rounded_rect_with_shadow(
    painter: QPainter,
    rect: QRect,
    radius: float,
    border_color: QColor,
    border_width: int = 1,
    *,
    shadow_color: QColor = None,
    shadow_offset_x: int = 2,
    shadow_offset_y: int = 2,
) -> None:
    """Draw a rounded rectangle border with a drop shadow.
    
    Used for header frames on Reddit/Spotify widgets. Shadow is drawn
    first (offset bottom-right), then the main border on top.
    
    Args:
        painter: QPainter to draw with
        rect: Bounding rectangle
        radius: Corner radius
        border_color: Border color
        border_width: Border width in pixels
        shadow_color: Shadow color (default: semi-transparent black)
        shadow_offset_x: Horizontal shadow offset
        shadow_offset_y: Vertical shadow offset
    """
    if shadow_color is None:
        shadow_color = QColor(0, 0, 0, 80)
    
    painter.save()
    try:
        # Draw shadow
        shadow_rect = QRect(
            rect.x() + shadow_offset_x,
            rect.y() + shadow_offset_y,
            rect.width(),
            rect.height(),
        )
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, radius, radius)
        
        pen = QPen(shadow_color)
        pen.setWidth(border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(shadow_path)
        
        # Draw main border
        main_path = QPainterPath()
        main_path.addRoundedRect(rect, radius, radius)
        
        pen = QPen(border_color)
        pen.setWidth(border_width)
        painter.setPen(pen)
        painter.drawPath(main_path)
    finally:
        painter.restore()
