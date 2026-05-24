"""Transient opacity-effect refresh helpers for WidgetManager.

Extracted from widget_manager.py (M-7 refactor) to reduce monolith size.
This module now owns only lightweight refresh behavior for widgets that
currently have a live ``QGraphicsOpacityEffect`` attached (for example,
while a shared fade helper is in flight). It no longer performs the old
menu/focus-era cache-busting effect toggles/recreation that existed for the
retired translucent shadow corruption path.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def invalidate_overlay_effects(mgr: "WidgetManager", reason: str) -> None:
    """Refresh only live opacity-fade effects owned by runtime widgets.

    Painter-owned card/text/header shadows no longer rely on QGraphicsEffect
    cache busting, so menu/focus/display-change callers should not toggle or
    recreate effects here. The remaining legitimate runtime use is to ask any
    currently fading overlay to repaint once if a caller knows a refresh would
    be helpful.
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

    seen: set[int] = set()
    for name, widget in mgr._widgets.items():
        if widget is None:
            continue
        try:
            seen.add(id(widget))
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        _refresh_widget_opacity_effect(widget, name)

    for attr_name in (
        "clock_widget",
        "clock2_widget",
        "clock3_widget",
        "weather_widget",
        "media_widget",
        "spotify_visualizer_widget",
        "spotify_volume_widget",
        "gmail_widget",
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
        _refresh_widget_opacity_effect(widget, attr_name)


def _refresh_widget_opacity_effect(widget: QWidget, name: str) -> None:
    """Request a repaint for a widget that currently owns an opacity effect."""
    try:
        eff = widget.graphicsEffect()
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        eff = None

    if not isinstance(eff, QGraphicsOpacityEffect):
        return

    try:
        if widget.isVisible():
            widget.update()
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Failed to refresh live opacity effect for %s", name, exc_info=True)
