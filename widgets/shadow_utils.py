"""Shared helpers for runtime widget shadows and overlay widget attributes.

Centralizes configuration for overlay widget shadows (clocks, weather,
media, and future widgets) so behaviour can be tuned in one place.

Runtime card, text, and header shadows are painter-drawn to avoid Qt
QGraphicsDropShadowEffect cache corruption on translucent overlay widgets.

Also provides `configure_overlay_widget_attributes()` to set Qt widget
attributes that prevent flickering when sibling QOpenGLWidgets repaint.

Text shadow helpers are provided for QPainter-based text rendering with
subtle drop shadows that improve readability on varied backgrounds.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Callable, Optional

from PySide6.QtWidgets import QLabel, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import QVariantAnimation, QEasingCurve, Qt, QRect, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QTextDocument
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging
from core.settings.shadow_tuning import (
    HEADER_SHADOW_TUNING,
    ICON_SHADOW_TUNING,
    TEXT_SHADOW_TUNING,
    TEXT_LARGE_SHADOW_TUNING,
)

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


def uses_painted_frame_shadow(widget: QWidget) -> bool:
    """Return True when a widget owns its framed-card shadow in paintEvent."""
    try:
        fn = getattr(widget, "uses_painted_frame_shadow", None)
        if callable(fn):
            return bool(fn())
    except Exception:
        return False
    return False


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


def shadow_config_enabled(config: Mapping[str, Any] | None, key: str = "enabled", default: bool = True) -> bool:
    """Read a runtime shadow boolean from ``widgets.shadows`` config."""

    if config is None:
        return default
    return _to_bool(config.get(key, default), default)


def text_shadows_enabled(config: Mapping[str, Any] | None) -> bool:
    return shadow_config_enabled(config, "text_enabled", True)


def header_shadows_enabled(config: Mapping[str, Any] | None) -> bool:
    return shadow_config_enabled(config, "header_enabled", True)


class ShadowFadeProfile:
    """Global helper for widget opacity fade-in/fade-out.

    Widgets call :meth:`start_fade_in` when they first become visible.
    The helper installs a temporary opacity effect, animates from 0.0 to
    1.0 with a single shared duration/easing, then removes the effect.

    A pair of attributes, ``_shadowfade_effect`` and ``_shadowfade_anim``,
    are attached to the widget instance to keep the effect and animation
    alive for the duration of the fade.
    """

    # Single global profile for all widgets – not user-configurable for
    # now. Keep this slightly longer than the earlier 1.5s profile, but
    # prefer a softer easing curve so startup feels coordinated rather than
    # immediately front-loaded into the first few hundred milliseconds.
    DURATION_MS: int = 1800
    EASING: QEasingCurve.Type = QEasingCurve.InOutCubic

    @classmethod
    def default_duration_ms(cls) -> int:
        """Return the canonical shared fade duration."""

        return max(0, int(cls.DURATION_MS))

    @classmethod
    def attach_shadow(
        cls,
        widget: QWidget,
        config: Mapping[str, Any] | None,
        *,
        has_background_frame: bool,
    ) -> None:
        """Refresh painter-owned shadows after no-fade fallback paths."""

        try:
            widget.update()
        except Exception:
            logger.debug("[SHADOW_FADE] attach_shadow refresh failed for %r", widget, exc_info=True)

    @classmethod
    def start_fade_in(
        cls,
        widget: QWidget,
        config: Mapping[str, Any] | None,
        *,
        duration_ms: Optional[int] = None,
        has_background_frame: bool,
        apply_shadow_on_finish: bool = True,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        """Fade ``widget`` in using an opacity effect.

        This helper intentionally does **not** look at any fade-related
        settings; duration and easing are global and fixed so that all
        widgets fade in with identical timing.
        """

        cfg = config or {}
        resolved_duration_ms = (
            cls.default_duration_ms() if duration_ms is None else max(0, int(duration_ms))
        )

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
                    resolved_duration_ms,
                    cls.EASING,
                )

            # Show immediately while pinned at 0 opacity so the coordinated
            # fade remains visible even if the event loop is briefly busy
            # before the first animation tick fires.
            try:
                widget.show()
            except Exception:
                # Showing may fail during shutdown; in that case we still
                # allow the animation/shadow logic to proceed.
                pass

            try:
                setattr(widget, "_shadowfade_progress", 0.0)
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)
            try:
                setattr(widget, "_shadowfade_completed", False)
            except Exception as e:
                logger.debug("[SHADOW] Exception suppressed: %s", e)

            anim = QVariantAnimation(widget)
            anim.setDuration(resolved_duration_ms)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            try:
                anim.setEasingCurve(cls.EASING)
            except Exception:
                # Easing failures should not break the fade.
                pass

            def _on_value_changed(value: float) -> None:
                if not Shiboken.isValid(effect):
                    return
                try:
                    f = float(value)
                except Exception as e:
                    logger.debug("[SHADOW] Exception suppressed: %s", e)
                    f = 0.0

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
            logger.warning(
                "[LIFECYCLE][FALLBACK] Shadow fade-in failed; using direct show for %r",
                widget,
                exc_info=True,
            )
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
                if not Shiboken.isValid(opacity_effect):
                    return
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

TEXT_SHADOW_OFFSET_X: float = float(TEXT_SHADOW_TUNING["offset_x"])
TEXT_SHADOW_OFFSET_Y: float = float(TEXT_SHADOW_TUNING["offset_y"])
TEXT_SHADOW_COLOR: QColor = QColor(0, 0, 0, int(TEXT_SHADOW_TUNING["alpha"]))
TEXT_SHADOW_MIN_FONT_SIZE: int = int(TEXT_SHADOW_TUNING["min_font_size"])
TEXT_SHADOW_SMALL_FONT_MIN_SCALE: float = float(TEXT_SHADOW_TUNING["small_font_min_scale"])
TEXT_LARGE_SHADOW_OFFSET_X: float = float(TEXT_LARGE_SHADOW_TUNING["offset_x"])
TEXT_LARGE_SHADOW_OFFSET_Y: float = float(TEXT_LARGE_SHADOW_TUNING["offset_y"])
TEXT_LARGE_SHADOW_COLOR: QColor = QColor(0, 0, 0, int(TEXT_LARGE_SHADOW_TUNING["alpha"]))
TEXT_LARGE_SHADOW_MIN_FONT_SIZE: int = int(TEXT_LARGE_SHADOW_TUNING["min_font_size"])
TEXT_LARGE_SHADOW_SMALL_FONT_MIN_SCALE: float = float(TEXT_LARGE_SHADOW_TUNING["small_font_min_scale"])
HEADER_SHADOW_OFFSET_X: float = float(HEADER_SHADOW_TUNING["offset_x"])
HEADER_SHADOW_OFFSET_Y: float = float(HEADER_SHADOW_TUNING["offset_y"])
HEADER_SHADOW_COLOR: QColor = QColor(0, 0, 0, int(HEADER_SHADOW_TUNING["alpha"]))


def _resolve_text_shadow_params(
    *,
    font_size: int,
    shadow_color: QColor | None,
    shadow_offset_x: float | None,
    shadow_offset_y: float | None,
) -> tuple[QColor, float, float, int, float]:
    """Resolve text or large-text shadow tuning for a font size."""

    use_large_tuning = font_size >= TEXT_LARGE_SHADOW_MIN_FONT_SIZE
    if use_large_tuning:
        color = shadow_color or QColor(TEXT_LARGE_SHADOW_COLOR)
        offset_x = TEXT_LARGE_SHADOW_OFFSET_X if shadow_offset_x is None else float(shadow_offset_x)
        offset_y = TEXT_LARGE_SHADOW_OFFSET_Y if shadow_offset_y is None else float(shadow_offset_y)
        min_font_size = TEXT_LARGE_SHADOW_MIN_FONT_SIZE
        small_font_min_scale = TEXT_LARGE_SHADOW_SMALL_FONT_MIN_SCALE
    else:
        color = shadow_color or QColor(TEXT_SHADOW_COLOR)
        offset_x = TEXT_SHADOW_OFFSET_X if shadow_offset_x is None else float(shadow_offset_x)
        offset_y = TEXT_SHADOW_OFFSET_Y if shadow_offset_y is None else float(shadow_offset_y)
        min_font_size = TEXT_SHADOW_MIN_FONT_SIZE
        small_font_min_scale = TEXT_SHADOW_SMALL_FONT_MIN_SCALE
    return color, offset_x, offset_y, min_font_size, small_font_min_scale


def resolve_text_shadow_params(font_size: int) -> tuple[QColor, float, float, int, float]:
    """Public resolver for cached native-label shadow paths."""
    return _resolve_text_shadow_params(
        font_size=font_size,
        shadow_color=None,
        shadow_offset_x=None,
        shadow_offset_y=None,
    )


def draw_text_with_shadow(
    painter: QPainter,
    x: int,
    y: int,
    text: str,
    *,
    shadow_color: QColor = None,
    shadow_offset_x: float = None,
    shadow_offset_y: float = None,
    font_size: int = 12,
    enabled: bool = True,
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
    if not enabled:
        painter.drawText(x, y, text)
        return
    
    shadow_color, shadow_offset_x, shadow_offset_y, min_font_size, small_font_min_scale = (
        _resolve_text_shadow_params(
            font_size=font_size,
            shadow_color=shadow_color,
            shadow_offset_x=shadow_offset_x,
            shadow_offset_y=shadow_offset_y,
        )
    )
    
    # Scale shadow opacity based on font size (smaller text = less shadow)
    if font_size < min_font_size:
        scale = max(small_font_min_scale, font_size / min_font_size)
        alpha = int(shadow_color.alpha() * scale)
        shadow_color = QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha)
    
    # Save current pen
    original_pen = painter.pen()
    
    # Draw shadow
    painter.setPen(shadow_color)
    painter.drawText(QPointF(float(x) + shadow_offset_x, float(y) + shadow_offset_y), text)
    
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
    shadow_offset_x: float = None,
    shadow_offset_y: float = None,
    font_size: int = 12,
    enabled: bool = True,
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
    if not enabled:
        painter.drawText(rect, flags, text)
        return
    
    shadow_color, shadow_offset_x, shadow_offset_y, min_font_size, small_font_min_scale = (
        _resolve_text_shadow_params(
            font_size=font_size,
            shadow_color=shadow_color,
            shadow_offset_x=shadow_offset_x,
            shadow_offset_y=shadow_offset_y,
        )
    )
    
    # Scale shadow opacity based on font size
    if font_size < min_font_size:
        scale = max(small_font_min_scale, font_size / min_font_size)
        alpha = int(shadow_color.alpha() * scale)
        shadow_color = QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha)
    
    # Save current pen
    original_pen = painter.pen()
    
    # Draw shadow (offset rect)
    shadow_rect = QRectF(
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


def draw_text_rect_shadow_only(
    painter: QPainter,
    rect: QRect,
    flags: int,
    text: str,
    *,
    shadow_color: QColor = None,
    shadow_offset_x: float = None,
    shadow_offset_y: float = None,
    font_size: int = 12,
) -> None:
    """Draw only the shadow pass for QLabel/native text paint paths."""
    if not text:
        return

    shadow_color, shadow_offset_x, shadow_offset_y, min_font_size, small_font_min_scale = (
        _resolve_text_shadow_params(
            font_size=font_size,
            shadow_color=shadow_color,
            shadow_offset_x=shadow_offset_x,
            shadow_offset_y=shadow_offset_y,
        )
    )

    if font_size < min_font_size:
        scale = max(small_font_min_scale, font_size / min_font_size)
        alpha = int(shadow_color.alpha() * scale)
        shadow_color = QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha)

    original_pen = painter.pen()
    shadow_rect = QRectF(
        rect.x() + shadow_offset_x,
        rect.y() + shadow_offset_y,
        rect.width(),
        rect.height(),
    )
    painter.setPen(shadow_color)
    painter.drawText(shadow_rect, flags, text)
    painter.setPen(original_pen)


class PaintedShadowLabel(QLabel):
    """QLabel variant that paints a safe text-shadow pass before native text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shadow_config: Mapping[str, Any] | None = None

    def set_shadow_config(self, config: Mapping[str, Any] | None) -> None:
        self._shadow_config = config
        self.update()

    def _should_paint_text_shadow(self) -> bool:
        if not text_shadows_enabled(self._shadow_config):
            return False
        text = self.text()
        if not text:
            return False
        text_format = self.textFormat()
        if text_format == Qt.TextFormat.RichText:
            return False
        if text_format == Qt.TextFormat.AutoText and ("<" in text and ">" in text):
            return False
        return True

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self._should_paint_text_shadow():
            painter = QPainter(self)
            try:
                painter.setFont(self.font())
                font_size = int(self.font().pointSize() or 12)
                draw_text_rect_shadow_only(
                    painter,
                    self.contentsRect(),
                    self.alignment(),
                    self.text(),
                    font_size=font_size,
                )
            finally:
                painter.end()
        super().paintEvent(event)


