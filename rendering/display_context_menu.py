"""Display Context Menu Handlers - Extracted from display_widget.py.

Contains context menu creation, transition selection, dimming toggle,
hard exit toggle, always-on-top toggle, and exit request handlers.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QCursor

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from widgets.context_menu import ScreensaverContextMenu

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def show_context_menu(widget, global_pos) -> None:
    """Show the context menu at the given global position."""
    try:
        current_transition, random_enabled = widget._refresh_transition_state_from_settings()
        
        hard_exit = widget._is_hard_exit_enabled()
        
        # Get dimming state - use dot notation for settings
        dimming_enabled = False
        if widget.settings_manager:
            dimming_enabled = SettingsManager.to_bool(
                widget.settings_manager.get("accessibility.dimming.enabled", False), False
            )
        
        # Create menu if needed (lazy init for performance)
        if widget._context_menu is None:
            current_transition, random_enabled = widget._refresh_transition_state_from_settings()
            widget._context_menu = ScreensaverContextMenu(
                parent=widget,
                current_transition=current_transition,
                random_enabled=random_enabled,
                dimming_enabled=dimming_enabled,
                hard_exit_enabled=hard_exit,
                is_mc_build=widget._is_mc_build,
                always_on_top=widget._always_on_top,
            )
            # Connect signals
            widget._context_menu.previous_requested.connect(widget.previous_requested.emit)
            widget._context_menu.next_requested.connect(widget.next_requested.emit)
            widget._context_menu.transition_selected.connect(widget._on_context_transition_selected)
            widget._context_menu.settings_requested.connect(widget.settings_requested.emit)
            widget._context_menu.dimming_toggled.connect(widget._on_context_dimming_toggled)
            widget._context_menu.hard_exit_toggled.connect(widget._on_context_hard_exit_toggled)
            widget._context_menu.always_on_top_toggled.connect(widget._on_context_always_on_top_toggled)
            widget._context_menu.exit_requested.connect(widget._on_context_exit_requested)
            try:
                widget._context_menu.aboutToShow.connect(lambda: widget._invalidate_overlay_effects("menu_about_to_show"))
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            try:
                submenu = getattr(widget._context_menu, "_transition_menu", None)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                submenu = None
            try:
                connected_sub = bool(getattr(widget, "_context_menu_sub_connected", False))
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                connected_sub = False
            if submenu is not None and not connected_sub:
                try:
                    submenu.aboutToShow.connect(lambda: widget._invalidate_overlay_effects("menu_sub_about_to_show"))
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                try:
                    submenu.aboutToHide.connect(lambda: widget._schedule_effect_invalidation("menu_sub_after_hide"))
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                try:
                    setattr(widget, "_context_menu_sub_connected", True)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        else:
            # Update state before showing
            current_transition, random_enabled = widget._refresh_transition_state_from_settings()
            widget._context_menu.update_transition_state(current_transition, random_enabled)
            widget._context_menu.update_dimming_state(dimming_enabled)
            widget._context_menu.update_hard_exit_state(hard_exit)
            widget._context_menu.update_always_on_top_state(widget._always_on_top)
        
        try:
            widget._context_menu_active = True
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        widget._hide_ctrl_cursor_hint(immediate=True)

        try:
            t0 = time.monotonic()
            setattr(widget, "_menu_open_ts", t0)
            if win_diag_logger.isEnabledFor(logging.DEBUG):
                win_diag_logger.debug(
                    "[MENU_OPEN] begin t=%.6f screen=%s pos=%s",
                    t0,
                    widget.screen_index,
                    global_pos,
                )
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            setattr(widget, "_menu_open_ts", None)

        try:
            connected = getattr(widget, "_context_menu_hide_connected", False)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            connected = False
        if not connected:
            try:
                def _on_menu_hide() -> None:
                    try:
                        widget._context_menu_active = False
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    # Phase E: Notify InputHandler of menu close for consistent state
                    try:
                        if widget._input_handler is not None:
                            widget._input_handler.set_context_menu_active(False)
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    try:
                        widget._invalidate_overlay_effects("menu_after_hide")
                        widget._schedule_effect_invalidation("menu_after_hide")
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    try:
                        start = getattr(widget, "_menu_open_ts", None)
                        if start is not None and win_diag_logger.isEnabledFor(logging.DEBUG):
                            t1 = time.monotonic()
                            win_diag_logger.debug(
                                "[MENU_OPEN] end t=%.6f dt=%.3fms screen=%s",
                                t1,
                                (t1 - start) * 1000.0,
                                widget.screen_index,
                            )
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    # Restore halo after menu closes if still in hard_exit or Ctrl mode
                    try:
                        hard_exit = False
                        if widget.settings_manager:
                            hard_exit = SettingsManager.to_bool(
                                widget.settings_manager.get("input.hard_exit", False), False
                            )
                        if hard_exit or widget._coordinator.ctrl_held:
                            # Re-show halo at current cursor position
                            global_pos = QCursor.pos()
                            local_pos = widget.mapFromGlobal(global_pos)
                            if widget.rect().contains(local_pos):
                                widget._coordinator.set_halo_owner(widget)
                                widget._show_ctrl_cursor_hint(local_pos, mode="fade_in")
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

                widget._context_menu.aboutToHide.connect(_on_menu_hide)
                setattr(widget, "_context_menu_hide_connected", True)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        # Phase E: Notify InputHandler of menu open for consistent state
        try:
            if widget._input_handler is not None:
                widget._input_handler.set_context_menu_active(True)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        try:
            # Phase E: Broadcast effect invalidation to ALL displays
            # Context menu on one display triggers Windows activation cascade
            # that corrupts QGraphicsEffect caches on OTHER displays
            from rendering.multi_monitor_coordinator import get_coordinator
            try:
                widget._invalidate_overlay_effects("menu_before_popup")
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            get_coordinator().invalidate_all_effects("menu_before_popup_broadcast")
            widget._context_menu.popup(global_pos)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            try:
                widget._context_menu.popup(QCursor.pos())
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    except Exception:
        logger.debug("Failed to show context menu", exc_info=True)
        widget._context_menu_active = False

def on_context_transition_selected(widget, name: str) -> None:
    """Handle transition selection from context menu."""
    try:
        if widget.settings_manager:
            trans_cfg = widget.settings_manager.get("transitions", {})
            if not isinstance(trans_cfg, dict):
                trans_cfg = {}
            
            # Handle 'Random' selection - sync with random_always checkbox
            if name == "Random":
                trans_cfg["random_always"] = True
                # Keep current type as fallback
                logger.info("Context menu: random transitions enabled")
                widget._transition_random_enabled = True
            else:
                trans_cfg["type"] = name
                trans_cfg["random_always"] = False
                logger.info("Context menu: transition changed to %s", name)
                widget._transition_random_enabled = False
                widget._transition_fallback_type = name

            # Clear any cached random selections when toggling modes
            try:
                widget.settings_manager.remove("transitions.random_choice")
                widget.settings_manager.remove("transitions.last_random_choice")
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Failed clearing cached random choices: %s", e)
            
            widget.settings_manager.set("transitions", trans_cfg)
            widget.settings_manager.save()

            if widget._context_menu is not None:
                menu_name = "Random" if widget._transition_random_enabled else widget._transition_fallback_type
                widget._context_menu.update_transition_state(menu_name, widget._transition_random_enabled)
    except Exception:
        logger.debug("Failed to set transition from context menu", exc_info=True)

def on_context_dimming_toggled(widget, enabled: bool) -> None:
    """Handle dimming toggle from context menu."""
    try:
        if widget.settings_manager:
            widget.settings_manager.set("accessibility.dimming.enabled", enabled)
            widget.settings_manager.save()
            logger.info("Context menu: dimming set to %s", enabled)
        
        # Update local GL compositor dimming
        widget._dimming_enabled = enabled
        comp = getattr(widget, "_gl_compositor", None)
        if comp is not None and hasattr(comp, "set_dimming"):
            comp.set_dimming(enabled, widget._dimming_opacity)
        
        # Emit signal to sync dimming across ALL displays
        widget.dimming_changed.emit(enabled, widget._dimming_opacity)
    except Exception:
        logger.debug("Failed to toggle dimming from context menu", exc_info=True)

def on_context_hard_exit_toggled(widget, enabled: bool) -> None:
    """Handle hard exit toggle from context menu."""
    try:
        if widget.settings_manager:
            widget.settings_manager.set("input.hard_exit", enabled)
            widget.settings_manager.save()
            logger.info("Context menu: hard exit mode set to %s", enabled)
    except Exception:
        logger.debug("Failed to toggle hard exit from context menu", exc_info=True)

def on_context_always_on_top_toggled(widget, on_top: bool) -> None:
    """Handle always on top toggle from context menu (MC mode only)."""
    try:
        widget._always_on_top = on_top
        
        # Block updates during flag change to prevent flash
        widget.setUpdatesEnabled(False)
        
        # Update window flags without hiding
        flags = widget.windowFlags()
        if on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        
        # Apply new flags - this requires re-showing the window
        widget.setWindowFlags(flags)
        
        # Restore geometry and show without flash
        if hasattr(widget, '_screen') and widget._screen is not None:
            widget.setGeometry(widget._screen.geometry())
        
        widget.show()
        
        if on_top:
            # Bring to front when enabling on-top
            widget.raise_()
        else:
            # Lower behind other windows when disabling on-top
            widget.lower()
        
        # Re-enable updates
        widget.setUpdatesEnabled(True)
        
        # Persist to settings
        if widget.settings_manager:
            widget.settings_manager.set("mc.always_on_top", on_top)
            widget.settings_manager.save()
        
        
        logger.info("[MC] Context menu: always on top set to %s", on_top)
    except Exception:
        logger.debug("Failed to toggle always on top from context menu", exc_info=True)
        # Ensure updates are re-enabled on error
        try:
            widget.setUpdatesEnabled(True)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def on_context_exit_requested(widget) -> None:
    """Handle exit request from context menu."""
    logger.info("Context menu: exit requested")
    widget._exiting = True
    widget.exit_requested.emit()

def on_input_exit_requested(widget) -> None:
    """Handle exit request from InputHandler (Phase E refactor)."""
    widget._exiting = True
    widget.exit_requested.emit()

def on_context_menu_requested(widget, global_pos: QPoint) -> None:
    """Handle context menu request from InputHandler (Phase E refactor).
    
    This method centralizes menu popup triggering through InputHandler,
    ensuring consistent effect invalidation ordering.
    """
    try:
        show_context_menu(widget, global_pos)
    except Exception:
        logger.debug("[INPUT_HANDLER] Failed to show context menu", exc_info=True)

