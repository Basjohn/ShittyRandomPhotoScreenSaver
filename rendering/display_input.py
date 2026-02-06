"""Display Input & Cursor Halo - Extracted from display_widget.py.

Contains cursor halo management (show/hide/fade/inactivity), mouse press
and mouse move event handling with Reddit click routing.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QMouseEvent

from core.logging.logger import get_logger
from widgets.cursor_halo import CursorHaloWidget

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def ensure_ctrl_cursor_hint(widget) -> None:
    """Create the cursor halo widget if it doesn't exist."""
    if widget._ctrl_cursor_hint is not None:
        return
    widget._ctrl_cursor_hint = CursorHaloWidget(widget)
    if widget._resource_manager:
        try:
            widget._resource_manager.register_qt(
                widget._ctrl_cursor_hint,
                description="Cursor halo hint widget",
            )
        except Exception:
            pass

def show_ctrl_cursor_hint(widget, pos, mode: str = "none") -> None:
    """Show/animate the cursor halo at the given position.
    
    Args:
        pos: Position to center the halo on (local widget coordinates)
        mode: "none" for reposition only, "fade_in" or "fade_out" for animation
    """
    ensure_ctrl_cursor_hint(widget, )
    hint = widget._ctrl_cursor_hint
    if hint is None:
        return

    # Do not show the halo while the settings dialog is active.
    try:
        from rendering.multi_monitor_coordinator import get_coordinator

        if get_coordinator().settings_dialog_active:
            hide_ctrl_cursor_hint(widget, immediate=True)
            return
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    # Normalize incoming position to QPoint for consistency
    try:
        if isinstance(pos, QPoint):
            local_point = QPoint(pos)
        else:
            local_point = QPoint(int(pos.x()), int(pos.y()))
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return
    rect = widget.rect()
    context_menu_active = bool(getattr(widget, "_context_menu_active", False))
    halo_slack = float(max(0.0, getattr(widget, "_halo_out_of_bounds_slack", 8.0)))

    if mode != "fade_out":
        if not rect.contains(local_point):
            should_hide = (
                local_point.x() < rect.left() - halo_slack
                or local_point.y() < rect.top() - halo_slack
                or local_point.x() > rect.right() + halo_slack
                or local_point.y() > rect.bottom() + halo_slack
            )
            if should_hide:
                hide_ctrl_cursor_hint(widget, immediate=True)
                return
        if context_menu_active:
            hide_ctrl_cursor_hint(widget, immediate=True)
            return
        widget._halo_last_local_pos = QPoint(local_point)
        widget._last_halo_activity_ts = time.monotonic()
        reset_halo_inactivity_timer(widget, )
        hint.move_to(local_point.x(), local_point.y())
    else:
        cancel_halo_inactivity_timer(widget, )

    if mode == "fade_in":
        # fade_in() handles show() internally
        hint.fade_in()
    elif mode == "fade_out":
        hint.fade_out()
    else:
        # mode == "none" - just reposition, ensure visible without animation
        if not hint.isVisible():
            hint.setWindowOpacity(1.0)
            hint.show()
            hint.raise_()

def hide_ctrl_cursor_hint(widget, *, immediate: bool = False) -> None:
    """Hide the cursor halo widget."""
    hint = widget._ctrl_cursor_hint
    if hint is None:
        return
    cancel_halo_inactivity_timer(widget, )
    try:
        if immediate:
            hint.cancel_animation()
            hint.hide()
        else:
            hint.fade_out()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        hint.hide()

def reset_halo_inactivity_timer(widget) -> None:
    """Restart the inactivity timer that hides the halo after inactivity."""
    timeout_sec = float(max(0.5, getattr(widget, "_halo_activity_timeout", 2.0)))
    timeout_ms = int(timeout_sec * 1000)

    timer = getattr(widget, "_halo_inactivity_timer", None)
    if timer is None:
        timer = QTimer(widget)
        timer.setSingleShot(True)
        timer.timeout.connect(widget._on_halo_inactivity_timeout)
        widget._halo_inactivity_timer = timer
        if widget._resource_manager:
            try:
                widget._resource_manager.register_qt(
                    timer, description="Halo inactivity timeout timer",
                )
            except Exception:
                pass

    try:
        timer.start(timeout_ms)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def cancel_halo_inactivity_timer(widget) -> None:
    timer = getattr(widget, "_halo_inactivity_timer", None)
    if timer is None:
        return
    try:
        timer.stop()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def on_halo_inactivity_timeout(widget) -> None:
    """Hide the halo if there has been no local movement recently."""
    now = time.monotonic()
    last = float(getattr(widget, "_last_halo_activity_ts", 0.0) or 0.0)
    timeout_sec = float(max(0.5, getattr(widget, "_halo_activity_timeout", 2.0)))
    if last <= 0.0 or (now - last) >= timeout_sec:
        hide_ctrl_cursor_hint(widget, immediate=True)