def draw_rich_text_shadow_only(
    painter: QPainter,
    rect: QRect,
    html: str,
    *,
    default_font,
    font_size: int,
    enabled: bool = True,
) -> None:
    """Draw a shadow-only pass for QLabel rich text."""
    if not html or not enabled:
        return

    shadow_color, shadow_offset_x, shadow_offset_y, min_font_size, small_font_min_scale = (
        _resolve_text_shadow_params(
            font_size=font_size,
            shadow_color=None,
            shadow_offset_x=None,
            shadow_offset_y=None,
        )
    )
    if font_size < min_font_size:
        scale = max(small_font_min_scale, font_size / min_font_size)
        shadow_color = QColor(
            shadow_color.red(),
            shadow_color.green(),
            shadow_color.blue(),
            int(shadow_color.alpha() * scale),
        )

    css_color = (
        f"rgba({shadow_color.red()},{shadow_color.green()},"
        f"{shadow_color.blue()},{shadow_color.alpha()})"
    )
    shadow_html = re.sub(r"color\s*:\s*[^;'\"]+;?", f"color:{css_color};", html)
    shadow_html = f"<div style='color:{css_color};'>{shadow_html}</div>"

    doc = QTextDocument()
    doc.setDefaultFont(default_font)
    doc.setDocumentMargin(0.0)
    doc.setDefaultStyleSheet(f"* {{ color: {css_color}; }}")
    doc.setHtml(shadow_html)
    doc.setTextWidth(float(rect.width()))

    painter.save()
    try:
        painter.translate(float(rect.x()) + shadow_offset_x, float(rect.y()) + shadow_offset_y)
        doc.drawContents(painter, QRectF(0.0, 0.0, float(rect.width()), float(rect.height())))
    finally:
        painter.restore()


