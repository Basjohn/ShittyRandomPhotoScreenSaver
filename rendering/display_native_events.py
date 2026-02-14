"""Display Native Event Handlers - Extracted from display_widget.py.

Contains Win32 native event handling (WM_APPCOMMAND, WM_INPUT, WM_ACTIVATE),
global event filter for cursor halo management, and related helpers.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import sys
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget, QApplication

from core.logging.logger import get_logger
from rendering.display_widget import (
    DisplayWidget,
    WM_APPCOMMAND,
    _APPCOMMAND_NAMES,
    _USER32,
)
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

# Windows message constants for media key interception
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Media VK codes that must be forwarded to DefWindowProcW so Windows
# generates WM_APPCOMMAND and propagates to the shell hook (Spotify etc.)
_MEDIA_VK_CODES = {
    0xAD,  # VK_VOLUME_MUTE
    0xAE,  # VK_VOLUME_DOWN
    0xAF,  # VK_VOLUME_UP
    0xB0,  # VK_MEDIA_NEXT_TRACK
    0xB1,  # VK_MEDIA_PREV_TRACK
    0xB2,  # VK_MEDIA_STOP
    0xB3,  # VK_MEDIA_PLAY_PAUSE
}

if TYPE_CHECKING:
    from rendering.multi_monitor_coordinator import MultiMonitorCoordinator

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")

# Import Raw Input for media key detection (Windows only)
if sys.platform == "win32":
    try:
        from core.windows.media_key_rawinput import (
            get_raw_input_instance,
            WM_INPUT,
        )
        _RAW_INPUT_AVAILABLE = True
    except Exception:
        _RAW_INPUT_AVAILABLE = False
else:
    _RAW_INPUT_AVAILABLE = False


def handle_nativeEvent(widget, eventType, message):
    try:
        if sys.platform != "win32":
            return QWidget.nativeEvent(widget, eventType, message)

        msg = extract_win_msg(widget, message)
        if msg is None:
            return QWidget.nativeEvent(widget, eventType, message)

        mid = int(getattr(msg, "message", 0) or 0)

        # -----------------------------------------------------------
        # Media key WM_KEYDOWN / WM_KEYUP interception
        # -----------------------------------------------------------
        # Qt normally swallows WM_KEYDOWN for media VK codes and
        # converts them to QKeyEvent *without* calling DefWindowProcW.
        # That breaks the standard Windows chain:
        #   WM_KEYDOWN → DefWindowProc → WM_APPCOMMAND → shell hook → Spotify
        # Fix: intercept media VK key messages, call DefWindowProcW
        # ourselves, and return True so Qt does NOT eat them.
        if mid in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
            try:
                wparam = int(getattr(msg, "wParam", 0) or 0)
                if wparam in _MEDIA_VK_CODES and _USER32 is not None:
                    hwnd = int(getattr(msg, "hwnd", 0) or 0)
                    lparam = int(getattr(msg, "lParam", 0) or 0)
                    if hwnd:
                        # Trigger UI feedback for key-down only
                        if mid in (WM_KEYDOWN, WM_SYSKEYDOWN):
                            _dispatch_media_vk_feedback(widget, wparam)
                        result = int(_USER32.DefWindowProcW(hwnd, mid, wparam, lparam))
                        return True, result
            except Exception as e:
                logger.debug("[NATIVE] Media VK interception error: %s", e)

        # -----------------------------------------------------------
        # WM_APPCOMMAND — dispatch feedback + propagate via DefWindowProcW
        # -----------------------------------------------------------
        if mid == WM_APPCOMMAND:
            handled, result = handle_win_appcommand(widget, msg)
            if handled:
                return True, result

        # Handle Raw Input for media key detection (non-blocking)
        if mid == WM_INPUT and _RAW_INPUT_AVAILABLE:
            try:
                hwnd = int(getattr(msg, "hwnd", 0) or 0)
                wparam = int(getattr(msg, "wParam", 0) or 0)
                lparam = int(getattr(msg, "lParam", 0) or 0)
                
                # CRITICAL: Check if input is from foreground (RIM_INPUT = 0)
                # Windows REQUIRES DefWindowProc for RIM_INPUT cleanup
                is_foreground = (wparam & 0xFF) == 0  # RIM_INPUT = 0
                
                raw_input = get_raw_input_instance()
                if not raw_input.is_registered():
                    # Initialize raw input registration
                    def on_media_key(command: str) -> None:
                        """Callback when media key detected - trigger visualizer wake."""
                        try:
                            # Find Spotify visualizer and wake it
                            for vis_w in widget.findChildren(SpotifyVisualizerWidget):
                                if hasattr(vis_w, '_trigger_wake'):
                                    vis_w._trigger_wake()
                                    break
                            # Also dispatch to media widget for UI feedback
                            mw = getattr(widget, "media_widget", None)
                            if mw and hasattr(mw, "handle_transport_command"):
                                mw.handle_transport_command(command, source="media_key", execute=False)
                        except Exception:
                            pass
                    
                    raw_input.register(hwnd, on_media_key)
                
                # Process the raw input message (detect media keys)
                raw_input.process_wm_input(wparam, lparam)
                
                # CRITICAL: For RIM_INPUT (foreground), MUST call DefWindowProc
                # This allows Windows to clean up and pass the input to other apps
                if is_foreground and _USER32 is not None and hwnd:
                    try:
                        result = int(_USER32.DefWindowProcW(hwnd, WM_INPUT, wparam, lparam))
                        return True, result  # Indicate we handled it (including cleanup)
                    except Exception:
                        pass
                
                # For RIM_INPUTSINK or if DefWindowProc fails, 
                # return False to let Qt handle it normally
                return False, 0
                
            except Exception:
                pass  # Ignore raw input errors

        if not win_diag_logger.isEnabledFor(logging.DEBUG):
            return QWidget.nativeEvent(widget, eventType, message)

        names = {
            0x0006: "WM_ACTIVATE",
            0x0086: "WM_NCACTIVATE",
            0x0046: "WM_WINDOWPOSCHANGING",
            0x0047: "WM_WINDOWPOSCHANGED",
            0x007C: "WM_STYLECHANGING",
            0x007D: "WM_STYLECHANGED",
            0x0014: "WM_ERASEBKGND",
            0x000B: "WM_SETREDRAW",
            WM_APPCOMMAND: "WM_APPCOMMAND",
        }

        name = names.get(mid)
        if name is not None:
            try:
                hwnd = int(getattr(msg, "hwnd", 0) or 0)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                hwnd = 0
            try:
                wparam = int(getattr(msg, "wParam", 0) or 0)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                wparam = 0
            try:
                lparam = int(getattr(msg, "lParam", 0) or 0)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                lparam = 0

            extra = f"msg={name} wParam={wparam} lParam={lparam} hwnd={hex(hwnd) if hwnd else '?'}"
            try:
                for inst in DisplayWidget.get_all_instances():
                    try:
                        inst._debug_window_state("nativeEvent", extra=extra)
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                widget._debug_window_state("nativeEvent", extra=extra)

    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    return QWidget.nativeEvent(widget, eventType, message)

def extract_win_msg(widget, raw_message):
    try:
        msg_ptr = int(raw_message)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return None
    if msg_ptr == 0:
        return None
    try:
        return ctypes.cast(msg_ptr, ctypes.POINTER(wintypes.MSG)).contents
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return None

def handle_win_appcommand(widget, msg) -> tuple[bool, int]:
    try:
        hwnd = int(getattr(msg, "hwnd", 0) or 0)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        hwnd = 0
    try:
        wparam = int(getattr(msg, "wParam", 0) or 0)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        wparam = 0
    try:
        lparam = int(getattr(msg, "lParam", 0) or 0)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        lparam = 0

    command = (lparam >> 16) & 0xFFFF
    command_name = _APPCOMMAND_NAMES.get(command, f"APPCOMMAND_{command:04x}")
    device = lparam & 0xFFFF
    window_mode = getattr(widget, "_mc_window_flag_mode", None) or "standard"

    target_logger = win_diag_logger if win_diag_logger.isEnabledFor(logging.DEBUG) else logger
    target_logger.debug(
        "[WIN_APPCOMMAND] mode=%s cmd=%s (%#06x) device=%#06x wParam=%s lParam=%#010x",
        window_mode,
        command_name,
        command,
        device,
        wparam,
        lparam,
    )

    # Always dispatch for visual feedback, but ALWAYS pass through to OS
    # by calling DefWindowProcW. The media keys should never be blocked.
    dispatch_appcommand(widget, command, command_name)

    # CRITICAL: Always call DefWindowProcW to ensure media keys pass through
    # to the OS and other applications like Spotify
    if _USER32 is not None and hwnd:
        try:
            result = int(_USER32.DefWindowProcW(hwnd, WM_APPCOMMAND, wparam, lparam))
            return True, result
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            target_logger.debug("[WIN_APPCOMMAND] DefWindowProcW failed", exc_info=True)

    return False, 0

def _dispatch_media_vk_feedback(widget, vk_code: int) -> None:
    """Trigger media widget UI feedback for a media VK key-down event."""
    _VK_TO_COMMAND = {
        0xB3: "play",   # VK_MEDIA_PLAY_PAUSE
        0xB0: "next",   # VK_MEDIA_NEXT_TRACK
        0xB1: "prev",   # VK_MEDIA_PREV_TRACK
        0xB2: "play",   # VK_MEDIA_STOP  (treat as play/pause toggle for feedback)
    }
    command = _VK_TO_COMMAND.get(vk_code)
    if command is None:
        # Volume keys — refresh mute button state after a short delay
        # (OS processes the volume change; we just update the UI)
        if vk_code in (0xAD, 0xAE, 0xAF):
            try:
                mute_btn = getattr(widget, "mute_button_widget", None)
                if mute_btn is not None and hasattr(mute_btn, "poll_mute_state"):
                    QTimer.singleShot(80, mute_btn.poll_mute_state)
            except Exception:
                pass
        return

    media_widget = getattr(widget, "media_widget", None)
    if media_widget is None:
        return
    try:
        media_widget.handle_transport_command(
            command, source=f"media_vk:{vk_code:#04x}", execute=False
        )
        logger.debug("[NATIVE] Media VK feedback: vk=%#04x cmd=%s", vk_code, command)
    except Exception as e:
        logger.debug("[NATIVE] Media VK feedback error: %s", e)

    # Wake Spotify visualizer
    try:
        for vis_w in widget.findChildren(SpotifyVisualizerWidget):
            if hasattr(vis_w, "_trigger_wake"):
                vis_w._trigger_wake()
                break
    except Exception:
        pass


def dispatch_appcommand_for_feedback(widget, msg) -> None:
    """Lightweight appcommand handler that only triggers visual feedback without blocking."""
    try:
        lparam = int(getattr(msg, "lParam", 0) or 0)
        command = (lparam >> 16) & 0xFFFF
        command_name = _APPCOMMAND_NAMES.get(command, f"APPCOMMAND_{command:04x}")
        
        # Just dispatch for visual feedback - don't block
        dispatch_appcommand(widget, command, command_name)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] _dispatch_appcommand_for_feedback error: %s", e)

def dispatch_appcommand(widget, command: int, command_name: str) -> bool:
    media_widget = getattr(widget, "media_widget", None)
    if media_widget is None:
        return False

    mapping = {
        0x0005: "next",  # APPCOMMAND_MEDIA_NEXTTRACK
        0x0006: "prev",  # APPCOMMAND_MEDIA_PREVIOUS
        0x0007: "play",  # treat stop as play/pause toggle for feedback
        0x000E: "play",  # APPCOMMAND_MEDIA_PLAY_PAUSE
        0x0008: "play",
        0x0009: "play",
    }
    key = mapping.get(command)
    if key is None:
        return False

    source = f"appcommand:{command_name}"
    try:
        return bool(
            media_widget.handle_transport_command(
                key,
                source=source,
                execute=False,
            )
        )
    except Exception:
        logger.debug("[DISPLAY_WIDGET] Appcommand dispatch failed", exc_info=True)
        return False

def handle_eventFilter(widget, watched, event):
    """Global event filter to keep the Ctrl halo responsive over children."""
    try:
        owning_display = None
        if isinstance(watched, DisplayWidget):
            owning_display = watched
        elif isinstance(watched, QWidget):
            try:
                top_level = watched.window()
            except Exception:
                top_level = None
            if isinstance(top_level, DisplayWidget):
                owning_display = top_level
        # Bail out for widgets that aren't part of any DisplayWidget tree (e.g. settings dialog)
        if owning_display is None:
            return QWidget.eventFilter(widget, watched, event)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return QWidget.eventFilter(widget, watched, event)
    try:
        coordinator = widget._coordinator
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        coordinator = None

    try:
        settings_dialog_active = False
        if coordinator is not None:
            try:
                settings_dialog_active = bool(coordinator.settings_dialog_active)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                settings_dialog_active = False

        if settings_dialog_active:
            # Settings dialog suppresses halo/activity entirely.
            try:
                owner = coordinator.halo_owner if coordinator is not None else None
                if owner is not None:
                    owner._hide_ctrl_cursor_hint(immediate=True)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            return QWidget.eventFilter(widget, watched, event)

        if event is not None and event.type() == QEvent.Type.KeyPress:
            try:
                key_event = event  # QKeyEvent
                target = widget._coordinator.focus_owner
                if target is None or not isinstance(target, DisplayWidget) or not target.isVisible():
                    target = widget
                if isinstance(target, DisplayWidget) and target.isVisible():
                    if key_event.key() == Qt.Key.Key_Control:
                        if target._input_handler is not None:
                            try:
                                target._input_handler.handle_ctrl_press(widget._coordinator)
                                event.accept()
                                return True
                            except Exception:
                                logger.debug("[KEY] Ctrl press delegation failed", exc_info=True)
                        event.accept()
                        return True
                    if target._input_handler is not None:
                        try:
                            if target._input_handler.handle_key_press(key_event):
                                if target._input_handler.is_exiting():
                                    target._exiting = True
                                event.accept()
                                return True
                        except Exception:
                            logger.debug("[KEY] Key press delegation failed", exc_info=True)
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        if event is not None and event.type() == QEvent.Type.KeyRelease:
            try:
                key_event = event  # QKeyEvent
                if key_event.key() == Qt.Key.Key_Control:
                    target = widget._coordinator.focus_owner
                    if target is None or not isinstance(target, DisplayWidget) or not target.isVisible():
                        target = widget
                    if isinstance(target, DisplayWidget) and target.isVisible():
                        if target._input_handler is not None:
                            try:
                                target._input_handler.handle_ctrl_release(widget._coordinator)
                                event.accept()
                                return True
                            except Exception:
                                logger.debug("[KEY] Ctrl release delegation failed", exc_info=True)
                        event.accept()
                        return True
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        if event is not None and event.type() == QEvent.Type.MouseMove:
            hard_exit = False
            try:
                hard_exit = widget._is_hard_exit_enabled()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                hard_exit = False

            # Phase 5: Use coordinator for global Ctrl state and halo ownership
            ctrl_held = bool(widget._coordinator.ctrl_held or getattr(DisplayWidget, "_global_ctrl_held", False))
            if ctrl_held or hard_exit:
                # Use global cursor position so we track even when the
                # event originates from a child widget. Resolve the
                # DisplayWidget that owns the halo based on the cursor's
                # current QScreen to behave correctly across mixed-DPI
                # multi-monitor layouts.
                global_pos = QCursor.pos()

                from PySide6.QtGui import QGuiApplication

                cursor_screen = None
                try:
                    cursor_screen = QGuiApplication.screenAt(global_pos)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    cursor_screen = None

                owner = widget._coordinator.halo_owner
                if owner is None:
                    owner = getattr(DisplayWidget, "_halo_owner", None)

                # If the cursor moved to a different screen, migrate the
                # halo owner to the DisplayWidget bound to that screen.
                if cursor_screen is not None:
                    screen_changed = (
                        owner is None
                        or getattr(owner, "_screen", None) is not cursor_screen
                    )
                    if screen_changed:
                        # Phase 5: Use coordinator for instance lookup
                        new_owner = widget._coordinator.get_instance_for_screen(cursor_screen)
                        
                        # Fallback to iteration only if cache miss (shouldn't happen)
                        if new_owner is None:
                            try:
                                widgets = QApplication.topLevelWidgets()
                            except Exception as e:
                                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                                widgets = []

                            for w in widgets:
                                try:
                                    if not isinstance(w, DisplayWidget):
                                        continue
                                    if getattr(w, "_screen", None) is cursor_screen:
                                        new_owner = w
                                        # Register with coordinator for future lookups
                                        widget._coordinator.register_instance(w, cursor_screen)
                                        break
                                except Exception as e:
                                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                                    continue

                        if new_owner is None:
                            new_owner = owner or widget

                        if owner is not None and owner is not new_owner:
                            try:
                                hint = getattr(owner, "_ctrl_cursor_hint", None)
                                if hint is not None:
                                    try:
                                        hint.cancel_animation()
                                    except Exception as e:
                                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                                    hint.hide()
                                    try:
                                        hint.setOpacity(0.0)
                                    except Exception as e:
                                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                            except Exception as e:
                                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                            owner._ctrl_held = False

                        # Phase 5: Use coordinator for halo ownership
                        widget._coordinator.set_halo_owner(new_owner)
                        try:
                            DisplayWidget._halo_owner = new_owner
                        except Exception as e:
                            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                        owner = new_owner

                if owner is None:
                    owner = widget

                try:
                    local_pos = owner.mapFromGlobal(global_pos)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    try:
                        local_pos = owner.rect().center()
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                        local_pos = None

                if local_pos is not None:
                    try:
                        # In hard-exit mode the halo should always be
                        # visible while the cursor is over an active
                        # DisplayWidget, without requiring Ctrl to be
                        # held. On the first move we trigger a fade-in;
                        # subsequent moves just reposition the halo.
                        #
                        # IMPORTANT: Check hard_exit on the OWNER widget, not widget,
                        # because multiple DisplayWidgets install eventFilters and
                        # self might not be the widget under the cursor.
                        owner_hard_exit = False
                        try:
                            owner_hard_exit = owner._is_hard_exit_enabled()
                        except Exception as e:
                            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                            owner_hard_exit = hard_exit  # fallback to self's value
                        
                        hint = getattr(owner, "_ctrl_cursor_hint", None)
                        halo_hidden = hint is None or not hint.isVisible()
                        
                        # In hard exit mode, always show halo on mouse move
                        # Phase 5: Use coordinator for halo ownership
                        if owner_hard_exit:
                            if widget._coordinator.halo_owner is None or halo_hidden:
                                # Fade in if halo owner not set OR if halo is hidden
                                widget._coordinator.set_halo_owner(owner)
                                owner._show_ctrl_cursor_hint(local_pos, mode="fade_in")
                            else:
                                # Just reposition
                                owner._show_ctrl_cursor_hint(local_pos, mode="none")
                        elif ctrl_held:
                            # Ctrl mode - show/reposition halo
                            # If halo is hidden (e.g., after settings dialog), fade it in
                            if halo_hidden:
                                widget._coordinator.set_halo_owner(owner)
                                try:
                                    DisplayWidget._halo_owner = owner
                                except Exception as e:
                                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                                owner._show_ctrl_cursor_hint(local_pos, mode="fade_in")
                            else:
                                owner._show_ctrl_cursor_hint(local_pos, mode="none")

                        # Forward halo hover position to the Reddit
                        # widget (if present) so it can manage its own
                        # delayed tooltips over post titles.
                        try:
                            rw = getattr(owner, "reddit_widget", None)
                            if rw is not None and rw.isVisible() and hasattr(rw, "handle_hover"):
                                try:
                                    local_rw_pos = rw.mapFromGlobal(global_pos)
                                except Exception as e:
                                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                                    local_rw_pos = None
                                if local_rw_pos is not None:
                                    rw.handle_hover(local_rw_pos, global_pos)
                        except Exception as e:
                            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                    except Exception as e:
                        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    except MemoryError:
        logger.error("[DISPLAY_WIDGET] eventFilter MemoryError; resetting halo/focus", exc_info=True)
        recover_from_event_filter_memory_error(widget, widget._coordinator)
        return False
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    return QWidget.eventFilter(widget, watched, event)

def recover_from_event_filter_memory_error(widget, coordinator: Optional["MultiMonitorCoordinator"]) -> None:
    """Best-effort recovery when eventFilter runs out of memory."""
    try:
        hint = getattr(widget, "_ctrl_cursor_hint", None)
        if hint is not None:
            try:
                hint.cancel_animation()
            except Exception:
                pass
            hint.hide()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    if coordinator is None:
        return

    try:
        coordinator.set_halo_owner(None)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    try:
        coordinator.release_focus(widget)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

