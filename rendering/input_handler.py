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

from PySide6.QtCore import Qt, Signal, QObject, QPoint
from PySide6.QtGui import QKeyEvent, QMouseEvent, QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
    from rendering.widget_manager import WidgetManager
    from rendering.multi_monitor_coordinator import MultiMonitorCoordinator

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


class InputHandler(QObject):
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
    
    # Signals emitted for DisplayWidget to handle
    exit_requested = Signal()
    settings_requested = Signal()
    next_image_requested = Signal()
    previous_image_requested = Signal()
    cycle_transition_requested = Signal()
    context_menu_requested = Signal(QPoint)  # Global position for menu popup
    
    # Exit threshold for mouse movement (pixels)
    MOUSE_EXIT_THRESHOLD = 10
    
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
        
        # Mouse state tracking
        self._mouse_press_pos: Optional[QPoint] = None
        self._mouse_press_time: float = 0.0
        self._last_mouse_pos: Optional[QPoint] = None
        self._initial_mouse_pos: Optional[QPoint] = None
        
        # Ctrl-held interaction mode
        self._ctrl_held: bool = False
        
        # Exit gesture state
        self._exit_gesture_active: bool = False
        self._exiting: bool = False
        
        # Context menu state
        self._context_menu_active: bool = False
        
        logger.debug("[INPUT_HANDLER] Initialized")
    
    # =========================================================================
    # Configuration
    # =========================================================================
    
    def is_hard_exit_enabled(self) -> bool:
        """Check if hard exit mode is enabled."""
        if self._settings_manager is None:
            return False
        try:
            return SettingsManager.to_bool(
                self._settings_manager.get('input.hard_exit', False), False
            )
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            return False
    
    def set_ctrl_held(self, held: bool) -> None:
        """Set Ctrl-held interaction mode."""
        self._ctrl_held = held
    
    def is_ctrl_held(self) -> bool:
        """Check if Ctrl is held (interaction mode)."""
        return self._ctrl_held
    
    def set_context_menu_active(self, active: bool) -> None:
        """Set context menu active state.
        
        Phase E: When the menu becomes inactive, triggers effect invalidation
        through the WidgetManager to ensure consistent ordering.
        """
        was_active = self._context_menu_active
        self._context_menu_active = active
        
        # Phase E: Trigger effect invalidation on menu close
        if was_active and not active:
            if self._widget_manager is not None:
                try:
                    self._widget_manager.schedule_effect_invalidation("menu_close", delay_ms=16)
                except Exception as e:
                    logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
    
    def is_context_menu_active(self) -> bool:
        """Check if context menu is currently active."""
        return self._context_menu_active
    
    # =========================================================================
    # Keyboard Event Handling
    # =========================================================================
    
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """
        Handle a key press event.
        
        Args:
            event: The key event
            
        Returns:
            True if the event was consumed, False otherwise
        """
        key = event.key()
        try:
            key_text = event.text().lower() if event.text() else ""
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            key_text = ""

        native_vk = 0
        try:
            if hasattr(event, "nativeVirtualKey"):
                native_vk = int(event.nativeVirtualKey() or 0)
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
            native_vk = 0
        
        # Log ALL key presses for diagnostics
        logger.debug("[INPUT_HANDLER] Key press: key=%s text=%s native_vk=%s", key, key_text, native_vk)
        
        # Ctrl key handling is done by DisplayWidget for halo management
        if key == Qt.Key.Key_Control:
            return False  # Let DisplayWidget handle Ctrl
        
        # Media keys should never cause exit, but we still mirror feedback
        if self._is_media_key(event):
            logger.info("[INPUT_HANDLER] Media key detected, routing for feedback")
            self._handle_media_key_feedback(event)
            logger.debug("Media key pressed - ignoring (passthrough) (key=%s)", key)
            return False
        
        # Determine current interaction mode
        ctrl_mode_active = self._ctrl_held
        hard_exit_enabled = self.is_hard_exit_enabled()
        
        # Hotkeys (always available regardless of hard-exit/ctrl state)
        if key_text == 'z' or key == Qt.Key.Key_Z or native_vk == 0x5A:
            logger.info("Z key pressed - previous image requested")
            self.previous_image_requested.emit()
            return True
        if key_text == 'x' or key == Qt.Key.Key_X or native_vk == 0x58:
            logger.info("X key pressed - next image requested")
            self.next_image_requested.emit()
            return True
        if key_text == 'c' or key == Qt.Key.Key_C or native_vk == 0x43:
            logger.info("C key pressed - cycle transition requested")
            self.cycle_transition_requested.emit()
            return True
        if key_text == 's' or key == Qt.Key.Key_S or native_vk == 0x53:
            logger.info("S key pressed - settings requested")
            self.settings_requested.emit()
            return True
        
        # Exit keys (Esc/Q) should always be honoured
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            logger.info("Exit key pressed (%s), requesting exit", key)
            self._exiting = True
            self.exit_requested.emit()
            return True
        
        # In hard-exit mode or Ctrl interaction mode, non-hotkey keys are ignored
        if hard_exit_enabled or ctrl_mode_active:
            logger.debug("Key %s ignored due to hard-exit/Ctrl interaction mode", key)
            return False
        
        # Normal mode: any other key exits
        logger.info("Non-hotkey key pressed (%s) in normal mode - requesting exit", key)
        self._exiting = True
        self.exit_requested.emit()
        return True
    
    def _is_media_key(self, event: QKeyEvent) -> bool:
        """Check if the key event is a media key."""
        key = event.key()
        
        media_keys = {
            Qt.Key.Key_MediaPlay,
            Qt.Key.Key_MediaPause,
            Qt.Key.Key_MediaTogglePlayPause,
            Qt.Key.Key_MediaNext,
            Qt.Key.Key_MediaPrevious,
            Qt.Key.Key_VolumeUp,
            Qt.Key.Key_VolumeDown,
            Qt.Key.Key_VolumeMute,
        }
        
        if key in media_keys:
            return True
        
        # Windows VK codes for media keys
        try:
            if hasattr(event, "nativeVirtualKey"):
                native_vk = int(event.nativeVirtualKey() or 0)
                media_vk_codes = {
                    0xAD,  # VK_VOLUME_MUTE
                    0xAE,  # VK_VOLUME_DOWN
                    0xAF,  # VK_VOLUME_UP
                    0xB0,  # VK_MEDIA_NEXT_TRACK
                    0xB1,  # VK_MEDIA_PREV_TRACK
                    0xB2,  # VK_MEDIA_STOP
                    0xB3,  # VK_MEDIA_PLAY_PAUSE
                }
                if native_vk in media_vk_codes:
                    return True
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        
        return False
    
    # =========================================================================
    # Mouse Event Handling
    # =========================================================================
    
    def handle_mouse_press(self, event: QMouseEvent, global_ctrl_held: bool = False) -> bool:
        """
        Handle a mouse press event.
        
        Args:
            event: The mouse event
            global_ctrl_held: Whether Ctrl is held globally across displays
            
        Returns:
            True if the event was consumed, False otherwise
        """
        ctrl_mode_active = self._ctrl_held or global_ctrl_held
        
        # Track mouse press for gesture detection
        self._mouse_press_pos = event.pos()
        self._mouse_press_time = time.time()
        
        # Right-click context menu handling
        if event.button() == Qt.MouseButton.RightButton:
            hard_exit_enabled = self.is_hard_exit_enabled()
            
            # Context menu available in hard-exit mode or with Ctrl held
            if hard_exit_enabled or ctrl_mode_active:
                global_pos = event.globalPos()
                
                # Phase E: Notify WidgetManager before menu popup
                if self._widget_manager is not None:
                    try:
                        self._widget_manager.invalidate_overlay_effects("menu_before_popup")
                    except Exception as e:
                        logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
                
                self.context_menu_requested.emit(global_pos)
                return True
        
        # Left-click handling
        if event.button() == Qt.MouseButton.LeftButton:
            # In interaction mode, let widgets handle clicks
            if ctrl_mode_active or self.is_hard_exit_enabled():
                return False  # Let DisplayWidget handle widget interaction
            
            # Normal mode: exit on click
            if not self._context_menu_active:
                logger.info("Left click in normal mode - requesting exit")
                self._exiting = True
                self.exit_requested.emit()
                return True
        
        return False
    
    def handle_mouse_move(self, event: QMouseEvent, global_ctrl_held: bool = False) -> bool:
        """
        Handle a mouse move event.
        
        Args:
            event: The mouse event
            global_ctrl_held: Whether Ctrl is held globally across displays
            
        Returns:
            True if the event was consumed (exit triggered), False otherwise
        """
        # Don't exit while context menu is active
        if self._context_menu_active:
            return False
        
        ctrl_mode_active = self._ctrl_held or global_ctrl_held
        hard_exit_enabled = self.is_hard_exit_enabled()
        
        # In hard-exit mode or Ctrl interaction mode, mouse movement doesn't exit
        if hard_exit_enabled or ctrl_mode_active:
            return False
        
        # Track initial position for exit threshold
        current_pos = event.pos()
        if self._initial_mouse_pos is None:
            self._initial_mouse_pos = current_pos
            return False
        
        # Check if we've moved beyond the exit threshold
        try:
            delta = current_pos - self._initial_mouse_pos
            distance = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
            
            if distance > self.MOUSE_EXIT_THRESHOLD:
                logger.info(
                    "Mouse moved beyond threshold (%.1f > %d) - requesting exit",
                    distance, self.MOUSE_EXIT_THRESHOLD
                )
                self._exiting = True
                self.exit_requested.emit()
                return True
        except Exception as e:
            logger.debug("[INPUT_HANDLER] Exception suppressed: %s", e)
        
        return False
    
    def handle_mouse_release(self, event: QMouseEvent, global_ctrl_held: bool = False) -> bool:
        """
        Handle a mouse release event.
        
        Args:
            event: The mouse event
            global_ctrl_held: Whether Ctrl is held globally across displays
            
        Returns:
            True if the event was consumed, False otherwise
        """
        # Reset press tracking
        self._mouse_press_pos = None
        self._mouse_press_time = 0.0
        
        return False
    
    def handle_mouse_double_click(self, event: QMouseEvent) -> bool:
        """
        Handle a mouse double click event.
        
        Triggers transition to the next image (same as 'x' key).
        """
        # Don't trigger if context menu is active
        if self._context_menu_active:
            return False

        logger.info("Double-click detected - requesting next image")
        self.next_image_requested.emit()
        return True
    
    # =========================================================================
    # State Management
    # =========================================================================
    
    def reset_initial_position(self) -> None:
        """Reset the initial mouse position for exit threshold tracking."""
        self._initial_mouse_pos = None
    
    def is_exiting(self) -> bool:
        """Check if exit has been triggered."""
        return self._exiting
    
    def set_exiting(self, exiting: bool) -> None:
        """Set the exiting state."""
        self._exiting = exiting
    
    def cleanup(self) -> None:
        """Clean up input handler state."""
        self._mouse_press_pos = None
        self._last_mouse_pos = None
        self._initial_mouse_pos = None
        self._ctrl_held = False
        self._exit_gesture_active = False
        self._context_menu_active = False
        logger.debug("[INPUT_HANDLER] Cleanup complete")

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
        hard_exit = self.is_hard_exit_enabled()
        
        if hard_exit:
            # In hard-exit mode, just clear Ctrl state but keep halo
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
    ) -> tuple:
        """
        Route clicks to interactive widgets in interaction mode.
        
        Returns:
            Tuple of (handled, reddit_handled, reddit_url)
        """
        handled = False
        reddit_handled = False
        reddit_url = None
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
                            # Legacy behaviour: handle_click already opened the URL
                            handled = True
                            reddit_handled = True
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
                    if hasattr(gw, 'handle_click'):
                        result = gw.handle_click(local_pos)
                        logger.debug("[INPUT] Gmail handle_click returned: %s", result)
                        if result:
                            handled = True
            except Exception:
                logger.debug("[INPUT] Gmail click routing failed", exc_info=True)
        
        logger.debug(
            "[INPUT] route_widget_click returning: handled=%s reddit_handled=%s reddit_url=%s",
            handled,
            reddit_handled,
            reddit_url,
        )
        return handled, reddit_handled, reddit_url

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

        if command is None:
            logger.info("[INPUT_HANDLER] Media key: command is None (key=%s), skipping", key)
            return

        # Try to get media widget from widget_manager first, then fall back to parent
        media_widget = None
        if self._widget_manager is not None:
            media_widget = self._widget_manager.get_widget("media") or self._widget_manager.get_widget("media_widget")
        if media_widget is None:
            media_widget = getattr(self._parent, "media_widget", None)
        # If still not found, search across all DisplayWidgets (multi-monitor setup)
        if media_widget is None:
            try:
                from rendering.display_widget import DisplayWidget
                for w in QApplication.topLevelWidgets():
                    if isinstance(w, DisplayWidget):
                        mw = getattr(w, "media_widget", None)
                        if mw is not None:
                            media_widget = mw
                            break
            except Exception as e:
                logger.debug("[INPUT_HANDLER] Exception searching for media widget: %s", e)
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