def handle_mousePressEvent(widget, event: QMouseEvent) -> None:
    """Handle mouse press - exit on any click unless hard exit is enabled."""
    # Phase 5: Use coordinator for global Ctrl state
    ctrl_mode_active = widget._ctrl_held or widget._coordinator.ctrl_held
    
    # Phase E: Delegate right-click context menu to InputHandler if available
    # This ensures effect invalidation is triggered consistently before menu popup
    if event.button() == Qt.MouseButton.RightButton:
        if widget._is_hard_exit_enabled() or ctrl_mode_active:
            if widget._input_handler is not None:
                try:
                    # InputHandler will trigger effect invalidation and emit context_menu_requested
                    if widget._input_handler.handle_mouse_press(event, widget._coordinator.ctrl_held):
                        event.accept()
                        return
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            # Fallback: direct context menu show
            widget._show_context_menu(event.globalPosition().toPoint())
            event.accept()
            return
        # Normal mode without Ctrl - fall through to exit
    
    if widget._is_hard_exit_enabled() or ctrl_mode_active:
        # Delegate widget click routing to InputHandler
        handled = False
        reddit_handled = False
        
        reddit_url = None
        if widget._input_handler is not None:
            try:
                handled, reddit_handled, reddit_url = widget._input_handler.route_widget_click(
                    event,
                    getattr(widget, "spotify_volume_widget", None),
                    getattr(widget, "media_widget", None),
                    getattr(widget, "reddit_widget", None),
                    getattr(widget, "reddit2_widget", None),
                    getattr(widget, "gmail_widget", None),
                    getattr(widget, "imgur_widget", None),
                )
                logger.info("[REDDIT] route_widget_click returned: handled=%s reddit_handled=%s screen=%s",
                           handled, reddit_handled, widget.screen_index)
            except Exception:
                logger.debug("[INPUT] Widget click routing failed", exc_info=True)

        if handled:
            # Request exit after Reddit clicks
            reddit_exit_on_click = getattr(widget, "_reddit_exit_on_click", True)
            logger.info("[REDDIT] Click routed: handled=%s reddit_handled=%s reddit_exit_on_click=%s screen=%s", 
                        handled, reddit_handled, reddit_exit_on_click, widget.screen_index)
            if reddit_handled and reddit_exit_on_click:
                # Detect display configuration for Reddit link handling:
                # A) All displays covered + hard_exit: Exit immediately
                # B) All displays covered + Ctrl held: Exit immediately
                # C) MC mode (primary NOT covered): Stay open, bring browser to foreground
                #
                # System-agnostic: uses QGuiApplication.primaryScreen() which is the
                # OS-configured primary, not necessarily screen index 0.
                
                this_is_primary = False
                primary_is_covered = False
                try:
                    from PySide6.QtGui import QGuiApplication
                    primary_screen = QGuiApplication.primaryScreen()
                    
                    # Check if THIS widget is on the primary screen
                    if widget._screen is not None and primary_screen is not None:
                        this_is_primary = (widget._screen is primary_screen)
                    
                    # If THIS is primary, then primary is definitely covered
                    if this_is_primary:
                        primary_is_covered = True
                    else:
                        # Check if primary screen has a DisplayWidget registered
                        if primary_screen is not None:
                            primary_widget = widget._coordinator.get_instance_for_screen(primary_screen)
                            primary_is_covered = (primary_widget is not None)
                except Exception as e:
                    logger.debug("[DISPLAY_WIDGET] Exception checking primary screen: %s", e)
                    # Fallback: assume primary is NOT covered (MC mode behavior)
                    # This is safer than assuming exit - user can always press Esc
                    primary_is_covered = False
                
                logger.info("[REDDIT] Exit check: this_is_primary=%s primary_is_covered=%s exiting=%s screen=%s",
                            this_is_primary, primary_is_covered, widget._exiting, widget.screen_index)
                
                if primary_is_covered:
                    # Cases A & B: Primary is covered, user wants to leave screensaver
                    logger.info("[REDDIT] Primary covered; requesting immediate exit")
                    if not widget._exiting:
                        widget._exiting = True
                        if reddit_url:
                            widget._pending_reddit_url = reddit_url
                        # Bring browser to foreground after windows start closing
                        def _bring_browser_foreground():
                            try:
                                from widgets.reddit_widget import _try_bring_reddit_window_to_front
                                _try_bring_reddit_window_to_front()
                            except Exception as e:
                                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                        QTimer.singleShot(300, _bring_browser_foreground)
                        widget.exit_requested.emit()
                else:
                    # Case C: MC mode - primary not covered, stay open
                    # Delay browser foreground to give browser time to open the URL
                    # and create a window with "reddit" in the title
                    logger.info("[REDDIT] MC mode (primary not covered); staying open, will bring browser to foreground after delay")
                    url_to_open = reddit_url
                    if url_to_open:
                        try:
                            from PySide6.QtCore import QUrl
                            from PySide6.QtGui import QDesktopServices
                            if QDesktopServices.openUrl(QUrl(url_to_open)):
                                logger.info("[REDDIT] MC mode: opened %s immediately", url_to_open)
                            else:
                                logger.warning("[REDDIT] MC mode: QDesktopServices rejected %s", url_to_open)
                        except Exception:
                            logger.debug("[REDDIT] MC mode immediate open failed; falling back", exc_info=True)
                            url_to_open = None
                    if not url_to_open:
                        logger.info("[REDDIT] MC mode: no URL opened immediately; skipping foreground attempt")
                    else:
                        def _bring_browser_foreground_mc():
                            try:
                                from widgets.reddit_widget import _try_bring_reddit_window_to_front
                                _try_bring_reddit_window_to_front()
                                logger.debug("[REDDIT] MC mode: browser foreground attempted")
                            except Exception as e:
                                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
                        QTimer.singleShot(300, _bring_browser_foreground_mc)
                
            event.accept()
            return

        # In interaction mode, don't exit on unhandled clicks
        event.accept()
        return

    logger.info(f"Mouse clicked at ({event.pos().x()}, {event.pos().y()}), requesting exit")
    widget._exiting = True
    # Deferred Reddit URLs are now flushed centrally by DisplayManager after teardown.
    widget.exit_requested.emit()
    event.accept()

