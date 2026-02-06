"""QGraphicsEffect lifecycle management for WidgetManager.

Extracted from widget_manager.py (M-7 refactor) to reduce monolith size.
Contains effect invalidation, recreation, and scheduled invalidation logic
(Phase E: cache corruption mitigation).
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def invalidate_overlay_effects(mgr: "WidgetManager", reason: str) -> None:
    """Invalidate and optionally recreate widget QGraphicsEffects.

    Phase E Context:
        This method centralizes effect cache-busting to prevent Qt's internal
        cached pixmap/texture backing from becoming corrupt during rapid
        focus/activation + popup menu sequencing across multi-monitor windows.

    Args:
        reason: Identifier for the trigger (e.g., "menu_about_to_show",
                "menu_before_popup", "focus_in"). Menu-related reasons
                trigger stronger invalidation with effect recreation.
    """
    screen_idx = "?"
    try:
        screen_idx = getattr(mgr._parent, "screen_index", "?")
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    if win_diag_logger.isEnabledFor(logging.DEBUG):
        effect_states = []
        for name, widget in mgr._widgets.items():
            if widget is None:
                continue
            try:
                eff = widget.graphicsEffect()
                if eff is not None:
                    eff_type = type(eff).__name__
                    eff_id = id(eff)
                    enabled = eff.isEnabled() if hasattr(eff, 'isEnabled') else '?'
                    effect_states.append(f"{name}:{eff_type}@{eff_id:#x}(en={enabled})")
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        win_diag_logger.debug(
            "[EFFECT_INVALIDATE] screen=%s reason=%s widgets=%d effects=[%s]",
            screen_idx, reason, len(mgr._widgets),
            ", ".join(effect_states) if effect_states else "none",
        )

    # Menu-related triggers warrant stronger invalidation (effect recreation)
    try:
        strong = "menu" in str(reason)
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        strong = False

    refresh_effects = False
    if strong:
        try:
            flip = bool(getattr(mgr, "_effect_refresh_flip", False))
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            flip = False
        flip = not flip
        try:
            setattr(mgr, "_effect_refresh_flip", flip)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        refresh_effects = flip

    seen: set[int] = set()
    for name, widget in mgr._widgets.items():
        if widget is None:
            continue
        try:
            seen.add(id(widget))
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        _invalidate_widget_effect(widget, name, refresh_effects)

    for attr_name in (
        "clock_widget",
        "clock2_widget",
        "clock3_widget",
        "weather_widget",
        "media_widget",
        "spotify_visualizer_widget",
        "spotify_volume_widget",
        "reddit_widget",
        "reddit2_widget",
    ):
        try:
            widget = getattr(mgr._parent, attr_name, None)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            widget = None
        if widget is None:
            continue
        try:
            if id(widget) in seen:
                continue
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        _invalidate_widget_effect(widget, attr_name, refresh_effects)


def _invalidate_widget_effect(widget: QWidget, name: str, refresh: bool) -> None:
    """Invalidate a single widget's graphics effect."""
    try:
        eff = widget.graphicsEffect()
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        eff = None

    if isinstance(eff, (QGraphicsDropShadowEffect, QGraphicsOpacityEffect)):
        if refresh:
            try:
                anim = getattr(widget, "_shadowfade_anim", None)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                anim = None
            try:
                shadow_anim = getattr(widget, "_shadowfade_shadow_anim", None)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                shadow_anim = None

            if anim is None and shadow_anim is None:
                eff = _recreate_effect(widget, eff)

        try:
            eff.setEnabled(False)
            eff.setEnabled(True)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        if isinstance(eff, QGraphicsDropShadowEffect):
            try:
                eff.setBlurRadius(eff.blurRadius())
                eff.setOffset(eff.offset())
                eff.setColor(eff.color())
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    try:
        if widget.isVisible():
            widget.update()
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)


def _recreate_effect(widget: QWidget, old_eff: Any) -> Any:
    """Recreate a QGraphicsEffect to bust Qt's internal cache."""
    if isinstance(old_eff, QGraphicsDropShadowEffect):
        try:
            blur = old_eff.blurRadius()
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            blur = None
        try:
            offset = old_eff.offset()
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            offset = None
        try:
            color = old_eff.color()
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            color = None

        try:
            widget.setGraphicsEffect(None)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        try:
            new_eff = QGraphicsDropShadowEffect(widget)
            if blur is not None:
                new_eff.setBlurRadius(blur)
            if offset is not None:
                new_eff.setOffset(offset)
            if color is not None:
                new_eff.setColor(color)
            widget.setGraphicsEffect(new_eff)
            return new_eff
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            try:
                return widget.graphicsEffect()
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                return old_eff

    elif isinstance(old_eff, QGraphicsOpacityEffect):
        try:
            opacity = old_eff.opacity()
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            opacity = None

        try:
            widget.setGraphicsEffect(None)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        try:
            new_eff = QGraphicsOpacityEffect(widget)
            if opacity is not None:
                new_eff.setOpacity(opacity)
            widget.setGraphicsEffect(new_eff)
            return new_eff
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            try:
                return widget.graphicsEffect()
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                return old_eff

    return old_eff


def schedule_effect_invalidation(mgr: "WidgetManager", reason: str, delay_ms: int = 16) -> None:
    """Schedule a deferred effect invalidation."""
    try:
        pending = getattr(mgr, "_pending_effect_invalidation", False)
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        pending = False

    if pending:
        return

    try:
        setattr(mgr, "_pending_effect_invalidation", True)
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    def _run() -> None:
        try:
            invalidate_overlay_effects(mgr, reason)
        finally:
            try:
                setattr(mgr, "_pending_effect_invalidation", False)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    try:
        QTimer.singleShot(max(0, delay_ms), _run)
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        _run()
