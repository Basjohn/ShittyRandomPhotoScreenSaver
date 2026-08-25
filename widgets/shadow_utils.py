"""Current QWidget overlay helpers used during the Qt Quick migration.

The retained helpers cover overlay attributes, old-presenter fade lifecycle,
and content painting still shared by unported families. Generic text, header,
and icon shadows from the retired global sidecar are intentionally absent.
"""
from __future__ import annotations

from typing import Any, Mapping, Callable, Optional

from PySide6.QtWidgets import QLabel, QWidget, QGraphicsOpacityEffect
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
# Plain content painting for current QWidget families
# ---------------------------------------------------------------------------

def draw_text_with_shadow(
    painter: QPainter,
    x: int,
    y: int,
    text: str,
    *,
    font_size: int = 12,
    enabled: bool = True,
) -> None:
    """Draw visible text after retirement of the generic QWidget shadow pass."""

    del font_size, enabled
    if not text:
        return
    painter.drawText(x, y, text)


def draw_text_rect_with_shadow(
    painter: QPainter,
    rect: QRect,
    flags: int,
    text: str,
    *,
    font_size: int = 12,
    enabled: bool = True,
) -> None:
    """Draw visible bounded text without the retired generic shadow pass."""

    del font_size, enabled
    if not text:
        return
    painter.drawText(rect, flags, text)


class PaintedShadowLabel(QLabel):
    """Plain label retained by unported families after generic shadow retirement."""

    def set_shadow_config(self, config: Mapping[str, Any] | None) -> None:
        del config
        self.update()


def draw_rounded_rect_border(
    painter: QPainter,
    rect: QRect,
    radius: float,
    border_color: QColor,
    border_width: int = 1,
) -> None:
    """Draw the visible rounded border without a generic header shadow."""

    painter.save()
    try:
        main_path = QPainterPath()
        main_path.addRoundedRect(rect, radius, radius)

        pen = QPen(border_color)
        pen.setWidth(border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(main_path)
    finally:
        painter.restore()