def handle_mouseMoveEvent(widget, event: QMouseEvent) -> None:
    """Handle mouse move - exit if moved beyond threshold (unless hard exit)."""
    # Don't exit while context menu is active
    if widget._context_menu_active:
        event.accept()
        return
    
    # Phase 5: Use coordinator for global Ctrl state
    ctrl_mode_active = widget._coordinator.ctrl_held
    hard_exit = widget._is_hard_exit_enabled()
    if hard_exit or ctrl_mode_active:
        # Show/update halo position
        local_pos = event.pos()
        hint = widget._ctrl_cursor_hint
        if hint is not None:
            halo_hidden = not hint.isVisible()
            if halo_hidden:
                widget._coordinator.set_halo_owner(widget)
                show_ctrl_cursor_hint(widget, local_pos, mode="fade_in")
            else:
                show_ctrl_cursor_hint(widget, local_pos, mode="none")
        
        # Delegate volume drag to InputHandler
        if widget._input_handler is not None:
            try:
                widget._input_handler.route_volume_drag(
                    event.pos(), getattr(widget, "spotify_volume_widget", None)
                )
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        event.accept()
        return

    # Store initial position on first move
    if widget._initial_mouse_pos is None:
        widget._initial_mouse_pos = event.pos()
        event.accept()
        return
    
    # Calculate distance from initial position
    dx = event.pos().x() - widget._initial_mouse_pos.x()
    dy = event.pos().y() - widget._initial_mouse_pos.y()
    distance = (dx * dx + dy * dy) ** 0.5
    
    # Exit if moved beyond threshold
    if distance > widget._mouse_move_threshold:
        logger.info(f"Mouse moved {distance:.1f} pixels, requesting exit")
        widget._exiting = True
        widget.exit_requested.emit()
    
    event.accept()

