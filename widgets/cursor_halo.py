"""
Cursor halo widget for Ctrl-click interaction mode.

Provides a visual indicator (ring + dot) that follows the cursor when
Ctrl is held, allowing users to interact with widgets without triggering
the screensaver exit.

The halo is implemented as a top-level frameless window (not a child widget)
so it floats above all other widgets including QOpenGLWidget-based overlays
like the Spotify visualizer and volume slider. This avoids Z-order fighting
with GL widgets that have their own native window handles.

Mouse events are forwarded to the parent widget so context menus and clicks
still work. The mouse cursor is hidden when the halo is visible.
"""
from typing import Optional
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPaintEvent, QMouseEvent, QWheelEvent
from shiboken6 import Shiboken

from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve
from core.logging.logger import get_logger
from rendering.multi_monitor_coordinator import get_coordinator

logger = get_logger(__name__)


class CursorHaloWidget(QWidget):
    """
    Visual cursor indicator for Ctrl-held interaction mode.
    
    Displays a semi-transparent ring with a center dot that follows
    the cursor position. Supports fade-in/fade-out animations.
    
    Implemented as a top-level frameless window to guarantee it stays
    above QOpenGLWidget-based overlays (Spotify visualizer, volume slider).
    Mouse events are forwarded to the parent widget for context menu support.
    """
    
    def __init__(self, parent: QWidget) -> None:
        # Create as top-level frameless window, not a child widget
        # This ensures it floats above all sibling widgets including GL overlays
        super().__init__(
            None,  # No parent - top-level window
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |  # Exclude from taskbar/alt-tab
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self._parent_widget = parent  # Keep reference for coordinate mapping and event forwarding
        
        # Don't use WA_TransparentForMouseEvents - we need to receive and forward events
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(False)
        # Hide mouse cursor over halo - the halo IS the cursor
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.resize(60, 60)
        self._opacity = 1.0
        self._animation_id: Optional[str] = None
        self._animation_manager = AnimationManager()

    def set_parent_widget(self, parent: QWidget) -> None:
        """Refresh the parent widget reference after display rebuilds."""
        if parent is not None and Shiboken.isValid(parent):
            self._parent_widget = parent

    def setOpacity(self, value: float) -> None:
        """Set the halo opacity (0.0 to 1.0)."""
        try:
            self._opacity = max(0.0, min(1.0, float(value)))
            self.setWindowOpacity(self._opacity)
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            self._opacity = 1.0
        self.update()

    def opacity(self) -> float:
        """Get the current opacity."""
        return float(self._opacity)

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        """Paint the halo ring and center dot with drop shadow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # No background fill needed - WA_TranslucentBackground handles it
        
        base_alpha = 200
        alpha = int(max(0.0, min(1.0, self._opacity)) * base_alpha)
        color = QColor(255, 255, 255, alpha)
        
        # Shadow parameters
        shadow_offset = 2
        shadow_alpha = int(max(0.0, min(1.0, self._opacity)) * 80)
        shadow_color = QColor(0, 0, 0, shadow_alpha)

        r = min(self.width(), self.height()) - 8
        cx = self.width() // 2
        cy = self.height() // 2
        inner_radius = max(2, r // 6)

        # Draw shadow ring (offset down-right)
        pen = painter.pen()
        pen.setColor(shadow_color)
        pen.setWidth(5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(4 + shadow_offset, 4 + shadow_offset, r, r)
        
        # Draw shadow dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_color)
        painter.drawEllipse(
            cx - inner_radius + shadow_offset,
            cy - inner_radius + shadow_offset,
            inner_radius * 2, inner_radius * 2
        )

        # Draw main outer ring
        pen.setColor(color)
        pen.setWidth(4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(4, 4, r, r)

        # Draw main inner dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(cx - inner_radius, cy - inner_radius, inner_radius * 2, inner_radius * 2)
        painter.end()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Forward mouse press to parent widget."""
        self._forward_mouse_event(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Forward mouse release to parent widget."""
        self._forward_mouse_event(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Forward mouse move to parent widget."""
        self._forward_mouse_event(event)
    
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Forward double click to parent widget."""
        self._forward_mouse_event(event)
    
    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        """Forward wheel events to the parent widget."""
        self._forward_wheel_event(event)
    
    def _resolve_target_widget(self) -> Optional[QWidget]:
        """Return a valid DisplayWidget target, refreshing stale references."""
        parent = self._parent_widget
        if parent is not None and Shiboken.isValid(parent):
            return parent

        target = None
        coordinator = None
        try:
            coordinator = get_coordinator()
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            coordinator = None

        if coordinator is not None:
            target = coordinator.halo_owner or coordinator.focus_owner

        if target is None and coordinator is not None:
            try:
                instances = coordinator.get_all_instances()
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
                instances = []
            for inst in instances:
                if inst is not None and Shiboken.isValid(inst):
                    target = inst
                    break

        if target is not None and Shiboken.isValid(target):
            self._parent_widget = target
            return target
        return None

    def _forward_mouse_event(self, event: QMouseEvent) -> None:
        """Forward a mouse event to the parent widget at the correct position."""
        parent = self._resolve_target_widget()
        if parent is None:
            return
        try:
            # Map halo-local position to global, then to parent-local
            global_pos = self.mapToGlobal(event.pos())
            local_pos = parent.mapFromGlobal(global_pos)
            
            # Create a new event with the mapped position
            new_event = QMouseEvent(
                event.type(),
                local_pos,
                global_pos,
                event.button(),
                event.buttons(),
                event.modifiers()
            )
            
            # Post the event to the parent widget
            QApplication.sendEvent(parent, new_event)
        except Exception as e:
            logger.debug("Failed to forward mouse event to parent", exc_info=True)
    
    def _forward_wheel_event(self, event: QWheelEvent) -> None:
        """Forward a wheel event to the parent widget."""
        parent = self._resolve_target_widget()
        if parent is None:
            return
        try:
            global_pos = event.globalPosition()
            local_point = parent.mapFromGlobal(global_pos.toPoint())
            local_pos = QPointF(local_point)
            logger.debug(
                "[HALO] Forwarding wheel event to parent: local=%s global=(%.1f, %.1f) delta=%s",
                local_pos,
                global_pos.x(),
                global_pos.y(),
                event.angleDelta(),
            )
            new_event = QWheelEvent(
                local_pos,
                global_pos,
                event.pixelDelta(),
                event.angleDelta(),
                event.buttons(),
                event.modifiers(),
                event.phase(),
                event.inverted(),
                event.source(),
            )
            # DEBUG_WHEEL_TRACE: parent metadata for easy removal once routing fixed.
            logger.debug(
                "[HALO] Wheel target parent id=%s screen=%s object=%s",
                hex(id(parent)),
                getattr(parent, "screen_index", None),
                getattr(parent, "objectName", None) or parent.__class__.__name__,
            )
            handled_direct = False
            if hasattr(parent, "handle_forwarded_halo_wheel"):
                try:
                    handled_direct = bool(
                        parent.handle_forwarded_halo_wheel(local_pos, global_pos, event.angleDelta())
                    )
                except Exception as e:
                    logger.debug("[HALO] Direct halo routing failed", exc_info=True)
            if not handled_direct:
                # DEBUG_WHEEL_TRACE: use postEvent so the app-wide filters observe it.
                QApplication.sendEvent(parent, new_event)
            event.accept()
            logger.debug("[HALO] Wheel event forwarded to parent (direct=%s)", handled_direct)
        except Exception as e:
            logger.debug("Failed to forward wheel event to parent", exc_info=True)
    
    def cancel_animation(self) -> None:
        """Cancel any running fade animation."""
        if self._animation_id is not None:
            try:
                self._animation_manager.cancel_animation(self._animation_id)
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            self._animation_id = None
    
    def fade_in(self, on_finished: Optional[callable] = None) -> None:
        """Fade in the halo over 600ms."""
        self._start_fade(fade_in=True, on_finished=on_finished)
    
    def fade_out(self, on_finished: Optional[callable] = None) -> None:
        """Fade out the halo over 1200ms."""
        self._start_fade(fade_in=False, on_finished=on_finished)
    
    def _start_fade(self, fade_in: bool, on_finished: Optional[callable] = None) -> None:
        """Start a fade animation."""
        self.cancel_animation()
        
        try:
            if fade_in:
                self.setWindowOpacity(0.0)
                # Show widget now that opacity is 0.0 to prevent flash
                if not self.isVisible():
                    self.show()
            else:
                self.setWindowOpacity(1.0)
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)

        duration_ms = 600 if fade_in else 1200
        start_val = 0.0 if fade_in else 1.0
        end_val = 1.0 if fade_in else 0.0
        
        def _on_tick(progress: float) -> None:
            try:
                value = start_val + (end_val - start_val) * progress
                self.setWindowOpacity(float(value))
                self._opacity = float(value)
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)

        def _on_anim_finished() -> None:
            if not fade_in:
                try:
                    self.hide()
                except Exception as e:
                    logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            try:
                self.setWindowOpacity(1.0)
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            self._animation_id = None
            if on_finished:
                try:
                    on_finished()
                except Exception as e:
                    logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)

        try:
            # AnimationManager uses seconds, not milliseconds
            duration_sec = duration_ms / 1000.0
            self._animation_id = self._animation_manager.animate_custom(
                duration=duration_sec,
                update_callback=_on_tick,
                on_complete=_on_anim_finished,
                easing=EasingCurve.QUAD_OUT,
            )
        except Exception as e:
            logger.debug("Failed to start halo animation via AnimationManager", exc_info=True)
    
    def show_at(self, x: int, y: int) -> None:
        """Show the halo centered at the given local position.
        
        Args:
            x, y: Position in parent widget coordinates (will be mapped to global)
        """
        # Don't show if settings dialog is active
        try:
            from rendering.multi_monitor_coordinator import get_coordinator
            if get_coordinator().settings_dialog_active:
                return
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
        
        size = self.size()
        # Convert local coordinates to global screen coordinates
        if self._parent_widget is not None:
            try:
                global_pos = self._parent_widget.mapToGlobal(
                    self._parent_widget.rect().topLeft()
                )
                global_x = global_pos.x() + x - size.width() // 2
                global_y = global_pos.y() + y - size.height() // 2
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
                global_x = x - size.width() // 2
                global_y = y - size.height() // 2
        else:
            global_x = x - size.width() // 2
            global_y = y - size.height() // 2
        
        self.move(global_x, global_y)
        self.show()
    
    def move_to(self, x: int, y: int) -> None:
        """Move the halo to be centered at the given local position.
        
        Args:
            x, y: Position in parent widget coordinates (will be mapped to global)
        """
        size = self.size()
        if self._parent_widget is not None:
            try:
                global_pos = self._parent_widget.mapToGlobal(
                    self._parent_widget.rect().topLeft()
                )
                global_x = global_pos.x() + x - size.width() // 2
                global_y = global_pos.y() + y - size.height() // 2
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
                global_x = x - size.width() // 2
                global_y = y - size.height() // 2
        else:
            global_x = x - size.width() // 2
            global_y = y - size.height() // 2
        
        self.move(global_x, global_y)
    
    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Ensure halo fades out when destroyed."""
        try:
            # Cancel any running animation
            self.cancel_animation()
            # Fade out before closing
            if self.isVisible():
                self.fade_out(on_finished=lambda: event.accept())
            else:
                event.accept()
        except Exception as e:
            logger.debug("[CURSOR_HALO] Exception suppressed during close: %s", e)
            event.accept()
