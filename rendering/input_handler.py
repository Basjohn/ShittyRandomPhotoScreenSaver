"""
Input Handler - Extracted from DisplayWidget for better separation of concerns.

Handles all user input for DisplayWidget including mouse/keyboard events,
context menu triggers, and exit gestures.

Phase E Context: This module centralizes input handling to provide a single
choke point for context menu open/close triggers, which is critical for
deterministic effect invalidation ordering.
"""
from __future__ import annotations

import logging
import time
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeyEvent, QMouseEvent, QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from rendering.runtime_input import RuntimeInputOwner

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
    from rendering.widget_manager import WidgetManager
    from rendering.multi_monitor_coordinator import MultiMonitorCoordinator

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


class InputHandler(RuntimeInputOwner):
    """
    Handles all user input for DisplayWidget.
    
    Responsibilities:
    - Mouse event handling (press, release, move)
    - Keyboard event handling (hotkeys, exit keys)
    - Context menu trigger coordination
    - Exit gesture detection
    - Ctrl-held interaction mode management
    
    Phase E Context:
        This class provides a single choke point for context menu triggers,
        enabling deterministic effect invalidation ordering when menus open/close.
    """
    
    def __init__(
        self,
        parent: "DisplayWidget",
        settings_manager: Optional[SettingsManager] = None,
        widget_manager: Optional["WidgetManager"] = None,
    ):
        """
        Initialize the InputHandler.
        
        Args:
            parent: The DisplayWidget that owns this handler
            settings_manager: Optional SettingsManager for input settings
            widget_manager: Optional WidgetManager for effect invalidation coordination
        """
        super().__init__(parent)
        self._parent = parent
        self._settings_manager = settings_manager
        self._widget_manager = widget_manager
        self._defer_focus_restore_after_widget_click: bool = False
        
        logger.debug("[INPUT_HANDLER] Initialized")
    
    # =========================================================================
    # Configuration
    # =========================================================================
    
    def is_interaction_mode_enabled(self) -> bool:
        """Check if Interaction Mode is enabled."""
        try:
            if bool(getattr(self._parent, "_is_mc_build", False)):
                return True
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        if self._settings_manager is None:
            return False
        try:
            return SettingsManager.to_bool(
                self._settings_manager.get('input.interaction_mode', False), False
            )
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            return False
    
    def _resolve_media_widget(self):
        """Return the best media widget candidate across the active display set."""
        media_widget = None
        if self._widget_manager is not None:
            media_widget = self._widget_manager.get_widget("media") or self._widget_manager.get_widget("media_widget")
        if media_widget is None:
            media_widget = getattr(self._parent, "media_widget", None)
        if media_widget is None:
            try:
                from rendering.display_widget import DisplayWidget
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, DisplayWidget):
                        candidate = getattr(widget, "media_widget", None)
                        if candidate is not None:
                            media_widget = candidate
                            break
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception searching for media widget: %s", e)
        return media_widget

    def handle_mouse_double_click(self, event: QMouseEvent) -> bool:
        """
        Handle a mouse double click event.

        First attempts to dispatch to the topmost interactive widget under the
        cursor via WidgetManager.  If no widget consumes the event, falls back
        to triggering a transition to the next image (same as 'x' key).
        """
        # Don't trigger if context menu is active
        if self._context_menu_active:
            return False

        global_pos = event.globalPosition().toPoint()

        # Try widget dispatch first
        if self._widget_manager is not None:
            try:
                if self._widget_manager.dispatch_double_click(global_pos):
                    return True
            except Exception:
                logger.debug("[INPUT] Widget double-click dispatch failed", exc_info=True)

        logger.info("Double-click detected - requesting next image")
        self.next_image_requested.emit()
        return True
    
    def cleanup(self) -> None:
        """Clean up input handler state."""
        super().cleanup()
        self._settings_manager = None
        self._widget_manager = None
        self._parent = None
        logger.debug("[INPUT_HANDLER] Cleanup complete")

    def _handle_media_key_passthrough(self, event: QKeyEvent) -> None:
        self._handle_media_key_feedback(event)

    # =========================================================================
    # Ctrl Halo Management (Phase 2c)
    # =========================================================================

    def handle_ctrl_press(self, coordinator: "MultiMonitorCoordinator") -> Optional["DisplayWidget"]:
        """
        Handle Ctrl key press - summon halo at cursor position.
        
        Phase 2c: Centralized Ctrl halo management.
        
        Args:
            coordinator: MultiMonitorCoordinator for cross-display state
            
        Returns:
            The DisplayWidget that should own the halo, or None
        """
        coordinator.set_ctrl_held(True)
        self._ctrl_held = True
        try:
            from rendering.display_widget import DisplayWidget

            DisplayWidget._global_ctrl_held = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        
        try:
            global_pos = QCursor.pos()
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            global_pos = None

        cursor_screen = None
        if global_pos is not None:
            try:
                cursor_screen = QGuiApplication.screenAt(global_pos)
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                cursor_screen = None

        display_widgets = coordinator.get_all_instances()
        if not display_widgets:
            try:
                from rendering.display_widget import DisplayWidget

                display_widgets = [
                    w for w in QApplication.topLevelWidgets() if isinstance(w, DisplayWidget)
                ]
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                display_widgets = []

        # Reset Ctrl state and hide halos on all displays
        for w in display_widgets:
            try:
                w._ctrl_held = False
                handler = getattr(w, "_input_handler", None)
                if handler is not None:
                    try:
                        handler.set_ctrl_held(False)
                    except Exception as e:
                        logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                hint = getattr(w, "_ctrl_cursor_hint", None)
                if hint is not None:
                    try:
                        hint.cancel_animation()
                        hint.hide()
                    except Exception as e:
                        logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                continue

        target_widget = None
        target_pos = None

        # Find DisplayWidget for cursor's screen
        if cursor_screen is not None and global_pos is not None:
            for w in display_widgets:
                try:
                    if getattr(w, "_screen", None) is cursor_screen:
                        local_pos = w.mapFromGlobal(global_pos)
                        target_widget = w
                        target_pos = local_pos
                        break
                except Exception as e:
                    logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                    continue

        # Fallback: geometry-based lookup
        if target_widget is None and global_pos is not None:
            for w in display_widgets:
                try:
                    local_pos = w.mapFromGlobal(global_pos)
                    if w.rect().contains(local_pos):
                        target_widget = w
                        target_pos = local_pos
                        break
                except Exception as e:
                    logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                    continue

        # Final fallback: use parent
        if target_widget is None:
            target_widget = self._parent
            try:
                if global_pos is not None:
                    target_pos = self._parent.mapFromGlobal(global_pos)
                else:
                    target_pos = self._parent.rect().center()
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                target_pos = self._parent.rect().center()

        coordinator.set_halo_owner(target_widget)
        target_widget._ctrl_held = True
        target_handler = getattr(target_widget, "_input_handler", None)
        if target_handler is not None:
            try:
                target_handler.set_ctrl_held(True)
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        try:
            from rendering.display_widget import DisplayWidget

            DisplayWidget._halo_owner = target_widget  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        
        logger.debug("[CTRL HALO] Ctrl pressed; target screen=%s pos=%s",
                     getattr(target_widget, "screen_index", "?"), target_pos)
        
        # Show halo on target widget
        try:
            target_widget._show_ctrl_cursor_hint(target_pos, mode="fade_in")
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        
        return target_widget

    def handle_ctrl_release(self, coordinator: "MultiMonitorCoordinator") -> None:
        """
        Handle Ctrl key release - fade out halo.
        
        Phase 2c: Centralized Ctrl halo management.
        
        Args:
            coordinator: MultiMonitorCoordinator for cross-display state
        """
        interaction_mode = self.is_interaction_mode_enabled()

        if interaction_mode:
            # In Interaction Mode, just clear Ctrl state but keep halo
            coordinator.set_ctrl_held(False)
            self._ctrl_held = False
            try:
                from rendering.display_widget import DisplayWidget

                DisplayWidget._global_ctrl_held = False  # type: ignore[attr-defined]
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            return

        # Clear global Ctrl state and fade out halo
        coordinator.set_ctrl_held(False)
        owner = coordinator.clear_halo_owner()
        self._ctrl_held = False

        try:
            from rendering.display_widget import DisplayWidget

            DisplayWidget._global_ctrl_held = False  # type: ignore[attr-defined]
            DisplayWidget._halo_owner = None  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)

        try:
            global_pos = QCursor.pos()
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            global_pos = None

        display_widgets = coordinator.get_all_instances()
        if not display_widgets:
            try:
                from rendering.display_widget import DisplayWidget

                display_widgets = [
                    w for w in QApplication.topLevelWidgets() if isinstance(w, DisplayWidget)
                ]
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                display_widgets = []

        # Fade out halo on owner (owner may not be registered in coordinator during tests).
        if owner is not None:
            try:
                owner._ctrl_held = False
                owner_handler = getattr(owner, "_input_handler", None)
                if owner_handler is not None:
                    try:
                        owner_handler.set_ctrl_held(False)
                    except Exception as e:
                        logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            try:
                hint = getattr(owner, "_ctrl_cursor_hint", None)
                if hint is not None and hint.isVisible():
                    try:
                        if global_pos is not None:
                            local_pos = owner.mapFromGlobal(global_pos)
                        else:
                            local_pos = hint.pos() + hint.rect().center()
                    except Exception as e:
                        logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                        local_pos = hint.pos() + hint.rect().center()
                    logger.debug("[CTRL HALO] Ctrl released; fading out at %s", local_pos)
                    try:
                        owner._show_ctrl_cursor_hint(local_pos, mode="fade_out")
                    except Exception as e:
                        logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)

        # Clear Ctrl state on all other displays
        for w in display_widgets:
            if w is owner:
                continue
            try:
                w._ctrl_held = False
                handler = getattr(w, "_input_handler", None)
                if handler is not None:
                    try:
                        handler.set_ctrl_held(False)
                    except Exception as e:
                        logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                hint = getattr(w, "_ctrl_cursor_hint", None)
                if hint is not None:
                    try:
                        hint.cancel_animation()
                        hint.hide()
                    except Exception as e:
                        logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                continue

    # =========================================================================
    # Widget Click Routing
    # =========================================================================

    def route_widget_click(
        self,
        event: QMouseEvent,
        spotify_volume_widget,
        media_widget,
        reddit_widget,
        reddit2_widget,
        gmail_widget=None,
        spotify_visualizer_widget=None,
        steam_widgets=(),
        weather_widget=None,
    ) -> tuple:
        """
        Route clicks to interactive widgets in interaction mode.
        
        Returns:
            Tuple of (handled, reddit_handled, reddit_url)
        """
        handled = False
        reddit_handled = False
        reddit_url = None
        self._defer_focus_restore_after_widget_click = False
        pos = event.pos()
        button = event.button()
        
        # Spotify volume widget
        if spotify_volume_widget is not None:
            try:
                vw = spotify_volume_widget
                if vw.isVisible() and vw.geometry().contains(pos):
                    geom = vw.geometry()
                    local_pos = QPoint(pos.x() - geom.x(), pos.y() - geom.y())
                    if hasattr(vw, 'handle_press') and vw.handle_press(local_pos, button):
                        handled = True
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        
        # Mute button widget
        if not handled:
            try:
                mute_btn = getattr(self._parent, "mute_button_widget", None) if self._parent else None
                if mute_btn is not None and mute_btn.isVisible() and mute_btn.geometry().contains(pos):
                    if hasattr(mute_btn, 'handle_click'):
                        handled = mute_btn.handle_click()
                        logger.debug("[MUTE_BTN] handle_click returned: %s", handled)
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)

        # Media widget transport controls
        if not handled and media_widget is not None:
            try:
                mw = media_widget
                if mw.isVisible() and mw.geometry().contains(pos):
                    from PySide6.QtCore import Qt as _Qt
                    if button == _Qt.MouseButton.LeftButton:
                        handled = self._route_media_left_click(mw, pos)
                    elif button == _Qt.MouseButton.RightButton:
                        handled = self._invoke_media_command(
                            mw,
                            "next",
                            source="mouse:right",
                        )
                    elif button == _Qt.MouseButton.MiddleButton:
                        handled = self._invoke_media_command(
                            mw,
                            "prev",
                            source="mouse:middle",
                        )
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)

        # Spotify visualizer preset shortcuts (middle=next, XButton1/back=previous)
        if not handled and spotify_visualizer_widget is not None:
            try:
                vis = spotify_visualizer_widget
                if vis.isVisible() and vis.geometry().contains(pos):
                    if button in (
                        Qt.MouseButton.MiddleButton,
                        Qt.MouseButton.XButton1,
                        Qt.MouseButton.BackButton,
                    ):
                        handler = getattr(vis, 'handle_mouse_button', None)
                        if callable(handler):
                            handled = bool(handler(button))
            except Exception:
                logger.debug("[INPUT] Visualizer click routing failed", exc_info=True)

        # Steam card affordances (unfinished cards may still be dev-gated).
        if not handled:
            for sw in tuple(steam_widgets or ()):
                if sw is None:
                    continue
                try:
                    if sw.isVisible() and sw.geometry().contains(pos):
                        geom = sw.geometry()
                        local_pos = QPoint(pos.x() - geom.x(), pos.y() - geom.y())
                        target = None
                        if hasattr(sw, "settings_action_at"):
                            target = sw.settings_action_at(local_pos)
                        if target and hasattr(sw, "handle_click") and sw.handle_click(local_pos):
                            handled = True
                            self._prime_settings_section(
                                "steam",
                                bucket="connection" if target == "steam_connection" else None,
                            )
                            self.settings_requested.emit()
                            break
                except Exception:
                    logger.debug("[INPUT] Steam click routing failed", exc_info=True)

        # Weather missing-location affordance uses the same centralized Settings route.
        if not handled and weather_widget is not None:
            try:
                ww = weather_widget
                if ww.isVisible() and ww.geometry().contains(pos):
                    geom = ww.geometry()
                    local_pos = QPoint(pos.x() - geom.x(), pos.y() - geom.y())
                    target = ww.settings_action_at(local_pos) if hasattr(ww, "settings_action_at") else None
                    if target and hasattr(ww, "handle_click") and ww.handle_click(local_pos):
                        handled = True
                        self._prime_settings_section("weather", bucket="source_layout")
                        self.settings_requested.emit()
            except Exception:
                logger.debug("[INPUT] Weather click routing failed", exc_info=True)
        
        # Reddit widgets
        for rw in [reddit_widget, reddit2_widget]:
            if handled or rw is None:
                continue
            try:
                if rw.isVisible() and rw.geometry().contains(pos):
                    geom = rw.geometry()
                    local_pos = QPoint(pos.x() - geom.x(), pos.y() - geom.y())
                    url = None
                    if hasattr(rw, "resolve_click_target"):
                        try:
                            url = rw.resolve_click_target(local_pos)
                        except Exception:
                            logger.debug("[INPUT] resolve_click_target failed", exc_info=True)
                    if not url and hasattr(rw, "handle_click"):
                        result = rw.handle_click(local_pos)
                        logger.debug("[INPUT] Reddit fallback handle_click returned: %s", result)
                        if isinstance(result, str) and result:
                            url = result
                        elif result:
                            # Non-link Reddit controls, such as the refresh
                            # spiral, can consume the click without producing
                            # a URL. Do not mark these as reddit_handled or
                            # the main build will exit as though a link was
                            # clicked.
                            handled = True
                            break
                    if url:
                        handled = True
                        reddit_handled = True
                        reddit_url = url
            except Exception:
                logger.debug("[INPUT] Reddit click routing failed", exc_info=True)
        
        # Gmail widget
        if not handled and gmail_widget is not None:
            try:
                gw = gmail_widget
                if gw.isVisible() and gw.geometry().contains(pos):
                    geom = gw.geometry()
                    local_pos = QPoint(pos.x() - geom.x(), pos.y() - geom.y())
                    url = None
                    if hasattr(gw, "resolve_click_target"):
                        try:
                            url = gw.resolve_click_target(local_pos)
                        except Exception:
                            logger.debug("[INPUT] Gmail resolve_click_target failed", exc_info=True)
                    if url:
                        handled = True
                        reddit_handled = True
                        reddit_url = url
                        logger.debug("[INPUT] Gmail resolved central URL click: %s", url)
                    elif hasattr(gw, 'handle_click'):
                        action_menu_point = False
                        if hasattr(gw, "is_action_menu_point"):
                            try:
                                action_menu_point = bool(gw.is_action_menu_point(local_pos))
                            except Exception:
                                logger.debug("[INPUT] Gmail action-menu hit test failed", exc_info=True)
                        result = gw.handle_click(local_pos)
                        logger.debug("[INPUT] Gmail handle_click returned: %s", result)
                        if result:
                            handled = True
                            if action_menu_point:
                                self._defer_focus_restore_after_widget_click = True
            except Exception:
                logger.debug("[INPUT] Gmail click routing failed", exc_info=True)
        
        logger.debug(
            "[INPUT] route_widget_click returning: handled=%s reddit_handled=%s reddit_url=%s",
            handled,
            reddit_handled,
            reddit_url,
        )
        return handled, reddit_handled, reddit_url

    def _prime_settings_section(self, section_id: str, *, bucket: str | None = None) -> None:
        """Ask the ordinary Settings dialog to open on a widget sub-section."""

        if self._settings_manager is None or not section_id:
            return
        try:
            raw_state = self._settings_manager.get("ui.tab_state", {})
            tab_state = dict(raw_state) if isinstance(raw_state, dict) else {}
            raw_widgets = tab_state.get("widgets", {})
            widgets_state = dict(raw_widgets) if isinstance(raw_widgets, dict) else {}
            raw_view_state = widgets_state.get("view_state", {})
            view_state = dict(raw_view_state) if isinstance(raw_view_state, dict) else {}
            view_state["subtab_id"] = section_id
            widgets_state["view_state"] = view_state
            tab_state["widgets"] = widgets_state
            self._settings_manager.set("ui.tab_state", tab_state)
            if bucket:
                raw_buckets = self._settings_manager.get("ui.widget_bucket_states", {})
                bucket_states = dict(raw_buckets) if isinstance(raw_buckets, dict) else {}
                bucket_states[f"{section_id}:{bucket}"] = True
                self._settings_manager.set("ui.widget_bucket_states", bucket_states)
            # SettingsDialog._tab_keys currently keeps Widgets at index 3.
            # This mirrors the existing persisted navigation seam instead of
            # adding a widget-local Settings launcher.
            self._settings_manager.set("ui.last_tab_index", 3)
        except Exception:
            logger.debug("[INPUT] Failed to prime Settings section %s", section_id, exc_info=True)

    def _route_media_left_click(self, mw, pos: QPoint) -> bool:
        """Route left click to media widget transport controls."""
        try:
            geom = mw.geometry()
            local_point = QPoint(pos.x() - geom.x(), pos.y() - geom.y())
            resolver = getattr(mw, "resolve_control_hit", None)
            if resolver is None:
                return False
            key = resolver(local_point)
            if key is None:
                return False
            return self._invoke_media_command(
                mw,
                key,
                source="mouse:left",
            )
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        return False

    def _invoke_media_command(
        self,
        media_widget,
        key: str,
        *,
        source: str,
        execute: bool = True,
    ) -> bool:
        logger.debug("[INPUT_HANDLER] _invoke_media_command ENTRY: key=%s source=%s execute=%s", key, source, execute)
        if media_widget is None or not hasattr(media_widget, "handle_transport_command"):
            logger.debug("[INPUT_HANDLER] _invoke_media_command: no widget or method")
            return False
        try:
            result = bool(
                media_widget.handle_transport_command(
                    key,
                    source=source,
                    execute=execute,
                )
            )
            logger.debug("[INPUT_HANDLER] _invoke_media_command EXIT: result=%s", result)
            return result
        except Exception:
            logger.debug("[INPUT_HANDLER] Media command dispatch failed", exc_info=True)
            return False

    def _handle_media_key_feedback(self, event: QKeyEvent) -> None:
        key = event.key()
        logger.debug("[INPUT_HANDLER] _handle_media_key_feedback: key=%s", key)
        command = None
        source = "media_key"
        native_vk = 0  # set early so volume-key check below always has a value

        if key in (
            Qt.Key.Key_MediaPlay,
            Qt.Key.Key_MediaPause,
            Qt.Key.Key_MediaTogglePlayPause,
            Qt.Key.Key_MediaStop,
        ):
            command = "play"
        elif key == Qt.Key.Key_MediaNext:
            command = "next"
        elif key == Qt.Key.Key_MediaPrevious:
            command = "prev"

        if command is None:
            try:
                if hasattr(event, "nativeVirtualKey"):
                    native_vk = int(event.nativeVirtualKey() or 0)
                else:
                    native_vk = 0
            except Exception as exc:
                logger.debug("[INPUT_HANDLER] Exception suppressed: %s", exc)
                native_vk = 0

            native_map = {
                0xB3: "play",  # VK_MEDIA_PLAY_PAUSE
                0xB0: "next",
                0xB1: "prev",
            }
            command = native_map.get(native_vk)
            source = f"media_key_vk:{native_vk}" if native_vk else source
        else:
            source = f"media_key:{int(key)}"

        # Volume mute/up/down: OS already handled the actual audio change.
        # We just need to refresh the mute button UI to reflect the new state.
        is_volume_key = (
            key in (Qt.Key.Key_VolumeMute, Qt.Key.Key_VolumeUp, Qt.Key.Key_VolumeDown)
            or (command is None and native_vk in (0xAD, 0xAE, 0xAF))
        )
        if is_volume_key:
            self._refresh_mute_button_state()
            if command is None:
                return  # pure volume key, no media command to route

        if command is None:
            logger.info("[INPUT_HANDLER] Media key: command is None (key=%s), skipping", key)
            return

        from rendering.media_command_ingress import (
            claim_external_media_command,
            wake_media_visualizers,
        )

        if not claim_external_media_command(command, route=f"qt:{source}"):
            return

        wake_media_visualizers(self._parent)
        logger.info(
            "[INPUT_HANDLER] Media key detected, routing for feedback: command=%s source=%s",
            command,
            source,
        )
        media_widget = self._resolve_media_widget()
        logger.debug("[INPUT_HANDLER] Media widget lookup: widget=%s", media_widget)
        if media_widget is None:
            logger.debug("[INPUT_HANDLER] Media key %s ignored (no media widget)", command)
            return
        
        logger.debug("[INPUT_HANDLER] Media key %s detected, routing to widget", command)
        
        # For media keys, the OS already executed the command.
        # We just need to trigger optimistic UI updates and feedback.
        # Use handle_transport_command with execute=False to avoid double-execution
        # but still get the optimistic UI updates and feedback animation.
        handled = self._invoke_media_command(
            media_widget,
            command,
            source=source,
            execute=False,  # OS already handled it
        )
        
        if handled:
            logger.info("[INPUT_HANDLER] Media key %s handled successfully", command)
        else:
            logger.debug("[INPUT_HANDLER] Media key %s not handled by media widget", command)

    def _refresh_mute_button_state(self) -> None:
        """Poll the mute button to refresh its UI after the OS handles a volume key."""
        mute_btn = None
        # Try parent (DisplayWidget) first
        if self._parent is not None:
            mute_btn = getattr(self._parent, "mute_button_widget", None)
        # Fall back to widget_manager
        if mute_btn is None and self._widget_manager is not None:
            mute_btn = self._widget_manager.get_widget("mute_button")
        if mute_btn is not None and hasattr(mute_btn, 'poll_mute_state'):
            try:
                mute_btn.poll_mute_state()
                logger.debug("[INPUT_HANDLER] Refreshed mute button state after volume key")
            except Exception as exc:
                logger.debug("[INPUT_HANDLER] Mute button refresh failed: %s", exc)

    def route_volume_drag(self, pos: QPoint, spotify_volume_widget) -> bool:
        """Route drag events to Spotify volume widget."""
        if spotify_volume_widget is None or not spotify_volume_widget.isVisible():
            return False
        try:
            geom = spotify_volume_widget.geometry()
            local_pos = QPoint(pos.x() - geom.x(), pos.y() - geom.y())
            if hasattr(spotify_volume_widget, 'handle_drag'):
                spotify_volume_widget.handle_drag(local_pos)
                return True
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        return False

    def route_volume_release(self, spotify_volume_widget) -> bool:
        """Route release events to Spotify volume widget."""
        if spotify_volume_widget is None:
            return False
        try:
            if hasattr(spotify_volume_widget, 'handle_release'):
                spotify_volume_widget.handle_release()
                return True
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        return False

    def route_wheel_event(
        self,
        pos: QPoint,
        delta_y: int,
        spotify_volume_widget,
        media_widget,
        spotify_visualizer_widget,
    ) -> bool:
        """
        Route wheel events to Spotify volume widget in interaction mode.
        
        Returns:
            True if wheel was handled
        """
        vw = spotify_volume_widget
        if vw is None or not vw.isVisible():
            logger.debug("[WHEEL] Volume widget not available or hidden; skipping wheel routing")
            return False
        
        try:
            geom_vol = vw.geometry()
            local_pos = QPoint(pos.x() - geom_vol.x(), pos.y() - geom_vol.y())
            logger.debug(
                "[WHEEL] Routing wheel to volume widget: global=%s local=%s delta=%d",
                pos,
                local_pos,
                delta_y,
            )
            if hasattr(vw, "handle_wheel") and vw.handle_wheel(local_pos, delta_y):
                logger.debug("[WHEEL] Volume widget handled wheel event")
                return True
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        
        logger.debug("[WHEEL] Volume widget ignored wheel event")
        return False
