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

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPaintEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import Shiboken

from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve
from core.logging.logger import get_logger
from rendering.multi_monitor_coordinator import get_coordinator

logger = get_logger(__name__)


HALO_BASE_DIAMETER = 48
HALO_SCALE = 0.8
HALO_DIAMETER = int(round(HALO_BASE_DIAMETER * HALO_SCALE))


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
        # Match the 2.6 reference footprint (48px * 0.8 scale).
        self.resize(HALO_DIAMETER, HALO_DIAMETER)
        self._opacity = 1.0
        self._shape: str = "circle"  # circle, ring, crosshair, diamond, dot
        self._animation_id: Optional[str] = None
        self._animation_manager = AnimationManager()
        self._is_fading_out = False  # Track fade state to prevent interference

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

    def set_shape(self, shape: str) -> None:
        """Set the halo shape. Valid: circle, ring, crosshair, diamond, dot, cursor_triangle."""
        valid = {"circle", "ring", "crosshair", "diamond", "dot", "cursor_triangle"}
        self._shape = shape if shape in valid else "circle"
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        """Paint the halo in the configured shape with drop shadow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        color = QColor(255, 255, 255, 200)
        shadow_offset = 2
        shadow_color = QColor(0, 0, 0, 80)

        r = min(self.width(), self.height()) - 8
        cx = self.width() // 2
        cy = self.height() // 2
        inner_radius = max(2, r // 6)
        shape = self._shape

        if shape == "ring":
            self._paint_ring(painter, cx, cy, r, color, shadow_color, shadow_offset)
        elif shape == "crosshair":
            self._paint_crosshair(painter, cx, cy, r, color, shadow_color, shadow_offset)
        elif shape == "diamond":
            self._paint_diamond(painter, cx, cy, r, color, shadow_color, shadow_offset)
        elif shape == "dot":
            self._paint_dot(painter, cx, cy, inner_radius * 2, color, shadow_color, shadow_offset)
        elif shape == "cursor_triangle":
            self._paint_cursor_triangle(painter, cx, cy, r, color, shadow_color, shadow_offset)
        else:
            self._paint_circle(painter, cx, cy, r, inner_radius, color, shadow_color, shadow_offset)
        painter.end()

    def _paint_circle(self, p, cx, cy, r, ir, color, shadow, so):
        """Default circle: ring + center dot."""
        pen = p.pen()
        pen.setColor(shadow); pen.setWidth(5)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(4 + so, 4 + so, r, r)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(shadow)
        p.drawEllipse(cx - ir + so, cy - ir + so, ir * 2, ir * 2)
        pen.setColor(color); pen.setWidth(3)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(4, 4, r, r)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(color)
        p.drawEllipse(cx - ir, cy - ir, ir * 2, ir * 2)

    def _paint_ring(self, p, cx, cy, r, color, shadow, so):
        """Ring only — no center dot."""
        pen = p.pen()
        pen.setColor(shadow); pen.setWidth(5)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(4 + so, 4 + so, r, r)
        pen.setColor(color); pen.setWidth(3)
        p.setPen(pen)
        p.drawEllipse(4, 4, r, r)

    def _paint_crosshair(self, p, cx, cy, r, color, shadow, so):
        """Crosshair: two perpendicular lines with a gap in the center."""
        from PySide6.QtCore import QLineF
        half = r // 2
        gap = max(3, r // 8)
        pen = p.pen()
        pen.setWidth(3)
        for col, dx, dy in ((shadow, so, so), (color, 0, 0)):
            pen.setColor(col); p.setPen(pen)
            p.drawLine(QLineF(cx - half + dx, cy + dy, cx - gap + dx, cy + dy))
            p.drawLine(QLineF(cx + gap + dx, cy + dy, cx + half + dx, cy + dy))
            p.drawLine(QLineF(cx + dx, cy - half + dy, cx + dx, cy - gap + dy))
            p.drawLine(QLineF(cx + dx, cy + gap + dy, cx + dx, cy + half + dy))

    def _paint_diamond(self, p, cx, cy, r, color, shadow, so):
        """Diamond (rotated square)."""
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF as QPF
        half = r // 2
        pts = [QPF(cx, cy - half), QPF(cx + half, cy), QPF(cx, cy + half), QPF(cx - half, cy)]
        pen = p.pen()
        pen.setWidth(3)
        for col, dx, dy in ((shadow, so, so), (color, 0, 0)):
            pen.setColor(col); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            shifted = QPolygonF([QPF(pt.x() + dx, pt.y() + dy) for pt in pts])
            p.drawPolygon(shifted)

    def _paint_dot(self, p, cx, cy, d, color, shadow, so):
        """Dot only — filled circle, no ring."""
        r = max(4, d)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(shadow)
        p.drawEllipse(cx - r // 2 + so, cy - r // 2 + so, r, r)
        p.setBrush(color)
        p.drawEllipse(cx - r // 2, cy - r // 2, r, r)

    def _paint_cursor_triangle(self, p, cx, cy, r, color, shadow, so):
        """Three elongated arrow-tip triangles merged at center, slightly left-slanted.

        Each triangle has a sharp outer tip and a wide inner base meeting at the
        centre, creating a 3-pointed star.  The whole shape is rotated ~15 degrees
        counter-clockwise so it reads as a left-leaning cursor.
        """
        import math
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF as QPF

        half = r / 2.0
        # Outer tip distance from centre; inner base half-width
        tip_r   = half * 0.95   # how far each tip extends
        base_r  = half * 0.38   # radius of the inner base arc
        base_hw = half * 0.28   # half-width of each triangle base

        def rot(angle_deg):
            a = math.radians(angle_deg)
            return math.cos(a), math.sin(a)

        # Three arms: primary tip at top-left (135°), then 120° apart
        arm_angles = [135.0, 255.0, 15.0]
        pts = []
        for ang in arm_angles:
            # Tip point
            tx, ty = rot(ang)
            tip = QPF(cx + tx * tip_r, cy - ty * tip_r)

            # Base points: perpendicular to arm, centred at base_r behind the tip
            perp_l = ang + 90.0
            perp_r = ang - 90.0
            lx, ly = rot(perp_l)
            rx, ry = rot(perp_r)
            back_x, back_y = rot(ang + 180.0)
            bcx = cx + back_x * base_r
            bcy = cy - back_y * base_r
            bl = QPF(bcx + lx * base_hw, bcy - ly * base_hw)
            br = QPF(bcx + rx * base_hw, bcy - ry * base_hw)

            pts += [tip, bl, br]

        # Build filled star: tip0, base0L, base0R, tip1, base1L, base1R, tip2, base2L, base2R
        # Reorder to trace the outline: tip0 -> base0R -> base1L -> tip1 -> base1R -> base2L -> tip2 -> base2R -> base0L
        outline = [
            pts[0],  # tip0
            pts[2],  # base0R
            pts[4],  # base1L
            pts[3],  # tip1
            pts[5],  # base1R
            pts[7],  # base2L
            pts[6],  # tip2
            pts[8],  # base2R
            pts[1],  # base0L
        ]

        pen = p.pen()
        pen.setWidth(2)
        for col, dx, dy in ((shadow, so, so), (color, 0, 0)):
            shifted = QPolygonF([QPF(pt.x() + dx, pt.y() + dy) for pt in outline])
            pen.setColor(col)
            p.setPen(pen)
            p.setBrush(col)
            p.drawPolygon(shifted)
    
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
            
            # Set guard so DisplayWidget skips halo repositioning for this event
            # (prevents feedback loop: halo forward → reposition halo → jitter)
            parent._halo_forwarding = True
            try:
                QApplication.sendEvent(parent, new_event)
            finally:
                parent._halo_forwarding = False
        except Exception:
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
                except Exception:
                    logger.debug("[HALO] Direct halo routing failed", exc_info=True)
            if not handled_direct:
                # DEBUG_WHEEL_TRACE: use postEvent so the app-wide filters observe it.
                QApplication.sendEvent(parent, new_event)
            event.accept()
            logger.debug("[HALO] Wheel event forwarded to parent (direct=%s)", handled_direct)
        except Exception:
            logger.debug("Failed to forward wheel event to parent", exc_info=True)
    
    def cancel_animation(self) -> None:
        """Cancel any running fade animation."""
        if self._animation_id is not None:
            try:
                self._animation_manager.cancel_animation(self._animation_id)
            except Exception as e:
                logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            self._animation_id = None
        self._is_fading_out = False
    
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
                self._is_fading_out = False
                # CRITICAL: Show widget BEFORE setting opacity to 0.0
                # Otherwise the widget stays hidden even after animation
                if not self.isVisible():
                    self.show()
                    # Force immediate visibility update
                    self.raise_()
                self.setWindowOpacity(0.0)
                self._opacity = 0.0
            else:
                self._is_fading_out = True
                self.setWindowOpacity(1.0)
                self._opacity = 1.0
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
                self._is_fading_out = False
                try:
                    self.hide()
                except Exception as e:
                    logger.debug("[CURSOR_HALO] Exception suppressed: %s", e)
            else:
                # Ensure full opacity after fade in completes
                try:
                    self.setWindowOpacity(1.0)
                    self._opacity = 1.0
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
        except Exception:
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
