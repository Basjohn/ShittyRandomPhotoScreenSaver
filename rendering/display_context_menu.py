"""Display Context Menu Handlers - Extracted from display_widget.py.

Contains context menu creation, transition selection, dimming toggle,
Interaction Mode toggle, always-on-top toggle, and exit request handlers.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QCursor

from core.logging.logger import get_logger
from rendering.custom_layout_manager import CustomLayoutManager
from rendering.transition_registry import canonicalize_transition_name
from core.settings.settings_manager import SettingsManager
from widgets.context_menu import ScreensaverContextMenu

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def _get_current_visualizer_mode(widget) -> str:
    """Read the current visualizer mode_id from the live widget."""
    try:
        vis = getattr(widget, "spotify_visualizer_widget", None)
        if vis is not None:
            return str(getattr(vis, "_vis_mode_str", "spectrum") or "spectrum")
    except Exception:
        pass
    return "spectrum"


def ensure_context_menu(
    widget,
    *,
    current_transition: str,
    random_enabled: bool,
    dimming_enabled: bool,
    interaction_mode: bool,
    current_vis: str,
) -> ScreensaverContextMenu:
    """Create and wire the shared context menu once for this display widget."""
    if widget._context_menu is None:
        widget._context_menu = ScreensaverContextMenu(
            parent=widget,
            current_transition=current_transition,
            random_enabled=random_enabled,
            dimming_enabled=dimming_enabled,
            interaction_mode_enabled=interaction_mode,
            is_mc_build=widget._is_mc_build,
            always_on_top=widget._always_on_top,
            current_visualizer=current_vis,
        )
    menu = widget._context_menu

    if not bool(getattr(widget, "_context_menu_hooks_connected", False)):
        menu.previous_requested.connect(widget.previous_requested.emit)
        menu.next_requested.connect(widget.next_requested.emit)
        menu.transition_selected.connect(widget._on_context_transition_selected)
        menu.visualizer_selected.connect(widget._on_context_visualizer_selected)
        menu.settings_requested.connect(widget.settings_requested.emit)
        menu.edit_mode_requested.connect(widget._on_context_edit_mode_requested)
        menu.save_edit_mode_requested.connect(widget._on_context_save_edit_mode_requested)
        menu.cancel_edit_mode_requested.connect(widget._on_context_cancel_edit_mode_requested)
        menu.reset_edit_mode_requested.connect(widget._on_context_reset_edit_mode_requested)
        menu.dimming_toggled.connect(widget._on_context_dimming_toggled)
        menu.interaction_mode_toggled.connect(widget._on_context_interaction_mode_toggled)
        menu.always_on_top_toggled.connect(widget._on_context_always_on_top_toggled)
        menu.exit_requested.connect(widget._on_context_exit_requested)
        try:
            menu.aboutToShow.connect(
                lambda: None if CustomLayoutManager.is_any_session_active() else widget._invalidate_overlay_effects("menu_about_to_show")
            )
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        try:
            submenu = getattr(menu, "_transition_menu", None)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            submenu = None
        if submenu is not None:
            try:
                submenu.aboutToShow.connect(
                    lambda: None if CustomLayoutManager.is_any_session_active() else widget._invalidate_overlay_effects("menu_sub_about_to_show")
                )
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            try:
                submenu.aboutToHide.connect(
                    lambda: None if CustomLayoutManager.is_any_session_active() else widget._schedule_effect_invalidation("menu_sub_after_hide")
                )
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        setattr(widget, "_context_menu_hooks_connected", True)

    return menu


def show_context_menu(widget, global_pos) -> None:
    """Show the context menu at the given global position."""
    try:
        menu_session_begun = False
        edit_mode_active = bool(CustomLayoutManager.is_any_session_active())
        current_transition, random_enabled = widget._refresh_transition_state_from_settings()
        
        interaction_mode = widget._is_interaction_mode_enabled()
        
        # Get dimming state - use dot notation for settings
        dimming_enabled = False
        if widget.settings_manager:
            dimming_enabled = SettingsManager.to_bool(
                widget.settings_manager.get("accessibility.dimming.enabled", False), False
            )
        
        # Read current visualizer mode for the submenu
        current_vis = _get_current_visualizer_mode(widget)
        
        widget._context_menu = ensure_context_menu(
            widget,
            current_transition=current_transition,
            random_enabled=random_enabled,
            dimming_enabled=dimming_enabled,
            interaction_mode=interaction_mode,
            current_vis=current_vis,
        )
        widget._context_menu.update_transition_state(current_transition, random_enabled)
        widget._context_menu.update_dimming_state(dimming_enabled)
        widget._context_menu.update_interaction_mode_state(interaction_mode)
        widget._context_menu.update_always_on_top_state(widget._always_on_top)
        widget._context_menu.update_visualizer_state(current_vis)
        widget._context_menu.update_edit_mode_state(CustomLayoutManager.is_any_session_active())
        
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
                        if not CustomLayoutManager.is_any_session_active():
                            widget._invalidate_overlay_effects("menu_after_hide")
                            widget._schedule_effect_invalidation("menu_after_hide")
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    try:
                        if CustomLayoutManager.is_any_session_active():
                            CustomLayoutManager.end_menu_interaction()
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
                    # Restore halo after menu closes if still in Interaction Mode or Ctrl mode
                    try:
                        interaction_mode = False
                        if widget.settings_manager:
                            interaction_mode = SettingsManager.to_bool(
                                widget.settings_manager.get("input.interaction_mode", False), False
                            )
                        if (
                            not CustomLayoutManager.is_any_session_active()
                            and (interaction_mode or widget._coordinator.ctrl_held)
                        ):
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
            if edit_mode_active:
                if CustomLayoutManager.has_cross_display_shells():
                    CustomLayoutManager.restore_shells_for_display(widget)
                CustomLayoutManager.begin_menu_interaction()
                menu_session_begun = True
            else:
                # Outside edit mode, keep the historical broad effect invalidation path.
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
                if menu_session_begun:
                    CustomLayoutManager.end_menu_interaction()
                    menu_session_begun = False
                if edit_mode_active:
                    CustomLayoutManager.begin_menu_interaction()
                    menu_session_begun = True
                widget._context_menu.popup(QCursor.pos())
            except Exception as e:
                if menu_session_begun:
                    try:
                        CustomLayoutManager.end_menu_interaction()
                    except Exception:
                        logger.debug("[DISPLAY_WIDGET] Failed to unwind menu interaction after popup failure", exc_info=True)
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
                canonical_name = canonicalize_transition_name(name, fallback="Crossfade")
                trans_cfg["type"] = canonical_name
                trans_cfg["random_always"] = False
                logger.info("Context menu: transition changed to %s", canonical_name)
                widget._transition_random_enabled = False
                widget._transition_fallback_type = canonical_name

            # Clear cached random selections from the dict itself so the
            # subsequent set("transitions", trans_cfg) doesn't re-introduce
            # stale values (the old remove() calls on flat keys were
            # immediately overwritten by the nested dict write).
            trans_cfg.pop("random_choice", None)
            trans_cfg.pop("last_random_choice", None)

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

def on_context_interaction_mode_toggled(widget, enabled: bool) -> None:
    """Handle Interaction Mode toggle from context menu."""
    try:
        if bool(getattr(widget, "_is_mc_build", False)):
            if widget.settings_manager:
                widget.settings_manager.set("input.interaction_mode", True)
                widget.settings_manager.save()
            logger.info("Context menu: MC build keeps interaction mode forced on")
            return
        if widget.settings_manager:
            widget.settings_manager.set("input.interaction_mode", enabled)
            widget.settings_manager.save()
            logger.info("Context menu: interaction mode set to %s", enabled)
    except Exception:
        logger.debug("Failed to toggle interaction mode from context menu", exc_info=True)

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

def on_context_visualizer_selected(widget, mode_id: str) -> None:
    """Handle visualizer mode selection from context menu.

    Routes through the visualizer widget's switch_to_mode() which uses
    the same crossfade transition path as double-click / cycle_mode.
    """
    try:
        vis = getattr(widget, "spotify_visualizer_widget", None)
        if vis is not None and hasattr(vis, "switch_to_mode"):
            vis.switch_to_mode(mode_id)
            logger.info("Context menu: visualizer mode switched to %s", mode_id)
        else:
            logger.debug("[CONTEXT_MENU] No visualizer widget available for mode switch")
    except Exception:
        logger.debug("Failed to switch visualizer mode from context menu", exc_info=True)


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