def make_alpha_shadow_pixmap(
    source: QPixmap,
    *,
    dpr: float,
    shadow_color: QColor,
) -> QPixmap:
    """Return a tinted alpha-mask shadow for *source*.

    The transparent pixels remain transparent; only the source alpha silhouette
    contributes to the shadow.
    """
    if source.isNull():
        return QPixmap()

    scale_dpr = max(1.0, float(dpr))
    try:
        source_dpr = max(1.0, float(source.devicePixelRatio()))
    except Exception:
        source_dpr = 1.0
    logical_w = max(1, int(round(source.width() / source_dpr)))
    logical_h = max(1, int(round(source.height() / source_dpr)))
    pixmap = QPixmap(max(1, int(logical_w * scale_dpr)), max(1, int(logical_h * scale_dpr)))
    pixmap.setDevicePixelRatio(scale_dpr)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(QRect(0, 0, logical_w, logical_h), source)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(QRect(0, 0, logical_w, logical_h), shadow_color)
    finally:
        painter.end()

    return pixmap


def draw_pixmap_drop_shadow(
    painter: QPainter,
    target: QRect,
    source: QPixmap,
    *,
    owner: object,
    cache_attr: str,
    shadow_config: Mapping[str, Any] | None,
    enabled_key: str = "header_enabled",
) -> None:
    """Draw a cached alpha-mask drop shadow for a logo/icon pixmap.

    The helper uses the same silhouette-shadow mechanism as weather icons:
    transparent pixels stay transparent, the shadow is offset down/right, and
    the tinted mask is cached per source pixmap/target/DPR/tuning tuple.
    """

    if source is None or source.isNull():
        return
    if target.width() <= 0 or target.height() <= 0:
        return
    if not shadow_config_enabled(shadow_config, enabled_key, True):
        return

    try:
        device = painter.device()
        dpr = float(device.devicePixelRatioF()) if device is not None else 1.0
    except Exception:
        dpr = 1.0
    dpr = max(1.0, dpr)

    offset_x = int(ICON_SHADOW_TUNING.get("offset_x", 3))
    offset_y = int(ICON_SHADOW_TUNING.get("offset_y", 4))
    alpha = max(0, min(255, int(ICON_SHADOW_TUNING.get("alpha", 67))))
    target_w = int(target.width())
    target_h = int(target.height())
    cache_key = (
        int(source.cacheKey()),
        target_w,
        target_h,
        round(dpr, 3),
        alpha,
    )

    cached_key = getattr(owner, f"{cache_attr}_key", None)
    shadow = getattr(owner, cache_attr, None)
    if cached_key != cache_key or not isinstance(shadow, QPixmap) or shadow.isNull():
        scaled = source.scaled(
            max(1, int(round(target_w * dpr))),
            max(1, int(round(target_h * dpr))),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        try:
            scaled.setDevicePixelRatio(dpr)
        except Exception:
            pass
        shadow = make_alpha_shadow_pixmap(
            scaled,
            dpr=dpr,
            shadow_color=QColor(0, 0, 0, alpha),
        )
        setattr(owner, cache_attr, shadow)
        setattr(owner, f"{cache_attr}_key", cache_key)

    painter.drawPixmap(int(target.x() + offset_x), int(target.y() + offset_y), shadow)


def draw_rounded_rect_with_shadow(
    painter: QPainter,
    rect: QRect,
    radius: float,
    border_color: QColor,
    border_width: int = 1,
    *,
    shadow_color: QColor = None,
    shadow_offset_x: int = None,
    shadow_offset_y: int = None,
    shadow_enabled: bool = True,
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
        shadow_color = HEADER_SHADOW_COLOR
    if shadow_offset_x is None:
        shadow_offset_x = HEADER_SHADOW_OFFSET_X
    if shadow_offset_y is None:
        shadow_offset_y = HEADER_SHADOW_OFFSET_Y
    
    painter.save()
    try:
        if shadow_enabled:
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
